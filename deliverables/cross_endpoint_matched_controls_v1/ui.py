"""Recorded ADB UI operations on the one owned emulator; never changes JS fields."""
import argparse, datetime, json, os, re, subprocess, time
from pathlib import Path
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
ADB=os.environ.get('B2B_ADB','/Users/xavier/Library/Android/sdk/platform-tools/adb')
SERIAL='emulator-5580'
OUT=Path(os.environ.get('B2B_UI_OUT',str(HERE/'private_runs/engineering/ui')))
def adb(*args):
    OUT.mkdir(parents=True,exist_ok=True)
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    p=subprocess.run([ADB,'-s',SERIAL,*args],text=True,capture_output=True,timeout=30)
    with (OUT/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(at=start,args=args,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))+'\n')
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout.strip()
def dump():
    adb('shell','uiautomator','dump','/sdcard/b2b-ui.xml')
    xml=adb('shell','cat','/sdcard/b2b-ui.xml')
    (OUT/f'{time.time_ns()}.xml').write_text(xml)
    return ET.fromstring(xml)
def center(n):
    a,b,c,d=map(int,re.findall(r'\d+',n.get('bounds')))
    return (a+c)//2,(b+d)//2
def tap(text):
    r=dump();ns=[n for n in r.iter('node') if n.get('text')==text or n.get('content-desc')==text]
    if len(ns)!=1:raise ValueError(f'Expected unique UI node {text!r}, got {len(ns)}')
    adb('shell','input','tap',*map(str,center(ns[0])))
def tap_id(resource_id):
    ns=[n for n in dump().iter('node') if n.get('resource-id')==resource_id]
    if len(ns)!=1:raise ValueError(f'Expected unique UI resource {resource_id!r}, got {len(ns)}')
    adb('shell','input','tap',*map(str,center(ns[0])))
def show():
    for n in dump().iter('node'):
        if n.get('text') or n.get('content-desc'):print(n.get('text'),n.get('content-desc'),n.get('resource-id'),n.get('bounds'))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['dump','tap','adb']);p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args()
    if a.action=='dump':show()
    elif a.action=='tap':tap(a.args[0]);show()
    else:print(adb(*a.args))
