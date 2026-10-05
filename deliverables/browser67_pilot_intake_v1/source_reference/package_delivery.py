"""Package a finalized local Browser67 delivery and verify the actual ZIP.

No directory scan is used for packaging. The delivery manifest is the evidence
allowlist; a Git byte audit permits only selected source/schema/catalog files.
Run --self-test while preparing, then --build only after delivery is finalized.
Original manifests, raw evidence, and collection programs are never modified.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[1]
DEFAULT_ZIP = WORKSPACE / "reports/week10/20261004_browser67_pilot/browser67_paired_pilot_evidence.zip"
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RESERVED_WINDOWS_NAMES = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)
FIXED_SUPPLEMENTS = (
    "source_current_git_audit.json", "upstream_contract_review.md",
    "delivery_method.md", "verifier_contract_tests.json",
    "package_delivery.py", "package_tool_tests.json",
)
CODE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".kt", ".kts", ".html", ".css", ".sql"}
SOURCE_PREFIXES = ("android_app/HybridGuard/", "web_probe/", "browser_probe_site/", "backend_server/", "hybridguard_agent/")
FORBIDDEN_PARTS = {
    "device_backup", "device_backups", "backups", "backup", "node_modules",
    "__pycache__", ".gradle", ".idea", "user data", "userdata", ".aws", ".ssh",
}


class PackageError(ValueError):
    """A concise error that does not print private evidence values."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackageError(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
    return value


def safe_name(value: str) -> str:
    """Reject ambiguous names before filesystem or ZIP operations."""
    require(isinstance(value, str) and bool(value), "PATH_REQUIRED")
    require(not any(ord(char) < 32 for char in value) and "\\" not in value and ":" not in value, "PATH_CHARACTER_INVALID")
    require(unicodedata.normalize("NFC", value) == value, "PATH_NORMALIZATION_INVALID")
    parts = value.split("/")
    require(not value.startswith("/") and all(part not in {"", ".", ".."} for part in parts), "PATH_ESCAPE")
    require(all(not part.endswith((" ", ".")) and not RESERVED_WINDOWS_NAMES.match(part) for part in parts), "WINDOWS_PATH_ALIAS")
    require(PurePosixPath(value).as_posix() == value, "PATH_NOT_CANONICAL")
    return value


def permitted_name(value: str) -> str:
    value = safe_name(value)
    lowered = value.casefold()
    parts = lowered.split("/")
    require(not FORBIDDEN_PARTS.intersection(parts), "PRIVATE_OR_GENERATED_PATH")
    require(not any(part.startswith("device_backup") for part in parts), "DEVICE_BACKUP_FORBIDDEN")
    require("private_profile_hmac" not in lowered and "hmac.key" not in lowered, "PRIVATE_KEY_FORBIDDEN")
    require(not lowered.endswith((".pem", ".key", ".p12", ".pfx", ".keystore", ".jks")), "PRIVATE_KEY_EXTENSION_FORBIDDEN")
    require(not any(part in {"chrome", "chromium"} for part in parts), "CHROME_USER_DATA_FORBIDDEN")
    if lowered.startswith("upstream/backend_server/"):
        require(not lowered.endswith(".jsonl") and not re.search(r"(?:collected|merged_sessions|receipts|pair_events|pair_provenance)", lowered), "HISTORICAL_BACKEND_DATA_FORBIDDEN")
    if ".git" in parts:
        require(lowered == "upstream/.git/head" or lowered == "upstream/.git/packed-refs"
                or lowered.startswith("upstream/.git/refs/"), "GIT_METADATA_NOT_ALLOWED")
    return value


def local_file(root: Path, name: str) -> Path:
    name = permitted_name(name)
    resolved_root = root.resolve()
    candidate = root.joinpath(*name.split("/"))
    current = root
    for part in name.split("/"):
        current = current / part
        require(not current.is_symlink(), "SOURCE_SYMLINK_FORBIDDEN")
    resolved = candidate.resolve()
    require(resolved.is_relative_to(resolved_root) and resolved.is_file(), "SOURCE_PATH_OUTSIDE_ROOT_OR_MISSING")
    return resolved


