"""Read-only table/reference checks; never imports model code or runs inference.

Run: python3 deliverables/normal_app_behavior_review/validate_evidence.py
Prints JSON to stdout. The saved VALIDATION.json records the delivery-time run.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ALLOWED = {
    'SPEC_OR_API_DEFINED', 'ENGINE_IMPLEMENTATION_SUPPORTED',
    'FRAMEWORK_CAPABILITY', 'APP_DEFAULT_PATH_SUPPORTED',
    'APP_CONDITIONAL_PATH_SUPPORTED', 'NOT_FOUND_IN_SCOPED_CODE', 'UNRESOLVED',
}
checks = []


def check(name, condition):
    checks.append({'check': name, 'passed': bool(condition)})


def read_table(name):
    with (HERE / name).open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    check(name + ': rectangular', all(None not in row and all(v is not None for v in row.values()) for row in rows))
    return rows


def array(row, name):
    return json.loads(row[name])


registry = json.loads((HERE / 'SOURCE_REGISTER.json').read_text())
sources = registry['sources']
source_ids = {source['source_id'] for source in sources}
check('source IDs unique', len(source_ids) == len(sources))
required = {'source_id', 'kind', 'title', 'maintainer', 'url', 'accessed_date', 'version',
            'locator', 'minimum_claim', 'does_not_establish', 'dependency_ids', 'runtime_validation'}
check('source metadata complete', all(required <= source.keys() and all(source[k] not in ('', None) for k in required - {'dependency_ids'}) for source in sources))
check('source dependencies resolve', all(set(source['dependency_ids']) <= source_ids for source in sources))
check('source runtime NOT_PERFORMED', all(source['runtime_validation'] == 'NOT_PERFORMED' for source in sources))
check('source links http(s)', all(source['url'].startswith(('https://', 'http://')) for source in sources))
local = [source for source in sources if source.get('local_path')]
check('local source files and line ranges', all((ROOT / source['local_path']).is_file() and 1 <= source['line_start'] <= source['line_end'] <= len((ROOT / source['local_path']).read_text().splitlines()) for source in local))

apps = read_table('APP_CODE_EVIDENCE.csv')
fields = read_table('FIELD_BEHAVIOR.csv')
rules = read_table('RULE_IMPACT.csv')
app_ids = {row['evidence_id'] for row in apps}
check('app evidence IDs unique', len(app_ids) == len(apps))
check('field IDs unique', len({row['field_id'] for row in fields}) == len(fields))
check('rule IDs unique', len({row['rule_id'] for row in rules}) == len(rules))
check('all evidence source IDs resolve', all(set(array(row, 'source_ids')) <= source_ids for row in apps + fields + rules))
check('field/rule app IDs resolve', all(set(array(row, 'app_evidence_ids')) <= app_ids for row in fields + rules))
check('all table runtime NOT_PERFORMED', all(row['runtime_validation'] == 'NOT_PERFORMED' for row in apps + fields + rules))
check('app evidence canonical strengths', all(row['evidence_strength'] in ALLOWED for row in apps))
check('field/rule canonical strengths', all(set(array(row, 'evidence_strength')) <= ALLOWED for row in fields + rules))
check('E excluded', all(row['user_opt_in_status'] == 'USER_OPT_IN_OUT_OF_SCOPE' for row in apps if row['behavior_class'] == 'E'))
check('all rules unchanged', all(row['model_changed'] == 'NO' for row in rules))
selection = registry['initial_sample_selection']
projects = {row['project'] for row in apps}
check('all initial samples covered', {sample['project'] for sample in selection} == projects)
check('8 distinct Apps and 3 frameworks', Counter(sample['project_kind'] for sample in selection) == {'APP': 8, 'FRAMEWORK': 3})
check('all sample commits pinned', all(re.fullmatch('[a-f0-9]{40}', sample['resolved_commit']) for sample in selection))
check('no discovery sample mixed', registry['discovery_samples'] == [] and all(row['sampling_role'] == 'INITIAL_SAMPLE' for row in apps))
check('six primary field groups', {'UA_PLATFORM','LANGUAGE','TIMEZONE','MEMORY_CONCURRENCY','PLUGINS_MIME_PDF','WEBDRIVER'} <= {row['field_group'] for row in fields})
primary_groups = {'ua_platform', 'language', 'timezone', 'memory_concurrency', 'plugins_mime_pdf', 'webdriver'}
coverage = {project: set() for project in projects}
for row in apps:
    group = row['field_group'].lower()
    if group == 'all_target_field_groups_coverage':
        coverage[row['project']].update(primary_groups)
    elif group in primary_groups:
        coverage[row['project']].add(group)
check('every initial App/framework has six-group coverage records', all(groups == primary_groups for groups in coverage.values()))

base = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v2_20260925/C_confirmation/trials'
def literals(method):
    model = json.loads((base / ('V2-C__ALL_DEVELOPMENT_162__' + method + '__attempt01') / 'model.json').read_text())
    clauses = model['engine_structure']['clauses']
    assert all(len(clause['literals']) == 1 for clause in clauses)
    return model['model_id'], {literal['atom_id'] + ':' + literal['polarity'] for clause in clauses for literal in clause['literals']}

main_id, actual_web = literals('W0__R_KEEP_V1')
other_id, other_web = literals('W0__GREEDY_OR')
c0_id, actual_c0 = literals('C0__GREEDY_OR')
check('six final Web clauses match saved model exactly', len(actual_web) == 6 and actual_web == {row['atom_id'] for row in rules if row['rule_role'] == 'FINAL_WEB'})
check('W0 comparison model has same clauses', actual_web == other_web)
check('C0 final clause matches saved model exactly', actual_c0 == {row['atom_id'] for row in rules if row['rule_role'] == 'FINAL_C0'})
check('CPU is historical only', all(row['rule_role'] == 'HISTORICAL_NOT_FINAL' for row in rules if 'hardware_concurrency' in row['atom_id']))
ledger = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol/CANDIDATE_LEDGER.jsonl'
candidate_rows = [json.loads(line) for line in ledger.read_text().splitlines()]
actual_core = {row['normalized_identity'] for row in candidate_rows if row['candidate_use']['core'] and row['candidate_use']['selectable_on_App177']}
documented_core = {row['atom_id'].split(' ')[0].removesuffix(':POSITIVE') for row in rules if row['rule_role'] in {'FINAL_C0','C0_CANDIDATE_NOT_SELECTED'}}
check('ten canonical C0 candidates accounted for', len(actual_core) == 10 and actual_core == documented_core)

for name in ('REPORT.md','SCOPE.md'):
    content = (HERE / name).read_text()
    ids = set(re.findall(r'\[((?:LOC|EXT|OFF|APPA|APPB)-\d{3})\]', content))
    check(name + ': source IDs resolve', ids <= source_ids)
    targets = re.findall(r'\]\(([^)]+)\)', content)
    check(name + ': relative file links resolve', all((HERE / target.split('#')[0]).exists() or target == 'VALIDATION.json' for target in targets if not target.startswith(('https://','http://'))))

result = {
    'validation_kind': 'FORMAT_REFERENCE_AND_SAVED_MODEL_IDENTITY_ONLY',
    'status': 'PASS' if all(item['passed'] for item in checks) else 'FAIL',
    'checks_passed': sum(item['passed'] for item in checks),
    'checks_total': len(checks),
    'counts': {'sources': len(sources), 'app_evidence_rows': len(apps), 'field_rows': len(fields), 'rule_rows': len(rules), 'apps': 8, 'frameworks': 3},
    'saved_model_ids': [main_id, other_id, c0_id],
    'runtime_validation': 'NOT_PERFORMED',
    'new_fits': 0, 'new_predictions': 0, 'new_fingerprint_records': 0,
    'limits': 'PASS only checks structure, references and serialized rule identity; it does not confirm source truth, App runtime behavior, independent confirmation or FPR.',
    'checks': checks,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(result['status'] != 'PASS')
