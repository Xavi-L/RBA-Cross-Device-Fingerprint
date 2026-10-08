#!/usr/bin/env python3
"""Saved-result figures and tables. No model loading, experimental execution or timing.

--check-only reads saved delivery files and link targets; it does not plot.
"""
import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OWNER='rba-round3-overview-saved-evidence-v1'
IDS=['F00','F09']
STATUS='初稿已生成／供导师选用'

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def check(checks,name,observed,expected):
    checks.append(dict(id=name,status='PASS' if observed==expected else 'FAIL',observed=observed,expected=expected))

def extract_f00(root):
    source=read_json(HERE/'F00_source.json');checks=list(source['checks'])
    catalog=read_csv(root/'android_app/HybridGuard/featureapp/src/main/assets/expanded_v2_field_catalog.csv')
    check(checks,'F00_catalog_live',[sum(r['layer']==layer for r in catalog) for layer in ('android_native_data','webview_data','web_data')],[84,26,67])
    check(checks,'F00_Browser_catalog_live',read_json(root/'browser_probe_site/public/probe/manifest.json')['signal_count'],67)
    app=[r for r in read_json(root/'deliverables/timezone_relation_validation_v1/models.json')['models'] if r['stage']=='RETENTION']
    paired=read_json(root/'deliverables/cross_endpoint_constrained_extension_v1/results/models.json')
    resource=read_json(root/'deliverables/app_resource_constrained_extension_v1/results/models.json')
    check(checks,'F00_App_model_identity',[r['model_id'] for r in app],source['source_model_identities']['app_retention'])
    check(checks,'F00_paired_C1',[r['extensions'] for r in paired],[['C1']]*3)
    check(checks,'F00_paired_frozen_App',[r['base_model_id'] for r in paired],[r['model_id'] for r in app])
    check(checks,'F00_resource_retains_base',[(r['selected_set'],r['extensions'],r['status']) for r in resource],[('S0',[],'BASELINE_RETAINED')]*3)
    check(checks,'F00_resource_frozen_pair',[r['base_model_id'] for r in resource],[r['model_id'] for r in paired])
    nodes=source['nodes'];edges=source['edges'];ids={r['id'] for r in nodes}
    check(checks,'F00_unique_nodes',len(ids),len(nodes))
    check(checks,'F00_edge_endpoints',all(e['from'] in ids and e['to'] in ids for e in edges),True)
    check(checks,'F00_no_specialist_into_accepted',any(e['to'] in ('app_rules','paired_rules','current_interfaces_app','current_interfaces_paired') and e['from'] in ('resource_trial','specialists') for e in edges),False)
    check(checks,'F00_no_training_to_current_data',any(e['from']=='training' and e['to'] in ('current_inputs','required_quality') for e in edges),False)
    for n in nodes:
        for s in n['evidence']:
            check(checks,'F00_source_'+n['id']+'_'+s['path'],(root/s['path']).is_file(),True)
    data={'F00_nodes':nodes,'F00_edges':edges}
    meta=dict(name='Observation, staged development and current-record decisions',
        kind='method schematic; not measured performance',sources=source['sources'],
        filtering='Source-grounded method and implementation mappings; no new conditions computed.',
        roles='Accepted App and App+C1 are distinct interfaces; Host geometry and resource relations remain unintegrated diagnostics.',
        limits=['Catalog counts do not imply full availability, model use or equality.',
            'Session/receipt association is provenance, not a prediction feature; same phase is not atomic synchronization.',
            'Labels, targets and pre/post verification are offline only; no automatic paired-to-App fallback.',
            'Native/Host are additional observations, not certified hardware truth. MTC144/117 are historical evaluation.'],
        node_mapping='data/F00_nodes.csv',edge_mapping='data/F00_edges.csv',editable_source='F00_source.json')
    return data,checks,meta

def plot_f00(data,save):
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch,FancyArrowPatch,Rectangle
    fig=plt.figure(figsize=(180/25.4,228/25.4));ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,180),ylim=(0,228));ax.axis('off')
    ax.text(6,223,'F00  Observations, staged development and current decisions',fontsize=10,weight='bold',va='center')
    for x,y,w,h,label in [(4,157,172,61,'A  Observation catalogue and association'),(4,77,172,77,'B  Offline development / selection'),(4,9,172,66,'C  Current-record decisions · separate interfaces')]:
        ax.add_patch(Rectangle((x,y),w,h,facecolor='#f6f8fa',edgecolor='#c6d3dc',lw=.7,zorder=0))
        ax.text(x+3,y+h-4,label,fontsize=9,weight='bold',va='center')
    for e in data['F00_edges']:
        points=e['points'];style='--' if e['style']=='dashed' else '-'
        for a,b in zip(points[:-2],points[1:-1]):ax.plot([a[0],b[0]],[a[1],b[1]],color='#527080',lw=.8,ls=style,zorder=1)
        ax.add_patch(FancyArrowPatch(points[-2],points[-1],arrowstyle='-|>',mutation_scale=8,linewidth=.8,color='#527080',linestyle=style,zorder=1))
    for n in data['F00_nodes']:
        if not n.get('visible',True):continue
        x,y,w,h=n['box'];is_side=n['status'] in ('diagnostic_unintegrated','rejected_extension')
        face='#edf4f8' if n['status'].startswith('accepted') else '#fff'
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.2,rounding_size=1',
            facecolor=face,edgecolor='#526e7e',linewidth=.8,linestyle='--' if is_side else '-',zorder=2))
        ax.text(x+w/2,y+h/2,n['label'],ha='center',va='center',fontsize=8,linespacing=1.2,zorder=3)
    ax.text(90,159,'Counts describe catalogues; not all fields are used, available or required to agree.',ha='center',fontsize=8)
    ax.text(7,3.3,'Solid: implemented flow   Dashed: tested / unintegrated   Accepted: current selected method',fontsize=8)
    save(fig,'F00',(180,228))


"""F09: count existing v15 fixed-condition outputs; never evaluate a condition."""
import gzip
import json
from collections import Counter

F09_BASE = 'deliverables/screen_geometry_observation_v1/'
F09_SOURCES = [F09_BASE + x for x in ('SUMMARY.json', 'predictions.jsonl.gz',
    'CONDITIONS_FROZEN.json', 'SEMANTICS.md', 'RESULTS.md', 'REPORT.md')] + [
    'deliverables/screen_geometry_closeout_v1/REPORT.md',
    'deliverables/screen_geometry_closeout_v1/V15_CONSISTENCY.json']
F09_CONDITIONS = ('R_HEIGHT710', 'R_SAME_WEB', 'R_HOST_GEOMETRY')
F09_STATES = ('T', 'F', 'U', 'FAILED')
F09_SCENARIOS = {'L1': 'Normal rotation attempt', 'L2': 'Normal layout enlargement',
    'L3': 'Normal WebView zoom', 'A': 'Controlled screen modification'}


def _f09_counts(group, condition):
    c = group['conditions'][condition]
    n = group['n']
    return dict(N=n, **{s: c[s] for s in F09_STATES}, defined=c['T'] + c['F'],
        rate=c['T'] / n if n else '', defined_rate=(c['T'] + c['F']) / n if n else '')


def _f09_saved_counts(records, condition):
    c = Counter(r['conditions'][condition]['state'] for r in records)
    return dict(N=len(records), **{s: c[s] for s in F09_STATES})


