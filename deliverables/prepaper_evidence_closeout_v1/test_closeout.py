"""Focused invariants; extra selector calls are test-only and separately logged."""
import copy,unittest
from collections import Counter
from closeout_io import *
from bridges import original_selector as s
from execute_ablation import ablation_settings
from build_tables import aggregate

class Closeout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.members=rows(HERE/'results/members.jsonl');cls.inputs=index(rows(B2C/'results/inputs.jsonl'));cls.models=read(HERE/'results/models.json');cls.checks=read(HERE/'results/candidate_checks.json')

    def test_only_cap_changed(self):
        before=copy.deepcopy(s.SETTINGS);after=ablation_settings()
        self.assertEqual(after['normal_alarm_budgets']['b2b42'],34)
        after['normal_alarm_budgets']['b2b42']=1
        self.assertEqual(after,before);self.assertEqual(s.SETTINGS,before)

    def test_original_models_conditions_trees_and_sources_unchanged(self):
        freeze=read(HERE/'results/FREEZE.json')
        for name,sha in freeze['sources'].items():self.assertEqual(digest(ROOT/name),sha,name)
        self.assertEqual(digest(HERE/'PROTOCOL.md'),freeze['protocol_sha256'])

    def test_members_normal_counterexamples_and_replacements_preserved(self):
        self.assertEqual(self.members,rows(B2C/'results/members.jsonl'))
        normal=[m for m in self.members if m['cohort']=='b2b42' and m['identity']=='NORMAL'];self.assertEqual(len(normal),34)
        pref=[m for m in normal if m['scenario']=='L_BROWSER_LANG' and m['phase']=='change'];self.assertEqual(len(pref),2)
        self.assertTrue(all(self.inputs[m['sample_id']]['conditions']['C2']=='T' for m in pref))
        selected=read(B2B/'ATTEMPT_SELECTION.json');ids=set(selected['replacement_sample_ids'])
        self.assertEqual(len(ids),6)
        for m in self.members:
            if m['cohort']=='b2b42':self.assertEqual(m['source_meta']['source_run'],selected['replacement_run'] if m['sample_id'] in ids else selected['original_run'])

    def test_four_sets_states_identical_to_original(self):
        key=lambda r:(r['base_model_id'],r['set_id'],r['sample_id'])
        old={key(r):r['state'] for r in rows(B2C/'results/candidate_outputs.jsonl')}
        new={key(r):r['state'] for r in rows(HERE/'results/candidate_outputs.jsonl')}
        self.assertEqual(len(new),3*4*690);self.assertEqual(old,new)
        old_checks={(r['base_model_id'],r['set_id']):r for r in read(B2C/'results/candidate_checks.json')}
        for r in self.checks:
            old=copy.deepcopy(old_checks[r['base_model_id'],r['set_id']]);new=copy.deepcopy(r)
            for entry in (old,new):
                entry.pop('feasible');entry['reasons']=[x for x in entry['reasons'] if x!='NORMAL_ALARM_BUDGET:b2b42'];entry['normals']['b2b42'].pop('budget')
            self.assertEqual(old,new)

    def test_historical_values_do_not_change_selection(self):
        train=[m for m in self.members if m['role']=='selection'];inputs=copy.deepcopy(self.inputs)
        for m in self.members:
            if m['role']!='selection':inputs[m['sample_id']]={'base_states':{k:'FAILED' for k in inputs[m['sample_id']]['base_states']},'conditions':{'C1':'T','C2':'FAILED'}}
        for model in [m for m in self.models if m['setting']=='R_NO_MATCHED_NORMAL_CAP']:
            base=model['predictor']['base'];checks,winner,_=s.select(model['base_model_id'],train,inputs,base['rule_count'],base['complexity'],ablation_settings())
            self.assertEqual(checks,[c for c in self.checks if c['base_model_id']==model['base_model_id']]);self.assertEqual(winner,model['predictor']['selection_result'])
        with self.assertRaisesRegex(ValueError,'EVALUATION_MEMBER'):
            s.select(model['base_model_id'],self.members,inputs,base['rule_count'],base['complexity'],ablation_settings())

    def test_three_bases_nine_settings_roles_no_pooling(self):
        predictions=rows(HERE/'results/predictions.jsonl')
        self.assertEqual(Counter(p['model_id'] for p in predictions),{m['model_id']:951 for m in self.models})
        self.assertEqual(Counter(m['role'] for m in self.members),{'selection':690,'historical_evaluation':261})
        for model in self.models:
            if model['setting']!='R_FULL':self.assertEqual(model['usage'],'ABLATION_ONLY');self.assertFalse(model['predictor']['deployment_eligible'])

    def test_effective_failed_unrestored_stays_in_denominator(self):
        train=copy.deepcopy([m for m in self.members if m['role']=='selection']);inputs=copy.deepcopy(self.inputs)
        m=next(m for m in train if m['identity']=='EFFECTIVE_INTERVENTION' and m['family']=='App_language');m['runtime_restored']=False
        model=self.models[0];mid=model['base_model_id'];inputs[m['sample_id']]['base_states'][mid]='FAILED';base=model['predictor']['base']
        score,states=s.score(mid,[],train,inputs,base['rule_count'],base['complexity'],ablation_settings())
        self.assertEqual(score['families']['App_language']['n'],2);self.assertEqual(score['families']['App_language']['FAILED'],1)
        part=[dict(sample_id=m['sample_id'],state='FAILED')]
        row=aggregate(part,index(train),model,'b2b42','selection','EFFECTIVE_INTERVENTION','fixture','B2C_incremental_rule')
        self.assertEqual(row['denominator'],1);self.assertEqual(row['FAILED'],1)

    def test_all_results_reconstruct_from_saved_states(self):
        models=index(self.models,'model_id');old={(r['model_id'],r['sample_id']):r for r in rows(B2C/'results/predictions.jsonl')}
        for p in rows(HERE/'results/predictions.jsonl'):
            model=models[p['model_id']];i=self.inputs[p['sample_id']]
            states=[i['base_states'][p['base_model_id']]]+[i['conditions'][k] for k in model['predictor']['extensions']]
            expected='FAILED' if 'FAILED' in states else 'T' if 'T' in states else 'U' if 'U' in states else 'F'
            self.assertEqual(p['state'],expected)
            if p['setting']=='R_FULL':self.assertEqual(p['state'],old[p['model_id'],p['sample_id']]['state'])

    def test_tables_trace_same_predictions_and_names(self):
        members=index(self.members)
        lookup={(p['model_id'],p['sample_id']):p for source in (HERE/'results/predictions.jsonl',B3A/'results/predictions.jsonl') for p in rows(source)}
        metrics=read(HERE/'tables/metric_index.json')
        for r in metrics:
            self.assertEqual(len(r['sample_ids']),r['denominator'])
            actual=counts(lookup[r['model_id'],sid]['state'] for sid in r['sample_ids'])
            self.assertEqual([actual[k] for k in STATES],[r[k] for k in STATES])
            self.assertEqual(r['numerator'],r['T'])
            if r['model_family']=='B3A_fixed_tree':self.assertIn(r['plan'],('P0','P1','P2'));self.assertIn(r['setting'],('V_APP','V_BROWSER','V_BOTH','V_BOTH_REL'))
            else:self.assertIn(r['setting'],SETTINGS_NAMES)

    def test_timing_equivalence_and_fixed_runs(self):
        timing=read(HERE/'timing/EXECUTION.json');self.assertEqual([timing[k] for k in ('fit','selection','collection')],[0,0,0])
        replay=rows(HERE/'timing/equivalence.jsonl');self.assertEqual(len(replay),21*60);self.assertTrue(all(r['prepared_equals_public_equals_both_loaded_raw_wrappers'] for r in replay))
        repeats=Counter((r['label'],r['stage']) for r in rows(HERE/'timing/batches.jsonl'));self.assertTrue(all(n==10 for n in repeats.values()))
        self.assertEqual(len(repeats),21*7+1)
        self.assertTrue(all(r['equal'] for r in rows(HERE/'timing/checks.jsonl')))
