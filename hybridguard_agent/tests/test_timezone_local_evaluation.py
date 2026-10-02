"""Local batch evidence/denominators stay separate from timezone predictions."""
from copy import deepcopy
import importlib.util
import gzip
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('local_timezone_eval_tests',ROOT/'deliverables/timezone_relation_validation_v1/evaluate_local.py')
local=importlib.util.module_from_spec(spec);spec.loader.exec_module(local)
tz=local.relation


def member(sid,phase,*,kind='A',zone='Asia/Shanghai',raw=480,webzone='Asia/Shanghai',offset=-480):
    vals={tz.NATIVE_ZONE:zone,tz.NATIVE_RAW:raw,tz.WEB_ZONE:webzone,tz.WEB_OFFSET:offset}
    obs={'valid':True,'session_id':sid,'values':vals,'source_reference':'raw:'+sid,'reasons':[]}
    flow={'verified':True,'session_id':sid,'operation_id':sid,'noop':kind=='L' or phase!='change',
          'evidence_refs':['receipt:'+sid],'fresh_process_verified':True,'process_removed_verified':True,
          'system_operation_verified':True,'cdp_rollback_verified':True,
          'after_rollback_runtime_observation':{'timezone_id':'Asia/Shanghai','timezone_offset':-480}}
    row={'sample_id':sid,'environment':'test','target_timezone':'UTC','process_type':kind,'phase':phase,
         'operation':{'status':'COLLECTED','system_before':{'timezone_id':zone},'system_after':{'timezone_id':zone}},
         'major_non_target_fields':{'memory':2,'cpu':1},'conditions':{'R_TZ':{'state':'F'},'R_ABSOLUTE':{'state':'T'}}}
    return {'observation':obs,'workflow':flow,'row':row}


class LocalAdjudicationTests(unittest.TestCase):
    def test_normal_setting_change_can_alarm_without_losing_normal_basis(self):
        trio=[member('pre','clean_pre',kind='L'),
              member('mid','change',kind='L',zone='UTC',raw=0,webzone='UTC',offset=0),
              member('post','clean_post',kind='L')]
        trio[1]['row']['conditions']['R_TZ']['state']='T'
        evidence=local.adjudicate_trio(trio)
        self.assertEqual(evidence['normal_supported'],[True,True,True])
        self.assertEqual(evidence['effect'],'OBSERVABLE_CHANGE')
        self.assertFalse(evidence['observable_intervention'])

    def test_actual_web_change_is_effect_even_if_relation_misses(self):
        trio=[member('pre','clean_pre'),member('mid','change',webzone='UTC',offset=0),member('post','clean_post')]
        result=local.adjudicate_trio(trio)
        self.assertTrue(result['observable_intervention'])
        self.assertEqual(result['normal_supported'],[True,False,True])
        self.assertEqual(result['recovery'],'RESTORED')
        self.assertFalse(result['confounded'])

    def test_no_effect_failed_operation_and_failed_recovery_stay_separate(self):
        trio=[member('pre','clean_pre'),member('mid','change'),member('post','clean_post')]
        result=local.adjudicate_trio(trio)
        self.assertEqual(result['effect'],'NO_OBSERVABLE_EFFECT')
        self.assertFalse(result['observable_intervention'])
        trio[1]['workflow']['verified']=False
        result=local.adjudicate_trio(trio)
        self.assertEqual(result['execution'],'OPERATION_FAILED')
        self.assertFalse(trio[2]['row']['normal_basis']['supported'])
        trio[1]['workflow']['verified']=True
        trio[2]['observation']['values'][tz.WEB_OFFSET]=0
        result=local.adjudicate_trio(trio)
        self.assertEqual(result['recovery'],'RECOVERY_NOT_VERIFIED')
        self.assertFalse(trio[2]['row']['normal_basis']['supported'])

    def test_non_target_change_is_reported_not_credited_to_timezone(self):
        trio=[member('pre','clean_pre'),member('mid','change',webzone='UTC',offset=0),member('post','clean_post')]
        trio[1]['row']['major_non_target_fields']['cpu']=48
        result=local.adjudicate_trio(trio)
        self.assertTrue(result['confounded'])
        self.assertEqual(result['non_target_differences']['cpu'],[1,48,1])

    def test_fixed_absolute_boundary_zero_minus_one_and_unknown(self):
        bound={'status':'OK','features':{tz.WEB_OFFSET:-480},'field_status':{tz.WEB_OFFSET:'observed'},
               'field_quality':{tz.WEB_OFFSET:'observed_value'}}
        for value,state in [(-480,'F'),(-481,'F'),(-1,'T'),(0,'T'),(420,'T'),(None,'U'),('0','U'),(float('nan'),'U')]:
            bound['features'][tz.WEB_OFFSET]=value
            self.assertEqual(local.condition_state(local.fixed_absolute(bound)),state)

    def test_complete_flow_stats_preserve_unknown_and_failed(self):
        rows=[{'conditions':{n:{'state':s} for n in ('R_ABSOLUTE','R_TZ')},
               'models':[{'model_id':'model','decision':d}]} for s,d in
              [('T','MANIPULATION_ALERT'),('F','NO_ALERT'),('U','INSUFFICIENT_EVIDENCE'),('FAILED','FAILED')]]
        stats=local.group_stats(rows)
        self.assertEqual(stats['n'],4)
        self.assertEqual(stats['conditions']['R_TZ'],{'T':1,'F':1,'U':1,'FAILED':1})
        self.assertEqual(stats['models']['model']['INSUFFICIENT_EVIDENCE'],1)


