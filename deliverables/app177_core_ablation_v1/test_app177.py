"""Focused protocol and input-isolation tests; no real or synthetic model fits."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import gzip
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import data
from data import engine
import tree

class App177Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=data.settings();cls.f=cls.s['folds'][0];cls.model=data.full_models()[cls.f['fold_id']]
        r,meta,mr,mm,ms=data.training(cls.f)
        cls.args=(cls.f,{s:r['raw'] for s,r in r.items()},meta,{s:r['raw'] for s,r in mr.items()},mm,cls.model.encoder)
        cls.kw={'mtc_ids':cls.s['mtc_normal_train_ids'],'evaluation_ids':cls.s['mtc_primary_ids']['development']+cls.s['mtc_primary_ids']['reserved_validation']}
        cls.prepared=engine.prepare(*cls.args,scheme='APP_FULL',**cls.kw)
    def test_membership_and_no_preprocessing_fit(self):
        with patch('hybridguard_agent.research.rule_learning_v2.adapter.encode_train',side_effect=AssertionError('refit')):
            for scheme in engine.SCHEMES:
                p=engine.prepare(*self.args,scheme=scheme,**self.kw)
                self.assertEqual(p.common.encoder,self.model.encoder)
                self.assertEqual(set(p.common.ids),set(self.f['train_ids']))
                self.assertFalse(set(p.common.ids)&set(self.f['outer_test_ids']))
        args=list(self.args);args[1]={**args[1],self.f['outer_test_ids'][0]:next(iter(args[1].values()))}
        with self.assertRaises(PermissionError):engine.prepare(*args,scheme=engine.SCHEMES[0],**self.kw)
    def test_full_score_and_pools_equal(self):
        p,_=engine.problem(self.prepared,time.monotonic()+60)
        self.assertEqual(json.loads(json.dumps(engine.json_score(p.score(self.model.clauses)))),self.model.fit['training_result'])
        self.assertEqual((p.budget,p.mtc_budget,len(p.clean),len(p.mtc_ids)),(8,31,168,630))
    def test_masks_aliases_both_polarities_and_zero_relations(self):
        atoms=engine.frozen_atoms(self.model.encoder)
        for scheme,family in [('A_NO_MEMORY_REL','memory_relation'),('A_NO_TIMEZONE_REL','timezone_relation')]:
            kept=[a for a in atoms if engine.allowed(a,scheme)]
            self.assertTrue(any(a.atom_id.startswith('CONTROL:') and ('device_memory' if family=='memory_relation' else 'timezone_offset') in a.atom_id for a in kept))
            self.assertFalse(any(engine.dependency(a)['family']==family for a in kept))
            original=next(a for a in atoms if engine.dependency(a)['family']==family)
            self.assertFalse(engine.allowed(replace(original,atom_id='renamed-equivalent',aliases=('fixed','date','negative')),scheme))
        web=engine.prepare(*self.args,scheme='A_APP_WEB_ONLY',**self.kw)
        self.assertTrue(all(set(engine.dependency(a)['measurement_surfaces'])=={'app_web67'} for a in web.common.atoms))
        self.assertTrue(any(a.atom_id==data.screen.ATOM_ID for a in web.common.atoms))
        # A legitimate zero-extra-relation problem needs no fabricated relation.
        atoms=tuple(a for a in web.common.atoms if a.atom_id!=data.screen.ATOM_ID);names={a.atom_id for a in atoms}
        c=replace(web.common,atoms=atoms,controlled_rows={s:{k:v for k,v in r.items() if k in names} for s,r in web.common.controlled_rows.items()},
                  mtc_rows={s:{k:v for k,v in r.items() if k in names} for s,r in web.common.mtc_rows.items()})
        p,_=engine.problem(replace(web,common=c),time.monotonic()+60)
        self.assertEqual(p.score(())['mtc_state_counts']['EMPTY_MODEL'],630)
    def test_budget_only_and_cache_immutable(self):
        capped,_=engine.problem(self.prepared,time.monotonic()+60)
        p=engine.prepare(*self.args,scheme='A_NO_MTC_CAP',**self.kw);uncapped,_=engine.problem(p,time.monotonic()+60)
        self.assertEqual([c.id for c in capped.candidates],[c.id for c in uncapped.candidates])
        self.assertEqual(uncapped.budget,capped.budget);self.assertEqual(uncapped.mtc_budget,630)
        for clauses in [(),self.model.clauses,*[(c,) for c in capped.candidates]]:
            a,b=capped.score(clauses),uncapped.score(clauses)
            for key in ['clean_alarms','mtc_coverage','mtc_state_counts','macro_tpr','complexity']:
                self.assertEqual(a[key],b[key])
            if 'CONTROLLED_SET_NORMAL_BUDGET' in a['constraint_reasons']:
                self.assertIn('CONTROLLED_SET_NORMAL_BUDGET',b['constraint_reasons'])
            if 'MTC_SET_DECISION_COVERAGE_BELOW_90_PERCENT' in a['constraint_reasons']:
                self.assertIn('MTC_SET_DECISION_COVERAGE_BELOW_90_PERCENT',b['constraint_reasons'])
        uncapped.mtc_budget=31
        with self.assertRaises(RuntimeError):uncapped.score(())
        self.assertEqual(capped.mtc_budget,31)
    def test_own_sparse_initialization_rejected_before_fit(self):
        p=engine.prepare(*self.args,scheme='A_NO_MEMORY_REL',**self.kw)
        with self.assertRaises(PermissionError):engine.fit(p,stage='RETENTION',initial_model=self.model,initial_training={})
    def test_empty_failed_identity_not_false(self):
        base=self.model
        for status in ['EMPTY_MODEL','FAILED']:
            model=engine.AppModel(base.method_id,status,(),(),
                dict(base.binding,experiment_id=engine.VERSION,scheme='A_NO_MEMORY_REL'),
                dict(base.view,kind='APP_COMPONENT_ABLATION'),dict(base.fit,adapter_version=engine.VERSION),encoder=base.encoder)
            pred=engine.predict_current(model,'test',{})
            self.assertEqual(pred['decision'],status);self.assertIsNone(pred['logical_state'])
    def test_web_only_current_raw_isolation(self):
        members=[r['value'] for r in data.records(data.HERE/'results/members.jsonl')]
        for cohort in ['controlled','memory','timezone','screen','paired60']:
            m=next(x for x in members if x['cohort']==cohort);ref=m['raw_reference'];raw=data.raw_at(ref);sid=raw['session_id'];v=raw['canonical_received_payload']['collection_manifest']['collector_version_code']
            before=data.adapt_raw(raw,sid,ref,v,'A_APP_WEB_ONLY')['raw']
            for modification in ['delete','corrupt']:
                changed=deepcopy(raw);p=changed['canonical_received_payload']
                for root in ['android_native_data','webview_data']:
                    if modification=='delete':p.pop(root,None)
                    else:p[root]='invalid ignored layer'
                p['collection_status']['fields']={k:x for k,x in p['collection_status']['fields'].items() if k.startswith('web_data.')}
                p.update(browser={'web_data':{'timezone_offset':-99}},label=1,phase='attack',target=42,future_post={'value':123})
                after=data.adapt_raw(changed,sid,ref,v,'A_APP_WEB_ONLY')['raw']
                self.assertEqual(before,after)
    def test_unselected_missing_does_not_fail_full_predictor(self):
        row=deepcopy(next(iter(self.args[1].values())))
        original=data.full_engine.predict_current(self.model,'test',row)
        used={a.atom_id for a in self.model.atoms}
        required=set(self.model.encoder['fixed_atoms'])&used
        required|={k for k,v in self.model.encoder['numeric'].items() if used&set(v['atom_ids'])}
        required|={a.atom_id for a in data.cand.registered_atoms()}&used
        for k in set(row)-required:row.pop(k)
        self.assertEqual(original,data.full_engine.predict_current(self.model,'test',row))
    def test_tree_weights_states_and_positive_probability(self):
        w=tree.weights(self.prepared);c=self.prepared.common
        self.assertEqual(sum(w[s] for s in c.mtc_train_ids),Fraction(1,4))
        self.assertEqual(sum(w[s] for s in c.ids if c.metadata[s]['phase']!='attack'),Fraction(1,4))
        configs=set(c.metadata[s]['config_id'] for s in c.ids)
        for cfg in configs:self.assertEqual(sum(w[s] for s in c.ids if c.metadata[s]['phase']=='attack' and c.metadata[s]['config_id']==cfg),Fraction(1,28))
        v,states,e=tree.vector({'a':data.cell('T','test'),'b':data.cell('U','missing')},['a','b'])
        self.assertEqual(v,[1,0,0,0,0,1]);self.assertIsNone(e)
        self.assertEqual(tree.vector({'a':data.cell('U','missing')},['a'])[2],'NO_VALID_MEASUREMENT')
        m={'children_left':[-1],'value':[[[.7,.3]]],'positive_class_index':0}
        self.assertEqual(tree.traverse(m,[0])[0],.7)
    def test_physical_lines_bad_json_duplicate_missing(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'raw.jsonl';p.write_bytes(b'{"session_id":"a"}\n\nnot-json\n{"session_id":"b"}\n')
            r=data.io.read_jsonl(p)
            self.assertEqual([x['line'] for x in r.records],[1,4]);self.assertEqual([e['line'] for e in r.errors],[2,3])
            self.assertEqual(data.raw_at(str(p)+':4','b')['session_id'],'b')
            with self.assertRaises(data.io.EvidenceError):data.raw_at(str(p)+':3')
            with self.assertRaises(data.io.EvidenceError):data.records(p)
            with self.assertRaises(ValueError):data.unique([{'sample_id':'x'},{'sample_id':'x'}])
    def test_specialists_and_paired_identity_denominators(self):
        ms=[r['value'] for r in data.records(data.HERE/'results/members.jsonl')]
        counts=data.Counter((m['cohort'],m['identity']) for m in ms)
        for key,n in [(('memory','NORMAL'),48),(('memory','EFFECTIVE_INTERVENTION'),18),(('memory','NO_OBSERVABLE_EFFECT'),6),
                      (('timezone','NORMAL'),30),(('timezone','EFFECTIVE_INTERVENTION'),6),(('screen','NORMAL'),66),(('screen','EFFECTIVE_INTERVENTION'),6),
                      (('paired60','NORMAL'),46),(('paired60','EFFECTIVE_INTERVENTION'),14)]:self.assertEqual(counts[key],n)
        train=set(self.f['train_ids'])|set(self.s['mtc_normal_train_ids'])
        self.assertFalse(train&{m['sample_id'] for m in ms if m['cohort'] in ('memory','timezone','screen','paired60')})

    def test_selective_mtc_reader_retains_corrupt_positions(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'paired_244.jsonl'
            p.write_bytes(b'{"sample_id":"a","dataset_view":"paired_244"}\n\xff\n{broken\n{"sample_id":"d","dataset_view":"paired_244"}\n')
            index={k:{'source_view':'paired_244','source_line':n} for n,k in enumerate(['a','b','c','d','e'],1)}
            rows,issues=data.selected_mtc(index,list(index),td)
            self.assertEqual(set(rows),{'a','d'});self.assertEqual(set(issues),{'b','c','e'})
            self.assertIn(':2:',issues['b']);self.assertIn(':3:',issues['c'])
            # Invalid evaluation bytes are not even deserialized for a training read.
            rows,issues=data.selected_mtc(index,['a'],td)
            self.assertEqual(set(rows),{'a'});self.assertFalse(issues)
    def test_mtc_projection_ignores_browser_and_native_measurements_for_web(self):
        s=data.settings();idx=data.prior.registry(s);ids=s['mtc_normal_train_ids'][:1]
        obs,issues=data.selected_mtc(idx,ids,data.ROOT/s['mtc_snapshot']);self.assertFalse(issues)
        sid=ids[0];o=obs[sid];before=data.base.adapt_mtc(o)['raw']
        after=deepcopy(o)
        for section in ['features','field_status','field_quality']:
            after[section]={k:v for k,v in after[section].items() if k.startswith('app.web_data.')}
        after['browser']='malformed ignored Browser';after['phase']='attack';after['future_post']={'label':0}
        self.assertEqual(before,data.base.adapt_mtc(after)['raw'])
    def test_current_timezone_zero_negative_one_and_memory_default(self):
        m=next(r['value'] for r in data.records(data.HERE/'results/members.jsonl') if r['value']['cohort']=='timezone')
        ref=m['raw_reference'];raw=deepcopy(data.raw_at(ref));sid=raw['session_id']
        for value in [0,-1]:
            raw['canonical_received_payload']['web_data']['execution_layer']['timezone_offset']=value
            x=data.adapt_raw(raw,sid,ref,14,'A_APP_WEB_ONLY')['raw']['UNFITTED_CONTROL:app.web_data.execution_layer.timezone_offset']
            self.assertTrue(x['available']);self.assertEqual(x['value'],value)
        raw['canonical_received_payload']['web_data']['navigator_layer']['device_memory']=0
        x=data.adapt_raw(raw,sid,ref,14,'A_APP_WEB_ONLY')['raw']['UNFITTED_CONTROL:app.web_data.navigator_layer.device_memory']
        self.assertFalse(x['available'])
    def test_new_entry_full_selected_prediction_regression(self):
        m=self.model
        shared=engine.AppModel(m.method_id,m.status,m.clauses,m.atoms,
            dict(m.binding,experiment_id=engine.VERSION,scheme='A_NO_MTC_CAP'),
            dict(m.view,kind='APP_COMPONENT_ABLATION'),dict(m.fit,adapter_version=engine.VERSION),encoder=m.encoder)
        raw=next(iter(self.args[1].values()))
        a=data.full_engine.predict_current(m,'test',raw);b=engine.predict_current(shared,'test',raw)
        for key in ['decision','logical_state','clause_explanations','failure_reason']:self.assertEqual(a[key],b[key])
    def test_saved_summary_cannot_predict_or_fit(self):
        import contextlib,io as stdio
        import summarize
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            for name in ['members.jsonl','full_predictions.jsonl.gz','predictions.jsonl.gz']:
                (out/name).write_bytes((data.HERE/'results'/name).read_bytes())
            with patch.object(engine,'fit',side_effect=AssertionError('fit in summary')),patch.object(engine,'predict_current',side_effect=AssertionError('predict in summary')),patch.object(tree,'fit',side_effect=AssertionError('tree fit in summary')),patch.object(tree,'predict',side_effect=AssertionError('tree predict in summary')),patch.object(data.full_engine,'predict_current',side_effect=AssertionError('full predict in summary')),contextlib.redirect_stdout(stdio.StringIO()):
                summarize.summarize(out)
            expected=json.loads((data.HERE/'results/summary/SUMMARY.json').read_text())
            self.assertEqual(expected,json.loads((out/'summary/SUMMARY.json').read_text()))

if __name__=='__main__':unittest.main()
