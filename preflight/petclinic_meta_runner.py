"""Bounded Meta selection/diagnosis and independent paired adjudication."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import time

from preflight.petclinic_adapter import AdmissionError, authenticate_plan, digest, exact, freeze_plan
from preflight.petclinic_evaluation import build_case, model_input, save_registration, start_attempt, strict_json

PROTOCOL_ID = "petclinic-transfer-evaluation-v2"


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True))


def verify_freeze(root, protocol, expected):
    if protocol.get("id") != PROTOCOL_ID or digest(protocol) != expected:
        raise AdmissionError("Unreviewed runner protocol")
    for path, sha in {**protocol["frozen_components"], **protocol["evaluation_components"]}.items():
        if path.startswith("/") or ".." in path.split("/"):
            raise AdmissionError("Unsafe component path")
        target = Path(root) / path
        if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != sha:
            raise AdmissionError("Frozen component changed: " + path)


def resolve_sources(refs, payload, *, selection=False):
    if type(refs) is not list or not (2 if selection else 1) <= len(refs) <= 6:
        raise AdmissionError("Source citation count")
    resolved, cited = [], set()
    for ref in refs:
        exact(ref, {"side", "path", "line_start", "line_end"})
        side, path = ref["side"], ref["path"]
        if side not in ("baseline", "candidate") or type(path) is not str or path not in payload[side + "_sources"]:
            raise AdmissionError("Unknown citation source")
        numbered = payload[side + "_sources"][path].splitlines()
        a, b = ref["line_start"], ref["line_end"]
        if type(a) is not int or type(b) is not int or not 1 <= a <= b <= len(numbered) or b - a >= 8:
            raise AdmissionError("Source citation bounds")
        if any(not line.startswith(str(i) + ": ") for i, line in enumerate(numbered, 1)):
            raise AdmissionError("Numbered source context changed")
        key = (side, path, a, b)
        if key in cited:
            raise AdmissionError("Duplicate source citation")
        cited.add(key)
        resolved.append({**ref, "recorded_lines": numbered[a - 1:b]})
    if selection and (not any(r["side"] == "candidate" for r in refs) or
                      not any(r["side"] == "baseline" for r in refs)):
        raise AdmissionError("Selection requires baseline and candidate references")
    return resolved


def bounded_text(value, maximum=3000):
    if type(value) is not str or not value.strip() or not 1 <= len(value) <= maximum:
        raise AdmissionError("Bounded nonempty text required")


def validate_selection(value, payload):
    if type(value) is not dict:
        raise AdmissionError("Expected response object")
    if value.get("status") == "abstain":
        if set(value) not in ({"status", "reason"}, {"status", "reason", "hypothesis", "source_refs"}):
            raise AdmissionError("Invalid abstention fields")
        bounded_text(value["reason"])
        return {"status": "abstain", "recorded_response": value}
    exact(value, {"status", "hypothesis", "source_refs", "plan"})
    if value["status"] != "propose":
        raise AdmissionError("Unknown response status")
    bounded_text(value["hypothesis"])
    citations = resolve_sources(value["source_refs"], payload, selection=True)
    return {"status": "propose", "recorded_response": value,
            "resolved_sources": citations, "frozen_plan": freeze_plan(value["plan"])}


def validate_diagnosis(value, payload, evidence):
    exact(value, {"summary", "source_refs", "evidence_refs", "limitations"})
    bounded_text(value["summary"])
    if type(value["limitations"]) is list:
        if not 1 <= len(value["limitations"]) <= 8:
            raise AdmissionError("Limitation count")
        for text in value["limitations"]:
            bounded_text(text, 1000)
    else:
        bounded_text(value["limitations"])
    refs = value["evidence_refs"]
    if type(refs) is not list or not 1 <= len(refs) <= 16 or any(type(r) is not str or r not in evidence for r in refs):
        raise AdmissionError("Unresolved execution evidence")
    return {"recorded_response": value, "resolved_sources": resolve_sources(value["source_refs"], payload),
            "resolved_evidence": {r: evidence[r] for r in refs}}


class MetaGateway:
    def __init__(self, client, output, protocol, method, *, transport="meta"):
        if method not in ("simple_meta", "wheel_meta"):
            raise AdmissionError("Unsupported Meta method")
        if transport == "meta" and not protocol.get("paid_execution_enabled"):
            raise AdmissionError("Paid execution is disabled by protocol")
        self.client, self.output, self.protocol, self.method = client, Path(output), protocol, method
        self.transport, self.calls = transport, 0
        self.used_phases = set()

    @classmethod
    def from_environment(cls, output, protocol, method):
        # Same endpoint/client configuration used by the successful inventory run.
        key = os.environ.pop("MODEL_API_KEY", "")
        if not key:
            raise RuntimeError("MODEL_API_KEY is missing")
        from openai import OpenAI
        client = OpenAI(base_url="https://api.meta.ai/v1", api_key=key,
                        max_retries=0, timeout=protocol["request_timeout_seconds"])
        return cls(client, output, protocol, method)

    def call(self, phase, prompt, packet):
        settings = self.protocol["methods"][self.method]
        if phase not in ("selection", "diagnosis") or phase in self.used_phases:
            raise AdmissionError("Unregistered phase or resampling")
        if settings.get(phase + "_requests", 0) != 1:
            raise AdmissionError("Phase request budget is zero")
        request = {"model": self.protocol["model"], "reasoning_effort": "low",
                   "max_completion_tokens": settings[phase + "_completion_limit"],
                   "messages": [{"role": "developer", "content": prompt},
                                {"role": "user", "content": json.dumps(packet, sort_keys=True)}]}
        if len(json.dumps(request).encode()) > self.protocol["max_model_request_bytes"]:
            raise AdmissionError("Request too large; no silent truncation")
        path = self.output / (phase + "-request.json")
        receipt = {"status": "attempted", "transport": self.transport, "request": request,
                   "numeric_usd_cost": None, "usage": None}
        # A pre-existing receipt consumes this phase even after a process crash.
        with path.open("x") as stream:
            json.dump(receipt, stream, indent=2)
        self.used_phases.add(phase)
        self.calls += 1
        started = time.monotonic()
        try:
            response = self.client.chat.completions.create(**request)
            raw = response.model_dump(exclude_none=True)
            receipt.update(status="response_received", response=raw, response_id=raw.get("id"), usage=raw.get("usage"),
                           request_id=getattr(response, "_request_id", None))
            if type(raw.get("id")) is not str or not raw["id"] or raw.get("model") != self.protocol["model"] or type(raw.get("choices")) is not list or len(raw["choices"]) != 1:
                raise AdmissionError("Unexpected model/choices")
            choice = raw["choices"][0]
            message = choice.get("message", {})
            if choice.get("finish_reason") != "stop" or message.get("role") != "assistant" or message.get("tool_calls") or type(message.get("content")) is not str:
                raise AdmissionError("Incomplete or tool-bearing response")
            return strict_json(message["content"])
        except AdmissionError as error:
            receipt.update(status="invalid_model_output", error_type=type(error).__name__)
            raise
        except (ValueError, TypeError, KeyError) as error:
            receipt.update(status="invalid_model_output", error_type=type(error).__name__)
            raise AdmissionError("Malformed model response") from None
        except Exception as error:
            # Never persist SDK exception bodies, headers or request credentials.
            status = getattr(error, "status_code", None)
            receipt.update(status="provider_error", error_type=type(error).__name__, http_status=status if type(status) is int else None)
            raise RuntimeError("Meta provider request failed") from None
        finally:
            receipt["elapsed_seconds"] = time.monotonic() - started
            save(path, receipt)


class WorldBudget:
    def __init__(self, executor, limit, output):
        self.executor, self.limit, self.output = executor, limit, Path(output)
        self.worlds = []

    def run(self, side, frozen):
        if len(self.worlds) >= self.limit:
            raise AdmissionError("World budget exhausted")
        identity = "world-" + str(len(self.worlds) + 1)
        entry = {"id": identity, "side": side, "plan_sha256": frozen["sha256"], "status": "attempted"}
        self.worlds.append(entry)
        save(self.output / "world-index.json", self.worlds)
        result = self.executor(side, copy.deepcopy(frozen))
        if result.get("side") != side or result.get("plan_sha256") != frozen["sha256"]:
            raise AdmissionError("World evidence identity mismatch")
        if result.get("status") not in ("contract_satisfied", "contract_violated", "execution_error"):
            raise AdmissionError("Unknown world result")
        entry.update(status=result["status"], evidence_sha256=digest(result), result=result)
        save(self.output / "world-index.json", self.worlds)
        return result


def paired_verdict(worlds, frozen, trials=4, expected_seed=None):
    pairs = []
    for _ in range(trials):
        base = worlds.run("baseline", frozen)
        if base["status"] != "contract_satisfied":
            return "baseline_invalid"
        if expected_seed is not None and base.get("seed_sha256") != expected_seed:
            return "baseline_invalid"
        candidate = worlds.run("candidate", frozen)
        if candidate["status"] == "execution_error":
            return "execution_error"
        if not base.get("seed_sha256") or base["seed_sha256"] != candidate.get("seed_sha256"):
            return "inconclusive"
        pairs.append(candidate["status"])
    if all(s == "contract_violated" for s in pairs):
        return "confirmed_violation"
    if all(s == "contract_satisfied" for s in pairs):
        return "no_violation_observed"
    return "inconclusive"


def evidence_index(worlds):
    return {world["id"] + "-event-" + str(i): event
            for world in worlds.worlds for i, event in enumerate(world.get("result", {}).get("events", []), 1)}


def run_meta_method(protocol, payload, prompts, controls, gateway, executor, output):
    output = Path(output)
    result = {"status": "execution_error", "method": gateway.method, "paid_requests": 0,
              "transport": gateway.transport, "diagnosis_status": "not_requested"}
    worlds = WorldBudget(executor, protocol["methods"][gateway.method]["world_limit"], output)
    stage = "controls"
    try:
        anchors = protocol["control_plan_sha256"]
        if len(controls) != len(anchors) or len(controls) != 2:
            raise AdmissionError("Expected two registered healthy controls")
        seeds = []
        for frozen, expected in zip(controls, anchors):
            authenticate_plan(frozen, expected)
            control = worlds.run("baseline", frozen)
            if control["status"] != "contract_satisfied" or not control.get("seed_sha256"):
                result["status"] = "baseline_invalid"
                return result
            seeds.append(control["seed_sha256"])
        if len(set(seeds)) != 1:
            result["status"] = "baseline_invalid"
            return result
        stage = "selection"
        prompt = prompts["simple_meta" if gateway.method == "simple_meta" else "wheel_meta_selection"]
        selected = validate_selection(gateway.call("selection", prompt, payload), payload)
        save(output / "selection-admission.json", selected)
        if selected["status"] == "abstain":
            result["status"] = "inconclusive"
            result["reason"] = "model_abstained"
            return result
        frozen = selected["frozen_plan"]
        stage = "execution"
        result["plan_sha256"] = frozen["sha256"]
        result["status"] = paired_verdict(worlds, frozen, protocol["repeat_pairs"] + 1, seeds[0])
        # Diagnosis is an independent annotation: it can never upgrade the verdict.
        if gateway.method == "wheel_meta" and result["status"] not in ("baseline_invalid", "execution_error"):
            evidence = evidence_index(worlds)
            try:
                diagnosis = gateway.call("diagnosis", prompts["wheel_meta_diagnosis"], {"source_context": payload, "evidence": evidence, "verifier_outcome": result["status"]})
                save(output / "diagnosis-admission.json", validate_diagnosis(diagnosis, payload, evidence))
                result["diagnosis_status"] = "admitted_references_semantics_need_review"
            except Exception as error:
                result["diagnosis_status"] = "rejected_or_error"
                result["diagnosis_error_type"] = type(error).__name__
        return result
    except AdmissionError as error:
        result.update(status="inconclusive" if stage == "selection" else "execution_error", error_type=type(error).__name__, reason="proposal_or_evidence_admission_failed")
        return result
    except Exception as error:
        result.update(status="execution_error", error_type=type(error).__name__)
        return result
    finally:
        result.update(paid_requests=gateway.calls if gateway.transport == "meta" else 0,
                      model_requests=gateway.calls, worlds_attempted=len(worlds.worlds))
        save(output / "result.json", result)


def claim_attempt(path, case_id, method, protocol):
    path = Path(path)
    lock = path.with_suffix(path.suffix + ".lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(descriptor)
        registry = strict_json(path.read_text())
        updated = start_attempt(registry, case_id, method, protocol)
        pending = path.with_suffix(path.suffix + ".pending")
        with pending.open("x") as stream:
            json.dump(updated, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        return next(c for c in registry["cases"] if c["id"] == case_id)
    finally:
        lock.unlink()


def run_conventional(protocol, payload, controls, packet, executor, output, case_sha256):
    """Execute a predeclared source-aware plan set, with no model access."""
    output = Path(output)
    result = {"status": "execution_error", "method": "source_aware_conventional", "paid_requests": 0}
    worlds = WorldBudget(executor, protocol["methods"]["source_aware_conventional"]["world_limit"], output)
    try:
        exact(packet, {"case_input_sha256", "preparation", "experiments"})
        if packet["case_input_sha256"] != case_sha256:
            raise AdmissionError("Conventional plans target another case")
        exact(packet["preparation"], {"kind", "author", "provenance_sha256"})
        if packet["preparation"]["kind"] not in ("AI_assisted", "independent_developer", "internal_developer"):
            raise AdmissionError("Declare actual conventional preparation")
        bounded_text(packet["preparation"]["author"], 120)
        if not re.fullmatch(r"[0-9a-f]{64}", packet["preparation"]["provenance_sha256"]):
            raise AdmissionError("Conventional provenance commitment required")
        experiments = packet["experiments"]
        if type(experiments) is not list or not 1 <= len(experiments) <= 8:
            raise AdmissionError("Conventional plan budget")
        admitted = [validate_selection(e, payload) for e in experiments]
        if any(e["status"] != "propose" for e in admitted):
            raise AdmissionError("Conventional packet must contain executable plans")
        if len({e["frozen_plan"]["sha256"] for e in admitted}) != len(admitted):
            raise AdmissionError("Duplicate conventional plans do not add coverage")
        # Persist the entire plan set before any result can influence selection.
        save(output / "conventional-plans.json", {"packet": packet, "sha256": digest(packet)})
        seed = None
        if len(controls) != 2:
            raise AdmissionError("Healthy controls missing")
        for frozen, anchor in zip(controls, protocol["control_plan_sha256"]):
            authenticate_plan(frozen, anchor)
            control = worlds.run("baseline", frozen)
            if control["status"] != "contract_satisfied" or not control.get("seed_sha256") or (seed is not None and seed != control["seed_sha256"]):
                result["status"] = "baseline_invalid"
                return result
            seed = control["seed_sha256"]
        for experiment in admitted:
            frozen = experiment["frozen_plan"]
            base = worlds.run("baseline", frozen)
            if base["status"] != "contract_satisfied" or base.get("seed_sha256") != seed:
                result["status"] = "baseline_invalid"
                return result
            candidate = worlds.run("candidate", frozen)
            if candidate["status"] == "execution_error":
                result["status"] = "execution_error"
                return result
            if candidate.get("seed_sha256") != seed:
                result["status"] = "inconclusive"
                return result
            if candidate["status"] == "contract_violated":
                repeated = paired_verdict(worlds, frozen, protocol["repeat_pairs"], seed)
                result["status"] = repeated if repeated in ("confirmed_violation", "baseline_invalid", "execution_error") else "inconclusive"
                result["plan_sha256"] = frozen["sha256"]
                return result
        result["status"] = "no_violation_observed"
        return result
    except AdmissionError as error:
        result.update(status="inconclusive", error_type=type(error).__name__)
        return result
    except Exception as error:
        result.update(status="execution_error", error_type=type(error).__name__)
        return result
    finally:
        result["worlds_attempted"] = len(worlds.worlds)
        save(output / "result.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--case", type=Path)
    parser.add_argument("--baseline-archive", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--method", choices=("simple_meta", "wheel_meta", "source_aware_conventional"))
    parser.add_argument("--conventional-plans", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--register-only", action="store_true")
    args = parser.parse_args()
    protocol = strict_json((args.root / "evaluation/petclinic_transfer_protocol_v2.json").read_text())
    expected = (args.root / "evaluation/petclinic_transfer_protocol_v2.sha256").read_text().strip()
    verify_freeze(args.root, protocol, expected)
    if args.case is None:
        if args.register_only:
            parser.error("Registration requires a case")
        print(json.dumps({"status": "runner_protocol_verified", "paid_calls": 0}))
        return
    if args.register_only:
        if args.output is None or args.baseline_archive is None or args.method is not None:
            parser.error("Registration requires output and baseline archive, without a method")
        case = strict_json(args.case.read_text())
        bundle = build_case(case, args.baseline_archive.read_bytes(), protocol)
        save_registration(args.output, args.registry or args.root / "evaluation/petclinic_transfer_registry_v2.json",
                          bundle, model_input(bundle, protocol), protocol)
        print(json.dumps({"status": "registered_not_executed", "case_id": case["id"], "paid_calls": 0}))
        return
    if any(v is None for v in (args.registry, args.method, args.output, args.baseline_archive)):
        parser.error("Case execution requires registry, method, output and baseline archive")
    args.output.mkdir(parents=True, exist_ok=False)
    from preflight.petclinic_world import DockerWorlds, BaselineInvalid, process
    gateway, worlds = None, None
    try:
        case = strict_json(args.case.read_text())
        bundle = build_case(case, args.baseline_archive.read_bytes(), protocol)
        payload = model_input(bundle, protocol)
        registered = claim_attempt(args.registry, case["id"], args.method, protocol)
        if registered != bundle["record"]:
            raise AdmissionError("Registered case differs from supplied case")
        prompts = strict_json((args.root / "evaluation/petclinic_transfer_prompts_v2.json").read_text())
        packet = None
        if args.method == "source_aware_conventional":
            if args.conventional_plans is None:
                raise AdmissionError("Predeclared conventional plans required")
            packet = strict_json(args.conventional_plans.read_text())
        else:
            gateway = MetaGateway.from_environment(args.output, protocol, args.method)
        images = {}
        for role, tag in (("maven", "maven:3.9.9-eclipse-temurin-17"), ("postgres", "postgres:17-bookworm")):
            if process(["docker", "pull", tag]).returncode:
                raise RuntimeError("Public runtime image acquisition failed")
            images[role] = process(["docker", "image", "inspect", tag, "--format", "{{index .RepoDigests 0}}"]).stdout.strip()
        report = bundle["record"]["source_admission"]
        worlds = DockerWorlds(images, args.output / "runtime", {"baseline": report["baseline_map_sha256"], "candidate": report["candidate_map_sha256"]})
        for side in ("baseline", "candidate"):
            archive = args.output / (side + ".tar.gz")
            archive.write_bytes(bundle[side + "_archive"])
            worlds.build(side, archive, report[side + "_normalized_sha256"])
        controls = strict_json((args.root / "evaluation/petclinic_healthy_plans_v1.json").read_text())
        result = (run_conventional(protocol, payload, controls, packet, worlds.run, args.output, registered["case_input_sha256"])
                  if gateway is None else run_meta_method(protocol, payload, prompts, controls, gateway, worlds.run, args.output))
        result["build_results"] = worlds.builds
        result.update(case_id=case["id"], case_input_sha256=registered["case_input_sha256"], protocol_sha256=digest(protocol))
        save(args.output / "result.json", result)
    except Exception as error:
        save(args.output / "result.json", {"status": "baseline_invalid" if isinstance(error, BaselineInvalid) else "execution_error", "error_type": type(error).__name__, "paid_requests": gateway.calls if gateway else 0, "build_results": worlds.builds if worlds else {}})
        raise
    finally:
        if worlds is not None:
            worlds.close()


if __name__ == "__main__":
    main()
