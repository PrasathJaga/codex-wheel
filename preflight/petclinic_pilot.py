"""One registered internal pilot; invokes frozen v2 CLI without changing it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from preflight.petclinic_adapter import digest
from preflight.petclinic_meta_runner import verify_freeze

METHODS = ("source_aware_conventional", "simple_meta", "wheel_meta")
CASES = ("pc-001", "pc-002")
PRICING = {"source": "https://dev.meta.ai/docs/pricing-rate-limits", "checked_on": "2026-11-01",
           "model": "muse-spark-1.3", "mode": "Standard",
           "input_per_million_usd": 1.25, "cached_input_per_million_usd": 0.15,
           "output_per_million_usd": 4.25}


def cost_accounting(receipts):
    total, complete, rows = 0.0, True, []
    for receipt in receipts:
        usage = receipt.get("usage") or {}
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if type(prompt) is not int or type(completion) is not int or min(prompt, completion) < 0:
            complete = False
            rows.append({"estimated_usd": None, "usage": receipt.get("usage")})
            continue
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        if type(cached) is int and 0 <= cached <= prompt:
            estimated = ((prompt - cached) * 1.25 + cached * 0.15 + completion * 4.25) / 1_000_000
            basis = "reported_usage_with_reported_cache"
        else:
            estimated = (prompt * 1.25 + completion * 4.25) / 1_000_000
            basis = "reported_usage_all_input_uncached_upper_estimate"
        total += estimated
        rows.append({"estimated_usd": estimated, "basis": basis, "usage": usage})
    return {"pricing": PRICING, "complete_reported_usage": complete,
            "estimated_standard_token_charge_usd": total if complete else None,
            "known_usage_subtotal_estimate_usd": total, "rows": rows,
            "invoice_or_credit_balance_verified": False}


def collect_receipts(output):
    receipts = []
    for path in sorted(Path(output).glob("pc-*/*/*-request.json")):
        try:
            receipt = json.loads(path.read_text())
        except (OSError, ValueError):
            receipt = {"status": "unreadable_attempt_receipt", "usage": None, "transport": "meta"}
        receipt["receipt_path"] = str(path.relative_to(output))
        receipts.append(receipt)
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--initialize-only", action="store_true")
    parser.add_argument("--case-id", choices=CASES)
    parser.add_argument("--method", choices=METHODS)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    protocol = json.loads((root / "evaluation/petclinic_transfer_protocol_v2.json").read_text())
    expected = (root / "evaluation/petclinic_transfer_protocol_v2.sha256").read_text().strip()
    verify_freeze(root, protocol, expected)
    key = os.environ.pop("MODEL_API_KEY", "")
    registry = output / "execution-registry.json"
    matrix = [(case_id, method) for case_id in CASES for method in METHODS]
    if args.initialize_only or args.case_id is None:
        if args.method is not None:
            parser.error("Single-method execution requires case ID")
        output.mkdir(parents=True, exist_ok=False)
        summary = {"evaluation_kind": "internal_transfer", "status": "ready", "method_results": [],
                   "protocol_sha256": expected, "max_paid_inference_requests": 6,
                   "case_order": list(CASES), "method_order": list(METHODS),
                   "independent_preparer": False, "human_effort_savings_measured": False}
        shutil.copyfile(root / "evaluation/petclinic_transfer_registry_v2.json", registry)
        selected = matrix
    else:
        if args.method is None:
            parser.error("Single-method execution requires a method")
        summary = json.loads((output / "pilot-summary.json").read_text())
        if summary["status"] not in ("ready", "in_progress") or summary["protocol_sha256"] != expected:
            raise RuntimeError("Pilot is stopped/completed or protocol changed")
        position = len(summary["method_results"])
        if position >= len(matrix) or matrix[position] != (args.case_id, args.method):
            raise RuntimeError("Methods must run once in registered order")
        selected = [(args.case_id, args.method)]
    receipts = collect_receipts(output)
    try:
        if not key and (args.initialize_only or any(m != "source_aware_conventional" for _, m in selected)):
            raise RuntimeError("Required Meta access missing")
        registered = json.loads(registry.read_text())
        if sorted(c["id"] for c in registered["cases"]) != list(CASES) or (args.initialize_only and registered["attempts"]):
            raise RuntimeError("Expected exactly two untouched registered cases")
        if args.initialize_only:
            return
        for case_id, method in selected:
            budget = protocol["methods"][method]
            reserved = budget.get("selection_requests", 0) + budget.get("diagnosis_requests", 0)
            if len(receipts) + reserved > 6:
                raise RuntimeError("Pilot inference request budget exhausted")
            method_output = output / case_id / method
            method_output.parent.mkdir(exist_ok=True)
            command = [sys.executable, "-m", "preflight.petclinic_meta_runner", "--root", str(root),
                       "--case", str(root / "evaluation/petclinic_cases_v2" / (case_id + ".json")),
                       "--baseline-archive", str(args.baseline_archive.resolve()), "--registry", str(registry),
                       "--method", method, "--output", str(method_output)]
            environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
            if method == "source_aware_conventional":
                command += ["--conventional-plans", str(root / "evaluation/petclinic_cases_v2" / (case_id + "-conventional.json"))]
            else:
                environment["MODEL_API_KEY"] = key
            print(json.dumps({"event": "method_started", "case_id": case_id, "method": method}), flush=True)
            started = time.monotonic()
            result = subprocess.run(command, cwd=root, env=environment, text=True, capture_output=True, timeout=3600)
            (method_output.parent / (method + "-controller.log")).write_text((result.stdout + result.stderr).replace(key, "[REDACTED]") if key else (result.stdout + result.stderr))
            path = method_output / "result.json"
            method_result = json.loads(path.read_text()) if path.is_file() else {"status": "execution_error", "reason": "missing_result"}
            row = {"case_id": case_id, "method": method, "returncode": result.returncode,
                   "elapsed_seconds_including_builds": time.monotonic() - started, "result": method_result}
            summary["method_results"].append(row)
            print(json.dumps({"event": "method_completed", "case_id": case_id, "method": method, "status": method_result["status"]}), flush=True)
            current_receipts = []
            for phase in ("selection", "diagnosis"):
                trace = method_output / (phase + "-request.json")
                if trace.is_file():
                    receipt = json.loads(trace.read_text())
                    if receipt.get("transport") != "meta":
                        raise RuntimeError("A paid pilot cannot use test-double receipts")
                    current_receipts.append(receipt)
            receipts.extend(current_receipts)
            summary["paid_inference_requests_attempted"] = len(receipts)
            summary["cost_accounting"] = cost_accounting(receipts)
            (output / "pilot-summary.json").write_text(json.dumps(summary, indent=2))
            if (result.returncode or method_result["status"] in ("execution_error", "baseline_invalid", "unsupported_change")
                    or any(r.get("status") == "provider_error" for r in current_receipts)):
                raise RuntimeError("Stopped on preserved execution/access/baseline failure")
        summary["status"] = "completed" if len(summary["method_results"]) == len(matrix) else "in_progress"
    except Exception as error:
        summary.update(status="stopped", error_type=type(error).__name__)
        raise
    finally:
        # Include uncertain/in-flight last-phase receipts even if a child timed out.
        receipts = collect_receipts(output)
        summary["paid_inference_requests_attempted"] = len(receipts)
        summary["cost_accounting"] = cost_accounting(receipts)
        (output / "pilot-summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
