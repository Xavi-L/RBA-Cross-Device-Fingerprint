import importlib.util,sys,unittest
from closeout_io import *
from guards import profile_calls
from test_closeout import Closeout

spec=importlib.util.spec_from_file_location('original_b2c_semantic_tests',B2C/'test_extension.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
suite=unittest.defaultTestLoader.loadTestsFromTestCase(Closeout)
for name in ('test_or_truth_table','test_failure_no_short_circuit','test_unselected_failure_and_empty_extension','test_fixed_tie_fewest_then_id'):
    suite.addTest(old.Semantics(name))
suite.addTest(old.Denominator('test_effective_but_restore_failed_stays'))
calls=profile_calls(True)
result=unittest.TextTestRunner(verbosity=2).run(suite);sys.setprofile(None)
write(HERE/'TEST_CALLS.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),calls=dict(calls),scope='extra test selector calls, not accepted new ablation tasks',fit=0,collection=0))
sys.exit(not result.wasSuccessful())
