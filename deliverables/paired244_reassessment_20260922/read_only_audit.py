import collections
import datetime
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hybridguard_agent.scripts.build_latest_paired244_snapshot import (
    load_catalog, validate_app_payload, validate_browser_payload, feature_map, APP_ROOTS,
)

P = ROOT / 'backend_server/collection_runs/mtc_20260917'
def read(name):
    return [json.loads(line) for line in (P / name).read_text().splitlines() if line.strip()]

cfg = json.loads((ROOT / 'hybridguard_agent/config/latest_paired244_sources.json').read_text())
rel = cfg['release']
app_fields, browser_fields, app_types, browser_types = load_catalog(ROOT / cfg['sources']['feature_catalog'], 177, 67)
ar = read('raw_expanded_payloads.jsonl')
br = read('raw_browser_payloads.jsonl')
analysis = read('expanded_collected_data.jsonl')
provenance = read('browser_pair_provenance.jsonl')
pairs = [p for p in provenance if p.get('pair_status') == 'completed']
aridx = {r['receipt_id']: r for r in ar}
bridx = {r['browser_receipt_id']: r for r in br}
installs, profiles, models, versions, apis, manufacturers, browsers = (collections.Counter() for _ in range(7))
errors = collections.Counter()
status_totals = {'app': collections.Counter(), 'browser': collections.Counter()}
field_states = {'app': collections.defaultdict(collections.Counter), 'browser': collections.defaultdict(collections.Counter)}
observed_per_row = {'app': [], 'browser': [], 'paired': []}
comparison = collections.defaultdict(collections.Counter)
version_details = collections.defaultdict(lambda: {'samples': 0, 'profiles': set()})
status_by_version = collections.defaultdict(collections.Counter)
valid = 0
binding_errors = collections.Counter()
receipt_alias_cases = []
shape_cases = []
feature_count_distr = {'app': collections.Counter(), 'browser': collections.Counter()}
for p in pairs:
    a = aridx.get(p['app_receipt_id'])
    b = bridx.get(p['browser_receipt_id'])
    if a is None:
        alternatives = [row for row in ar if row['session_id'] == p['app_session_id'] and row['payload_sha256'] == p['app_payload_sha256']]
        if len(alternatives) == 1:
            binding_errors['app_duplicate_receipt_points_to_original_payload_archive'] += 1
            a = alternatives[0]
            receipt_alias_cases.append({'app_session_id': p['app_session_id'], 'pair_id': p['pair_id'], 'paired_at': p['paired_at']})
    if a is None or b is None:
        binding_errors['missing_raw_receipt_unresolved'] += 1
        continue
    for source, key, expected in [(a, 'session_id', p['app_session_id']), (b, 'app_session_id', p['app_session_id']), (b, 'pair_id', p['pair_id'])]:
        if source.get(key) != expected: binding_errors[key] += 1
    av, bv = a['canonical_received_payload'], b['canonical_received_payload']
    m = av['collection_manifest']
    this_rel = dict(rel, featureapp_version_code=m['collector_version_code'], featureapp_version_name=m['collector_version_name'])
    ae, af, ast = validate_app_payload(av, this_rel, app_fields, app_types)
    be, bf, bst = validate_browser_payload(bv, this_rel, browser_fields, browser_types)
    errors.update(ae + be)
    if ae or be:
        shape_cases.append({'pair_id': p['pair_id'], 'app_session_id': p['app_session_id'], 'manufacturer': m['manufacturer'], 'model': m['model'], 'android_release': m['android_release'], 'app_field_count': len(af), 'reasons': ae + be, 'missing_app_field_statuses': {field: ast.get(field) for field in sorted(set(app_fields) - set(af))}})
    valid += not (ae or be)
    feature_count_distr['app'][len(af)] += 1
    feature_count_distr['browser'][len(bf)] += 1
    profile = (m['manufacturer'], m['model'], m['android_release'])
    profiles[profile] += 1
    models[profile[:2]] += 1
    installs[m['collector_install_id']] += 1
    versions[m['collector_version_name']] += 1
    apis[str(m['android_api'])] += 1
    manufacturers[m['manufacturer']] += 1
    browsers[p.get('selected_browser_package', '')] += 1
    version_details[m['collector_version_name']]['samples'] += 1
    version_details[m['collector_version_name']]['profiles'].add(profile)
    for lane, states in [('app', ast), ('browser', bst)]:
        status_totals[lane].update(states.values())
        observed_per_row[lane].append(sum(v == 'observed' for v in states.values()))
        status_by_version[m['collector_version_name'] + '/' + lane].update(states.values())
        for field, state in states.items(): field_states[lane][field][state] += 1
    observed_per_row['paired'].append(observed_per_row['app'][-1] + observed_per_row['browser'][-1])
    for field in browser_fields:
        if ast.get(field) == 'observed' and bst.get(field) == 'observed':
            comparison[field]['both_observed'] += 1
            literal_equal = json.dumps(af.get(field),sort_keys=True,separators=(',',':')) == json.dumps(bf.get(field),sort_keys=True,separators=(',',':'))
            comparison[field]['literal_equal' if literal_equal else 'literal_different'] += 1
            comparison[field]['semantic_equal' if af.get(field) == bf.get(field) else 'semantic_different'] += 1
            if not literal_equal and af.get(field) == bf.get(field): comparison[field]['numeric_serialization_only_difference'] += 1
        else:
            comparison[field]['unavailable'] += 1

