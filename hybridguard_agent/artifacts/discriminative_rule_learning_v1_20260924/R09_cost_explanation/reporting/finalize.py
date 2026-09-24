"""Saved-artifact-only R09 reconciliation, tables, validation and report."""
import csv
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys

out=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(out/"driver"))
from benchmark import read, lines, write, sha, require, NOW, validate_resources
from saved_audit import table

study=out.parent
root=study.parents[2]
freeze=study/"R04_freeze_r1"
checks=[]
def check(name, condition, evidence=None):
    checks.append({"check":name,"status":"PASS" if condition else "FAIL","evidence":evidence})
    require(condition,name)

manifest=read(out/"DRIVER_FREEZE_MANIFEST.json")
check("independent_driver_seal_unchanged",all(sha(out/k)==v for k,v in manifest['digests'].items()))
validate_resources(out)
check("all_219_bound_driver_resources_unchanged",True)
check("R01_protocol_recomputed_from_configs_and_candidates",read(out/"benchmark_protocol.json")["protocol_digest_recomputed"]=="4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4")
old=read(out/"checks/HISTORICAL_FILES_BEFORE.json")
changes=[]
for rel,stat in old.items():
    p=root/rel
    if not p.is_file() or p.stat().st_size!=stat["bytes"] or p.stat().st_mtime_ns!=stat["mtime_ns"]:changes.append(rel)
check("historical_workspace_protection_separate_from_R01_semantic_acceptance",not changes,{"checked_files":len(old),"changes":changes})
saved=read(out/"SAVED_ARTIFACT_MANIFEST.json")["files"]
check("saved_model_prediction_training_bytes_unchanged",all(sha(x["path"])==x["sha256"] for x in saved),{"files":len(saved)})
base=read(study/"REAL_RESEARCH_BUDGET/ledger.json")
budget=read(out/"TIMING_BUDGET_LEDGER.json")
check("original_shared_ledger_bytes_unchanged",sha(study/"REAL_RESEARCH_BUDGET/ledger.json")==budget["shared_ledger_sha256"])
check("no_fit_increment_and_no_budget_reset",budget["new_fit_jobs"]==0 and base["used_fit_jobs"]==71 and len(base["jobs"])==114)
check("linked_debit_within_original_wall_budget",budget["cumulative_charged_seconds_including_base"]<base["limits"]["wall_clock_seconds"])
link=read(study/"REAL_RESEARCH_BUDGET/R09_TIMING_LINK.json")
check("linked_account_discoverable_from_shared_budget_directory",link["account_sha256"]==sha(out/"TIMING_BUDGET_LEDGER.json"))
expected=lines(out/"expected_repeats.jsonl")
observed=lines(out/"timing_raw.jsonl")
check("exact_repeat_membership_and_execution_order",len(expected)==len(observed)==1134 and all(all(a[k]==b[k] for k in ("sequence","phase","pass_number","fold_id","model_id","opaque_id","record_role")) for a,b in zip(expected,observed)))
check("all_semantics_match_saved_closed_predictions",all(r["status"]=="MATCH" for r in observed))
check("exact_repetitions_not_new_samples",Counter(r["phase"] for r in observed)==Counter({"COLD":162,"WARMUP":162,"TIMED":810}) and len({r["opaque_id"] for r in observed})==162)
model_manifest=read(out/"model_input_manifest.json")["models"]
refs={(m["model_id"],r["opaque_id"]):r for m in model_manifest for r in lines(m["predictions_path"])}
def canonical_sha(row):return hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
check("independent_postclosure_semantic_digest_check",all(r["semantic_sha256"]==canonical_sha(refs[r["model_id"],r["opaque_id"]]) for r in observed))
check("unmeasured_boolean_and_explanation_stay_null",all(r["boolean_only_ns"] is None and r["explanation_only_ns"] is None for r in observed))
closure=read(out/"BENCHMARK_CLOSURE.json")
check("three_fresh_workers_empty_cwd_and_no_training_calls",len({x["pid"] for x in closure["startups"]})==3 and all(x["cwd_empty"] and x["fit_calls"]==0 for x in closure["startups"]) and len(closure["closures"])==3 and all(not x["rejected_training_calls"] for x in closure["closures"]))
check("frozen_python_and_module_paths",all(Path(x["executable"]).resolve()==(freeze/"dependencies/python/bin/python3.12").resolve() and all(Path(p).is_relative_to(freeze/"snapshot") for p in x["module_paths"].values()) for x in closure["startups"]))
check("one_real_attempt_no_technical_or_semantic_retries",closure["status"]=="PASS" and closure["error"] is None and read(out/"BENCHMARK_ATTEMPT.json")["retry"] is False)
synth=read(out/"synthetic_validation.json")
check("prebenchmark_synthetic_checks_on_exact_driver_bytes",synth["status"]=="PASS" and synth["driver_sha256"]==sha(out/"driver/benchmark.py"),{"checks_passed":len(synth["checks"])})
extra=read(out/"synthetic_explanation_audit.json")
check("explanation_auditor_rejects_synthetic_counterexamples",extra["status"]=="PASS",{"checks_passed":extra["checks_passed"]})
audit=read(out/"explanation_audit_summary.json")
check("all_saved_OOF_records_accounted_and_linked",audit["audited_records"]==4374 and audit["unique_supervised_stages"]==162 and audit["unique_model_stage_links"]==4212 and audit["failure_n"]==0)
check("human_semantics_not_auto_accepted",audit["manual_review"]=="NOT_REVIEWED" and audit["manual_record_n"]==4374)
fit_rows=list(csv.DictReader((out/"existing_training_costs.csv").open()))
check("71_actual_fits_with_3_reuses_excluded",len(fit_rows)==len({r['fit_job_id'] for r in fit_rows})==71 and audit["model_units"]==114 and audit["distinct_models"]==111)
check("no_training_substage_time_invented",all(r["transform_only_seconds"]==r["candidate_support_only_seconds"]==r["selection_solver_only_seconds"]==r["audit_only_seconds"]=="null" for r in fit_rows))
status_path=root/"deliverables/formal_experiment_execution_plan/EXECUTION_STATUS.json"
status=read(status_path)
check("R08_partial_and_R10_not_started",next(s for s in status["steps"] if s["id"]=="R08")["status"]=="PARTIALLY_COMPLETED" and next(s for s in status["steps"] if s["id"]=="R10")["status"]=="PENDING_AUTHORIZATION")
before=(out/"checks/GIT_STATUS_BEFORE.bin").read_bytes().split(b'\0')
after=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=root).split(b'\0')
allowed=[str(out.relative_to(root)),str(status_path.relative_to(root)),str((study/'REAL_RESEARCH_BUDGET/R09_TIMING_LINK.json').relative_to(root))]
def unrelated(rows):return sorted(x for x in rows if x and not any(x[3:].decode().startswith(p) for p in allowed))
check("270_unrelated_git_entries_preserved",unrelated(before)==unrelated(after) and len(unrelated(before))==270)

