#!/usr/bin/env python3
"""Read-only design consistency validation; no candidate/model execution.

Print the full result as JSON. --output exclusively creates a new report; it never
replaces a prior report. Git dirtiness is diagnostic, not a design-content check.
"""
import argparse
import csv
import io
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APPROVED_DESIGN_COMMIT = '8eeeb2238bd829a7078efe009c46e3e7f052c576'
DESIGN_PATH = Path('deliverables/rule_semantics_revision')
FROZEN_DESIGN_FILES = ('DESIGN.md', 'CANDIDATE_SPEC.json', 'RULE_MIGRATION.csv',
                       'IMPLEMENTATION_PLAN.md', 'ADDITIONAL_SOURCES.json', 'VALIDATION.json')
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
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    return list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8'))))


def _git(root, *args):
    return subprocess.run(['git', *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False,
                          env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})


def _error(exc):
    return {'type': type(exc).__name__, 'message': str(exc)}


def _git_identity(root, approved_ref, check):
    """Read only six frozen files and commit ancestry; never inspect real records."""
    identity = {'design_starting_baseline': None, 'approved_design_commit': approved_ref,
                'validation_head': None, 'history_status': 'UNVERIFIABLE'}
    workspace = {'status': 'UNAVAILABLE', 'affects_design_result': False}
    try:
        head = _git(root, 'rev-parse', '--verify', 'HEAD^{commit}')
        approved = _git(root, 'rev-parse', '--verify', approved_ref + '^{commit}')
        if head.returncode or approved.returncode:
            check('git_history_available', False, {'status': 'UNVERIFIABLE',
                  'HEAD_available': head.returncode == 0,
                  'approved_design_commit_available': approved.returncode == 0})
            if not head.returncode:
                identity['validation_head'] = head.stdout.decode().strip()
            return identity, workspace
        identity['validation_head'] = head.stdout.decode().strip()
        identity['approved_design_commit'] = approved.stdout.decode().strip()
        approved_spec = None
        file_results = []
        for name in FROZEN_DESIGN_FILES:
            relpath = DESIGN_PATH / name
            frozen = _git(root, 'show', approved_ref + ':' + relpath.as_posix())
            path = root / relpath
            state = 'MATCH'
            if frozen.returncode:
                state = 'APPROVED_CONTENT_UNAVAILABLE'
            elif not path.is_file():
                state = 'WORKING_FILE_MISSING'
            elif path.read_bytes() != frozen.stdout:
                state = 'VERSION_DIFFERENCE'
            file_results.append({'path': relpath.as_posix(), 'status': state})
            if name == 'CANDIDATE_SPEC.json' and frozen.returncode == 0:
                approved_spec = json.loads(frozen.stdout)
        check('approved_design_file_identity', all(x['status'] == 'MATCH' for x in file_results),
              {'comparison': 'exact bytes against approved commit; validator intentionally excluded',
               'files': file_results})
        if not isinstance(approved_spec, dict):
            check('git_history_available', False, {'status': 'UNVERIFIABLE',
                  'reason': 'Approved design spec is unavailable or invalid.'})
            return identity, workspace
        baseline = approved_spec.get('actual_head')
        identity['design_starting_baseline'] = baseline
        baseline_exists = (_git(root, 'rev-parse', '--verify', baseline + '^{commit}')
                           if isinstance(baseline, str) else None)
        if baseline_exists is None or baseline_exists.returncode:
            check('git_history_available', False, {'status': 'UNVERIFIABLE',
                  'reason': 'Design starting baseline history is unavailable.'})
            return identity, workspace
        check('git_history_available', True)
        identity['history_status'] = 'AVAILABLE'
        for name, ancestor, descendant in (
            ('design_baseline_is_ancestor_of_approved_design', baseline, approved_ref),
            ('approved_design_is_ancestor_of_validation_HEAD', approved_ref, 'HEAD'),
            ('HEAD_contains_first_review', approved_spec.get('first_review_commit'), 'HEAD'),
        ):
            if not isinstance(ancestor, str):
                check(name, False, {'status': 'UNVERIFIABLE', 'reason': 'Missing commit identity.'})
                continue
            relation = _git(root, 'merge-base', '--is-ancestor', ancestor, descendant)
            check(name, relation.returncode == 0, {'ancestor': ancestor, 'descendant': descendant,
                  'status': 'ANCESTOR' if relation.returncode == 0 else
                            'NOT_ANCESTOR' if relation.returncode == 1 else 'UNVERIFIABLE'})
        status = _git(root, 'status', '--porcelain=v1', '-z')
        staged = _git(root, 'diff', '--cached', '--name-only', '-z')
        workspace = {'status': 'AVAILABLE' if status.returncode == staged.returncode == 0 else 'UNAVAILABLE',
                     'affects_design_result': False,
                     'status_record_count': len([x for x in status.stdout.split(b'\0') if x]),
                     'staged_path_count': len([x for x in staged.stdout.split(b'\0') if x]),
                     'note': 'Unrelated staged/unstaged files do not invalidate the approved design; no Git writes are performed.'}
    except (OSError, ValueError, TypeError) as exc:
        check('git_identity_validation_completed', False, {'status': 'UNVERIFIABLE', 'error': _error(exc)})
    return identity, workspace


