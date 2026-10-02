#!/usr/bin/env python3
"""36 fixed positions on owned read-only AVDs; existing six models frozen first."""
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

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SDK = Path.home() / 'Library/Android/sdk'
PACKAGE = 'com.example.hybridguard.featureapp'
TARGETS = ['UTC', 'America/Los_Angeles']
PHASES = ['clean_pre', 'change', 'clean_post']
ENVIRONMENTS = ['api29_swiftshader', 'api30_swiftshader', 'api36_swiftshader']


def now(): return datetime.now(timezone.utc).isoformat()
def read(path): return json.loads(Path(path).read_text())
def write(path, obj): Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def positions(settings):
    return [{'step_id': f'timezone-{target.replace("/", "_")}-{kind}-{phase}',
             'target_timezone': target, 'process_type': kind, 'phase': phase, 'round': 1}
            for target in settings['targets_timezone'] for kind in settings['types'] for phase in settings['phases']]


def collection_settings(settings):
    """Permit the main experiment to nest this bounded collection configuration."""
    return settings.get('local_collection', settings)


def validate_settings(settings):
    settings = collection_settings(settings)
    if (settings['targets_timezone'] != TARGETS or settings['types'] != ['L', 'A'] or
            settings['phases'] != PHASES or settings['rounds'] != 1 or
            settings['planned_records'] != 36 or settings.get('attempts_per_position', 1) != 1 or
            [e['environment_group_id'] for e in settings['environments']] != ENVIRONMENTS or
            settings['collector']['version_code'] != 14):
        raise ValueError('Fixed 36-position experiment required; no new environments or retries')
    return settings


def require_frozen(out):
    frozen = read(out / 'MODELS_FROZEN.json')
    if frozen.get('status') != 'FROZEN' or frozen.get('actual_fit_calls') != 6:
        raise ValueError('The six fits must finish before boot/collection')
    if (len(frozen.get('baseline_model_ids', [])) != 3 or len(frozen.get('new_model_ids', [])) != 3 or
            len(set(frozen.get('baseline_model_ids', []) + frozen.get('new_model_ids', []))) != 6):
        raise ValueError('Three saved B_REL and three final B_REL_TZ model IDs required')
    if not frozen.get('frozen_at'):
        raise ValueError('Missing candidate and model freeze time')
    return frozen


def available(port):
    with socket.socket() as sock:
        return sock.connect_ex(('127.0.0.1', port)) != 0


def preflight(settings):
    settings = validate_settings(settings)
    return {'checked_at': now(), 'emulator': str(SDK / 'emulator/emulator'),
            'adb': str(SDK / 'platform-tools/adb'), 'node': shutil.which('node'),
            'receiver_python_exists': (ROOT / 'backend_server/.venv-collection/bin/python').exists(),
            'apk_exists': (ROOT / settings['collector']['apk']['path']).exists(),
            'environments': [{'environment_id': e['environment_group_id'],
                'avd_config_exists': (ROOT / e['avd_home'] / (e['avd_name'] + '.avd') / 'config.ini').exists(),
                'registered_webview_version': e['expected_webview_version']} for e in settings['environments']],
            'ports_free': {str(p): available(p) for p in (*settings['ports'].values(), settings['ports']['emulator'] + 1)},
            'planned_per_environment': len(positions(settings)), 'read_only': True}


def timezone_snapshot(command, adb):
    return {'timezone_id': command(adb + ['shell', 'getprop', 'persist.sys.timezone']).strip(),
            'auto_time_zone': command(adb + ['shell', 'settings', 'get', 'global', 'auto_time_zone']).strip(),
            'device_date': command(adb + ['shell', 'date', '+%s,%z,%Z']).strip(), 'observed_at': now()}


def set_zone(command, adb, zone):
    # Service invokes AlarmManager.setTimeZone (updates zone and broadcasts), not setprop.
    output = command(adb + ['shell', 'cmd', 'alarm', 'set-timezone', zone])
    time.sleep(1.5)
    actual = timezone_snapshot(command, adb)
    if actual['timezone_id'] != zone:
        raise RuntimeError(f'System zone not applied: expected {zone}, observed {actual["timezone_id"]}')
    return {'mechanism': 'cmd alarm set-timezone', 'output': output, 'requested_zone': zone,
            'status': 'COMPLETED', 'after': actual}


