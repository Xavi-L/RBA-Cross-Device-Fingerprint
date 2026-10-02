"""Source and time boundaries, using only explicitly allowed training records."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from hybridguard_agent.research import timezone_relation_sources as source
from hybridguard_agent.research import mtc_relation_sources as prior
from hybridguard_agent.research import mtc_timezone_relation as tz
from hybridguard_agent.research.memory_relation_validation import state
from hybridguard_agent.research.mtc_cap8_data import load_mtc_replay_data

ROOT = Path(__file__).resolve().parents[2]


class TimezoneSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = json.loads((ROOT / 'deliverables/mtc_constrained_reselection_v1/SETTINGS.json').read_text())
        cls.ids = cls.settings['folds'][0]['train_ids'][:2]
        cls.bound = source.load_controlled_sources(cls.ids, allowed_ids=cls.ids)
        ref = cls.bound[cls.ids[0]]['source_binding']['raw_reference']
        path, number = ref.rsplit(':',1)
        with (ROOT / path).open() as stream:
            for n,line in enumerate(stream,1):
                if n == int(number): cls.raw = json.loads(line);break
        cls.session = cls.raw['session_id']
        cls.kw = {'session_id': cls.session, 'source_reference': ref,
            'environment_id': cls.raw['canonical_received_payload']['collection_manifest']['device_manifest_id']}

    def test_old_feature_transfer_is_byte_equivalent_and_time_separate(self):
        old = prior.load_controlled_sources(self.ids, allowed_ids=self.ids)
        for sid in self.ids:
            for key in ('features','field_status','field_quality'):
                self.assertEqual(old[sid][key], self.bound[sid][key])
            time = self.bound[sid]['acquisition_time']
            self.assertEqual(time['status'],'observed_device_interval')
            self.assertNotIn('collection_started_at_ms',self.bound[sid]['features'])
            self.assertEqual(time['session_id'],self.bound[sid]['source_binding']['app_session_id'])

    def test_actual_raw_datetime_values_match_bound_record(self):
        p = self.raw['canonical_received_payload'];b=self.bound[self.ids[0]]
        self.assertEqual(b['acquisition_time']['started_at_ms'],p['collection_manifest']['collection_started_at_ms'])
        self.assertEqual(b['acquisition_time']['finished_at_ms'],p['collection_diagnostics']['collection_finished_at_ms'])
        self.assertEqual(b['features'][tz.NATIVE_RAW],p['android_native_data']['locale_timezone_layer']['native_timezone_offset_min'])
        self.assertEqual(state(tz.evaluate(b)[tz.TIMEZONE_ID]),'F')

    def test_new_batch_identity_preserves_old_entry_restriction(self):
        b=source.bind_timezone_batch(self.raw,**self.kw)
        self.assertEqual(b['status'],'OK')
        self.assertEqual(b['source_binding']['sample_id'],'timezoneonly-'+self.session)
        reference={'opaque_id':'timezoneonly-'+self.session,'session_id':self.session,'observation_mode':'raw_observation_v1'}
        self.assertEqual(prior.bind_controlled_record(reference['opaque_id'],reference,self.raw)['status'],'FAILED')

    def test_cross_record_field_or_metadata_borrowing_fails(self):
        for what in ('outer','inner','field_session','version','environment'):
            r=deepcopy(self.raw);p=r['canonical_received_payload']
            if what=='outer':r['session_id']='other'
            if what=='inner':p['session_id']='other'
            if what=='field_session':p['field_session_ids']={tz.NATIVE_ZONE:'other'}
            if what=='version':p['collection_manifest']['collector_version_code']=11
            if what=='environment':p['collection_manifest']['device_manifest_id']='other'
            self.assertEqual(source.bind_timezone_batch(r,**self.kw)['status'],'FAILED',what)

    def test_no_upload_or_payload_timestamp_fallback(self):
        r=deepcopy(self.raw);p=r['canonical_received_payload']
        p['collection_manifest'].pop('collection_started_at_ms')
        r['received_at']='2026-07-01T00:00:00Z'
        b=source.bind_timezone_batch(r,**self.kw)
        self.assertEqual(b['status'],'OK')
        self.assertEqual(b['acquisition_time']['status'],'unavailable_device_interval')
        self.assertIsNone(b['acquisition_time']['started_at_ms'])

    def test_timestamp_units_and_inconsistent_device_range(self):
        r=deepcopy(self.raw);p=r['canonical_received_payload']
        p['collection_manifest']['collection_started_at_ms']=p['timestamp']
        p['collection_diagnostics']['collection_finished_at_ms']=p['timestamp']+1
        b=source.bind_timezone_batch(r,**self.kw)
        self.assertEqual(b['acquisition_time']['reason'],'DEVICE_RANGE_PAYLOAD_SECONDS_INCONSISTENT')
        for v in (None,-1,True,'timestamp',float('inf')):
            p['collection_manifest']['collection_started_at_ms']=v
            self.assertEqual(source.bind_timezone_batch(r,**self.kw)['acquisition_time']['status'],'unavailable_device_interval')

    def test_labels_phase_target_browser_ignored(self):
        original=source.bind_timezone_batch(self.raw,**self.kw)
        r=deepcopy(self.raw);p=r['canonical_received_payload']
        p.update(label=1,phase='attack',target_zone='America/Los_Angeles',model_id='phone')
        p['browser']={'timezone_offset':900}
        changed=source.bind_timezone_batch(r,**self.kw)
        for key in ('features','field_status','field_quality','acquisition_time'):
            self.assertEqual(changed[key],original[key])

    def test_minus_one_and_zero_timezone_are_not_generic_sentinels(self):
        r=deepcopy(self.raw);p=r['canonical_received_payload']
        p['android_native_data']['locale_timezone_layer']['native_timezone_id']='GMT+00:01'
        p['android_native_data']['locale_timezone_layer']['native_timezone_offset_min']=1
        for web, expected in ((-1,'F'),(0,'T')):
            p['web_data']['execution_layer']['timezone_offset']=web
            b=source.bind_timezone_batch(r,**self.kw)
            self.assertEqual(b['field_quality'][tz.WEB_OFFSET],'observed_value')
            self.assertEqual(state(tz.evaluate(b)[tz.TIMEZONE_ID]),expected)

    def test_missing_or_nonobject_raw_payload_is_failed_without_mutating_bound(self):
        original=self.bound[self.ids[0]]
        before=deepcopy(original)
        cases=(None, [], "bad-row", {}, {'canonical_received_payload': []},
               {'canonical_received_payload': 'bad-payload'})
        for raw in cases:
            bad=source._attach(original,raw,'test-raw-reference:1')
            self.assertEqual(bad['status'],'FAILED',repr(raw))
            self.assertIn('TIMEZONE_RAW_PAYLOAD_NOT_AN_OBJECT',bad['errors'])
            self.assertFalse(bad['source_binding']['binding_valid'])
            self.assertEqual(bad['features'],{})
            self.assertEqual(bad['field_status'],{})
            self.assertEqual(bad['field_quality'],{})
            self.assertNotIn('acquisition_time',bad)
        self.assertEqual(original,before)

    def test_selected_mtc_malformed_raw_line_keeps_member_as_failed(self):
        sid=self.settings['mtc_normal_train_ids'][0]
        r=next(r for r in load_mtc_replay_data()['records'] if r['sample_id']==sid)
        number=r['p2']['app_raw_line']
        with TemporaryDirectory() as directory:
            path=Path(directory)/'malformed.jsonl'
            for row in ('{not valid json}', 'null', '[]',
                        '{"canonical_received_payload": []}'):
                path.write_text('\n'*(number-1)+row+'\n')
                result=source.load_mtc_sources({sid:r['observation']},{sid:r['p2']},[sid],
                    allowed_ids=[sid],raw_path=path)
                self.assertEqual(list(result),[sid])
                self.assertEqual(result[sid]['status'],'FAILED',row)
                self.assertEqual(result[sid]['features'],{})
                self.assertIn('TIMEZONE_RAW_PAYLOAD_NOT_AN_OBJECT',result[sid]['errors'])

    def test_requested_ids_cannot_escape_allowed_training_members(self):
        with self.assertRaises(ValueError):source.load_controlled_sources(self.ids,allowed_ids=[])
        with self.assertRaises(ValueError):source.load_mtc_sources({}, {}, ['heldout'], allowed_ids=[])

    def test_real_discovery_binding_uses_same_raw_line_and_retains_old_inputs(self):
        sid=self.settings['mtc_normal_train_ids'][0]
        r=next(r for r in load_mtc_replay_data()['records'] if r['sample_id']==sid)
        b=source.load_mtc_sources({sid:r['observation']},{sid:r['p2']},[sid],allowed_ids=[sid])[sid]
        old=prior.bind_mtc_observation(r['observation'],sid,allowed_ids=[sid],expected_registry=r['p2'])
        self.assertEqual(b['status'],'OK')
        for key in ('features','field_status','field_quality'):self.assertEqual(b[key],old[key])
        self.assertEqual(b['acquisition_time']['status'],'observed_device_interval')
        self.assertTrue(b['acquisition_time']['source_reference'].endswith(':'+str(r['p2']['app_raw_line'])))
        with TemporaryDirectory() as directory:
            path=Path(directory)/'missing.jsonl';path.write_text('{}\n')
            bad=source.load_mtc_sources({sid:r['observation']},{sid:r['p2']},[sid],allowed_ids=[sid],raw_path=path)[sid]
            self.assertEqual(bad['status'],'FAILED')


if __name__ == '__main__':unittest.main()
