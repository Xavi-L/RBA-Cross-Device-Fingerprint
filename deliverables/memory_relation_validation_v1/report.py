"""Saved-result-only Chinese report. No source acquisition or model prediction."""
import json
from pathlib import Path


def render(out):
    out=Path(out);s=json.loads((out/'summary.json').read_text())
    w='app.web_data.navigator_layer.device_memory';n='app.android_native_data.memory_layer.total_memory_gb'
    lines=['# 内存关系的单字段对照与取值变化验证','',
      '本轮固定比较单条条件 R_REL 与 R_WEB8；完整 B/B_REL 六个保存模型另列。模型训练 0 次，关系、阈值、编码器、选择器和未知语义均未修改。旧378条受控记录与891条MTC代表记录属于已有材料上的事后补充比较。', '',
      'R_REL 沿用同次 App 的 Native 内核可见总内存 N（GiB）与 Web 暴露 W，检验 W 是否超过不小于 N 的最小二次幂。R_WEB8 只检验有效 W>8；8本身为F，缺失、默认0和错误类型保留U。固定条件与六个模型身份在新采集前写入 SETTINGS.json。版本依据见 SOURCES.md。','',
      '## 已有数据：完整分母','',
      '| 集合 | 条件 | T | F | U | FAILED | T/F覆盖 |','|---|---|---:|---:|---:|---:|---|']
    if s['historical'] and s['new_batch']:
        g=s['historical']['saved_B_REL_additional_detections'];new=s['new_batch']
        a=new['observable_changes']['conditions'];extra=new['observable_changes']['only_relation_triggered_common_evaluable']
        lines[2:2]=[f"旧模型新增的{g['planned_n']}条检出全部可由单字段对照解释（R_WEB8触发{g['conditions']['R_WEB8']['T']}/{g['planned_n']}）。新批次中，有效变化{a['R_REL']['n']}次，R_REL触发{a['R_REL']['T']}次、R_WEB8触发{a['R_WEB8']['T']}次，仅关系识别{extra}次；无可观测效应{new['no_observable_effect']['planned_n']}次单列。",'']
    for key,group in s['historical'].items():
        if 'conditions' not in group:continue
        for name,c in group['conditions'].items():
            lines.append(f"| {key} | {name} | {c['T']} | {c['F']} | {c['U']} | {c['FAILED']} | {c['evaluable']}/{c['n']} |")
    if s['historical']:
        gain=s['historical']['saved_B_REL_additional_detections']
        lines+=['',f"原保存 B_REL 相比 B 新增的 {gain['planned_n']} 条检出中，R_WEB8 同时触发 {gain['conditions']['R_WEB8']['T']} 条。因此这批新增检出可以由显眼的单字段 W>8 解释，不能仅凭旧 resource-pair 结果证明 Native 参照不可替代。旧配置还同时设置了 hardwareConcurrency=48，本轮不把其效应归因混在一起。",'',
          '| 旧攻击配置 | R_REL T/全分母 | R_WEB8 T/全分母 | 共同可评估 | 共同子集联合状态 R_REL/R_WEB8 |',
          '|---|---:|---:|---:|---|']
        for key,g in s['historical']['attack_configurations'].items():
            lines.append(f"| {key} | {g['conditions']['R_REL']['T']}/{g['planned_n']} | {g['conditions']['R_WEB8']['T']}/{g['planned_n']} | {g['common_evaluable']['n']} | {g['joint_states']} |")
        lines+=['','共同子集只用于辅助比较，未删除完整分母中的U或FAILED。summary.json 保存每组完整分母与共同子集的T/F/U/FAILED、联合状态、Web实际值分布和差异样本ID。historical.jsonl.gz 保留每条 N/W、字段状态、原始引用和原因。','',
          '| MTC集合 | W值分布 | 联合状态 R_REL/R_WEB8 |','|---|---|---|']
        for key in ('mtc/discovery','mtc/development','mtc/reserved_validation'):
            g=s['historical'][key];lines.append(f"| {key} | {g['web_value_distribution']} | {g['joint_states']} |")
        attack=s['historical']['controlled/attack']
        lines+=['',f"旧126条攻击中：共同触发 {attack['both_triggered']}/126，仅R_REL触发 {attack['only_relation_triggered_common_evaluable']}/126，仅R_WEB8触发 {attack['only_web8_triggered_common_evaluable']}/126。R_REL的独有触发发生在旧多字段配置，不是新的memory-only隔离证据；与完整B/B_REL模型新增检出9条是不同分析层次。"]
        lines+=['','常规采集正常依据沿用 mtc_cap8_replay_v1 的标签侧表；不覆盖历史 unlabeled 标签。MTC三个子集630/144/117分开，不把同一条记录的多模型输出当独立样本。','',
                '## 同样的 Web 值，来自各自同次 Native 参照的比较','']
        for value,examples in s['historical']['normal_W4_W8_examples'].items():
            for r in examples[:2]:
                binding=r['source_binding'];ref=f"hybridguard_agent/artifacts/mtc_paired244_v2_20260922_final/{binding['source_view']}.jsonl:{binding['source_line']}"
                lines.append(f"- 正常MTC `{r['sample_id']}`：N={r['operands'][n]['value']} GiB，W={value}，R_REL=F。来源 `{ref}`；原App归档行 {binding['app_raw_line']}，会话 `{binding['app_session_id']}`。")
        lines+=['','这些例子各自保留原始绑定；它们与新实验的并列展示不是把不同记录拼成一个样本。']
    lines+=['','## 新 memory-only 本地采集','']
    collection=json.loads((out/'COLLECTION.json').read_text()) if (out/'COLLECTION.json').exists() else None
    if collection:
        lines.append(f"预定72个位置（3环境×4目标×2轮×3阶段），真实接收 {collection.get('actual_records',0)} 条；不是72台设备。")
        for e in collection['environments']:
            lines.append(f"- {e['environment']}：{e['status']}，接收{e['raw_records']}/{e['planned']}；App {e.get('app_version_name')}，API {e.get('actual_android_api')}；清理自有进程={e.get('owned_processes_exited')}。{e.get('error','')}")
    if s['new_batch']:
        b=s['new_batch'];lines+=['','执行、变化和恢复分别计数：`'+json.dumps(b['effect_counts'],ensure_ascii=False)+'`。','',
          '| 环境 | 目标W | 轮次 | 操作 | 实际效果 | 恢复 | R_REL | R_WEB8 | 非目标差异 |',
          '|---|---:|---:|---|---|---|---|---|---|']
        for t in b['triplets']:
            lines.append(f"| {t['environment']} | {t['target_gib']} | {t['round']} | {t['execution']} | {t['effect']} | {t['recovery']} | {t['active_conditions']['R_REL']} | {t['active_conditions']['R_WEB8']} | {t['confound_status']} |")
        lines+=['',f"逐三阶段检查 {b['major_non_target_field_count']} 项主要非目标字段；hardwareConcurrency实际值集合为 {b['hardware_concurrency_values']}。检查覆盖导航器、屏幕、图形、自动化表面、时区以及Native总内存，差异逐项保留；无差异仅限这些观测，不代表未观测状态全部相同。",'',
                '| 同次新App记录 | N（GiB） | 上包络 | W | R_REL | R_WEB8 |',
                '|---|---:|---:|---:|---|---|']
        for r in b['native_web_examples']:
            lines.append(f"| {r['environment']} / `{r['sample_id']}` | {r['operands'][n]['value']} | {r['conditions']['R_REL'].get('diagnostics',{}).get('upper_envelope_gib')} | {r['operands'][w]['value']} | {r['conditions']['R_REL']['state']} | {r['conditions']['R_WEB8']['state']} |")
        lines+=['','这些N/W均来自表中各自同一次App会话，原始归档路径和行号见 new_batch.jsonl.gz 的 source_binding；与上面的正常MTC W=8相比，差别来自各自的Native参照。','',
                '| 新批次完整分母 | 条件 | T | F | U | FAILED | T/F覆盖 |','|---|---|---:|---:|---:|---:|---|']
        for key in ('all','normal_phases'):
            for name,c in b[key]['conditions'].items():
                lines.append(f"| {key} | {name} | {c['T']} | {c['F']} | {c['U']} | {c['FAILED']} | {c['evaluable']}/{c['n']} |")
        lines+=['','| 有效变化统计 | 条件 | T | F | U | FAILED | 全分母 |','|---|---|---:|---:|---:|---:|---:|']
        for key in ('observable_changes','observable_unconfounded','no_observable_effect'):
            for name,c in b[key]['conditions'].items():
                lines.append(f"| {key} | {name} | {c['T']} | {c['F']} | {c['U']} | {c['FAILED']} | {c['n']} |")
        extras=[t for t in b['triplets'] if t['effect_positive'] and t['active_conditions']=={'R_REL':'T','R_WEB8':'F'}]
        lines+=['',f"实际可观测变化中，仅关系识别、R_WEB8不识别的有 {len(extras)} 次；目标值为 {sorted({t['target_gib'] for t in extras})}。无可观测效应单列，不当成检出成功。实际改变但落在包络内的F仍是检出边界，不重标为正常。",'',
           '## 完整模型：六个保存模型分别评价','',
           '| 方案／折 | 集合 | 报警 | 明确不报警 | U | FAILED | EMPTY_MODEL | 明确输出/全分母 |',
           '|---|---|---:|---:|---:|---:|---:|---|']
        for m in b['models'].values():
            for subset,g in m['subsets'].items():
                c=g['decisions'];lines.append(f"| {m['scheme']}/{m['fold_id']} | {subset} | {c.get('MANIPULATION_ALERT',0)} | {c.get('NO_ALERT',0)} | {c.get('INSUFFICIENT_EVIDENCE',0)} | {c.get('FAILED',0)} | {c.get('EMPTY_MODEL',0)} | {g['explicit']}/{g['n']} |")
        lines+=['','模型逐条输出及实际触发条件见 new_batch.jsonl.gz。预测只读当前App原始记录；三阶段关系只用于事后变化/恢复核验。非目标字段差异在 summary.json 的 triplets 中逐项保存，混杂记录保留，完整模型报警不能全部归因于内存。']
        lines+=['','实际触发条件集合：`'+json.dumps(b['triggered_rule_ids_by_scheme'],ensure_ascii=False)+'`。这里分别报告同一批记录的三个模型，不把结果相加为更多样本。']
    else:lines.append('新批次尚未执行或尚未评价；不得从已有离线数据推定真实新采集成绩。')
    lines+=['','## 能力与限制','',
      'W=16 的旧新增检出并不必须依赖 Native。新批次4/8的额外识别和同次Native值见上述实测结果。降低W、改成仍在当前包络内的值、原本相同的设置均不能被这条单向上界关系当作偏离。Native过小或无效、Web默认0/缺失等保留U；来源绑定错误为FAILED。','',
      '本轮固定目标没有低于2的值，没有为补充结果追加目标或更改AVD内存。设置2但原W为2的记录不证明能识别包络内的有效修改。“降低W”或“改变但仍在包络内”的漏检边界由固定公式和单元测试说明，不能冒充真实采集的检测结果。','',
      '内存两条件在891条MTC上均未触发，65条旧Web默认0仍为U，不能把它们当明确正常。完整模型仍保留非内存条件的旧报警：development三折为1、1、0条/144，reserved_validation为2、2、1条/117，主要是inner_height/时区；这些保存输出的上下文在summary.json中另列，不是本轮新增误报。B_REL每折评价U仍为8+6条，未通过单字段对照偷偷补F。','',
      'MTC正常触发与未知以上表为准，不因报警改变正常依据。这里没有验证所有浏览器/OEM共享内存口径，不宣称官方攻击不变量，也不以少量模拟器验证替代真机正常人群证据。新小批次不与旧126条攻击合并计算总体检出率。','',
      '## 复现','', '```bash',
      'PYTHONDONTWRITEBYTECODE=1 python3 deliverables/memory_relation_validation_v1/evaluate.py summarize',
      '# 新输出目录中先复制 SETTINGS.json，再依次运行：',
      'python3 deliverables/memory_relation_validation_v1/evaluate.py historical --output-dir <新目录>',
      'python3 deliverables/memory_relation_validation_v1/collect.py --output-dir <新目录>',
      'python3 deliverables/memory_relation_validation_v1/evaluate.py new --output-dir <新目录>',
      '```','', '采集入口拒绝覆盖已有 runs；仅启动与清理本轮自有进程。原始记录位于各环境 runs/*/backend/raw_expanded_payloads.jsonl，操作与撤销证据位于 operations.jsonl、*.cdp.json 和 environment.json。']
    if (out/'VALIDATION.json').exists():
        v=json.loads((out/'VALIDATION.json').read_text());lines+=['',f"测试与检查：{v['tests_passed']}项测试通过，模型拟合0次；完整命令及检查见 VALIDATION.json。"]
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
