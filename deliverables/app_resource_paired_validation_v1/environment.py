"""Read-only environment capture for the task-owned ephemeral emulator."""
from pathlib import Path
import subprocess,json,hashlib,datetime,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ADB='/Users/xavier/Library/Android/sdk/platform-tools/adb'
def shell(*args):return subprocess.check_output([ADB,'-s','emulator-5580','shell',*args],text=True).strip()
def record():
    owner=json.loads((HERE/'private_runs/OWNER.json').read_text());assert owner['started_by_current_task']
    apk=ROOT/'deliverables/browser67_pilot_intake_v1/evidence_archive/pilot_r8/installed_collector.apk'
    props={k:shell('getprop',k) for k in ['ro.build.fingerprint','ro.build.version.sdk','ro.build.version.sdk_full','ro.build.version.release','ro.product.cpu.abi','persist.sys.timezone','persist.sys.locale']}
    packages={p:'\n'.join(l.strip() for l in shell('dumpsys','package',p).splitlines() if any(k in l for k in ['versionName=','versionCode='])) for p in ['com.android.chrome','com.google.android.webview','com.example.hybridguard.featureapp']}
    probes={}
    with zipfile.ZipFile(apk) as z:
        for n in z.namelist():
            if n.startswith('assets/') and ('probe' in n) and n.endswith(('.js','.html')):probes[n]=hashlib.sha256(z.read(n)).hexdigest()
    browser=ROOT/'deliverables/browser67_pilot_intake_v1/evidence_archive/upstream/browser_probe_site/public'
    browser_probes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in browser.iterdir() if p.suffix in ('.js','.html') and 'probe' in p.name}
    out={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'owner':owner,'properties':props,'packages':packages,'meminfo':shell('cat','/proc/meminfo').splitlines()[0],'cpu_possible':shell('cat','/sys/devices/system/cpu/possible'),'original_system_settings':{k:shell('settings','get','global',k) for k in ['auto_time_zone','airplane_mode_on']},'configuration':shell('am','get-config'),'apk_path':str(apk.relative_to(ROOT)),'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'apk_probe_digests':probes,'browser_probe_digests':browser_probes,'app_origin':'file:///android_asset/expanded_probe.html','browser_origin':'http://127.0.0.1:8001','control':'CDP on task-owned emulator; no certificate/safe-context bypass; system RAM/CPU/timezone untouched','historical_comparison':'new resource cohort; not old pilot device or old App triplets'}
    (HERE/'ENVIRONMENT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'properties':props,'packages':packages,'meminfo':out['meminfo'],'cpu_possible':out['cpu_possible']}))
if __name__=='__main__':record()
