#!/usr/bin/env python3
"""Design consistency only. Never imports or executes a candidate/model/experiment.
Reads design JSON/CSV, field catalog, saved model structures and candidate ledger.
Optional --initial-status checks Git status preservation; no hashes/network/fit.
"""
import argparse
import csv
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIRST = ROOT / 'deliverables/normal_app_behavior_review'
CATALOG = ROOT / 'android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv'
LEDGER = ROOT / 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol/CANDIDATE_LEDGER.jsonl'
RELATIONS = ROOT / 'hybridguard_agent/research/rule_learning_v2/relations.py'
SUPPORT = {'EXISTING_INPUTS_SUFFICIENT_FOR_PROPOSED_SCOPE', 'CONDITIONAL_SCOPE_ONLY',
           'NEEDS_COLLECTION_METADATA', 'BLOCKED_SEMANTIC_MAPPING', 'DUPLICATES_EXISTING_SEMANTICS'}
REQUIRED = {'candidate_id', 'version', 'family', 'old_rule_ids', 'old_identity_references',
            'purpose', 'source_ids', 'inputs', 'proposed_metadata', 'applicability',
            'deployment_applicability', 'trust_assumptions', 'gate_trust_review',
            'normalization', 'formula', 'state_semantics', 'fixed_parameters',
            'trainable_parameters', 'normal_counterexamples_and_boundaries',
            'possible_interventions_detected', 'not_detected', 'information_relation',
            'existing_data_support', 'implementation_changes', 'blockers',
            'specification_examples', 'input_contract'}