def extract_f09(root):
    summary = json.loads((root / (F09_BASE + 'SUMMARY.json')).read_text())
    frozen = json.loads((root / (F09_BASE + 'CONDITIONS_FROZEN.json')).read_text())
    consistency = json.loads((root / F09_SOURCES[-1]).read_text())
    with gzip.open(root / (F09_BASE + 'predictions.jsonl.gz'), 'rt', encoding='utf-8') as fh:
        records = [json.loads(line) for line in fh]
    checks = []
    def check(name, observed, expected):
        checks.append(dict(id='F09.' + name, status='PASS' if observed == expected else 'FAIL',
                           observed=observed, expected=expected))
    check('formal_version_and_role', sorted(set((r['source_binding']['collector_version_code'],
          r['material_role']) for r in records)), [(15, 'FROZEN_FORMAL_MATRIX')])
    check('formal_record_scope', [frozen['formal_planned_records'], summary['planned_records'],
          summary['actual_attempted'], summary['actual_executed'], summary['received_raw_records'], len(records)], [72] * 6)
    check('source_frozen', [frozen['status'], frozen['model_fit_calls'], summary['model_fit_calls']], ['FROZEN', 0, 0])
    check('condition_identity', sorted(set(tuple(r['conditions']) for r in records)), [F09_CONDITIONS])
    check('binding_and_geometry', [sum(r['source_binding']['binding_valid'] is True for r in records),
          sum(r['geometry_evidence']['usable_window'] is True for r in records)], [72, 72])
    check('snapshots_separate', sum(r['same_snapshot_as_legacy_screen_layer'] is False for r in records), 72)
    check('saved_replay_scope_only', [consistency['expected_records'], consistency['compared_records'],
          consistency['passed'], len(consistency['summary_differences']),
          sum(p['unchanged'] and not p['differences'] for p in consistency['per_id'])], [72, 72, True, 0, 72])
    trios = {(g['environment'], g['process_type'], g['round']): (i, g)
             for i, g in enumerate(summary['trios'])}
    check('independent_group_identity', len(trios), 24)
    normal = [r for r in records if r['normal_basis']['supported'] is True]
    modified = [r for r in records if r['process_type'] == 'A' and r['phase'] == 'change'
                and r['normal_basis']['supported'] is False and r['observable_intervention'] is True
                and r['workflow_evidence']['verified'] is True]
    layout = [r for r in records if r['process_type'] == 'L2' and r['phase'] == 'change'
              and r['normal_basis']['supported'] is True
              and trios[(r['environment'], r['process_type'], r['round'])][1]['effect'] == 'OBSERVABLE_CHANGE']
    check('normal_modified_partition', [len(normal), len(modified), len(normal) + len(modified)], [66, 6, 72])
    check('layout_is_normal_subset', [len(layout), all(r in normal for r in layout)], [6, True])
    # Saved evidence establishes normal identity and actual effects; output states never label a record.
    normal_checks = []
    effect_checks = []
    for r in records:
        _, g = trios[(r['environment'], r['process_type'], r['round'])]
        phase_index = ('clean_pre', 'change', 'clean_post').index(r['phase'])
        normal_checks.append(r['normal_basis']['supported'] == g['normal_supported'][phase_index])
        if r in modified:
            effect_checks.append(g['observable_intervention'] is True and g['effect'] == 'OBSERVABLE_CHANGE'
                                 and g['execution'] == 'EXECUTED' and g['recovery'] == 'RESTORED')
    check('normal_evidence_matches_saved_trios', all(normal_checks), True)
    check('actual_modification_evidence', effect_checks, [True] * 6)
    data = dict(F09=[], F09_scenarios=[], F09_normal_changes=[], F09_environments=[],
                F09_records=[], F09_effects=[], F09_conditions=[])
    comparisons = []
    def add_group(target, cohort, group, subset, source_pointer, **extra):
        for condition in F09_CONDITIONS:
            count = _f09_counts(group, condition)
            simple = {k: count[k] for k in ('N',) + F09_STATES}
            observed = _f09_saved_counts(subset, condition)
            comparisons.append((cohort + '/' + condition, simple == observed))
            c = group['conditions'][condition]
            comparisons.append((cohort + '/' + condition + '/partition',
                count['N'] == sum(count[s] for s in F09_STATES)))
            comparisons.append((cohort + '/' + condition + '/proportions',
                c['alarm_proportion'] == dict(numerator=count['T'], denominator=count['N']) and
                c['explicit_coverage'] == dict(numerator=count['defined'], denominator=count['N'])))
            data[target].append(dict(cohort=cohort, condition=condition, **extra, **count,
                source=F09_BASE + 'SUMMARY.json', source_locator=source_pointer + '/conditions/' + condition,
                verification_source=F09_BASE + 'predictions.jsonl.gz'))
    add_group('F09', 'normal_layout_middle', summary['normal_change_by_process']['L2'], layout,
              '/normal_change_by_process/L2', hierarchy='subset of all_normal; never add to it')
    add_group('F09', 'effective_screen_modification', summary['observable_intervention'], modified,
              '/observable_intervention', hierarchy='disjoint from all_normal')
    add_group('F09', 'all_normal', summary['confirmed_normal'], normal, '/confirmed_normal',
              hierarchy='includes normal_layout_middle')
    for key, group in summary['by_process_phase'].items():
        scenario, phase = key.split('/')
        rows = [r for r in records if r['process_type'] == scenario and r['phase'] == phase]
        add_group('F09_scenarios', key, group, rows, '/by_process_phase/' + key,
                  scenario=scenario, scenario_label=F09_SCENARIOS[scenario], phase=phase,
                  independent_normal_count=sum(r['normal_basis']['supported'] is True for r in rows),
                  effective_modification_count=sum(r in modified for r in rows),
                  hierarchy='12 disjoint scene-phase groups partition 72')
    for env, group in summary['by_environment'].items():
        add_group('F09_environments', env, group, [r for r in records if r['environment'] == env],
                  '/by_environment/' + env, hierarchy='3 disjoint environments partition 72')
    for category in ('normal_change_by_process', 'normal_observable_change_by_process'):
        for process, group in summary[category].items():
            subset = [r for r in normal if r['process_type'] == process and r['phase'] == 'change'
                      and (category == 'normal_change_by_process' or
                           trios[(r['environment'], process, r['round'])][1]['effect'] == 'OBSERVABLE_CHANGE')]
            add_group('F09_normal_changes', category + '/' + process, group, subset,
                      '/' + category + '/' + process, scenario=process, scenario_label=F09_SCENARIOS[process],
                      phase='change', hierarchy='actual-effect group is a subset of attempted normal group')
    no_effect = [r for r in normal if r['phase'] == 'change' and
                 trios[(r['environment'], r['process_type'], r['round'])][1]['effect'] == 'NO_OBSERVABLE_EFFECT']
    add_group('F09_normal_changes', 'no_observable_effect', summary['no_observable_effect_positions'], no_effect,
              '/no_observable_effect_positions', scenario='L1', scenario_label='Normal rotation attempt',
              phase='change', hierarchy='subset of L1 normal-change attempts')
    for key in ('all', 'attempted_intervention', 'common_evaluable_subset', 'common_evaluable_normal',
                'common_evaluable_intervention'):
        subset = records if key in ('all', 'common_evaluable_subset') else normal if key == 'common_evaluable_normal' else modified
        for condition in F09_CONDITIONS:
            c = _f09_counts(summary[key], condition)
            comparisons.append((key + '/' + condition,
                                {k: c[k] for k in ('N',) + F09_STATES} == _f09_saved_counts(subset, condition)))
    failures = [name for name, passed in comparisons if not passed]
    check('summary_vs_saved_record_counts', failures, [])
    check('checked_count_comparisons', len(comparisons), 240)
    check('all_states_known', sorted(set(r['conditions'][c]['state'] for r in records for c in F09_CONDITIONS)), ['F', 'T'])
    check('no_undefined_or_failed', sum(r['conditions'][c]['state'] in ('U', 'FAILED') for r in records for c in F09_CONDITIONS), 0)
    for line, r in enumerate(records, 1):
        trio_index, g = trios[(r['environment'], r['process_type'], r['round'])]
        data['F09_records'].append(dict(record=f'G{line:02d}', source=F09_BASE + 'predictions.jsonl.gz',
            source_line=line, environment=r['environment'], scenario=r['process_type'], phase=r['phase'],
            repetition=r['round'], collector_version=r['source_binding']['collector_version_code'],
            material_role=r['material_role'], normal_supported=r['normal_basis']['supported'],
            normal_basis_kind=r['normal_basis']['kind'], observable_intervention=r['observable_intervention'],
            workflow_verified=r['workflow_evidence']['verified'], trio_effect=g['effect'],
            trio_source=F09_BASE + 'SUMMARY.json', trio_locator=f'/trios/{trio_index}',
            **{c: r['conditions'][c]['state'] for c in F09_CONDITIONS}))
    for i, g in enumerate(summary['trios']):
        data['F09_effects'].append(dict(environment=g['environment'], scenario=g['process_type'],
            scenario_label=F09_SCENARIOS[g['process_type']], repetition=g['round'], execution=g['execution'],
            effect=g['effect'], observable_intervention=g['observable_intervention'], recovery=g['recovery'],
            requested_orientation_achieved=g['requested_orientation_achieved'],
            normal_pre=g['normal_supported'][0], normal_middle=g['normal_supported'][1],
            normal_post=g['normal_supported'][2], source=F09_BASE + 'SUMMARY.json', source_locator=f'/trios/{i}'))
    rotation = [g for g in summary['trios'] if g['process_type'] == 'L1']
    check('rotation_effect_scope', [len(rotation), sum(g['effect'] == 'OBSERVABLE_CHANGE' for g in rotation),
          sum(g['effect'] == 'NO_OBSERVABLE_EFFECT' for g in rotation)], [6, 4, 2])
    for condition, label, semantics in (
        ('R_HEIGHT710', 'Legacy height > 710', frozen['comparators'][0]),
        ('R_SAME_WEB', 'Legacy same-Web viewport relation', frozen['comparators'][1]),
        ('R_HOST_GEOMETRY', 'Host geometry upper bound', frozen['new_relations']['formula'])):
        data['F09_conditions'].append(dict(condition=condition, label=label,
            method_role='fixed-condition comparison; not a complete fitted model',
            integration_status=('not integrated into current accepted App full model' if condition == 'R_HOST_GEOMETRY'
                                else 'legacy comparator; its containing full model is not evaluated in this figure'),
            saved_definition=semantics, source=F09_BASE + 'CONDITIONS_FROZEN.json',
            semantics_source=F09_BASE + 'SEMANTICS.md'))
    metadata = {'F09': dict(sources=F09_SOURCES,
        filtering='Only the original v15 FROZEN_FORMAL_MATRIX (72). Normal identity uses saved normal_basis.supported; effective modifications require A/change, saved observable_intervention and verified workflow, cross-checked against trios. Layout middle requires L2/change plus independent normal proof and saved observable effect.',
        aggregation='Plot counts come directly from original SUMMARY.json groups, cross-checked by counting existing condition states. No condition formula is executed. ALL, scenario, environment and nested normal-change summaries are alternative views, never summed together.',
        method_roles='R_HEIGHT710, R_SAME_WEB and R_HOST_GEOMETRY are three fixed conditions, not three complete-model ablations. Host condition remains outside current accepted App full model.',
        denominators={'all_formal': len(records), 'all_normal': len(normal), 'effective_screen_modifications': len(modified), 'normal_layout_middle_subset': len(layout), 'rotation_attempts': len(rotation), 'observed_rotation_effects': sum(g['effect'] == 'OBSERVABLE_CHANGE' for g in rotation)},
        limits=['Repeated observations from three emulator environments; not device-population rates.',
            'Six fewer alarms on normal layout enlargement while retaining the same six local detections as the old height threshold; no extra detection gain over that threshold.',
            'Exclude v16 engineering 12, early smoke, original App378, MTC and resource54; V15_CONSISTENCY is a saved scope check only.',
            'Fixed numerical tolerance is not a guarantee for all WebViews; no broad real-device, nonzero-padding, foldable or split-screen normal coverage.',
            'Within-bound or coordinated modifications may remain undetected; Host is an additional observation, not authenticated ground truth.',
            'Scale is not filled with 1, inferred from width ratios, or mixed across old/new snapshots.'])}
    return data, checks, metadata


