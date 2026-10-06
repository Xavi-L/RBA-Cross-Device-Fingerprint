"""Fixed transparent fields; only current measurements, never experiment sidecars."""
import importlib.util,math,sys
from io_utils import ROOT,HERE,require
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
p=HERE.parent/'browser67_cross_endpoint_diagnostic_v1/conditions.py'
spec=importlib.util.spec_from_file_location('b3_frozen_conditions',p);conditions=importlib.util.module_from_spec(spec);spec.loader.exec_module(conditions)
from hybridguard_agent.research.rule_semantics_revision_v1.language import limited_full_tag
N='app.android_native_data.locale_timezone_layer.'
A='app.web_data.';B='browser.web_data.'
# output name -> raw path, transform, endpoint, array type
FIELDS={
 'native_locale':(N+'native_locale','category','app','category'),
 'native_zone':(N+'native_timezone_id','category','app','category'),
 'native_raw_offset':(N+'native_timezone_offset_min','number','app','numeric')}
for side,prefix in [('app',A),('browser',B)]:
 for name,path,transform,kind in [('language','navigator_layer.language','tag','category'),('first_language','navigator_layer.languages','first','category'),('language_count','navigator_layer.languages','length','numeric'),('web_offset','execution_layer.timezone_offset','number','numeric')]:
  FIELDS[side+'_'+name]=(prefix+path,transform,side,kind)
APP=[k for k,v in FIELDS.items() if v[2]=='app'];BROWSER=[k for k,v in FIELDS.items() if v[2]=='browser']
VIEWS={'V_APP':APP,'V_BROWSER':BROWSER,'V_BOTH':APP+BROWSER,'V_BOTH_REL':APP+BROWSER+['C1','C2']}
CAT=[k for k,v in FIELDS.items() if v[3]=='category'];NUM=[k for k,v in FIELDS.items() if v[3]=='numeric']
RAW_FIELDS=sorted(set(v[0] for v in FIELDS.values()))

def measure(projection,path,transform):
 fs,st,q=(projection.get(k,{}) for k in ('features','field_status','field_quality'))
 value=fs.get(path);reason=None
 if path not in fs:reason='FIELD_ABSENT'
 elif st.get(path)!='observed':reason='STATUS:'+str(st.get(path))
 elif q.get(path)!='observed_value':reason='QUALITY:'+str(q.get(path))
 elif value is None:reason='NULL'
 result=None
 if reason is None:
  if transform=='number':
   if type(value) not in (int,float) or not math.isfinite(value):reason='NOT_FINITE_NUMBER'
   else:result=value
  elif transform=='category':
   if type(value) is not str or not value:reason='NOT_NONEMPTY_STRING'
   else:result=value
  elif transform=='tag':
   result=limited_full_tag(value)
   if result is None:reason='OUTSIDE_LIMITED_TAG_DOMAIN'
  elif transform in ('first','length'):
   if type(value) is not list or any(type(x) is not str for x in value):reason='NOT_STRING_LIST'
   elif transform=='length':result=len(value)
   elif not value:reason='EMPTY_LIST_NO_FIRST'
   else:
    result=limited_full_tag(value[0])
    if result is None:reason='FIRST_OUTSIDE_LIMITED_TAG_DOMAIN'
 return dict(value=result,available=reason is None,reason=reason or 'OBSERVED',field=path,
  source_status=st.get(path),source_quality=q.get(path),raw_type=type(value).__name__)

def extract(source):
 require(set(source)<= {'features','field_status','field_quality','endpoint_errors','pair_errors'},'SOURCE_CONTAINS_SIDECAR')
 require(all(type(source.get(k)) is dict for k in ('features','field_status','field_quality')),'SOURCE_MAP_STRUCTURE')
 cells={}
 for name,(path,transform,side,kind) in FIELDS.items():
  cell=measure(source,path,transform)
  if source['endpoint_errors'][side]:cell.update(value=None,available=False,reason='ENDPOINT_BINDING_FAILED')
  cells[name]=cell
 errors=[*source['endpoint_errors']['app'],*source['endpoint_errors']['browser'],*source['pair_errors']]
 pair={k:{f:v for f,v in source[k].items() if f in set(conditions.DEPS['C1']+conditions.DEPS['C2'])} for k in ('features','field_status','field_quality')};pair['errors']=errors
 for cid in ('C1','C2'):
  r=conditions.evaluate(cid,pair)
  cells[cid]=dict(value=r['state'],available=r['state'] in ('T','F'),reason=r['reason'],field=cid,source_status='derived_original_condition',source_quality='not_an_independent_measurement')
 return dict(cells=cells,endpoint_errors=source['endpoint_errors'],pair_errors=source['pair_errors'])

def view_status(item,view):
 sides=('app',) if view=='V_APP' else ('browser',) if view=='V_BROWSER' else ('app','browser')
 errors=[e for s in sides for e in item['endpoint_errors'][s]]
 if len(sides)==2:errors+=item['pair_errors']
 if view=='V_BOTH_REL' and any(item['cells'][c]['value']=='FAILED' for c in ('C1','C2')):errors+=['RELATION_EXECUTION_FAILED']
 fields=[f for f in VIEWS[view] if f in FIELDS]
 available=sum(item['cells'][f]['available'] for f in fields)
 return dict(gate='FAILED' if errors else 'U' if available==0 else 'READY',errors=errors,
  measured_available=available,measured_expected=len(fields),input_complete=available==len(fields),
  missing={f:item['cells'][f]['reason'] for f in fields if not item['cells'][f]['available']})
