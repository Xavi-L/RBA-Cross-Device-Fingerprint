"""Synthetic tests for a new train preference, not evidence of research benefit."""
import copy
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hybridguard_agent.research.rule_learning.models import Atom, Clause, Literal
from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning_v2.adapter import TrainAccess, V2Problem, save_model as save_a
from hybridguard_agent.research.rule_learning_v2.retention import retain, diversity, signal_group
from hybridguard_agent.research.rule_learning_v2 import b_engine
from hybridguard_agent.research.rule_learning_v2.common import write
from hybridguard_agent.tests.test_rule_learning_v2 import toy, toy_fit


def fixture(n=6, mutate=None, same_group=False):
    atoms=tuple(Atom('fixture:'+s,s,('app_web67',),('SYNTHETIC',),('fixture:'+s,),
                    provenance={'field':'fixture.'+s,'signal_group':'same' if same_group else s}) for s in ('a','b'))
    rows={};meta={}
    for t in range(n):
        for phase in ('clean_pre','attack','clean_post'):
            i=f'fixture-{t}-{phase}'
            row={a.atom_id:cell('T' if phase=='attack' else 'F') for a in atoms}
            if mutate: mutate(t,phase,row)
            rows[i]=row;meta[i]={'supervised_label':int(phase=='attack'),'phase':phase,'bundle_id':'fixture',
               'triplet_id':str(t),'environment_group_id':'fixture-env','config_id':'fixture-config'}
    job={'fold_id':'fixture','train_ids':list(rows),'outer_test_ids':['fixture-test'],'representation':'W0'}
    access=TrainAccess(job,rows,meta);p=V2Problem(access,rows,atoms,math.inf)
    groups={a.atom_id:signal_group(a) for a in atoms}
    a=Clause((Literal('fixture:a'),));b=Clause((Literal('fixture:b'),))
    return access,p,groups,a,b,atoms


