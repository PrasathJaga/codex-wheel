"""Prospective evaluation registration; no model calls or external execution."""
import argparse
import copy
import difflib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile

from preflight.petclinic_adapter import AdmissionError, EDIT_PATHS, canonical, digest, exact
from preflight.petclinic_source_intake import MAX_COMPRESSED, collect_archive, prepare_pair

PROTOCOL_ID = "petclinic-transfer-evaluation-v1"
METHODS = ("source_aware_conventional", "simple_meta", "wheel_meta")


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise AdmissionError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def require_hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise AdmissionError("Expected SHA-256 commitment")


def verify_protocol(root, protocol, expected_sha256):
    require_hash(expected_sha256)
    if digest(protocol) != expected_sha256 or protocol.get("id") != PROTOCOL_ID:
        raise AdmissionError("Unreviewed evaluation protocol")
    for path, expected in {**protocol["frozen_components"], **protocol["evaluation_components"]}.items():
        require_hash(expected)
        if not path or path.startswith("/") or ".." in path.split("/") or "\\" in path:
            raise AdmissionError("Unsafe frozen-component path")
        target = Path(root) / path
        if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise AdmissionError("Frozen component changed: " + path)
    return protocol


def validate_case(case, protocol):
    exact(case, {"id", "infrastructure_revision", "preparation", "expectation_commitment_sha256", "replacements"})
    if type(case["id"]) is not str or not re.fullmatch(r"pc-[0-9]{3}", case["id"]):
        raise AdmissionError("Use neutral case identifiers")
    if case["infrastructure_revision"] != protocol["infrastructure_revision"]:
        raise AdmissionError("Case targets different infrastructure")
    preparation = case["preparation"]
    exact(preparation, {"kind", "author", "provenance_sha256"})
    if preparation["kind"] not in ("internal_transfer", "independent_developer"):
        raise AdmissionError("Unrecognized preparation category")
    if type(preparation["author"]) is not str or not 1 <= len(preparation["author"]) <= 120:
        raise AdmissionError("Preparer declaration required")
    require_hash(preparation["provenance_sha256"])
    require_hash(case["expectation_commitment_sha256"])
    replacements = case["replacements"]
    if type(replacements) is not list or not 1 <= len(replacements) <= len(EDIT_PATHS):
        raise AdmissionError("Bounded nonempty source replacements required")
    seen = set()
    for item in replacements:
        exact(item, {"path", "before_sha256", "content"})
        if type(item["path"]) is not str or item["path"] not in EDIT_PATHS or item["path"] in seen:
            raise AdmissionError("Unsupported or duplicate edit path")
        seen.add(item["path"])
        require_hash(item["before_sha256"])
        if type(item["content"]) is not str or not 1 <= len(item["content"].encode("utf-8")) <= 200_000:
            raise AdmissionError("Replacement source outside size limit")
    return copy.deepcopy(case)


def case_archive(files, root):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as stream:
        with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for path, content in sorted(files.items()):
                item = tarfile.TarInfo(root + "/" + path)
                item.mode, item.size, item.mtime = 0o644, len(content), 0
                archive.addfile(item, io.BytesIO(content))
    return output.getvalue()


def build_case(case, baseline_archive, protocol):
    case = validate_case(case, protocol)
    root = "spring-petclinic-rest-" + protocol["upstream_revision"]
    baseline = collect_archive(baseline_archive, protocol["baseline_archive_sha256"], root)
    candidate = dict(baseline)
    for item in case["replacements"]:
        path = item["path"]
        if path not in baseline or hashlib.sha256(baseline[path]).hexdigest() != item["before_sha256"]:
            raise AdmissionError("Replacement does not match pinned original source")
        candidate[path] = item["content"].encode("utf-8")
        if candidate[path] == baseline[path]:
            raise AdmissionError("No-op replacement is not a fresh changed case")
    raw_candidate = case_archive(candidate, root)
    policy = {"upstream_revision": protocol["upstream_revision"],
              "baseline_archive_sha256": protocol["baseline_archive_sha256"],
              "candidate_archive_sha256": hashlib.sha256(raw_candidate).hexdigest()}
    base_tar, candidate_tar, source_report = prepare_pair(baseline_archive, raw_candidate, policy)
    record = {"id": case["id"], "protocol_id": protocol["id"], "protocol_sha256": digest(protocol),
              "case_input_sha256": digest(case), "preparation": case["preparation"],
              "independence_status": "declared_unverified" if case["preparation"]["kind"] == "independent_developer" else "not_independent",
              "expectation_commitment_sha256": case["expectation_commitment_sha256"],
              "source_admission": source_report, "status": "registered_not_executed"}
    return {"record": record, "baseline": baseline, "candidate": candidate,
            "baseline_archive": base_tar, "candidate_archive": candidate_tar,
            "raw_candidate_archive": raw_candidate}