def restore_original(command, adb, original, supported):
    evidence = {'started_at': now(), 'original': original, 'status': 'STARTED'}
    try:
        if supported:
            evidence['zone_restore'] = set_zone(command, adb, original['timezone_id'])
        if original['auto_time_zone'] == 'null':
            command(adb + ['shell', 'settings', 'delete', 'global', 'auto_time_zone'])
        else:
            command(adb + ['shell', 'settings', 'put', 'global', 'auto_time_zone', original['auto_time_zone']])
        time.sleep(1.5)
        evidence['after'] = timezone_snapshot(command, adb)
        evidence['status'] = 'RESTORED' if all(evidence['after'][k] == original[k]
                          for k in ('timezone_id', 'auto_time_zone')) else 'RESTORATION_FAILED'
    except Exception as exc:
        evidence.update(status='RESTORATION_FAILED', error=type(exc).__name__ + ': ' + str(exc))
    evidence['finished_at'] = now()
    return evidence


def find_raw(archive, offset, context):
    rows = []
    if archive.exists():
        with archive.open('rb') as stream:
            stream.seek(offset)
            for line in stream:
                if not line.endswith(b'\n'): continue
                raw = json.loads(line)
                if raw.get('canonical_received_payload', {}).get('collection_manifest', {}).get('runtime_context') == context:
                    rows.append(raw)
    if len(rows) > 1: raise RuntimeError('Multiple raw payloads for one fixed position')
    return rows[0] if rows else None


def timezone_observation(raw):
    p = raw['canonical_received_payload']
    n = p.get('android_native_data', {}).get('locale_timezone_layer', {})
    w = p.get('web_data', {}).get('execution_layer', {})
    return {'native_timezone_id': n.get('native_timezone_id'),
            'native_timezone_offset_min': n.get('native_timezone_offset_min'),
            'web_timezone_id': w.get('timezone_id'), 'web_timezone_offset': w.get('timezone_offset')}


def trio_evidence(steps, restoration):
    """Flow facts, independent of candidate/model decisions and target labels."""
    pre, mid, post = steps
    obs = [s.get('observed_timezone') for s in steps]
    complete = all(s.get('status') == 'COLLECTED' for s in steps)
    evidence = {'process_type': mid['process_type'], 'target_timezone': mid['target_timezone'],
                'step_ids': [s['step_id'] for s in steps], 'position_statuses': [s['status'] for s in steps],
                'execution': 'COMPLETED' if mid.get('cdp_status') == 'COMPLETED' and
                    (mid['process_type'] == 'A' or mid.get('system_change', {}).get('status') == 'COMPLETED') else 'FAILED_OR_NOT_EXECUTED',
                'effect': 'MISSING_OBSERVATION', 'recovery': 'MISSING_OBSERVATION',
                'setting_restoration': restoration.get('status'), 'observations': obs}
    if all(isinstance(o, dict) and all(v is not None for v in o.values()) for o in obs):
        nkeys = ('native_timezone_id', 'native_timezone_offset_min')
        wkeys = ('web_timezone_id', 'web_timezone_offset')
        native_changed = any(obs[0][k] != obs[1][k] for k in nkeys)
        web_changed = any(obs[0][k] != obs[1][k] for k in wkeys)
        evidence.update(native_changed=native_changed, web_changed=web_changed,
            effect='OBSERVABLE_CHANGE' if web_changed else 'NO_OBSERVABLE_EFFECT',
            recovery='RESTORED' if obs[0] == obs[2] else 'RECOVERY_FAILED',
            system_unchanged=all(s.get('system_before', {}).get('timezone_id') == pre.get('system_before', {}).get('timezone_id')
                                 and s.get('system_after', {}).get('timezone_id') == pre.get('system_before', {}).get('timezone_id') for s in steps))
        if mid['process_type'] == 'A' and (native_changed or not evidence['system_unchanged']):
            evidence['confounded'] = True
        else: evidence['confounded'] = False
    evidence['all_positions_collected'] = complete
    return evidence