def plot_f09(data, save):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    index = {(r['cohort'], r['condition']): r for r in data['F09']}
    normal_n = index[('all_normal', F09_CONDITIONS[0])]['N']
    modification_n = index[('effective_screen_modification', F09_CONDITIONS[0])]['N']
    layout_n = index[('normal_layout_middle', F09_CONDITIONS[0])]['N']
    all_n = len(data['F09_records'])
    rotation = [r for r in data['F09_effects'] if r['scenario'] == 'L1']
    rotations_effective = sum(r['effect'] == 'OBSERVABLE_CHANGE' for r in rotation)
    environment_n = len(set(r['environment'] for r in data['F09_records']))
    dims = (180, 119)
    fig = plt.figure(figsize=(dims[0] / 25.4, dims[1] / 25.4), facecolor='white')
    fig.text(.035, .966, 'F09  Host geometry preserves local detection with fewer normal alarms',
             fontsize=10, weight='bold', va='top')
    fig.text(.035, .921, 'Fixed-condition specialist study | Not integrated into the current App full model', fontsize=8.5)
    fig.text(.035, .865, 'A  Local comparison', fontsize=9, weight='bold')
    ax = fig.add_axes([.31, .555, .66, .222])
    cohorts = ('normal_layout_middle', 'effective_screen_modification')
    arr = [[index[(cohort, c)]['rate'] for c in F09_CONDITIONS] for cohort in cohorts]
    mesh = ax.pcolormesh(arr, cmap=LinearSegmentedColormap.from_list('f09_alarm', ['#f5f8fa', '#77a8c9']),
                         vmin=0, vmax=1, edgecolors='white', linewidth=2)
    mesh.set_rasterized(False)
    ax.set_xlim(0, 3); ax.set_ylim(2, 0)
    ax.set_xticks([.5, 1.5, 2.5], ['Height > 710\n(legacy)', 'Same-Web relation\n(legacy)', 'Host upper bound\n(specialist)'])
    ax.tick_params(axis='x', top=True, labeltop=True, bottom=False, labelbottom=False, length=0, pad=6, labelsize=8.5)
    ax.set_yticks([.5, 1.5], ['Normal layout enlargement\n(fewer alarms is better)', 'Effective screen modification\n(more detections is better)'])
    ax.tick_params(axis='y', length=0, pad=8, labelsize=8.5)
    for spine in ax.spines.values(): spine.set_visible(False)
    for y, cohort in enumerate(cohorts):
        for x, condition in enumerate(F09_CONDITIONS):
            r = index[(cohort, condition)]
            ax.text(x + .5, y + .5, f"{r['T']}/{r['N']} ({100 * r['rate']:.0f}%)", ha='center', va='center', fontsize=10)
    fig.text(.31, .518, 'Cells: T / N (alarm proportion). Blue denotes more alarms.', fontsize=8)
    fig.text(.035, .454, 'B  Complete cohort states', fontsize=9, weight='bold')
    fig.text(.57, .42, f'All normal (N={normal_n})', fontsize=8.5, ha='center', weight='bold')
    fig.text(.86, .42, f'All modifications (N={modification_n})', fontsize=8.5, ha='center', weight='bold')
    fig.text(.57, .385, 'T / F / U / FAILED', fontsize=8, ha='center')
    fig.text(.86, .385, 'T / F / U / FAILED', fontsize=8, ha='center')
    for i, (condition, label) in enumerate(zip(F09_CONDITIONS, ['Legacy height > 710', 'Legacy same-Web relation', 'Host geometry upper bound'])):
        yy = .342 - i * .047
        fig.text(.055, yy, label, fontsize=8.5)
        for xx, cohort in ((.57, 'all_normal'), (.86, 'effective_screen_modification')):
            r = index[(cohort, condition)]
            fig.text(xx, yy, ' / '.join(str(r[s]) for s in F09_STATES), ha='center', fontsize=9)
    fig.text(.035, .184, f'Normal layout enlargement ({layout_n}) is a subset of all normal records ({normal_n}); do not add them.', fontsize=8)
    fig.text(.035, .145, f'All {all_n} positions have explicit outputs for all three conditions: U = 0 and FAILED = 0.', fontsize=8)
    fig.text(.035, .106, 'T: alarm; F: no alarm; U: cannot judge; FAILED: execution / binding failure.', fontsize=8)
    fig.text(.035, .067, f'v15 formal matrix: {all_n} positions in {environment_n} emulator environments. Rotation effect observed in {rotations_effective}/{len(rotation)} attempts.', fontsize=8)
    fig.text(.035, .028, 'Host measures the current WebView content region, not the whole physical screen.', fontsize=8)
    save(fig, 'F09', dims)


"""Saved-only T05 extraction. This module never imports an experiment runtime."""
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

COST_BASE = 'deliverables/prepaper_evidence_closeout_v1/'
COST_TREES = 'deliverables/cross_endpoint_four_view_comparison_v1/results/'
COST_MAIN_LABELS = tuple(f'R_FULL / {i:02d}' for i in (1, 2, 3)) + tuple(
    'P0 / ' + v for v in ('V_APP', 'V_BROWSER', 'V_BOTH', 'V_BOTH_REL'))
COST_STAGES = ('load_parse_validate', 'model_input_prepare', 'prepared_inference',
               'original_current_interface', 'cached_from_adapted',
               'loaded_raw_to_original', 'loaded_raw_to_cached')
