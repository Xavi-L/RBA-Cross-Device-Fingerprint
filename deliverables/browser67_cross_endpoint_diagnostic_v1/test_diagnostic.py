import ast,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run
import conditions as c
from hybridguard_agent.research import mtc_timezone_relation as tz

class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot=run.pilot();cls.models,_=run.load_models();cls.item=cls.pilot[0]
    def pair(self,cid,x,y):
        fs=dict(zip(c.DEPS[cid],[x,y]));return {'features':fs,'field_status':dict.fromkeys(fs,'observed'),'field_quality':dict.fromkeys(fs,'observed_value'),'errors':[]}
    def test_offset_zero_minus_one_and_direction(self):
        for x,y,s in [(0,0,'F'),(-1,-1,'F'),(0,-1,'T'),(540,-540,'T'),(-540,-540,'F')]:self.assertEqual(c.evaluate('C1',self.pair('C1',x,y))['state'],s)
    def test_offset_invalid_values(self):
        for x in [True,False,'0',None,float('nan'),float('inf')]:
            r=c.evaluate('C1',self.pair('C1',x,0));self.assertEqual(r['state'],'U');json.dumps(r,allow_nan=False)
    def test_timezone_time_is_diagnostic_only(self):
        p=self.pair('C1',0,-1);p['times']={'invalid_interval':True};self.assertEqual(c.evaluate('C1',p)['state'],'T')
    def test_case_and_granularity(self):
        self.assertEqual(c.evaluate('C2',self.pair('C2','EN-us','en-US'))['state'],'F')
        for cid,s in [('C2','T'),('C3','F')]:self.assertEqual(c.evaluate(cid,self.pair(cid,'zh-Hans-CN','zh-Hant-TW'))['state'],s)
        self.assertEqual(c.evaluate('C3',self.pair('C3','en-US','fr-FR'))['state'],'T')
    def test_parser_does_not_guess(self):
        for v in ['zh-RCN','en_US',' en-US','en-x-private','und',True]:self.assertEqual(c.evaluate('C2',self.pair('C2',v,'en-US'))['state'],'U')
    def test_p3_polarity_and_raw_list(self):
        for ys,s,p in [(['en-US'],'F','MATCH'),(['en-US','en'],'T','COUNTEREXAMPLE'),(['EN-us'],'T','COUNTEREXAMPLE')]:
            r=c.evaluate('D1',self.pair('D1',['en-US'],ys));self.assertEqual((r['state'],r['p3_outcome']),(s,p))
    def test_browser_first_list(self):
        for v in [[],None,'en-US',['en-US',False]]:self.assertEqual(c.evaluate('D2',self.pair('D2','en-US',v))['state'],'U')
        self.assertEqual(c.evaluate('D2',self.pair('D2','en-US',['EN-us','fr']))['state'],'F')
    def test_status_and_binding_failure(self):
        p=self.pair('C1',0,0);p['field_status'][c.DEPS['C1'][1]]='runtime_error';self.assertEqual(c.evaluate('C1',p)['state'],'U')
        p['errors']=['wrong_pair'];self.assertEqual(c.evaluate('C1',p)['state'],'FAILED')
    def test_no_label_or_phase_features(self):
        p=self.pair('C2','zh-CN','en-US');before=copy.deepcopy(p);p.update(phase='clean',label='normal',future_post='en-US',target='fr-FR')
        self.assertEqual(c.evaluate('C2',p),c.evaluate('C2',before));self.assertEqual(p['label'],'normal')
    def test_app_is_current_app_only(self):
        x=self.item;before=run.compile_app(x['raw'],x['app_session'],x['meta']['app_reference'])
        changed=copy.deepcopy(x);changed['pair']['features']={k:'OTHER_BROWSER' for k in changed['pair']['features']};changed['pair']['errors']=['browser_only_error']
        after=run.compile_app(changed['raw'],changed['app_session'],changed['meta']['app_reference']);self.assertEqual(before,after)
        self.assertFalse(any(k.startswith('browser.') for k in before[1]['features']))
        self.assertEqual(run.predict_item(x,self.models[0])['prediction'],run.predict_item(changed,self.models[0])['prediction'])
    def test_v16_not_relabelled(self):
        x=self.item;r=copy.deepcopy(x['raw']);r['canonical_received_payload']['collection_manifest']['collector_version_code']=14
        with self.assertRaises(ValueError):run.bind_v16(r,x['app_session'],'unit')
        r=copy.deepcopy(x['raw']);r['session_id']='different'
        with self.assertRaises(ValueError):run.bind_v16(r,x['app_session'],'unit')
    def test_missing_dates_fixed_vs_dynamic(self):
        x=self.item;r=copy.deepcopy(x['raw']);p=r['canonical_received_payload'];p['collection_manifest'].pop('collection_started_at_ms',None);p['collection_diagnostics'].pop('collection_finished_at_ms',None)
        b=run.bind_v16(r,x['app_session'],'unit');self.assertEqual(b['acquisition_time']['status'],'unavailable_device_interval')
        v=list(tz.evaluate(b).values())[0];self.assertTrue(v['available']);self.assertEqual(v['diagnostics']['date_basis'],'existing_syntactically_fixed_zone_no_date_required')
        f='app.android_native_data.locale_timezone_layer.native_timezone_id';b['features'][f]='Europe/Paris'
        v=list(tz.evaluate(b).values())[0];self.assertFalse(v['available']);self.assertEqual(v['reason'],'TIMEZONE_RELIABLE_DEVICE_DATE_INTERVAL_REQUIRED')
    def test_optional_modules_not_selected(self):
        x=self.item;r=copy.deepcopy(x['raw']);r['canonical_received_payload'].pop('collection_observations',None)
        a,b=run.compile_app(r,x['app_session'],'unit');prediction=run.selection.predict_current(self.models[0],'unit',a['raw']);self.assertEqual(prediction['decision'],'NO_ALERT')
    def test_frozen_models_unchanged(self):
        manifest=json.loads((run.HERE/'results/MODEL_MANIFEST.json').read_text())
        for m,row in zip(self.models,manifest):self.assertEqual(run.digest(run.ROOT/row['path']),row['sha256']);self.assertEqual(m.model_id,row['model_id'])
    def test_planned_members_and_phase_sidecar(self):
        from collections import Counter
        self.assertEqual(Counter(x['meta']['group'] for x in self.pilot),{'normal':12,'language_fr':3,'timezone_tokyo':3})
        self.assertEqual(len(run.mtc_members()),891)
    def test_duplicate_and_missing_not_guessed(self):
        for records in [[],[(1,{'id':'x'},None),(2,{'id':'x'},None)]]:
            with self.assertRaises(ValueError):run.unique(records,'id','x')
        # Corrupt raw source retains all 18 planned positions rather than shrinking n.
        original=run.rows
        def broken(path,selected=None):
            out=original(path,selected)
            if str(path).endswith('data/raw_browser_payloads.jsonl'):return []
            return out
        with patch.object(run,'rows',broken):
            out=run.pilot();self.assertEqual(len(out),18);self.assertTrue(all(x['pair']['errors'] for x in out))
    def test_malformed_physical_line_retained(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.jsonl';p.write_text('{bad\n{"id":"ok"}\n');r=run.rows(p);self.assertEqual([x[0] for x in r],[1,2]);self.assertIsNotNone(r[0][2])
    def test_saved_denominators_and_no_normal_relabel(self):
        a=[json.loads(l) for l in (run.HERE/'results/app_predictions.jsonl').read_text().splitlines()];b=[json.loads(l) for l in (run.HERE/'results/condition_results.jsonl').read_text().splitlines()]
        self.assertEqual(len(a),54);self.assertEqual(len(b),4545)
        self.assertEqual(len({(r['meta']['sample_id'],r['condition_id']) for r in b}),4545)
        self.assertTrue(any(r['meta']['cohort']=='mtc' and r['state']=='T' and r['meta']['normal_basis']['supported'] for r in b))
    def test_no_training_or_collection_calls(self):
        for p in [run.HERE/'run.py',run.HERE/'conditions.py']:
            for n in ast.walk(ast.parse(p.read_text())):
                if isinstance(n,ast.Call):
                    name=n.func.id if isinstance(n.func,ast.Name) else n.func.attr if isinstance(n.func,ast.Attribute) else ''
                    self.assertFalse(name.startswith('fit'),name);self.assertNotIn(name,{'Popen','system','create_subprocess_exec','train','collect'})
        readiness=json.loads((run.B1/'local_acceptance/experiment_plan/experiment_readiness.json').read_text())
        self.assertFalse(readiness['structural_ready']);self.assertEqual(readiness['counts']['split_assigned_count'],0)

    def test_browser_loader_failure_preserves_current_app(self):
        original = run.rows
        def missing(path, selected=None):
            return [] if str(path).endswith('data/raw_browser_payloads.jsonl') else original(path, selected)
        with patch.object(run, 'rows', missing):
            items = run.pilot()
        self.assertEqual(len(items), 18)
        self.assertTrue(all(item['raw'] is not None for item in items))
        self.assertTrue(all(item['pair']['errors'] for item in items))
        self.assertEqual(run.predict_item(items[0], self.models[0])['prediction']['decision'], 'NO_ALERT')

    def temporary_b1(self, root):
        import shutil
        files = ['local_acceptance/stage_inventory.jsonl', 'local_acceptance/paired244_snapshot/sample_index.jsonl',
                 'local_acceptance/paired244_snapshot/paired_244.jsonl', 'evidence_archive/pilot_r8/captures.jsonl',
                 'evidence_archive/data/raw_expanded_payloads.jsonl', 'evidence_archive/data/raw_browser_payloads.jsonl',
                 'evidence_archive/verification.json', 'PUBLICATION.json']
        for name in files:
            dst = root / name;dst.parent.mkdir(parents=True, exist_ok=True);shutil.copyfile(run.B1 / name, dst)

    def test_real_missing_browser_file_retains_all_app_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);self.temporary_b1(root)
            (root / 'evidence_archive/data/raw_browser_payloads.jsonl').unlink()
            with patch.object(run, 'B1', root): items = run.pilot()
            self.assertEqual(len(items), 18)
            self.assertTrue(all(item['raw'] is not None for item in items))
            self.assertTrue(all(item['pair']['errors'] for item in items))

    def test_d2_does_not_require_app_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);self.temporary_b1(root)
            (root / 'evidence_archive/data/raw_expanded_payloads.jsonl').unlink()
            with patch.object(run, 'B1', root): items = run.pilot()
            self.assertEqual(len(items), 18)
            self.assertTrue(all(item['raw'] is None for item in items))
            self.assertTrue(all(c.evaluate('C2', item['pair'])['state'] == 'FAILED' for item in items))
            self.assertTrue(all(c.evaluate('D2', item['pair'])['state'] == 'F' for item in items))

    def mutate_mtc(self, mutation):
        members = run.mtc_members();original = run.rows
        def changed(path, selected=None):
            rs = original(path, selected)
            if Path(path) == run.MTC / 'paired_244.jsonl':
                number, row, error = rs[0];row = copy.deepcopy(row);mutation(row);rs[0] = (number, row, error)
            return rs
        with patch.object(run, 'rows', changed): return run.mtc(members)

    def test_mtc_missing_browser_reference_is_one_failed_position(self):
        items = self.mutate_mtc(lambda row: row['source_refs'].pop('browser_raw_line'))
        self.assertEqual(len(items), 891)
        self.assertEqual(sum(bool(item['pair']['errors']) for item in items), 1)
        failed = next(item for item in items if item['pair']['errors'])
        self.assertEqual(c.evaluate('C1', failed['pair'])['state'], 'FAILED')

    def test_mtc_malformed_reference_shape_retained(self):
        items = self.mutate_mtc(lambda row: row.update(source_refs=[]))
        self.assertEqual(len(items), 891)
        self.assertEqual(sum(bool(item['pair']['errors']) for item in items), 1)

    def test_mtc_projection_cannot_change_raw_operand(self):
        items = self.mutate_mtc(lambda row: row['features'].update({'browser.web_data.navigator_layer.language': 'xx-ZZ'}))
        self.assertEqual(len(items), 891)
        self.assertEqual(sum(bool(item['pair']['errors']) for item in items), 1)
        self.assertTrue(any('RAW_VALUE_MISMATCH' in error for item in items for error in item['pair']['errors']))

    def test_mtc_absent_quality_is_not_promoted_to_observed(self):
        items = self.mutate_mtc(lambda row: row['field_quality'].pop('browser.web_data.navigator_layer.language'))
        affected = [item for item in items if item['pair']['field_quality'].get('browser.web_data.navigator_layer.language') is None]
        self.assertEqual(len(affected), 1)
        self.assertEqual(c.evaluate('C2', affected[0]['pair'])['state'], 'U')

    def test_stage_sidecar_bound_to_archived_capture(self):
        original = run.rows
        def changed(path, selected=None):
            rs = original(path, selected)
            if str(path).endswith('local_acceptance/stage_inventory.jsonl'):
                number, row, error = rs[0];row = dict(row, stage='attack_active');rs[0] = (number, row, error)
            return rs
        with patch.object(run, 'rows', changed): items = run.pilot()
        self.assertEqual(len(items), 18)
        self.assertTrue(any('CAPTURE_STAGE_MISMATCH' in error for item in items for error in item['pair']['errors']))

    def saved(self):
        a = [json.loads(line) for line in (run.HERE/'results/app_predictions.jsonl').read_text().splitlines()]
        b = [json.loads(line) for line in (run.HERE/'results/condition_results.jsonl').read_text().splitlines()]
        return a, b

    def test_summary_rejects_duplicate_model_with_same_total(self):
        a, b = self.saved();a[-1] = copy.deepcopy(a[0])
        with self.assertRaisesRegex(ValueError, 'APP_POSITION_PRODUCT_MISMATCH'):
            run.validate_saved_positions(run.HERE/'results', a, b)

    def test_summary_rejects_duplicate_condition_with_same_total(self):
        a, b = self.saved();b[-1] = copy.deepcopy(b[0])
        with self.assertRaisesRegex(ValueError, 'CONDITION_POSITION_PRODUCT_MISMATCH'):
            run.validate_saved_positions(run.HERE/'results', a, b)

    def test_summary_rejects_wrong_group_or_state(self):
        a, b = self.saved();b[0]['meta']['group'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'OUTPUT_SIDECAR_MISMATCH'):
            run.validate_saved_positions(run.HERE/'results', a, b)
        a, b = self.saved();b[0]['state'] = 'PASS'
        with self.assertRaisesRegex(ValueError, 'INVALID_SAVED_CONDITION_STATE'):
            run.validate_saved_positions(run.HERE/'results', a, b)

    def test_missing_pilot_feature_does_not_abort_other_positions(self):
        original = run.rows
        def missing(path, selected=None):
            rs = original(path, selected)
            if str(path).endswith('paired244_snapshot/paired_244.jsonl'):
                number, row, error = rs[0];row = copy.deepcopy(row);row['features'].pop('browser.web_data.navigator_layer.language');rs[0] = (number, row, error)
            return rs
        with patch.object(run, 'rows', missing): items = run.pilot()
        self.assertEqual(len(items), 18)
        self.assertEqual(sum(c.evaluate('C2', item['pair'])['state']=='U' for item in items), 1)

    def test_duplicate_mtc_ids_and_references_keep_both_positions(self):
        for field in ('sample_id', 'source_line'):
            members = copy.deepcopy(run.mtc_members())
            members[1][1][field] = members[0][1][field]
            items = run.mtc(members)
            self.assertEqual(len(items), 891)
            self.assertEqual(sum(bool(item['pair']['errors']) for item in items), 2)

    def test_mtc_wrong_browser_session_is_not_repaired(self):
        items = self.mutate_mtc(lambda row: row['browser'].update(session_id='unrelated-session'))
        self.assertEqual(len(items), 891)
        self.assertEqual(sum(bool(item['pair']['errors']) for item in items), 1)

    def test_bad_quality_container_retains_position_as_failure(self):
        items = self.mutate_mtc(lambda row: row.update(field_quality=[]))
        self.assertEqual(len(items), 891)
        self.assertEqual(sum(bool(item['pair']['errors']) for item in items), 1)

    def test_bad_v16_manifest_is_explicit_failure(self):
        item = copy.deepcopy(self.item)
        item['raw']['canonical_received_payload']['collection_manifest'] = None
        result = run.predict_item(item, self.models[0])['prediction']
        self.assertEqual(result['decision'], 'FAILED')

    def test_browser_index_mismatch_cannot_remove_valid_app(self):
        original = run.rows
        def changed(path, selected=None):
            rs = original(path, selected)
            if str(path).endswith('paired244_snapshot/sample_index.jsonl'):
                number, row, error = rs[0];row = dict(row, browser_session_id='wrong-browser-session');rs[0] = (number, row, error)
            return rs
        with patch.object(run, 'rows', changed): items = run.pilot()
        self.assertEqual(sum(item['raw'] is not None for item in items), 18)
        self.assertEqual(sum(bool(item['pair']['errors']) for item in items), 1)

if __name__=='__main__':unittest.main(verbosity=2)
