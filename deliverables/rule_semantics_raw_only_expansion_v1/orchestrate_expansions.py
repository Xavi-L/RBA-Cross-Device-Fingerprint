#!/usr/bin/env python3
"""Sequential owned-emulator campaigns; per-environment failure stops, no retries."""
import json
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
SDK=Path('/Users/xavier/Library/Android/sdk')
ENVIRONMENTS={
    30:(HERE/'runtime/avd','Codex_Webdriver_Raw_API30'),
    29:(ROOT/'deliverables/featureapp_webdriver_raw_multienv_v1/runtime/avd','Codex_Webdriver_Raw_API29'),
    36:(ROOT/'deliverables/featureapp_webdriver_runtime_v1/runtime/avd','Codex_Webdriver_Raw_API36_1'),
}


def now():return datetime.now(timezone.utc).isoformat()


def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def run_environment(api,stage='expand12'):
    config_path=HERE/f'protocol_api{api}_{stage}.json'
    config=json.loads(config_path.read_text());run=Path(config['paths']['output_dir'])
    prior=ROOT/config['source_campaign']
    if json.loads((prior/'SUMMARY.json').read_text())['status']!='COMPLETE':
        raise ValueError('Source minimal campaign must be complete')
    if (run/'LIFECYCLE.json').exists():raise FileExistsError('No repeat of an attempted environment')
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8000))==0:raise RuntimeError('Receiver port already in use')
    avd_home,avd_name=ENVIRONMENTS[api]
    port=config['serial'].split('-')[-1]
    record={'api':api,'started_at':now(),'status':'STARTED','commands':[]}
    write(run/'LIFECYCLE.json',record)
    emulator=receiver=None
    def call(args,name,timeout=60):
        with (run/name).open('x') as output:
            result=subprocess.run(args,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
        record['commands'].append({'argv':list(map(str,args)),'returncode':result.returncode,'log':name})
        write(run/'LIFECYCLE.json',record)
        if result.returncode:raise RuntimeError(name+': command failed')
    try:
        env={**os.environ,'ANDROID_AVD_HOME':str(avd_home),'ANDROID_SDK_ROOT':str(SDK)}
        with (run/'emulator.log').open('x') as log:
            emulator=subprocess.Popen([str(SDK/'emulator/emulator'),'-avd',avd_name,'-port',port,'-no-window','-no-audio','-no-snapshot','-no-boot-anim','-gpu','swiftshader_indirect'],env=env,stdout=log,stderr=subprocess.STDOUT)
        record['emulator_pid']=emulator.pid
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if emulator.poll() is not None:raise RuntimeError('Emulator exited during boot')
            boot=subprocess.run([config['paths']['adb'],'-s',config['serial'],'shell','getprop','sys.boot_completed'],capture_output=True,text=True,timeout=5)
            if boot.stdout.strip()=='1':break
            time.sleep(1)
        else:raise TimeoutError('Emulator boot timeout')
        with (run/'receiver.log').open('x') as log:
            receiver=subprocess.Popen([str(ROOT/'backend_server/.venv-collection/bin/python'),'-B','-m','uvicorn','main:app','--host','127.0.0.1','--port','8000','--workers','1'],cwd=ROOT/'backend_server',env={**os.environ,'HYBRIDGUARD_DATA_DIR':str(run/'backend'),'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
        record['receiver_pid']=receiver.pid;write(run/'LIFECYCLE.json',record)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if receiver.poll() is not None:raise RuntimeError('Receiver startup failed')
            if 'Application startup complete' in (run/'receiver.log').read_text():break
            time.sleep(0.2)
        else:raise TimeoutError('Receiver startup timeout')
        call([sys.executable,'-B',str(HERE/'manage_runtime.py'),'--config',str(config_path)],'setup-console.log')
        call([sys.executable,'-B',str(HERE/'run_expansion.py'),'--config',str(config_path),'--stage','smoke'],'smoke-console.log',120)
        call([sys.executable,'-B',str(HERE/'run_expansion.py'),'--config',str(config_path),'--stage','campaign'],'campaign-console.log',2100)
        record['status']='COMPLETE'
    except Exception as error:
        record.update(status='FAILED_OR_INCOMPLETE',error=str(error))
    finally:
        if receiver is not None and receiver.poll() is None:
            receiver.send_signal(signal.SIGINT)
            try:receiver.wait(timeout=15)
            except subprocess.TimeoutExpired:
                receiver.terminate();receiver.wait(timeout=5)
        if emulator is not None and emulator.poll() is None:
            closed=subprocess.run([config['paths']['adb'],'-s',config['serial'],'emu','kill'],capture_output=True,text=True,timeout=15)
            record['emulator_kill']={'returncode':closed.returncode,'stdout':closed.stdout,'stderr':closed.stderr}
            try:emulator.wait(timeout=20)
            except subprocess.TimeoutExpired:
                emulator.terminate();emulator.wait(timeout=5)
        record.update(finished_at=now(),receiver_returncode=receiver.returncode if receiver else None,
                      emulator_returncode=emulator.returncode if emulator else None,
                      receiver_graceful_shutdown_observed=receiver is not None and 'Application shutdown complete' in (run/'receiver.log').read_text())
        write(run/'LIFECYCLE.json',record)
    print(json.dumps({'api':api,'status':record['status'],'error':record.get('error')},ensure_ascii=False),flush=True)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('expand12','repair4','fresh4'),default='expand12')
    args=parser.parse_args()
    prefix={'expand12':'EXPANSIONS','repair4':'REPAIRED_EXPANSIONS','fresh4':'FRESH_LAUNCH_EXPANSION'}[args.stage]
    if args.stage=='repair4' and not (HERE/'EXPANSIONS_FINISHED.json').exists():
        raise RuntimeError('Original campaigns must finish before separate amended attempts')
    if args.stage=='fresh4' and not (HERE/'REPAIRED_EXPANSIONS_FINISHED.json').exists():
        raise RuntimeError('Repaired campaigns must finish before fresh-launch amendment')
    order=(36,) if args.stage=='fresh4' else (30,29,36)
    with (HERE/f'{prefix}_STARTED.json').open('x') as stream:
        json.dump({'at':now(),'order':list(order),'retry_policy':'NONE'},stream)
    results=[run_environment(api,args.stage) for api in order]
    write(HERE/f'{prefix}_FINISHED.json',{'finished_at':now(),'environments':results})
