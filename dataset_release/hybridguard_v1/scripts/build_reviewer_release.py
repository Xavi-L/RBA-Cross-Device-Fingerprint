#!/usr/bin/env python3
"""Build the anonymous, independently usable reviewer archive; never upload it.

Repository provenance is used only while building. None is copied into the
artifact. The frozen source lock and existing random ID map remain unchanged.
"""
from __future__ import annotations
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

import release
import reviewer_runtime as runtime
from common import canonical, write_json

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILES = runtime.PACKAGE_FILES
PREFIX = 'cross_view_consistency_v1/'
ARCHIVE_NAME = 'Cross_View_Consistency_Dataset_v1.0_Reviewer.zip'
TEMPLATES = ('README.md', 'DATASET_CARD.md', 'RELEASE_REVIEW.md',
             'LICENSE_DATA.md', 'FIGSHARE_UPLOAD.md')
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def check_inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Package root must be a real directory')
    entries = list(root.iterdir())
    if {p.name for p in entries} != set(PACKAGE_FILES):
        raise ValueError('Missing or unexpected package file')
    if any(p.is_symlink() or not p.is_file() for p in entries):
        raise ValueError('Package directories and symbolic links are forbidden')
    return sorted(entries)


def audit_anonymity(root, forbidden_terms=(), forbidden_digests=()):
    """Inspect actual deliverable files; never print matched identities or values."""
    files = check_inventory(root)
    names = [str(x).casefold() for x in forbidden_terms if len(str(x)) >= 3]
    digests = {str(x).lower() for x in forbidden_digests}
    for path in files:
        content = path.read_text(encoding='utf-8')
        folded = content.casefold()
        if any(name in folded for name in names):
            raise ValueError('Private identity or source path detected in ' + path.name)
        found = set(re.findall(r'(?<![a-fA-F0-9])[a-fA-F0-9]{64}(?![a-fA-F0-9])', content))
        if found or {x.lower() for x in found} & digests:
            raise ValueError('Source/file digest is not permitted in anonymous package: ' + path.name)
        # These concrete-value patterns also inspect script strings/comments;
        # their regex definitions do not themselves resemble real credentials.
        patterns = (
            r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
            r'/(?:Users|home)/[^\s/]+',
            r'https?://(?:www\.)?(?:github\.com|gitlab\.com)/[^\s)]+',
            r'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]+',
            r'\bBearer\s+[A-Za-z0-9._~+/-]{8,}',
            r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            r'\b(?:Author|Creator|LastModifiedBy)\s*[:=]\s*[^\s]+',
            r'\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
        )
        if any(re.search(pattern, content, re.I) for pattern in patterns):
            raise ValueError('Anonymity or credential pattern detected in ' + path.name)
    return {'status': 'PASS_NO_MATCHES', 'files_scanned': len(files),
            'private_paths_author_identity_credentials': 'PASS',
            'source_sha256_catalogue_excluded': 'PASS',
            'git_history_logs_mapping_and_document_metadata_excluded': 'PASS',
            'limits': 'Pattern/allowlist checks do not prove immunity to inference or external content matching.'}


def write_zip(root, target):
    files = check_inventory(root)
    target = Path(target)
    if target.is_symlink():
        raise ValueError('Archive destination cannot be a symbolic link')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(PREFIX + path.name, FIXED_TIME)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return target


def validate_archive(target):
    with zipfile.ZipFile(target) as archive:
        entries = archive.infolist()
        names = [x.filename for x in entries]
        if len(names) != len(set(names)) or set(names) != {PREFIX + name for name in PACKAGE_FILES}:
            raise ValueError('Archive member allowlist mismatch')
        if archive.comment:
            raise ValueError('Archive comments are forbidden')
        for entry in entries:
            path = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or entry.is_dir() or not stat.S_ISREG(mode):
                raise ValueError('Unsafe archive member')
            if (entry.date_time != FIXED_TIME or entry.extra or entry.comment or
                    entry.create_system != 3 or mode != stat.S_IFREG | 0o644 or
                    entry.flag_bits & 1 or entry.compress_type != zipfile.ZIP_DEFLATED):
                raise ValueError('Noncanonical or identifying archive metadata')
        if archive.testzip() is not None:
            raise ValueError('Archive CRC integrity check failed')
    return {'status': 'PASS', 'files': len(entries), 'crc_integrity': 'PASS',
            'member_paths_and_metadata': 'PASS'}