COST_SOURCES = [COST_BASE + p for p in (
    'tables/cost.csv', 'tables/model_resources.csv', 'timing/TIMING_FREEZE.json',
    'timing/batches.jsonl', 'existing_times/collection_log_intervals.csv',
    'existing_times/historical_training_timing.json', 'REPORT.md', 'cost_runtime.py',
    'measure_cost.py', 'build_tables.py', 'extract_existing_times.py')]
COST_SOURCES += [COST_BASE + f'results/{s}_{i:02d}.json' for i in (1, 2, 3)
                for s in ('R_FULL', 'R_NO_CROSS', 'R_NO_MATCHED_NORMAL_CAP')]
COST_SOURCES += [COST_TREES + f'{p}_{v}.json' for p in ('P0', 'P1', 'P2')
                for v in ('V_APP', 'V_BROWSER', 'V_BOTH', 'V_BOTH_REL')]
COST_SOURCES += [f'deliverables/timezone_relation_validation_v1/trials/B_REL_TZ__WEBGL1-LOEO-v1-{i:02d}__RETENTION/model.json'
                for i in (1, 2, 3)]


def _cost_read_csv(path):
    with path.open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def _cost_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _cost_check(checks, name, failures, count):
    checks.append({'name': name, 'status': 'FAIL' if failures else 'PASS',
                   'checked': count, 'failures': failures})


def _cost_near(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-8)


def _cost_p95(values):
    # Verify the statistic already saved by build_tables.py; no new measurements.
    ordered = sorted(values)
    position = (len(ordered) - 1) * .95
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _cost_stage_definitions():
    # Boundaries verified against cost_runtime.py and measure_cost.py (read only).
    definitions = [
        ('load_parse_validate', 'one model per batch', 'model descriptor / local model files',
         'parsed and validated model object', 'YES: model JSON, preprocessing and identity validation; rule base and condition digest checks',
         'NO', 'NO relation evaluation',
         '模型/预处理JSON读取、解析、身份校验；规则含基础模型与条件摘要校验。热文件系统重复读，不是OS冷启动。'),
        ('loaded_raw_adaptation', '60 positions per batch', 'already loaded App, Browser and association archive objects',
         'adapted App measurements, bound pair and field projection', 'NO', 'NO: raw objects already in memory',
         'App atom/internal relation compilation and pair binding; no model-specific C1/C2',
         '已加载两端归档与关联对象→App原子/内部关系编译、配对绑定及字段投影；共享阶段。'),
        ('model_input_prepare', '60 positions per batch', 'already adapted measurements / loaded model',
         'encoded selected inputs or projected tree input', 'NO', 'NO',
         'YES: rule selected C1/C2; tree C1/C2 only for V_BOTH_REL; frozen encoding/preprocessing included',
         '已适配测量→规则冻结编码及所选C1/C2；树含视图测量、REL关系、冻结预处理和投影。'),
        ('prepared_inference', '60 positions per batch', 'prepared model input / loaded model',
         'output state', 'NO model file loading; rule identity checks remain', 'NO',
         'NO new relation preparation; original rule judgement+extension combination or JSON tree traversal',
         '已准备输入→原规则判定与扩展组合，或JSON树遍历；规则入口自身身份检查等开销保留。'),
        ('original_current_interface', '60 positions per batch',
         'rules: adapted App/pair; trees: already derived measurement cells', 'original public-interface output',
         'RULE: YES base file loading/digests each call; TREE: NO model loading', 'NO',
         'RULE: frozen preprocessing and selected conditions; TREE: excludes cells/relations prepared before timer, includes frozen transform/traversal',
         '原规则公开接口每次含基础文件读取/摘要校验、预处理和条件；树原接口从已派生cells开始，cells/关系准备在该计时之外。'),
        ('cached_from_adapted', '60 positions per batch', 'already adapted measurements / reused loaded model',
         'cached-wrapper output', 'NO', 'NO', 'YES: model_input_prepare plus prepared_inference',
         '本地计时包装复用已加载对象；已适配测量→准备→判定，不代表旧生产代码已改造。'),
        ('loaded_raw_to_original', '60 positions per batch', 'already loaded App/Browser/association archive objects',
         'original public-interface output', 'RULE: YES within original interface; TREE: NO', 'NO: raw disk/JSON load excluded',
         'YES: shared adaptation plus model/view-specific cells/relations and public interface',
         '已加载两端raw→共享适配→所需cells/关系→原公开接口；不含raw文件读取/JSON解析。'),
        ('loaded_raw_to_cached', '60 positions per batch', 'already loaded App/Browser/association archive objects / reused loaded model',
         'cached-wrapper output', 'NO', 'NO: raw disk/JSON load excluded',
         'YES: shared adaptation plus model_input_prepare plus prepared_inference',
         '已加载两端raw→共享适配→缓存准备与判定；单端树仍可能承担多余的共享App准备。'),
    ]
    result = []
    for stage, denominator, start, end, model_load, raw_load, relations, explanation in definitions:
        result.append(dict(stage=stage, denominator=denominator, start=start, end=end,
                           model_load=model_load, raw_file_read_and_json_parse=raw_load,
                           relation_and_preprocessing_scope=relations, explanation_zh=explanation,
                           original_unit='microseconds', display_unit='milliseconds', conversion='ms = us / 1000',
                           excluded='device collection; page startup; network upload; pair waiting; first module import; timed-region logging',
                           source=COST_BASE+'cost_runtime.py;'+COST_BASE+'measure_cost.py',
                           source_locator='functions load_descriptor/adapt_loaded/prepare/infer_prepared/original_current/current_input/cached_current/loaded_raw_original/loaded_raw_cached; benchmark'))
    return result


