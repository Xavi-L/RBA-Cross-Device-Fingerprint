#!/usr/bin/env python3
"""Lightweight saved result checks, no refits, predictions or cryptographic scans."""
import gzip
import json
from pathlib import Path
from summarize import ROOT,HERE,read,rows,validate,write

def main(out=HERE):
    settings=read(out/'SETTINGS.json');members=read(ROOT/settings['membership_and_baseline_settings'])
    data=rows(out/'predictions.jsonl.gz');validate(data,members)
    old={(r['fold_id'],r['sample_id']):r for r in rows(ROOT/settings['baseline_predictions']) if r['scheme']=='B_REL'}
    reused=0
    for r in data:
        if r['scheme']=='B_REL':
            assert r==old[r['fold_id'],r['sample_id']];reused+=1
        states=[rule['state'] for rule in r['rules']]
        assert set(states) <= {'T','F','U'}
        expected='MANIPULATION_ALERT' if 'T' in states else 'INSUFFICIENT_EVIDENCE' if 'U' in states else 'NO_ALERT'
        assert r['decision']==expected,(r['sample_id'],expected,r['decision'])
    entries=read(out/'models.json')['models']
    assert len(entries)==6
    assert len((out/'FIT_CALLS.jsonl').read_text().splitlines())==6
    base=read(ROOT/settings['baseline_models'])['models']
    for m in entries:
        b=next(x for x in base if x['fold_id']==m['fold_id'] and x['stage']=='RETENTION')
        original=read((ROOT/settings['baseline_models']).parent/b['path'])
        current=read(out/m['path'])
        assert current['encoder']==original['encoder']
        assert current['fit']['relation_parameters']['timezone']['tzdb_version']=='2026c'
        assert current['fit']['clean_budget_count']==8
        assert current['fit']['mtc_budget_count']==31
    checks={'saved_predictions_or_checks':len(data),'saved_B_REL_rows_reused_identically':reused,
        'six_model_encoders_equal_same_fold_saved_baseline':True,'actual_fit_calls':6,
        'extra_fit_calls_from_validation':0,'exact_planned_member_alignment':True}
    local=rows(out/'new_batch.jsonl.gz')
    if local:
        assert len(local)==36
        assert len({(r['environment'],r['step_id']) for r in local})==36
        checks['local_planned_positions']=36
    write(out/'SAVED_RESULT_CHECKS.json',checks)
    print(json.dumps(checks,ensure_ascii=False))

if __name__=='__main__':main()
