import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from run_expansion import Expansion, Campaign, REGISTRY, plan


class ExpansionContractTests(unittest.TestCase):
    def test_plan_keeps_three_complete_triplets_per_configuration(self):
        ids = [i for i in REGISTRY if i not in ('cdp_webdriver_only_v1','stealth_languages_only_v1')]
        config = {'campaign_id':'synthetic','additional_configurations':ids}
        rows = plan(config)
        self.assertEqual(len(rows),108)
        self.assertEqual(len({r['step_id'] for r in rows}),108)
        for offset in range(0,len(rows),3):
            pre,active,post = rows[offset:offset+3]
            self.assertEqual([r['phase'] for r in (pre,active,post)],['clean_pre','attack','clean_post'])
            self.assertEqual({r['group'] for r in (pre,active,post)},{active['configuration']})
            self.assertIsNone(pre['configuration']); self.assertIsNone(post['configuration'])
        for bad in ([ids[0],ids[0]],['unknown']):
            with self.assertRaises(ValueError):plan({**config,'additional_configurations':bad})

    def test_emulation_uses_distinct_runner_and_verified_rollback(self):
        obj = Expansion.__new__(Expansion)
        obj.config = {}
        obj.paths = {'runner':'original'}
        cfg = REGISTRY['cdp_timezone_only_v1']
        receipt = {'configId':cfg['configId'], 'injected':cfg['profile'],
                   'declaredObservableFields':cfg['observableFields'], 'declaredStealthEvasions':None,
                   'declaredCdpEmulation':cfg['cdpEmulation'],
                   'cdpEmulation':{'rollback':{'rollback_verified':True}}}
        def original(*args):
            self.assertTrue(obj.paths['runner'].endswith('week10_cdp_emulation_runner_v5.mjs'))
            return copy.deepcopy(receipt)
        with patch.object(Campaign,'run_injection',side_effect=original):
            obj.run_injection({'configuration':cfg['id']},Path('/unused'))
            self.assertEqual(obj.paths['runner'],'original')
            receipt['cdpEmulation']['rollback']['rollback_verified']=False
            with self.assertRaises(ValueError):obj.run_injection({'configuration':cfg['id']},Path('/unused'))
            self.assertEqual(obj.paths['runner'],'original')

    def test_declared_profile_mismatch_is_rejected(self):
        obj=Expansion.__new__(Expansion);obj.paths={'runner':'original'};obj.config={}
        cfg=REGISTRY['playwright']
        receipt={'configId':cfg['configId'],'injected':{},'declaredObservableFields':cfg['observableFields'],'declaredStealthEvasions':None}
        with patch.object(Campaign,'run_injection',return_value=receipt):
            with self.assertRaises(ValueError):obj.run_injection({'configuration':'playwright'},Path('/unused'))
        self.assertEqual(obj.paths['runner'],'original')

    def test_cleanup_checks_own_device_and_client_port(self):
        obj=Expansion.__new__(Expansion);obj.active_configuration='playwright';obj.config={'serial':'emulator-synthetic'}
        with patch.object(Campaign,'adb',return_value='another-device tcp:9223 localabstract:test\n') as adb:
            obj.adb(['forward','--remove','tcp:9222'],Path('/unused'),False)
            self.assertEqual(adb.call_count,1)
        with patch.object(Campaign,'adb',side_effect=['emulator-synthetic tcp:9223 localabstract:test\n','']) as adb:
            obj.adb(['forward','--remove','tcp:9222'],Path('/unused'),False)
            self.assertEqual(adb.call_args.args[0],['forward','--remove','tcp:9223'])

    def test_fresh_direct_launch_waits_for_new_activity(self):
        obj=Expansion.__new__(Expansion);obj.config={'fresh_launch_contract':'process-absent-then-am-start-S-W-v1'}
        with patch.object(Campaign,'adb',return_value='Status: ok') as adb:
            obj.adb(['shell','am','start','-n','example/.Main'],Path('/unused'))
            self.assertEqual(adb.call_args.args[0],['shell','am','start','-S','-W','-n','example/.Main'])


if __name__ == '__main__':unittest.main()