def jsonl_rows(name: str, data: bytes) -> int | None:
    if not name.endswith(".jsonl"):
        return None
    require(not data or data.endswith(b"\n"), "PARTIAL_JSONL_ROW")
    count = 0
    for line in data.split(b"\n"):
        if not line.strip():
            continue
        value = json.loads(line.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(PackageError("NONFINITE_JSON")))
        require(isinstance(value, dict), "JSONL_OBJECT_REQUIRED")
        count += 1
    return count


def identity(name: str, data: bytes) -> dict:
    require(len(data) <= MAX_FILE_BYTES, "FILE_TOO_LARGE")
    # A detection test/source string can mention a BEGIN sentinel without being
    # key material. Reject a complete PEM envelope containing base64 body lines.
    pem_private_key = rb"-----BEGIN ((?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----[ \t]*\r?\n(?:[A-Za-z0-9+/=]+[ \t]*\r?\n)+-----END \1-----"
    require(not re.search(pem_private_key, data), "PEM_PRIVATE_KEY_CONTENT_FORBIDDEN")
    return {"path": name, "bytes": len(data), "sha256": digest(data), "jsonl_rows": jsonl_rows(name, data)}


def validate_identity(actual: dict, expected: dict) -> None:
    require(type(expected.get("bytes")) is int and expected["bytes"] >= 0, "MANIFEST_BYTES_INVALID")
    require(bool(SHA256.fullmatch(expected.get("sha256", ""))), "MANIFEST_HASH_INVALID")
    require(actual["bytes"] == expected["bytes"], "MANIFEST_BYTES_MISMATCH")
    require(actual["sha256"] == expected["sha256"], "MANIFEST_HASH_MISMATCH")
    require(actual["jsonl_rows"] == expected.get("jsonl_rows"), "MANIFEST_JSONL_ROWS_MISMATCH")


def audited_source_allowed(name: str) -> bool:
    """An explicit type/path policy, never every entry in the source audit."""
    if not name.startswith(SOURCE_PREFIXES):
        return False
    lowered = name.casefold()
    if any(part in FORBIDDEN_PARTS or part in {"build", "data", "artifacts", "datasets"} for part in lowered.split("/")):
        return False
    suffix = PurePosixPath(name).suffix.casefold()
    if suffix in CODE_SUFFIXES:
        return True
    if suffix == ".json":
        return any(part in {"config", "schemas", "fixtures", "public"} for part in lowered.split("/")) or PurePosixPath(name).name in {"package.json", "package-lock.json", "tsconfig.json"}
    if suffix == ".csv":
        return "catalog" in PurePosixPath(name).name.casefold() or "registry" in PurePosixPath(name).name.casefold()
    return suffix == ".txt" and PurePosixPath(name).name.startswith("requirements")


