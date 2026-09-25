"""Integrity shapes and bindings; all corruption is confined to synthetic files."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from hybridguard_agent.tests import test_rule_learning_v2_b_summary as summary_tests
from hybridguard_agent.research.rule_learning_v2.adapter import V2Model, load_model, predict_current
from hybridguard_agent.research.rule_learning_v2.common import read, lines
from hybridguard_agent.research.rule_learning_v2.pilot import preserve_failed_attempt
from hybridguard_agent.research.rule_learning_v2.trial_summary import inspect_attempt


class IntegrityTests(unittest.TestCase):
    fixture = summary_tests.SummaryTests.fixture
    assert_failed = summary_tests.SummaryTests.assert_failed

    def test_null_and_wrong_json_object_types(self):
        for name in ('model.json', 'training.json', 'receipt.json'):
            for value in (None, [], 'object', 17, True):
                with self.subTest(artifact=name, value=value), tempfile.TemporaryDirectory() as t:
                    d=Path(t);job,_,_=self.fixture(d)
                    (d/name).write_text(json.dumps(value))
                    result=self.assert_failed(d,job)
                    self.assertEqual(result['audit']['status'],'INTEGRITY_EXCEPTION')
                    self.assertTrue(result['audit']['issues'])

    def test_training_required_fields_and_types(self):
        for key in ('trace','candidate_manifest','atoms','access_operations'):
            for value in ('MISSING',None,{},'bad',7,[None]):
                with self.subTest(key=key,value=value), tempfile.TemporaryDirectory() as t:
                    d=Path(t);job,_,_=self.fixture(d);obj=read(d/'training.json')
                    if value=='MISSING':del obj[key]
                    else:obj[key]=value
                    (d/'training.json').write_text(json.dumps(obj))
                    self.assertEqual(self.assert_failed(d,job)['audit']['status'],'INTEGRITY_EXCEPTION')

    def test_receipt_required_fields_types_and_count(self):
        for key,value in [('state',None),('state','OK'),('model_id',None),('model_id',7),('model_id',''),('predictions',0),('predictions',True)]:
            with self.subTest(key=key,value=value), tempfile.TemporaryDirectory() as t:
                d=Path(t);job,_,_=self.fixture(d);obj=read(d/'receipt.json')
                if value is None:del obj[key]
                else:obj[key]=value
                (d/'receipt.json').write_text(json.dumps(obj))
                self.assertEqual(self.assert_failed(d,job)['audit']['status'],'INTEGRITY_EXCEPTION')

    def test_prediction_bindings_logic_and_required_fields(self):
        for key,value in [('model_id','other'),('fold_id','other'),('method_id','IP'),('model_status','EMPTY_MODEL'),('logical_state','T'),('atom_explanations',None)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as t:
                d=Path(t);job,_,pred=self.fixture(d);pred[0][key]=value
                (d/'predictions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in pred))
                self.assertEqual(self.assert_failed(d,job)['audit']['status'],'INTEGRITY_EXCEPTION')

    def test_train_fold_and_candidate_binding(self):
        for change in ('fold','train','candidate'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as t:
                d=Path(t);job,_,_=self.fixture(d)
                if change=='fold':job['fold_id']='wrong'
                elif change=='train':job['train_ids']=[]
                else:
                    obj=read(d/'training.json')
                    for row in obj['candidate_manifest']:row['eligible']=False
                    (d/'training.json').write_text(json.dumps(obj))
                self.assertEqual(self.assert_failed(d,job)['audit']['status'],'INTEGRITY_EXCEPTION')

    def test_legal_empty_and_failed_models_are_not_null_artifacts(self):
        for status in ('EMPTY_MODEL','FAILED'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as t:
                d=Path(t);job,_,_=self.fixture(d);original=load_model(d/'model.json')
                model=V2Model(replace(original.engine,status=status,clauses=(),atoms=(),fit=dict(original.fit,status=status)))
                (d/'model.json').write_text(json.dumps(model.to_dict()))
                (d/'receipt.json').write_text(json.dumps({'state':status,'model_id':model.model_id}))
                pred=[predict_current(model,i,{}) for i in job['outer_test_ids']]
                (d/'predictions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in pred))
                before={p.name:p.read_bytes() for p in d.iterdir()}
                result=inspect_attempt(d,job)
                self.assertEqual(result['audit']['issues'],[])
                self.assertEqual(result['audit']['status'],'OK' if status=='EMPTY_MODEL' else 'MODEL_FAILED')
                self.assertEqual({r['decision'] for r in result['predictions']},{status})
                self.assertEqual(before,{p.name:p.read_bytes() for p in d.iterdir()})

    def test_worker_failure_dominates_null_and_partial_outputs(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);job,_,_=self.fixture(d);preserve_failed_attempt(d,job,'synthetic crash')
            for name in ('training.json','receipt.json','model.json'):(d/name).write_text('null')
            result=self.assert_failed(d,job)
            self.assertEqual(result['audit']['status'],'WORKER_FAILED')


if __name__=='__main__':unittest.main()
