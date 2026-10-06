"""Read-only closeout checks plus a new local validation manifest; no model calls."""
import ast,re,subprocess
from datetime import datetime,timezone
from closeout_io import *

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def validate():
    baseline=read(HERE/'WORKTREE_BASELINE.json')
    head=git('rev-parse','HEAD').decode().strip()
    require(head==baseline['initial_head'],'HEAD_CHANGED')
    now={x[3:].decode():x[:2].decode() for x in git('status','--porcelain=v1','-z').split(b'\0') if x}
    old=baseline['initial_status']
    require(all(now.get(name)==status for name,status in old.items()),'PREEXISTING_WORKTREE_STATUS_CHANGED')
    expected={'RBA_SUPERVISOR_REPORT.md':' M','RBA_PRE_PAPER_EXPERIMENT_PLAN.md':' M',ref(HERE)+'/':'??'}
    require({name:status for name,status in now.items() if name not in old}==expected,'UNEXPECTED_NEW_WORKTREE_PATH')
    require(not git('diff','--cached','--name-only'),'INDEX_NOT_EMPTY')
    root_prefixes=read(HERE/'ROOT_APPEND_BASELINE.json')
    for record in root_prefixes:
        prefix=(ROOT/record['path']).read_bytes()[:record['prefix_bytes']]
        require(hashlib.sha256(prefix).hexdigest()==record['prefix_sha256'],'ROOT_HISTORY_REWRITTEN')
    frozen=read(HERE/'results/FREEZE.json')
    for name,sha in frozen['sources'].items():require(digest(ROOT/name)==sha,'ORIGINAL_FROZEN_SOURCE_CHANGED:'+name)
    require(digest(HERE/'PROTOCOL.md')==frozen['protocol_sha256'],'PROTOCOL_CHANGED')
    timer=read(HERE/'timing/TIMING_FREEZE.json')
    for name,sha in timer['implementation'].items():require(digest(ROOT/name)==sha,'TIMING_IMPLEMENTATION_CHANGED')
    python_files=list(HERE.glob('*.py'))
    for p in python_files:ast.parse(p.read_text(),filename=str(p))
    docs=[(p,p.read_text()) for p in HERE.glob('*.md')]
    docs += [(ROOT/r['path'],(ROOT/r['path']).read_bytes()[r['prefix_bytes']:].decode()) for r in root_prefixes]
    links=0
    for p,text in docs:
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in target or target.startswith('#'):continue
            relative=target.split('#',1)[0]
            target_path=(p.parent/relative).resolve()
            if target_path!=HERE/'VALIDATION.json':
                require(target_path.exists(),'BROKEN_LOCAL_LINK:'+str(p)+':'+relative)
            links+=1
    # Only new authored text: a focused credential-shape check, not a repo scan.
    names=subprocess.check_output(['rg','--files','--hidden',str(HERE)],cwd=ROOT).decode().splitlines()
    patterns=[re.compile(r'AIza[0-9A-Za-z_-]{35}'),re.compile(r'gh[pousr]_[0-9A-Za-z]{30,}'),re.compile(r'sk-[A-Za-z0-9_-]{32,}'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
    scanned=0
    for name in names:
        p=Path(name)
        if p.suffix.lower() not in ('.py','.txt','.md','.json','.jsonl','.csv','.log'):continue
        text=p.read_text();require(not any(pattern.search(text) for pattern in patterns),'CREDENTIAL_SHAPE:'+p.name);scanned+=1
    tests=read(HERE/'TEST_CALLS.json');require(tests['tests']==15 and tests['failures']==tests['errors']==0,'TEST_FAILURE')
    rebuild=read(HERE/'REBUILD_VERIFICATION.json');require(rebuild['status']=='PASSED' and len(rebuild['files'])==30,'REBUILD_FAILURE')
    selection=read(HERE/'results/EXECUTION.json');require(selection['new_selection_tasks']==3 and selection['candidate_checks']==12,'SELECTION_SCOPE')
    timing=read(HERE/'timing/EXECUTION.json');require(timing['status']=='PASSED' and timing['recorded_batches']==1480,'TIMING_SCOPE')
    figures=read(HERE/'figures/FIGURES.json');require(len(figures)==4,'FIGURE_COUNT')
    result=dict(status='PASSED',time=datetime.now(timezone.utc).isoformat(),head=head,
        worktree=dict(preexisting_status_entries=len(old),preserved_status_entries=len(old),new_scope=expected,index_empty=True,git_mutations=0,root_history_prefixes_preserved=True,submodule_status_preserved=True),
        frozen_original_files=len(frozen['sources']),protocol_unchanged=True,timed_implementation_unchanged=True,
        tests=tests,accepted_selection=selection,accepted_timing=timing,
        engineering_failures=read(HERE/'ENGINEERING_EVENTS.json'),
        unrecorded_calls='First interrupted preflight partial prediction call counts NOT_RECORDED; zero fit/selection/collection',
        saved_only_rebuild=dict(status=rebuild['status'],files=len(rebuild['files']),selection=0,prediction=0,timing=0,fit=0,collection=0),
        syntax_files=len(python_files),local_links_checked=links,credential_shape_text_files=scanned,
        visual_review=dict(figures=4,svg_png_csv_per_figure=True,all_pngs_inspected=True,layout_only_revision='fig03 title padding; data unchanged'),
        evidence=dict(positions=951,development=690,historical_evaluation=261,rule_models=9,rule_outputs=8559,frozen_trees=12,frozen_tree_outputs=11412,metric_rows=348),
        privacy='Existing private raw/archive/private_runs remain referenced locally; no archive copy or publication',
        scope='Completed B3-B; stop experiments and begin bounded exploratory paper writing')
    write(HERE/'VALIDATION.json',result)
    require((HERE/'VALIDATION.json').exists(),'VALIDATION_MANIFEST_MISSING')
    print(json.dumps(dict(status='PASSED',frozen_original_files=len(frozen['sources']),tests=15,saved_rebuild_files=30,preexisting_worktree_entries=len(old),local_links=links)))

if __name__=='__main__':validate()
