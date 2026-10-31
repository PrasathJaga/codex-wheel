import copy
import hashlib
import json
from pathlib import Path
import unittest

from preflight import petclinic_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.plans = json.loads((ROOT / "evaluation/petclinic_healthy_plans_v1.json").read_text())
        self.state = {"owners": [{"id": 1}],
                      "pets": [{"id": 2, "owner_id": 1, "name": "Old", "birth_date": "2018-01-01", "type_id": 1},
                               {"id": 3, "owner_id": 1, "name": "Other"}],
                      "visits": [{"id": 4, "pet_id": 2, "description": "retained"}],
                      "types": [{"id": 1, "name": "cat"}, {"id": 2, "name": "dog"}]}

    def fake_request(self, method, path, body):
        pet_id = int(path.rsplit("/", 1)[1])
        if body and not body["name"]:
            return 400, "invalid"
        row = next((p for p in self.state["pets"] if p["id"] == pet_id), None)
        if row is None:
            return 404, "missing"
        if method == "GET":
            return 200, json.dumps(row)
        row.update(name=body["name"], birth_date=body["birthDate"], type_id=body["type"]["id"])
        return 204, ""

    def run_plan(self, frozen, requester=None, events=None):
        return adapter.execute_plan(frozen, copy.deepcopy(self.state), requester or self.fake_request,
                                    lambda: copy.deepcopy(self.state), events if events is not None else [],
                                    expected_sha256=frozen["sha256"])

    def test_two_distinct_public_plans_execute_without_driver_edits(self):
        results = []
        initial = copy.deepcopy(self.state)
        for frozen in self.plans:
            self.state = copy.deepcopy(initial)
            results.append(self.run_plan(frozen))
        self.assertNotEqual(results[0]["plan_sha256"], results[1]["plan_sha256"])
        self.assertEqual([r["actions"] for r in results], [5, 5])

    def test_reject_arbitrary_capabilities_and_budget_overrun(self):
        original = self.plans[0]["plan"]
        for mutate in (
            lambda p: p.update(url="https://example.com"),
            lambda p: p["actions"].append({"op": "SHELL", "command": "cat /secrets"}),
            lambda p: p["actions"][3].update(sql="DROP TABLE pets"),
            lambda p: p["actions"][3].update(pet="/api/owners"),
            lambda p: p["actions"][3].update(birth_date="2030-01-01"),
            lambda p: p["actions"][3].update(name=True),
            lambda p: p.update(actions=p["actions"] * 2),
            lambda p: p.update(actions=[{"op": "READ_PET", "pet": "visited_pet"}]),
        ):
            p = copy.deepcopy(original)
            mutate(p)
            with self.subTest(plan=p), self.assertRaises(adapter.AdmissionError):
                adapter.freeze_plan(p)

    def test_tamper_even_with_recomputed_self_hash_rejected(self):
        original = self.plans[0]
        changed = copy.deepcopy(original)
        changed["plan"]["actions"][3]["name"] = "Changed"
        changed["sha256"] = adapter.digest(changed["plan"])
        with self.assertRaises(adapter.AdmissionError):
            adapter.authenticate_plan(changed, original["sha256"])

    def test_source_admission_preserves_protected_paths(self):
        path = sorted(adapter.EDIT_PATHS)[0]
        base = {path: "a" * 64, "pom.xml": "b" * 64}
        self.assertTrue(adapter.admit_pair(base, base)["unchanged_control"])
        self.assertEqual(adapter.admit_pair(base, {**base, path: "c" * 64})["changed_paths"], [path])
        for candidate in ({**base, "pom.xml": "c" * 64}, {**base, "new.java": "c" * 64}, {path: "a" * 64}):
            with self.assertRaises(adapter.AdmissionError):
                adapter.admit_pair(base, candidate)

    def test_preserve_failure_event_and_committed_evidence(self):
        def corrupt(method, path, body):
            result = self.fake_request(method, path, body)
            if method == "PUT" and result[0] == 204:
                self.state["visits"].clear()
            return result
        events = []
        with self.assertRaises(adapter.ExperimentViolation):
            self.run_plan(self.plans[0], corrupt, events)
        self.assertEqual(events[-1]["status"], 204)
        self.assertEqual(events[-1]["committed_state"]["visits"], [])

    def test_lock_binds_actual_components_and_plan_anchors(self):
        lock = json.loads((ROOT / "evaluation/petclinic_adapter_lock_v1.json").read_text())
        self.assertEqual(lock["public_plan_sha256"], [p["sha256"] for p in self.plans])
        for path, expected in lock["components"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected, path)


if __name__ == "__main__":
    unittest.main()