stats = {
    'checked_at': datetime.datetime.now().astimezone().isoformat(),
    'scope': str(P.relative_to(ROOT)),
    'audit_kind': 'read_only_contract_and_coverage_assessment_not_formal_snapshot',
    'completed_pairs': len(pairs), 'unique_pair_ids': len({p['pair_id'] for p in pairs}),
    'unique_app_sessions': len({p['app_session_id'] for p in pairs}),
    'unique_install_profiles': len(installs), 'unique_manufacturer_model': len(models),
    'unique_manufacturer_model_android_release': len(profiles),
    'repeated_install_groups': sum(n > 1 for n in installs.values()),
    'extra_install_sessions': sum(n - 1 for n in installs.values()),
    'repeated_model_os_groups': sum(n > 1 for n in profiles.values()),
    'extra_model_os_sessions': sum(n - 1 for n in profiles.values()),
    'app_analysis_rows': len(analysis), 'app_analysis_unique_sessions': len({a['session_id'] for a in analysis}),
    'paired_release_counts': dict(versions), 'paired_android_api_counts': dict(sorted(apis.items(), key=lambda kv: int(kv[0]))),
    'manufacturer_count': len(manufacturers), 'browser_package_counts': dict(browsers),
    'last_completed_at_utc': max(p['paired_at'] for p in pairs),
    'paired_raw_contract_pass_count': valid, 'paired_raw_contract_error_counts': dict(errors),
    'binding_errors': dict(binding_errors), 'feature_count_distributions': feature_count_distr,
    'receipt_alias_cases': receipt_alias_cases, 'shape_cases': shape_cases,
    'status_totals': status_totals,
    'observed_counts': {k: {'min': min(v), 'median': statistics.median(v), 'max': max(v), 'all_observed_rows': sum(x == {'app':177, 'browser':67, 'paired':244}[k] for x in v)} for k,v in observed_per_row.items()},
    'field_status_counts': field_states, 'app_browser_same_named_field_comparison': comparison,
    'version_strata': {k: {'samples': v['samples'], 'model_os_profiles': len(v['profiles'])} for k,v in version_details.items()},
    'status_by_version': status_by_version,
    'active_batch': json.loads((P/'active_collection_batch.json').read_text())['collection_batch_id'],
}
all_app_profiles = {(a['collection_manifest']['manufacturer'], a['collection_manifest']['model'], a['collection_manifest']['android_release']) for a in analysis}
stats['all_app_model_os_profiles'] = len(all_app_profiles)
stats['app_model_os_profiles_without_completed_pair'] = len(all_app_profiles - set(profiles))
out = pathlib.Path(__file__).resolve().with_name('AUDIT.json')
out.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n')
small = {k:v for k,v in stats.items() if k not in {'field_status_counts','app_browser_same_named_field_comparison','status_by_version','shape_cases','receipt_alias_cases'}}
print(json.dumps(small, ensure_ascii=False, indent=2))
print('Lowest observed fields')
for lane in ['app','browser']:
    for field, counts in sorted(field_states[lane].items(), key=lambda kv: kv[1]['observed'])[:12]:
        print(lane,field,dict(counts))
print('Comparisons')
for field in ['web_data.navigator_layer.user_agent','web_data.navigator_layer.hardware_concurrency','web_data.navigator_layer.device_memory','web_data.graphics_layer.webgl_renderer','web_data.graphics_layer.canvas_hash','web_data.audio_layer.audio_hash','web_data.screen_layer.device_pixel_ratio','web_data.execution_layer.timezone_id']:
    print(field,dict(comparison[field]))