# Pure export and descriptive arithmetic from saved timing rows; no rerun.
for phase in ("COLD","WARMUP","TIMED"):
    table(out/("timing_"+phase.lower()+"_raw.csv"),[r for r in observed if r["phase"]==phase])
table(out/"timing_passes.csv",read(out/"timing_passes.json"))
table(out/"timing_cold_startup_raw.csv",closure["startups"])
table(out/"repeat_reconciliation.csv",[dict(r,observed_status=observed[i]["status"],missing=False) for i,r in enumerate(expected)])
timing_fields=["cached_input_read_parse_ns","fixed_feature_conversion_ns","predict_including_explanation_and_model_integrity_ns",
    "semantic_verification_ns","prediction_serialization_ns","sample_inclusive_ns","ipc_request_response_inclusive_ns"]
summary=[]
for phase in ("COLD","WARMUP","TIMED"):
    for fold in ("ALL_FOLDS",*[m["fold_id"] for m in model_manifest]):
        selected=[r for r in observed if r["phase"]==phase and (fold=="ALL_FOLDS" or r["fold_id"]==fold)]
        for field in timing_fields:
            values=sorted(r[field] for r in selected)
            summary.append(dict(phase=phase,fold_id=fold,field=field,unit="ns",n=len(values),mean=statistics.mean(values),
                median=statistics.median(values),p95_nearest_rank=values[math.ceil(len(values)*.95)-1],
                minimum=min(values),maximum=max(values),sum=sum(values),role="DESCRIPTIVE_ALL_PLANNED_PASSES_NO_SELECTION"))
