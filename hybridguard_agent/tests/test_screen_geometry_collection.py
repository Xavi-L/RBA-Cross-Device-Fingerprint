from copy import deepcopy
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('screen_collection',ROOT/'deliverables/screen_geometry_observation_v1/collect.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class ScreenCollectionTests(unittest.TestCase):
 def settings(self):return json.loads((ROOT/'deliverables/screen_geometry_observation_v1/SETTINGS.json').read_text())
 def test_fixed_matrix_and_separate_smoke(self):
  s=c.validate_settings(self.settings());p=c.positions(s)
  self.assertEqual(len(p),24);self.assertEqual(len({r['step_id'] for r in p}),24)
  self.assertEqual(len(c.positions(s,True)),6)
  self.assertFalse(set(r['step_id'] for r in p)&set(r['step_id'] for r in c.positions(s,True)))
  s['rounds']=3
  with self.assertRaises(ValueError):c.validate_settings(s)
 def test_l3_matching_settings_and_real_host_controls(self):
  s=self.settings()
  for p in c.positions(s):
   args=c.launch_extras(p,s);values={args[i+1]:args[i+2] for i in range(0,len(args),3)}
   self.assertEqual(values[c.PACKAGE+'.GEOMETRY_ENABLE_ZOOM'],str(p['process_type']=='L3').lower())
   self.assertEqual(values[c.PACKAGE+'.GEOMETRY_ZOOM_FACTOR'],'1.25' if p['process_type']=='L3' and p['phase']=='change' else '1.0')
 def test_original_intervention_cannot_be_retuned(self):
  s=self.settings();s['screen_configuration']['cdpEmulation']['applyCommands'][0]['params']['height']=710
  with self.assertRaises(ValueError):c.validate_settings(s)
if __name__=='__main__':unittest.main()