def extract_cost(root):
    root = Path(root)
    checks = []
    costs = _cost_read_csv(root / (COST_BASE + 'tables/cost.csv'))
    resources = _cost_read_csv(root / (COST_BASE + 'tables/model_resources.csv'))
    freeze = _cost_json(root / (COST_BASE + 'timing/TIMING_FREEZE.json'))
    batches = [_cost_json_line for _cost_json_line in
               (json.loads(s) for s in (root / (COST_BASE + 'timing/batches.jsonl')).read_text().splitlines())]
    collection = _cost_read_csv(root / (COST_BASE + 'existing_times/collection_log_intervals.csv'))
    training = _cost_json(root / (COST_BASE + 'existing_times/historical_training_timing.json'))
    model_labels = {r['label'] for r in resources}
    observed_groups = {(r['label'], r['stage']) for r in costs}
    expected_groups = {(label, stage) for label in model_labels for stage in COST_STAGES}
    expected_groups.add(('shared_all_models', 'loaded_raw_adaptation'))
    failures = []
    if not (len(resources) == len(model_labels) == 21 and len(costs) == len(observed_groups) == 148):
        failures.append('Expected 21 models and 148 unique stages')
    if observed_groups != expected_groups:
        failures.append('Stage model coverage differs from 21 x 7 plus one shared adaptation')
    if not set(COST_MAIN_LABELS) <= model_labels:
        failures.append('Prespecified seven main models missing')
    _cost_check(checks, 'cost_saved_scope_and_prespecified_main_models', failures, len(costs))

    grouped = defaultdict(list)
    batch_failures = []
    for rowno, record in enumerate(batches, 1):
        grouped[(record['label'], record['stage'])].append(record)
        if not _cost_near(record['amortized_us'], record['elapsed_ns']/record['n']/1000):
            batch_failures.append(f'Batch line {rowno}: elapsed/n/us conversion')
    if len(batches) != 1480 or set(grouped) != expected_groups:
        batch_failures.append('Expected 1480 saved batches / 148 groups')
    if not (freeze['batch_n'] == 60 and freeze['recorded_passes'] == 10 and freeze['warmup_passes'] == 1):
        batch_failures.append('Freeze batch/repeat/warmup mismatch')
    if freeze['member_ids'] != [r['sample_id'] for r in collection]:
        batch_failures.append('Collection and timing freeze member order differs')
    _cost_check(checks, 'saved_batch_units_counts_and_member_order', batch_failures, len(batches))

    cost_rows = []
    statistic_failures = []
    unit_fields = ('median_amortized_us', 'p95_batch_amortized_us', 'minimum_amortized_us', 'maximum_amortized_us')
    resource_by_label = {r['label']: r for r in resources}
    for rowno, original in enumerate(costs, 2):
        row = dict(original)
        label, stage = row['label'], row['stage']
        saved = grouped[label, stage]
        n = 1 if stage == 'load_parse_validate' else 60
        if len(saved) != 10 or {b['repeat'] for b in saved} != set(range(10)) or {b['n'] for b in saved} != {n} or int(row['batch_n']) != n or int(row['repeats']) != 10:
            statistic_failures.append(f'{label}/{stage}: repeat or denominator mismatch')
        values = [r['amortized_us'] for r in saved]
        derived = (statistics.median(values), _cost_p95(values), min(values), max(values))
        for field, value in zip(unit_fields, derived):
            if not _cost_near(row[field], value):
                statistic_failures.append(f'{label}/{stage}/{field}: saved summary mismatch')
            # Original CSV strings retain source precision; only display units are converted.
            row[field.replace('_us', '_ms')] = float(row[field])/1000
        row.update(original_unit='microseconds', display_unit='milliseconds',
                   denominator='per_model' if n == 1 else 'per_position_batch_amortized_60',
                   model_id=resource_by_label.get(label, {}).get('model_id', ''),
                   main_table=label in COST_MAIN_LABELS, source=COST_BASE+'tables/cost.csv',
                   source_row=rowno, p95_scope='P95 of 10 batch-amortized values; not individual-request tail',
                   statistic_operation='saved values reused; us/1000 for display; no timing')
        cost_rows.append(row)
    _cost_check(checks, 'cost_summaries_match_all_saved_batches', statistic_failures, len(costs))
    cost_lookup = {(r['label'], r['stage']): r for r in cost_rows}
    main_cost = [cost_lookup[(label, stage)] for label in COST_MAIN_LABELS for stage in COST_STAGES]

    resource_rows = []
    model_failures = []
    for rowno, original in enumerate(resources, 2):
        row = dict(original)
        model_file = root / row['source']
        obj = _cost_json(model_file)
        if obj['model_id'] != row['model_id'] or model_file.stat().st_size != int(row['file_bytes']):
            model_failures.append(row['label'] + ': model identity or saved file size mismatch')
        if 'predictor' in obj:
            predictor = obj['predictor']
            if predictor['rule_count'] != int(row['rules']) or predictor['complexity'] != int(row['complexity']):
                model_failures.append(row['label'] + ': rule metadata mismatch')
            if (root / predictor['base']['path']).stat().st_size != int(row['base_file_bytes']):
                model_failures.append(row['label'] + ': base file size mismatch')
            if obj['setting'] == 'R_FULL' and not (predictor['extensions'] == ['C1'] and obj['usage'] == 'FROZEN_MAIN_REFERENCE' and obj['input_scope'] == 'frozen_App_atoms_plus_C1'):
                model_failures.append(row['label'] + ': R_FULL is not the frozen App+C1 reference')
            if obj['setting'] == 'R_NO_CROSS' and not (predictor['extensions'] == [] and predictor['mode'] == 'ABLATION_ONLY' and obj['allowed_sets'] == ['S0']):
                model_failures.append(row['label'] + ': R_NO_CROSS is not old baseline-only ablation')
            row.update(kind='rule', extensions=','.join(predictor['extensions']) or 'none',
                       base_model_id=predictor['base_model_id'], base_source=predictor['base']['path'],
                       identity=('frozen paired App+C1' if obj['setting'] == 'R_FULL' else
                                 'old paired-increment ablation; frozen App baseline; not new fit' if obj['setting'] == 'R_NO_CROSS' else
                                 'old matched-normal-cap ablation; not accepted resource extension'),
                       preprocessing_and_metadata='wrapper includes source/selection metadata; frozen preprocessing in required base model',
                       file_size_scope='model wrapper plus separately listed frozen base file; additional condition/adapter code and environment excluded',
                       extra_code_bytes='NOT_RECORDED', deployment_package='NO')
        else:
            if len(obj['tree']['feature']) != int(row['nodes']) or obj['tree']['depth'] != int(row['depth']):
                model_failures.append(row['label'] + ': tree node/depth metadata mismatch')
            if row['label'] != obj['plan']+' / '+obj['view']:
                model_failures.append(row['label'] + ': tree plan/view mismatch')
            row.update(kind='tree', extensions='C1,C2' if obj['view'] == 'V_BOTH_REL' else 'none',
                       base_model_id='', base_source='', identity='saved four-view comparison tree; not primary rule method',
                       preprocessing_and_metadata='JSON includes frozen preprocessing, source metadata and development/evaluation membership metadata',
                       file_size_scope='saved JSON bundle only; engine/adapter code and Python/numpy/sklearn environment excluded',
                       extra_code_bytes='NOT_RECORDED', deployment_package='NO')
        row.update(main_table=row['label'] in COST_MAIN_LABELS,
                   resource_table_source=COST_BASE+'tables/model_resources.csv', source_row=rowno,
                   later_resource_combinations_and_new_App_ablation='NOT_TIMED; no inherited cost assigned')
        resource_rows.append(row)
    _cost_check(checks, 'model_identity_and_saved_resource_values', model_failures, len(resources))
    resource_map = {r['label']: r for r in resource_rows}

    interval_rows = []
    collection_failures = []
    for rowno, original in enumerate(collection, 2):
        row = {k: v for k, v in original.items() if k not in ('sample_id', 'source', 'started_at', 'finished_at')}
        row.update(record=f'C{rowno-1:02d}', source=COST_BASE+'existing_times/collection_log_intervals.csv',
                   source_row=rowno, clock_scope='same runner host for the saved endpoints; no cross-host subtraction',
                   timestamps_and_identifiers='not copied; source CSV row locator retained')
        if original['clock'] != 'runner_host_UTC_wall_clock':
            collection_failures.append(f'CSV row {rowno}: unsupported clock')
        elapsed = (datetime.fromisoformat(original['finished_at'].replace('Z','+00:00'))-
                   datetime.fromisoformat(original['started_at'].replace('Z','+00:00'))).total_seconds()
        if elapsed < 0 or not _cost_near(elapsed, original['capture_orchestration_seconds']):
            collection_failures.append(f'CSV row {rowno}: saved same-host interval mismatch')
        if original['pure_probe_duration'] != 'NOT_RECORDED':
            collection_failures.append(f'CSV row {rowno}: unexpected pure-probe status')
        interval_rows.append(row)
    if Counter(r['cohort'] for r in collection) != Counter(pilot18=18, b2b42=42):
        collection_failures.append('Collection cohort counts differ')
    waits = [r for r in collection if float(r['explicit_preference_persistence_wait_seconds']) > 0]
    if len(waits) != 4 or any(float(r['explicit_preference_persistence_wait_seconds']) != 15 for r in waits):
        collection_failures.append('Expected all four saved 15-second preference waits retained')
    _cost_check(checks, 'same_host_collection_intervals_and_untrimmed_waits', collection_failures, len(collection))
    collection_summary = []
    fields = ('capture_orchestration_seconds', 'app_navigation_to_pair_complete_seconds',
              'settings_workflow_seconds', 'explicit_preference_persistence_wait_seconds')
    for cohort in ('pilot18', 'b2b42'):
        rows = [r for r in collection if r['cohort'] == cohort]
        for field in fields:
            values = [float(r[field]) for r in rows if r[field] != '']
            collection_summary.append(dict(cohort=cohort, metric=field, cohort_n=len(rows), recorded_n=len(values),
                                           not_recorded_n=len(rows)-len(values),
                                           median_seconds=statistics.median(values) if values else '',
                                           minimum_seconds=min(values) if values else '', maximum_seconds=max(values) if values else '',
                                           positive_wait_records=sum(v > 0 for v in values) if field == 'explicit_preference_persistence_wait_seconds' else '',
                                           status='RECORDED' if values else 'NOT_RECORDED',
                                           scope='saved same-host orchestration interval; not pure probe; includes protocol waits; no trimming',
                                           source=COST_BASE+'existing_times/collection_log_intervals.csv'))
        collection_summary.append(dict(cohort=cohort, metric='pure_probe_duration', cohort_n=len(rows), recorded_n=0,
                                       not_recorded_n=len(rows), median_seconds='', minimum_seconds='', maximum_seconds='',
                                       positive_wait_records='', status='NOT_RECORDED', scope='No pure-probe interval saved; not estimated',
                                       source=COST_BASE+'existing_times/collection_log_intervals.csv'))

    training_rows = []
    training_failures = []
    for index, original in enumerate(training):
        row = dict(original)
        if row['status'] == 'RECORDED':
            original_model = _cost_json(root / row['source'])
            if original_model['model_id'] != row['model_id'] or not _cost_near(original_model['fit']['elapsed_seconds'], row['elapsed_seconds']):
                training_failures.append(f'Training record {index}: original model interval mismatch')
            row['elapsed_seconds'] = original['elapsed_seconds']
        elif row['elapsed_seconds'] is not None:
            training_failures.append(f'Training record {index}: NOT_RECORDED has a number')
        row.update(index_source=COST_BASE+'existing_times/historical_training_timing.json', source_locator=f'[{index}]',
                   elapsed_seconds='' if original['elapsed_seconds'] is None else original['elapsed_seconds'])
        training_rows.append(row)
    if Counter(r['status'] for r in training) != Counter(RECORDED=3, NOT_RECORDED=3):
        training_failures.append('Expected 3 saved historical intervals and 3 explicit unrecorded methods')
    _cost_check(checks, 'historical_training_intervals_and_missingness', training_failures, len(training))

    settings = dict(recorded_at=freeze['time'], python=freeze['python'].split()[0], operating_system='Darwin '+freeze['platform'].split()[2],
                    machine=freeze['machine'], processor=freeze['processor'], gc_enabled=freeze['gc_enabled'],
                    timer=freeze['timer'], timer_implementation=freeze['timer_info']['implementation'],
                    timer_resolution_seconds=freeze['timer_info']['resolution'], timer_monotonic=freeze['timer_info']['monotonic'],
                    warmup_passes=freeze['warmup_passes'], recorded_passes=freeze['recorded_passes'], batch_n=freeze['batch_n'],
                    model_count=len(resources), stage_groups=len(costs), recorded_batches=len(batches),
                    numpy=freeze['packages']['numpy'], scikit_learn=freeze['packages']['scikit-learn'], scipy=freeze['packages']['scipy'],
                    inclusion=freeze['inclusion'], exclusion=freeze['exclusion'], metric=freeze['metric'],
                    host_name_and_member_ids='not copied', source=COST_BASE+'timing/TIMING_FREEZE.json')
    batch_rows = [dict(r, source=COST_BASE+'timing/batches.jsonl', source_line=i)
                  for i, r in enumerate(batches, 1)]
    data = dict(T05_cost_main=main_cost, T05_cost_all=cost_rows,
                T05_cost_shared=[cost_lookup['shared_all_models', 'loaded_raw_adaptation']],
                T05_cost_batches=batch_rows, T05_stage_definitions=_cost_stage_definitions(),
                T05_model_resources_main=[resource_map[label] for label in COST_MAIN_LABELS],
                T05_model_resources_all=resource_rows, T05_collection_intervals=interval_rows,
                T05_collection_summary=collection_summary, T05_historical_training_timing=training_rows,
                T05_timing_settings=[settings])
    metadata = dict(sources=COST_SOURCES, selection='prespecified coverage: R_FULL configurations 01/02/03 and P0 four views; no speed-based selection',
                    identity='R_FULL is frozen App+C1; R_NO_CROSS is an old baseline-only paired ablation; later resource and new App ablations were not timed',
                    numerical_sources='cost.csv; model_resources.csv; TIMING_FREEZE.json; saved batches; existing-time indices',
                    aggregation='reuse 148 saved summary rows; verify against 1480 saved batches; us/1000 display conversion only; collection cohorts remain separate',
                    limits=['No new timing or model execution', 'P95 is from ten batch-amortized values, not single-request tail latency',
                            'Overlapping paths/medians/P95 must not be added', 'Different public-interface starts and redundant raw preparation prohibit algorithm speed rankings',
                            'No collection/page start/upload/pair wait included in compute timing', 'Pure probe and isolated later training/selection durations remain unrecorded'],
                    tables={key: len(rows) for key, rows in data.items()}, status='cost table generated; no F10 chart')
    return data, checks, metadata