def _check_design(root, check):
    here = root / DESIGN_PATH
    first = root / 'deliverables/normal_app_behavior_review'
    catalog_path = root / 'android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv'
    ledger_path = root / 'hybridguard_agent/artifacts/discriminative_rule_learning_v1_20260924/R01_protocol/CANDIDATE_LEDGER.jsonl'
    relations_path = root / 'hybridguard_agent/research/rule_learning_v2/relations.py'
    spec = read(here / 'CANDIDATE_SPEC.json')
    extra = read(here / 'ADDITIONAL_SOURCES.json')
    sources = read(first / 'SOURCE_REGISTER.json')['sources']
    all_sources = sources + extra['sources']
    source_ids = {s['source_id'] for s in all_sources}
    candidates = spec['candidates']
    by_family = {c['family']: c for c in candidates}
    ids = {c['candidate_id'] for c in candidates}
    old_rows = read_csv(first / 'RULE_IMPACT.csv')
    rows = read_csv(here / 'RULE_MIGRATION.csv')
    original = {r['rule_id']: r for r in old_rows}
    catalog = {'app.'+r['field']: r for r in read_csv(catalog_path)}
    ledger = [json.loads(l) for l in ledger_path.read_text().splitlines() if l.strip()]
    aliases = {}
    for row in ledger:
        if row['candidate_use']['core'] and row['candidate_use']['selectable_on_App177']:
            aliases.setdefault(row['normalized_identity'], []).append(row['rule_id'])
    check('required_artifacts', all((here/f).exists() for f in ('DESIGN.md', 'CANDIDATE_SPEC.json', 'RULE_MIGRATION.csv', 'IMPLEMENTATION_PLAN.md', 'ADDITIONAL_SOURCES.json', 'validate_design.py')))
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
        model = read(root / baseline['path'])
        literals = [l['atom_id']+':'+l['polarity'] for cl in model['engine_structure']['clauses'] for l in cl['literals']]
        selected[(baseline['representation'], baseline['method'])]=literals
        check('saved_model_identity_and_literals_'+baseline['representation']+'_'+baseline['method'], model['model_id']==baseline['model_id'] and literals==baseline['selected_literal_ids'])
    web_literals = {r['old_identity_verbatim'] for r in rows if r['old_role']=='FINAL_WEB'}
    check('six_final_web_literal_mappings', set(selected[('W0','GREEDY_OR')])==web_literals==set(selected[('W0','R_KEEP_V1')]))
    check('final_C0_literal_mapping', selected[('C0','GREEDY_OR')]==['DEVIATION:OFFDER-UA-001:POSITIVE'])
    relation_text = relations_path.read_text()  # read only; never import or evaluate it
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
            p=root/s['local_path']
            if not p.is_file():
                local_errors.append(s['source_id']+':missing_path'); continue
            n=len(p.read_text().splitlines())
            for lo,hi in s['locator']['line_ranges']:
                if not 1<=lo<=hi<=n:
                    local_errors.append(s['source_id']+':invalid_lines')
    check('additional_local_source_locations_exist', not local_errors, local_errors)
    return {'candidate_templates': len(candidates), 'migration_rows': len(rows),
            'manual_specification_examples': len(examples), 'additional_source_records': len(extra['sources'])}