def run_environment(settings, env, out):
    eid = env['environment_group_id']; run = out / 'runs' / eid; run.mkdir(parents=True, exist_ok=False)
    record = {'environment': eid, 'started_at': now(), 'status': 'STARTED', 'planned': 12,
              'attempts': 0, 'raw_records': 0, 'commands': []}
    life = run / 'environment.json'; write(life, record)
    plan = positions(settings)
    operations = [{**s, 'status': 'NOT_EXECUTED', 'cdp_status': 'NOT_EXECUTED'} for s in plan]
    trios = []
    def save_operations():
        (run / 'operations.jsonl').write_text(''.join(json.dumps(o, ensure_ascii=False) + '\n' for o in operations))
        write(run / 'trios.json', trios)
    save_operations()
    adb = [str(SDK / 'platform-tools/adb'), '-s', f'emulator-{settings["ports"]["emulator"]}']
    receiver = emulator = None
    forward_owned = False; original = None; system_supported = False; installation = None
    def command(argv, timeout=30, required=True):
        completed = subprocess.run(list(map(str, argv)), capture_output=True, text=True, timeout=timeout)
        record['commands'].append({'argv': list(map(str, argv)), 'returncode': completed.returncode,
                                   'stdout': completed.stdout[-2000:], 'stderr': completed.stderr[-1000:]})
        if required and completed.returncode:
            raise RuntimeError('Command failed: ' + str(argv) + ': ' + completed.stderr[-1000:])
        return completed.stdout
    try:
        if any(not available(p) for p in (*settings['ports'].values(), settings['ports']['emulator'] + 1)):
            raise RuntimeError('Required port occupied; existing processes are not touched')
        args = [str(SDK / 'emulator/emulator'), '-avd', env['avd_name'], '-port', str(settings['ports']['emulator']),
                '-read-only', '-no-window', '-no-audio', '-no-snapshot', '-no-boot-anim', '-gpu', env['gpu']]
        with (run / 'emulator.log').open('x') as log:
            emulator = subprocess.Popen(args, env={**os.environ, 'ANDROID_SDK_ROOT': str(SDK),
                'ANDROID_AVD_HOME': str(ROOT / env['avd_home'])}, stdout=log, stderr=subprocess.STDOUT)
        record.update(emulator_pid=emulator.pid, emulator_command=args)
        deadline = time.monotonic() + settings['limits']['boot_seconds']
        while time.monotonic() < deadline:
            if emulator.poll() is not None: raise RuntimeError('Owned emulator exited during boot')
            if command(adb + ['shell', 'getprop', 'sys.boot_completed'], timeout=8, required=False).strip() == '1': break
            time.sleep(1)
        else: raise TimeoutError('Owned emulator boot timeout')
        api = command(adb + ['shell', 'getprop', 'ro.build.version.sdk']).strip()
        if api != str(env['android_api']): raise ValueError('Unexpected API; no environment substitution')
        provider = command(adb + ['shell', 'dumpsys', 'webviewupdate'])
        record.update(actual_android_api=api, webview_provider=provider)
        if f"({env['expected_webview_package']}, {env['expected_webview_version']})" not in provider:
            raise ValueError('WebView differs from registered environment')
        original = timezone_snapshot(command, adb)
        if not original['timezone_id']: raise ValueError('Cannot safely restore empty original system timezone')
        record['original_system_settings'] = original
        alarm_help = command(adb + ['shell', 'cmd', 'alarm', 'help'], required=False)
        system_supported = 'set-timezone' in alarm_help
        record.update(alarm_command_help=alarm_help, system_timezone_change_supported=system_supported)
        command(adb + ['install', '-r', str(ROOT / settings['collector']['apk']['path'])], timeout=60)
        command(adb + ['shell', 'pm', 'clear', PACKAGE])
        package = command(adb + ['shell', 'dumpsys', 'package', PACKAGE])
        record['app_version_code'] = int(re.search(r'versionCode=(\d+)', package).group(1))
        record['app_version_name'] = re.search(r'versionName=(\S+)', package).group(1)
        if record['app_version_code'] != 14 or record['app_version_name'] != settings['collector']['version_name']:
            raise ValueError('Unexpected installed App version')
        record.update(registered_before_collection_at=now(), read_only_owned_avd=True)
        write(life, record)
        command(adb + ['reverse', 'tcp:8000', 'tcp:' + str(settings['ports']['receiver'])])
        args = [str(ROOT / 'backend_server/.venv-collection/bin/python'), '-B', '-m', 'uvicorn', 'main:app',
                '--host', '127.0.0.1', '--port', str(settings['ports']['receiver']), '--workers', '1']
        with (run / 'receiver.log').open('x') as log:
            receiver = subprocess.Popen(args, cwd=ROOT / 'backend_server', env={**os.environ,
                'HYBRIDGUARD_DATA_DIR': str(run / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1'}, stdout=log, stderr=subprocess.STDOUT)
        record.update(receiver_pid=receiver.pid, receiver_command=args)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if receiver.poll() is not None: raise RuntimeError('Owned receiver exited')
            if 'Application startup complete' in (run / 'receiver.log').read_text(): break
            time.sleep(.2)
        else: raise TimeoutError('Receiver startup timeout')
        environment_deadline = time.monotonic() + settings['limits']['environment_seconds']
        for start in range(0, len(operations), 3):
            steps = operations[start:start + 3]; target = steps[0]['target_timezone']; kind = steps[0]['process_type']
            if kind == 'L' and not system_supported:
                for op in steps: op['reason'] = 'System AlarmManager timezone command unavailable; L not executed'
                trios.append(trio_evidence(steps, {'status': 'NOT_CHANGED'})); save_operations(); continue
            try:
                command(adb + ['shell', 'settings', 'put', 'global', 'auto_time_zone', '0'])
                # Preserve the starting zone; all L/A phases share the same auto-timezone setting.
                if timezone_snapshot(command, adb)['timezone_id'] != original['timezone_id']:
                    raise RuntimeError('System original zone changed before trio')
                for op in steps:
                    if time.monotonic() > environment_deadline: raise TimeoutError('Environment time limit')
                    if receiver.poll() is not None or emulator.poll() is not None: raise RuntimeError('Owned runtime exited')
                    op.update(started_at=now(), status='STARTED'); record['attempts'] += 1
                    context = 'timezone-validation:' + eid + ':' + op['step_id']
                    archive = run / 'backend/raw_expanded_payloads.jsonl'
                    offset = archive.stat().st_size if archive.exists() else 0
                    print('START', eid, op['step_id'], flush=True)
                    try:
                        command(adb + ['shell', 'am', 'force-stop', PACKAGE])
                        if command(adb + ['shell', 'pidof', PACKAGE], required=False).strip():
                            raise RuntimeError('Old owned App process remains alive')
                        if kind == 'L' and op['phase'] in ('change', 'clean_post'):
                            op['system_change'] = set_zone(command, adb, target if op['phase'] == 'change' else original['timezone_id'])
                        op['system_before'] = timezone_snapshot(command, adb)
                        command(adb + ['shell', 'am', 'start', '-S', '-W', '-n', PACKAGE + '/.MainActivity',
                            '--es', PACKAGE + '.COLLECT_ENDPOINT', 'http://127.0.0.1:8000/api/collect/fingerprint',
                            '--es', PACKAGE + '.RUNTIME_CONTEXT', context, '--ei', PACKAGE + '.COLLECTION_ROUND', '1',
                            '--es', PACKAGE + '.DEVICE_MANIFEST_ID', 'timezone-validation-' + eid,
                            '--ez', PACKAGE + '.ENABLE_WEBVIEW_DEBUG', 'true', '--ez', PACKAGE + '.WAIT_FOR_WEBVIEW_CONTROL', 'true',
                            '--el', PACKAGE + '.PROBE_DELAY_MS', '60000'])
                        time.sleep(2.5)
                        pids = command(adb + ['shell', 'pidof', PACKAGE]).strip().split()
                        sockets = command(adb + ['shell', 'cat', '/proc/net/unix'])
                        matching = [p for p in pids if 'webview_devtools_remote_' + p in sockets]
                        if len(matching) != 1: raise RuntimeError('No unique owned App debugging socket')
                        command(adb + ['forward', 'tcp:' + str(settings['ports']['cdp']), 'localabstract:webview_devtools_remote_' + matching[0]])
                        forward_owned = True
                        receipt = run / (op['step_id'] + '.cdp.json')
                        command([shutil.which('node'), str(HERE / 'timezone_cdp.mjs'),
                            'http://127.0.0.1:' + str(settings['ports']['cdp']), str(receipt),
                            target if kind == 'A' and op['phase'] == 'change' else 'noop',
                            str(archive), str(offset), context], timeout=90)
                        cdp = read(receipt); op.update(cdp_status=cdp['status'], cdp_receipt=receipt.name,
                                                     cdp_rollback_status=cdp.get('rollback_status'))
                        if cdp['status'] != 'COMPLETED': raise RuntimeError('CDP operation failed')
                        op['owned_app_pid'] = matching[0]
                    except Exception as exc:
                        op.update(status='FAILED', error=type(exc).__name__ + ': ' + str(exc))
                    finally:
                        receipt = run / (op['step_id'] + '.cdp.json')
                        if receipt.exists():
                            cdp = read(receipt); op.update(cdp_status=cdp.get('status'), cdp_receipt=receipt.name,
                                                         cdp_rollback_status=cdp.get('rollback_status'))
                        raw = find_raw(archive, offset, context)
                        if raw is not None:
                            p = raw['canonical_received_payload']; sid = p.get('session_id'); identity = p['collection_manifest'].get('collector_install_id')
                            if sid != raw.get('session_id') or not identity: raise ValueError('Raw session/installation missing')
                            if installation is None: installation = identity
                            if installation != identity: raise ValueError('App installation changed')
                            op.update(session_id=sid, raw_archive='backend/raw_expanded_payloads.jsonl', raw_byte_offset=offset,
                                collector_install_id=identity, observed_timezone=timezone_observation(raw))
                            record['raw_records'] += 1
                            if op['status'] != 'FAILED': op['status'] = 'COLLECTED'
                        elif op['status'] != 'FAILED': op.update(status='FAILED', error='Missing raw position')
                        op['system_after'] = timezone_snapshot(command, adb)
                        command(adb + ['shell', 'am', 'force-stop', PACKAGE], required=False)
                        op['owned_app_process_absent_after'] = not command(adb + ['shell', 'pidof', PACKAGE], required=False).strip()
                        if forward_owned:
                            command(adb + ['forward', '--remove', 'tcp:' + str(settings['ports']['cdp'])], required=False); forward_owned = False
                        op['finished_at'] = now(); save_operations(); write(life, record)
                        print(op['status'], eid, op['step_id'], op.get('session_id', ''), flush=True)
                    # No retries. Post is retained/attempted to verify restoration after a failed middle position.
            finally:
                restoration = restore_original(command, adb, original, system_supported)
                trios.append(trio_evidence(steps, restoration)); trios[-1]['restoration_details'] = restoration
                save_operations()
                if restoration['status'] != 'RESTORED': raise RuntimeError('Original system settings restoration failed')
        record['status'] = 'COMPLETE' if all(o['status'] == 'COLLECTED' for o in operations) else 'INCOMPLETE'
    except Exception as exc:
        record.update(status='UNAVAILABLE_OR_INCOMPLETE', error=type(exc).__name__ + ': ' + str(exc))
    finally:
        if original is not None and emulator is not None and emulator.poll() is None:
            record['final_system_restoration'] = restore_original(command, adb, original, system_supported)
            if record['final_system_restoration']['status'] != 'RESTORED':
                record['status'] = 'INCOMPLETE'; record['error'] = 'Final system settings restoration failed'
        for op in operations:
            if op['status'] == 'NOT_EXECUTED': op.setdefault('reason', record.get('error', 'Not executed'))
        save_operations()
        for process, kind in ((receiver, 'receiver'), (emulator, 'emulator')):
            if process is not None and process.poll() is None:
                process.send_signal(signal.SIGINT if kind == 'receiver' else signal.SIGTERM)
                try: process.wait(timeout=20)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
            record[kind + '_returncode'] = process.poll() if process else None
        record.update(finished_at=now(), owned_processes_exited=all(p is None or p.poll() is not None for p in (receiver, emulator)))
        write(life, record)
    print('ENVIRONMENT', eid, record['status'], record.get('error', ''), flush=True)
    return {k: v for k, v in record.items() if k != 'commands'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=HERE)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args(); out = args.output_dir.resolve(); settings = validate_settings(read(out / 'SETTINGS.json'))
    check = preflight(settings)
    if args.preflight: print(json.dumps(check, ensure_ascii=False, indent=2)); return
    frozen = require_frozen(out)
    if (out / 'COLLECTION.json').exists() or (out / 'runs').exists(): raise FileExistsError('No automatic recollection')
    write(out / 'COLLECTION.json', {'started_at': now(), 'preflight': check, 'model_freeze': frozen, 'environments': []})
    results = []
    try:
        for env in settings['environments']:
            results.append(run_environment(settings, env, out))
            write(out / 'COLLECTION.json', {'preflight': check, 'environments': results, 'planned_records': 36,
                                           'collection_model_fit_calls': 0, 'model_freeze': frozen})
    finally:
        write(out / 'COLLECTION.json', {'preflight': check, 'environments': results, 'finished_at': now(),
            'planned_records': 36, 'actual_records': sum(r['raw_records'] for r in results),
            'collection_model_fit_calls': 0, 'model_freeze': frozen})


if __name__ == '__main__': main()
