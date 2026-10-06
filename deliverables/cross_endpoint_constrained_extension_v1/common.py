"""Dependency-light file and state contracts; no model execution."""
import gzip, hashlib, json
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IDS = ['mtc-rel-tz-6e10284c39b1b601ab406240', 'mtc-rel-tz-9c5fa0e310ba10a00e520b1c', 'mtc-rel-tz-4ae67bb9da899cc419dd525f']
STATES = ('T', 'F', 'U', 'FAILED')
MODE = 'DEVELOPMENT_EXTENSION_SELECTION'
COHORTS = ('mtc_discovery', 'pilot18', 'b2b42', 'mtc_development', 'mtc_reserved_validation')
def require(ok, reason):
    if not ok: raise ValueError(reason)
def read(path): return json.loads(Path(path).read_text())
def rows(path):
    with (gzip.open(path, 'rt') if str(path).endswith('.gz') else Path(path).open()) as f:
        # Blank/malformed physical lines are errors, never silently dropped.
        return [json.loads(line) for line in f]
def write(path, obj): Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
def jsonl(path, values): Path(path).write_text(''.join(json.dumps(v, ensure_ascii=False, allow_nan=False)+'\n' for v in values))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path, line=None):
    p = str(Path(path).resolve().relative_to(ROOT))
    return p if line is None else f'{p}:{line}'
def state(prediction):
    expected = {'MANIPULATION_ALERT':'T', 'NO_ALERT':'F', 'INSUFFICIENT_EVIDENCE':'U', 'FAILED':'FAILED'}
    s = expected[prediction['decision']]
    require(s == 'FAILED' or prediction.get('logical_state') == s, 'DECISION_STATE_MISMATCH')
    return s
def counts(values):
    c = Counter(values); require(set(c) <= set(STATES), 'INVALID_STATE')
    return dict(n=sum(c.values()), **{s:c[s] for s in STATES}, defined=c['T']+c['F'])
def unique(records, key):
    result = {key(r):r for r in records}
    require(len(result)==len(records), 'DUPLICATE_MEMBERS')
    return result