class LocalWorkflowTests(unittest.TestCase):
    def test_real_batch_keeps_old_inputs_and_excludes_labels_from_prediction(self):
        run=ROOT/'deliverables/timezone_relation_validation_v1/runs/api29_swiftshader'
        raw=local.rows(run/'backend/raw_expanded_payloads.jsonl')[0]
        sid=raw['session_id'];reference=str((run/'backend/raw_expanded_payloads.jsonl').relative_to(ROOT))+':1'
        _,adapted=local.adapt_current(raw,sid,reference,'api29_swiftshader')
        compiler,contract=local.memory.compiler()
        prepared=compiler.compile_record(raw['canonical_received_payload'],expected_session_id=sid,
                    source_reference=reference,measurement_contract=contract)
        old=local.old_candidates.adapt_controlled(prepared)
        self.assertTrue(all(adapted['raw'][k]==v for k,v in old['raw'].items()))
        changed=deepcopy(raw)
        changed.update(phase='attack',target_timezone='Europe/London',label='attack')
        changed['canonical_received_payload'].update(phase='clean_post',label='normal',target_timezone='UTC')
        _,second=local.adapt_current(changed,sid,reference,'api29_swiftshader')
        self.assertEqual(adapted['raw'],second['raw'])
        with self.assertRaises(ValueError):local.adapt_current(raw,'another-session',reference,'api29_swiftshader')

    def test_summarizer_preserves_all_failed_planned_positions(self):
        settings=local.read(ROOT/'deliverables/timezone_relation_validation_v1/SETTINGS.json')
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);(out/'SETTINGS.json').write_text(json.dumps(settings))
            with gzip.open(out/'new_batch.jsonl.gz','wt') as stream:
                for env in settings['environments']:
                    for p in local.collector.positions(settings):
                        row={**p,'environment':env['environment_group_id'],'sample_id':env['environment_group_id']+':'+p['step_id'],
                             'source_binding':{'binding_valid':False},'normal_basis':{'supported':False,'reasons':['NOT_EXECUTED']},
                             'conditions':{n:{'state':'FAILED'} for n in ('R_ABSOLUTE','R_TZ')},
                             'models':[{'model_id':'test-model','decision':'FAILED'}]}
                        stream.write(json.dumps(row)+'\n')
            summary=local.summarize(out)
            self.assertEqual((summary['processed_positions'],summary['confirmed_normal_positions']),(36,0))
            self.assertEqual(summary['all']['conditions']['R_TZ']['FAILED'],36)
            self.assertEqual(summary['all']['models']['test-model']['FAILED'],36)
            self.assertEqual(len(summary['normal_evidence_exclusions']),30)

    def test_raw_session_and_runtime_receipt_must_match(self):
        sid='current';step='timezone-UTC-A-clean_pre';context='timezone-validation:test:'+step
        bound={'status':'OK','source_binding':{'binding_valid':True,'app_session_id':sid,'raw_reference':'raw:1'},
               'features':{tz.WEB_ZONE:'Asia/Shanghai',tz.WEB_OFFSET:-480}}
        raw={'server_received_at':'2026-10-02T10:00:02Z','canonical_received_payload':{'collection_manifest':{
             'runtime_context':context,'collector_install_id':'install'}}}
        op={'step_id':step,'session_id':sid,'status':'COLLECTED','cdp_status':'COMPLETED','cdp_rollback_status':'COMPLETED',
            'collector_install_id':'install','phase':'clean_pre','process_type':'A','target_timezone':'UTC',
            'started_at':'2026-10-02T10:00:00Z','finished_at':'2026-10-02T10:00:04Z',
            'system_before':{'timezone_id':'Asia/Shanghai'},'system_after':{'timezone_id':'Asia/Shanghai'},
            'owned_app_process_absent_after':True}
        rt={'timezone_id':'Asia/Shanghai','timezone_offset':-480}
        commands=[{'argv':['adb','shell','am','force-stop','pkg'],'returncode':0},
                  {'argv':['adb','shell','pidof','pkg'],'returncode':1,'stdout':''},
                  {'argv':['adb','shell','am','start',context],'returncode':0},
                  {'argv':['node','/tmp/'+step+'.cdp.json',context],'returncode':0},
                  {'argv':['adb','shell','am','force-stop','pkg'],'returncode':0},
                  {'argv':['adb','shell','pidof','pkg'],'returncode':1,'stdout':''}]
        events=[{'method':m,'params':p,'result':r} for m,p,r in
                [('Page.enable',{},{}),('Emulation.setTimezoneOverride',{'timezoneId':''},{}),
                 ('Page.navigate',{'url':'file:///android_asset/expanded_probe.html'},{}),
                 ('Runtime.evaluate',{}, {'result':{'value':rt}}),
                 ('Emulation.setTimezoneOverride',{'timezoneId':''},{}),('Runtime.evaluate',{}, {'result':{'value':rt}})]]
        receipt={'version':'timezone-only-cdp-v1','status':'COMPLETED','apply_status':'COMPLETED','rollback_status':'COMPLETED',
                 'target_timezone':None,'changed_domains':[],'raw_receipt':{'session_id':sid,'received_before_rollback':True},
                 'started_at':'2026-10-02T10:00:01Z','finished_at':'2026-10-02T10:00:03Z',
                 'commands':events,'current_runtime_observation':rt,'after_rollback_runtime_observation':rt}
        run=Path('runs/test')
        self.assertTrue(local.workflow_proof(bound,raw,op,receipt,commands,environment='test',run=run)['verified'])
        changed=deepcopy(receipt);changed['raw_receipt']['session_id']='other'
        self.assertFalse(local.workflow_proof(bound,raw,op,changed,commands,environment='test',run=run)['verified'])
        changed=deepcopy(receipt);changed['current_runtime_observation']['timezone_offset']=0
        self.assertFalse(local.workflow_proof(bound,raw,op,changed,commands,environment='test',run=run)['verified'])


if __name__=='__main__':unittest.main()
