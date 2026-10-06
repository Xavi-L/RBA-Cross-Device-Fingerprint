"""Reconcile actual acquisition attempts without evaluating a detector."""
import json
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
def rows(p):return [json.loads(s) for s in p.read_text().splitlines() if s]
def run():
    groups=[]
    for name,n in [('engineering/smoke01',12),('formal01',42),('repair01',6)]:
        root=HERE/'private_runs'/name;caps=rows(root/'captures.jsonl');apps=rows(root/'data/raw_expanded_payloads.jsonl');browsers=rows(root/'data/raw_browser_payloads.jsonl');pairs=rows(root/'data/browser_pair_provenance.jsonl')
        assert len(caps)==n and len({c['sample_id'] for c in caps})==n
        delta=[(datetime.fromisoformat(p['browser_received_at'].replace('Z','+00:00'))-datetime.fromisoformat(p['app_receipt_server_received_at'].replace('Z','+00:00'))).total_seconds() for p in pairs]
        row={'run':name,'planned_attempts':n,'recorded_attempts':len(caps),'completed_pairs':sum(c['result']=='COMPLETED' for c in caps),'app_raw_records':len(apps),'browser_raw_records':len(browsers),'provenance_records':len(pairs),'unique_app_sessions':len({a['session_id'] for a in apps}),'unique_browser_sessions':len({b['browser_session_id'] for b in browsers}),'unique_pair_ids':len({p['pair_id'] for p in pairs}),'runtime_restoration_failures':sum(any(x['status']!='COMPLETED' for x in c['restoration']) for c in caps),'server_receipt_difference_seconds_range':[min(delta),max(delta)],'lifecycle':json.loads((root/'backend_lifecycle_summary.json').read_text()),'capture_reference':str((root/'captures.jsonl').relative_to(HERE))}
        assert row['lifecycle']['closed_cleanly'] and row['lifecycle']['active_marker_removed']
        groups.append(row)
    out={'runs':groups,'actual_acquisition_attempts':sum(g['recorded_attempts'] for g in groups),'formal_and_repair_attempts':48,'canonical_evaluation_positions':42,'original_superseded_attempts_retained':6,'training_calls':0,'source':'Private physical raw lines, exact pair provenance, capture ledgers, closed backend batches. No predictions used.'}
    (HERE/'ACQUISITION_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out)
if __name__=='__main__':run()
