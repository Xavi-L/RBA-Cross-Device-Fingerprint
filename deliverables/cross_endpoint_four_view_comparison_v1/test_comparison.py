import copy,tempfile,unittest
import numpy as np
import engine as e
from io_utils import *
from features import *
from source_adapter import p1_source,v16_projection

def raw_source():
 values={N+'native_locale':'en-US',N+'native_timezone_id':'Asia/Shanghai',N+'native_timezone_offset_min':480}
 for prefix in (A,B):values.update({prefix+'navigator_layer.language':'en-US',prefix+'navigator_layer.languages':['en-US','en'],prefix+'execution_layer.timezone_offset':-480})
 return dict(features=values,field_status={k:'observed' for k in values},field_quality={k:'observed_value' for k in values},endpoint_errors={'app':[],'browser':[]},pair_errors=[])

def fixtures():
 rs=[];ms=[]
 for i in range(8):
  s=raw_source()
  if i>=4:s['features'][B+'execution_layer.timezone_offset']=-540
  rs.append(dict(sample_id=str(i),**extract(s)))
  ms.append(dict(sample_id=str(i),identity='NORMAL' if i<4 else 'EFFECTIVE_INTERVENTION',cohort='mtc_discovery' if i<2 else 'b2b42',family='Browser_timezone' if i>=4 else None))
 return rs,ms

class Features(unittest.TestCase):
 def test_catalog_views(self):
  self.assertEqual(len(RAW_FIELDS),9);self.assertEqual(len(FIELDS),11)
  self.assertEqual(VIEWS['V_BOTH_REL'],VIEWS['V_BOTH']+['C1','C2'])
  self.assertTrue(all(FIELDS[k][2]=='app' for k in APP));self.assertTrue(all(FIELDS[k][2]=='browser' for k in BROWSER))
 def test_same_web_representation(self):
  x=extract(raw_source())
  for f in ('language','first_language','language_count','web_offset'):self.assertEqual(x['cells']['app_'+f]['value'],x['cells']['browser_'+f]['value'])
 def test_zero_minus_one_and_bool(self):
  for value in (0,-1):
   s=raw_source();s['features'][B+'execution_layer.timezone_offset']=value
   self.assertEqual(extract(s)['cells']['browser_web_offset']['value'],value)
  s['features'][B+'execution_layer.timezone_offset']=False
  self.assertEqual(extract(s)['cells']['browser_web_offset']['reason'],'NOT_FINITE_NUMBER')
 def test_runtime_error_zero_missing(self):
  s=raw_source();f=B+'execution_layer.timezone_offset';s['features'][f]=0;s['field_status'][f]='runtime_error';s['field_quality'][f]='source_unavailable'
  x=extract(s);self.assertFalse(x['cells']['browser_web_offset']['available']);self.assertEqual(x['cells']['C1']['value'],'U')
 def test_empty_list(self):
  s=raw_source();s['features'][B+'navigator_layer.languages']=[];x=extract(s)
  self.assertEqual(x['cells']['browser_language_count']['value'],0);self.assertIsNone(x['cells']['browser_first_language']['value'])
 def test_unsupported_tag_not_known_language(self):
  s=raw_source();s['features'][B+'navigator_layer.language']='zh_CN';x=extract(s)
  self.assertFalse(x['cells']['browser_language']['available']);self.assertEqual(x['cells']['C2']['value'],'U')
 def test_endpoint_and_pair_isolation(self):
  x=extract(raw_source());x['endpoint_errors']['browser']=['BAD_BROWSER']
  self.assertEqual(view_status(x,'V_APP')['gate'],'READY');self.assertEqual(view_status(x,'V_BROWSER')['gate'],'FAILED')
  x['endpoint_errors']={'app':['BAD_APP'],'browser':[]}
  self.assertEqual(view_status(x,'V_BROWSER')['gate'],'READY')
  x['endpoint_errors']['app']=[];x['pair_errors']=['MISMATCH']
  self.assertEqual(view_status(x,'V_APP')['gate'],'READY');self.assertEqual(view_status(x,'V_BROWSER')['gate'],'READY')
  self.assertEqual(view_status(x,'V_BOTH')['gate'],'FAILED')
 def test_all_missing_is_U(self):
  s=raw_source()
  for f in RAW_FIELDS:
   if f.startswith('app.'):s['field_status'][f]='runtime_error'
  x=extract(s);self.assertEqual(view_status(x,'V_APP')['gate'],'U');self.assertEqual(view_status(x,'V_BOTH')['gate'],'READY')
 def test_no_sidecar_input(self):
  for key in ('label','phase','scenario','model_output','version','timestamp','target','pair_id'):
   s=raw_source();s[key]='forbidden'
   with self.assertRaises(ValueError):extract(s)
 def test_bad_snapshot_retained_failed(self):
  source=p1_source(None,{'sample_id':'planned'});self.assertEqual(view_status(extract(source),'V_BOTH')['gate'],'FAILED')
 def test_broken_browser_structure_keeps_app(self):
  s=raw_source();app={'canonical_received_payload':{'collection_status':{'fields':{k.removeprefix('app.'):v for k,v in s['field_status'].items() if k.startswith('app.') }},'web_data':{'navigator_layer':{'language':'en-US','languages':['en-US']},'execution_layer':{'timezone_offset':-480}},'android_native_data':{'locale_timezone_layer':{'native_locale':'en-US','native_timezone_id':'Asia/Shanghai','native_timezone_offset_min':480}}}}
  x=extract(v16_projection(app,{'bad':'structure'}))
  self.assertEqual(view_status(x,'V_APP')['gate'],'READY');self.assertEqual(view_status(x,'V_BROWSER')['gate'],'FAILED')