def collect_whitelist(root: Path, pilot: str) -> tuple[dict, dict[str, dict], dict[str, str]]:
    manifest_name = "delivery/delivery_manifest.json"
    manifest = read_json(local_file(root, manifest_name))
    require(manifest.get("selected_pilot") == pilot and manifest.get("independent_verification") == "passed", "DELIVERY_NOT_FINALIZED_FOR_PILOT")
    require(type(manifest.get("files")) is list and bool(manifest["files"]), "MANIFEST_FILES_REQUIRED")
    expected: dict[str, dict] = {}
    origins: dict[str, str] = {}
    folded: dict[str, str] = {}

    def add(name: str, record: dict, basis: str) -> None:
        name = permitted_name(name)
        require(folded.get(name.casefold(), name) == name, "CASE_COLLIDING_PATHS")
        folded[name.casefold()] = name
        actual = identity(name, local_file(root, name).read_bytes())
        validate_identity(actual, record)
        if name in expected:
            require(expected[name] == actual, "CONFLICTING_WHITELIST_IDENTITY")
            return
        expected[name] = actual
        origins[name] = basis

    for row in manifest["files"]:
        require(isinstance(row, dict) and isinstance(row.get("path"), str), "MANIFEST_ENTRY_INVALID")
        require(row["path"] not in expected, "DUPLICATE_MANIFEST_PATH")
        add(row["path"], row, "delivery_manifest.files")
    for name in (manifest_name, *FIXED_SUPPLEMENTS):
        blob = local_file(root, name).read_bytes()
        add(name, identity(name, blob), "explicit_delivery_supplement")

    audit = read_json(local_file(root, "source_current_git_audit.json"))
    require(audit.get("pinned_commit") == manifest.get("source_commit"), "AUDIT_COMMIT_MISMATCH")
    require(isinstance(audit.get("files"), list) and bool(audit["files"]), "SOURCE_AUDIT_FILES_REQUIRED")
    for row in audit["files"]:
        require(isinstance(row, dict) and isinstance(row.get("path"), str), "AUDIT_ENTRY_INVALID")
        name = safe_name(row["path"])
        if row.get("matches_git", row.get("byte_equal")) is not True or not audited_source_allowed(name):
            continue
        actual_hash = row.get("actual_sha256", row.get("current_sha256"))
        actual_bytes = row.get("actual_bytes", row.get("current_bytes"))
        require(actual_hash == row.get("git_blob_sha256"), "AUDIT_GIT_IDENTITY_MISMATCH")
        add("upstream/" + name, {"bytes": actual_bytes, "sha256": actual_hash, "jsonl_rows": None}, "git_byte_audit_and_source_type_policy")

    # Only the minimum Git metadata read by the independent verifier is copied.
    head_name = "upstream/.git/HEAD"
    head_blob = local_file(root, head_name).read_bytes()
    add(head_name, identity(head_name, head_blob), "exact_head_and_commit_resolution")
    head = head_blob.decode("ascii").strip()
    commit = head
    if head.startswith("ref: "):
        reference = safe_name(head[5:])
        require(reference.startswith("refs/"), "HEAD_REFERENCE_INVALID")
        ref_name = "upstream/.git/" + reference
        if (root / ref_name).is_file():
            ref_blob = local_file(root, ref_name).read_bytes()
            add(ref_name, identity(ref_name, ref_blob), "exact_head_and_commit_resolution")
            commit = ref_blob.decode("ascii").strip()
        else:
            packed_name = "upstream/.git/packed-refs"
            packed_blob = local_file(root, packed_name).read_bytes()
            add(packed_name, identity(packed_name, packed_blob), "exact_head_and_commit_resolution")
            matched = [line.split()[0] for line in packed_blob.decode("ascii").splitlines() if line and not line.startswith(("#", "^")) and line.split()[1] == reference]
            require(len(matched) == 1, "HEAD_REFERENCE_UNRESOLVED")
            commit = matched[0]
    require(commit == manifest["source_commit"], "HEAD_COMMIT_MISMATCH")
    require(sum(row["bytes"] for row in expected.values()) <= MAX_TOTAL_BYTES, "PACKAGE_TOO_LARGE")
    require("verify_pilot.py" in expected and f"{pilot}/installed_collector.apk" in expected, "REPRODUCTION_INPUT_MISSING")
    return manifest, dict(sorted(expected.items())), origins


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2026, 10, 4, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    return info