def _cost_table(headers, rows):
    def clean(value):
        return str(value).replace('|', '\\|').replace('\n', '<br>')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---']*len(headers)) + ' |'] +
                     ['| ' + ' | '.join(clean(x) for x in row) + ' |' for row in rows])


def render_cost_markdown(data):
    settings = data['T05_timing_settings'][0]
    lookup = {(r['label'], r['stage']): r for r in data['T05_cost_main']}
    lines = ['# T05 分阶段成本与既有时间记录', '',
             '初稿已生成／供导师选用。F10本轮以本表交付，图形化未制作／暂不需要。所有数值来自旧保存结果；本轮0重新计时、0预测、0拟合、0选择。', '',
             '## 方法身份与计时范围', '',
             '`R_FULL`是冻结App方法+C1跨端时区，不是`APP_FULL`，也不是资源增强模型。`R_NO_CROSS`是旧双端增量消融的冻结App基线，并非本轮新拟合。主表事先选当前双端基础的01/02/03三个配置与P0四视图，覆盖不同方法与接口，不按速度选优。后来的资源组合与App新消融未重新计时，不能套用旧值。', '',
             f"旧测量环境：{settings['operating_system']} {settings['machine']}，Python {settings['python']}，numpy {settings['numpy']}、sklearn {settings['scikit_learn']}、scipy {settings['scipy']}。GC开启；计时器{settings['timer']}／{settings['timer_implementation']}，分辨率约{settings['timer_resolution_seconds']*1e9:.1f} ns（不是精度保证）。", '',
             f"固定60位置（先导18+匹配42）、固定顺序；{settings['model_count']}模型、{settings['stage_groups']}阶段组，1遍预热和10遍记录，共{settings['recorded_batches']}批次。加载每批1模型，其他每批60位置均摊。P95来自10个批次均摊值，**不是单请求尾延迟**。", '',
             '保留Python循环/调用、对象分配、原入口与轻量包装计数；profiling关闭，审计钩子保留。日志写入和结果核验在计时区间之外。计算计时不含设备采集、页面启动、网络上传、配对等待、raw文件读取/JSON解析和首次模块导入。未测项目不等于零成本。', '',
             '## 1. 判断计算成本', '',
             '以下均显示**中位数 / P95，ms**。原始微秒数、原单位与分母完整保留在[主表CSV](data/T05_cost_main.csv)和[完整148组CSV](data/T05_cost_all.csv)；仅做`ms = μs / 1000`展示换算。', '']
    specs = [
        ('加载、准备与已准备输入判断', [('load_parse_validate','加载校验／每模型'), ('model_input_prepare','输入准备／每位置'), ('prepared_inference','准备后判断／每位置')]),
        ('公开接口与缓存路径', [('original_current_interface','原接口／每位置'), ('cached_from_adapted','已适配→缓存输出／每位置')]),
        ('已加载raw到输出', [('loaded_raw_to_original','已加载raw→原接口／每位置'), ('loaded_raw_to_cached','已加载raw→缓存输出／每位置')]),
    ]
    for title, columns in specs:
        lines += ['### '+title, '', _cost_table(['模型']+[name for _,name in columns],
                  [[label]+[f"{lookup[label,stage]['median_amortized_ms']:.4f} / {lookup[label,stage]['p95_batch_amortized_ms']:.4f}" for stage,_ in columns]
                   for label in COST_MAIN_LABELS]), '']
    shared = data['T05_cost_shared'][0]
    lines += [f"共享的已加载raw→适配阶段：中位{shared['median_amortized_ms']:.4f} ms/P95 {shared['p95_batch_amortized_ms']:.4f} ms每位置（60位置批均），见[共享阶段](data/T05_cost_shared.csv)。", '',
              '**上述是不同且重叠的路径。不可把各阶段中位数相加当作端到端中位数，也不可相加不同路径P95。**规则原接口与树原接口的计时起点不同，统一raw包装又可能为单端树做多余App准备；因此不据此绘制算法速度排行榜。热文件系统重复读也不是OS冷启动。', '',
              '### 各阶段起止与加载／关系边界', '',
              _cost_table(['阶段','分母','已保存测量范围'], [[r['stage'], '每模型' if r['stage']=='load_parse_validate' else '60位置批均',r['explanation_zh']] for r in data['T05_stage_definitions']]), '',
              '完整机器可读的起点、终点、模型加载、raw读取、关系/预处理范围见[阶段定义](data/T05_stage_definitions.csv)。[所有1480批次](data/T05_cost_batches.csv)保留慢批次，P1/P2也完整保留于148组明细，无裁剪或追加重复。', '',
              '## 2. 模型文件与额外依赖', '',
              _cost_table(['模型','规则数','复杂度','节点数','深度','模型/包装JSON bytes','额外基础模型 bytes'],
                          [[r['label'],r['rules'] or '—',r['complexity'] or '—',r['nodes'] or '—',r['depth'] or '—',r['file_bytes'],r['base_file_bytes']] for r in data['T05_model_resources_main']]), '',
              '规则JSON是含来源、选择记录等元数据的包装；冻结预处理位于另列的基础模型。还需已有条件与适配代码，其额外代码字节数未记录。树JSON含冻结预处理、来源及开发/评价成员元数据；不是裁剪后的部署包。表中不含代码库、Python与依赖环境大小。规则复用Python标准库和原规则/适配模块；树沿用原engine，模块导入仍依赖numpy/sklearn，不能宣称无需这些运行环境。', '',
              '[7模型资源主表](data/T05_model_resources_main.csv)／[全部21模型资源与来源](data/T05_model_resources_all.csv)。空规则/节点字段为不适用，不代表0；额外代码大小未记录。', '',
              '## 3. 已有采集与历史训练日志', '',
              '### 同host采集编排区间', '',
              '只解释已有同一runner host UTC墙钟端点的差值，不跨客户端/服务器时钟相减。墙钟不是单调时钟保证。这些秒级区间包含设置、UI、控制、上传、等待、恢复等编排，不与微秒级树遍历混为同种延迟。', '']
    summaries = {(r['cohort'],r['metric']):r for r in data['T05_collection_summary']}
    def summary_cell(cohort, metric):
        r = summaries[cohort, metric]
        return '未记录' if not r['recorded_n'] else f"{r['median_seconds']:.4f} ({r['minimum_seconds']:.4f}–{r['maximum_seconds']:.4f})；{r['recorded_n']}/{r['cohort_n']}"
    lines += [_cost_table(['批次','全流程中位（范围）秒；有效条数','App导航→pair complete 秒','设置流程秒','纯探针'],
                          [[cohort,summary_cell(cohort,'capture_orchestration_seconds'),summary_cell(cohort,'app_navigation_to_pair_complete_seconds'),summary_cell(cohort,'settings_workflow_seconds'),'未记录'] for cohort in ('pilot18','b2b42')]), '',
              '匹配正常Browser偏好的两次change、两次post均保留已记录的15秒持久化等待；共4条，未扣除后冒充纯探针耗时。纯探针时间60/60均未记录。先导App导航→pair complete没有可相减的同host字段，留空而非补零。', '',
              '[60条去标识区间](data/T05_collection_intervals.csv)／[分批次汇总](data/T05_collection_summary.csv)。不复制会话、票据、sample_id、真实host名与原始时间戳；来源定位到旧派生CSV行。', '',
              '### 历史训练／选择计时', '',
              _cost_table(['方法/配置','保存时长（秒）','时钟与范围'],
                          [[r['method'] + (f" / {i+1:02d}" if r['method']=='historical_App_RETENTION' else ''),
                            f"{r['elapsed_seconds']:.6f}" if r['elapsed_seconds']!='' else '未记录',
                            '旧time.monotonic内部fit区间；已准备输入→问题构造/选择→结束汇总前' if r['status']=='RECORDED' else r['scope']]
                           for i,r in enumerate(data['T05_historical_training_timing'])]), '',
              '三个App RETENTION保存区间不含编码器准备、raw解析、此前SPARSE拟合或完整训练流程。旧B2-C纯选择、B3-A每棵树纯fit、B3-B三个有限选择的独立时长未记录；整体流水线起止与调用次数不能替代纯训练延迟。[历史计时原值和来源](data/T05_historical_training_timing.csv)。', '',
              '## 原始来源与使用边界', '',
              '[旧成本CSV](../../../deliverables/prepaper_evidence_closeout_v1/tables/cost.csv) · [旧模型资源](../../../deliverables/prepaper_evidence_closeout_v1/tables/model_resources.csv) · [TIMING_FREEZE](../../../deliverables/prepaper_evidence_closeout_v1/timing/TIMING_FREEZE.json) · [旧成本报告](../../../deliverables/prepaper_evidence_closeout_v1/REPORT.md#4-一次离线成本测量) · [旧原始计时批次](../../../deliverables/prepaper_evidence_closeout_v1/timing/batches.jsonl)', '',
              '本表支持分清实现路径与测量边界，不支持算法倍速、设备端端到端延迟或精简部署包结论；不把后续未计时的资源增强/新App消融当作已测。', '']
    return '\n'.join(lines)


