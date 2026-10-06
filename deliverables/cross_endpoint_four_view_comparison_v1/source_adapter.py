"""Load the same 951 members from original current pairs or verified MTC P1 fields."""
import importlib.util,sys
from collections import Counter
from io_utils import *
from features import RAW_FIELDS,extract
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('b3_b2b',HERE.parent/'cross_endpoint_matched_controls_v1/evaluate.py')
b2b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b2b);b2a=b2b.b2
USED={}
def use(path):
 p=Path(path)
 if ref(p) not in USED:USED[ref(p)]=digest(p)
 return p

def reduce_source(p,app_errors=(),browser_errors=(),pair_errors=()):
 if any(type(p.get(k)) is not dict for k in ('features','field_status','field_quality')):
  p={k:{} for k in ('features','field_status','field_quality')};app_errors=[*app_errors,'MAP_STRUCTURE'];browser_errors=[*browser_errors,'MAP_STRUCTURE']
 return {**{k:{f:v for f,v in p[k].items() if f in RAW_FIELDS} for k in ('features','field_status','field_quality')},
  'endpoint_errors':{'app':list(app_errors),'browser':list(browser_errors)},'pair_errors':list(pair_errors)}

def v16_projection(app,browser,app_errors=(),browser_errors=(),pair_errors=()):
 errors={'app':list(app_errors),'browser':list(browser_errors)}
 combined={k:{} for k in ('features','field_status','field_quality')}
 for side,raw in [('app',app),('browser',browser)]:
  if raw is None:
   errors[side].append('ENDPOINT_UNAVAILABLE');continue
  try:
   part=b2b.project(raw,None) if side=='app' else b2b.project(None,raw)
   for key in combined:combined[key].update(part[key])
  except (KeyError,ValueError,TypeError):errors[side].append('ENDPOINT_STRUCTURE')
 return reduce_source(combined,errors['app'],errors['browser'],pair_errors)

def p1_source(p,reg):
 ae=[];be=[];pe=[]
 if not p or p.get('sample_id')!=reg['sample_id'] or p.get('record_schema_version')!='hybridguard-mtc-observation-v2' or p.get('dataset_view')!='paired_244':
  return reduce_source({},['P1_ID_OR_STRUCTURE'],['P1_ID_OR_STRUCTURE'],['P1_ID_OR_STRUCTURE'])
 app=p.get('app',{});browser=p.get('browser',{});refs=p.get('source_refs',{})
 if type(app) is not dict or app.get('session_id')!=reg['app_session_id'] or app.get('payload_sha256')!=reg['app_payload_sha256'] or app.get('collector_version_code') not in (9,11) or refs.get('app_raw_line')!=reg['app_raw_line']:ae.append('P1_APP_BINDING')
 if type(browser) is not dict or browser.get('payload_sha256')!=reg['browser_payload_sha256'] or not browser.get('session_id') or not browser.get('receipt_id') or type(refs.get('browser_raw_line')) is not int:be.append('P1_BROWSER_BINDING')
 if p.get('pair',{}).get('pair_status')!='completed' or not p.get('pair',{}).get('browser_pair_id') or p.get('qc',{}).get('status')!='passed':pe.append('P1_PAIR_BINDING')
 return reduce_source(p,ae,be,pe)

def load():
 members=rows(use(B2C/'results/members.jsonl'));require(len(members)==951,'951_MEMBERS_REQUIRED')
 require(Counter(m['cohort'] for m in members)==dict(mtc_discovery=630,pilot18=18,b2b42=42,mtc_development=144,mtc_reserved_validation=117),'MEMBER_COHORTS_CHANGED')
 require(Counter(m['identity'] for m in members)=={'NORMAL':937,'EFFECTIVE_INTERVENTION':14},'IDENTITIES_CHANGED')
 # Verify the versioned snapshot used by B2-C; no repeat full-MTC raw audit.
 locked=read(B2C/'results/SOURCE_MANIFEST.json')['source_files'];pp=b2a.MTC/'paired_244.jsonl'
 require(digest(use(pp))==locked[ref(pp)],'P1_SNAPSHOT_CHANGED')
 registry=b2a.mtc_members();reg={r['sample_id']:r for _,r in registry}
 obs={n:r for n,r,e in b2a.rows(pp,{r['source_line'] for r in reg.values()}) if not e}
 pilot={x['meta']['sample_id']:x for x in b2a.pilot()}
 plan=read(use(b2b.HERE/'PLAN.json'));attempt=read(use(b2b.HERE/'ATTEMPT_SELECTION.json'))
 saved=unique(rows(use(b2b.HERE/'private_runs/formal01/evaluation/positions.jsonl')),lambda r:r['meta']['sample_id'])
 bindings={};caps={}
 for name in (attempt['original_run'],attempt['replacement_run']):caps[name]=unique(rows(use(b2b.HERE/name/'captures.jsonl')),lambda r:r['sample_id'])
 features=[]
 for member in members:
  sid=member['sample_id'];meta=member['source_meta']
  if member['cohort'].startswith('mtc_'):
   r=reg[sid];p=obs.get(r['source_line']);source=p1_source(p,r)
   require(r['split']==member['cohort'].removeprefix('mtc_') and meta['pair_reference']==ref(pp,r['source_line']),'MTC_REFERENCE_OR_SPLIT_CHANGED')
   refs={'snapshot':meta['pair_reference'],'app':meta['app_reference'],'browser':meta['browser_reference']}
  elif member['cohort']=='pilot18':
   item=pilot[sid];require(item['meta']==meta,'PILOT_IDENTITY_CHANGED')
   browser=None;be=list(item['pair'].get('browser_errors',[]))
   try:
    path,n=meta['browser_reference'].rsplit(':',1);browser=json.loads(use(ROOT/path).read_bytes().splitlines()[int(n)-1])
   except (OSError,ValueError,KeyError,IndexError,TypeError):be.append('BROWSER_REFERENCE_UNREADABLE')
   source=v16_projection(item['raw'],browser,item.get('app_errors',[]),be,item['pair']['errors'])
   refs={'app':meta['app_reference'],'browser':meta.get('browser_reference'),'binding':meta['capture_reference']}
  else:
   q=saved[sid];require(q['meta']==meta,'B2B_POSITION_CHANGED')
   name=attempt['replacement_run'] if sid in attempt['replacement_sample_ids'] else attempt['original_run']
   require(meta['source_run']==name,'ATTEMPT_SOURCE_CHANGED')
   slot=next(s for s in plan['positions'] if s['sample_id']==sid)
   item=b2b.bind(b2b.HERE/name,plan,slot,caps[name].get(sid))
   source=reduce_source(item['pair'],item['app_errors'],item['browser_errors'],item['pair_errors'])
   refs={'app':meta['app_reference'],'browser':meta['browser_reference'],'binding':meta['provenance_reference']}
  features.append(dict(sample_id=sid,**extract(source),references=refs))
 require({r['sample_id'] for r in features}=={m['sample_id'] for m in members},'FEATURE_MEMBERSHIP')
 # Original conditions are recalculated from actual operands, never from summary totals.
 saved_inputs=unique(rows(use(B2C/'results/inputs.jsonl')),lambda r:r['sample_id'])
 for row in features:
  for cid in ('C1','C2'):require(row['cells'][cid]['value']==saved_inputs[row['sample_id']]['conditions'][cid],'C1_C2_REPLAY_CHANGED')
 return members,features