def private_scan_inputs():
    repo = ROOT.parents[1]
    terms = {getpass.getuser(), Path.home().name, str(repo), repo.name, 'HybridGuard',
             'hybridguard_agent/', 'dataset_release/', 'output/pdf/'}
    for key in ('user.name', 'user.email'):
        value = subprocess.run(['git', 'config', key], cwd=repo, capture_output=True, text=True, check=False).stdout.strip()
        if len(value) >= 3:
            terms.add(value)
    remote = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=repo, text=True).strip()
    terms.add(remote.rstrip('/').rsplit('/', 2)[-2].rsplit(':', 1)[-1])
    lock = json.loads((ROOT / '.private/source_lock.json').read_text())
    # File-level digests can identify an otherwise renamed anonymous release.
    digests = {entry['sha256'] for entry in lock['inputs']}
    terms.update(entry['path'] for entry in lock['inputs'])
    mapping = json.loads((ROOT / '.private/identity_map.json').read_text())
    original_ids = set()
    for category in mapping.values():
        for key in category:
            original_ids.update(re.findall(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', key))
    return terms, digests, original_ids


def verify_preservation(tables):
    baseline = ROOT / '.private/pre_reviewer_baseline'
    if not baseline.exists():
        raise ValueError('Preservation baseline is required; snapshot the existing candidate before conversion')
    baseline_tables = runtime.load_tables(baseline)
    for name in runtime.DATA_FILES:
        before = baseline_tables[name]
        after = tables[name]
        if name == 'metadata.jsonl':
            before = [{**row, 'public_release_status': runtime.RELEASE_STATUS} for row in before]
        if before != after:
            raise ValueError('Existing observation, relationship, label, group, or redaction changed: ' + name)
    for name in ('identity_map.json', 'source_lock.json'):
        if (baseline / name).read_bytes() != (ROOT / '.private' / name).read_bytes():
            raise ValueError('Private random identity map or historical source freeze changed')
    return 'PASS_ALL_RECORDS_IDS_LABELS_RELATIONSHIPS_REDACTIONS_AND_MISSINGNESS'


DATA_CONTENT_FILES = runtime.DATA_FILES + ('statistics.json',)


def data_file_digests(archive_path):
    """Hash only the five published data resources required for license updates."""
    result = {}
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        for name in DATA_CONTENT_FILES:
            member = PREFIX + name
            if names.count(member) != 1:
                raise ValueError('Missing or duplicate data member: ' + name)
            checksum = hashlib.sha256()
            with archive.open(member) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    checksum.update(chunk)
            result[name] = checksum.hexdigest()
    return result


def verify_data_unchanged(before_archive, after_archive):
    before = data_file_digests(before_archive)
    after = data_file_digests(after_archive)
    if before != after:
        changed = sorted(name for name in before if before[name] != after[name])
        raise ValueError('Published data changed during metadata-only update: ' + ', '.join(changed))
    return {'status': 'PASS', 'algorithm': 'SHA-256',
            'files': {name: {'before_sha256': before[name], 'after_sha256': after[name],
                             'unchanged': True} for name in DATA_CONTENT_FILES}}


def build(preserve_data_from=None):
    private = ROOT / '.private'
    candidate = private / 'candidate'
    # This is the independent packaging path. Source-building remains an
    # explicit separate command; package assembly never recollects or refits.
    release.ensure_preservation_baseline()
    release.check_lock(ROOT.parents[1])
    release.verify(candidate)
    evidence = release.verify_evidence(ROOT.parents[1], candidate)
    tables = runtime.load_tables(candidate)
    preservation = verify_preservation(tables)
    schema = runtime.read_json(ROOT / 'schema.json')
    catalog = runtime.read_json(ROOT / 'field_catalog.json')
    quality = runtime.validate_tables(tables, schema, catalog)
    statistics = runtime.compute_statistics(tables)
    terms, digests, original_ids = private_scan_inputs()
    with tempfile.TemporaryDirectory(prefix='reviewer_stage_', dir=private) as temporary:
        stage = Path(temporary)
        for name in runtime.DATA_FILES:
            shutil.copyfile(candidate / name, stage / name)
        for name in ('schema.json', 'field_catalog.json', 'SCHEMA.md', 'STATISTICS.md'):
            shutil.copyfile(ROOT / name, stage / name)
        for name in TEMPLATES:
            shutil.copyfile(ROOT / 'reviewer_templates' / name, stage / name)
        shutil.copyfile(ROOT / 'scripts/reviewer_runtime.py', stage / 'validate.py')
        shutil.copyfile(ROOT / 'scripts/load_example.py', stage / 'load_example.py')
        write_json(stage / 'statistics.json', statistics)
        quality.update(evidence)
        quality.update(public_authorization='CONFIRMED_BY_PROJECT_LEAD',
                       publication_status=runtime.RELEASE_STATUS, release_records=len(tables['features.jsonl']),
                       preservation=preservation, statistics_recomputed='PASS',
                       validation_stage='prepackaging; run validate.py to verify the unpacked files')
        write_json(stage / 'quality_report.json', quality)
        inventory = [{'path': name, 'bytes': (stage / name).stat().st_size}
                     for name in sorted(PACKAGE_FILES - {'manifest.json'})]
        write_json(stage / 'manifest.json', {
            'dataset_version': '1.0', 'title': 'Cross-View Consistency Dataset v1.0',
            'publication_status': runtime.RELEASE_STATUS, 'release_records': 1509,
            'public_authorization': 'Project lead explicitly confirmed all included sources may be publicly released.',
            'source_ids': sorted(statistics['sources']), 'data_license': runtime.DATA_LICENSE,
            'data_license_url': runtime.DATA_LICENSE_URL, 'data_license_file': 'LICENSE_DATA.md',
            'data_license_scope': sorted(runtime.DATA_LICENSE_FILES),
            'software_license': runtime.SOFTWARE_LICENSE,
            'software_license_scope': sorted(runtime.SOFTWARE_FILES),
            'independent_physical_devices': None, 'independent_experiment_replication': False,
            'file_inventory': inventory,
            'inventory_scope': 'All package files except this manifest; byte sizes, no original source digests or paths.',
            'reproduction_scope': 'Load released observations, validate structure and relationships, reproduce descriptive statistics. No full original detector replay.',
        })
        validation = runtime.validate(stage)
        anonymity = audit_anonymity(stage, terms, digests)
        for name in runtime.DATA_FILES:
            content = (stage / name).read_text()
            identifiers = set(re.findall(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', content))
            if identifiers & original_ids:
                raise ValueError('Original source identifier leaked into release')
        anonymity['original_uuid_identifiers_excluded'] = 'PASS'
        target = ROOT / 'reviewer_release' / ARCHIVE_NAME
        pending_archive = private / 'reviewer_pending.zip'
        write_zip(stage, pending_archive)
        archive_report = validate_archive(pending_archive)
        isolated = Path(tempfile.mkdtemp(prefix='cross_view_reviewer_', dir='/private/tmp'))
        with zipfile.ZipFile(pending_archive) as archive:
            archive.extractall(isolated)
        unpacked = isolated / PREFIX.rstrip('/')
        env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME')}
        def run_script(script, *args):
            result = subprocess.run([sys.executable, '-I', str(unpacked / script), *args],
                                    cwd=isolated, env=env, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        standalone = run_script('validate.py', '--root', str(unpacked), '--recompute-statistics', str(isolated / 'recomputed-statistics.json'))
        loaded = run_script('load_example.py', '--data', str(unpacked))
        if runtime.read_json(isolated / 'recomputed-statistics.json') != statistics:
            raise ValueError('Independent directory statistics mismatch')
        if loaded['observations'] != 1509:
            raise ValueError('Independent directory did not load every observation')
        # Inspect the bytes actually extracted, including their documentation.
        audit_anonymity(unpacked, terms, digests)
        comparison_archive = Path(preserve_data_from) if preserve_data_from is not None else target
        comparison = (verify_data_unchanged(comparison_archive, pending_archive)
                      if comparison_archive.exists() else None)
        if preserve_data_from is not None and comparison is None:
            raise ValueError('Requested pre-update archive does not exist')
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(pending_archive, target)
        inventory.append({'path': 'manifest.json', 'bytes': (stage / 'manifest.json').stat().st_size})
        report = {'status': 'PASS', 'archive': 'reviewer_release/' + ARCHIVE_NAME,
                  'archive_bytes': target.stat().st_size, 'file_inventory': sorted(inventory, key=lambda x: x['path']),
                  'uncompressed_bytes': sum(x['bytes'] for x in inventory),
                  'release_records': 1509, 'hosted_public_data_records': 0,
                  'candidate_preservation': preservation, 'source_evidence_agreement': evidence,
                  'validation': validation, 'anonymity': anonymity, 'archive_validation': archive_report,
                  'standalone_validation': standalone, 'standalone_loading': loaded,
                  'statistics_recomputed_outside_repository': 'PASS', 'data_license': runtime.DATA_LICENSE,
                  'data_license_url': runtime.DATA_LICENSE_URL, 'software_license': runtime.SOFTWARE_LICENSE,
                  'archive_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        if comparison is not None:
            report['published_data_content_preservation'] = comparison
        write_json(ROOT / 'reviewer_release_report.json', report)
        write_json(private / 'reviewer_isolation.json', {'directory': str(unpacked), 'report': report})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preserve-data-from', type=Path, metavar='PREVIOUS_ZIP',
                        help='Require identical SHA-256 for four JSONL files and statistics.json before replacing the ZIP')
    args = parser.parse_args()
    report = build(preserve_data_from=args.preserve_data_from)
    print(canonical({key: report[key] for key in ('status', 'archive', 'archive_bytes', 'release_records')}))


if __name__ == '__main__':
    main()
