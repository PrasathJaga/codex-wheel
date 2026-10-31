"""Trusted host check; never mount this module or Wheel into the service."""
import copy
import hashlib
import json
import ipaddress
import os
from pathlib import Path
from secrets import token_hex
import subprocess
import time
import urllib.error
import urllib.request


if "__WHEEL_EMBEDDED_ADAPTER__" not in globals():
    from preflight.petclinic_adapter import authenticate_plan, execute_plan, ExperimentViolation


class ContractFailure(ValueError):
    pass


def verify_update(before, after, pet_id, expected):
    """Require exact row preservation except three explicitly editable columns."""
    if set(before) != {"owners", "pets", "visits", "types"} or set(after) != set(before):
        raise ContractFailure("Incomplete evidence tables")
    for table in before:
        rows = before[table]
        if not isinstance(rows, list) or not isinstance(after[table], list):
            raise ContractFailure("Unknown rows are not empty rows")
        for values in (rows, after[table]):
            ids = [r["id"] for r in values]
            if len(ids) != len(set(ids)):
                raise ContractFailure("Duplicate evidence identities")
    if not before["owners"] or not before["visits"]:
        raise ContractFailure("Missing non-vacuous owner/visit controls")
    targets = [p for p in before["pets"] if p["id"] == pet_id]
    if len(targets) != 1 or not any(v["pet_id"] == pet_id for v in before["visits"]):
        raise ContractFailure("Target must have existing visit history")
    if len(before["pets"]) < 2:
        raise ContractFailure("Missing unrelated pet control")
    if set(expected) != {"name", "birth_date", "type_id"}:
        raise ContractFailure("Unapproved edited columns")
    wanted = copy.deepcopy(before)
    target = next(p for p in wanted["pets"] if p["id"] == pet_id)
    if all(target[k] == v for k, v in expected.items()):
        raise ContractFailure("Vacuous update")
    target.update(expected)
    if after != wanted:
        raise ContractFailure("Committed state violates profile-update preservation")
    return {"verdict": "healthy_contract_observed", "pet_id": pet_id,
            "preserved_visits": len(before["visits"]), "preserved_owners": len(before["owners"])}


def command(args, *, data=None, env=None, check=True):
    return subprocess.run(args, input=data, text=True, capture_output=True,
                          env=env, check=check, timeout=180)


def sql(database, statement, role="postgres", check=True):
    return command(["docker", "exec", "-i", database, "psql", "-X", "-qAt",
                    "-v", "ON_ERROR_STOP=1", "-U", role, "-d", "petclinic"],
                   data=statement, check=check)


def snapshot(database):
    # One consistent committed-state snapshot, using SELECT privileges only.
    parts = []
    for table in ("owners", "pets", "visits", "types"):
        parts.append("'%s', (SELECT coalesce(json_agg(t ORDER BY id), '[]'::json) "
                     "FROM (SELECT * FROM %s) t)" % (table, table))
    query = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT json_build_object(" + ",".join(parts) + "); COMMIT;"
    return json.loads(sql(database, query, role="wheel_verify").stdout)


