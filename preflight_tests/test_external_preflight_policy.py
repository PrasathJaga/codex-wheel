"""Regression gates for the external runner's non-exposure boundary."""
import json
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def validate_external_job(job):
    if job.get("permissions") != {}:
        raise ValueError("external job token permissions must be empty")
    if set(job.get("env", {})) != {"UPSTREAM_REVISION"}:
        raise ValueError("unapproved job environment")
    for step in job["steps"]:
        if "env" in step:
            raise ValueError("external steps cannot receive host credentials")
        action = step.get("uses", "")
        if action and not re.fullmatch(r"actions/upload-artifact@[0-9a-f]{40}", action):
            raise ValueError("no checkout or external actions on external runner")
        script = step.get("run", "")
        for forbidden in ("secrets.", "github.token", "GITHUB_TOKEN", "docker.sock",
                          "--privileged", "--env-file", "--env ", "--network host",
                          "github.workspace", "$HOME", "git clone", "docker cp",
                          "codex-wheel", "curl -d", "curl --data"):
            if forbidden in script:
                raise ValueError("forbidden capability: " + forbidden)
        mounts = re.findall(r'--mount "([^"]+)"', script)
        for mount in mounts:
            allowed = {
                "type=bind,src=$RUNNER_TEMP/public-input/source.tar.gz,dst=/input/source.tar.gz,readonly",
                "type=bind,src=$RUNNER_TEMP/public-input/candidate.tar.gz,dst=/input/source.tar.gz,readonly",
                "type=volume,src=$work_volume,dst=/work",
                "type=volume,src=$work_volume,dst=/work,readonly",
            }
            if mount not in allowed:
                raise ValueError("unapproved host mount")
        joined = script.replace("\\\n", " ")
        if re.search(r"docker run[^\n]*(?:\s-v\s|\s-e\s)", joined):
            raise ValueError("unreviewed shorthand mount/environment")


class ExternalPreflightPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load((ROOT / ".github/workflows/external-preflight.yml").read_text())
        cls.job = cls.workflow["jobs"]["external-baseline"]

    def test_external_runner_has_no_wheel_or_credentials(self):
        validate_external_job(self.job)
        self.assertEqual(self.job["needs"], "policy")
        self.assertEqual(self.job["runs-on"], "ubuntu-latest")

    def test_reject_checkout_secret_and_host_mount(self):
        for step in (
            {"uses": "actions/checkout@" + "a" * 40},
            {"run": "docker run --env GITHUB_TOKEN image"},
            {"run": 'docker run --mount "type=bind,src=/workspace,dst=/input" image'},
            {"run": "echo ${{ secrets.META_API_KEY }}"},
            {"run": "docker run --network host image"},
        ):
            with self.subTest(step=step), self.assertRaises(ValueError):
                validate_external_job({**self.job, "steps": [step]})

    def test_pinned_upstream_and_no_paid_execution(self):
        manifest = json.loads((ROOT / "evaluation/external_preflight_v1.json").read_text())
        self.assertEqual(self.job["env"]["UPSTREAM_REVISION"], manifest["revision"])
        self.assertRegex(manifest["revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(manifest["paid_calls"], 0)
        scripts = "\n".join(s.get("run", "") for s in self.job["steps"])
        self.assertIn("mvn -B -ntp -Dmaven.repo.local=/tmp/m2 verify", scripts)
        self.assertNotIn("skipTests", scripts)
        self.assertNotIn("skipITs", scripts)
        self.assertIn("exit \"$build_status\"", scripts)

    def test_runtime_is_readonly_and_offline(self):
        runtime = next(s["run"] for s in self.job["steps"] if s.get("name", "").startswith("Verify fresh"))
        self.assertIn("--network none", runtime)
        self.assertIn("--user 1000:1000 --read-only", runtime)
        self.assertIn("--cap-drop ALL --security-opt no-new-privileges", runtime)
        self.assertIn("src=$work_volume,dst=/work,readonly", runtime)
        self.assertIn('for trial in 1 2', runtime)
        self.assertNotIn("type=bind", runtime)

    def test_failure_evidence_and_cleanup_always_run(self):
        cleanup, upload = self.job["steps"][-2:]
        self.assertEqual(cleanup["if"], "always()")
        self.assertEqual(upload["if"], "always()")
        self.assertEqual(upload["with"]["path"], "${{ runner.temp }}/preflight-evidence/")
        self.assertEqual(upload["with"]["if-no-files-found"], "error")


if __name__ == "__main__":
    unittest.main()