def verify_zip(archive: Path, expected: dict[str, dict], index_blob: bytes) -> dict:
    all_expected = {**expected, "package_contents.json": identity("package_contents.json", index_blob)}
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        names = [item.filename for item in infos]
        require(len(names) == len(set(names)) and len(names) == len({name.casefold() for name in names}), "ZIP_DUPLICATE_PATH")
        require(set(names) == set(all_expected), "ZIP_WHITELIST_MISMATCH")
        require(sum(item.file_size for item in infos) <= MAX_TOTAL_BYTES, "ZIP_TOO_LARGE")
        for item in infos:
            permitted_name(item.filename)
            require(not item.is_dir() and not (item.flag_bits & 1), "ZIP_DIRECTORY_OR_ENCRYPTION_FORBIDDEN")
            require(stat.S_IFMT(item.external_attr >> 16) in {0, stat.S_IFREG}, "ZIP_LINK_OR_SPECIAL_FILE_FORBIDDEN")
            require(item.file_size == all_expected[item.filename]["bytes"], "ZIP_FILE_SIZE_MISMATCH")
        require(package.testzip() is None, "ZIP_CRC_MISMATCH")
        for item in infos:
            actual = identity(item.filename, package.read(item))
            validate_identity(actual, all_expected[item.filename])
        require(package.read("package_contents.json") == index_blob, "ZIP_INDEX_BYTES_MISMATCH")
    return {"file_count": len(all_expected), "uncompressed_bytes": sum(row["bytes"] for row in all_expected.values()),
            "crc_verified": True, "exact_whitelist_verified": True, "sha256_bytes_jsonl_rows_verified": True,
            "excluded_private_paths_absent": True}


def extract_verified(archive: Path, destination: Path, expected: dict[str, dict], index_blob: bytes) -> None:
    require(destination.is_dir() and not any(destination.iterdir()), "EXTRACTION_DIRECTORY_NOT_FRESH")
    verify_zip(archive, expected, index_blob)
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            name = permitted_name(item.filename)
            target = destination.joinpath(*name.split("/"))
            require(target.resolve().is_relative_to(destination.resolve()), "EXTRACTION_PATH_ESCAPE")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(package.read(item))
    for name, expected_row in expected.items():
        validate_identity(identity(name, local_file(destination, name).read_bytes()), expected_row)


def run_verifier(extracted: Path, pilot: str, self_test: bool) -> dict:
    arguments = [sys.executable, "-B", str(extracted / "verify_pilot.py"), "--root", str(extracted), "--pilot", pilot]
    if self_test:
        arguments.append("--self-test")
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": ""}
    result = subprocess.run(arguments, cwd=extracted, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=180, check=False)
    output_name = "verification_tests.json" if self_test else "verification.json"
    require((extracted / output_name).is_file(), "EXTRACTED_VERIFIER_REPORT_MISSING")
    report = read_json(extracted / output_name)
    require(result.returncode == 0, "EXTRACTED_VERIFIER_FAILED:" + str(report.get("failure_code", "UNKNOWN")))
    require(report.get("selected_pilot") == pilot, "EXTRACTED_VERIFIER_PILOT_MISMATCH")
    if self_test:
        require(report.get("real_data_baseline_passed") is True and report.get("original_evidence_modified") is False
                and type(report.get("tests")) is int and report["tests"] == report.get("passed")
                and report["tests"] == len(report.get("rejected_mutations", [])) + 1, "EXTRACTED_SELF_TEST_INCOMPLETE")
    else:
        require(report.get("verification") == "passed", "EXTRACTED_VERIFICATION_NOT_PASSED")
    return {"arguments": ["python", "-B", "verify_pilot.py", "--root", "<fresh_extracted_root>", "--pilot", pilot, *(["--self-test"] if self_test else [])],
            "returncode": result.returncode, "report": report, "stderr": result.stderr[-2000:]}


