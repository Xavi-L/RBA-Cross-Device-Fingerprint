"""Semantic counterexamples and train-only relation encoders, synthetic only."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hybridguard_agent.research.rule_learning.contracts import state
from hybridguard_agent.research.rule_learning.fold_data import TrainQuantiles
from hybridguard_agent.research.rule_learning_v2 import relations as r, b_engine
from hybridguard_agent.research.rule_learning_v2.adapter import TrainAccess
from hybridguard_agent.tests.test_rule_learning_v2 import toy


def payload(**overrides):
    features={r.N_MEM:2.4145,r.W_MEM:2,r.N_LANG:'en-US',r.W_LANG:'en-US',r.W_LANGS:['en-US'],
              r.N_TZ:'GMT',r.N_OFFSET:0,r.W_OFFSET:0}
    features.update(overrides)
    return {'features':features,'field_status':{f:'observed' for f in features},
            'field_quality':{f:'observed_value' for f in features}}


class RelationTests(unittest.TestCase):
    def test_memory_rounding_clamping_are_valid_scale_values_not_equality_conflicts(self):
        for native,web in [(2.4145,2),(6,8),(32,8)]:
            self.assertEqual(r.memory_ratio(native,web),web/native)
        self.assertIsNone(r.memory_ratio(0,2));self.assertIsNone(r.memory_ratio(True,2))
        self.assertIsNone(r.memory_ratio(2,float('nan')));self.assertIsNone(r.memory_ratio(1e-320,1e300))

    def test_language_region_case_order_fallback_and_scripts(self):
        spec={'relation_families':['language'],'matched_single_features':True}
        out=r.raw_relations(payload(**{r.N_LANG:'EN-gb',r.W_LANG:'en-US',r.W_LANGS:['fr-FR','en','en-US']}),spec)
        self.assertEqual([state(out[n]) for n in (r.LANG_PRIMARY,r.LANG_LIST,r.WEB_LIST)],['F','F','F'])
        self.assertEqual(r.primary_language('zh-Hans-CN'),r.primary_language('zh-Hant-TW'))

    def test_legitimate_per_application_language_mismatch_is_not_attack_truth(self):
        spec={'relation_families':['language'],'matched_single_features':True}
        out=r.raw_relations(payload(**{r.N_LANG:'en-US',r.W_LANG:'fr-FR',r.W_LANGS:['fr-FR','fr']}),spec)
        self.assertEqual(state(out[r.LANG_LIST]),'T')  # A legitimate counterexample to automatic attack interpretation.
        self.assertEqual(state(out[r.WEB_LIST]),'F')

    def test_unsupported_missing_or_low_quality_language_is_U(self):
        for value in ('und','x-private','i-klingon','en_US','zh-cmn-Hans','en-US-u-ca-gregory','iw-IL'):
            self.assertIsNone(r.primary_language(value))
        self.assertIsNone(r.language_members([]));self.assertIsNone(r.language_members(['en',3]))
        p=payload();p['field_quality'][r.N_LANG]='unverified'
        self.assertEqual(state(r.raw_relations(p,{'relation_families':['language']})[r.LANG_PRIMARY]),'U')

    def test_timezone_alias_sign_units_DST_and_bad_native_pair(self):
        for zone in ('GMT','UTC','+00:00','Etc/UTC','Etc/GMT'):
            self.assertFalse(r.timezone_difference(zone,0,0))
        self.assertFalse(r.timezone_difference('GMT+08:00',480,-480))
        self.assertFalse(r.timezone_difference('Etc/GMT+7',-420,420))
        self.assertTrue(r.timezone_difference('UTC',0,420))
        self.assertIsNone(r.timezone_difference('America/New_York',-300,240))
        self.assertIsNone(r.timezone_difference('America/Los_Angeles',-480,420))
        self.assertIsNone(r.timezone_difference('GMT+08:00',0,-480))
        self.assertIsNone(r.timezone_difference('invalid',0,0))

    def test_second_source_values_change_each_function_not_just_validity(self):
        self.assertNotEqual(r.memory_ratio(2,8),r.memory_ratio(32,8))
        spec={'relation_families':['language','timezone']}
        p=payload(**{r.W_LANG:'fr-FR',r.W_LANGS:['fr'],r.W_OFFSET:420})
        before=r.raw_relations(p,spec)
        p['features'][r.N_LANG]='fr-FR';p['features'][r.N_TZ]='GMT-07:00';p['features'][r.N_OFFSET]=-420
        after=r.raw_relations(p,spec)
        for name in (r.LANG_PRIMARY,r.LANG_LIST,r.TZ):
            self.assertEqual((state(before[name]),state(after[name])),('T','F'))

    def test_web_matched_control_uses_identical_parser_and_no_native_field(self):
        spec={'relation_families':[],'matched_single_features':True}
        self.assertEqual(set(r.relation_fields(spec)),{r.W_LANG,r.W_LANGS})
        p=payload(**{r.W_LANGS:['fr-FR','fr']})
        left=r.raw_relations(p,spec)
        p['features'][r.N_LANG]='ar-SA';p['features'][r.N_MEM]=999
        self.assertEqual(r.raw_relations(p,spec),left)
        self.assertEqual(set(left),{r.WEB_LIST})

    def test_ratio_train_only_freeze_and_model_roundtrip_prediction_does_not_fit(self):
        _,defs,job,rows,meta=toy()
        access=TrainAccess(job,rows,meta)
        inputs={i:payload(**{r.N_MEM:2,r.W_MEM:4 if meta[i]['phase']=='attack' else 2}) for i in job['train_ids']}
        spec={'representation':'JX-fixture','base_representation':'S_FLAT','method':'R_KEEP_V1',
              'relation_families':['memory','language','timezone'],'matched_single_features':True}
        binding={'study_version':'discriminative-rule-learning-v2-20260925','phase':'V2-B','fold_id':job['fold_id'],'operating_point':'OP05'}
        model,training=b_engine.fit_b(access,defs,spec,binding,inputs)
        e=model.encoder['v2_relations']
        self.assertEqual(e['numeric'][r.RATIO]['thresholds'],[1.,2.])
        self.assertEqual(e['train_ids'],job['train_ids'])
        with self.assertRaisesRegex(PermissionError,'EXACT_OWN_TRAIN'):
            r.encode_relations(access,dict(inputs,**{'outer':payload()}),spec)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model.json';b_engine.save_model(model,path);loaded=b_engine.load_model(path)
            current=next(iter(rows.values()));outside=payload(**{r.W_MEM:1e6})
            with patch.object(TrainQuantiles,'fit',side_effect=AssertionError('Prediction must not fit')):
                before=b_engine.predict_current(model,'outside',current,outside)
                after=b_engine.predict_current(loaded,'outside',current,outside)
            self.assertEqual(before,after);self.assertEqual(loaded.encoder['v2_relations'],e)

    def test_frozen_relation_encoder_reuse_performs_no_internal_fit(self):
        _,_,job,rows,meta=toy();access=TrainAccess(job,rows,meta)
        inputs={i:payload() for i in job['train_ids']};spec={'relation_families':['memory','language']}
        rows1,atoms1,encoder=r.encode_relations(access,inputs,spec)
        with patch.object(TrainQuantiles,'fit',side_effect=AssertionError('No hidden extra fit')):
            rows2,atoms2,e2=r.encode_relations(access,inputs,spec,encoder)
        self.assertEqual((rows1,atoms1,encoder),(rows2,atoms2,e2))


if __name__=='__main__': unittest.main()
