import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml
from preflight import petclinic_adapter as adapter
from preflight import petclinic_source_intake as intake

ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40
PREFIX = "spring-petclinic-rest-" + REVISION
JAVA = sorted(adapter.EDIT_PATHS)[0]


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        for name, content, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = len(content)
                tar.addfile(member, io.BytesIO(content))
            else:
                member.linkname = "/host/private"
                tar.addfile(member)
    return output.getvalue()


def regular(path, value=b"public"):
    return (PREFIX + "/" + path, value, tarfile.REGTYPE)


def policy(base, candidate):
    return {"upstream_revision": REVISION,
            "baseline_archive_sha256": hashlib.sha256(base).hexdigest(),
            "candidate_archive_sha256": hashlib.sha256(candidate).hexdigest()}


class SourceIntakeTests(unittest.TestCase):
    def setUp(self):
        self.base = archive([regular("pom.xml"), regular(JAVA)])

    def test_complete_maps_and_separate_normalized_inputs(self):
        a, b, report = intake.prepare_pair(self.base, self.base, policy(self.base, self.base))
        self.assertEqual(a, b)
        self.assertTrue(report["unchanged_control"])
        self.assertEqual(set(report["baseline_files"]), {"pom.xml", JAVA})
        with tarfile.open(fileobj=io.BytesIO(a), mode="r:gz") as tar:
            self.assertTrue(all(m.isfile() and m.mode == 0o644 for m in tar))

    def test_supported_source_edit_and_protected_edit(self):
        supported = archive([regular("pom.xml"), regular(JAVA, b"different public source")])
        _, _, report = intake.prepare_pair(self.base, supported, policy(self.base, supported))
        self.assertEqual(report["changed_paths"], [JAVA])
        bad = archive([regular("pom.xml", b"changed build"), regular(JAVA)])
        with self.assertRaises(adapter.AdmissionError):
            intake.prepare_pair(self.base, bad, policy(self.base, bad))

    def test_links_special_traversal_duplicate_and_wrong_root_rejected(self):
        for entries in (
            [(PREFIX + "/link", b"", tarfile.SYMTYPE)],
            [(PREFIX + "/link", b"", tarfile.LNKTYPE)],
            [(PREFIX + "/pipe", b"", tarfile.FIFOTYPE)],
            [regular("../escape")], [regular("/absolute")],
            [regular("x"), regular("x")], [regular("x"), regular("x/y")],
            [("other-root/x", b"a", tarfile.REGTYPE)],
        ):
            data = archive(entries)
            with self.subTest(entries=entries), self.assertRaises(adapter.AdmissionError):
                intake.collect_archive(data, hashlib.sha256(data).hexdigest(), PREFIX)

    def test_digest_size_and_entry_budgets(self):
        with self.assertRaises(adapter.AdmissionError):
            intake.collect_archive(self.base, "0" * 64, PREFIX)
        for name, limit in (("MAX_COMPRESSED", 1), ("MAX_EXPANDED", 1), ("MAX_FILE", 1), ("MAX_FILES", 1)):
            with self.subTest(limit=name), patch.object(intake, name, limit), self.assertRaises(adapter.AdmissionError):
                intake.collect_archive(self.base, hashlib.sha256(self.base).hexdigest(), PREFIX)

    def test_failure_before_build_inputs_written(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "upstream.tar.gz").write_bytes(self.base)
            (source / "candidate-input.tar.gz").write_bytes(b"not an archive")
            with self.assertRaises(adapter.AdmissionError):
                intake.prepare_inputs(source, source, policy(self.base, self.base))
            self.assertFalse((source / "candidate.tar.gz").exists())
            self.assertFalse((source / "source.tar.gz").exists())
            self.assertEqual(json.loads((source / "source-admission.json").read_text())["status"], "source_admission_error")

    def test_workflow_admits_before_builds_with_no_wheel_checkout(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/external-preflight.yml").read_text())
        job = workflow["jobs"]["external-baseline"]
        steps = job["steps"]
        names = [s["name"] for s in steps]
        admit = names.index("Admit complete source archives before any upstream execution")
        self.assertLess(admit, names.index("Build unchanged upstream only inside restricted container"))
        self.assertLess(admit, names.index("Build admitted unchanged candidate in separate restricted container"))
        self.assertEqual(job["permissions"], {})
        self.assertFalse(any("checkout" in s.get("uses", "") for s in steps))
        script = steps[admit]["run"]
        self.assertIn((ROOT / "preflight/petclinic_source_intake.py").read_text(), script)
        candidate = next(s["run"] for s in steps if s["name"].startswith("Build admitted unchanged"))
        self.assertIn("petclinic-candidate-", candidate)
        self.assertIn("candidate.tar.gz,dst=/input/source.tar.gz,readonly", candidate)
        self.assertNotIn("github.workspace", candidate)


if __name__ == "__main__":
    unittest.main()