class RetentionTests(unittest.TestCase):
    def test_overlapping_train_signals_complement_on_synthetic_holdout(self):
        access,p,g,a,b,atoms=fixture()
        selected,outcome,trace=retain(p,(a,),g,math.inf)
        self.assertEqual(selected,(a,b));self.assertEqual(outcome['D_initial'],1)
        self.assertEqual(outcome['D_final'],2);self.assertEqual(trace[0]['delta_macro_tpr'],0)
        # This held-out vector is consumed only after selection.
        from hybridguard_agent.research.rule_learning.predictor import clause_state
        heldout={'fixture:a':cell('F'),'fixture:b':cell('T')}
        self.assertEqual(clause_state(a,heldout),'F');self.assertEqual(clause_state(b,heldout),'T')

    def test_aliases_and_thresholds_cannot_multiply_D(self):
        _,p,g,a,b,_=fixture(same_group=True)
        self.assertEqual(diversity(p,(a,b),g),diversity(p,(a,),g))
        self.assertEqual(retain(p,(a,),g,math.inf)[0],(a,))

    def test_individually_eligible_but_union_clean_exceeds_budget(self):
        def change(t,phase,row):
            if phase=='clean_pre' and t in (0,1): row['fixture:'+('a' if t==0 else 'b')]=cell('T')
        _,p,g,a,b,_=fixture(10,change)
        self.assertTrue(p.score((a,))['feasible']);self.assertTrue(p.score((b,))['feasible'])
        self.assertEqual(p.score((a,b))['clean_alarms'],2);self.assertEqual(p.budget,1)
        self.assertEqual(retain(p,(a,),g,math.inf)[0],(a,))

    def test_U_strict_logic_and_phase_coverage(self):
        def change(t,phase,row):
            if phase=='clean_pre' and t<3: row['fixture:b']=cell('U')
        _,p,g,a,b,_=fixture(mutate=change)
        self.assertIn(b,p.candidates)
        proposed=p.score((a,b))
        self.assertEqual(float(proposed['coverage']['clean_pre']),.5)
        self.assertEqual(float(proposed['coverage']['attack']),1)
        self.assertEqual(retain(p,(a,),g,math.inf)[0],(a,))

    def test_no_legal_addition_keeps_original_and_is_repeatable(self):
        _,p,g,a,_,_=fixture(same_group=True)
        left=retain(p,(a,),g,math.inf);right=retain(p,(a,),g,math.inf)
        self.assertEqual(left,right);self.assertEqual(left[0],(a,))

    def test_outer_labels_modified_fields_and_ids_not_predictors_save_load(self):
        access,p,g,a,b,atoms=fixture()
        defs={'atoms':[vars(x) for x in atoms],'single_surface_allowlists':{'native84':[],'app_web67':[x.atom_id for x in atoms],'host26':[]}}
        spec={'base_representation':'W0','representation':'W0','method':'R_KEEP_V1'}
        binding={'study_version':'discriminative-rule-learning-v2-20260925','phase':'V2-B','fold_id':'fixture','operating_point':'OP05'}
        first,training=b_engine.fit_b(access,defs,spec,binding)
        poisoned=copy.deepcopy(access.metadata)
        for m in poisoned.values(): m['expected_modified_fields']=['bad'];m['outer_test_label']=0
        job=copy.deepcopy(access.job);job['outer_labels']={'fixture-test':1}
        second,_=b_engine.fit_b(TrainAccess(job,access.rows,poisoned),defs,spec,binding)
        self.assertEqual(first.clauses,second.clauses)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model.json';b_engine.save_model(first,path);loaded=b_engine.load_model(path)
            raw={'fixture:a':cell('F'),'fixture:b':cell('T'),'label':'poison','expected_modified_fields':['bad']}
            self.assertEqual(b_engine.predict_current(first,'fixture-test',raw),b_engine.predict_current(loaded,'fixture-test',raw))
            self.assertEqual(b_engine.predict_current(loaded,'fixture-test',raw)['decision'],'MANIPULATION_ALERT')
            self.assertEqual(b_engine.predict_current(loaded,'different-id',raw)['decision'],'MANIPULATION_ALERT')

    def test_saved_initialization_uses_exact_fold_encoder_without_refit(self):
        _,defs,job,rows,meta=toy();_,initial,training=toy_fit()
        from dataclasses import replace
        from hybridguard_agent.research.rule_learning_v2.adapter import V2Model
        initial=V2Model(replace(initial.engine,binding=dict(initial.binding,operating_point='OP05')))
        binding={'study_version':'discriminative-rule-learning-v2-20260925','phase':'V2-B','fold_id':job['fold_id'],'operating_point':'OP05'}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'model.json';save_a(initial,path);write(path.with_name('training.json'),training)
            spec={'base_representation':'S_FLAT','representation':'S_FLAT','method':'R_KEEP_V1','initial_model_ref':str(path)}
            with patch.object(b_engine,'encode_train',side_effect=AssertionError('Must reuse frozen thresholds')):
                model,trained=b_engine.fit_b(TrainAccess(job,rows,meta),defs,spec,binding)
            self.assertEqual(model.encoder,initial.encoder)
            self.assertTrue(trained['initialization']['candidate_support_and_training_score_verified'])
            bad=dict(job,fold_id='wrong-fold')
            with self.assertRaisesRegex(ValueError,'FOLD_MISMATCH'):
                b_engine.fit_b(TrainAccess(bad,rows,meta),defs,spec,binding)

    def test_native_validity_gate_is_not_new_signal_group(self):
        def a(name): return Atom(name,'a',('app_web67',),('fixture',),(name,))
        self.assertEqual(signal_group(a('CAT:NW-006')),signal_group(a('DEVIATION:OFFDER-UA-001')))

    def test_timeout_without_incumbent_is_failure_not_valid_empty(self):
        _,p,g,a,_,_=fixture()
        self.assertEqual(retain(p,(),g,0)[1]['status'],'FAILED_FIT')
        selected,outcome,_=retain(p,(a,),g,0)
        self.assertEqual(selected,(a,));self.assertEqual(outcome['status'],'TIME_LIMIT_FEASIBLE')


if __name__=='__main__': unittest.main()
