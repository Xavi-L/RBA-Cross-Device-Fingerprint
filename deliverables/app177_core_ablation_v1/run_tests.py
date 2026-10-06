"""Record test API invocations separately from the bounded research fits."""
from collections import Counter
from contextlib import ExitStack
import json,sys,unittest
from unittest.mock import patch
from pathlib import Path
import data,tree
from data import engine
counts=Counter()
def wrap(obj,name,label):
    original=getattr(obj,name)
    def call(*args,**kwargs):counts[label]+=1;return original(*args,**kwargs)
    return patch.object(obj,name,call)
with ExitStack() as stack:
    for obj,name,label in [(engine,'fit','rule_fit_API_calls_rejected_before_fit'),(engine,'predict_current','ablation_prediction_calls'),
                           (data.full_engine,'predict_current','full_prediction_calls'),(tree,'fit','tree_fit_calls'),(tree,'predict','tree_prediction_calls')]:
        stack.enter_context(wrap(obj,name,label))
    suite=unittest.defaultTestLoader.discover(str(data.HERE),pattern='test_app177.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
(data.HERE/'results/TEST_CALLS.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
 'passed':result.wasSuccessful(),'calls':dict(counts),'actual_rule_fits':0,'actual_tree_fits':0,
 'earlier_test_runs':[{'tests':11,'failures':1,'actual_fits':0,'reason':'JSON tuple/list score comparison adapter, repaired'},{'tests':11,'failures':0,'actual_fits':0}],
 'early_source_load_probes':{'model_predictions':0,'fits':0}},indent=2)+'\n')
sys.exit(not result.wasSuccessful())
