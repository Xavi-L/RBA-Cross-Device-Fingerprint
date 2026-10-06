"""Run after engineering smoke, before any formal acquisition or model evaluation."""
import hashlib,json,subprocess,datetime
from pathlib import Path
import ui,settings_control
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];B1=HERE.parent/'browser67_pilot_intake_v1'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if __name__=='__main__':
    assert not (HERE/'FROZEN.json').exists()
    ui.OUT=HERE/'private_runs/engineering/environment'
    apk=B1/'evidence_archive/pilot_r8/installed_collector.apk'
    installed=ui.adb('shell','pm','path','com.example.hybridguard.featureapp').removeprefix('package:')
    installed_copy=ui.OUT/'installed-v16.apk';ui.adb('pull',installed,str(installed_copy));assert h(installed_copy)==h(apk)
    files=[ROOT/'deliverables/browser67_cross_endpoint_diagnostic_v1'/n for n in ['conditions.py','CANDIDATES_FROZEN.json','run.py']]
    files+=[ROOT/'deliverables/timezone_relation_validation_v1/MODELS_FROZEN.json']
    files+=sorted((ROOT/'deliverables/timezone_relation_validation_v1/trials').glob('B_REL_TZ__*__RETENTION/model.json'))
    files+=[ROOT/'hybridguard_agent/research'/n for n in ['mtc_timezone_relation.py','mtc_timezone_candidates.py','mtc_timezone_selection.py','rule_semantics_revision_v1/language.py']]
    capture_files=[HERE/n for n in ['collect.mjs','settings_control.py','ui.py','backend.py','make_plan.mjs']]
    props=['ro.build.fingerprint','ro.build.version.sdk','ro.build.version.sdk_full','ro.build.version.release','ro.product.cpu.abi']
    env={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':'macOS Apple Silicon','owned_serial':'emulator-5580','avd':'Medium_Phone_API_36.1','emulator_flags':['-read-only','-no-snapshot-save','-no-window','-no-audio'],'properties':{p:ui.adb('shell','getprop',p) for p in props},'initial_settings':settings_control.snapshot(),'browser_package':'com.android.chrome','browser_version':'134.0.6998.135','webview_package':'com.google.android.webview','webview_version':'134.0.6998.135','collector_version':'1.6.9-expanded-v2.2-geometry (16)','apk_sha256':h(apk),'installed_apk_matches_archive':True,'original_ephemeral_app_version':'1.3.0-expanded-v2.2-browser-web67','source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'historical_pilot_comparison':'B1 x86_64 Chrome 133; separate environment and separate cohort.'}
    for pkg in ['com.android.chrome','com.google.android.webview','com.example.hybridguard.featureapp']:
        (ui.OUT/(pkg+'.package.txt')).write_text(ui.adb('shell','dumpsys','package',pkg))
    assert env['initial_settings']['locale']=='en-US' and env['initial_settings']['timezone']=='Asia/Shanghai'
    smoke=HERE/'private_runs/engineering/smoke01'
    caps=[json.loads(s) for s in (smoke/'captures.jsonl').read_text().splitlines()]
    assert len(caps)==12 and all(c['result']=='COMPLETED' and all(x['status']=='COMPLETED' for x in c['restoration']) for c in caps)
    for name in ['system-setting-apply.json','system-setting-restore.json','browser-setting-apply03.json','browser-setting-restore03.json','timezone-setting-apply.json','timezone-setting-restore.json']:
        assert json.loads((HERE/'private_runs/engineering'/name).read_text())['status']=='EXECUTED'
    for name,obj in [('ENVIRONMENT.json',env),('FROZEN.json',{'frozen_at':env['captured_at'],'source_commit':env['source_head'],'fit_calls':0,'formal_positions':42,'engineering_pairs':12,'files':{str(p.relative_to(ROOT)):h(p) for p in files},'collection_files':{str(p.relative_to(ROOT)):h(p) for p in capture_files},'apk_sha256':h(apk),'probe':{'revision':'expanded-web-67-v2','archive_reference':'deliverables/browser67_pilot_intake_v1/evidence_archive/upstream/browser_probe_site/public','canonical_probe_sha256':h(B1/'evidence_archive/upstream/browser_probe_site/public/probe/canonical_web_probe.js')},'backend':'B1 frozen upstream with unchanged restricted source_reference/run_backend.py wrapper; own isolated data directory','targets':{'language':'fr-FR','languages':['fr-FR'],'timezone':'Asia/Tokyo'},'scope':'One local matched environment; no formal training eligibility or final ablation.'})]:
        with (HERE/name).open('x') as f:f.write(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print('Frozen: 12 engineering pairs; three real-setting apply/restore paths; 42 formal slots.')
