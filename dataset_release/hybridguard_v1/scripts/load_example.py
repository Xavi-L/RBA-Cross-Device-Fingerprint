#!/usr/bin/env python3
"""Independently load de-identified JSONL sidecars without repository dependencies."""
import argparse
import json
from collections import Counter
from pathlib import Path


def load(directory):
    directory=Path(directory)
    tables={}
    for name in ('features','metadata','annotations'):
        path=directory/(name+'.jsonl')
        if not path.exists():
            raise ValueError('Required dataset table is missing; provide the unpacked reviewer package directory.')
        rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        tables[name]={r['sample_id']:r for r in rows}
        if len(tables[name])!=len(rows):raise ValueError('Repeated sample ID')
    if not (tables['features'].keys()==tables['metadata'].keys()==tables['annotations'].keys()):
        raise ValueError('Sidecar reference mismatch')
    return [(f,tables['metadata'][sid],tables['annotations'][sid]) for sid,f in tables['features'].items()]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True)
    records=load(parser.parse_args().data)
    print(json.dumps({'observations':len(records),
                      'views':dict(Counter(f['view'] for f,m,a in records)),
                      'labels':dict(Counter(a['label'] for f,m,a in records))},sort_keys=True))

if __name__=='__main__':main()