def plot_all(data,output):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'rba-round3-mpl'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.text import Text
    from PIL import Image
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
        'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
        'svg.fonttype':'none','svg.hashsalt':OWNER,'savefig.dpi':300,'hatch.linewidth':.35})
    specs={}
    def save(fig,id_,size):
        fig.canvas.draw();renderer=fig.canvas.get_renderer();outside=[];fonts=[]
        for t in fig.findobj(match=Text):
            if not t.get_visible() or not t.get_text():continue
            fonts.append(t.get_fontsize());b=t.get_window_extent(renderer)
            if b.width and b.height and (b.x0 < -1 or b.y0 < -1 or b.x1 > fig.bbox.width+1 or b.y1 > fig.bbox.height+1):outside.append(t.get_text())
        if outside or min(fonts)<8:raise ValueError((id_,outside,min(fonts)))
        fig.savefig(output/'figures'/(id_+'.svg'),metadata={'Date':None})
        fig.savefig(output/'figures'/(id_+'.png'),dpi=300,metadata={'Software':OWNER})
        if os.environ.get('RBA_ROUND3_QA_DIR'):
            qa=Path(os.environ['RBA_ROUND3_QA_DIR']);qa.mkdir(parents=True,exist_ok=True)
            fig.savefig(qa/(id_+'_96dpi.png'),dpi=96)
        with Image.open(output/'figures'/(id_+'.png')) as im:pixels=list(im.size)
        specs[id_]=dict(id=id_,svg='figures/'+id_+'.svg',png='figures/'+id_+'.png',
            size_mm=list(size),dpi=300,pixel_dimensions=pixels,minimum_font_pt=min(fonts),text_canvas_bounds='PASS')
        plt.close(fig)
    plot_f00(data,save);plot_f09(data,save)
    return specs


def link_checks(paths):
    import re
    checks=[];missing=[];count=0
    for path in paths:
        if not path.is_file():missing.append(str(path));continue
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):continue
            target=target.split('#')[0];count+=1
            if not (path.parent/target).exists():missing.append(dict(file=str(path),target=target))
    check(checks,'documentation_local_links',missing,[])
    checks[-1]['checked']=count
    return checks


