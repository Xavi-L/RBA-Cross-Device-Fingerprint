"""Small stdlib-only IO; never triggers learning or inference."""
import json,hashlib
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
B2C=HERE.parent/'cross_endpoint_constrained_extension_v1'
STATES=('T','F','U','FAILED')
MODE='DEVELOPMENT_FOUR_VIEW_COMPARISON'
def read(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(s) for s in Path(p).read_text().splitlines()]
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def jsonl(p,vs):Path(p).write_text(''.join(json.dumps(v,ensure_ascii=False,allow_nan=False)+'\n' for v in vs))
def require(ok,why):
 if not ok:raise ValueError(why)
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p,n=None):
 s=str(Path(p).resolve().relative_to(ROOT));return s if n is None else s+':'+str(n)
def unique(rs,key):
 d={key(r):r for r in rs};require(len(d)==len(rs),'DUPLICATE_KEY');return d
def counts(ss):
 c=Counter(ss);require(set(c)<=set(STATES),'INVALID_STATE');return dict(n=sum(c.values()),**{s:c[s] for s in STATES},defined=c['T']+c['F'])
