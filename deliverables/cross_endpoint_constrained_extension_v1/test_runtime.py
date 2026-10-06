import copy,unittest
from common import *
import adapter as a
from prepare_current import v16_pair
from inference import predict_current,predict_saved
from selector import select

class CurrentInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models=read(HERE/'results/models.json')
        p=rows(a.B2B/'positions.jsonl')[0];meta=p['meta']
        def physical(r):
            f,n=r.rsplit(':',1);return json.loads((ROOT/f).read_bytes().splitlines()[int(n)-1])
        cls.app,cls.pair=v16_pair(physical(meta['app_reference']),physical(meta['browser_reference']),physical(meta['provenance_reference']),meta['app_reference'])
        require(not cls.pair['errors'],'FIXTURE_BINDING_FAILED')
    def test_empty_extension_reproduces_base(self):
        for model in self.models:
            model=copy.deepcopy(model);model['extensions']=[];model['status']='BASELINE_RETAINED'
            p=predict_current(model,self.app,self.pair)
            self.assertEqual(p['state'],p['base_state']);self.assertFalse(p['selected_conditions'])
    def test_browser_missing_does_not_delete_app(self):
        pair=copy.deepcopy(self.pair)
        for name in ('features','field_status','field_quality'):
            pair[name]={k:v for k,v in pair[name].items() if not k.startswith('browser.')}
        p=predict_current(self.models[0],self.app,pair)
        self.assertEqual(p['base_state'],'F');self.assertEqual(p['state'],'U')
    def test_current_offset_only_changes_extension(self):
        pair=copy.deepcopy(self.pair);pair['features']['browser.web_data.execution_layer.timezone_offset']=-540
        p=predict_current(self.models[0],self.app,pair)
        self.assertEqual(p['base_state'],'F');self.assertEqual(p['state'],'T')
    def test_reject_labels_phases_browser_in_app(self):
        for key in ('label','phase','target_value','pre','post','scenario_id'):
            with self.assertRaises(ValueError):predict_current(self.models[0],self.app,dict(self.pair,**{key:'hidden'}))
            bad=copy.deepcopy(self.app);bad['raw'][key]='hidden'
            with self.assertRaises(ValueError):predict_current(self.models[0],bad,self.pair)
        bad=copy.deepcopy(self.app);bad['raw']['browser.web_data.language']='fr-FR'
        with self.assertRaises(ValueError):predict_current(self.models[0],bad,self.pair)
    def test_unselected_language_cannot_change_output(self):
        pair=copy.deepcopy(self.pair);pair['features']['browser.web_data.navigator_layer.language']='fr-FR'
        self.assertEqual(predict_current(self.models[0],self.app,pair)['state'],'F')
    def test_selected_binding_failure_dominates(self):
        pair=copy.deepcopy(self.pair);pair['errors']=['WRONG_PAIR']
        self.assertEqual(predict_current(self.models[0],self.app,pair)['state'],'FAILED')
    def test_original_model_conditions_frozen(self):
        for path,expected in read(a.b2b.HERE/'FROZEN.json')['files'].items():self.assertEqual(digest(ROOT/path),expected)
    def test_all_saved_output_compositions(self):
        inp=unique(rows(HERE/'results/inputs.jsonl'),lambda r:r['sample_id']);models={m['model_id']:m for m in self.models}
        for p in rows(HERE/'results/predictions.jsonl'):
            r=inp[p['sample_id']]
            self.assertEqual(predict_saved(models[p['model_id']],r['base_states'][p['base_model_id']],r['conditions']),p['state'])
    def test_whole_scenario_groups_retained(self):
        members=rows(HERE/'results/selection_members.jsonl');groups=read(HERE/'results/selection_groups.json')
        self.assertEqual(len(members),690)
        self.assertTrue(all(m['role']=='selection' for m in members))
        lookup={m['sample_id']:m for m in members}
        for g,ids in groups.items():
            if not g.startswith('mtc-group-'):
                self.assertEqual(len(ids),3)
                self.assertIn({lookup[i]['phase'] for i in ids},[{'pre','change','post'},{'clean_pre','attack_active','clean_post'}])
    def test_real_holdout_mutation_invariant(self):
        # Metamorphic test, not a second accepted learning run. Existing development
        # states fixed; arbitrary heldout144/117 state mutations cannot affect selection.
        members=rows(HERE/'results/selection_members.jsonl');all_i=unique(rows(HERE/'results/inputs.jsonl'),lambda r:r['sample_id'])
        train={m['sample_id'] for m in members};checks=read(HERE/'results/candidate_checks.json')
        for sid,r in all_i.items():
            if sid not in train:r['base_states']={m:'FAILED' for m in IDS};r['conditions']={'C1':'T','C2':'FAILED'}
        for model in self.models:
            check,winner,_=select(model['base_model_id'],members,all_i,model['base']['rule_count'],model['base']['complexity'])
            self.assertEqual(check,[r for r in checks if r['base_model_id']==model['base_model_id']]);self.assertEqual(winner['set_id'],model['selected_set'])

if __name__=='__main__':unittest.main()
