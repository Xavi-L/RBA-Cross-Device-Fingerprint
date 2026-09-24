"""Hand-constructed explanation-auditor counterexamples; zero fitting."""
import copy
from pathlib import Path
import sys

out=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(out/"driver"))
from benchmark import frozen_api, write, NOW
from saved_audit import audit_one

models,predictor,baselines,contracts,paths,rejected=frozen_api(out.parent/"R04_freeze_r1")
atom=models.Atom("toy","toy_family",("toy_surface",),("E",),("toy_alias",),provenance={"field_refs":["toy.current"]})
model=models.RuleModel("GREEDY_OR","FITTED",(models.Clause((models.Literal("toy","NEGATIVE"),)),),(atom,),
    {"data_origin":"BUILTIN_SYNTHETIC","fit_job_id":None},
    {"view_id":"TOY","input_atom_ids":["toy"]},{"status":"HAND_CONSTRUCTED_NO_FIT","train_ids":[]})
cells={"toy":contracts.cell("U")}
row=predictor.predict(model,"synthetic",{"features":cells,"view_id":"TOY"})
assert audit_one(model,row,cells,contracts)["status"].startswith("PASS")
checks=["negative_U_stays_U_and_audits"]
mutations=[("alias",lambda r:r["atom_explanations"][0].update(aliases=["unused"]),"ATOM_METADATA"),
    ("field",lambda r:r["atom_explanations"][0].update(provenance={"field_refs":["future.post"]}),"ATOM_METADATA"),
    ("polarity",lambda r:r["clause_explanations"][0]["literals"][0].update(polarity="POSITIVE"),"LITERAL_POLARITY"),
    ("unused_rule",lambda r:r["clause_explanations"].append({"clause_id":"unused","state":"T","literals":[]}),"CLAUSE_MEMBERSHIP"),
    ("U_to_alert",lambda r:r.update(decision="MANIPULATION_ALERT"),"RECORDED_DECISION_LOGIC"),
    ("intent_claim",lambda r:r["atom_explanations"][0].update(intent="confirmed malicious"),"UNEXPECTED_NARRATIVE"),
    ("unknown_coverage",lambda r:r.update(selected_atoms_available=1),"ATOM_AVAILABILITY")]
for name,mutate,reason in mutations:
    r=copy.deepcopy(row);mutate(r)
    try:audit_one(model,r,cells,contracts)
    except ValueError as e:assert reason in str(e);checks.append(name+"_rejected")
    else:raise AssertionError(name)
for status in ("EMPTY_MODEL","FAILED"):
    m=models.RuleModel("GREEDY_OR",status,(),(),{"data_origin":"BUILTIN_SYNTHETIC"},{"view_id":"TOY","input_atom_ids":[]},{"status":"HAND_CONSTRUCTED_NO_FIT","train_ids":[]})
    r=predictor.predict(m,"synthetic",{"features":{},"view_id":"TOY"})
    assert audit_one(m,r,{},contracts)["status"]=="PASS_NONEXECUTABLE_STATE"
    r["decision"]="NO_ALERT"
    try:audit_one(m,r,{},contracts)
    except ValueError as e:assert "EMPTY_FAILED_SEPARATION" in str(e);checks.append(status+"_not_no_alert")
    else:raise AssertionError(status)
write(out/"synthetic_explanation_audit.json",{"status":"PASS","checks":checks,"checks_passed":len(checks),
    "fit_calls":0,"real_inputs_read":0,"module_paths":paths,"utc":NOW(),"forbidden_calls":rejected})
