"""Bounded profile-update experiment interface; trusted host code only."""
import copy
from datetime import date
import hashlib
import json
import re

PROTOCOL = "petclinic-profile-v1"
MAX_ACTIONS = 8
EDIT_PATHS = frozenset({
    "src/main/java/org/springframework/samples/petclinic/rest/controller/v1/PetRestControllerV1.java",
    "src/main/java/org/springframework/samples/petclinic/mapper/PetMapper.java",
    "src/main/java/org/springframework/samples/petclinic/model/Pet.java",
    "src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java",
})


class AdmissionError(ValueError):
    pass


class ExperimentViolation(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise AdmissionError("Unknown or missing fields")


def validate_plan(plan):
    exact(plan, {"protocol", "actions"})
    if plan["protocol"] != PROTOCOL:
        raise AdmissionError("Unsupported protocol")
    actions = plan["actions"]
    if type(actions) is not list or not 1 <= len(actions) <= MAX_ACTIONS:
        raise AdmissionError("Action budget exceeded or empty")
    meaningful = False
    for action in actions:
        if type(action) is not dict:
            raise AdmissionError("Action must be an object")
        op = action.get("op")
        if op == "READ_PET":
            exact(action, {"op", "pet"})
        elif op == "UPDATE_PET_PROFILE":
            exact(action, {"op", "pet", "name", "birth_date", "type"})
            if type(action["name"]) is not str or not re.fullmatch(r"[A-Za-z0-9 ]{0,30}", action["name"]):
                raise AdmissionError("Name outside declared input domain")
            if type(action["birth_date"]) is not str:
                raise AdmissionError("Birth date must be ISO text")
            try:
                birth = date.fromisoformat(action["birth_date"])
            except ValueError as error:
                raise AdmissionError("Invalid birth date") from error
            if birth.isoformat() != action["birth_date"] or not date(2000, 1, 1) <= birth <= date(2025, 12, 31):
                raise AdmissionError("Date outside frozen input domain")
            if action["type"] not in ("original_type", "alternate_type"):
                raise AdmissionError("Unsupported type reference")
            if action["pet"] not in ("visited_pet", "missing_pet"):
                raise AdmissionError("Only declared target can be edited")
            meaningful |= action["pet"] == "visited_pet" and bool(action["name"])
        else:
            raise AdmissionError("Unsupported action")
        if action["pet"] not in ("visited_pet", "unrelated_pet", "missing_pet"):
            raise AdmissionError("Unsupported pet reference")
    if not meaningful:
        raise AdmissionError("Plan has no valid target-update experiment")
    return copy.deepcopy(plan)


def freeze_plan(plan):
    validated = validate_plan(plan)
    return {"plan": validated, "sha256": digest(validated)}


def authenticate_plan(frozen, expected_sha256):
    exact(frozen, {"plan", "sha256"})
    plan = validate_plan(frozen["plan"])
    if type(expected_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise AdmissionError("Missing trusted plan digest")
    if type(frozen["sha256"]) is not str or digest(plan) != frozen["sha256"] or frozen["sha256"] != expected_sha256:
        raise AdmissionError("Frozen plan changed")
    return plan


def admit_pair(baseline, candidate):
    """Compare COMPLETE trusted path/content-hash maps; no model-provided maps."""
    for tree in (baseline, candidate):
        if type(tree) is not dict or not tree:
            raise AdmissionError("Complete nonempty source maps required")
        for path, value in tree.items():
            if type(path) is not str or path.startswith("/") or ".." in path.split("/") or "\\" in path:
                raise AdmissionError("Unsafe source path")
            if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise AdmissionError("Expected SHA-256 source identity")
    if baseline.keys() != candidate.keys():
        raise AdmissionError("File additions/deletions are unsupported")
    changed = sorted(p for p in baseline if baseline[p] != candidate[p])
    if not set(changed) <= EDIT_PATHS:
        raise AdmissionError("Unsupported changed path")
    return {"baseline_map_sha256": digest(baseline), "candidate_map_sha256": digest(candidate),
            "changed_paths": changed, "unchanged_control": not changed}


def execute_plan(frozen, initial, request_fn, snapshot_fn, events, *, expected_sha256):
    """URLs and expected effects derive from validated actions, never model prose."""
    plan = authenticate_plan(frozen, expected_sha256)
    visited_ids = {v["pet_id"] for v in initial["visits"]}
    target = next((p for p in initial["pets"] if p["id"] in visited_ids), None)
    if target is None:
        raise AdmissionError("Seed lacks visited target")
    unrelated = next((p for p in initial["pets"] if p["id"] != target["id"]), None)
    alternate = next((t for t in initial["types"] if t["id"] != target["type_id"]), None)
    original = next((t for t in initial["types"] if t["id"] == target["type_id"]), None)
    if unrelated is None or alternate is None or original is None:
        raise AdmissionError("Seed lacks required controls")
    if any(p["id"] == 2147483647 for p in initial["pets"]):
        raise AdmissionError("Missing-target sentinel exists")
    ids = {"visited_pet": target["id"], "unrelated_pet": unrelated["id"], "missing_pet": 2147483647}
    kinds = {"original_type": original, "alternate_type": alternate}
    expected = copy.deepcopy(initial)
    changed = False
    for action in plan["actions"]:
        pet_id = ids[action["pet"]]
        path = "/api/pets/" + str(pet_id)
        body = None
        if action["op"] == "READ_PET":
            method, expected_status = "GET", 404 if action["pet"] == "missing_pet" else 200
        else:
            method = "PUT"
            body = {"name": action["name"], "birthDate": action["birth_date"], "type": kinds[action["type"]]}
            expected_status = 400 if not action["name"] else 404 if action["pet"] == "missing_pet" else 204
            if expected_status == 204:
                row = next(p for p in expected["pets"] if p["id"] == pet_id)
                fields = {"name": action["name"], "birth_date": action["birth_date"], "type_id": kinds[action["type"]]["id"]}
                changed |= any(row[k] != v for k, v in fields.items())
                row.update(fields)
        status, response = request_fn(method, path, body)
        event = {"action": copy.deepcopy(action), "method": method, "path": path,
                 "body": body, "status": status, "response": response}
        events.append(event)
        state = snapshot_fn()
        event["committed_state"] = state
        if status != expected_status:
            raise ExperimentViolation("Unexpected HTTP outcome at action " + str(len(events)))
        if state != expected:
            raise ExperimentViolation("Committed effects violate contract at action " + str(len(events)))
    if not changed:
        raise AdmissionError("Selected input produces no non-vacuous profile change")
    return {"verdict": "healthy_contract_observed", "plan_sha256": frozen["sha256"],
            "actions": len(events), "pet_id": target["id"], "final_state": expected}