class Learning(unittest.TestCase):
 def test_weights_halves_and_present_families(self):
  _,ms=fixtures();y,w,groups=e.weights(ms)
  self.assertAlmostEqual(sum(w[:4]),.5);self.assertAlmostEqual(sum(w[4:]),.5)
  self.assertEqual({g['group'] for g in groups if g['label']==1},{'Browser_timezone'})
  self.assertTrue(all(g['total']==.25 for g in groups if g['label']==0))
 def test_unknown_label_not_normal(self):
  _,ms=fixtures();ms[0]['identity']='UNCONFIRMED'
  with self.assertRaises(ValueError):e.weights(ms)
 def test_whole_batch_groups_and_repair(self):
  ms=rows(B2C/'results/members.jsonl')
  for plan,n in [('P0',690),('P1',672),('P2',648)]:
   tr,ev=e.split(ms,plan);self.assertEqual(len(tr),n);self.assertFalse({m['group_id'] for m in tr}&{m['group_id'] for m in ev})
  tr,_=e.split(ms,'P2');self.assertEqual({m['family'] for m in tr if m['identity']=='EFFECTIVE_INTERVENTION'},{'Browser_language','Browser_timezone'})
  for m in ms:
   if m['cohort']=='b2b42' and m['scenario']=='L_BROWSER_LANG':self.assertEqual(m['source_meta']['source_run'],'private_runs/repair01')
 def test_restore_failed_effective_identity_retained(self):
  _,ms=fixtures();ms[4]['runtime_restored']=False
  self.assertEqual(e.label(ms[4]),1);self.assertEqual(len(e.weights(ms)[0]),8)
 def test_train_vocab_median_and_eval_unseen(self):
  rs,_=fixtures();spec=e.fit_preprocessor(rs[:4],[r['sample_id'] for r in rs[:4]]);saved=copy.deepcopy(spec)
  unseen=copy.deepcopy(rs[4]);unseen['cells']['native_zone']['value']='EvaluationOnly';unseen['cells']['native_raw_offset'].update(value=None,available=False)
  X,unknown=e.transform(spec,[unseen]);self.assertEqual(spec,saved)
  self.assertIn({'field':'native_zone','value':'EvaluationOnly'},unknown[0]);self.assertEqual(X[0,spec['columns']['native_raw_offset'][0]],480)
  self.assertIsNone(unseen['cells']['native_raw_offset']['value'])
 def test_all_missing_training_placeholder(self):
  rs,_=fixtures()
  for r in rs:r['cells']['browser_web_offset'].update(value=None,available=False)
  spec=e.fit_preprocessor(rs,[r['sample_id'] for r in rs]);self.assertTrue(spec['numeric']['browser_web_offset']['all_training_missing']);X,_=e.transform(spec,rs)
  self.assertTrue(np.all(X[:,spec['columns']['browser_web_offset']]==[0,1]))
 def test_both_share_original_columns(self):
  rs,_=fixtures();spec=e.fit_preprocessor(rs,[r['sample_id'] for r in rs]);X,_=e.transform(spec,rs)
  both,_=e.view_array(spec,X,rs,'V_BOTH');rel,names=e.view_array(spec,X,rs,'V_BOTH_REL');self.assertTrue(np.array_equal(both,rel[:,:both.shape[1]]));self.assertEqual(names[-6:],['C1=F','C1=T','C1=U','C2=F','C2=T','C2=U'])
 def test_positive_column_and_half_threshold(self):
  self.assertEqual(e.positive_probability(np.array([[.8,.2]]),[1,0])[0],.8)
  self.assertEqual(e.positive_probability(np.array([[1.]]),[0])[0],0)
  self.assertTrue(e.positive_probability(np.array([[.5,.5]]),[0,1])[0]>=.5)
 def test_actual_deterministic_fit_and_portable_replay(self):
  rs,ms=fixtures();spec=e.fit_preprocessor(rs,[r['sample_id'] for r in rs]);X,_=e.transform(spec,rs);X,names=e.view_array(spec,X,rs,'V_BOTH_REL')
  a,wa,_=e.fit_tree(X,ms);b,wb,_=e.fit_tree(X,ms);ta=e.tree_json(a,names);tb=e.tree_json(b,names)
  self.assertEqual(ta,tb);self.assertEqual(wa,wb);self.assertEqual(a.get_params()['class_weight'],None)
  p,l=e.predict_tree(a,X);jp,jl=e.predict_json(ta,X);self.assertTrue(np.allclose(p,jp));self.assertTrue(np.array_equal(l,jl))
 def test_app_inference_does_not_read_browser(self):
  rs,ms=fixtures();spec=e.fit_preprocessor(rs,[r['sample_id'] for r in rs]);X,_=e.transform(spec,rs);X,names=e.view_array(spec,X,rs,'V_APP');model,_,_=e.fit_tree(X,ms)
  bundle=dict(view='V_APP',preprocessing=spec,tree=e.tree_json(model,names))
  item={k:copy.deepcopy(rs[0][k]) for k in ('cells','endpoint_errors','pair_errors')}
  item['cells']={k:v for k,v in item['cells'].items() if k in APP};item['endpoint_errors']={'app':[],'browser':['MISSING']}
  self.assertIn(e.predict_current(bundle,item)['state'],('T','F'))
 def test_app_preprocessing_independent_of_browser_values(self):
  rs,_=fixtures();a=e.fit_preprocessor(rs,[r['sample_id'] for r in rs]);changed=copy.deepcopy(rs)
  for r in changed:r['cells']['browser_language']['value']='eval-only-marker'
  b=e.fit_preprocessor(changed,[r['sample_id'] for r in changed]);xa,_=e.transform(a,rs);xb,_=e.transform(b,rs)
  self.assertTrue(np.array_equal(e.view_array(a,xa,rs,'V_APP')[0],e.view_array(b,xb,rs,'V_APP')[0]))
