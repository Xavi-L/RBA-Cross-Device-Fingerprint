#!/usr/bin/env python3
"""One 72-position geometry matrix; bounded separate smoke; owned local processes."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json,os,re,shutil,signal,socket,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
SDK=Path.home()/'Library/Android/sdk';PACKAGE='com.example.hybridguard.featureapp'

def now():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text())
def write(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def available(port):
    with socket.socket() as s:return s.connect_ex(('127.0.0.1',port))!=0

def positions(settings,smoke=False):
    if smoke:return [dict(step_id=f'smoke-{kind}-{phase}',process_type=kind,round=1,phase=phase)
                     for kind in ('L1','L3') for phase in settings['phases']]
    return [dict(step_id=f'screen-{kind}-r{r}-{phase}',process_type=kind,round=r,phase=phase)
            for kind in settings['types'] for r in range(1,settings['rounds']+1) for phase in settings['phases']]

def validate_settings(s):
    if (s['model_fit_calls']!=0 or s['types']!=['L1','L2','L3','A'] or s['rounds']!=2
        or s['planned_records']!=72 or s['phases']!=['clean_pre','change','clean_post']
        or s['zoom_factor']!=1.25 or s['collector']['version_code']!=15):raise ValueError('FIXED_SCREEN_MATRIX_REQUIRED')
    expected={'width':393,'height':851,'deviceScaleFactor':2.75,'mobile':True,'screenWidth':393,'screenHeight':851,'positionX':0,'positionY':0}
    if s['screen_configuration']['cdpEmulation']['applyCommands']!=[{'method':'Emulation.setDeviceMetricsOverride','params':expected}]:raise ValueError('ORIGINAL_SCREEN_INTERVENTION_REQUIRED')
    return s

def preflight(s):
    return {'checked_at':now(),'apk_exists':(ROOT/s['collector']['apk']['path']).exists(),
       'emulator_exists':(SDK/'emulator/emulator').exists(),'receiver_python_exists':(ROOT/'backend_server/.venv-collection/bin/python').exists(),
       'node':shutil.which('node'),'ports_free':{str(p):available(p) for p in (*s['ports'].values(),s['ports']['emulator']+1)},
       'environments':[{'id':e['environment_group_id'],'avd_exists':(ROOT/e['avd_home']/(e['avd_name']+'.avd')/'config.ini').exists()} for e in s['environments']]}

def system_snapshot(cmd,adb):
    return {'accelerometer_rotation':cmd(adb+['shell','settings','get','system','accelerometer_rotation']).strip(),
            'user_rotation':cmd(adb+['shell','settings','get','system','user_rotation']).strip(),
            'input_orientation':re.findall(r'SurfaceOrientation:\s*(\d+)',cmd(adb+['shell','dumpsys','input'],required=False)),
            'observed_at':now()}

def orientation(cmd,adb,target):
    cmd(adb+['shell','settings','put','system','accelerometer_rotation','0'])
    cmd(adb+['shell','settings','put','system','user_rotation',str(target)])
    time.sleep(1.5)
    return {'status':'COMPLETED','mechanism':'system settings with actual orientation readback',
            'requested_rotation':target,'after':system_snapshot(cmd,adb)}

def restore_system(cmd,adb,original):
    try:
        for k in ('user_rotation','accelerometer_rotation'):
            cmd(adb+['shell','settings','delete','system',k] if original[k]=='null' else adb+['shell','settings','put','system',k,original[k]])
        time.sleep(1.5);after=system_snapshot(cmd,adb)
        return {'status':'RESTORED' if all(after[k]==original[k] for k in ('user_rotation','accelerometer_rotation')) else 'RESTORATION_FAILED','before':original,'after':after}
    except Exception as exc:return {'status':'RESTORATION_FAILED','error':str(exc)}

def find_raw(path,offset,context):
    matches=[]
    if path.exists():
        with path.open('rb') as stream:
            stream.seek(offset)
            for line in stream:
                if not line.endswith(b'\n'):continue
                r=json.loads(line)
                if r.get('canonical_received_payload',{}).get('collection_manifest',{}).get('runtime_context')==context:matches.append(r)
    if len(matches)>1:raise ValueError('DUPLICATE_CURRENT_RAW_SESSION')
    return matches[0] if matches else None

def launch_extras(op,s):
    zoom=op['process_type']=='L3';changed=op['phase']=='change'
    return ['--ez',PACKAGE+'.GEOMETRY_HIDE_HEADER',str(op['process_type']=='L2' and changed).lower(),
            '--ez',PACKAGE+'.GEOMETRY_ENABLE_ZOOM',str(zoom).lower(),
            '--ef',PACKAGE+'.GEOMETRY_ZOOM_FACTOR',str(s['zoom_factor'] if zoom and changed else 1.0)]

def run_environment(s,env,out,smoke=False):
    validate_settings(s)
    return run_profile_environment(s,env,out,smoke=smoke)


def run_profile_environment(s,env,out,smoke=False,profile=None):
    eid=env['environment_group_id'];run=out/'runs'/eid;run.mkdir(parents=True,exist_ok=False)
    planned = profile['positions'][eid] if profile else positions(s,smoke)
    operations=[{**p,'status':'NOT_EXECUTED','cdp_status':'NOT_EXECUTED'} for p in planned]
    life={'environment':eid,'started_at':now(),'status':'STARTED','planned':len(operations),'raw_records':0,'attempts':0,'commands':[],
          'material_role':'ENGINEERING_SMOKE' if smoke or profile else 'FROZEN_FORMAL_MATRIX'}
    def save():
        write(run/'environment.json',life)
        (run/'operations.jsonl').write_text(''.join(json.dumps(o,ensure_ascii=False)+'\n' for o in operations))
    def cmd(argv,timeout=30,required=True):
        c=subprocess.run(list(map(str,argv)),text=True,capture_output=True,timeout=timeout)
        life['commands'].append({'argv':list(map(str,argv)),'returncode':c.returncode,'stdout':c.stdout[-2500:],'stderr':c.stderr[-1000:]})
        if required and c.returncode:raise RuntimeError('Command failed: '+str(argv)+': '+c.stderr[-1000:])
        return c.stdout
    adb=[str(SDK/'platform-tools/adb'),'-s',f'emulator-{s["ports"]["emulator"]}']
    receiver=emulator=None;original=None;forward_owned=False;installation=None;save()
    try:
        if any(not available(p) for p in (*s['ports'].values(),s['ports']['emulator']+1)):raise RuntimeError('Required port occupied; no existing process touched')
        argv=[str(SDK/'emulator/emulator'),'-avd',env['avd_name'],'-port',str(s['ports']['emulator']),'-read-only','-no-window','-no-audio','-no-snapshot','-no-boot-anim','-gpu',env['gpu']]
        with (run/'emulator.log').open('x') as log:emulator=subprocess.Popen(argv,env={**os.environ,'ANDROID_SDK_ROOT':str(SDK),'ANDROID_AVD_HOME':str(ROOT/env['avd_home'])},stdout=log,stderr=subprocess.STDOUT)
        life.update(emulator_pid=emulator.pid,emulator_command=argv)
        deadline=time.monotonic()+s['limits']['boot_seconds']
        while time.monotonic()<deadline:
            if emulator.poll() is not None:raise RuntimeError('Owned emulator exited')
            if cmd(adb+['shell','getprop','sys.boot_completed'],timeout=8,required=False).strip()=='1':break
            time.sleep(1)
        else:raise TimeoutError('Boot timeout')
        api=cmd(adb+['shell','getprop','ro.build.version.sdk']).strip();provider=cmd(adb+['shell','dumpsys','webviewupdate'])
        if api!=str(env['android_api']) or f"({env['expected_webview_package']}, {env['expected_webview_version']})" not in provider:raise ValueError('Registered environment version mismatch')
        life.update(actual_android_api=api,webview_provider=provider)
        original=system_snapshot(cmd,adb);life['original_system_settings']=original
        cmd(adb+['install','-r',str(ROOT/s['collector']['apk']['path'])],timeout=60);cmd(adb+['shell','pm','clear',PACKAGE])
        package=cmd(adb+['shell','dumpsys','package',PACKAGE]);version=int(re.search(r'versionCode=(\d+)',package).group(1));name=re.search(r'versionName=(\S+)',package).group(1)
        if version!=s['collector']['version_code'] or name!=s['collector']['version_name']:raise ValueError('Installed APK version mismatch')
        life.update(app_version_code=version,app_version_name=name,registered_before_collection_at=now(),read_only_owned_avd=True);save()
        cmd(adb+['reverse','tcp:8000','tcp:'+str(s['ports']['receiver'])])
        argv=[str(ROOT/'backend_server/.venv-collection/bin/python'),'-B','-m','uvicorn','main:app','--host','127.0.0.1','--port',str(s['ports']['receiver']),'--workers','1']
        with (run/'receiver.log').open('x') as log:receiver=subprocess.Popen(argv,cwd=ROOT/'backend_server',env={**os.environ,'HYBRIDGUARD_DATA_DIR':str(run/'backend'),'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT)
        life.update(receiver_pid=receiver.pid,receiver_command=argv);deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if receiver.poll() is not None:raise RuntimeError('Receiver exited')
            if 'Application startup complete' in (run/'receiver.log').read_text():break
            time.sleep(.2)
        else:raise TimeoutError('Receiver startup')
        deadline=time.monotonic()+s['limits']['environment_seconds']
        for op in operations:
            if time.monotonic()>deadline:raise TimeoutError('Environment deadline')
            context=(profile['context_prefix'] if profile else ('screen-geometry-smoke:' if smoke else 'screen-geometry:'))+eid+':'+op['step_id']
            archive=run/'backend/raw_expanded_payloads.jsonl';offset=archive.stat().st_size if archive.exists() else 0
            op.update(started_at=now(),status='STARTED');life['attempts']+=1
            print('START',eid,op['step_id'],flush=True)
            try:
                cmd(adb+['shell','am','force-stop',PACKAGE])
                if cmd(adb+['shell','pidof',PACKAGE],required=False).strip():raise RuntimeError('Owned App did not exit')
                op['orientation_operation']=orientation(cmd,adb,1 if op['process_type']=='L1' and op['phase']=='change' else 0)
                op['system_before']=system_snapshot(cmd,adb)
                extras=launch_extras(op,s);op['host_operation_request']={'hide_header':op['process_type']=='L2' and op['phase']=='change','enable_zoom':op['process_type']=='L3','zoom_factor':s['zoom_factor'] if op['process_type']=='L3' and op['phase']=='change' else 1.0}
                cmd(adb+['shell','am','start','-S','-W','-n',PACKAGE+'/.MainActivity','--es',PACKAGE+'.COLLECT_ENDPOINT','http://127.0.0.1:8000/api/collect/fingerprint',
                    '--es',PACKAGE+'.RUNTIME_CONTEXT',context,'--ei',PACKAGE+'.COLLECTION_ROUND',str(op['round']),
                    '--es',PACKAGE+'.DEVICE_MANIFEST_ID',(profile['identity_prefix'] if profile else ('screen-geometry-smoke-' if smoke else 'screen-geometry-'))+eid,
                    *([] if op.get('control')=='default' else ['--ez',PACKAGE+'.ENABLE_WEBVIEW_DEBUG','true','--ez',PACKAGE+'.WAIT_FOR_WEBVIEW_CONTROL','true','--el',PACKAGE+'.PROBE_DELAY_MS','60000']),*extras])
                time.sleep(2.5);pids=cmd(adb+['shell','pidof',PACKAGE]).split();sockets=cmd(adb+['shell','cat','/proc/net/unix'])
                matching=[p for p in pids if 'webview_devtools_remote_'+p in sockets]
                op.update(owned_app_pid=pids[0] if len(pids)==1 else None,debug_socket_present=bool(matching))
                receipt=run/(op['step_id']+'.cdp.json')
                if op.get('control')=='default':
                    if matching:raise RuntimeError('Default launch has a debugging socket; its source is not inferred')
                    receipt_data={'version':'featureapp-default-start-v1','started_at':now(),'debug_socket_present':False,
                                  'status':'STARTED','commands':[], 'control_extras_absent':True}
                    write(receipt,receipt_data)
                    wait_deadline=time.monotonic()+60
                    while time.monotonic()<wait_deadline:
                        received=find_raw(archive,offset,context)
                        if received:break
                        time.sleep(.25)
                    else:raise TimeoutError('Default App raw upload timeout')
                    receipt_data.update(session_id=received['session_id'],raw_received_at=received['server_received_at'])
                    # Observe longer than the module's 5s overall deadline, without CDP.
                    time.sleep(6)
                    if find_raw(archive,offset,context)['session_id']!=received['session_id']:raise ValueError('Current session changed')
                    after_sockets=cmd(adb+['shell','cat','/proc/net/unix'])
                    receipt_data['debug_socket_present_after']=any('webview_devtools_remote_'+pid in after_sockets for pid in pids)
                    if receipt_data['debug_socket_present_after']:raise RuntimeError('Default launch debugging enabled')
                    receipt_data.update(status='COMPLETED',finished_at=now(),late_observation_seconds=6)
                    write(receipt,receipt_data);op.update(cdp_status='NOT_USED',cdp_receipt=receipt.name,owned_app_pid=pids[0])
                else:
                    if len(matching)!=1:raise RuntimeError('One owned debugging socket required')
                    cmd(adb+['forward','tcp:'+str(s['ports']['cdp']),'localabstract:webview_devtools_remote_'+matching[0]]);forward_owned=True
                    driver=Path(profile['fault_driver']) if profile and op.get('control')=='fault' else HERE/'screen_cdp.mjs'
                    cmd([shutil.which('node'),str(driver),'http://127.0.0.1:'+str(s['ports']['cdp']),str(receipt),'active' if op['process_type']=='A' and op['phase']=='change' else 'noop',str(archive),str(offset),context],timeout=100)
                    cdp=read(receipt);op.update(cdp_status=cdp['status'],cdp_receipt=receipt.name,cdp_rollback_status=cdp.get('rollback_status'),owned_app_pid=matching[0])
                    if cdp['status']!='COMPLETED':raise RuntimeError('CDP failed')
            except Exception as exc:op.update(status='FAILED',error=type(exc).__name__+': '+str(exc))
            finally:
                receipt=run/(op['step_id']+'.cdp.json')
                if receipt.exists():
                    cdp=read(receipt);op.update(cdp_status=cdp.get('status'),cdp_receipt=receipt.name,cdp_rollback_status=cdp.get('rollback_status'))
                raw=find_raw(archive,offset,context)
                if raw is not None:
                    p=raw['canonical_received_payload'];sid=p.get('session_id');identity=p['collection_manifest'].get('collector_install_id')
                    if sid!=raw.get('session_id') or not identity:raise ValueError('Raw session/install binding missing')
                    if installation is None:installation=identity
                    if installation!=identity:raise ValueError('Installation changed')
                    op.update(session_id=sid,raw_archive='backend/raw_expanded_payloads.jsonl',raw_byte_offset=offset,collector_install_id=identity,
                        observed_screen=p.get('web_data',{}).get('screen_layer',{}),geometry_status=p.get('collection_observations',{}).get('webview_geometry',{}).get('read_status'))
                    life['raw_records']+=1
                    if profile:
                        op['module_version']=p.get('collection_observations',{}).get('webview_geometry',{}).get('collector_version')
                        if op['module_version']!=profile['module_version']:op.update(status='FAILED',error='Actual geometry module version mismatch')
                    if op['status']!='FAILED':op['status']='COLLECTED'
                elif op['status']!='FAILED':op.update(status='FAILED',error='No current raw receipt')
                op['system_after']=system_snapshot(cmd,adb)
                cmd(adb+['shell','am','force-stop',PACKAGE],required=False);op['owned_app_process_absent_after']=not cmd(adb+['shell','pidof',PACKAGE],required=False).strip()
                if forward_owned:cmd(adb+['forward','--remove','tcp:'+str(s['ports']['cdp'])],required=False);forward_owned=False
                op['finished_at']=now();save();print(op['status'],eid,op['step_id'],op.get('session_id',''),flush=True)
        life['status']='COMPLETE' if all(o['status']=='COLLECTED' for o in operations) else 'INCOMPLETE'
    except Exception as exc:life.update(status='UNAVAILABLE_OR_INCOMPLETE',error=type(exc).__name__+': '+str(exc))
    finally:
        if original is not None and emulator is not None and emulator.poll() is None:life['final_system_restoration']=restore_system(cmd,adb,original)
        for op in operations:
            if op['status']=='NOT_EXECUTED':op.setdefault('reason',life.get('error','Not executed'))
        for process,kind in ((receiver,'receiver'),(emulator,'emulator')):
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGINT if kind=='receiver' else signal.SIGTERM)
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            life[kind+'_returncode']=process.poll() if process else None
        life.update(finished_at=now(),owned_processes_exited=all(p is None or p.poll() is not None for p in (receiver,emulator)));save()
    print('ENVIRONMENT',eid,life['status'],life.get('error',''),flush=True)
    return {k:v for k,v in life.items() if k!='commands'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=HERE);p.add_argument('--preflight',action='store_true');p.add_argument('--smoke',action='store_true')
    args=p.parse_args();out=args.output_dir.resolve();s=validate_settings(read(out/'SETTINGS.json'));check=preflight(s)
    if args.preflight:print(json.dumps(check,indent=2));return
    if args.smoke:out=out/'smoke';out.mkdir(exist_ok=False)
    else:
        freeze=read(out/'CONDITIONS_FROZEN.json')
        if freeze.get('status')!='FROZEN' or freeze.get('model_fit_calls')!=0:raise ValueError('Conditions must freeze before formal collection')
    if (out/'COLLECTION.json').exists() or (out/'runs').exists():raise FileExistsError('No automatic recollection')
    results=[];write(out/'COLLECTION.json',{'started_at':now(),'preflight':check,'smoke':args.smoke,'environments':[]})
    try:
        for e in s['environments'][:1] if args.smoke else s['environments']:
            results.append(run_environment(s,e,out,args.smoke));write(out/'COLLECTION.json',{'preflight':check,'smoke':args.smoke,'environments':results})
    finally:
        write(out/'COLLECTION.json',{'preflight':check,'finished_at':now(),'smoke':args.smoke,'environments':results,
            'planned_records':6 if args.smoke else 72,'actual_records':sum(e['raw_records'] for e in results),'model_fit_calls':0})

if __name__=='__main__':main()
