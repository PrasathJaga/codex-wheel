"""Bounded archive collection on the trusted host, with no source execution."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

if "__WHEEL_EMBEDDED_ADAPTER__" not in globals():
    from preflight.petclinic_adapter import AdmissionError, admit_pair

MAX_COMPRESSED = 32 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024
MAX_FILES = 3000


def collect_archive(data, expected_sha256, root):
    if len(data) > MAX_COMPRESSED:
        raise AdmissionError("Compressed archive exceeds budget")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise AdmissionError("Archive digest differs from reviewed input")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            expanded = stream.read(MAX_EXPANDED + 1)
        if len(expanded) > MAX_EXPANDED:
            raise AdmissionError("Expanded archive exceeds budget")
        files, seen = {}, set()
        with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
            for member in archive:
                if len(seen) >= MAX_FILES:
                    raise AdmissionError("Archive entry budget exceeded")
                name = member.name.rstrip("/") if member.isdir() else member.name
                if name in seen:
                    raise AdmissionError("Duplicate archive path")
                seen.add(name)
                if not (member.isdir() or member.isfile()) or member.issparse():
                    raise AdmissionError("Links/sparse/special archive entries unsupported")
                if (not name or name.startswith("/") or "\\" in name or
                        any(part in ("", ".", "..") for part in name.split("/")) or
                        any(ord(c) < 32 or ord(c) == 127 for c in name)):
                    raise AdmissionError("Unsafe archive path")
                if name == root and member.isdir():
                    continue
                if not name.startswith(root + "/"):
                    raise AdmissionError("Unexpected archive root")
                relative = name[len(root) + 1:]
                if member.isdir():
                    continue
                if not 0 <= member.size <= MAX_FILE:
                    raise AdmissionError("File exceeds budget")
                source = archive.extractfile(member)
                if source is None:
                    raise AdmissionError("Missing regular-file content")
                content = source.read(MAX_FILE + 1)
                if len(content) != member.size:
                    raise AdmissionError("Truncated file content")
                # Fail closed if path text cannot be represented canonically.
                relative.encode("utf-8", errors="strict")
                files[relative] = content
        if not files:
            raise AdmissionError("Empty source archive")
        for path in files:
            parts = path.split("/")
            if any("/".join(parts[:i]) in files for i in range(1, len(parts))):
                raise AdmissionError("File/directory prefix collision")
        return files
    except (OSError, tarfile.TarError, UnicodeError, EOFError) as error:
        raise AdmissionError("Malformed source archive") from error


def normalized_archive(files):
    """Reconstruct only checked regular files; discard input ownership/PAX/modes."""
    result = io.BytesIO()
    with gzip.GzipFile(fileobj=result, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for path, content in sorted(files.items()):
                info = tarfile.TarInfo("admitted/" + path)
                info.size, info.mode, info.mtime = len(content), 0o644, 0
                info.uid = info.gid = 0
                archive.addfile(info, io.BytesIO(content))
    return result.getvalue()


def prepare_pair(baseline, candidate, policy):
    root = "spring-petclinic-rest-" + policy["upstream_revision"]
    base_files = collect_archive(baseline, policy["baseline_archive_sha256"], root)
    candidate_files = collect_archive(candidate, policy["candidate_archive_sha256"], root)
    base_map = {p: hashlib.sha256(v).hexdigest() for p, v in base_files.items()}
    candidate_map = {p: hashlib.sha256(v).hexdigest() for p, v in candidate_files.items()}
    admitted = admit_pair(base_map, candidate_map)
    base_tar, candidate_tar = normalized_archive(base_files), normalized_archive(candidate_files)
    report = {"status": "admitted", "upstream_revision": policy["upstream_revision"],
              "baseline_archive_sha256": policy["baseline_archive_sha256"],
              "candidate_archive_sha256": policy["candidate_archive_sha256"],
              "baseline_files": base_map, "candidate_files": candidate_map,
              "baseline_normalized_sha256": hashlib.sha256(base_tar).hexdigest(),
              "candidate_normalized_sha256": hashlib.sha256(candidate_tar).hexdigest(), **admitted}
    return base_tar, candidate_tar, report


def prepare_inputs(input_directory, evidence_directory, policy):
    source = Path(input_directory)
    evidence = Path(evidence_directory)
    try:
        # This workflow's live intake exercise is explicitly an unchanged control.
        # Future candidate acquisition requires a reviewed candidate artifact/hash.
        with (source / "upstream.tar.gz").open("rb") as stream:
            baseline = stream.read(MAX_COMPRESSED + 1)
        with (source / "candidate-input.tar.gz").open("rb") as stream:
            candidate = stream.read(MAX_COMPRESSED + 1)
        base_tar, candidate_tar, report = prepare_pair(baseline, candidate, policy)
        (source / "source.tar.gz").write_bytes(base_tar)
        (source / "candidate.tar.gz").write_bytes(candidate_tar)
        (evidence / "source-admission.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    except Exception as error:
        (evidence / "source-admission.json").write_text(json.dumps({
            "status": "source_admission_error", "error_type": type(error).__name__,
            "error": str(error)}, indent=2))
        raise
