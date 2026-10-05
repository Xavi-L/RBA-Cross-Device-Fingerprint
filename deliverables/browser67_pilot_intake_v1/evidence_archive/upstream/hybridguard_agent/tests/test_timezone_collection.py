import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('timezone_collect_tests', ROOT / 'deliverables/timezone_relation_validation_v1/collect.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def settings():
    s = json.loads((ROOT / 'deliverables/memory_relation_validation_v1/SETTINGS.json').read_text())
    s.update(targets_timezone=['UTC', 'America/Los_Angeles'], types=['L', 'A'],
             phases=['clean_pre', 'change', 'clean_post'], rounds=1, planned_records=36)
    return s


def steps(kind='A', changed=True, recovered=True):
    values = [{'native_timezone_id': 'Asia/Shanghai', 'native_timezone_offset_min': 480,
               'web_timezone_id': 'Asia/Shanghai', 'web_timezone_offset': -480} for _ in range(3)]
    if changed: values[1].update(web_timezone_id='UTC', web_timezone_offset=0)
    if kind == 'L' and changed: values[1].update(native_timezone_id='UTC', native_timezone_offset_min=0)
    if not recovered: values[2] = copy.deepcopy(values[1])
    out = []
    for i, p in enumerate(c.PHASES):
        zone = 'UTC' if kind == 'L' and i == 1 else 'Asia/Shanghai'
        out.append({'step_id': p, 'phase': p, 'process_type': kind, 'target_timezone': 'UTC', 'status': 'COLLECTED',
                    'cdp_status': 'COMPLETED', 'system_change': {'status': 'COMPLETED'},
                    'observed_timezone': values[i], 'system_before': {'timezone_id': zone}, 'system_after': {'timezone_id': zone}})
    return out


class TimezoneCollectionTests(unittest.TestCase):
    def test_exact_plan_no_extra_targets_rounds_or_environment(self):
        s = settings(); c.validate_settings(s)
        p = c.positions(s)
        self.assertEqual(len(p) * len(s['environments']), 36)
        self.assertEqual(len({r['step_id'] for r in p}), 12)
        self.assertEqual({r['process_type'] for r in p}, {'A', 'L'})
        for k, v in [('targets_timezone', ['UTC']), ('rounds', 2), ('planned_records', 72), ('attempts_per_position', 2)]:
            bad = copy.deepcopy(s); bad[k] = v
            with self.assertRaises(ValueError): c.validate_settings(bad)

    def test_freeze_gate_precedes_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            with self.assertRaises(FileNotFoundError): c.require_frozen(d)
            f = {'status': 'FROZEN', 'actual_fit_calls': 6, 'baseline_model_ids': ['b1', 'b2', 'b3'],
                 'new_model_ids': ['tz1', 'tz2', 'tz3'], 'frozen_at': '2026-10-02T00:00:00Z'}
            c.write(d / 'MODELS_FROZEN.json', f); self.assertEqual(c.require_frozen(d), f)
            for k, v in [('status', 'STARTED'), ('actual_fit_calls', 5), ('new_model_ids', ['b1', 'b2', 'b3'])]:
                bad = dict(f); bad[k] = v; c.write(d / 'MODELS_FROZEN.json', bad)
                with self.assertRaises(ValueError): c.require_frozen(d)

    def test_real_raw_field_mapping_no_native_web_cross_join(self):
        p = ROOT / 'deliverables/memory_relation_validation_v1/runs/api29_swiftshader/backend/raw_expanded_payloads.jsonl'
        raw = json.loads(p.read_text().splitlines()[0]); result = c.timezone_observation(raw)
        self.assertEqual(result, {'native_timezone_id': 'Asia/Shanghai', 'native_timezone_offset_min': 480,
                                 'web_timezone_id': 'Asia/Shanghai', 'web_timezone_offset': -480})

    def test_system_service_and_auto_setting_are_restored_not_only_property(self):
        state = {'timezone_id': 'UTC', 'auto_time_zone': '0'}; calls = []
        def command(argv):
            a = argv[1:]; calls.append(a)
            if a[:4] == ['shell', 'cmd', 'alarm', 'set-timezone']: state['timezone_id'] = a[4]
            if a[:4] == ['shell', 'settings', 'put', 'global']: state['auto_time_zone'] = a[5]
            if a == ['shell', 'getprop', 'persist.sys.timezone']: return state['timezone_id']
            if a == ['shell', 'settings', 'get', 'global', 'auto_time_zone']: return state['auto_time_zone']
            if a[:2] == ['shell', 'date']: return '1790000000,+0800,CST'
            return ''
        original = {'timezone_id': 'Asia/Shanghai', 'auto_time_zone': '1'}
        with patch.object(c.time, 'sleep'):
            result = c.restore_original(command, ['adb'], original, True)
        self.assertEqual(result['status'], 'RESTORED'); self.assertEqual(state, original)
        self.assertIn(['shell', 'cmd', 'alarm', 'set-timezone', 'Asia/Shanghai'], calls)
        self.assertFalse(any('setprop' in a for a in calls))

    def test_actual_effect_and_recovery_independent_of_detector_labels(self):
        s = steps(); s[1].update(label='normal', model_result='F', relation_result='F')
        r = c.trio_evidence(s, {'status': 'RESTORED'})
        self.assertEqual((r['effect'], r['recovery']), ('OBSERVABLE_CHANGE', 'RESTORED'))
        self.assertFalse(r['native_changed']); self.assertFalse(r['confounded'])
        r = c.trio_evidence(steps(changed=False), {'status': 'RESTORED'})
        self.assertEqual(r['effect'], 'NO_OBSERVABLE_EFFECT')
        r = c.trio_evidence(steps(kind='L'), {'status': 'RESTORED'})
        self.assertTrue(r['native_changed']); self.assertTrue(r['web_changed']); self.assertFalse(r['confounded'])

    def test_failed_execution_missing_evidence_and_bad_restore_preserved(self):
        s = steps(recovered=False); s[1]['cdp_status'] = 'FAILED'; s[1]['status'] = 'FAILED'
        r = c.trio_evidence(s, {'status': 'RESTORATION_FAILED'})
        self.assertEqual((r['execution'], r['effect'], r['recovery']),
                         ('FAILED_OR_NOT_EXECUTED', 'OBSERVABLE_CHANGE', 'RECOVERY_FAILED'))
        self.assertFalse(r['all_positions_collected'])
        s[2].pop('observed_timezone')
        r = c.trio_evidence(s, {'status': 'RESTORATION_FAILED'})
        self.assertEqual(r['recovery'], 'MISSING_OBSERVATION')

    def test_web_only_system_change_is_a_confound_not_a_successful_target(self):
        s = steps(); s[1]['system_after']['timezone_id'] = 'UTC'
        r = c.trio_evidence(s, {'status': 'RESTORED'})
        self.assertTrue(r['confounded']); self.assertFalse(r['system_unchanged'])


if __name__ == '__main__': unittest.main()
