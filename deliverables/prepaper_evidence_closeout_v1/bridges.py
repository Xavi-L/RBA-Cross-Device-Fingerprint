"""Import original frozen modules without changing their implementation."""
import sys
from closeout_io import ROOT,B2C,B3A
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(B2C))
import selector as original_selector
import inference as original_inference

def runtime():
    import adapter
    import prepare_current
    sys.path.insert(0,str(B3A))
    import engine
    import features
    import source_adapter
    return adapter,prepare_current,engine,features,source_adapter
