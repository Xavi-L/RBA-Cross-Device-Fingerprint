"""Regenerate tables/figures under no-execution guards and compare saved bytes."""
import os,sys,tempfile
from closeout_io import *
import build_tables,plot_saved

def verify():
    allowed={str(HERE/name) for name in ('closeout_io.py','build_tables.py','plot_saved.py','verify_saved_only.py')}
    repo_prefix=str(ROOT)+'/'
    runtime_prefix=str(HERE/'.plot-runtime')+'/'
    reads=set();calls=Counter()
    with tempfile.TemporaryDirectory(prefix='b3b-saved-only-') as directory:
        out=Path(directory).resolve()
        def audit(event,args):
            if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.posix_spawn'):
                raise RuntimeError('SAVED_ONLY_NETWORK_PROCESS_FORBIDDEN')
            if event=='open':
                path,mode,flags=args
                if isinstance(path,int):return
                p=Path(os.fsdecode(path)).resolve()
                if (flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                    require(p.is_relative_to(out) or p.is_relative_to(HERE/'.mplconfig'),'SAVED_ONLY_EXTERNAL_WRITE')
                elif p.is_relative_to(ROOT) and not str(p).startswith(runtime_prefix):
                    require('private_runs' not in p.parts and 'evidence_archive' not in p.parts,'SAVED_ONLY_RAW_READ')
                    reads.add(str(p.relative_to(ROOT)))
        def profile(frame,event,arg):
            if event!='call':return
            path=frame.f_code.co_filename
            if not path.startswith(repo_prefix) or path.startswith(runtime_prefix):return
            require(path in allowed,'SAVED_ONLY_EXECUTION_FORBIDDEN:'+path)
            if frame.f_code.co_name in ('build','plot'):calls[frame.f_code.co_name]+=1
        sys.addaudithook(audit);sys.setprofile(profile)
        build_tables.build(out/'tables');plot_saved.plot(out/'tables',out/'figures')
        sys.setprofile(None)
        compared=[]
        for section in ('tables','figures'):
            old={p.name:p for p in (HERE/section).iterdir() if p.is_file()}
            new={p.name:p for p in (out/section).iterdir() if p.is_file()}
            require(old.keys()==new.keys(),'REBUILD_FILE_SET')
            for name,p in new.items():
                require(p.read_bytes()==old[name].read_bytes(),'REBUILD_BYTE_DIFFERENCE:'+name)
                compared.append(section+'/'+name)
        result=dict(status='PASSED',files=sorted(compared),calls=dict(calls),selection=0,prediction=0,timing=0,fit=0,collection=0,
            repository_reads=sorted(reads),verification='Saved-only runtime call guard; no raw read or historical write; exact byte equality including SVG and PNG')
        # The guard permits temporary output only; publish after this process via stdout.
        print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':verify()
