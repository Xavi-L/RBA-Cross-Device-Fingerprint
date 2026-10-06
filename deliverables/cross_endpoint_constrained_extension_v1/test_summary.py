import tempfile,unittest
from common import *
from summarize import summarize

class SavedSummary(unittest.TestCase):
    def test_recovery_group_does_not_change_main_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'saved';source.mkdir();output=Path(d)/'output'
            for name in ('members.jsonl','predictions.jsonl','models.json'):(source/name).write_bytes((HERE/'results'/name).read_bytes())
            members=rows(source/'members.jsonl');m=next(m for m in members if m['cohort']=='b2b42' and m['identity']=='EFFECTIVE_INTERVENTION')
            m['full_recovery_qualified']=False;m['runtime_restored']=False
            jsonl(source/'members.jsonl',members);table=summarize(source,output)
            for row in table:
                if row['cohort']=='b2b42' and row['group']=='EFFECTIVE_INTERVENTION':self.assertEqual(row['n'],8)
                if row['cohort']=='b2b42' and row['group']=='recovery_complete':self.assertEqual(row['n'],39)
    def test_missing_output_is_not_silently_removed(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'saved';source.mkdir()
            for name in ('members.jsonl','models.json'):(source/name).write_bytes((HERE/'results'/name).read_bytes())
            jsonl(source/'predictions.jsonl',rows(HERE/'results/predictions.jsonl')[:-1])
            with self.assertRaisesRegex(ValueError,'OUTPUT_MEMBERSHIP'):summarize(source,Path(d)/'output')
