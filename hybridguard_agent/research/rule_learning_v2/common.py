"""Small file-backed V2-A contract and artifact helpers."""
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V1 = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924'
FROZEN = V1 / 'R04_freeze_r1'
OUT = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v2_20260925/A_diagnosis_pilot'
DOC = ROOT / 'deliverables/v2_development'
SURFACES = ('native84', 'app_web67', 'host26')
ROLE = 'EXPOSED_RETROSPECTIVE_DEVELOPMENT'
VERSION = 'v2-a-adapter-1'


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def write_lines(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def write_csv(path, rows):
    rows = list(rows)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, tuple)) else v
                             for k, v in row.items()})


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def definitions():
    return read(FROZEN / 'data/definitions.json')


def folds():
    return [f for f in read(V1 / 'R02_matrix/FOLD_INPUT_MANIFEST.json')['folds']
            if f['fold_id'] in ('LOEO-v1-01', 'LOEO-v1-02', 'LOEO-v1-03')]


def budget_base():
    ledger = read(V1 / 'REAL_RESEARCH_BUDGET/ledger.json')
    link = read(V1 / 'REAL_RESEARCH_BUDGET/R09_TIMING_LINK.json')
    account = read(link['account_ref'])
    if (account['state'] != 'COMPLETED' or account['base_used_fit_jobs'] != ledger['used_fit_jobs']
            or account['base_charged_seconds'] != ledger['charged_seconds']
            or account['incremental_charged_seconds'] != link['additional_charged_seconds']
            or link['new_fit_jobs'] != 0):
        raise ValueError('V1_R09_BUDGET_LINK_UNRESOLVED')
    if any(j['state'] == 'RUNNING_RESERVED' for j in ledger['jobs'].values()):
        raise ValueError('V1_RESEARCH_JOB_STILL_RESERVED')
    charged = ledger['charged_seconds'] + link['additional_charged_seconds']
    return {'ledger_ref': relative(V1 / 'REAL_RESEARCH_BUDGET/ledger.json'),
            'r09_link_ref': relative(V1 / 'REAL_RESEARCH_BUDGET/R09_TIMING_LINK.json'),
            'r09_account_ref': relative(link['account_ref']),
            'used_fit_jobs': ledger['used_fit_jobs'], 'charged_seconds': charged,
            'v1_charged_seconds': ledger['charged_seconds'], 'r09_charged_seconds': link['additional_charged_seconds'],
            'limits': ledger['limits'], 'remaining_fits': ledger['limits']['max_fit_jobs'] - ledger['used_fit_jobs'],
            'remaining_seconds': ledger['limits']['wall_clock_seconds'] - charged}
