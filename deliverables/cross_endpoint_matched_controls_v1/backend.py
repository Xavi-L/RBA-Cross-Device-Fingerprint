"""A fresh private B2-B batch through B1's unchanged restricted backend wrapper."""
import importlib.util, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
B1=HERE.parent/'browser67_pilot_intake_v1'
if __name__=='__main__':
    out=Path(sys.argv[1]).resolve();out.mkdir(exist_ok=True,parents=True)
    if HERE/'private_runs' not in out.parents:raise ValueError('Private fresh run directory required')
    s=importlib.util.spec_from_file_location('b1_backend',B1/'source_reference/run_backend.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    m.UPSTREAM=B1/'evidence_archive/upstream';m.DATA=out/'data';m.STOP=out/'backend.stop';m.SUMMARY=out/'backend_lifecycle_summary.json'
    m.main()
