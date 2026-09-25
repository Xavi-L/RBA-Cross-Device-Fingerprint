"""C entry scope and parity on synthetic records only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hybridguard_agent.tests.test_rule_learning_v2 import toy
from hybridguard_agent.research.rule_learning_v2 import b_engine,c_engine,c_experiment,c_probes
from hybridguard_agent.research.rule_learning_v2.adapter import TrainAccess
from hybridguard_agent.research.rule_learning_v2.common import digest,write
from hybridguard_agent.research.rule_learning_v2.retention import GROUP_VERSION


def fixture():
    _,defs,job,rows,meta=toy();job.update(representation='W0',base_representation='W0',method='GREEDY_OR')
    b={'study_version':'discriminative-rule-learning-v2-20260925','phase':'V2-C','authorization_id':c_engine.AUTH,
       'fold_id':job['fold_id'],'operating_point':'OP05','candidate_version':GROUP_VERSION,
       'evaluation_role':'SYNTHETIC_ENGINEERING_FIXTURE','train_membership_digest':digest(job['train_ids'])}
    return defs,job,rows,meta,b


class CEngineTests(unittest.TestCase):
    def test_C_identity_preserves_B_greedy_math_on_same_synthetic_train(self):
        defs,job,rows,meta,b=fixture()
        c,_=c_engine.fit_c(TrainAccess(job,rows,meta),defs,job,b)
        old,_=b_engine.fit_b(TrainAccess(job,rows,meta),defs,job,dict(b,phase='V2-B'))
        self.assertEqual(c.clauses,old.clauses);self.assertEqual(c.encoder,old.encoder)
        self.assertEqual(c.fit['training_result'],old.fit['training_result'])
        self.assertTrue(c.model_id.startswith('v2c-'));self.assertEqual(c.binding['phase'],'V2-C')

    def test_matching_C_initialization_no_hidden_encoder_or_sparse_refit(self):
        defs,job,rows,meta,b=fixture()
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);initial,training=c_engine.fit_c(TrainAccess(job,rows,meta),defs,job,b)
            c_engine.save_model(initial,d/'model.json');write(d/'training.json',training)
            spec=dict(job,method='R_KEEP_V1',initial_model_ref=str(d/'model.json'))
            with patch.object(b_engine,'encode_train',side_effect=AssertionError('hidden encoder fit')),patch.object(b_engine,'greedy',side_effect=AssertionError('hidden sparse fit')):
                model,trace=c_engine.fit_c(TrainAccess(job,rows,meta),defs,spec,b)
            c_engine.save_model(model,d/'retained.json');loaded=c_engine.load_model(d/'retained.json')
            for i,row in rows.items():self.assertEqual(c_engine.predict_current(model,i,row),c_engine.predict_current(loaded,i,row))
            self.assertFalse(trace['initialization']['threshold_refit'])
            wrong=dict(job,fold_id='different-fold')
            with self.assertRaisesRegex(ValueError,'FOLD_MISMATCH'):
                c_engine.fit_c(TrainAccess(wrong,rows,meta),defs,spec,b)

    def test_C_rejects_new_method_relation_or_missing_charged_initialization(self):
        defs,job,rows,meta,b=fixture()
        for change in ({'method':'IP'},{'representation':'JX'},{'method':'R_KEEP_V1'},{'relation_families':['memory']}):
            with self.subTest(change=change),self.assertRaises(PermissionError):
                c_engine.fit_c(TrainAccess(job,rows,meta),defs,dict(job,**change),b)

    def test_stage_closed_and_single_use_worker_claim_reject_before_fit(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);write(p/'linked_budget_ledger.json',{'state':'CLOSED_STOP_FOR_USER_REVIEW'});write(p/'C_CONTRACT.json',{})
            with patch.object(c_experiment,'C_OUT',p),self.assertRaisesRegex(PermissionError,'C_CLOSED'):
                c_experiment.validate(c_engine.AUTH)
            write(p/'worker_claim.json',{'previous':True})
            with self.assertRaises(FileExistsError):c_experiment.execute({}, {}, p)

    def test_raw_probe_conversion_preserves_domain_and_failure_semantics(self):
        cases={x['id']:x for x in c_probes.specification()['cases']}
        baseline=c_probes.measure(c_probes.payload_for(cases['baseline_partial_android']))
        self.assertEqual(baseline['CAT:NW-006']['state'],'F')
        name='UNFITTED_CONTROL:app.web_data.navigator_layer.device_memory'
        missing=c_probes.measure(c_probes.payload_for(cases['missing_memory']))
        broken=c_probes.measure(c_probes.payload_for(cases['invalid_measurement_status']))
        self.assertFalse(missing[name]['available']);self.assertEqual(missing[name]['evaluation_status'],'OK')
        self.assertEqual(broken[name]['evaluation_status'],'FAILED')
        multi=c_probes.measure(c_probes.payload_for(cases['multiple_languages']))
        self.assertEqual(multi['UNFITTED_CONTROL:app.web_data.navigator_layer.languages']['value'],2)


if __name__=='__main__':unittest.main()