def validate(repo_root=ROOT, approved_design_commit=APPROVED_DESIGN_COMMIT, initial_status=None):
    """Return a report without writes. Internal dependency injection is for Git fixtures.

    The command line intentionally has no repository/approved-ref override.
    """
    root = Path(repo_root).resolve()
    checks = []

    def check(name, condition, detail=None):
        item = {'check': name, 'status': 'PASS' if condition else 'FAIL'}
        if detail is not None:
            item['detail'] = detail
        checks.append(item)

    identity, workspace = _git_identity(root, approved_design_commit, check)
    counts = None
    try:
        counts = _check_design(root, check)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        check('design_inputs_readable_and_well_formed', False, _error(exc))
    preservation = {'status': 'NOT_CHECKED_NO_INITIAL_STATUS_ARGUMENT',
                    'affects_design_result': False,
                    'limitation': 'Git status comparison is diagnostic, not a content checksum or runtime proof.'}
    if initial_status is not None:
        try:
            before = Path(initial_status).read_bytes()
            current = _git(root, 'status', '--porcelain=v1', '-z')
            preservation.update(status='UNCHANGED' if current.returncode == 0 and before == current.stdout
                                else 'CHANGED' if current.returncode == 0 else 'UNVERIFIABLE')
        except OSError as exc:
            preservation.update(status='UNVERIFIABLE', error=_error(exc))
    return {'schema_version': 'rule-semantics-design-validation-v2',
            'status': 'PASS' if all(x['status'] == 'PASS' for x in checks) else 'FAIL',
            'validation_kind': 'DESIGN_CONSISTENCY_ONLY',
            'generated_at': datetime.now(timezone.utc).isoformat(), **identity,
            'checks_passed': sum(c['status'] == 'PASS' for c in checks),
            'checks_total': len(checks), 'counts': counts,
            'not_validated': ['APP_RUNTIME', 'HISTORICAL_APK_SOURCE_EQUIVALENCE',
                              'CANDIDATE_EXECUTION_EVEN_ON_EXAMPLES', 'REAL_RECORD_RELATION_VALUES',
                              'MODEL_PREDICTIONS', 'PERFORMANCE_OR_FPR', 'EXTERNAL_SOURCE_FETCH_REPLAY',
                              'INDEPENDENT_CONFIRMATION'],
            'limits': 'References, completeness, metadata and stored identities only; examples are annotations and are not executed. A passing design does not establish method effectiveness.',
            'git_workspace': workspace, 'workspace_status_preservation': preservation,
            'checks': checks}


def main(argv=None, *, repo_root=ROOT, approved_design_commit=APPROVED_DESIGN_COMMIT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initial-status', type=Path, help='Optional diagnostic status snapshot; never a design gate.')
    parser.add_argument('--output', type=Path, help='Exclusively create a new JSON report; existing paths are refused.')
    args = parser.parse_args(argv)
    result = validate(repo_root, approved_design_commit, args.initial_status)
    if args.output is not None:
        result['report_output'] = {'path': str(args.output.resolve()), 'status': 'CREATED'}
        try:
            # Mode x is atomic for existing-path refusal, including symlinks.
            with args.output.open('x', encoding='utf-8') as out:
                out.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        except OSError as exc:
            result['report_output'].update(status='REFUSED_OR_FAILED', error=_error(exc))
            result['status'] = 'FAIL'
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
