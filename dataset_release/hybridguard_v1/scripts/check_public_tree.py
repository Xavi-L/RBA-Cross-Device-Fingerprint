#!/usr/bin/env python3
"""Check intended tracked release files without exposing identity-matching text."""
from __future__ import annotations
import getpass
import json
from pathlib import Path
import re
import subprocess
from common import ROOT, privacy_findings


def check():
    repo=ROOT.parents[1]
    names={getpass.getuser(),Path.home().name}
    for key in ('user.name','user.email'):
        value=subprocess.run(['git','config',key],cwd=repo,capture_output=True,text=True).stdout.strip()
        if len(value)>3:names.add(value)
    remote=subprocess.check_output(['git','remote','get-url','origin'],cwd=repo,text=True).strip()
    names.add(remote.rstrip('/').rsplit('/',2)[-2].rsplit(':',1)[-1])
    public=[p for p in ROOT.rglob('*') if p.is_file() and '.private' not in p.parts and '__pycache__' not in p.parts and 'reviewer_release' not in p.parts]
    for path in public:
        if path.suffix in {'.zip','.gz','.jsonl'}:
            raise ValueError('Candidate/sample/archive content cannot enter tracked release tree')
        content=path.read_text()
        if any(name and re.search(re.escape(name),content,re.I) for name in names):
            raise ValueError('Author identity detected in '+str(path.relative_to(ROOT)))
        # Python negative-test fixtures deliberately contain synthetic PII patterns.
        if path.suffix=='.json':
            if privacy_findings(json.loads(content)):
                raise ValueError('Privacy pattern in public JSON '+str(path.relative_to(ROOT)))
        if path.suffix=='.md' and privacy_findings(content):
            raise ValueError('Privacy pattern in public prose '+str(path.relative_to(ROOT)))
    ignored=['dataset_release/hybridguard_v1/.private/identity_map.json',
             'dataset_release/hybridguard_v1/.private/candidate/features.jsonl',
             'dataset_release/hybridguard_v1/data/features.jsonl']
    for path in ignored:
        subprocess.run(['git','check-ignore','--quiet',path],cwd=repo,check=True)
        if subprocess.check_output(['git','ls-files','--',path],cwd=repo,text=True).strip():
            raise ValueError('Private/sample path is already tracked')
    return {'status':'PASS','intended_public_files':len(public),'author_identity_scan':'PASS',
            'public_prose_and_json_privacy_scan':'PASS','private_and_public_sample_git_ignores':'PASS',
            'scope':'repository-tree checks; standalone artifact anonymity is checked by build_reviewer_release.py'}

if __name__=='__main__':print(json.dumps(check(),sort_keys=True))
