#!/usr/bin/env python3
"""Check saved table counts and group membership; never runs research code.

Usage: python3 tables/verify_tables.py [--repo /path/to/repository]
The optional repository path also cross-checks bundled data against its sources.
This checks data, not visual layout; compile/render the manuscript separately.
"""
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path)
args = parser.parse_args()
here = Path(__file__).resolve().parent
read = lambda name: json.loads((here / name).read_text())
app = read('01_compact_groups.json')
mechanisms = read('02_table_data.json')
cap = read('03_table_data.json')
paired = read('04_table_data.json')

methods = app['methods']
assert methods == ['APP_FULL', 'A_NO_MTC_CAP', 'A_APP_WEB_ONLY',
                   'A_NO_MEMORY_REL', 'A_NO_TIMEZONE_REL', 'APP_TREE']
assert [g['configuration_count'] for g in app['groups']] == [1, 1, 2, 8, 2]
members = [m for g in app['groups'] for m in g['members']]
assert len(members) == len(set(members)) == 14
totals = [sum(g['configuration_count'] * g['counts'][i]
              for g in app['groups']) for i in range(6)]
assert totals == [105, 108, 96, 96, 105, 72]
for group in app['groups']:
    assert len(group['members']) == group['configuration_count']
    for method, detected in zip(methods, group['counts']):
        n, t, f, u, failed, empty = group['states_by_method'][method]
        assert n == 9 and t == detected and t + f + u + failed + empty == n
        assert u == failed == empty == 0

expected_mechanisms = [
    (18, 48, [('R_WEB8', 6, 0), ('R_REL', 18, 0)]),
    (6, 30, [('R_ABSOLUTE', 6, 6), ('R_TZ', 6, 0)]),
    (6, 66, [('R_HEIGHT710', 6, 6), ('R_SAME_WEB', 0, 0), ('R_HOST_GEOMETRY', 6, 0)]),
]
for group, (attack_n, normal_n, rows) in zip(mechanisms['groups'], expected_mechanisms):
    assert (group['attack_N'], group['normal_N']) == (attack_n, normal_n)
    assert [(r['condition_id'], r['detected'], r['false_alarms'])
            for r in group['rows']] == rows

assert [g['N'] for g in cap['groups']] == [144, 117]
for group, expected in zip(cap['groups'], [(135, 136, 8), (110, 111, 6)]):
    f12, f3, u = expected
    assert [(r['T'], r['F'], r['U']) for r in group['with_cap']] == [(1, f12, u), (0, f3, u)]
    assert (group['without_cap']['T'], group['without_cap']['F'], group['without_cap']['U']) == (group['N'], 0, 0)
    for row in group['with_cap'] + [group['without_cap']]:
        assert row['T'] + row['F'] + row['U'] == row['N']
        assert row['FAILED'] == row['EMPTY_MODEL'] == 0
assert [(r['N'], r['T']) for r in cap['controlled_interventions']] == [(126, 105), (126, 108)]
assert [(r['N'], r['T']) for r in cap['controlled_normals']] == [(252, 0), (252, 0)]
assert [(r['N'], r['T'], r['U']) for r in cap['constraint_training']] == [(630, 6, 51), (630, 6, 51), (630, 0, 51), (630, 630, 0), (630, 630, 0), (630, 630, 0)]

for row, counts in zip(paired['rows'], [[2, 0, 0, 0], [2, 0, 5, 0]]):
    families = row['families']
    assert [f['N'] for f in families] == [2, 2, 5, 5]
    assert [f['T'] for f in families] == counts
    assert row['total_modifications']['T'] == sum(counts)
    assert row['total_modifications']['N'] == 14
    assert row['normal']['N'] == 46 and row['normal']['T'] == 0
    assert all(f['U'] == f['FAILED'] == 0 for f in families + [row['normal']])
assert paired['delta_counts'] == {'App_timezone': 0, 'App_language': 0,
                                  'Browser_timezone': 5, 'Browser_language': 0,
                                  'TOTAL': 5, 'NORMAL': 0}
for row in paired['historical_normal_context']:
    assert row['app']['N'] == row['paired']['N'] == 261
    assert row['app']['U'] == 14 and row['paired']['U'] == 17
    assert row['app']['T'] == row['paired']['T']
    assert [r['n'] for r in row['paired_original_groups']] == [144, 117]

repository_crosscheck = False
if args.repo:
    originals = args.repo / 'paper/figures/experiment_storyboards_20261016'
    for name in ['01_compact_groups.json', '02_table_data.json', '03_table_data.json', '04_table_data.json']:
        assert read(name) == json.loads((originals / name).read_text())
    with (args.repo / app['source']).open() as handle:
        raw = list(csv.DictReader(handle))
    keys = app['grouping_keys']
    for group in app['groups']:
        for member in group['members']:
            for method in methods:
                matches = [r for r in raw if r['configuration'] == member and r['scheme'] == method]
                assert len(matches) == 1, (member, method, len(matches))
                assert [int(matches[0][k]) for k in keys] == group['states_by_method'][method]
    repository_crosscheck = True

print(json.dumps({'status': 'PASS', 'verification': 'Saved-summary arithmetic, group membership, and expected display values',
                  'repository_crosscheck': repository_crosscheck, 'app_weighted_detections': totals,
                  'new_experiments': False, 'layout_verified_by_this_script': False}, indent=2))
