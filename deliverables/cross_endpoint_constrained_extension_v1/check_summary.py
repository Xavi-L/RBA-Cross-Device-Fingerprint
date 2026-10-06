"""Prove saved-only recount has no selection, prediction, collection, or raw reads."""
import os,sys,tempfile
from common import *
from summarize import summarize
with tempfile.TemporaryDirectory(prefix='b2c-summary-') as d:
    out=Path(d).resolve();events=[]
    def guard(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):raise RuntimeError(event)
        if event=='open':
            path,mode,flags=args
            if isinstance(path,int):return
            p=Path(os.fsdecode(path)).resolve()
            if (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                if not p.is_relative_to(out) and p!=HERE/'results/SUMMARY_GUARD.json':raise RuntimeError('WRITE_OUTSIDE_SUMMARY')
            elif p.suffix in ('.json','.jsonl','.gz') and p.parent!=HERE/'results' and not p.is_relative_to(HERE/'results/summary') and not p.is_relative_to(out):raise RuntimeError('NON_SAVED_INPUT_READ:'+str(p))
    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_filename.startswith(str(ROOT)):
            path=frame.f_code.co_filename
            if Path(path).name not in ('check_summary.py','summarize.py','common.py'):raise RuntimeError('SUMMARY_EXECUTED_OTHER_CODE:'+path)
    sys.addaudithook(guard);sys.setprofile(profile)
    summarize(HERE/'results',out)
    sys.setprofile(None)
    names=['summary.json','summary.csv','intersections.json','denominators.json']
    equal={n:(out/n).read_bytes()==(HERE/'results/summary'/n).read_bytes() for n in names}
    require(all(equal.values()),'SUMMARY_REPRODUCTION_MISMATCH')
    write(HERE/'results/SUMMARY_GUARD.json',dict(status='PASSED',files_equal=equal,new_learning_calls=0,prediction_calls=0,raw_reads=0,network_process_calls=0))
    print('Saved-only recount:',equal)
