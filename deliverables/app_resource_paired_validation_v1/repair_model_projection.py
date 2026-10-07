"""One engineering replay after correcting encoded-name to raw-column mapping.

Original 486 FAILED outputs are retained. No condition re-evaluation or fit.
"""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path[:0]=[str(HERE),str(HERE.parents[1])]
import data as d
from evaluate import models,predict,jsonl,write
out=HERE/'results';eng=out/'engineering';marker=eng/'MODEL_PROJECTION_REPAIR.json'
if marker.exists():raise FileExistsError('ENGINEERING_REPLAY_ALREADY_COMPLETE')
old=d.rows(out/'model_predictions.jsonl')
assert len(old)==486 and all(r['state']=='FAILED' and 'UNFITTED_CONTROL:' in r['failure_reason'] for r in old)
jsonl(eng/'model_predictions_first_attempt.jsonl',old)
write(eng/'model_execution_first_attempt.json',d.read(out/'EXECUTION.json'))
run=HERE/'private_runs/formal01';plan=d.read(run/'plan.json');caps={r['sample_id']:r for r in d.capture_records(run)};positions=d.rows(out/'positions.jsonl');frozen=models();new=[]
for s,position in zip(plan['positions'],positions,strict=True):
    item=d.bind(run,plan,s,caps[s['sample_id']]);meta={k:position[k] for k in ['sample_id','scenario','round','phase','identity','cohort']}
    for scheme,fold,model,_ in frozen:new.append({**meta,'scheme':scheme,'fold':fold,**predict(model,scheme,item)})
assert len(new)==486
execution=d.read(out/'EXECUTION.json')
assert all(hashlib.sha256((d.ROOT/p).read_bytes()).hexdigest()==digest for p,digest in execution['frozen_files_before_after_unchanged'].items())
jsonl(out/'model_predictions.jsonl',new)
write(marker,{'first_model_prediction_calls':486,'engineering_model_prediction_calls':486,'actual_total_model_prediction_calls':972,'canonical_model_positions':486,'first_states':{'FAILED':486},'reason':'Thin adapter passed encoded CONTROL:*:LE:* IDs to the raw-template projector, omitting UNFITTED_CONTROL:<field> keys required by the original saved encoder. It now maps each selected CONTROL_LE back to its existing numeric raw field. Tests compare the partial projection with original full projection for all9 frozen models, without prediction or fitting.','data_rules_encoders_thresholds_unchanged':True,'condition_calls':0,'fit_calls':0,'first_outputs':'model_predictions_first_attempt.jsonl'})
execution.update(model_prediction_calls=972,canonical_model_positions=486,engineering_model_prediction_calls=486,model_projection_repair='engineering/MODEL_PROJECTION_REPAIR.json');write(out/'EXECUTION.json',execution)
print(json.dumps({'canonical_model_positions':486,'actual_model_prediction_calls':972,'new_states':dict(__import__('collections').Counter(r['state'] for r in new)),'fit_calls':0}))