def saved_checks(output):
    import struct
    import xml.etree.ElementTree as ET
    manifest=read_json(output/'FIGURES.json');checks=[];tables={}
    check(checks,'owner',manifest['owner'],OWNER)
    check(checks,'two_figures',[r['id'] for r in manifest['figures']],IDS)
    check(checks,'F10_tables_only',manifest['T05']['graphic_status'],'图形化未制作／暂不需要')
    for f in manifest['generated_files']:
        path=output/f['path'];check(checks,f['path']+'_bytes',digest(path),f['sha256'])
        if path.suffix!='.csv':continue
        rows=read_csv(path);tables[path.stem]=rows;check(checks,path.stem+'_rows',len(rows),f['rows'])
        errors=[]
        for i,r in enumerate(rows,2):
            if not all(k in r for k in ('N','T','F','U','FAILED')):continue
            counts={k:int(r[k]) for k in ('N','T','F','U','FAILED')}
            if min(counts.values())<0 or sum(counts[k] for k in ('T','F','U','FAILED'))!=counts['N']:errors.append(i)
            if 'rate' in r and (abs(float(r['rate'])-counts['T']/counts['N'])>1e-12 if counts['N'] else r['rate']!=''):errors.append(i)
        check(checks,path.stem+'_state_counts',errors,[])
    check(checks,'F09_nine_scope_condition_rows',len(tables['F09']),9)
    check(checks,'T05_148_stage_groups',len(tables['T05_cost_all']),148)
    check(checks,'T05_21_resources',len(tables['T05_model_resources_all']),21)
    check(checks,'T05_1480_saved_batches',len(tables['T05_cost_batches']),1480)
    check(checks,'T05_fixed_49_main_rows',len(tables['T05_cost_main']),49)
    for f in manifest['figures']:
        svg=ET.parse(output/f['svg']).getroot();ns='{http://www.w3.org/2000/svg}'
        check(checks,f['id']+'_svg_vector',len(svg.findall('.//'+ns+'path'))>0,True)
        check(checks,f['id']+'_svg_no_images',len(svg.findall('.//'+ns+'image')),0)
        check(checks,f['id']+'_svg_text_editable',len(svg.findall('.//'+ns+'text'))>0,True)
        for axis,mm in zip(('width','height'),f['size_mm']):
            value=svg.attrib[axis];check(checks,f['id']+'_'+axis,value.endswith('pt') and abs(float(value[:-2])*25.4/72-mm)<.001,True)
        b=(output/f['png']).read_bytes();pos=8;dpi=None;pixels=None
        while pos<len(b):
            n=struct.unpack('>I',b[pos:pos+4])[0];kind=b[pos+4:pos+8];payload=b[pos+8:pos+8+n]
            if kind==b'IHDR':pixels=list(struct.unpack('>II',payload[:8]))
            if kind==b'pHYs':
                x,y,unit=struct.unpack('>IIB',payload);dpi=min(x,y)*.0254 if unit==1 else None
            pos+=n+12
        check(checks,f['id']+'_pixels',pixels,f['pixel_dimensions']);check(checks,f['id']+'_dpi',bool(dpi and dpi>=299.99),True)
    checks.extend(link_checks([output/'README.md',output/'CAPTIONS.md',output/'T05.md',HERE.parent/'README.md']+
        [HERE.parent/r/f for r in ('round1_app','round2_paired') for f in ('README.md','CAPTIONS.md')]))
    for round_ in ('round1_app','round2_paired'):
        base=HERE.parent/round_;m=read_json(base/'FIGURES.json')
        absent=[(f['id'],k) for f in m['figures'] for k in ('svg','png','plotting_csv') if not (base/f[k]).is_file()]
        check(checks,round_+'_manifest_targets_exist',absent,[])
        check(checks,round_+'_caption_IDs',all(('## '+f['id']+'：') in (base/'CAPTIONS.md').read_text() for f in m['figures']),True)
    return checks


def compact_checks(checks):
    failures=[c for c in checks if c['status']!='PASS']
    return dict(status='FAIL' if failures else 'PASS',groups=len(checks),
        items=[dict(id=c.get('id',c.get('name')),status=c['status'],**({'checked':c['checked']} if 'checked' in c else {})) for c in checks],failures=failures)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check-only',action='store_true')
    parser.add_argument('--output',type=Path,default=HERE);args=parser.parse_args();output=args.output.resolve()
    if args.check_only:
        result=compact_checks(saved_checks(output))
        print(json.dumps(dict(mode='saved_outputs_and_links_only',status=result['status'],check_groups=result['groups'],failures=result['failures'],source_result_reads=0,writes=0),ensure_ascii=False))
        return int(result['status']!='PASS')
    output.mkdir(parents=True,exist_ok=True)
    previous=read_json(output/'FIGURES.json') if (output/'FIGURES.json').exists() else None
    if previous and previous.get('owner')!=OWNER:raise ValueError('Unknown output owner')
    allowed={'plot_round3.py','F00_source.json','README.md','CAPTIONS.md','.gitattributes'}
    if not previous:
        unknown=[str(p.relative_to(output)) for p in output.rglob('*') if p.is_file() and str(p.relative_to(output)) not in allowed]
        if unknown:raise ValueError('Unowned files: '+str(unknown))
    previous_check=read_json(output/'CHECK.json') if (output/'CHECK.json').exists() else {}
    sources=sorted(set(read_json(HERE/'F00_source.json')['sources']+F09_SOURCES+COST_SOURCES+
        ['paper/figures/round3_overview/F00_source.json','RBA_EXPERIMENT_REPORT_FOR_ADVISOR.md',
         'deliverables/app_browser_evidence_consolidation_v1/REPORT.md','deliverables/app_browser_evidence_consolidation_v1/evidence_matrix.csv']))
    before={p:digest(ROOT/p) for p in sources}
    prior_files=[p for name in ('round1_app','round2_paired') for p in (HERE.parent/name).rglob('*') if p.is_file()]
    old_before={str(p.relative_to(ROOT)):digest(p) for p in prior_files}
    data={};checks=[];metadata={}
    for key,extract in [('F00',extract_f00),('F09',extract_f09),('T05',extract_cost)]:
        d,c,m=extract(ROOT)
        if data.keys()&d.keys():raise ValueError('Duplicate data table')
        data.update(d);checks.extend(c);metadata[key]=m.get(key,m)
    failed=[c for c in checks if c['status']!='PASS']
    if failed:raise ValueError(json.dumps(failed,ensure_ascii=False))
    targets={f'data/{name}.csv' for name in data}|{f'figures/{id_}.{ext}' for id_ in IDS for ext in ('svg','png')}|{'T05.md'}
    if previous:
        owned={r['path'] for r in previous['generated_files']}
        unknown=[p for p in targets if (output/p).exists() and p not in owned]
        if unknown:raise ValueError('Refuse overwrite of unknown output '+str(unknown))
    for d in ('data','figures'):(output/d).mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rba-round3-') as name:
        stage=Path(name);(stage/'data').mkdir();(stage/'figures').mkdir()
        for name,rows in data.items():write_csv(stage/'data'/(name+'.csv'),rows)
        (stage/'T05.md').write_text(render_cost_markdown(data),encoding='utf-8')
        specs=plot_all(data,stage)
        for path in sorted(targets):(stage/path).replace(output/path)
    figures=[]
    for id_ in IDS:
        meta=dict(metadata[id_]);meta['sources']=[dict(path=p,sha256=before[p]) for p in meta['sources']]
        figures.append(dict(meta,**specs[id_],status=STATUS,
            plotting_csv='data/F09.csv' if id_=='F09' else 'data/F00_nodes.csv',
            counts=data['F09'] if id_=='F09' else {'Native':84,'Host':26,'App_Web':67,'Browser':67,'count_role':'acquisition_catalog_only'},
            png_sha256=digest(output/specs[id_]['png']),svg_sha256=digest(output/specs[id_]['svg'])))
    costmeta=dict(metadata['T05']);costmeta['sources']=[dict(path=p,sha256=before[p]) for p in costmeta['sources']]
    generated=[]
    for p in sorted(targets):
        item=dict(path=p,sha256=digest(output/p))
        if p.endswith('.csv'):item['rows']=len(data[Path(p).stem])
        generated.append(item)
    manifest=dict(owner=OWNER,status=STATUS,figures=figures,T05=dict(costmeta,markdown='T05.md',graphic_status='图形化未制作／暂不需要'),
        generated_files=generated,source_files=[dict(path=p,sha256=h) for p,h in before.items()],
        operations=dict(collection=0,fitting=0,selection=0,prediction=0,condition_evaluation=0,retiming=0,network=0),
        old_round_policy='Existence/links/naming and unchanged-byte check only; no earlier plotting entry point executed.')
    write_json(output/'FIGURES.json',manifest)
    after={p:digest(ROOT/p) for p in sources};old_after={str(p.relative_to(ROOT)):digest(p) for p in prior_files}
    check(checks,'sources_unchanged',before,after);check(checks,'earlier_rounds_unchanged',old_before,old_after)
    # This record is itself a linked deliverable; make its pending state explicit on first generation.
    if not (output/'CHECK.json').exists():write_json(output/'CHECK.json',dict(owner=OWNER,status='PENDING_CHECKS'))
    saved=saved_checks(output);visual=previous_check.get('visual_review',{})
    current_png={r['id']:r['png_sha256'] for r in figures}
    if visual.get('png_sha256')!=current_png:visual=dict(status='PENDING',png='Final PNGs and 96 dpi working-size proofs require actual inspection.',svg='Structure only; visual rendering NOT_EVALUATED.')
    report=dict(owner=OWNER,numeric=compact_checks(checks),saved_outputs=compact_checks(saved),
        source_digests=before,source_files_unchanged=before==after,
        earlier_rounds=dict(file_count=len(old_before),unchanged=old_before==old_after),
        operations=manifest['operations'],visual_review=visual)
    write_json(output/'CHECK.json',report)
    print(json.dumps(dict(figures=2,tables=len(data),numeric_status=report['numeric']['status'],saved_status=report['saved_outputs']['status'],visual_status=visual['status'],output=str(output)),ensure_ascii=False))
    return int(any(r['status']!='PASS' for r in checks+saved))


if __name__=='__main__':
    raise SystemExit(main())
