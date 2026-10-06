"""Standard-library artifacts only; no learning, prediction, timing or acquisition."""
import csv,hashlib,json
from pathlib import Path
from collections import Counter

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
B2C=HERE.parent/'cross_endpoint_constrained_extension_v1'
B3A=HERE.parent/'cross_endpoint_four_view_comparison_v1'
B2B=HERE.parent/'cross_endpoint_matched_controls_v1'
B2A=HERE.parent/'browser67_cross_endpoint_diagnostic_v1'
STATES=('T','F','U','FAILED')
SETTINGS_NAMES=('R_FULL','R_NO_CROSS','R_NO_MATCHED_NORMAL_CAP')
def require(ok,message):
    if not ok:raise ValueError(message)
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(line) for line in Path(p).read_text().splitlines()]
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jsonl(p,values):Path(p).write_text(''.join(json.dumps(v,ensure_ascii=False,allow_nan=False)+'\n' for v in values))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p,n=None):
    s=str(Path(p).resolve().relative_to(ROOT));return s if n is None else f'{s}:{n}'
def index(rs,key='sample_id'):
    d={r[key]:r for r in rs};require(len(d)==len(rs),'DUPLICATE_KEY');return d
def counts(values):
    c=Counter(values);require(set(c)<=set(STATES),'INVALID_STATE')
    return dict(n=sum(c.values()),**{s:c[s] for s in STATES},defined=c['T']+c['F'])
def csv_write(path,values):
    values=list(values)
    with Path(path).open('w',newline='') as f:
        if values:
            w=csv.DictWriter(f,fieldnames=list(values[0]));w.writeheader();w.writerows(values)