def build_package(root: Path, archive: Path, pilot: str) -> dict:
    root, archive = root.resolve(), archive.resolve()
    require(root == HERE and archive == DEFAULT_ZIP.resolve(), "PACKAGE_TARGET_OUTSIDE_AUTHORIZED_DIRECTORIES")
    require(not archive.exists(), "ARCHIVE_ALREADY_EXISTS")
    manifest, expected, origins = collect_whitelist(root, pilot)
    index = {"schema_version": "browser67-package-contents-v1", "source_commit": manifest["source_commit"],
             "selected_pilot": pilot, "delivery_manifest_sha256": expected["delivery/delivery_manifest.json"]["sha256"],
             "policy": "Exactly delivery_manifest.files, named delivery supplements, Git-byte-equal explicitly typed source/schema/catalog files, and minimum HEAD metadata. No whole-directory packaging.",
             "files": [{**row, "allowlist_basis": origins[name]} for name, row in expected.items()],
             "index_self_hash": "The ZIP hash in the external package_verification.json locks this index; no circular self-hash is asserted."}
    index_blob = json_bytes(index)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for name, expected_row in expected.items():
            blob = local_file(root, name).read_bytes()
            validate_identity(identity(name, blob), expected_row)
            package.writestr(zip_info(name), blob)
        package.writestr(zip_info("package_contents.json"), index_blob)
    zip_checks = verify_zip(archive, expected, index_blob)
    for name, expected_row in expected.items():
        validate_identity(identity(name, local_file(root, name).read_bytes()), expected_row)

    extracted = Path(tempfile.mkdtemp(prefix="browser67-package-extracted-", dir=WORKSPACE / "tmp"))
    extract_verified(archive, extracted, expected, index_blob)
    verification = run_verifier(extracted, pilot, False)
    for name, input_hash in verification["report"]["input_file_sha256"].items():
        name = permitted_name(name)
        require(name in expected and expected[name]["sha256"] == input_hash
                and digest(local_file(extracted, name).read_bytes()) == input_hash, "EXTRACTED_VERIFIER_INPUT_OUTSIDE_LOCKED_PACKAGE")
    tests = run_verifier(extracted, pilot, True)
    for name, expected_row in expected.items():
        if name not in {"verification.json", "verification_tests.json"}:
            validate_identity(identity(name, local_file(extracted, name).read_bytes()), expected_row)
        validate_identity(identity(name, local_file(root, name).read_bytes()), expected_row)
    zip_checks = verify_zip(archive, expected, index_blob)
    report = {"schema_version": "browser67-package-verification-v1", "verification": "passed",
              "verified_at_utc": datetime.now(timezone.utc).isoformat(), "selected_pilot": pilot,
              "source_commit": manifest["source_commit"], "archive": {"path": str(archive), "bytes": archive.stat().st_size, "sha256": digest(archive.read_bytes())},
              "delivery_manifest_sha256": expected["delivery/delivery_manifest.json"]["sha256"],
              "package_contents_sha256": digest(index_blob), "zip_checks": zip_checks,
              "allowlist_basis_counts": dict(Counter(origins.values())), "extracted_root": str(extracted),
              "independent_extracted_verification": verification,
              "independent_extracted_self_test": tests,
              "all_verifier_inputs_resolved_inside_extracted_root": True,
              "original_evidence_unchanged": True,
              "source_scope_note": "Only explicitly audited Git-byte-equal source files are supplemental. Historical and CRLF-different files may remain described by the audit but are not included as supplemental sources. No complete-checkout Git-clean or binary rebuild claim is made.",
              "privacy_scope": "Local evidence package contains experiment raw fingerprints and private ticket command logs from the explicit evidence allowlist. It excludes HMAC key, device backups, Chrome user data and PEM private keys; it was not transmitted externally."}
    report_path = archive.parent / "package_verification.json"
    with report_path.open("x", encoding="utf-8") as handle:
        handle.write(json_bytes(report).decode("utf-8"))
    return {"verification": "passed", "archive": str(archive), "report": str(report_path),
            "archive_sha256": report["archive"]["sha256"], "file_count": zip_checks["file_count"],
            "extracted_verification": "passed", "self_tests_passed": tests["report"]["passed"]}


