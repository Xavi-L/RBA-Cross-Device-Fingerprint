import json,unittest
import engine as e
from test_comparison import fixtures
class Export(unittest.TestCase):
 def test_json_tree_and_preprocess_export(self):
  rs,ms=fixtures();spec=e.fit_preprocessor(rs,[r['sample_id'] for r in rs]);X,_=e.transform(spec,rs);X,names=e.view_array(spec,X,rs,'V_APP');model,_,_=e.fit_tree(X,ms)
  tree=e.tree_json(model,names);self.assertEqual(json.loads(json.dumps(tree)),tree);self.assertEqual(json.loads(json.dumps(spec)),spec)
