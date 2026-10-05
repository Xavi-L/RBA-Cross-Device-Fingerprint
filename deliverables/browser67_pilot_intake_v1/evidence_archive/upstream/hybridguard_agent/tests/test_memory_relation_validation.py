import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from hybridguard_agent.research import memory_relation_validation as v
from hybridguard_agent.research import mtc_reselection_candidates as old
from hybridguard_agent.research import mtc_resource_relations as rel
from hybridguard_agent.research import mtc_relation_sources as sources
from hybridguard_agent.research.rule_learning.contracts import logic, negate


ROOT=Path(__file__).resolve().parents[2]


def bound(web=8, native=2):
    return {'status':'OK','features':{v.WEB:web,v.NATIVE:native},
        'field_status':{v.WEB:'observed',v.NATIVE:'observed'},
        'field_quality':{v.WEB:'observed_value',v.NATIVE:'observed_value'},
        'source_binding':{'binding_valid':True,'same_app_record':True,'app_session_id':'one'}}


def observation(web):
    b=bound(web)
    return {'operands':v.operand_details(b),'conditions':v.compare(b)}


class FixedConditionTests(unittest.TestCase):
    def test_web_threshold_strict_boundary(self):
        for w,s in [(2,'F'),(4,'F'),(8,'F'),(8.01,'T'),(16,'T')]:
            self.assertEqual(v.state(v.web8(bound(w))),s)

    def test_invalid_or_missing_stays_unknown(self):
        for w in (None,False,True,'16',[],{},0,-1,float('inf'),float('-inf'),float('nan')):
            self.assertEqual(v.state(v.web8(bound(w))),'U',repr(w))
        b=bound();del b['features'][v.WEB]
        self.assertEqual(v.state(v.web8(b)),'U')
        b=bound(16);b['field_quality'][v.WEB]='ambiguous_sentinel'
        self.assertEqual(v.state(v.web8(b)),'U')

    def test_web_does_not_read_native_source_or_labels(self):
        b=bound(16);expected=v.web8(b)
        del b['features'][v.NATIVE];del b['source_binding']
        b.update(label='normal',phase='post',target_gib=2,model='example',source='other')
        self.assertEqual(v.web8(b),expected)
        self.assertEqual(v.web8({'features':{v.WEB:16},'field_status':{v.WEB:'observed'},
                                 'field_quality':{v.WEB:'observed_value'}}),expected)

    def test_relation_unchanged_and_extra_discrimination(self):
        for n,w,rs,ws in [(1.95,4,'T','F'),(1.95,8,'T','F'),(10.9,8,'F','F'),
                          (2.4,4,'F','F'),(8,4,'F','F'),(2,16,'T','T'),(0,8,'U','F')]:
            b=bound(w,n);r=v.compare(b)
            self.assertEqual(r['R_REL']['state'],rs)
            self.assertEqual(r['R_WEB8']['state'],ws)
            self.assertEqual({k:x for k,x in r['R_REL'].items() if k!='state'},rel.evaluate(b)[rel.MEMORY_ID])

    def test_failure_not_unknown(self):
        r=v.compare({'status':'FAILED','errors':['unreadable']})
        self.assertEqual({c['state'] for c in r.values()},{'FAILED'})

    def test_or_and_negation_do_not_hide_unknown(self):
        self.assertEqual(logic(('T','U'),'OR'),'T')
        self.assertEqual(logic(('F','U'),'OR'),'U')
        self.assertEqual(negate('U'),'U')

    def test_effect_is_independent_of_alarm_and_noop_not_success(self):
        op={'cdp_status':'COMPLETED','target_gib':2}
        r=v.intervention_effect(observation(2),observation(2),observation(2),op)
        self.assertEqual(r['effect'],'NO_OBSERVABLE_EFFECT');self.assertFalse(r['effect_positive'])
        op['target_gib']=4
        active=observation(4);active['conditions']={'R_REL':{'state':'F'},'R_WEB8':{'state':'FAILED'}}
        r=v.intervention_effect(observation(2),active,observation(2),op)
        self.assertTrue(r['effect_positive']);self.assertEqual(r['recovery'],'RESTORED')

    def test_operation_effect_recovery_failures_separate(self):
        op={'cdp_status':'FAILED','target_gib':8}
        r=v.intervention_effect(observation(2),observation(8),observation(4),op)
        self.assertEqual((r['execution'],r['effect'],r['recovery']),
                         ('OPERATION_FAILED','OBSERVABLE_TARGET_CHANGE','RECOVERY_FAILED'))
        self.assertFalse(r['effect_positive'])
        r=v.intervention_effect(observation(2),None,None,None)
        self.assertEqual((r['execution'],r['effect'],r['recovery']),
                         ('NOT_EXECUTED','MISSING_OBSERVATION','MISSING_OBSERVATION'))
        r=v.intervention_effect(None,None,None,{'status':'FAILED','cdp_status':'NOT_EXECUTED','target_gib':4})
        self.assertTrue(r['position_attempted']);self.assertFalse(r['cdp_attempted'])


class RealSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/'deliverables/webgl1_fresh_comparison_v1/runs/api29_swiftshader/backend/raw_expanded_payloads.jsonl'
        with path.open() as stream:cls.raw=json.loads(next(stream))
        cls.sid=cls.raw['session_id']
        cls.env=cls.raw['canonical_received_payload']['collection_manifest']['device_manifest_id']
        cls.kw={'session_id':cls.sid,'source_reference':str(path.relative_to(ROOT))+':1','environment_id':cls.env}

    def test_real_saved_values_and_states(self):
        b=v.bind_memory_batch(self.raw,**self.kw)
        self.assertEqual(b['status'],'OK')
        p=self.raw['canonical_received_payload']
        self.assertEqual(b['features'][v.NATIVE],p['android_native_data']['memory_layer']['total_memory_gb'])
        self.assertEqual(b['features'][v.WEB],p['web_data']['navigator_layer']['device_memory'])
        self.assertEqual({x['state'] for x in v.compare(b).values()},{'F'})

    def test_same_session_binding_and_version(self):
        for change in ('envelope','payload','field_session','version','environment'):
            r=copy.deepcopy(self.raw);p=r['canonical_received_payload']
            if change=='envelope':r['session_id']='borrowed'
            elif change=='payload':p['session_id']='borrowed'
            elif change=='field_session':p['field_session_ids']={v.NATIVE:'borrowed'}
            elif change=='version':p['collection_manifest']['collector_version_code']=11
            else:p['collection_manifest']['device_manifest_id']='another'
            self.assertEqual(v.bind_memory_batch(r,**self.kw)['status'],'FAILED',change)
            with self.assertRaises(ValueError):v.adapt_memory_batch(r,**self.kw)

    def test_new_identity_does_not_bypass_old_entry(self):
        ref={'opaque_id':'memoryonly-'+self.sid,'session_id':self.sid,'observation_mode':'raw_observation_v1'}
        old_bound=sources.bind_controlled_record(ref['opaque_id'],ref,self.raw)
        self.assertEqual(old_bound['status'],'FAILED')

    def test_new_adapter_preserves_original_50_and_freezes_models(self):
        module,contract=v.compiler()
        original=old.adapt_controlled(module.compile_record(self.raw['canonical_received_payload'],
            expected_session_id=self.sid,source_reference=self.kw['source_reference'],measurement_contract=contract))
        with (patch('hybridguard_agent.research.mtc_constrained_reselection.prepare_fold',side_effect=AssertionError('No training')),
              patch('hybridguard_agent.research.mtc_relation_selection.fit',side_effect=AssertionError('No training'))):
            b,a=v.adapt_memory_batch(self.raw,**self.kw)
        self.assertEqual({k:a['raw'][k] for k in original['raw']},original['raw'])
        self.assertEqual(b['source_binding']['sample_id'],'memoryonly-'+self.sid)

    def test_phase_target_model_and_source_never_change_prediction_inputs(self):
        before=copy.deepcopy(self.raw)
        _,first=v.adapt_memory_batch(self.raw,**self.kw)
        r=copy.deepcopy(self.raw);p=r['canonical_received_payload']
        p.update(label='attack',phase='clean_post',target_gib=16)
        p['collection_manifest'].update(runtime_context='other',collection_round=99,model='other')
        _,second=v.adapt_memory_batch(r,**{**self.kw,'source_reference':'another-reference'})
        self.assertEqual(first['raw'],second['raw'])
        self.assertEqual(self.raw,before)

    def test_fixed_plan_exactly_72_no_hidden_field_override(self):
        spec=importlib.util.spec_from_file_location('memory_collect_test',ROOT/'deliverables/memory_relation_validation_v1/collect.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        settings=json.loads((ROOT/'deliverables/memory_relation_validation_v1/SETTINGS.json').read_text())
        plan=m.positions(settings)
        self.assertEqual(len(plan)*len(settings['environments']),72)
        self.assertEqual({p['target_gib'] for p in plan},{2,4,8,16})
        self.assertEqual(len({p['step_id'] for p in plan}),24)
        self.assertEqual(settings['model_training_calls'],0)
        self.assertEqual(len(settings['saved_models']),6)


if __name__=='__main__':unittest.main()
