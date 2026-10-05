"""Opt-in representation cannot change old cells or encode time metadata."""
from copy import deepcopy
import unittest
from hybridguard_agent.research import mtc_timezone_candidates as new
from hybridguard_agent.research import mtc_relation_candidates as old
from hybridguard_agent.research import mtc_timezone_relation as tz
from hybridguard_agent.research import mtc_timezone_selection as engine
from hybridguard_agent.research import mtc_reselection_candidates as base
from hybridguard_agent.research.rule_learning.contracts import cell
from hybridguard_agent.research.rule_learning.predictor import clause_state
from hybridguard_agent.research.rule_learning.models import Clause, Literal

class TimezoneCandidateTests(unittest.TestCase):
    def source(self):
        features={tz.NATIVE_ZONE:'UTC',tz.NATIVE_RAW:0,tz.WEB_OFFSET:0}
        return {'status':'OK','errors':[], 'features':features,
            'field_status':{f:'observed' for f in features},
            'field_quality':{f:'observed_value' for f in features},
            'source_binding':{'binding_valid':True,'same_app_record':True,'app_session_id':'s'}}

    def test_old_cells_and_input_registry_unchanged(self):
        raw={'raw':{'old-cell':cell('F')},'candidate_inputs':{}}
        source=self.source()
        before=old.extend(raw,source)
        after=new.extend(raw,source)
        for field,value in before['raw'].items(): self.assertEqual(value,after['raw'][field])
        for field,value in before['candidate_inputs'].items(): self.assertEqual(value,after['candidate_inputs'][field])
        self.assertEqual(len(base.approved_atoms(base.definitions())),50)
        self.assertEqual(len(new.registered_atoms()),3)
        self.assertEqual(len(old.registered_atoms()),2)
        self.assertFalse(new.parameters()['fitted'])

    def test_model_metadata_and_future_recovery_do_not_affect_relation(self):
        source=self.source(); raw={'raw':{},'candidate_inputs':{}}
        expected=new.extend(raw,source)['raw']
        source.update(label='attack',phase='clean_post',target_timezone='America/Los_Angeles',
                      model_id='tablet',future_post={tz.WEB_OFFSET:420},sample_id='attack-id')
        self.assertEqual(new.extend(raw,source)['raw'],expected)
        source['features'][tz.WEB_OFFSET]=-1
        self.assertTrue(new.extend(raw,source)['raw'][tz.TIMEZONE_ID]['value'])

    def test_bad_current_session_is_failed_not_unknown(self):
        source=self.source();source['source_binding']['same_app_record']=False
        measured=new.extend({'raw':{},'candidate_inputs':{}},source)['raw'][tz.TIMEZONE_ID]
        self.assertNotEqual(measured['evaluation_status'],'OK')

if __name__=='__main__': unittest.main()