def request(method, path, body=None, *, base_url, timeout=10):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base_url + path,
                                 data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def main():
    evidence = Path(os.environ["RUNNER_TEMP"]) / "preflight-evidence"
    image = (evidence / "build-image.txt").read_text().strip()
    pg_image = (evidence / "postgres-image.txt").read_text().strip()
    suffix = os.environ["GITHUB_RUN_ID"] + "-" + os.environ["GITHUB_RUN_ATTEMPT"]
    volume = "petclinic-preflight-" + suffix
    if "PUBLIC_HEALTHY_PLANS" in globals():
        healthy_plans = PUBLIC_HEALTHY_PLANS
        expected_hashes = PUBLIC_PLAN_HASHES
    else:
        root = Path(__file__).resolve().parents[1]
        healthy_plans = json.loads((root / "evaluation/petclinic_healthy_plans_v1.json").read_text())
        lock = json.loads((root / "evaluation/petclinic_adapter_lock_v1.json").read_text())
        expected_hashes = lock["public_plan_sha256"]
    if len(healthy_plans) != 2 or len(expected_hashes) != 2:
        raise ValueError("Expected exactly two public healthy adapter controls")
    for frozen, expected_hash in zip(healthy_plans, expected_hashes):
        authenticate_plan(frozen, expected_hash)
    (evidence / "plan-admission.json").write_text(json.dumps({"accepted_plan_sha256": expected_hashes}))
    outcomes = []
    for trial, (frozen, plan_hash) in enumerate(zip(healthy_plans, expected_hashes), 1):
        network = "petclinic-contract-" + suffix + "-" + str(trial)
        database, service = network + "-db", network + "-api"
        folder = evidence / ("contract-" + str(trial))
        folder.mkdir()
        record = {"scope": "healthy-profile-update-only", "trial": trial,
                  "status": "execution_error", "requests": []}
        try:
            command(["docker", "network", "create", "--internal", network])
            admin_password, app_password = token_hex(24), token_hex(24)
            db_env = {**os.environ, "POSTGRES_PASSWORD": admin_password}
            command(["docker", "run", "-d", "--name", database, "--network", network,
                     "--network-alias", "database", "--user", "999:999", "--read-only",
                     "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                     "--memory", "512m", "--pids-limit", "128",
                     "--tmpfs", "/var/lib/postgresql/data:rw,uid=999,gid=999,size=512m",
                     "--tmpfs", "/var/run/postgresql:rw,uid=999,gid=999,size=16m",
                     "--tmpfs", "/tmp:rw,uid=999,gid=999,size=16m",
                     "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_DB=petclinic", pg_image], env=db_env)
            for attempt in range(60):
                ready = command(["docker", "exec", database, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "petclinic"], check=False)
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("PostgreSQL readiness timeout")
            # Temporary application role can initialize its own disposable schema;
            # it does not know the admin password or verifier role credentials.
            sql(database, "CREATE ROLE petclinic LOGIN PASSWORD '" + app_password + "';"
                "GRANT ALL ON SCHEMA public TO petclinic;"
                "CREATE ROLE wheel_verify LOGIN;"
                "ALTER ROLE wheel_verify SET default_transaction_read_only=on;")
            service_env = {**os.environ, "POSTGRES_PASS": app_password}
            command(["docker", "run", "-d", "--name", service, "--network", network,
                     "--entrypoint", "java",
                     "--user", "1000:1000", "--read-only", "--cap-drop", "ALL",
                     "--security-opt", "no-new-privileges", "--memory", "2g", "--pids-limit", "256",
                     "--tmpfs", "/tmp:rw,uid=1000,gid=1000,size=256m",
                     "--mount", "type=volume,src=" + volume + ",dst=/work,readonly",
                     "--env", "SPRING_PROFILES_ACTIVE=postgres,spring-data-jpa",
                     "--env", "POSTGRES_URL=jdbc:postgresql://database:5432/petclinic",
                     "--env", "POSTGRES_USER=petclinic", "--env", "POSTGRES_PASS",
                     image, "-jar", "/work/target/spring-petclinic-rest-4.0.2.jar"], env=service_env)
            info = json.loads(command(["docker", "inspect", service]).stdout)[0]
            address = info["NetworkSettings"]["Networks"][network]["IPAddress"]
            if not ipaddress.ip_address(address).is_private:
                raise RuntimeError("Unexpected non-private container address")
            api_base = "http://" + address + ":9966/petclinic"
            (folder / "runtime-config.json").write_text(json.dumps(info["HostConfig"], sort_keys=True))
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    status, body = request("GET", "/actuator/health", base_url=api_base, timeout=2)
                    record["readiness"] = {"last_status": status, "last_response": body}
                    if status == 200 and json.loads(body).get("status") == "UP":
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("PetClinic PostgreSQL readiness timeout")
            sql(database, "GRANT USAGE ON SCHEMA public TO wheel_verify;"
                "GRANT SELECT ON ALL TABLES IN SCHEMA public TO wheel_verify;")
            role = sql(database, "SELECT current_user; SHOW default_transaction_read_only;", role="wheel_verify").stdout.splitlines()
            if role != ["wheel_verify", "on"]:
                raise RuntimeError("Verifier identity/read-only configuration mismatch")
            denied = sql(database, "DELETE FROM pets WHERE false;", role="wheel_verify", check=False)
            if denied.returncode == 0 or "read-only" not in denied.stderr:
                raise RuntimeError("Verifier write restriction was not enforced")
            (folder / "verifier-access.json").write_text(json.dumps({"role": role[0], "read_only": True, "write_rejected": True}))
            before = snapshot(database)
            (folder / "before.json").write_text(json.dumps(before, sort_keys=True))
            record["frozen_plan"] = frozen
            plan_result = execute_plan(
                frozen, before,
                lambda method, path, body: request(method, path, body, base_url=api_base),
                lambda: snapshot(database), record["requests"], expected_sha256=plan_hash)
            record["plan_sha256"] = plan_result["plan_sha256"]
            target_id = plan_result["pet_id"]
            desired = next(p for p in plan_result["final_state"]["pets"] if p["id"] == target_id)
            expected = {k: desired[k] for k in ("name", "birth_date", "type_id")}
            command(["docker", "stop", "--timeout", "10", service])
            stopped = snapshot(database)
            record["contract"] = verify_update(before, stopped, target_id, expected)
            (folder / "after-service-stop.json").write_text(json.dumps(stopped, sort_keys=True))
            record["status"] = "healthy_contract_observed"
            record["seed_sha256"] = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
            outcomes.append(record["seed_sha256"])
        except (ContractFailure, ExperimentViolation) as error:
            record["status"], record["error"] = "baseline_contract_failure", str(error)
            raise
        except Exception as error:
            record["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            (folder / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True))
            for name, label in ((service, "service"), (database, "database")):
                logs = command(["docker", "logs", name], check=False)
                (folder / (label + ".log")).write_text(logs.stdout + logs.stderr)
                command(["docker", "rm", "-f", name], check=False)
            command(["docker", "network", "rm", network], check=False)
    if len(set(outcomes)) != 1:
        raise ContractFailure("Fresh database seeds differed")
    (evidence / "contract-summary.json").write_text(json.dumps({
        "status": "healthy_contract_observed", "trials": 2,
        "independent_sql_verifier": True, "paid_calls": 0,
        "scope": "two-public-bounded-plans; no candidate or repair"}, indent=2))


if __name__ == "__main__":
    main()
