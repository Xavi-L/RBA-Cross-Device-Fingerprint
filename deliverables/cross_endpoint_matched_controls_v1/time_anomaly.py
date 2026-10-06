"""Inspect only the previously named MTC pair, without altering historical data."""
import json
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SOURCE=ROOT/'backend_server/collection_backups/mtc_final_20260922/sources'
PAIR='hgpair-v1-a01c05ee9faf637996ed1ddc'
def selected(file,predicate):
    with (SOURCE/file).open() as f:
        return [(n,json.loads(line)) for n,line in enumerate(f,1) if predicate(json.loads(line))]
def reference(file,n):return str((SOURCE/file).relative_to(ROOT))+':'+str(n)
def iso(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def utc(s):return datetime.fromtimestamp(s,timezone.utc).isoformat()
def run():
    bn,b=selected('raw_browser_payloads.jsonl',lambda r:r.get('pair_id')==PAIR)[0]
    aa=selected('raw_expanded_payloads.jsonl',lambda r:r.get('session_id')==b['app_session_id'] and r.get('receipt_id')==b['app_receipt_id'])
    assert len(aa)==1
    an,a=aa[0];batch=a['collection_batch_id'];ap=a['canonical_received_payload'];bp=b['canonical_received_payload']
    r={'sample_id':'mtc-pair-'+PAIR,'app_reference':reference('raw_expanded_payloads.jsonl',an),'browser_reference':reference('raw_browser_payloads.jsonl',bn),
       'app':{'payload_timestamp_seconds':ap['timestamp'],'payload_timestamp_interpreted_utc':utc(ap['timestamp']),'server_received_at':a['server_received_at'],
              'collection_started_at_ms':ap['collection_manifest'].get('collection_started_at_ms'),'collection_finished_at_ms':ap.get('collection_diagnostics',{}).get('collection_finished_at_ms')},
       'browser':{'payload_timestamp_seconds':bp['timestamp'],'payload_timestamp_interpreted_utc':utc(bp['timestamp']),'server_received_at':b['server_received_at'],'collection_diagnostics':bp.get('collection_diagnostics')},
       'payload_timestamp_difference_seconds':bp['timestamp']-ap['timestamp'],
       'server_receipt_difference_seconds':(iso(b['server_received_at'])-iso(a['server_received_at'])).total_seconds(),
       'events':[],'lifecycle':[],'provenance':[]}
    for file,dest,predicate in [('browser_pair_events.jsonl','events',lambda v:v.get('pair_id')==PAIR),('browser_pair_provenance.jsonl','provenance',lambda v:v.get('pair_id')==PAIR),('collection_batches.jsonl','lifecycle',lambda v:v.get('collection_batch_id')==batch)]:
        for n,v in selected(file,predicate):
            keep={k:val for k,val in v.items() if any(x in k for x in ['time','_at','event','status','clock']) or k in ['collection_batch_id','pair_id','ticket_binding_mode']}
            r[dest].append({'reference':reference(file,n),'values':keep})
    r['interpretation']='Server receive events in the same retained backend process batch are 32.100967 seconds apart. Payload clock difference does not establish elapsed collection time. Exact cause of device clock change, stale timestamp, or payload construction timing is not proven by these records.'
    r['unchanged']='No historical rows, labels, thresholds, membership, or prior outputs changed.'
    (HERE/'TIME_ANOMALY.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
