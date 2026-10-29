"""Mandatory integrity checks on a trusted runner; not hostile-process isolation."""
import hashlib
import json
from pathlib import Path

class IntegrityError(RuntimeError):
    pass

def sha(data):
    return hashlib.sha256(data).hexdigest()

class PlanGuard:
    def __init__(self, plan_path, expected_plan, source_paths):
        self.expected = {}
        self.checks = []
        self.bind(plan_path, expected_plan)
        # Pin independent expected bytes in trusted memory, not a replaceable sidecar.
        for path in source_paths:
            self.bind(path, Path(path).read_bytes())

    def bind(self, path, data):
        path = Path(path)
        expected = sha(data)
        if path in self.expected and self.expected[path] != expected:
            raise IntegrityError('Cannot replace an already bound artifact')
        self.expected[path] = expected

    def verify(self, stage):
        for path, expected in self.expected.items():
            if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != expected:
                raise IntegrityError('Frozen artifact mismatch: ' + path.name)
        self.checks.append({'stage': stage, 'bound_files': len(self.expected)})

    def call(self, stage, operation, *args, **kwargs):
        self.verify(stage)
        return operation(*args, **kwargs)

    def publish(self, path, summary):
        self.verify('before_summary')
        Path(path).write_text(json.dumps({**summary, 'integrity_checks': self.checks}, indent=2))