table(out/"inference_cost_summary.csv",summary)
write(out/"inference_cost_summary.json",summary)
groups=defaultdict(list)
for r in fit_rows:groups[(r['experiment_id'],r['method_id'],r['operating_point'],r['input_view'],r['source_condition'])].append(r)
training_summary=[]
for key,rows in sorted(groups.items()):
    values=[float(r['candidate_support_selection_validation_combined_seconds']) for r in rows]
    training_summary.append(dict(zip(('experiment_id','method_id','operating_point','input_view','source_condition'),key))|
        dict(fit_n=len(rows),combined_seconds_total=sum(values),combined_seconds_median=statistics.median(values),
             combined_seconds_min=min(values),combined_seconds_max=max(values),model_statuses=Counter(r['model_status'] for r in rows),
             solver_statuses=Counter(r['solver_status'] for r in rows)))
table(out/'training_cost_summary.csv',training_summary)
write(out/'BRANCH_STATUS.json',{
    'R09_COST':{'status':'DONE','saved_fits_summarized':71,'inference_models':3,'benchmark_repeats':1134,'new_fit_jobs':0},
    'R09_EXPLANATION':{'status':'DONE_PROGRAMMATIC_AUDIT','saved_records':4374,'programmatic_failures':0,
        'manual_semantics':'NOT_REVIEWED','manual_result':None,'historical_literal_explanations':'NOT_EVALUABLE_SAVED_ADAPTER','historical_literal_result':None},
    'historical_detector_runtime':{'status':'NOT_EVALUABLE_SAVED_LOOKUP_NOT_FAIR_RUNTIME','result':None},
    'R08_parent':'PARTIALLY_COMPLETED','R08_MECHANISM':'NOT_EVALUABLE_UNVERIFIED_MECHANISM_PARTITION','R08_PROSPECTIVE':'NOT_AVAILABLE',
    'R10':{'status':'NOT_RUN_NOT_AUTHORIZED','result':None},'user_acceptance':'PENDING','stop_after_R09':True})
write(out/'VALIDATION.json',{'status':'PASS_WITH_DECLARED_NOT_RECORDED_AND_NOT_REVIEWED_ITEMS','utc':NOW(),
    'checks':checks,'checks_passed':len(checks),'synthetic_driver_checks':len(synth['checks']),
    'synthetic_explanation_checks':extra['checks_passed'],'initial_synthetic_fixture_failure_preserved':True,
    'real_fit_increment':0,'real_benchmark_attempts':1,'benchmark_record_n':1134,'benchmark_semantic_matches':1134,
    'programmatic_explanation_audit_records':4374,'manual_semantic_review':'NOT_REVIEWED','user_acceptance':'PENDING'})
write(out/'RUN_MANIFEST.json',{'stage':'R09','scope':'SAVED_COST_SUMMARY_FIXED_INFERENCE_BENCHMARK_EXPLANATION_AUDIT',
    'execution_basis_commit':'e6a1ba47f732b1494ae0a042b056866fe36f6023','started_at':budget['started_at'],'ended_at':budget['ended_at'],
    'protocol_digest':read(out/'benchmark_protocol.json')['protocol_digest_recomputed'],
    'freeze_manifest_digest':sha(freeze/'FREEZE_MANIFEST.json'),'resource_manifest_digest':sha(freeze/'RESOURCE_MANIFEST.json'),
    'driver_freeze_manifest_digest':sha(out/'DRIVER_FREEZE_MANIFEST.json'),'driver_resource_manifest_digest':sha(out/'DRIVER_RESOURCE_MANIFEST.json'),
    'runtime':read(freeze/'RESOURCE_MANIFEST.json')['runtime'],'actual_workers':closure['startups'],
    'saved_fit_jobs':71,'saved_model_units':114,'unique_saved_models':111,'saved_prediction_records':4374,
    'unique_supervised_stages':162,'new_fit_jobs':0,'new_scientific_predictions':0,'benchmark_records':1134,
    'clock':'MONOTONIC_PERF_COUNTER_NS','new_independent_samples':0,'benchmark_only':True,
    'shared_budget_base_sha256':budget['shared_ledger_sha256'],'linked_timing_account':str(out/'TIMING_BUDGET_LEDGER.json'),
    'linked_shared_budget_ref':str(study/'REAL_RESEARCH_BUDGET/R09_TIMING_LINK.json'),
    'charged_seconds_increment':budget['incremental_charged_seconds'],'cumulative_charged_seconds':budget['cumulative_charged_seconds_including_base'],
    'fit_jobs_cumulative':71,'benchmark_retries':0,'raw_collection_or_relation_extraction_measured':False,
    'manual_semantics':'NOT_REVIEWED','historical_files_modified':False,'R10_started':False,'commit_or_push':False})

