from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from hybridguard_agent.research import mtc_timezone_relation as tz
from hybridguard_agent.research.memory_relation_validation import state


def ms(text):
    return int(datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp() * 1000)


def record(zone='America/Los_Angeles', raw=-480, web=420, date='2026-07-01T12:00:00'):
    values = {tz.NATIVE_ZONE: zone, tz.NATIVE_RAW: raw, tz.WEB_OFFSET: web, tz.WEB_ZONE: zone}
    return {'status': 'OK', 'source_binding': {'binding_valid': True, 'same_app_record': True,
        'app_session_id': 'one'}, 'features': values,
        'field_status': {k: 'observed' for k in values},
        'field_quality': {k: 'observed_value' for k in values},
        'acquisition_time': {'status': 'observed_device_interval', 'session_id': 'one',
            'started_at_ms': ms(date), 'finished_at_ms': ms(date) + 1000}}


def outcome(r):
    return tz.evaluate(r)[tz.TIMEZONE_ID]


class TimezoneRelationTest(unittest.TestCase):
    def test_minutes_sign_and_valid_zero_and_minus_one(self):
        self.assertEqual(state(outcome(record('UTC', 0, 0))), 'F')
        self.assertEqual(state(outcome(record('GMT+00:01', 1, -1))), 'F')
        self.assertEqual(state(outcome(record('GMT-00:01', -1, 1))), 'F')
        self.assertEqual(state(outcome(record('GMT+08:00', 480, -480))), 'F')
        self.assertEqual(state(outcome(record('GMT+08:00', 480, 480))), 'T')
        self.assertEqual(state(outcome(record('Etc/GMT-8', 480, -480))), 'F')

    def test_winter_summer_and_raw_standard_not_current(self):
        self.assertEqual(state(outcome(record(web=420))), 'F')
        self.assertEqual(state(outcome(record(web=480, date='2026-01-01T12:00:00'))), 'F')
        self.assertEqual(state(outcome(record(web=480))), 'T')
        self.assertEqual(outcome(record())['diagnostics']['expected_web_offset_min'], 420)
        # ID and dated library suffice in the dynamic domain; raw standard
        # offset is diagnostic, not an incorrect additional DST invariant.
        r = record(); r['features'].pop(tz.NATIVE_RAW)
        self.assertEqual(state(outcome(r)), 'F')

    def test_alias_and_distinct_id_same_offset_allowed(self):
        r = record('US/Pacific');r['features'][tz.WEB_ZONE] = 'America/Vancouver'
        self.assertEqual(state(outcome(r)), 'F')
        r = record('Asia/Shanghai', 480, -480);r['features'][tz.WEB_ZONE] = 'Asia/Singapore'
        self.assertEqual(state(outcome(r)), 'F')

    def test_missing_date_dynamic_u_fixed_still_comparable(self):
        r = record();r.pop('acquisition_time')
        self.assertEqual(state(outcome(r)), 'U')
        r['features'].update({tz.NATIVE_ZONE: 'GMT-08:00',tz.WEB_OFFSET:480})
        self.assertEqual(state(outcome(r)), 'F')

    def test_unknown_zone_and_invalid_values(self):
        self.assertEqual(state(outcome(record('Imaginary/Region'))), 'U')
        for value in (None, True, '420', float('nan'), float('inf'), -1440, 1440, 0.5):
            r = record();r['features'][tz.WEB_OFFSET] = value
            self.assertEqual(state(outcome(r)), 'U', repr(value))
        r = record();r['features'][tz.WEB_OFFSET] = 0
        self.assertEqual(state(outcome(r)), 'T')
        r['features'][tz.WEB_OFFSET] = -1
        self.assertEqual(state(outcome(r)), 'T')

    def test_interval_change_and_same_endpoint_long_interval(self):
        r = record(date='2026-03-08T09:59:59')
        r['acquisition_time']['finished_at_ms'] = ms('2026-03-08T10:00:01')
        self.assertEqual(state(outcome(r)), 'U')
        self.assertIn('CROSSES_OFFSET_CHANGE', outcome(r)['reason'])
        r = record(date='2026-01-01T00:00:00')
        r['acquisition_time']['finished_at_ms'] = ms('2027-01-01T00:00:00')
        self.assertEqual(state(outcome(r)), 'U')
        # Beyond the stored TZif transition table, parsed POSIX future rules.
        r = record(date='2050-01-01T00:00:00')
        r['acquisition_time']['finished_at_ms'] = ms('2051-01-01T00:00:00')
        self.assertEqual(state(outcome(r)), 'U')

    def test_invalid_timestamps_and_cross_session(self):
        for value in (-1, '123', True, float('nan'), 10**30):
            r = record();r['acquisition_time']['started_at_ms'] = value
            self.assertEqual(state(outcome(r)), 'U')
        r = record();r['acquisition_time']['session_id'] = 'other'
        self.assertEqual(state(outcome(r)), 'FAILED')
        r = record();r['source_binding']['same_app_record'] = False
        self.assertEqual(state(outcome(r)), 'FAILED')

    def test_no_today_fallback_or_label_target_phase_feature(self):
        r = record();expected = outcome(r)
        r.update(phase='attack', target='UTC', label='normal', sample_id='different', model='other')
        self.assertEqual(outcome(r), expected)
        r['acquisition_time']['finished_at_ms'] = r['acquisition_time']['started_at_ms'] = ms('2026-01-01T12:00:00')
        self.assertEqual(state(outcome(r)), 'T')

    def test_normal_system_change_vs_web_only_change(self):
        r = record('Asia/Shanghai',480,-480)
        self.assertEqual(state(outcome(r)), 'F')
        r['features'].update({tz.NATIVE_ZONE:'UTC',tz.NATIVE_RAW:0,tz.WEB_OFFSET:0,tz.WEB_ZONE:'UTC'})
        self.assertEqual(state(outcome(r)), 'F')
        r['features'].update({tz.NATIVE_ZONE:'Asia/Shanghai',tz.NATIVE_RAW:480})
        self.assertEqual(state(outcome(r)), 'T')

    def test_runtime_database_mismatch_is_failed_not_false(self):
        with patch.object(tz, 'tzdb_directory', side_effect=RuntimeError('TIMEZONE_DATABASE_VERSION_MISMATCH:test')):
            self.assertEqual(state(outcome(record())), 'FAILED')

    def test_registry_and_parameters_are_fixed_and_honest(self):
        atom, = tz.registered_atoms()
        self.assertEqual(atom.surfaces, ('native84','app_web67'))
        self.assertFalse(tz.parameters()['fitted'])
        self.assertEqual(tz.parameters()['parameter_fit_calls'],0)
        self.assertEqual(tz.parameters()['tzdb_version'],'2026c')


if __name__ == '__main__': unittest.main()
