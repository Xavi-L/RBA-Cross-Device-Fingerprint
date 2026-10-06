"""Guard saved-only recount; sklearn/numpy and raw adapters must remain unloaded."""
import tempfile,sys,os
from io_utils import *
from summarize import summarize
with tempfile.TemporaryDirectory(prefix='b3a-summary-') as d:
 out=Path(d).resolve();active=True
 def guard(event,args):
  if not active:return
  if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):raise RuntimeError(event)
  if event=='open':
   path,mode,flags=args
   if isinstance(path,int):return
   p=Path(os.fsdecode(path)).resolve()
   if (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_APPEND|os.O_TRUNC):require(p.is_relative_to(out),'SUMMARY_WRITE')
   elif p.suffix in ('.json','.jsonl','.gz'):require(p.parent==HERE/'results' or p.parent==HERE/'results/summary' or p.is_relative_to(out),'SUMMARY_RAW_READ')
 def profile(frame,event,arg):
  if event=='call' and str(ROOT) in frame.f_code.co_filename:require(Path(frame.f_code.co_filename).name in ('summarize.py','io_utils.py','check_summary.py'),'SUMMARY_OTHER_EXECUTION')
 sys.addaudithook(guard);sys.setprofile(profile)
 summarize(HERE/'results',out);sys.setprofile(None)
 require(not any(n in sys.modules for n in ('sklearn','numpy','engine','source_adapter','features')),'SUMMARY_FORBIDDEN_IMPORT')
 equal={p.name:p.read_bytes()==(HERE/'results/summary'/p.name).read_bytes() for p in out.iterdir()}
 require(all(equal.values()),'SUMMARY_BYTES_CHANGED')
 active=False
 write(HERE/'results/SUMMARY_GUARD.json',dict(status='PASSED',files_equal=equal,tree_fits=0,preprocessor_fits=0,predictions=0,raw_reads=0,network_process_calls=0))
 print('Saved-only summary reproduced:',len(equal),'files')