def model_input(bundle, protocol):
    # Fixed selection: do not pass the whole registration record or case metadata.
    baseline, candidate = bundle["baseline"], bundle["candidate"]
    numbered = lambda content: "\n".join(f"{i}: {line}" for i, line in enumerate(content.decode("utf-8").splitlines(), 1))
    diffs = []
    for path in sorted(EDIT_PATHS):
        if path not in baseline or path not in candidate:
            raise AdmissionError("Required source context missing")
        diffs.extend(difflib.unified_diff(baseline[path].decode("utf-8").splitlines(True),
                                         candidate[path].decode("utf-8").splitlines(True),
                                         fromfile="baseline/" + path, tofile="candidate/" + path))
    payload = {"contract": protocol["public_contract"], "action_interface": protocol["action_interface"],
               "baseline_sources": {p: numbered(baseline[p]) for p in sorted(EDIT_PATHS)},
               "candidate_sources": {p: numbered(candidate[p]) for p in sorted(EDIT_PATHS)},
               "diff": "".join(diffs)}
    if len(canonical(payload)) > protocol["max_model_input_bytes"]:
        raise AdmissionError("Source context exceeds declared budget; do not silently truncate")
    return payload


def register_record(registry, record, protocol):
    exact(registry, {"protocol_sha256", "cases", "attempts"})
    if registry["protocol_sha256"] != digest(protocol) or record["protocol_sha256"] != digest(protocol):
        raise AdmissionError("Registry protocol mismatch")
    if len(registry["cases"]) >= protocol["pilot_case_limit"]:
        raise AdmissionError("Pilot case budget exhausted; expansion needs new registration")
    if any(old["id"] == record["id"] for old in registry["cases"]):
        raise AdmissionError("Case identity is already registered")
    result = copy.deepcopy(registry)
    result["cases"].append(copy.deepcopy(record))
    return result


def start_attempt(registry, case_id, method, protocol):
    if registry["protocol_sha256"] != digest(protocol) or method not in METHODS:
        raise AdmissionError("Unregistered method/protocol")
    if not any(c["id"] == case_id for c in registry["cases"]):
        raise AdmissionError("Unregistered case")
    if any(a["case_id"] == case_id and a["method"] == method for a in registry["attempts"]):
        raise AdmissionError("Resampling/retry is not registered")
    result = copy.deepcopy(registry)
    result["attempts"].append({"case_id": case_id, "method": method, "status": "started",
                               "method_budget": copy.deepcopy(protocol["methods"][method])})
    return result


def save_registration(output, registry_path, bundle, payload, protocol):
    """Serialize local registration; no silent replacement or concurrent writer."""
    output, registry_path = Path(output), Path(registry_path)
    lock = registry_path.with_suffix(registry_path.suffix + ".lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(descriptor)
        registry = strict_json(registry_path.read_text())
        updated = register_record(registry, bundle["record"], protocol)
        output.mkdir(parents=True, exist_ok=False)
        (output / "registration.json").write_text(json.dumps(bundle["record"], indent=2, sort_keys=True))
        (output / "model-input.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
        for key, name in (("baseline_archive", "baseline.tar.gz"), ("candidate_archive", "candidate.tar.gz"),
                          ("raw_candidate_archive", "raw-candidate.tar.gz")):
            (output / name).write_bytes(bundle[key])
        temporary = registry_path.with_suffix(registry_path.suffix + ".pending")
        # Preserve a stale pending write instead of overwriting uncertain history.
        with temporary.open("x") as stream:
            json.dump(updated, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, registry_path)
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--case", type=Path)
    parser.add_argument("--baseline-archive", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    protocol = strict_json((args.root / "evaluation/petclinic_transfer_protocol_v1.json").read_text())
    expected = (args.root / "evaluation/petclinic_transfer_protocol_v1.sha256").read_text().strip()
    verify_protocol(args.root, protocol, expected)
    if args.case is None:
        if args.baseline_archive is not None or args.output is not None:
            parser.error("Case, baseline archive and output must be supplied together")
        print(json.dumps({"status": "protocol_verified", "protocol_sha256": expected, "paid_calls": 0}))
        return
    if args.baseline_archive is None or args.output is None:
        parser.error("Case, baseline archive and output must be supplied together")
    case = strict_json(args.case.read_text())
    with args.baseline_archive.open("rb") as stream:
        baseline_archive = stream.read(MAX_COMPRESSED + 1)
    bundle = build_case(case, baseline_archive, protocol)
    payload = model_input(bundle, protocol)
    registry_path = args.registry or args.root / "evaluation/petclinic_transfer_registry_v1.json"
    save_registration(args.output, registry_path, bundle, payload, protocol)
    print(json.dumps({"status": "registered_not_executed", "case_id": case["id"], "paid_calls": 0}))


if __name__ == "__main__":
    main()
