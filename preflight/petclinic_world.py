"""Trusted Docker executor; containers receive only admitted upstream bytes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
from secrets import token_hex
import subprocess
import time
import urllib.error
import urllib.request

if "__WHEEL_EMBEDDED_ADAPTER__" not in globals():
    from preflight.petclinic_adapter import execute_plan, ExperimentViolation


class BaselineInvalid(RuntimeError):
    pass


def child_environment(extra=None):
    # Do not forward model/GitHub credentials even to the Docker CLI process.
    if set(extra or {}) - {"POSTGRES_PASS", "POSTGRES_PASSWORD"}:
        raise ValueError("Only disposable database credentials may enter subprocess environment")
    values = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"}
    values.update(extra or {})
    return values


def process(args, data=None, extra=None, timeout=300):
    return subprocess.run(args, input=data, text=True, capture_output=True,
                          env=child_environment(extra), timeout=timeout, check=False)


class DockerWorlds:
    def __init__(self, images, output, source_identity):
        if set(images) != {"maven", "postgres"}:
            raise ValueError("Expected fixed image roles")
        for name, image in images.items():
            if not re.fullmatch(name + r"@sha256:[0-9a-f]{64}", image):
                raise ValueError("Execute resolved official image digests only")
        self.images = images
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.prefix = "pc-runner-" + token_hex(8)
        self.volumes = {side: self.prefix + "-" + side for side in ("baseline", "candidate")}
        self.source_identity = copy.deepcopy(source_identity)
        self.builds, self.ordinal = {}, 0

    def build(self, side, archive, expected_sha256):
        if side not in self.volumes:
            raise ValueError("Unsupported source side")
        archive = Path(archive).resolve()
        if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected_sha256:
            raise ValueError("Admitted build input changed")
        volume = self.volumes[side]
        created = process(["docker", "volume", "create", volume])
        if created.returncode:
            raise RuntimeError("Volume preparation failed")
        init = process(["docker", "run", "--rm", "--entrypoint", "chown", "--network", "none",
                        "--read-only", "--cap-drop", "ALL", "--cap-add", "CHOWN",
                        "--security-opt", "no-new-privileges", "--mount", "type=volume,src=" + volume + ",dst=/work",
                        self.images["maven"], "1000:1000", "/work"])
        if init.returncode:
            raise RuntimeError("Volume ownership preparation failed")
        base = ["docker", "run", "--rm", "--entrypoint", "/bin/sh", "--user", "1000:1000",
                "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--cpus", "2", "--memory", "3g", "--pids-limit", "256", "--network", "bridge",
                "--tmpfs", "/tmp:rw,uid=1000,gid=1000,size=1g",
                "--mount", "type=bind,src=" + str(archive) + ",dst=/input/source.tar.gz,readonly",
                "--mount", "type=volume,src=" + volume + ",dst=/work", self.images["maven"], "-eu", "-c"]
        verify = process(base + ["tar -xzf /input/source.tar.gz -C /work --strip-components=1; cd /work; mvn -B -ntp -Dmaven.repo.local=/work/.maven-cache verify"], timeout=900)
        (self.output / (side + "-verify.log")).write_text(verify.stdout + verify.stderr)
        self.builds[side] = {"verify_returncode": verify.returncode, "tests_unchanged": True,
                             "package_used_skip_tests": False}
        if verify.returncode:
            if side == "baseline":
                raise BaselineInvalid("Healthy upstream Maven verification failed")
            # Retain the original failure; package only to observe business effects.
            package = process(base + ["cd /work; mvn -B -ntp -Dmaven.repo.local=/work/.maven-cache -DskipTests package"], timeout=900)
            (self.output / (side + "-package.log")).write_text(package.stdout + package.stderr)
            self.builds[side].update(package_returncode=package.returncode, package_used_skip_tests=True)
            if package.returncode:
                raise RuntimeError("Candidate packaging failed after retained verify failure")
        (self.output / "build-results.json").write_text(json.dumps(self.builds, indent=2))

    def run(self, side, frozen):
        if side not in self.volumes:
            raise ValueError("Unsupported source side")
        self.ordinal += 1
        folder = self.output / ("world-" + str(self.ordinal))
        folder.mkdir()
        network = self.prefix + "-w" + str(self.ordinal)
        database, service = network + "-db", network + "-api"
        record = {"side": side, "plan_sha256": frozen["sha256"], "status": "execution_error",
                  "events": [], "source_identity_sha256": self.source_identity[side]}

        def sql(statement, role="postgres", check=True):
            result = process(["docker", "exec", "-i", database, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
                              "-U", role, "-d", "petclinic"], data=statement)
            if check and result.returncode:
                raise RuntimeError("SQL command failed")
            return result

        def snapshot():
            parts = ["'%s',(SELECT coalesce(json_agg(t ORDER BY id),'[]'::json) FROM (SELECT * FROM %s) t)" % (t, t)
                     for t in ("owners", "pets", "visits", "types")]
            return json.loads(sql("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT json_build_object(" + ",".join(parts) + "); COMMIT;", "wheel_verify").stdout)

        def request(method, path, body):
            data = None if body is None else json.dumps(body).encode()
            req = urllib.request.Request(api_base + path, data=data, method=method, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3) as response:
                    return response.status, response.read().decode()
            except urllib.error.HTTPError as error:
                return error.code, error.read().decode()

        try:
            if process(["docker", "network", "create", "--internal", network]).returncode:
                raise RuntimeError("Internal network preparation failed")
            admin_password, app_password = token_hex(24), token_hex(24)
            started = process(["docker", "run", "-d", "--name", database, "--network", network, "--network-alias", "database",
                               "--user", "999:999", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                               "--memory", "512m", "--pids-limit", "128",
                               "--tmpfs", "/var/lib/postgresql/data:rw,uid=999,gid=999,size=512m",
                               "--tmpfs", "/var/run/postgresql:rw,uid=999,gid=999,size=16m", "--tmpfs", "/tmp:rw,uid=999,gid=999,size=16m",
                               "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_DB=petclinic", self.images["postgres"]], extra={"POSTGRES_PASSWORD": admin_password})
            if started.returncode:
                raise RuntimeError("Database container did not start")
            for _ in range(60):
                if process(["docker", "exec", database, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "petclinic"]).returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Database readiness timeout")
            sql("CREATE ROLE petclinic LOGIN PASSWORD '" + app_password + "'; GRANT ALL ON SCHEMA public TO petclinic; CREATE ROLE wheel_verify LOGIN; ALTER ROLE wheel_verify SET default_transaction_read_only=on;")
            started = process(["docker", "run", "-d", "--name", service, "--network", network,
                               "--entrypoint", "java", "--user", "1000:1000", "--read-only", "--cap-drop", "ALL",
                               "--security-opt", "no-new-privileges", "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
                               "--tmpfs", "/tmp:rw,uid=1000,gid=1000,size=256m",
                               "--mount", "type=volume,src=" + self.volumes[side] + ",dst=/work,readonly",
                               "--env", "SPRING_PROFILES_ACTIVE=postgres,spring-data-jpa", "--env", "POSTGRES_URL=jdbc:postgresql://database:5432/petclinic",
                               "--env", "POSTGRES_USER=petclinic", "--env", "POSTGRES_PASS", self.images["maven"],
                               "-jar", "/work/target/spring-petclinic-rest-4.0.2.jar"], extra={"POSTGRES_PASS": app_password})
            if started.returncode:
                raise RuntimeError("Service container did not start")
            info = json.loads(process(["docker", "inspect", service]).stdout)[0]
            config = info["HostConfig"]
            mounts = config.get("Mounts", [])
            if (not config["ReadonlyRootfs"] or config["Privileged"] or config.get("Binds") or
                    info["Config"]["User"] != "1000:1000" or config["NetworkMode"] != network or
                    not any(m.get("Type") == "volume" and m.get("Source") == self.volumes[side] and
                            m.get("Target") == "/work" and m.get("ReadOnly") for m in mounts)):
                raise RuntimeError("Runtime isolation configuration mismatch")
            api_base = "http://" + info["NetworkSettings"]["Networks"][network]["IPAddress"] + ":9966/petclinic"
            record["runtime_config"] = info["HostConfig"]
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    status, body = request("GET", "/actuator/health", None)
                    if status == 200 and json.loads(body).get("status") == "UP":
                        break
                except (OSError, ValueError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Service readiness timeout")
            sql("GRANT USAGE ON SCHEMA public TO wheel_verify; GRANT SELECT ON ALL TABLES IN SCHEMA public TO wheel_verify;")
            access = sql("SELECT current_user; SHOW default_transaction_read_only;", "wheel_verify").stdout.splitlines()
            denied = sql("DELETE FROM pets WHERE false;", "wheel_verify", False)
            if access != ["wheel_verify", "on"] or denied.returncode == 0 or "read-only" not in denied.stderr:
                raise RuntimeError("Independent read-only role check failed")
            record["verifier"] = {"role": "wheel_verify", "read_only": True, "write_rejected": True}
            initial = snapshot()
            record["initial_state"] = initial
            record["seed_sha256"] = hashlib.sha256(json.dumps(initial, sort_keys=True).encode()).hexdigest()
            result = execute_plan(frozen, initial, request, snapshot, record["events"], expected_sha256=frozen["sha256"])
            if process(["docker", "stop", "--timeout", "10", service]).returncode:
                raise RuntimeError("Service stop failed")
            stopped = process(["docker", "inspect", service, "--format", "{{.State.Running}}"])
            if stopped.returncode or stopped.stdout.strip() != "false":
                raise RuntimeError("Service stop not established")
            record["final_state"] = snapshot()
            if record["final_state"] != result["final_state"]:
                raise ExperimentViolation("Post-stop committed state differs")
            record["status"] = "contract_satisfied"
        except ExperimentViolation as error:
            record["status"], record["error"] = "contract_violated", str(error)
        except Exception as error:
            record["error_type"] = type(error).__name__
        finally:
            for name, label in ((service, "service"), (database, "database")):
                result = process(["docker", "logs", name])
                (folder / (label + ".log")).write_text(result.stdout + result.stderr)
                process(["docker", "rm", "-f", name])
            process(["docker", "network", "rm", network])
            (folder / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True))
        return record

    def close(self):
        for volume in self.volumes.values():
            process(["docker", "volume", "rm", volume])
