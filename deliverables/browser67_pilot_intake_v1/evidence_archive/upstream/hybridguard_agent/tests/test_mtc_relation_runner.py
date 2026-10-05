"""No evaluation before the six fixed relation fits have closed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[2]/'deliverables/mtc_relation_extension_v1/run_experiment.py'
SPEC = importlib.util.spec_from_file_location('relation_runner_test', PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RelationRunnerTests(unittest.TestCase):
    def test_six_complete_stages_required_before_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            new,parent = runner.config(out)
            models = [{'fold_id':f['fold_id'],'stage':s} for f in parent['folds'] for s in new['new_fit_stages']]
            runner.write(out/'models.json',{'models':models})
            runner.write(out/'EXECUTION.json',{'all_fits_closed':True,'actual_fit_calls':6})
            (out/'FIT_CALLS.jsonl').write_text('{}\n'*5)
            with self.assertRaises(PermissionError): runner.evaluation_ready(out)
            (out/'FIT_CALLS.jsonl').write_text('{}\n'*6)
            self.assertEqual(len(runner.evaluation_ready(out)[2]),6)
            models[0] = models[1]
            (out/'models.json').write_text(__import__('json').dumps({'models':models}))
            with self.assertRaises(PermissionError): runner.evaluation_ready(out)

    def test_only_prespecified_primary_members_and_no_parameter_search(self):
        new,parent=runner.config(PATH.parent)
        self.assertEqual(new['planned_fit_calls'],6)
        self.assertFalse(new['supplementary_replay'])
        self.assertEqual([len(parent['mtc_primary_ids'][k]) for k in new['primary_mtc_subsets']],[630,144,117])
        self.assertEqual(parent['mtc_normal_train_ids'],parent['mtc_primary_ids']['discovery'])
        self.assertEqual(new['old_encoder'],'controlled own-fold train quantiles; exact equality with saved B encoder required')
        self.assertEqual(new['relation_parameters'],'fixed semantic constants only; no learned tolerance')


if __name__ == '__main__': unittest.main()