timed={r['field']:r for r in summary if r['phase']=='TIMED' and r['fold_id']=='ALL_FOLDS'}
cost_lines='\n'.join(f"| {key} | {timed[key]['median']/1000:.3f} | {timed[key]['p95_nearest_rank']/1000:.3f} |" for key in timing_fields)
model_lines='\n'.join(f"| {m['fold_id']} | {m['model_id']} | {len(m['train_ids'])} | {len(m['outer_test_ids'])} |" for m in model_manifest)
train_lines=[]
for method in ('GREEDY_OR','FINITE_IP_OR','FINITE_IP_DNF2'):
    rows=[r for r in fit_rows if r['method_id']==method];v=[float(r['candidate_support_selection_validation_combined_seconds']) for r in rows]
    train_lines.append(f"| {method} | {len(rows)} | {sum(v):.9f} | {statistics.median(v):.9f} | {min(v):.9f}–{max(v):.9f} |")
total_combined=sum(float(r['candidate_support_selection_validation_combined_seconds']) for r in fit_rows)
passes=read(out/'timing_passes.json')
report=f"""# R09：训练/推理成本与解释忠实性

本步完成已保存训练成本汇总、固定 R05 主模型计时及全部已保存 OOF 的程序解释审计，等待外部验收。新增 fit = **0**；没有阈值学习、规则选择、性能优化、重建模型、R10 或提交推送。人工语义项仍为 NOT_REVIEWED。

R08_CONFIG_TRANSFER 在提交 e6a1ba47f732b1494ae0a042b056866fe36f6023 的外部验收单独登记在 R08_CONFIG_TRANSFER_EXTERNAL_ACCEPTANCE.json。R08 父步骤仍 PARTIALLY_COMPLETED；MECHANISM 不可评估，PROSPECTIVE 为 NOT_AVAILABLE，均无补造结果。

## 冻结、驱动与范围

使用 R04_freeze_r1 原副本、Python 3.12.14、macOS 15.7 arm64。原入口实际校验 3,298 个资源；由配置与候选重新计算研究 digest 为 4ab418434ea79085746c2761a1314751b7c83a538813ae3872b3d9721a2823d4。原 FREEZE_MANIFEST = bff86c2423283d9ecdf6402c2975a747707cd7d521a328561ef676cdcff2ddad，RESOURCE_MANIFEST = 7e2aa45c9cf78abc106cb61e3863c5d89f2491fe0b406b645cd48fad80bd0de0。

新增代码仅位于本目录 driver/ 与 reporting/；benchmark.py 是独立计时入口，saved_audit.py 读取已保存训练与预测，prepare.py 在真实计时前封存清单，reporting/ 仅做合成反例与保存结果导出。原 selector、predictor、投影、模型字节、encoder、freeze_time 和旧授权均未更改。驱动资源清单绑定 219 项并引用完整学习资源清单；真实计时前封存模型/输入、全局 ID 顺序、输出字段、边界、重复及失败策略。

计时只用三个 R05 GREEDY_OR/OP05/core/SRC-111 模型，各为 1 原子、1 子句、复杂度 2，规则为 DEVIATION:OFFDER-UA-001:POSITIVE。底层目录原子为负偏差极性，转换仍用冻结 project_core，未把规范极性当作目录原子极性。

| fold | model_id | 原 train 数 | outer 数 |
|---|---|---:|---:|
{model_lines}

每轮全局升序访问全部 162 个 LOEO outer ID；3 个新进程各加载一个固定模型，随后复用进程完成预热和正式轮次。cold=1、warmup=1、timed=5，时钟 perf_counter_ns。冷启动包含解释器/驱动/模块/模型加载与记录核验，未清除 OS 页缓存。使用 R02 缓存，不包含原始指纹采集、网络上传或关系提取。本步没有其他在线比较器；历史七条查表不能充当原检测器运行耗时。

## 已保存训练成本

71 次实际拟合：R05 27、R06 21、R07 9、R08 14；R06 的 3 次精确复用单列为非新增 fit。114 个模型单元引用 111 份不同模型，其中 40 个固定基线、59 个 FITTED、12 个 EMPTY_MODEL。没有删除空模型；6 个来源空候选和6个单层未找到满足约束的非空模型均保留。实际记录中无训练失败、超时或预算耗尽。

以下是旧 model.fit.elapsed_seconds，边界为候选/支持度构建、选择/求解和训练约束检查的组合计时，使用原 time.monotonic；不含先前的特征视图转换、模型保存及外层预测。不同来源/操作点/视图的合计仅用于资源描述，不是公平算法速度排名。细分见 existing_training_costs.csv 与 training_cost_summary.csv。

| 方法 | 旧 fit 数 | 组合时间总秒 | 中位秒 | 范围秒 |
|---|---:|---:|---:|---:|
{chr(10).join(train_lines)}

组合计时总计 {total_combined:.9f} 秒；71 个含拟合作业的已记进程总时间为 {sum(float(r['process_job_elapsed_seconds']) for r in fit_rows):.9f} 秒，后者还包括资源校验、预测和评价等整作业工作。未以两者相减推断开销。转换、候选支持、选择/求解、审计的单独时间均 NOT_RECORDED/null。所有114个作业累计账本时间为 {base['charged_seconds']:.9f} 秒，包含固定基线及复用作业，不是纯训练总时间。

18 次有限 IP 均记录 OPTIMAL_FINITE_POOL、gap=0.0，求解器 HiGHS/highspy 1.12.0，冻结 NumPy 2.3.5；这只覆盖各自有限池。41 次 HEURISTIC_FEASIBLE、6 次 EMPTY_CANDIDATE_POOL、6 次 HEURISTIC_NO_FEASIBLE_MODEL_FOUND_EMPTY_MODEL 保持原状态。贪心/未调用求解器的 gap 为 null。未实现 CG，不报告定价成本或 CG 最优性。候选规模、来源、训练成员、模型复杂度与原日志路径逐行保留。

## 固定输入推理计时

唯一真实尝试于 {budget['started_at']} 至 {budget['ended_at']}（UTC）完成。1,134/1,134 次全字段语义比较一致，0 失败、0 缺失、0 重试：冷 162、预热 162、正式 810。它们仍对应162个原阶段，没有增加独立样本，也没有重新汇报更高 TPR。冷/预热/正式原始表分别导出，原 predictions.jsonl 没有覆盖。

冷轮包含3次进程启动及162个调用共 {passes[0]['elapsed_inclusive_ns']/1e9:.9f} 秒；预热轮 {passes[1]['elapsed_inclusive_ns']/1e9:.9f} 秒。五个正式完整轮次毫秒为 {', '.join(f"{p['elapsed_inclusive_ns']/1e6:.6f}" for p in passes if p['phase']=='TIMED')}，包含 IPC 与逐轮审计 fsync，没有选最快轮。下表使用全部810个正式调用，单位微秒，p95 为预先声明的 nearest-rank 描述统计。

| 直接测量字段 | 中位 µs | p95 µs |
|---|---:|---:|
{cost_lines}

冻结 predict 内部交织逻辑、解释构造及 model_id 内容序列化/摘要校验，故组合列不能称为纯单规则判断耗时；boolean_only_ns、explanation_only_ns 均为 NOT_RECORDED/null，未改写代码或用减法分离。模块/模型加载、worker启动、原记录核验、预测序列化、父进程审计写入和 fsync 均有各自直接记录；inclusive 列嵌套，不能相加。sample_inclusive 不含父进程 IPC/最终审计；这些边界均不等于完整系统端到端延迟。按折结果和所有原始数值见 inference_cost_summary、timing_*。

## 解释忠实性与限制

全量4374条已关闭 OOF 已对账：R05 2106、R06 1296、R07 486、R08 486。3078条有实际原子/子句的记录通过模型成员、元数据、字段引用、原始别名、规范/目录方向、冻结数值阈值、当前缓存状态、T/F/U逻辑和覆盖分母核对；324条常数基线及648条空模型通过状态区分检查。324条历史七条只通过保存结果/合同/输入证明适配核对，缺少当前字面解释，标 NOT_EVALUABLE_SAVED_ADAPTER。

每条保留触发子句 ID；F/U 子句可作为诊断说明但未列为触发。模型没有使用的原子/子句不能通过审计。R06复用记录连接原模型与阶段；R08 LOCO 与 R05 LOEO 保留不同评价轨。4374条仅有4212个不同 model/stage 关联，唯一监督阶段仍162，不能视为4374个独立证据。100个描述阶段未加入，未连接 UNKNOWN/MTC 标签，也未重算科学性能。

程序核验对象是冻结字段引用和 R02 缓存派生值；未对原始采集语义作人工复审，4374条人工项均 NOT_REVIEWED，原始测量含义、因果机制及恶意意图不由程序一致性证明。输出结构没有新增意图字段，关系命中不是确定攻击归因，历史查表也不补造字面解释。

## 验证、预算与停止

真实计时前 {len(synth['checks'])} 项合成检查通过，覆盖三值/负极性/保存加载、固定投影、失败与未提取、空模型/常数、拟合入口拒绝、空回执与预算过期。首次夹具误用 int 代替 bool 被合同拒绝，失败日志保留；修正只涉及合成夹具，真实计时未重试。另有 {extra['checks_passed']} 项合成审计检查验证未使用规则、字段/别名/极性篡改、把U改成报警、意图字段和空/失败伪装为NO_ALERT均被拒绝。本步验证共 {len(checks)} 项通过。

原 REAL_RESEARCH_BUDGET/ledger.json 字节、71个fit、114个作业及复用路径全部不变。冻结 dispatcher 没有 R09非拟合作业，因此单列 TIMING_BUDGET_LEDGER.json，由共享预算目录的 R09_TIMING_LINK.json 关联。沿用200个fit/21600秒总预算，计时前预留上限300秒，实际计费增量 {budget['incremental_charged_seconds']:.9f} 秒；含原账本累计 {budget['cumulative_charged_seconds_including_base']:.9f} 秒、71个fit，剩余 {21600-budget['cumulative_charged_seconds_including_base']:.9f} 秒和129个fit名额。本步没有产生任何新fit授权。后续若获授权须汇总原账本与关联非拟合扣账，不能只读旧ledger而漏掉此项，也不能重置额度。

扣账覆盖正式 benchmark 的worker启动到关闭；准备/资源预检、合成验证与保存结果审计导出属于本步工程/离线工作，未被当作训练或在线模型延迟。本步没有声称完整研究人员工作时间。8974份历史文件的执行时点保护记录与配置/语义绑定分开核对；旧R01 mtime/user_acceptance 检查未重跑，旧报告、VALIDATION、模型与负结果不变，270个无关本地Git条目保留。

停止在 R09，等待审查。R10、V2、联合/集成模型、全开发集重拟合、补采、攻击工具和提交推送均未执行。
"""
with (out/'STEP_REPORT.md').open('x') as f:f.write(report)
with (out/'STARTUP.md').open('x') as f:
    f.write('''# R09 独立入口与运行边界

学习快照始终是 ../R04_freeze_r1，使用其中 dependencies/python/bin/python3.12 加 -B -I -S，在空 cwd 执行本目录脚本。真实本轮已关闭，BENCHMARK_ATTEMPT.json 会阻止在同一输出目录重试，不得删除标记或改旧产物来重跑。

实际执行顺序：原 launch.py verify → driver/benchmark.py synthetic → driver/saved_audit.py（只读旧产物）→ driver/prepare.py 封存协议/清单 → DRIVER_FREEZE_MANIFEST.json → driver/benchmark.py run → reporting/audit_synthetic.py → reporting/finalize.py（只读导出）。具体日志见 checks/；实际模块/解释器/空cwd见 workers/*/STARTUP.json。

驱动的 worker 子命令是本轮编排的固定推理子进程，无拟合接口。模型按原字节 load_model；输入仅接受预先绑定的三个R05外层成员，调用未修改的project_core与predict。没有调用core_view、single_surface_view或TrainQuantiles.fit。学习模块导入拒绝与CPython3.12局部入口监测拒绝拟合，合成反例证明边界。

driver/ 在真实计时前已绑定，reporting/ 后处理源码通过 POSTPROCESS_MANIFEST.json 独立绑定。所有CSV由已保存JSON/JSONL生成；它们不能用于新训练、择优轮次或新性能主张。运行需新授权；本轮材料可只读复核。共享预算必须读原 ledger 与 R09_TIMING_LINK 的非拟合扣账。本目录的任何清单都不授予后续拟合。
''')
write(out/'POSTPROCESS_MANIFEST.json',{'role':'SAVED_ONLY_REPORTING_NOT_TIMED_DRIVER','files':[{'path':str(p),'sha256':sha(p)} for p in sorted((out/'reporting').glob('*.py'))]})
print(json.dumps({'status':'PASS','checks':len(checks),'benchmark_matches':1134,'saved_explanation_records':4374,'fit_increment':0}))
