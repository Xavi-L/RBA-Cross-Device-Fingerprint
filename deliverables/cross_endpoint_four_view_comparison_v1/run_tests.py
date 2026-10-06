"""Explicit test learning ledger, separate from twelve accepted experiment fits."""
import sys,unittest,argparse
from io_utils import *
import engine as e
e.PHASE='tests';e.COUNTS.clear();e.EVENTS.clear()
parser=argparse.ArgumentParser();parser.add_argument('--pattern',default='test_*.py');args=parser.parse_args()
suite=unittest.defaultTestLoader.discover(str(HERE),pattern=args.pattern)
result=unittest.TextTestRunner(verbosity=2).run(suite)
write(HERE/'TEST_CALLS.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),calls=dict(e.COUNTS),events=e.EVENTS,scope='Synthetic/temp test fits only, separate from accepted 12 trees'))
sys.exit(not result.wasSuccessful())
