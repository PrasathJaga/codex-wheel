import copy
import importlib.util
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contract", ROOT / "preflight/petclinic_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.before = {"owners": [{"id": 1, "name": "A"}],
                       "pets": [{"id": 2, "owner_id": 1, "name": "P", "birth_date": "2019-01-01", "type_id": 1},
                                {"id": 3, "owner_id": 1, "name": "Other"}],
                       "visits": [{"id": 4, "pet_id": 2, "description": "history"}],
                       "types": [{"id": 1, "name": "cat"}]}
        self.expected = {"name": "Updated", "birth_date": "2020-01-02", "type_id": 1}
        self.after = copy.deepcopy(self.before)
        self.after["pets"][0].update(self.expected)

    def test_healthy_update(self):
        self.assertEqual(contract.verify_update(self.before, self.after, 2, self.expected)["verdict"], "healthy_contract_observed")

    def test_reject_owner_history_and_unrelated_changes(self):
        mutations = [lambda s: s["pets"][0].update(owner_id=9),
                     lambda s: s["visits"].clear(),
                     lambda s: s["visits"][0].update(pet_id=3),
                     lambda s: s["visits"][0].update(description="lost"),
                     lambda s: s["pets"][1].update(name="corrupted"),
                     lambda s: s["types"][0].update(name="wrong")]
        for mutate in mutations:
            state = copy.deepcopy(self.after)
            mutate(state)
            with self.subTest(mutation=mutate), self.assertRaises(contract.ContractFailure):
                contract.verify_update(self.before, state, 2, self.expected)

    def test_success_response_cannot_substitute_for_effect(self):
        with self.assertRaises(contract.ContractFailure):
            contract.verify_update(self.before, self.before, 2, self.expected)

    def test_unknown_missing_and_vacuous_evidence_rejected(self):
        for table, value in (("visits", None), ("visits", []), ("owners", [])):
            state = copy.deepcopy(self.before)
            state[table] = value
            with self.subTest(table=table, value=value), self.assertRaises(contract.ContractFailure):
                contract.verify_update(state, self.after, 2, self.expected)
        same = {k: self.before["pets"][0][k] for k in self.expected}
        with self.assertRaises(contract.ContractFailure):
            contract.verify_update(self.before, self.before, 2, same)

    def test_workflow_executes_exact_host_verifier(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/external-preflight.yml").read_text())
        job = workflow["jobs"]["external-baseline"]
        step = next(s for s in job["steps"] if s.get("name") == "Independent committed-state contract checks")
        code = step["run"].split("python - <<'PY_CONTRACT'\n", 1)[1].rsplit("PY_CONTRACT", 1)[0]
        self.assertTrue(code.rstrip().endswith((ROOT / "preflight/petclinic_contract.py").read_text().rstrip()))
        self.assertTrue(code.startswith((ROOT / "preflight/petclinic_adapter.py").read_text()))
        self.assertEqual(job["permissions"], {})
        self.assertNotIn("checkout", "\n".join(s.get("uses", "") for s in job["steps"]))
        self.assertNotIn("type=bind", code)
        self.assertNotIn("docker.sock", code)
        self.assertNotIn("${{ secrets", code)
        self.assertIn('"network", "create", "--internal"', code)
        self.assertIn('"type=volume,src=" + volume + ",dst=/work,readonly"', code)


if __name__ == "__main__":
    unittest.main()
