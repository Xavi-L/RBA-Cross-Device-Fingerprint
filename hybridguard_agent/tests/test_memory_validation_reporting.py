import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hybridguard_agent.tests.test_memory_relation_validation import bound, ROOT
from hybridguard_agent.research import memory_relation_validation as v


spec=importlib.util.spec_from_file_location('memory_report_test',ROOT/'deliverables/memory_relation_validation_v1/evaluate.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


class ReportingTests(unittest.TestCase):
    def test_unknown_and_failures_remain_in_full_denominator(self):
        data=[e.record('normal-valid',bound(8,12),normal_basis={'supported':True}),
              e.record('default',bound(0),normal_basis={'supported':True}),
              e.record('broken',{'status':'FAILED'},normal_basis={'supported':True})]
        c=e.comparison(data)
        self.assertEqual(c['planned_n'],3)
        self.assertEqual(c['common_evaluable']['n'],1)
        self.assertEqual(c['conditions']['R_REL']['F'],1)
        self.assertEqual(c['conditions']['R_REL']['U'],1)
        self.assertEqual(c['conditions']['R_REL']['FAILED'],1)
        self.assertEqual(c['normal_basis_supported']['n'],3)

    def test_common_subset_does_not_remove_relation_only_or_unknown_records(self):
        data=[e.record('cross',bound(4,1.95)), e.record('both',bound(16,2)),
              e.record('native-unavailable',bound(16,0))]
        c=e.comparison(data)
        self.assertEqual(c['conditions']['R_WEB8']['T'],2)
        self.assertEqual(c['common_evaluable']['n'],2)
        self.assertEqual(c['only_relation_triggered_common_evaluable'],1)
        self.assertEqual(c['both_triggered'],1)
        self.assertEqual(c['joint_states']['U/T'],1)

    def test_observed_normal_counterexample_not_relabeled_or_hidden(self):
        r=e.record('normal-counterexample',bound(4,2),normal_basis={'supported':True},label='unlabeled')
        before=copy.deepcopy(r);c=e.comparison([r])
        self.assertEqual(c['conditions']['R_REL']['T'],1)
        self.assertEqual(c['normal_basis_supported']['conditions']['R_REL']['T'],1)
        self.assertEqual(r,before)

    def test_saved_summary_rejects_missing_planned_positions(self):
        settings=e.read(ROOT/'deliverables/memory_relation_validation_v1/SETTINGS.json')
        row={'environment':'api29_swiftshader','target_gib':2,'round':1,'phase':'clean_pre'}
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);(out/'SETTINGS.json').write_text(json.dumps(settings))
            with patch.object(e,'rows',side_effect=lambda p:[row] if str(p).endswith('new_batch.jsonl.gz') else []):
                with self.assertRaisesRegex(ValueError,'ALL_PLANNED_POSITIONS'):
                    e.summary(out)

    def test_unavailable_environments_remain_failed_not_unconfounded_successes(self):
        settings=e.read(ROOT/'deliverables/memory_relation_validation_v1/SETTINGS.json')
        data=[]
        for env in settings['environments']:
            for w in settings['targets_gib']:
                for number in range(1,3):
                    for phase in settings['phases']:
                        row=e.record(f"missing-{env['environment_group_id']}-{w}-{number}-{phase}",{'status':'FAILED'},
                            environment=env['environment_group_id'],target_gib=w,round=number,phase=phase,
                            operation={'status':'NOT_EXECUTED'})
                        row['models']=[{**entry,'decision':'FAILED','rules':[],'triggered_rules':[]} for entry in settings['saved_models']]
                        data.append(row)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);(out/'SETTINGS.json').write_text(json.dumps(settings))
            with patch.object(e,'rows',side_effect=lambda p:data if str(p).endswith('new_batch.jsonl.gz') else []):
                summary=e.summary(out)
            self.assertEqual(summary['new_batch']['all']['conditions']['R_REL']['FAILED'],72)
            self.assertEqual(summary['new_batch']['effect_counts']['confound_status'],{'NOT_EVALUABLE':24})
            self.assertEqual(summary['new_batch']['observable_unconfounded']['planned_n'],0)
            spec=importlib.util.spec_from_file_location('memory_failed_report_test',ROOT/'deliverables/memory_relation_validation_v1/report.py')
            report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
            report.render(out)
            self.assertIn('NOT_EVALUABLE',(out/'REPORT.md').read_text())

    def test_six_saved_models_equal_previous_predictions_through_new_batch_adapter(self):
        settings=e.read(ROOT/'deliverables/memory_relation_validation_v1/SETTINGS.json')
        models=e.fixed_models(settings)
        self.assertEqual(len(models),6)
        # A real controlled current-session record with a saved reference score.
        old=e.rows(ROOT/'deliverables/mtc_relation_extension_v1/predictions.jsonl.gz')
        saved=next(r for r in old if r['dataset']=='controlled' and r['scheme']=='B_REL'
                   and r.get('configuration_id')=='w9-rule-boundary-cdp-resource-pair-v1' and r.get('stage')=='attack')
        sid=saved['sample_id'].removeprefix('webgl1fresh-')
        reference=e.read(ROOT/'deliverables/webgl1_fresh_comparison_v1/prepared/evaluation'/(saved['sample_id']+'.json'))
        archive=ROOT/reference['source_ref']/'backend/raw_expanded_payloads.jsonl'
        raw=next(r for r in e.rows(archive) if r['session_id']==sid)
        env=raw['canonical_received_payload']['collection_manifest']['device_manifest_id']
        with (patch('hybridguard_agent.research.mtc_constrained_reselection.fit_sparse',side_effect=AssertionError('No training')),
              patch('hybridguard_agent.research.mtc_constrained_reselection.fit_retention',side_effect=AssertionError('No training')),
              patch('hybridguard_agent.research.mtc_relation_selection.fit',side_effect=AssertionError('No training'))):
            b,a=v.adapt_memory_batch(raw,session_id=sid,source_reference='real-record-new-adapter-test',environment_id=env)
            predicted=e.models_current(models,'memoryonly-'+sid,a,b)
        for m in predicted:
            if m['fold_id']==saved['fold_id']:
                previous=next(r for r in old if r['sample_id']==saved['sample_id'] and r['scheme']==m['scheme'])
                self.assertEqual(m['decision'],previous['decision'])
                self.assertEqual([r['state'] for r in m['rules']],[r['state'] for r in previous['rules']])


if __name__=='__main__':unittest.main()
