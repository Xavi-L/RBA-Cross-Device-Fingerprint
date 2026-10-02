#!/usr/bin/env python3
"""72 fixed positions on owned read-only AVD instances; never fit a model."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
SDK=Path.home()/'Library/Android/sdk'
PACKAGE='com.example.hybridguard.featureapp'


def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())
def write(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def append(p,obj):
    with Path(p).open('a') as stream:stream.write(json.dumps(obj,ensure_ascii=False)+'\n')


def positions(settings):
    return [{'step_id':f'memory-{target}-r{number}-{phase}','target_gib':target,'round':number,'phase':phase}
        for target in settings['targets_gib'] for number in range(1,settings['rounds']+1) for phase in settings['phases']]


def available(port):
    with socket.socket() as sock:
        return sock.connect_ex(('127.0.0.1',port))!=0


def preflight(settings):
    return {'checked_at':now(),'emulator':str(SDK/'emulator/emulator'),'adb':str(SDK/'platform-tools/adb'),
            'node':shutil.which('node'),'receiver_python_exists':(ROOT/'backend_server/.venv-collection/bin/python').exists(),
            'apk_exists':(ROOT/settings['collector']['apk']['path']).exists(),
            'environments':[{'environment_id':e['environment_group_id'],
                'avd_config_exists':(ROOT/e['avd_home']/(e['avd_name']+'.avd')/'config.ini').exists(),
                'previous_webview_version':e['expected_webview_version'],
                'actual_provider_registration':'before first position, after owned boot'} for e in settings['environments']],
            'ports_free':{str(p):available(p) for p in (*settings['ports'].values(),settings['ports']['emulator']+1)},
            'planned_per_environment':len(positions(settings)), 'fixed_settings_at':settings['fixed_at']}


def run_environment(settings, env, out):
    eid=env['environment_group_id'];run=out/'runs'/eid;run.mkdir(parents=True,exist_ok=False)
    record={'environment':eid,'started_at':now(),'status':'STARTED','planned':len(positions(settings)),
            'attempts':0,'raw_records':0,'commands':[]}
    life=run/'environment.json';write(life,record)
    adb=[str(SDK/'platform-tools/adb'),'-s',f'emulator-{settings["ports"]["emulator"]}']
    receiver=emulator=None
    forward_owned=False
    def command(argv,timeout=30,required=True):
        completed=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=timeout)
        record['commands'].append({'argv':list(map(str,argv)),'returncode':completed.returncode})
        if required and completed.returncode:
            raise RuntimeError('Command failed: '+str(argv)+': '+completed.stderr[-1000:])
        return completed.stdout
    try:
        if any(not available(p) for p in (*settings['ports'].values(),settings['ports']['emulator']+1)):
            raise RuntimeError('Required port occupied; do not touch existing services')
        args=[str(SDK/'emulator/emulator'),'-avd',env['avd_name'],'-port',str(settings['ports']['emulator']),
              '-read-only','-no-window','-no-audio','-no-snapshot','-no-boot-anim','-gpu',env['gpu']]
        with (run/'emulator.log').open('x') as log:
            emulator=subprocess.Popen(args,env={**os.environ,'ANDROID_SDK_ROOT':str(SDK),
                      'ANDROID_AVD_HOME':str(ROOT/env['avd_home'])},stdout=log,stderr=subprocess.STDOUT)
        record.update(emulator_pid=emulator.pid,emulator_command=args)
        deadline=time.monotonic()+settings['limits']['boot_seconds']
        while time.monotonic()<deadline:
            if emulator.poll() is not None:raise RuntimeError('Owned emulator exited during boot')
            boot=command(adb+['shell','getprop','sys.boot_completed'],timeout=8,required=False).strip()
            if boot=='1':break
            time.sleep(1)
        else:raise TimeoutError('Owned emulator boot timeout')
        api=command(adb+['shell','getprop','ro.build.version.sdk']).strip()
        if api!=str(env['android_api']):raise ValueError('Unexpected Android API; no substitution')
        provider=command(adb+['shell','dumpsys','webviewupdate'])
        record.update(actual_android_api=api,webview_provider=provider)
        if f"({env['expected_webview_package']}, {env['expected_webview_version']})" not in provider:
            raise ValueError('WebView differs from registered environment')
        command(adb+['install','-r',str(ROOT/settings['collector']['apk']['path'])],timeout=60)
        command(adb+['shell','pm','clear',PACKAGE]) # owned read-only instance only
        package=command(adb+['shell','dumpsys','package',PACKAGE])
        record['app_version_code']=int(re.search(r'versionCode=(\d+)',package).group(1))
        record['app_version_name']=re.search(r'versionName=(\S+)',package).group(1)
        if record['app_version_code']!=14 or record['app_version_name']!=settings['collector']['version_name']:
            raise ValueError('Unexpected installed App version')
        record.update(registered_before_collection_at=now(),read_only_owned_avd=True)
        write(life,record)
        command(adb+['reverse','tcp:8000','tcp:8000'])
        args=[str(ROOT/'backend_server/.venv-collection/bin/python'),'-B','-m','uvicorn','main:app',
              '--host','127.0.0.1','--port','8000','--workers','1']
        with (run/'receiver.log').open('x') as log:
            receiver=subprocess.Popen(args,cwd=ROOT/'backend_server',env={**os.environ,
                'HYBRIDGUARD_DATA_DIR':str(run/'backend'),'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
        record.update(receiver_pid=receiver.pid,receiver_command=args)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if receiver.poll() is not None:raise RuntimeError('Owned receiver exited')
            if 'Application startup complete' in (run/'receiver.log').read_text():break
            time.sleep(0.2)
        else:raise TimeoutError('Receiver startup timeout')
        installation=None
        environment_deadline=time.monotonic()+settings['limits']['environment_seconds']
        for step in positions(settings):
            if time.monotonic()>environment_deadline:raise TimeoutError('Environment limit')
            if receiver.poll() is not None or emulator.poll() is not None:raise RuntimeError('Owned runtime exited')
            operation={**step,'started_at':now(),'status':'STARTED','cdp_status':'NOT_EXECUTED'}
            record['attempts']+=1
            stepid=step['step_id'];context='memory-validation:'+eid+':'+stepid
            archive=run/'backend/raw_expanded_payloads.jsonl'
            offset=archive.stat().st_size if archive.exists() else 0
            print('START',eid,stepid,flush=True)
            try:
                command(adb+['shell','am','force-stop',PACKAGE])
                # Process absence is the actual removal of the previous realm.
                oldpid=command(adb+['shell','pidof',PACKAGE],required=False).strip()
                if oldpid:raise RuntimeError('Old App process remains alive')
                command(adb+['shell','am','start','-S','-W','-n',PACKAGE+'/.MainActivity',
                     '--es',PACKAGE+'.COLLECT_ENDPOINT','http://127.0.0.1:8000/api/collect/fingerprint',
                     '--es',PACKAGE+'.RUNTIME_CONTEXT',context,'--ei',PACKAGE+'.COLLECTION_ROUND',str(step['round']),
                     '--es',PACKAGE+'.DEVICE_MANIFEST_ID','memory-validation-'+eid,
                     '--ez',PACKAGE+'.ENABLE_WEBVIEW_DEBUG','true',
                     '--ez',PACKAGE+'.WAIT_FOR_WEBVIEW_CONTROL','true','--el',PACKAGE+'.PROBE_DELAY_MS','60000'])
                time.sleep(2.5)
                pids=command(adb+['shell','pidof',PACKAGE]).strip().split()
                sockets=command(adb+['shell','cat','/proc/net/unix'])
                matching=[p for p in pids if f'webview_devtools_remote_{p}' in sockets]
                if len(matching)!=1:raise RuntimeError('No unique owned App debugging socket')
                command(adb+['forward','tcp:9222','localabstract:webview_devtools_remote_'+matching[0]])
                forward_owned=True
                receipt=run/(stepid+'.cdp.json')
                command([shutil.which('node'),str(HERE/'memory_only_cdp.mjs'),'http://127.0.0.1:9222',str(receipt),
                         str(step['target_gib']) if step['phase']=='attack' else 'noop'],timeout=60)
                cdp=read(receipt);operation['cdp_status']=cdp['status'];operation['cdp_receipt']=receipt.name
                deadline=time.monotonic()+40
                while time.monotonic()<deadline:
                    fresh=[]
                    if archive.exists():
                        with archive.open('rb') as stream:
                            stream.seek(offset)
                            for line in stream:
                                if not line.endswith(b'\n'):continue
                                raw=json.loads(line);p=raw.get('canonical_received_payload',{})
                                if p.get('collection_manifest',{}).get('runtime_context')==context:fresh.append(raw)
                    if len(fresh)>1:raise RuntimeError('Multiple current raw payloads')
                    if len(fresh)==1:break
                    time.sleep(0.25)
                else:raise TimeoutError('No raw payload for planned position')
                raw=fresh[0];payload=raw['canonical_received_payload'];sid=payload['session_id']
                manifest=payload['collection_manifest'];identity=manifest.get('collector_install_id')
                if raw['session_id']!=sid or not identity:raise ValueError('Raw session/installation missing')
                if installation is None:installation=identity
                if installation!=identity:raise ValueError('App installation changed')
                operation.update(status='COLLECTED',session_id=sid,raw_archive='backend/raw_expanded_payloads.jsonl',
                       raw_byte_offset=offset,collector_install_id=identity,owned_app_pid=matching[0])
                record['raw_records']+=1
                print('COLLECTED',eid,stepid,sid,flush=True)
            except Exception as exc:
                operation.update(status='FAILED',error=type(exc).__name__+': '+str(exc))
                # Preserve a receipt/arrived raw row even if operation failed.
                receipt=run/(stepid+'.cdp.json')
                if receipt.exists():operation.update(cdp_status=read(receipt).get('status'),cdp_receipt=receipt.name)
            finally:
                command(adb+['shell','am','force-stop',PACKAGE],required=False)
                operation['owned_app_process_absent_after']=not command(adb+['shell','pidof',PACKAGE],required=False).strip()
                if forward_owned:
                    command(adb+['forward','--remove','tcp:9222'],required=False);forward_owned=False
                operation['finished_at']=now();append(run/'operations.jsonl',operation);write(life,record)
            if operation['status']=='FAILED':raise RuntimeError('Stop environment after failed position; no automatic retry')
        record['status']='COMPLETE'
    except Exception as exc:
        record.update(status='UNAVAILABLE_OR_INCOMPLETE',error=type(exc).__name__+': '+str(exc))
    finally:
        for process,kind in ((receiver,'receiver'),(emulator,'emulator')):
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGINT if kind=='receiver' else signal.SIGTERM)
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            record[kind+'_returncode']=process.poll() if process else None
        record.update(finished_at=now(),owned_processes_exited=all(p is None or p.poll() is not None for p in (receiver,emulator)))
        write(life,record)
    print('ENVIRONMENT',eid,record['status'],record.get('error',''),flush=True)
    return {k:v for k,v in record.items() if k!='commands'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=HERE)
    parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args();out=args.output_dir.resolve();settings=read(out/'SETTINGS.json')
    if settings['targets_gib']!=[2,4,8,16] or settings['rounds']!=2 or settings['model_training_calls']!=0:
        raise ValueError('Fixed bounded experiment required')
    check=preflight(settings)
    if args.preflight:print(json.dumps(check,ensure_ascii=False,indent=2));return
    if (out/'COLLECTION.json').exists() or (out/'runs').exists():raise FileExistsError('No automatic recollection')
    write(out/'COLLECTION.json',{'started_at':now(),'preflight':check,'environments':[]})
    results=[]
    try:
        for env in settings['environments']:
            results.append(run_environment(settings,env,out))
            write(out/'COLLECTION.json',{'preflight':check,'environments':results,'planned_records':72,'model_fit_calls':0})
    finally:
        write(out/'COLLECTION.json',{'preflight':check,'environments':results,'finished_at':now(),
              'planned_records':72,'actual_records':sum(r['raw_records'] for r in results),'model_fit_calls':0})


if __name__=='__main__':main()
