#!/usr/bin/env python3
"""Publish authorized B1 evidence, or reproduce its checks without either ZIP."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import intake
from path_compat import PILOT, run_verifier

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "evidence_archive"
LOCAL = HERE / "local_acceptance"
SOURCE = HERE / "source_reference"
MANIFEST = HERE / "PUBLICATION.json"
PATTERNS = {
    "google_api_key": rb"AIza[0-9A-Za-z_-]{35}",
    "github_token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    "openai_key": rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}",
    "aws_access_key": rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "slack_token": rb"xox[baprs]-[A-Za-z0-9-]{20,}",
    "pem_private_key": rb"-----BEGIN ((?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY)-----[ \t]*\r?\n(?:[A-Za-z0-9+/=]+[ \t]*\r?\n)+-----END \1-----",
}


def credential_findings(name, data):
    """Targeted known credential formats; never print values or claim exhaustive detection."""
    findings = [{"path": name, "kind": kind} for kind, pattern in PATTERNS.items() if re.search(pattern, data)]
    if name.endswith(".apk"):
        with zipfile.ZipFile(io.BytesIO(data)) as apk:
            for member in apk.infolist():
                if not member.is_dir():
                    findings.extend(credential_findings(name + "!" + member.filename, apk.read(member)))
    return findings


def stored_name(original):
    path = intake.relative_path(original)
    if path.parts[:2] == ("upstream", ".git"):
        return "upstream_git_metadata/" + "/".join(path.parts[2:])
    intake.require(".git" not in path.parts, "UNEXPECTED_NESTED_GIT_PATH")
    return path.as_posix()


def copy_exact(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        intake.require(destination.read_bytes() == source.read_bytes(), "EXISTING_PUBLIC_COPY_DIFFERS")
    else:
        shutil.copyfile(source, destination)


def publish():
    original = intake.PRIVATE / "originals/evidence"
    run_id = intake.read(intake.PRIVATE / "latest_run.json")["run_id"]
    run = intake.PRIVATE / "runs" / run_id
    intake.check_inventory(original)
    receipt = intake.read(run / "intake_receipt.json")
    intake.require(receipt["status"] == "passed", "LOCAL_INTAKE_NOT_PASSED")
    captures = intake.rows(original / PILOT / "captures.jsonl")
    expires = [row["ticket_expires_at"] for row in intake.rows(original / "data/browser_pair_events.jsonl") if "ticket_expires_at" in row]
    intake.require(len(expires) == 18 and all(datetime.fromisoformat(v.replace("Z", "+00:00")) < datetime.now(timezone.utc) for v in expires),
                   "UNEXPIRED_OR_MISSING_LOCAL_TICKET_EXPIRY")
    source = next((intake.PRIVATE / "originals/source").iterdir()) / "execution_log/browser67_pilot_20261004"
    # The ZIP's unrelated papers and other experiments are outside B1. This
    # directory contains all thirteen B1 public harness/reference files.
    sources = sorted(p for p in source.iterdir() if p.is_file())
    originals = sorted(p for p in original.rglob("*") if p.is_file())
    findings = []
    for path in originals + sources:
        findings.extend(credential_findings(path.name, path.read_bytes()))
    intake.write(intake.PRIVATE / "publication_credential_findings.json", findings)
    intake.require(not findings, "CREDENTIAL_PATTERN_MATCH_SEE_PRIVATE_FINDINGS")
    archive_entries = []
    for path in originals:
        name = path.relative_to(original).as_posix()
        mapped = stored_name(name)
        copy_exact(path, ARCHIVE / mapped)
        archive_entries.append({"original_path": name, "stored_path": mapped,
                                "bytes": path.stat().st_size, "sha256": intake.sha(path)})
    for path in sources:
        copy_exact(path, SOURCE / path.name)
    LOCAL.mkdir(exist_ok=True)
    transformations = []
    excluded = ["git_before.json", "final_git_scope.json"]
    replacements = [(str(original), "${EVIDENCE_ROOT}"), (str(run), "${REVIEW_RUN}"),
                    (str(intake.REPO), "${REPO_ROOT}")]
    for path in sorted(run.rglob("*")):
        if not path.is_file() or path.name in excluded:
            continue
        relative = path.relative_to(run)
        target = LOCAL / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        text = data.decode("utf-8")
        if path.suffix == ".json":
            # Substitution is made in parsed strings, so escaped paths in JSON
            # remain syntactically valid. Hash fields keep their original meaning.
            def replace(value):
                if isinstance(value, str):
                    for old, new in replacements:
                        value = value.replace(old, new)
                    return value
                if isinstance(value, dict):
                    return {key: replace(v) for key, v in value.items()}
                if isinstance(value, list):
                    return [replace(v) for v in value]
                return value
            value = intake.read(path)
            changed = replace(value)
            if changed != value:
                intake.write(target, changed)
            else:
                target.write_bytes(data)
        else:
            for old, new in replacements:
                text = text.replace(old, new)
            target.write_bytes(text.encode("utf-8"))
        intake.require(str(intake.REPO) not in target.read_text(), "LOCAL_HOST_PATH_REMAINS")
        findings = credential_findings(relative.as_posix(), target.read_bytes())
        intake.require(not findings, "DERIVED_CREDENTIAL_PATTERN_MATCH")
        if target.read_bytes() != data:
            transformations.append({"path": relative.as_posix(), "change": "local absolute paths replaced by documented placeholders"})
    publication = {
        "schema_version": "browser67-authorized-evidence-publication-v1",
        "scope": "User authorized useful B1 evidence publication except credentials and the two ZIPs; no new collection or scoring.",
        "archive_file_count": len(archive_entries), "archive_total_bytes": sum(v["bytes"] for v in archive_entries),
        "original_measurement_bytes_unchanged": True, "archive_files": archive_entries,
        "source_reference_file_count": len(sources), "local_acceptance_source_run": run_id,
        "derived_path_transformations": transformations,
        "excluded": {"zip_files": list(v[0] for v in intake.PACKAGES.values()),
                     "unrelated_workspace_inventory": excluded,
                     "credentials": "No credential files supplied; original package excludes HMAC key, keystores, Chrome profiles and backups."},
        "credential_review": {"known_format_scan_matches": 0, "apk_contents_included_in_scan": True,
                              "scope": "Known API/access-token formats and complete PEM private keys, plus manual review of credential-like JSON field names; not an exhaustive secret detection guarantee.",
                              "source_test_markers": "Private-key BEGIN strings are scanner/test source, not complete private-key material.",
                              "hmac": "Only key ID/source metadata and HMAC-derived evidence; no HMAC key; no new signature verification.",
                              "local_ticket_count": len(expires), "latest_local_ticket_expiry": max(expires),
                              "local_tickets": "Expired local-loopback experiment tickets retained for control-order and pair provenance review."},
        "browser_products": sorted({v["browser_version"]["product"] for v in captures}),
        "git_metadata": "Two identity files stored in upstream_git_metadata, restored only inside temporary review inputs; never a nested Git repository.",
        "byte_preservation": "evidence_archive/**, local_acceptance/** and source_reference/** use -text in .gitattributes.",
    }
    intake.write(MANIFEST, publication)
    return {"published_archive_files": len(archive_entries), "source_reference_files": len(sources), "path_normalized_derived_files": len(transformations)}


def materialize(destination, archive=ARCHIVE, manifest=MANIFEST):
    publication = intake.read(manifest)
    intake.require(not destination.exists(), "REVIEW_INPUT_DIRECTORY_ALREADY_EXISTS")
    entries = publication["archive_files"]
    intake.require(len(entries) == publication["archive_file_count"] == 488, "PUBLIC_ARCHIVE_COUNT_MISMATCH")
    expected = {row["stored_path"] for row in entries}
    intake.require(len(expected) == len(entries), "DUPLICATE_PUBLIC_ARCHIVE_PATH")
    actual = {p.relative_to(archive).as_posix() for p in archive.rglob("*") if p.is_file()}
    intake.require(actual == expected, "PUBLIC_ARCHIVE_INVENTORY_MISMATCH")
    for row in entries:
        original = intake.relative_path(row["original_path"])
        intake.require(row["stored_path"] == stored_name(original.as_posix()), "PUBLIC_ARCHIVE_MAPPING_MISMATCH")
        source = archive / row["stored_path"]
        intake.require(source.resolve().is_relative_to(archive.resolve()) and not source.is_symlink(), "PUBLIC_ARCHIVE_PATH_ESCAPE")
        intake.require(source.stat().st_size == row["bytes"] and intake.sha(source) == row["sha256"], "PUBLIC_ARCHIVE_BYTES_MISMATCH:" + row["stored_path"])
    destination.mkdir(parents=True)
    for row in entries:
        copy_exact(archive / row["stored_path"], destination / row["original_path"])
    intake.check_inventory(destination)
    return publication


def verify(output):
    intake.require(not output.exists(), "REVIEW_OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    root = output / "inputs"
    publication = materialize(root)
    before = intake.tree_hashes(root)
    verification = run_verifier(root, output / "verification.json")
    tests = run_verifier(root, output / "verification_tests.json", self_test=True)
    intake.require(verification == intake.read(root / "verification.json") and tests == intake.read(root / "verification_tests.json"), "ARCHIVED_REPORT_DIFFERENCE")
    config = output / "sources.local.json"
    intake.generate_config(root, config)
    from hybridguard_agent.scripts.build_latest_paired244_snapshot import build_snapshot
    from hybridguard_agent.scripts.build_latest_experiment_plan import build_plan
    snapshot = output / "paired244_snapshot"
    build_snapshot(config, snapshot, "browser67_public_review")
    comparison, members = intake.compare_snapshots(root / "delivery/paired244_snapshot", snapshot)
    intake.write_rows(output / "member_comparison.jsonl", members)
    intake.write_rows(output / "stage_inventory.jsonl", intake.stage_inventory(root, snapshot))
    readiness = build_plan(snapshot, output / "experiment_plan", facts_path=root / "delivery/latest_experiment_facts.jsonl")
    intake.require(readiness == intake.read(root / "delivery/experiment_plan/experiment_readiness.json"), "READINESS_DIFFERENCE")
    intake.require(before == intake.tree_hashes(root), "PUBLISHED_EVIDENCE_CHANGED_DURING_REVIEW")
    result = {"schema_version": "browser67-public-evidence-review-v1", "status": "passed", "zip_required": False,
              "archive_files_verified": publication["archive_file_count"], "verification_stages": verification["verified_stages"],
              "self_tests_passed": tests["passed"], "rebuild": comparison,
              "qc_counts": intake.read(snapshot / "qc_summary.json")["counts"],
              "readiness": readiness, "evidence_unchanged": True,
              "operations": {"new_collection": 0, "training": 0, "detector_scoring": 0},
              "whole_zip_verification": "Historical intake attestation; ZIPs are not published or rehashed by this command."}
    intake.write(output / "review_summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["publish", "verify"])
    parser.add_argument("--output", type=Path, help="New output directory; default is a disposable temporary directory")
    args = parser.parse_args()
    if args.command == "publish":
        result = publish()
    elif args.output:
        result = verify(args.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="browser67-public-review-") as directory:
            result = verify(Path(directory) / "review")
    print(intake.canonical(result))


if __name__ == "__main__":
    main()
