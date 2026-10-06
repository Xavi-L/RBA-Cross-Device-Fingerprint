"""Guard one complete current-stage evaluation; record actual calls and writes."""
import argparse,os,sys
from collections import Counter
from pathlib import Path
sys.dont_write_bytecode=True
import evaluate as e
def reproduce(directory):
    run=Path(directory).resolve();out=run/'evaluation';counts=Counter();writes=set();violations=[]
    def deny(reason):violations.append(reason);raise RuntimeError(reason)
    def profile(frame,event,arg):
        if event!='call':return
        file=frame.f_code.co_filename;name=frame.f_code.co_name
        if not file.startswith(str(e.ROOT)+os.sep):return
        if name=='fit' or name.startswith('fit_') or name in ['train','prepare_fold','collect']:deny('FORBIDDEN_CALL:'+name)
        if file.endswith('/mtc_timezone_selection.py') and name=='predict_current':counts['actual_model_calls']+=1
        if file==str(e.b2.HERE/'conditions.py') and name=='evaluate':counts['actual_condition_calls']+=1
    def audit(event,args):
        if event in ['subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind']:deny('FORBIDDEN_PROCESS_OR_NETWORK:'+event)
        if event=='open':
            path,mode,flags=args
            if not isinstance(path,int) and (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                p=Path(os.fsdecode(path)).resolve()
                if not p.is_relative_to(out):deny('WRITE_OUTSIDE_OUTPUT:'+str(p))
                writes.add(str(p.relative_to(out)))
        if event in ['os.mkdir','os.remove','os.rmdir','os.rename']:
            for p in (args[:2] if event=='os.rename' else args[:1]):
                if not Path(os.fsdecode(p)).resolve().is_relative_to(out):deny('MUTATION_OUTSIDE_OUTPUT')
    sys.addaudithook(audit);sys.setprofile(profile)
    try:e.run(run)
    finally:sys.setprofile(None)
    assert counts['actual_condition_calls']==210 and counts['actual_model_calls']<=126
    e.write(out/'RUNTIME_AUDIT.json',{'status':'PASSED','actual_calls':dict(counts),'fit_calls':0,'prohibited_operations':violations,'writes':sorted(writes),'scope':'Current App only / current pair only; no collection, subprocess, network, training, or writes to history.'})
    print(dict(counts))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_directory');reproduce(p.parse_args().run_directory)
