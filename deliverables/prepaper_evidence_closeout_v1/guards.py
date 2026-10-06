"""Bound writes and prohibit fit/acquisition; profile is never used inside timings."""
import os,sys
from collections import Counter
from closeout_io import HERE,ROOT,B2C,B3A,Path,require

def audit_guard(output):
    output=Path(output).resolve()
    def audit(event,args):
        if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):
            raise RuntimeError('NO_NETWORK_OR_PROCESS:'+event)
        if event=='open':
            p,mode,flags=args
            if not isinstance(p,int) and (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                require(Path(os.fsdecode(p)).resolve().is_relative_to(output),'WRITE_OUTSIDE_OUTPUT')
    sys.addaudithook(audit)

def profile_calls(allow_selection=False):
    calls=Counter()
    def profile(frame,event,arg):
        if event!='call':return
        path=frame.f_code.co_filename;name=frame.f_code.co_name
        if not path.startswith(str(ROOT)):return
        if name=='fit' or name.startswith('fit_') or name in ('train','prepare_fold','collect'):
            raise RuntimeError('FIT_OR_COLLECTION_FORBIDDEN:'+name)
        if path==str(B2C/'selector.py') and name in ('select','score'):
            require(allow_selection,'RESELECTION_FORBIDDEN');calls[name]+=1
        if path==str(B2C/'selector.py') and name=='combine':calls['state_combinations']+=1
    sys.setprofile(profile)
    return calls
