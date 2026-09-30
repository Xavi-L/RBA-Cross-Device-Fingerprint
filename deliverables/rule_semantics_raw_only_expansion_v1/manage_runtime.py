#!/usr/bin/env python3
"""Read back an owned emulator, or close this campaign's owned receiver/device."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import urllib.request


def manage(config_path, install=False, shutdown=False):
    config = json.loads(Path(config_path).read_text())
    root = Path(config['paths']['root'])
    run = Path(config['paths']['output_dir'])
    adb = [config['paths']['adb'], '-s', config['serial']]
    if shutdown:
        pid = int(re.search(r'Started server process \[(\d+)\]', (run/'receiver.log').read_text()).group(1))
        command = subprocess.run(['ps', '-p', str(pid), '-o', 'args='], text=True, capture_output=True, check=True).stdout.strip()
        if '-m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1' not in command:
            raise RuntimeError('Owned receiver identity mismatch')
        os.kill(pid, signal.SIGINT)
        emulator = subprocess.run(adb + ['emu', 'kill'], text=True, capture_output=True, timeout=20)
        for _ in range(50):
            if 'Application shutdown complete' in (run/'receiver.log').read_text():
                break
            time.sleep(0.1)
        result = {'receiver_pid':pid, 'receiver_command':command,
                  'receiver_graceful_shutdown_observed':'Application shutdown complete' in (run/'receiver.log').read_text(),
                  'emulator_serial':config['serial'], 'emulator_kill_returncode':emulator.returncode,
                  'emulator_kill_stdout':emulator.stdout, 'emulator_kill_stderr':emulator.stderr}
        filename = 'shutdown.json'
    else:
        commands = []
        if (run/'setup_commands.json').exists():
            raise FileExistsError('Setup already attempted; preserve its results')
        def execute(args):
            p = subprocess.run(args, text=True, capture_output=True, timeout=45)
            commands.append({'argv':args, 'returncode':p.returncode, 'stdout':p.stdout, 'stderr':p.stderr})
            (run/'setup_commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2)+'\n')
            if p.returncode:
                raise RuntimeError(p.stderr or p.stdout)
            return p.stdout.strip()
        if execute(adb+['shell','getprop','sys.boot_completed']) != '1':
            raise RuntimeError('Emulator not booted')
        sdk = execute(adb+['shell','getprop','ro.build.version.sdk'])
        android = execute(adb+['shell','getprop','ro.build.version.release'])
        wv = execute(adb+['shell','dumpsys','webviewupdate'])
        if install:
            execute(adb+['install',str(root/'deliverables/featureapp_webdriver_raw_v1/featureapp-1.6.5-webdriver-raw-debug.apk')])
        package = execute(adb+['shell','dumpsys','package','com.example.hybridguard.featureapp'])
        execute(adb+['reverse','tcp:8000','tcp:8000'])
        node = execute([config['paths']['node'],'--version'])
        provider = re.search(r'Current WebView package \(name, version\): \(([^,]+), ([^)]+)\)',wv)
        if not provider:
            raise RuntimeError('No identifiable WebView provider')
        version_code = int(re.search(r'versionCode=(\d+)',package).group(1))
        if version_code != 12:
            raise RuntimeError('Unexpected FeatureApp version')
        result = {'android_sdk':int(sdk), 'android_release':android, 'serial':config['serial'],
                  'webview_package':provider.group(1), 'webview_version':provider.group(2),
                  'app_code':version_code, 'app_version':re.search(r'versionName=([^\s]+)',package).group(1),
                  'node_version':node, 'new_install_performed':install,
                  'device_manifest_id':config['device_manifest_id'],
                  'receiver':'main:app --host 127.0.0.1 --port 8000 --workers 1',
                  'data_directory':str(run/'backend'), 'sources':'setup_commands.json and frozen environment registration'}
        with urllib.request.urlopen('http://127.0.0.1:8000/api/collect/readiness',timeout=10) as response:
            ready = json.load(response)
        with (run/'readiness.json').open('x') as stream:
            json.dump(ready,stream,ensure_ascii=False,indent=2)
        if ready['status'] != 'ready' or ready['collection_storage_isolated'] is not True:
            raise RuntimeError('Receiver not ready/isolated')
        filename = 'environment.json'
    result['recorded_at'] = datetime.now(timezone.utc).isoformat()
    with (run/filename).open('x') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--install',action='store_true')
    parser.add_argument('--shutdown',action='store_true')
    args = parser.parse_args()
    manage(args.config,args.install,args.shutdown)