def self_test() -> dict:
    """Exercise packaging boundaries with tiny disposable fixtures only."""
    passed = []
    def rejected(name: str, callback) -> None:
        try:
            callback()
        except (PackageError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            passed.append(name)
        else:
            raise PackageError("SELF_TEST_EXPECTED_REJECTION:" + name)

    for name in ["../escape", "/absolute", "C:/drive", "a\\b", "a//b", "a/./b", "file.", "CON", "nul.txt", "a\x00b"]:
        rejected("unsafe_path_" + repr(name), lambda name=name: safe_name(name))
    for name in ["private_profile_hmac.key", "device_backup/base.apk", "x/Chrome/User Data/file", "upstream/backend_server/raw_browser_payloads.jsonl", "server/private.pem", "upstream/.git/config"]:
        rejected("forbidden_path_" + name, lambda name=name: permitted_name(name))
    rejected("partial_jsonl", lambda: jsonl_rows("row.jsonl", b'{"x":1}'))
    rejected("invalid_jsonl", lambda: jsonl_rows("row.jsonl", b'invalid\n'))
    rejected("nonfinite_json", lambda: jsonl_rows("row.jsonl", b'{"x":NaN}\n'))
    rejected("private_key_content", lambda: identity("source.txt", b"-----BEGIN OPENSSH PRIVATE KEY-----\n" + b"A" * 64 + b"\n-----END OPENSSH PRIVATE KEY-----\n"))
    identity("source.py", b'"-----BEGIN OPENSSH PRIVATE KEY-----"')
    passed.append("source_detection_sentinel_is_not_key_material")
    require(jsonl_rows("row.jsonl", b'{"x":1}\n\n') == 1, "SELF_TEST_JSONL_VALID_FAILED")
    passed.append("valid_jsonl")
    require(audited_source_allowed("hybridguard_agent/schemas/test.schema.json")
            and audited_source_allowed("backend_server/main.py")
            and not audited_source_allowed("backend_server/merged_sessions.json")
            and not audited_source_allowed("hybridguard_agent/data/history.py"), "SELF_TEST_SOURCE_POLICY_FAILED")
    passed.append("explicit_source_policy")
    with tempfile.TemporaryDirectory(prefix="package-tool-test-", dir=WORKSPACE / "tmp") as temporary:
        root = Path(temporary)
        archive = root / "fixture.zip"
        blob, name = b'{"x":1}\n', "data/rows.jsonl"
        expected = {name: identity(name, blob)}
        index_blob = json_bytes({"files": list(expected.values())})
        with zipfile.ZipFile(archive, "x") as package:
            package.writestr(zip_info(name), blob)
            package.writestr(zip_info("package_contents.json"), index_blob)
        require(verify_zip(archive, expected, index_blob)["crc_verified"], "SELF_TEST_ZIP_FAILED")
        passed.append("exact_zip_roundtrip")
        extracted = root / "extracted"
        extracted.mkdir()
        extract_verified(archive, extracted, expected, index_blob)
        require((extracted / name).read_bytes() == blob, "SELF_TEST_EXTRACT_FAILED")
        passed.append("safe_fresh_extraction")
        rejected("nonfresh_extraction", lambda: extract_verified(archive, extracted, expected, index_blob))
        rejected("zip_hash_tampering", lambda: verify_zip(archive, {name: {**expected[name], "sha256": "0" * 64}}, index_blob))
        rejected("zip_whitelist_tampering", lambda: verify_zip(archive, {}, index_blob))
        wrong = {**expected[name], "jsonl_rows": 2}
        rejected("jsonl_count_tampering", lambda: validate_identity(expected[name], wrong))
    return {"schema_version": "browser67-package-tool-tests-v1", "tests": len(passed), "passed": len(passed), "synthetic_inputs_only": True,
            "tested_cases": passed, "source_sha256": digest(Path(__file__).read_bytes())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--self-test", action="store_true")
    actions.add_argument("--build", action="store_true")
    parser.add_argument("--root", type=Path, default=HERE)
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--pilot", default="pilot_r8")
    args = parser.parse_args()
    try:
        require(args.pilot == "pilot_r8", "UNAUTHORIZED_PILOT")
        if args.self_test:
            result = self_test()
            (HERE / "package_tool_tests.json").write_bytes(json_bytes(result))
        else:
            result = build_package(args.root, args.zip, args.pilot)
        print(json.dumps(result, ensure_ascii=False))
    except (PackageError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
        code = str(error) if isinstance(error, PackageError) else type(error).__name__
        print(json.dumps({"verification": "failed", "failure_code": code}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
