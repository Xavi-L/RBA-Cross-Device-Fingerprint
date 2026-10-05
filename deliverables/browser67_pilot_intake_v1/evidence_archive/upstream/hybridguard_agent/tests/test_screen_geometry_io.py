"""Temporary fault fixtures only; no historical evidence is ever written."""
from pathlib import Path
from tempfile import TemporaryDirectory
import gzip
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from hybridguard_agent.research import screen_geometry_io as io

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'deliverables/screen_geometry_observation_v1'
NEW=ROOT/'deliverables/screen_geometry_closeout_v1'
spec=importlib.util.spec_from_file_location('geometry_io_evaluate',OLD/'evaluate.py')
ev=importlib.util.module_from_spec(spec);spec.loader.exec_module(ev)


class ReaderTests(unittest.TestCase):
    def test_good_bad_blank_nonobjects_encoding_good_physical_lines(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.jsonl'
            p.write_bytes(b'{"session_id":"a"}\n{bad\n\nnull\n[]\n"s"\n42\n\xff\n{"session_id":"b"}\n')
            r=io.read_jsonl(p)
            self.assertEqual([v['line'] for v in r.records],[1,9])
            self.assertEqual([e['line'] for e in r.errors],list(range(2,9)))
            self.assertEqual(r.records[-1]['path'],str(p))
            self.assertEqual(r.records[-1]['reference'],str(p)+':9')

    def test_truncated_line_and_invalid_ids_do_not_disappear(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.jsonl';p.write_bytes(b'{}\n{"session_id": []}\n{"session_id":"ok"}\n{"session_id":')
            r=io.read_jsonl(p);ix=io.index_records(r,'session_id')
            self.assertEqual(list(ix),['ok'])
            self.assertEqual([e['kind'] for e in r.errors].count('INVALID_IDENTIFIER'),2)
            self.assertEqual(r.errors[0]['kind'],'INVALID_UNTERMINATED_JSON')

    def test_gzip_footer_truncation_and_broken_next_member_preserve_prior_lines(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.jsonl.gz';good=b'{"id":"a"}\n\n{"id":"b"}\n'
            for payload,kind in ((gzip.compress(good)[:-8],'GZIP_TRUNCATED'),
                                 (gzip.compress(good)+b'broken gzip member','GZIP_ERROR')):
                p.write_bytes(payload);r=io.read_jsonl(p)
                self.assertEqual([x['line'] for x in r.records],[1,3])
                self.assertIn(kind,[e['kind'] for e in r.errors])

    def test_missing_unreadable_and_object_config_errors(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)
            self.assertEqual(io.read_jsonl(p/'absent').errors[0]['kind'],'FILE_NOT_FOUND')
            self.assertEqual(io.read_jsonl(p).errors[0]['kind'],'FILE_UNREADABLE')
            for data in ('null','[]','"s"','42','{bad'):
                f=p/'config.json';f.write_text(data)
                with self.assertRaises(io.EvidenceError):io.read_object(f,required=True)

    def test_duplicate_ids_not_overwritten(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'x';p.write_text('{"step_id":"a"}\n{"step_id":"a"}\n')
            r=io.read_jsonl(p);ix=io.index_records(r,'step_id')
            self.assertEqual(len(ix['a']),2)
            self.assertEqual(r.errors[0]['kind'],'DUPLICATE_IDENTIFIER')

    def test_nonfinite_numbers_and_duplicate_keys_are_explicit_errors(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.jsonl'
            p.write_text('{"x":1e400}\n{"x":NaN}\n{"x":1,"x":2}\n{"x":8.5}\n')
            r=io.read_jsonl(p)
            self.assertEqual([x['line'] for x in r.records],[4])
            self.assertEqual(len(r.errors),3)


class BatchTests(unittest.TestCase):
    def fixture(self,tmp):
        source=Path(tmp)/'input';run=source/'runs/api29_swiftshader';(run/'backend').mkdir(parents=True)
        origin=OLD/'runs/api29_swiftshader'
        settings=json.loads((OLD/'SETTINGS.json').read_text())
        ops=[json.loads(l) for l in (origin/'operations.jsonl').read_text().splitlines()]
        ops=[o for o in ops if o['process_type']=='A' and o['round']==1]
        raws={r['session_id']:r for r in [json.loads(l) for l in (origin/'backend/raw_expanded_payloads.jsonl').read_text().splitlines()]}
        (run/'operations.jsonl').write_text(''.join(json.dumps(o)+'\n' for o in ops))
        archive=run/'backend/raw_expanded_payloads.jsonl'
        archive.write_text(''.join(json.dumps(raws[o['session_id']])+'\n' for o in ops))
        shutil.copyfile(origin/'environment.json',run/'environment.json')
        for o in ops:shutil.copyfile(origin/(o['step_id']+'.cdp.json'),run/(o['step_id']+'.cdp.json'))
        plan=[{'environment':'api29_swiftshader',**{k:o[k] for k in ('step_id','process_type','round','phase')}} for o in ops]
        return source,run,settings,plan,archive

    def test_bad_unknown_line_does_not_guess_member_and_good_following_keeps_line(self):
        with TemporaryDirectory() as tmp:
            source,run,s,plan,archive=self.fixture(tmp)
            lines=archive.read_text().splitlines();archive.write_text(lines[0]+'\n{broken\n\n'+lines[2]+'\n')
            data,errors=ev.evaluate_positions(source,s,plan)
            self.assertEqual(len(data),3)
            self.assertEqual(data[1]['conditions']['R_HOST_GEOMETRY']['state'],'FAILED')
            self.assertTrue(data[2]['raw_reference'].endswith(':4'))
            self.assertEqual(data[2]['conditions']['R_HOST_GEOMETRY']['state'],'F')
            self.assertTrue(any(e['kind']=='INVALID_JSON' and not e.get('step_id') for e in errors))

    def test_nonobjects_missing_identity_and_partial_gzip_keep_planned_denominator(self):
        for bad in ('null','[]','42','{"session_id": []}','{}'):
            with self.subTest(bad=bad),TemporaryDirectory() as tmp:
                source,run,s,plan,archive=self.fixture(tmp)
                lines=archive.read_text().splitlines();archive.write_text(lines[0]+'\n'+bad+'\n'+lines[2]+'\n')
                data,errors=ev.evaluate_positions(source,s,plan)
                self.assertEqual(len(data),3);self.assertEqual(data[1]['position_status'],'FAILED_INPUT')
                self.assertEqual(data[2]['conditions']['R_HOST_GEOMETRY']['state'],'F')
        with TemporaryDirectory() as tmp:
            source,run,s,plan,archive=self.fixture(tmp)
            data=archive.read_bytes().splitlines(keepends=True);archive.unlink()
            archive.with_suffix('.jsonl.gz').write_bytes(gzip.compress(data[0])[:-8])
            rows,errors=ev.evaluate_positions(source,s,plan)
            self.assertEqual(len(rows),3);self.assertEqual(rows[0]['conditions']['R_HOST_GEOMETRY']['state'],'F')
            self.assertEqual([r['conditions']['R_HOST_GEOMETRY']['state'] for r in rows[1:]],['FAILED','FAILED'])
            self.assertIn('GZIP_TRUNCATED',[e['kind'] for e in errors])

    def test_duplicate_session_step_and_operation_session_conflicts(self):
        for kind in ('raw','step','shared_session'):
            with self.subTest(kind=kind),TemporaryDirectory() as tmp:
                source,run,s,plan,archive=self.fixture(tmp)
                if kind=='raw':archive.write_text(archive.read_text()+archive.read_text().splitlines()[0]+'\n')
                elif kind=='step':
                    p=run/'operations.jsonl';p.write_text(p.read_text()+p.read_text().splitlines()[0]+'\n')
                else:
                    p=run/'operations.jsonl';ops=[json.loads(l) for l in p.read_text().splitlines()]
                    ops[1]['session_id']=ops[0]['session_id'];p.write_text(''.join(json.dumps(o)+'\n' for o in ops))
                data,errors=ev.evaluate_positions(source,s,plan)
                self.assertEqual(data[0]['conditions']['R_HOST_GEOMETRY']['state'],'FAILED')
                self.assertEqual(len(data),3)
                if kind=='shared_session':self.assertEqual(data[1]['position_status'],'FAILED_INPUT')

    def test_bad_receipt_or_environment_is_failed_evidence_not_lost_position(self):
        for kind in ('missing','bad_json','null','environment'):
            with self.subTest(kind=kind),TemporaryDirectory() as tmp:
                source,run,s,plan,archive=self.fixture(tmp)
                p=run/(plan[1]['step_id']+'.cdp.json') if kind!='environment' else run/'environment.json'
                if kind=='missing':p.unlink()
                else:p.write_text('null' if kind=='null' else '{broken')
                data,errors=ev.evaluate_positions(source,s,plan)
                self.assertEqual(len(data),3);self.assertEqual(data[1]['position_status'],'FAILED_EVIDENCE')
                self.assertFalse(data[1]['observable_intervention']);self.assertTrue(errors)
                # Valid current raw still has a meaningful independent condition result.
                self.assertEqual(data[1]['conditions']['R_HOST_GEOMETRY']['state'],'T')

    def test_fatal_config_emits_no_scores_and_v16_cannot_impersonate_v15(self):
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir();out=Path(tmp)/'output'
            for data in ('{bad','null',json.dumps({'collector':{'version_code':16}})):
                (source/'SETTINGS.json').write_text(data)
                with self.assertRaises(io.EvidenceError):ev.evaluate(out,input_dir=source)
                self.assertFalse(out.exists())

    def test_external_output_and_missing_planned_members_keep_72(self):
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir();out=Path(tmp)/'output'
            shutil.copyfile(OLD/'SETTINGS.json',source/'SETTINGS.json')
            summary=ev.evaluate(out,input_dir=source)
            self.assertEqual(summary['all']['n'],72)
            self.assertEqual(summary['all']['conditions']['R_HOST_GEOMETRY']['FAILED'],72)
            self.assertTrue((out/'READ_ERRORS.json').exists())
            with self.assertRaises(FileExistsError):ev.evaluate(out,input_dir=source)

    def test_latest_code_keeps_all_original_v15_fields_and_summary(self):
        spec=importlib.util.spec_from_file_location('geometry_v15_comparison',NEW/'verify_v15.py')
        sys.path.insert(0,str(NEW))
        try:
            compare=importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)
        finally:sys.path.pop(0)
        settings=io.read_object(OLD/'SETTINGS.json',required=True)[0]
        data,errors=ev.evaluate_positions(OLD,settings,ev.legacy_plan(settings))
        old=ev.rows(OLD/'predictions.jsonl.gz');by_id={r['sample_id']:r for r in data}
        self.assertEqual(len(data),72);self.assertFalse(errors)
        self.assertEqual(set(by_id),{r['sample_id'] for r in old})
        for r in old:self.assertFalse(compare.differences(r,by_id[r['sample_id']]))
        self.assertFalse(compare.differences(ev.read(OLD/'SUMMARY.json'),ev.summary_data(data,72)))

    def test_v16_entry_keeps_twelve_under_nested_damage_and_has_separate_identity(self):
        with TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';out=Path(tmp)/'evaluation'
            shutil.copytree(NEW/'v16_smoke/runs',source/'runs')
            archive=source/'runs/api29_swiftshader/backend/raw_expanded_payloads.jsonl'
            rows=[json.loads(l) for l in archive.read_text().splitlines()]
            rows[0]['canonical_received_payload']=None
            rows[4]['canonical_received_payload']['collection_observations']=[]
            archive.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            command=[sys.executable,'-B',str(NEW/'evaluate.py'),'--input-dir',str(source),'--output-dir',str(out)]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            data=ev.rows(out/'predictions.jsonl.gz')
            self.assertEqual(len(data),12)
            self.assertTrue(all(r['material_role']=='ENGINEERING_SMOKE' for r in data))
            checks=ev.read(out/'ENGINEERING_CHECKS.json')['positions']
            self.assertEqual(len(checks),12)
            self.assertEqual(checks[0]['status'],'FAILED_INPUT')
            self.assertEqual(checks[4]['status'],'FAILED_INPUT')
            self.assertTrue(checks[-1]['bound_window'])
            # This same fixed entry rejects the old profile before producing output.
            badout=Path(tmp)/'bad-profile-output'
            command=[sys.executable,'-B',str(NEW/'evaluate.py'),'--input-dir',str(source),'--output-dir',str(badout),'--settings',str(OLD/'SETTINGS.json')]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse(badout.exists())


if __name__=='__main__':unittest.main()
