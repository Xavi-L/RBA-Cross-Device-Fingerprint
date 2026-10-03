#!/usr/bin/env python3
"""One v16 engineering smoke, at most twelve fixed positions; no old matrix."""
import argparse,json,subprocess
from pathlib import Path
from profile import HERE,ROOT,load,validate,evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings',type=Path,default=HERE/'SETTINGS.json')
    parser.add_argument('--output-dir',type=Path,default=HERE/'v16_smoke')
    parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    s=validate(evidence.read_object(args.settings,required=True)[0]);c=load('collect')
    build=evidence.read_object(ROOT/s['source_build_record'],required=True)[0]
    apk=ROOT/s['collector']['apk']['path']
    if apk!=(ROOT/s['source_build_record']).parent/build['apk'] or build['version_code']!=16:raise ValueError('SAVED_V16_BUILD_REQUIRED')
    tool=c.SDK/'build-tools/36.0.0/aapt'
    info=subprocess.check_output([str(tool),'dump','badging',str(apk)],text=True)
    first=info.splitlines()[0]
    if "versionCode='16'" not in first or "versionName='1.6.9-expanded-v2.2-geometry'" not in first:raise ValueError('APK_PACKAGE_IDENTITY_MISMATCH')
    check=c.preflight(s);check['apk_package']=first;check['source_build_record']=s['source_build_record']
    if args.preflight:print(json.dumps(check,indent=2));return
    out=args.output_dir.absolute();out.mkdir(parents=True,exist_ok=False)
    profile={'positions':{e['environment_group_id']:[p for p in s['positions'] if p['environment']==e['environment_group_id']] for e in s['environments']},
             'context_prefix':s['context_prefix'],'identity_prefix':s['identity_prefix'],'module_version':s['module_version'],'fault_driver':str(HERE/'fault_cdp.mjs')}
    results=[];record={'preflight':check,'planned_records':12,'model_fit_calls':0,'environments':results,'settings_source':str(args.settings.absolute())}
    c.write(out/'COLLECTION.json',record)
    try:
        for env in s['environments']:
            results.append(c.run_profile_environment(s,env,out,profile=profile));c.write(out/'COLLECTION.json',record)
    finally:
        record.update(finished_at=c.now(),actual_records=sum(r['raw_records'] for r in results));c.write(out/'COLLECTION.json',record)


if __name__=='__main__':main()