def read(path):
    return json.loads(path.read_text())

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initial-status', type=Path)
    args = parser.parse_args()
    checks = []
    def check(name, condition, detail=None):
        item = {'check': name, 'status': 'PASS' if condition else 'FAIL'}
        if detail is not None:
            item['detail'] = detail
        checks.append(item)
    spec = read(HERE / 'CANDIDATE_SPEC.json')
    extra = read(HERE / 'ADDITIONAL_SOURCES.json')
    sources = read(FIRST / 'SOURCE_REGISTER.json')['sources']
    all_sources = sources + extra['sources']
    source_ids = {s['source_id'] for s in all_sources}
    candidates = spec['candidates']
    by_family = {c['family']: c for c in candidates}
    ids = {c['candidate_id'] for c in candidates}
    old_rows = list(csv.DictReader((FIRST / 'RULE_IMPACT.csv').open()))
    rows = list(csv.DictReader((HERE / 'RULE_MIGRATION.csv').open()))
    original = {r['rule_id']: r for r in old_rows}
    catalog = {'app.'+r['field']: r for r in csv.DictReader(CATALOG.open())}
    ledger = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    aliases = {}
    for row in ledger:
        if row['candidate_use']['core'] and row['candidate_use']['selectable_on_App177']:
            aliases.setdefault(row['normalized_identity'], []).append(row['rule_id'])
    check('required_artifacts', all((HERE/f).exists() for f in ('DESIGN.md', 'CANDIDATE_SPEC.json', 'RULE_MIGRATION.csv', 'IMPLEMENTATION_PLAN.md', 'ADDITIONAL_SOURCES.json', 'validate_design.py')))
    check('six_unique_bounded_templates', len(candidates)==len(ids)==spec['candidate_count']==6)
    check('six_families_only', set(by_family)=={'UA','LANGUAGE','TIMEZONE','MEMORY','MIME','WEBDRIVER'})
    check('all_candidate_required_sections', all(REQUIRED <= set(c) for c in candidates))
    check('versions_present', all(c['version']=='1.0.0' for c in candidates))
    check('source_ids_unique_no_register_copy', len(source_ids)==len(all_sources) and not ({s['source_id'] for s in sources} & {s['source_id'] for s in extra['sources']}))
    check('source_count', extra['source_count']==len(extra['sources']))
    unresolved = sorted(({sid for c in candidates for sid in c['source_ids']} | {sid for r in rows for sid in json.loads(r['source_ids'])}) - source_ids)
    check('all_evidence_ids_resolve', not unresolved, unresolved)
    check('first_review_evidence_linked_per_candidate', all(any(s in {x['source_id'] for x in sources} for s in c['source_ids']) for c in candidates))
    check('both_deployments_explicit', all({'CONTROLLED_HOST','GENERAL_APP_WEBVIEW'} <= set(c['deployment_applicability']) for c in candidates))
    inputs = [i for c in candidates for i in c['inputs']]
    check('current_input_fields_exist_in_catalog', all(i['field'] in catalog for i in inputs), {'unique_field_count':len({i['field'] for i in inputs})})
    check('exact_value_status_quality_paths', all(i['value_path']=='$.features['+json.dumps(i['field'])+']' and i['status_path']=='$.field_status['+json.dumps(i['field'])+']' and i['quality_path']=='$.field_quality['+json.dumps(i['field'])+']' for i in inputs))
    check('input_source_unit_scope_type_defined', all(all(i.get(k) for k in ('source','unit','scope','type','raw_path')) for i in inputs))
    proposed = [m for c in candidates for m in c['proposed_metadata']]
    check('proposed_fields_not_claimed_existing', all(m.get('path') and m.get('type') and m.get('status')=='PROPOSED_NOT_COLLECTED' and m.get('exists_in_current_catalog') is False and m['path'] not in catalog for m in proposed))
    check('one_support_enum_per_candidate', all(c['existing_data_support']['classification'] in SUPPORT and c['existing_data_support'].get('reason') for c in candidates))
    check('states_defined', all(set(c['state_semantics'])=={'T','F','U','FAILED'} for c in candidates))
    check('no_fitted_semantic_parameters', all(c['trainable_parameters']['parameters']==[] for c in candidates))
    examples = [e for c in candidates for e in c['specification_examples']]
    check('examples_are_manual_nonperformance_only', all(e.get('kind')=='SPECIFICATION_EXAMPLES' and e.get('real_sample') is False and e.get('executed') is False for e in examples))
    check('examples_have_all_state_classes', all({'T','F','U','FAILED'} <= {e['expected_state'] for e in c['specification_examples']} for c in candidates))
    check('example_ids_unique', len(examples)==len({e['example_id'] for e in examples}))
    check('migration_exact_17_rows', len(rows)==len(original)==17 and {r['old_rule_id'] for r in rows}==set(original))
    check('migration_original_identity_role_condition_preserved', all((r['old_identity_verbatim'],r['old_role'],r['old_judgment'])==(original[r['old_rule_id']]['atom_id'],original[r['old_rule_id']]['rule_role'],original[r['old_rule_id']]['actual_condition']) for r in rows))
    check('migration_no_historical_edits_or_static_alarm_approval', all(r['historical_change']=='NONE' and r['alarm_eligibility']=='NOT_DECIDED_BY_STATIC_DESIGN' for r in rows))
    crows = [r for r in rows if r['old_rule_id'].startswith('C')]
    check('ten_canonical_core_alias_sets_exact', len(aliases)==len(crows)==10 and {r['canonical_atom_id'] for r in crows}==set(aliases) and all(json.loads(r['registered_alias_rule_ids'])==sorted(aliases[r['canonical_atom_id']]) for r in crows))
    check('unique_final_C0_selection', [r['old_rule_id'] for r in rows if r['old_role']=='FINAL_C0']==['C01'])
    selected = {}
    for baseline in spec['baseline_models']:
        model = read(ROOT / baseline['path'])
        literals = [l['atom_id']+':'+l['polarity'] for cl in model['engine_structure']['clauses'] for l in cl['literals']]
        selected[(baseline['representation'], baseline['method'])]=literals
        check('saved_model_identity_and_literals_'+baseline['representation']+'_'+baseline['method'], model['model_id']==baseline['model_id'] and literals==baseline['selected_literal_ids'])
    web_literals = {r['old_identity_verbatim'] for r in rows if r['old_role']=='FINAL_WEB'}
    check('six_final_web_literal_mappings', set(selected[('W0','GREEDY_OR')])==web_literals==set(selected[('W0','R_KEEP_V1')]))
    check('final_C0_literal_mapping', selected[('C0','GREEDY_OR')]==['DEVIATION:OFFDER-UA-001:POSITIVE'])
    relation_text = RELATIONS.read_text()  # read only; never import or evaluate it
    check('timezone_reuses_existing_identity', by_family['TIMEZONE']['reuse_atom_id']=='V2REL:FIXED_NATIVE_VS_WEB_OFFSET_DIFFERS' and by_family['TIMEZONE']['reuse_atom_id'] in relation_text and by_family['TIMEZONE']['existing_data_support']['classification']=='DUPLICATES_EXISTING_SEMANTICS')
    prior_ids = {r['old_identity_verbatim'] for r in rows}|{r['canonical_atom_id'] for r in rows}|{'UNFITTED_CONTROL:V2REL.MEMORY_WEB_NATIVE_RATIO'}
    for match in re.findall(r"(?:V2REL|V2SINGLE):[A-Z_]+", relation_text):
        prior_ids.add(match)
    unresolved_old = sorted({x for c in candidates for x in c['old_identity_references']} - prior_ids)
    check('candidate_predecessor_ids_resolve', not unresolved_old, unresolved_old)
    check('at_most_two_priority_families_no_new_crosslayer_claim', len(spec['priority_families'])<=2 and all(p['candidate_id'] in ids for p in spec['priority_families']) and spec['common_contract']['no_new_independent_crosslayer_ready_claim'] is True)
    check('all_runtime_actions_marked_not_performed', all(v is False for v in spec['run_scope'].values()) and all(c['runtime_validation']=='NOT_PERFORMED' and c['model_evaluation']=='NOT_PERFORMED' for c in candidates))
    check('additional_sources_have_version_locator_claim', all(all(s.get(k) for k in ('source_id','version','locator','url','minimum_claim','does_not_establish','access_status')) for s in extra['sources']))
    local_errors = []
    for s in extra['sources']:
        if s.get('local_path'):
            p=ROOT/s['local_path']
            if not p.is_file():
                local_errors.append(s['source_id']+':missing_path'); continue
            n=len(p.read_text().splitlines())
            for lo,hi in s['locator']['line_ranges']:
                if not 1<=lo<=hi<=n:
                    local_errors.append(s['source_id']+':invalid_lines')
    check('additional_local_source_locations_exist', not local_errors, local_errors)
    head=git('rev-parse','HEAD').decode().strip()
    ancestor=subprocess.run(['git','merge-base','--is-ancestor',spec['first_review_commit'],'HEAD'],cwd=ROOT,check=False).returncode==0
    check('recorded_head_matches_validation', head==spec['actual_head'])
    check('HEAD_contains_first_review', ancestor)
    staged=git('diff','--cached','--name-only','-z')
    check('no_staged_changes', not staged)
    preservation={'status':'NOT_CHECKED_NO_INITIAL_STATUS_ARGUMENT','limitation':'Git status comparison is not a content checksum or a runtime proof.'}
    if args.initial_status:
        before={x for x in args.initial_status.read_bytes().split(b'\0') if x}
        current={x for x in git('status','--porcelain=v1','-z').split(b'\0') if x}
        prefix=b'?? deliverables/rule_semantics_revision/'
        external={x for x in current if not x.startswith(prefix)}
        ok=external==before
        preservation={'status':'PASS' if ok else 'FAIL','initial_entries':len(before),'current_outside_design_entries':len(external),'new_design_entries':len(current-external),'scope':'status entries only; no heavyweight integrity audit'}
        check('preexisting_git_status_entries_preserved',ok,preservation)
    result={'schema_version':'rule-semantics-design-validation-v1','status':'PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL','validation_kind':'DESIGN_CONSISTENCY_ONLY','generated_at':datetime.now(timezone.utc).isoformat(),'actual_head':head,'checks_passed':sum(c['status']=='PASS' for c in checks),'checks_total':len(checks),'counts':{'candidate_templates':len(candidates),'migration_rows':len(rows),'manual_specification_examples':len(examples),'additional_source_records':len(extra['sources'])},'not_validated':['APP_RUNTIME','HISTORICAL_APK_SOURCE_EQUIVALENCE','CANDIDATE_EXECUTION_EVEN_ON_EXAMPLES','REAL_RECORD_RELATION_VALUES','MODEL_PREDICTIONS','PERFORMANCE_OR_FPR','EXTERNAL_SOURCE_FETCH_REPLAY','INDEPENDENT_CONFIRMATION'],'limits':'References, completeness, metadata and stored identities only; examples are annotations and are not executed. A passing design does not establish method effectiveness.','workspace_status_preservation':preservation,'checks':checks}
    (HERE/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','checks_passed','checks_total','counts')},ensure_ascii=False))
    for c in checks:
        if c['status']=='FAIL':print(json.dumps(c,ensure_ascii=False))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
