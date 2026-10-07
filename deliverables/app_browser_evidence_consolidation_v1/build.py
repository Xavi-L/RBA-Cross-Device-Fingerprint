"""Consolidate saved evidence; no inference, selection, fitting or new timing."""
import csv
import json
import sys
from contextlib import contextmanager
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXT = HERE.parent / 'app_resource_constrained_extension_v1'
APP = HERE.parent / 'app177_core_ablation_v1'
RESOURCE = HERE.parent / 'app_resource_paired_validation_v1'
CLOSE = HERE.parent / 'prepaper_evidence_closeout_v1'
VIEW = HERE.parent / 'cross_endpoint_four_view_comparison_v1'
REFERENCE = '5d71536a404ab3329fcc394a62ede0ce6061a502'
sys.path.insert(0, str(EXT))
from report import DISPLAY_SETS, saved_context, normal_rows, state_differences
from rx_common import counts, index, read, rows, require
from missingness import targeted_review

SCHEMES = ('APP_FULL', 'A_NO_MTC_CAP', 'A_APP_WEB_ONLY',
           'A_NO_MEMORY_REL', 'A_NO_TIMEZONE_REL', 'APP_TREE')
LABEL = dict(zip(SCHEMES, ('APP_FULL', '去MTC报警预算', 'App Web-only',
                         '去内存关系', '去时区关系', '普通App小树')))
ROLES = {
    'APP_FULL': 'App177当前候选池中的B_REL_TZ RETENTION；含Native—App Web内存/时区关系，不含新Host几何或Browser条件',
    'PAIRED_BASE': 'B2-C：冻结APP_FULL + 旧跨端时区C1；本次资源选择实际保留的S0',
    'RESOURCE_DIAGNOSTIC': '固定M/W/B条件及其与S0的未通过接入要求的组合；不是新的已接受模型',
    'FOUR_VIEW_TREE': '固定容量语言/时区有限表示树；不同于普通App候选状态小树，也不是177/67全部字段上限',
}


@contextmanager
def saved_only_guard():
    """Fail immediately if a research engine is accidentally called."""
    forbidden = {'fit', 'fit_transform', 'partial_fit', 'predict', 'predict_proba',
                 'evaluate', 'evaluate_condition', 'score', 'choose', 'select',
                 'combine', 'collect', 'benchmark', 'run_collection'}
    previous = sys.getprofile()
    record = {'forbidden_engine_calls': 0, 'blocked_calls': []}

    def profile(frame, event, arg):
        if event == 'call':
            filename = frame.f_code.co_filename
            name = frame.f_code.co_name
            if name in forbidden and (filename.startswith(str(ROOT)) or 'sklearn' in filename):
                record['forbidden_engine_calls'] += 1
                record['blocked_calls'].append(filename + ':' + name)
                raise RuntimeError('SAVED_ONLY_ENGINE_CALL_BLOCKED:' + name)
        return profile

    sys.setprofile(profile)
    try:
        yield record
    finally:
        sys.setprofile(previous)


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def write_csv(name, records):
    with (HERE / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)


def one(records, **fields):
    found = [r for r in records if all(r.get(k) == v for k, v in fields.items())]
    require(len(found) == 1, 'EXPECTED_ONE_ROW:' + str(fields))
    return found[0]


def state(c):
    return '/'.join(str(c[k]) for k in ('T', 'F', 'U', 'FAILED'))


def tn(c):
    return f"{c['T']}/{c.get('N', c.get('n'))}"


def coverage(c):
    n = c.get('N', c.get('n'))
    return f"{c['defined']}/{n} ({c['defined']/n:.2%})" if n else '不适用（N=0）'


def table(lines, headers, records):
    lines.extend(['|' + '|'.join(headers) + '|', '|' + '|'.join(['---'] * len(headers)) + '|'])
    lines.extend('|' + '|'.join(str(v).replace('|', '\\|') for v in r) + '|' for r in records)
    lines.append('')


def saved_tables():
    members, models, predictions = saved_context(EXT / 'results')
    inputs = index(rows(EXT / 'results/inputs.jsonl'))
    mi = index(members)
    require(set(inputs) == set(mi), 'INPUT_MEMBER_IDS')
    require(all(m['selected_set'] == 'S0' and m['extensions'] == [] and
                m['status'] == 'BASELINE_RETAINED' for m in models), 'SAVED_SELECTION_CHANGED')
    checks = read(EXT / 'results/candidate_checks.json')
    require(len(checks) == len({(c['base_model_id'], c['set_id']) for c in checks}) == 24,
            'SAVED_CHECK_COUNT')
    for c in checks:
        mid, st = c['base_model_id'], c['set_id']
        for co, expected in c['normals'].items():
            actual = counts(predictions[m['sample_id'], mid, st]['state'] for m in members
                            if m['cohort'] == co and m['identity'] == 'NORMAL')
            require(all(actual[k] == expected[k] for k in actual), 'SAVED_CHECK_NORMAL_TOTAL')
    selected = rows(EXT / 'results/selected_predictions.jsonl')
    require(len(index(selected, lambda r: (r['base_model_id'], r['sample_id']))) == 3015,
            'SELECTED_OUTPUT_COUNT')
    for p in selected:
        require(p['state'] == predictions[p['sample_id'], p['base_model_id'], 'S0']['state'] ==
                inputs[p['sample_id']]['base_states'][p['base_model_id']], 'SELECTED_NOT_SAVED_BASE')
        require(all(p[k] == mi[p['sample_id']][k] for k in ('cohort', 'role', 'identity')),
                'SELECTED_MEMBER_IDENTITY')
    historical = normal_rows(members, models, predictions, ('mtc_development', 'mtc_reserved_validation'))
    discovery = normal_rows(members, models, predictions, ('mtc_discovery',))
    differences = [dict(first=a['fold'], second=b['fold'], set_id=st,
                        different_ids=state_differences(members, predictions, a['base_model_id'], b['base_model_id'], st),
                        compared_members=len(members))
                   for i, a in enumerate(models) for b in models[i+1:] for st in DISPLAY_SETS]
    # No recombination: every state below is a saved output or a saved input cell.
    combined = []
    for model in models:
        for st in DISPLAY_SETS:
            check = one(checks, base_model_id=model['base_model_id'], set_id=st)
            for role in ('selection', 'historical_evaluation'):
                sub = [m for m in members if m['role'] == role]
                groups = {label: counts(predictions[m['sample_id'], model['base_model_id'], st]['state']
                                       for m in sub if m['identity'] == ident)
                          for label, ident in [('normal', 'NORMAL'), ('modified', 'EFFECTIVE_INTERVENTION')]}
                combined.append(dict(fold=model['fold'], base_model_id=model['base_model_id'], set_id=st,
                                     role=role, N=len(sub), **groups, feasible=check['feasible'],
                                     reasons=check['reasons'], macro=check['macro']))
    paired = []
    for dataset, cohorts in [('language_timezone60', ('pilot18', 'b2b42')), ('resource54', ('resource54',))]:
        sub = [m for m in members if m['cohort'] in cohorts]
        methods = [(f'{method}_{model["fold"][-2:]}', method, model['base_model_id'])
                   for model in models for method in ('APP_FULL', 'PAIRED_BASE')]
        if dataset == 'resource54':
            methods.extend((s, 'RESOURCE_DIAGNOSTIC', None) for s in ('M', 'B', 'W'))
        for label, method, mid in methods:
            def saved_state(m):
                r = inputs[m['sample_id']]
                return r['app_states'][mid] if method == 'APP_FULL' else r['base_states'][mid] if method == 'PAIRED_BASE' else r['conditions'][label]
            grouped = {}
            for group in ('App', 'Browser', 'NORMAL'):
                selected_members = [m for m in sub if (m['identity'] == 'NORMAL' if group == 'NORMAL'
                                    else m['identity'] == 'EFFECTIVE_INTERVENTION' and m['family'].startswith(group + '_'))]
                grouped[group] = counts(saved_state(m) for m in selected_members)
            paired.append(dict(dataset=dataset, method=method, label=label, **grouped))
    app = {name: read(APP / 'results/summary' / (name + '.json'))
           for name in ('main', 'configurations14', 'mtc', 'specialists', 'tree_input_integrity')}
    app['specialists'] = [r for r in app['specialists'] if r['scenario'] == 'ALL' and r['phase'] == 'ALL']
    for scheme in SCHEMES:
        for ident, n in [('NORMAL', 252), ('EFFECTIVE_INTERVENTION', 126)]:
            total = one(app['main'], scheme=scheme, identity=ident)
            cfg = [r for r in app['configurations14'] if r['scheme'] == scheme and r['identity'] == ident]
            require(len(cfg) == 14 and total['N'] == n and all(sum(r[k] for r in cfg) == total[k]
                    for k in ('N', 'T', 'F', 'U', 'FAILED', 'EMPTY_MODEL', 'defined')), 'APP_CONFIGURATION_TOTAL')
    four = read(CLOSE / 'tables/four_view.json')
    view_summary = read(VIEW / 'results/summary/summary.json')
    for r in four:
        for identity, key in [('NORMAL', 'normal'), ('EFFECTIVE_INTERVENTION', 'attack')]:
            old = [x for x in view_summary if x['plan'] == r['plan'] and x['view'] == r['view']
                   and x['group'] == identity and x['cohort'] in r['cohort'].split('+')]
            require(sum(x['T'] for x in old) == r[key+'_T'] and sum(x['n'] for x in old) == r[key+'_n'],
                    'FOUR_VIEW_SAVED_TABLE_MISMATCH')
    mtc_conditions = read(RESOURCE / 'results/summary/mtc.json')
    with (CLOSE / 'tables/cost.csv').open() as f:
        costs = [r for r in csv.DictReader(f) if r['stage'] == 'cached_from_adapted'
                 and (r['label'].startswith('P0 / ') or r['label'].startswith('R_FULL / '))]
    result = dict(method_roles=ROLES, reference_commit=REFERENCE, app_primary_stage='RETENTION; APP_TREE=FITTED',
                  app=app, paired=paired, four_view=four, resource_combinations=combined,
                  historical_mtc=historical, discovery_mtc=discovery, configuration_state_comparison=differences,
                  mtc_resource_conditions=mtc_conditions, existing_costs=costs,
                  models=[{k:m[k] for k in ('model_id','base_model_id','app_model_id','fold','selected_set','status')} for m in models])
    return result, dict(saved_models=len(models), saved_set_checks=len(checks), independent_members=len(members),
                        saved_combinations=len(predictions), saved_selected_outputs=len(selected),
                        historical_display_rows=len(historical), app_configuration_rows=len(app['configurations14']),
                        app_specialist_nonoverlapping_rows=len(app['specialists']), four_view_rows=len(four),
                        saved_selected_equals_S0=True, saved_check_totals_match_independent_members=True)


def evidence_matrix():
    data = [
        ('A1', 'App候选池主体能力与四项公平重训消融', 'APP_FULL', '原378受控+MTC630/144/117', 'SUPPORTED_WITHIN_SCOPE', '../app177_core_ablation_v1/REPORT.md', '固定RETENTION；14配置/分母完整；不等于全部177字段或未见工具上限'),
        ('A2', 'Native—App Web内存关系对资源识别有贡献', 'APP_FULL', '主实验resource-pair+内存72+资源54的App方向', 'SUPPORTED_WITHIN_SCOPE', '../app177_core_ablation_v1/results/summary/specialists.json', '与原观测缺失带来的U代价并列；非不可篡改Native真值'),
        ('A3', '时区关系帮助容忍正常换区并覆盖局部修改', 'APP_FULL', '旧378+时区36+语言/时区60', 'SUPPORTED_WITHIN_SCOPE', '../app177_core_ablation_v1/REPORT.md', '旧主表相同105/126不能证明关系无用；正常换区与新方向单列'),
        ('A4', 'Host新几何关系有局部专项证据', 'HOST_SPECIALIST', '屏幕专项72；v16工程冒烟12另计', 'SPECIALIST_ONLY', '../screen_geometry_closeout_v1/REPORT.md', '未进入APP_FULL；真机正常表现与整模接入未验证；未证明三层各有独立整模贡献'),
        ('B1', 'App+C1在已测Browser时区方向补充App主体', 'PAIRED_BASE', '语言/时区60=4App修改+10Browser修改+46正常', 'SUPPORTED_WITHIN_SCOPE', '../cross_endpoint_constrained_extension_v1/REPORT.md', '新增5次Browser时区检出；语言遗漏仍在，不代表通用跨端'),
        ('B2', '有限双端表示可区分部分单端同输入记录', 'FOUR_VIEW_TREE', '语言/时区60，P0/P1/P2', 'MIXED_RESULTS', '../cross_endpoint_four_view_comparison_v1/REPORT.md', 'P2 BOTH与REL无收益；正常偏好及配方/环境混杂保留；非177/67原始字段上限'),
        ('B3', 'Native参照在Browser内存4方向超越单字段>8', 'RESOURCE_DIAGNOSTIC', '资源54=6App修改+6Browser修改+42正常', 'LOCAL_CONDITION_EFFECT', '../app_resource_paired_validation_v1/REPORT.md', '3条局部补充；App侧6条已由内部关系报警，W仅重复；上界内/向下/共同修改未覆盖'),
        ('C1', '受约束资源接入尝试已经完成且仅保留S0', 'PAIRED_BASE / RESOURCE_DIAGNOSTIC', '同1005，开发744/历史正常261，3配置/24集合', 'COMPLETED_NEGATIVE_ADMISSION', '../app_resource_constrained_extension_v1/REPORT.md', '19/26仅S0+M/W诊断；已接受方法仍13/26；覆盖与正常报警分别报告'),
        ('C2', '新增9条U有原档案依据，重放不能恢复旧有效观测', 'RESOURCE_DIAGNOSTIC', 'discovery7+reserved2，另列3正常反例', 'SUPPORTED_AVAILABILITY_ONLY', 'missingness_review.csv', 'raw零值observed→ambiguous_sentinel；没有有效正值被漏读；API/读取机制仍未确认'),
        ('C3', '当前已接受联合模型具备通用资源检测能力', 'PAIRED_BASE', '资源接入未通过', 'NOT_SUPPORTED', '../app_resource_constrained_extension_v1/results/models.json', '不能把固定条件局部结果转写为已通过约束的系统能力'),
        ('D1', '其他UA/屏幕/WebGL等通用跨端效果', 'UNTESTED_CROSS_ENDPOINT_SCOPE', '缺相应双端修改、正常对照与同方法比较', 'REQUIRES_EVIDENCE_ONLY_IF_CLAIM_EXPANDED', '../app177_core_ablation_v1/PAIRED_COVERAGE.md', '原App专项不能替代跨端验证；无需写作前自动穷举所有字段'),
        ('D2', '新设备/未见工具攻击泛化、完整244字段公平上限', 'BROADER_CLAIM', '26开发修改有接触历史；261历史评价全正常', 'NOT_SUPPORTED', '../app_resource_constrained_extension_v1/REPORT.md', '仅扩大此主张才需独立设备/工具阳性与公平比较；本轮不采集或拟合'),
    ]
    return [dict(zip(('claim_id','claim','method','data','status','source','boundary'), r)) for r in data]


def render_report(t, review, missing, counterexamples, matrix):
    app = t['app']
    folds = [m['fold'] for m in t['models']]
    lines = ['# App主体、Browser扩展与资源双端证据统一报告', '',
        '2026-10-07；承接提交 `' + REFERENCE + '`。本轮完成报告配置修正、9条新增未知及3条正常反例的定向原证据核对、保存结果整理。**0采集、0拟合、0增量选择、0模型/条件预测、0重新计时。**此前学习与回放次数仍属于各原实验，不归零也不重复执行。', '',
        '**App主体消融、语言/时区局部跨端证据、资源配对及一次受约束接入尝试均已完成。资源接入的答案是保留基础App+C1。**当前有限结论没有新增阻断；这不支持通用资源联合能力或未见设备/工具泛化。', '',
        '## 方法与分母', '']
    table(lines, ['方法角色', '准确含义'], ROLES.items())
    lines += ['APP_FULL与各目录的Full不能互换。普通App小树属于表A的共享候选表示对照；FOUR_VIEW_TREE属于表B的有限语言/时区表示对照。Host几何保持专项身份。以下表均来自保存结果；[机器可读表](tables.json)保留全部配置、分母和来源方法身份。', '',
              '## 表A：App主体与四项重训消融', '',
              '主表固定RETENTION，普通App小树固定FITTED；不择优选择SPARSE或某个折。原378位置为126有效修改、252正常，各配置9修改+18正常。四项消融各自重训SPARSE→RETENTION，原24次规则拟合已经完成；本轮直接引用保存汇总。', '']
    table(lines, ['方案', '修改T/F/U/FAILED；N=126', '正常T/F/U/FAILED；N=252'],
          [(LABEL[s], state(one(app['main'], scheme=s, identity='EFFECTIVE_INTERVENTION')),
            state(one(app['main'], scheme=s, identity='NORMAL'))) for s in SCHEMES])
    table(lines, ['原14配置：修改T/N', *[LABEL[s] for s in SCHEMES]],
          [(cfg, *[tn(one(app['configurations14'], scheme=s, configuration=cfg, identity='EFFECTIVE_INTERVENTION')) for s in SCHEMES])
           for cfg in sorted({r['configuration'] for r in app['configurations14']})])
    normal_cfg = [r for r in app['configurations14'] if r['identity'] == 'NORMAL']
    require(all(r['N'] == 18 and (r['T'], r['F'], r['U'], r['FAILED']) == (0,18,0,0) for r in normal_cfg), 'APP_CONFIG_NORMAL_UNIFORM')
    require(all(r['U'] == r['FAILED'] == r['EMPTY_MODEL'] == 0 for r in app['main'] + app['configurations14']), 'APP_CONFIG_HIDDEN_UNDEFINED')
    lines += ['14配置每格对应的正常结果均0T/18F/0U/0FAILED；修改格余数均F。完整168行与EMPTY_MODEL=0保留在机器表，未合并成额外样本。', '',
              'MTC各格为T/F/U/FAILED，分母明确列于表头。同一891记录由三配置分别输出；这些输出不增加独立样本量。', '']
    table(lines, ['方案', '配置', 'discovery N=630', 'development N=144', 'reserved N=117'],
          [(LABEL[s], fold[-2:], *[state(one(app['mtc'], scheme=s, fold_id=fold, subset=co))
                                 for co in ('discovery','development','reserved_validation')]) for s in SCHEMES for fold in folds])
    lines += ['专项每格列修改T/N与正常T/N；内存另列无可观察效果T/N。这些不是主实验378之外可直接混成一个总体分数的独立重复试验。', '']
    specialist_rows = []
    for s in SCHEMES:
        for fold in folds:
            def specialist(co, ident):
                return one(app['specialists'], scheme=s, fold_id=fold, cohort=co, identity=ident)
            specialist_rows.append((LABEL[s], fold[-2:],
                tn(specialist('memory','EFFECTIVE_INTERVENTION'))+'；'+tn(specialist('memory','NORMAL'))+'；'+tn(specialist('memory','NO_OBSERVABLE_EFFECT')),
                tn(specialist('timezone','EFFECTIVE_INTERVENTION'))+'；'+tn(specialist('timezone','NORMAL')),
                tn(specialist('screen','EFFECTIVE_INTERVENTION'))+'；'+tn(specialist('screen','NORMAL'))))
    table(lines, ['方案', '配置', '内存72：修改；正常；无效果', '时区36：修改；正常', '屏幕72：修改；正常'], specialist_rows)
    require(all(r['U'] == r['FAILED'] == r['EMPTY_MODEL'] == 0 for r in app['specialists']), 'SPECIALIST_UNDEFINED_NOT_SHOWN')
    lines += [
        '专项上述各格其余状态均F，U/FAILED/EMPTY_MODEL均0。内存：Full在18次有效变化全部报警，去内存关系、Web-only和小树均未报警；同时Full在历史261正常有14U，去内存关系后为1U。关系收益与可用性成本都存在。', '',
        '时区：Full与去时区关系的旧主表同为105/126，但去关系与Web-only对6次正常系统换区报警，Full不报警；语言/时区新配对方向还需表B单列。不能凭旧总分相同断言关系无用，也不能把正常换区误报解释为跨端收益。', '',
        'MTC预算：去约束主表增加3次检出，却在630/144/117每条MTC正常上报警。旧受控正常0/252不能抵消该代价。屏幕：Full配置01/02的旧inner_height>710在6次正常布局变化与6次干预均报警；03两者均不报。**新Host几何未进入Full**，现有池也不提供独立Host贡献消融；不声称三层各有整模贡献。', '',
        'Host几何的独立专项记录见[屏幕收尾报告](../screen_geometry_closeout_v1/REPORT.md)：旧72位置中正常0/66报警、有效修改6/6；v16的12个工程冒烟位置单列，保留1个预定故障U及2个FAILED_EVIDENCE流程位置，未混入旧72或App主表。真机正常表现与整模接入仍未验证。', '',
        '普通App小树固定depth≤3、min_samples_leaf=2、阈值0.5；使用同折完整候选准入后的63/63/54个原子，各编码T/F/U，源池为50基础模板+3固定关系。没有只喂最终选中规则，也没有Browser、标签、ID、未来恢复输入；它不是全部177原始字段的性能上限。各折受控留出126有15条含未知候选，MTC891有73条；树仍给二值，不能称观测完整率提高。原3棵交付树及1次导出失败的工程fit分开留档。', '',
        '详细依据：[App主体报告](../app177_core_ablation_v1/REPORT.md)、[固定阶段汇总入口](../app177_core_ablation_v1/summarize.py)、[Browser配对覆盖范围](../app177_core_ablation_v1/PAIRED_COVERAGE.md)。原378与旧专项没有同期Browser；新增54条不倒填这些历史配对。', '',
        '## 表B：双端参照的已测作用', '',
        '语言/时区60＝App修改4、Browser修改10、正常46；资源54＝App修改6、Browser修改6、正常42。三个配置分别列出；不把重复输出当额外样本。M/B/W在这里是单个诊断条件，表C才是与基础S0的固定组合。', '']
    table(lines, ['数据', '方法/配置', 'App修改T/N', 'Browser修改T/N', '正常T/N', '三组U合计', '三组FAILED合计'],
          [(r['dataset'], r['label'], tn(r['App']), tn(r['Browser']), tn(r['NORMAL']),
            sum(r[k]['U'] for k in ('App','Browser','NORMAL')), sum(r[k]['FAILED'] for k in ('App','Browser','NORMAL'))) for r in t['paired']])
    lines += [
        '语言/时区：APP_FULL为App时区2/2、App语言0/2，Browser两家族均0；PAIRED_BASE由C1补充Browser时区5/5，仍漏Browser语言5条，总7/14，正常0/46。B3-B中放开匹配正常报警预算后选C2可得9/14，但相对C1新增7条语言检出、丢失5条Browser时区检出，并引入2/34匹配正常报警；这是ABLATION_ONLY，不能替代实际PAIRED_BASE。', '',
        '资源：App侧6次修改已由Native—App Web内部关系检出，去内存关系与Web-only均0/6；W在这些位置报警只是重复证据，M也不触发。Browser资源16/48的3条被M与单字段>8的B共同识别；Browser内存4的3条为M/W报警而B不报警，才是Native参照相对B的直接局部补充。新环境原内存报告2，4为向上变化；向下、上界内与双端协调变化仍未获得该批覆盖。', '',
        '固定单端有限视图存在可验证的信息缺口：App视图下旧先导12正常与6次Browser修改同输入，匹配组30正常与4次Browser修改同输入；Browser视图下28正常与4次App修改同输入，另有2次正常换区与2次Browser时区修改都报告-540。它们说明该固定输入不能区分这些成员，不证明任何单端全字段模型都无法区分。见[同输入反例](../cross_endpoint_four_view_comparison_v1/results/input_collisions.json)。', '',
        '四视图固定depth≤3、min_samples_leaf=2、阈值0.5。V_APP仅7个语言/时区派生测量，V_BROWSER为4个，BOTH为11个，REL再加入C1/C2状态指示。P0是开发拟合；P1/P2是已接触数据的整批留出诊断，均非新盲测。', '']
    table(lines, ['方案', '视图', '报告对象', '修改T/N', '正常T/N', 'U', 'FAILED'],
          [(r['plan'], r['view'], r['cohort'], f"{r['attack_T']}/{r['attack_n']}",
            f"{r['normal_T']}/{r['normal_n']}", r['U'], r['FAILED']) for r in t['four_view']])
    lines += [
        'P0：REL在开发60位置降低正常报警，不能据此声称可泛化的全面优势。P1：REL在留出先导正常0/12，但训练匹配正常2/34仍超预算1。P2：BOTH与REL在全部951位置状态/概率一致；匹配留出均4/8修改报警、6/34正常报警，**显式关系没有额外收益**。普通设置变化仍是正常标签。', '',
        '两次正常Browser语言偏好change：P0 REL为F，P1/P2 REL均为T；不同列表配方和Native locale、环境、ABI、版本可能相互混杂，现有材料不能分离。正常内存差异也不能直接当攻击：原891 MTC固定M为3T/838F/50U，W为62T/741F/88U，B为0T/841F/50U；FAILED均0。', '',
        '四视图在951位置均输出二值，但完整输入只有V_APP 947/951、V_BROWSER 920/951、BOTH与REL各918/951。缺失指示与训练侧填充值允许部分输入二值输出，不等于未知观测被恢复，也不与规则U直接视为同一语义。', '',
        '下表仅引用原B3-B计时，单位μs/位置，60位置批量摊销、10轮；p95是批摊销样本的p95，不是在线单请求尾延迟，未含新采集/网络成本，也不是本轮资源组合重新计时。', '']
    table(lines, ['原方法标记', '缓存适配输入→输出中位', '批摊销p95'],
          [(r['label'], f"{float(r['median_amortized_us']):.2f}", f"{float(r['p95_batch_amortized_us']):.2f}") for r in t['existing_costs']])
    lines += ['继续引用既有[四视图检出图](../prepaper_evidence_closeout_v1/figures/fig01_four_view_detection.svg)、[四视图正常报警图](../prepaper_evidence_closeout_v1/figures/fig02_four_view_normal_alarms.svg)、[正常偏好图](../prepaper_evidence_closeout_v1/figures/fig04_preference_recipe.svg)与[成本边界](../prepaper_evidence_closeout_v1/REPORT.md)；不复制图或重跑计时。', '',
        '## 表C：同1,005成员的资源接入结论', '',
        '开发744＝718正常+26有效修改；历史评价261全正常，无攻击阳性。26修改均有开发接触历史；历史正常表现不能证明新攻击泛化。下表全由保存的combinations与独立members按模型ID重汇总。正常和修改格均为T/F/U/FAILED，覆盖单列；历史修改N=0不计算检出率。', '']
    reason = {'MODEL_DEFINED_COVERAGE:mtc_discovery':'联合明确不足90%',
              'NORMAL_ALARM_BUDGET:mtc_discovery':'MTC正常报警超预算', 'CANDIDATE_COVERAGE:W':'W候选明确不足90%'}
    table(lines, ['配置', '组合', '范围N', '修改T/F/U/FAILED（N）', '正常T/F/U/FAILED（N）', '正常明确覆盖', '开发接入结论'],
          [(r['fold'][-2:], r['set_id'], ('开发' if r['role']=='selection' else '历史')+str(r['N']),
            state(r['modified'])+f" ({r['modified']['n']})", state(r['normal'])+f" ({r['normal']['n']})", coverage(r['normal']),
            '保留S0' if r['feasible'] else '；'.join(reason.get(x,x) for x in r['reasons'])) for r in t['resource_combinations']])
    lines += ['接入约束逐正常来源执行，不能以开发744的总体覆盖替代MTC630门槛。各配置discovery实际如下；先导12、匹配34、资源42在四组合下均全部F、100%明确。', '']
    table(lines, ['配置', '组合', 'MTC discovery N', 'T', 'F', 'U', 'FAILED', '明确覆盖'],
          [(r['fold'][-2:], r['set_id'], r['n'], r['T'], r['F'], r['U'], r['FAILED'], coverage(r)) for r in t['discovery_mtc']])
    lines += ['S0为567/630，恰好90%；M/B单条件虽589/630明确，与基础合用却只有560/630。W另有超预算正常报警和候选覆盖不足。容量未放宽、U未补F、阈值与上界未改。**实际保留仍13/26、八家族宏平均50%；19/26和75%只属于S0+M/W诊断。**S0+B为16/26、宏平均62.5%，同样未通过。完整8集合×3配置仍为原24组检查。', '',
        '相对基础：M新增6次Browser检出和2开发/1历史正常报警；B新增3次检出、无新增正常报警；W新增6次检出和40开发/22历史正常报警。三者都新增7开发+2历史正常U，没有检出丢失或新增FAILED。261历史正常须继续拆开：', '']
    table(lines, ['配置', '组合', '历史集合', 'N', 'T', 'F', 'U', 'FAILED', '明确覆盖'],
          [(r['fold'][-2:], r['set_id'], r['cohort'].removeprefix('mtc_'), r['n'], r['T'], r['F'], r['U'], r['FAILED'], coverage(r)) for r in t['historical_mtc']])
    lines += ['配置修正：[简短修正记录](REPORT_CORRECTION.md)。原报告用配置01代表历史表并误称三配置逐条相同；现为24行模型ID汇总。01/02确经全1,005成员逐状态比较相同，03在每个S0/M/B/W集合各有8条不同；这里只说明逐ID验证结果，展示仍保留三配置。', '',
        '## 9条新增未知与3条正常反例的定向说明', '',
        f"唯一缺测成员{review['unique_missing_records']}条：discovery 7、development 0、reserved_validation 2；M/B和三配置的ID集合相同。每条只沿一次P2→P1→App raw/Browser raw与原C1物理行核对，共{review['decoded_original_records']}条原始/中间引用记录，未重审其余MTC。比较保存的payload标识、session/receipt/批次绑定；没有全档案重哈希。", '',
        '9条Browser字段都存在，原值0、原状态observed；既有[_quality分支](../../hybridguard_agent/research/mtc_relation_sources.py)把device_memory零值标为ambiguous_sentinel。P1保存值/状态/quality与raw一致；[资源operand分支](../app_resource_paired_validation_v1/conditions.py)要求observed且observed_value，因此为QUALITY_UNAVAILABLE→U。observed不自动使零值成为有效零GiB容量。', '',
        '均归A：原档案已有不可用零值，现有U有依据；B类有效正观测被适配漏读为0条。更深机制仍属C/证据不足：归档origin均HTTPS（GitHub 7、采集站2），记录了v1探针与自报UA Chrome版本，未保存isSecureContext或直接API可用性/读取异常。不能用其他批次v2源码、HTTP或某版本推定本批原因，也不能称这些记录状态为runtime_error/unsupported。', '',
        '这些记录App Native/App Web内存有效、App内存条件F、三配置App和C1均F，所以S0明确F；M/B需要的Browser内存不可用，原OR中的F与U得到U。没有从另一端补测量。', '']
    table(lines, ['成员ID', '原组', 'Browser raw值/状态', 'P1 quality', 'App内存/C1', '原分类'],
          [(r['sample_id'],r['group'],str(r['raw_browser_memory'])+'/'+r['raw_field_status'],r['p1_quality'],r['app_memory_condition']+'/'+r['C1'],r['classification']) for r in missing])
    lines += ['逐条原物理行、背景和分支见[missingness_review.csv](missingness_review.csv)。以下3条另属有效正常反例，不属于缺测：', '']
    table(lines, ['成员ID', '原组', 'Native GiB', 'App Web', 'Browser', 'Native上界', 'M/B/W'],
          [(r['sample_id'],r['group'],r['native_memory_gib'],r['app_web_memory'],r['raw_browser_memory'],r['native_upper_envelope_gib'],r['M']+'/'+r['B']+'/'+r['W']) for r in counterexamples])
    lines += ['它们仍为NORMAL：discovery 2、reserved_validation 1；原值/标签/分组和T状态均未改。完整引用见[normal_counterexamples.csv](normal_counterexamples.csv)。**关闭“再次回放恢复这批旧Browser有效观测”任务**：归档未保存可恢复的有效正值；机制未确认不是降低门槛或把560改为567的理由。', '',
        '## 结论状态与证据边界', '']
    table(lines, ['结论', '方法', '状态', '边界'], [(r['claim'],r['method'],r['status'],r['boundary']) for r in matrix])
    lines += ['[证据矩阵](evidence_matrix.csv)附逐项数据与来源。当前有限主张已经有证据，没有因资源未入选而尚未运行的实验，也没有新增适配错误阻断。App主体仍是主线；Browser局部结果与资源负面接入结果同时保留。', '',
        '只有扩大“更多设备/未见工具攻击泛化”时，优先缺口才是开发接触之外的独立阳性与匹配正常、按同方法比较；现有261全正常无法回答。UA/屏幕/WebGL其他跨端字段同理按具体主张留限制，不自动升级为写作前必须穷举的事项。实验整理阶段到此停止；用户随后单独授权提交推送供远端审查，不新增采集、拟合或W1全文工作。', '',
        '## 复现与本轮检查', '',
        '运行 `PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_resource_constrained_extension_v1/report.py` 修正原展示；运行 `PYTHONDONTWRITEBYTECODE=1 python3 deliverables/app_browser_evidence_consolidation_v1/build.py` 生成本目录表格；再运行同目录 `test_consolidation.py`。汇总入口有禁用研究引擎的执行检查，调用拟合/选择/预测/条件计算会直接失败。', '',
        '检查范围与结果见[CHECK.json](CHECK.json)：按模型ID的24行历史表、逐ID等价条件、3模型/24旧检查/1,005成员/24,120旧组合/3,015选择输出，及9+3定向记录。原模型、输入、预测、选择、计时均受保护；根目录仅更新当前状态并标明历史章节。', '',
        '16个必要证据文件已经由此前明确授权纳入public仓库，见[原审核范围](../app_resource_constrained_extension_v1/REMOTE_REVIEW.md)；本轮按现有物理引用使用，不重复复制raw，不添加其他原始指纹/票据/日志。', '']
    return '\n'.join(lines)


def render_correction(t):
    lines = ['# 资源报告配置展示修正', '',
        '2026-10-07；原实验提交 `' + REFERENCE + '`。', '',
        '原report.py历史表只过滤models[0][fold]，却声称三个配置逐条状态相同；discovery的“6T/561F/63U”和W“46条报警”也被泛化到03。', '',
        '现从保存combinations.jsonl与独立members.jsonl按base_model_id重汇总，展示3配置×S0/M/B/W×144/117＝24行，逐行给N/T/F/U/FAILED/明确覆盖；discovery文字按配置生成。01/02基础为6T/561F/63U、W为46T；03基础为0T/567F/63U、W为40T。历史03的基础144/117正常报警分别为0/0，01/02为1/1。', '',
        '只修改报告生成器与报告，不改模型或状态。保存历史汇总及24组旧候选检查的正常总数与独立成员重汇总一致；未发现底层数据阻断。逐成员比较如下，不能用总数等同替代该检查：', '']
    table(lines, ['配置对', '集合', '比较成员N', '不同状态数'],
          [(r['first'][-2:]+'/'+r['second'][-2:],r['set_id'],r['compared_members'],len(r['different_ids'])) for r in t['configuration_state_comparison']])
    lines += ['影响范围仅为展示和结论适用配置说明；三个已保存选择仍为S0。新增9条未知和3条正常反例核对未重选模型，也未对旧输出补值。检查结果见[CHECK.json](CHECK.json)。', '']
    return '\n'.join(lines)


def build():
    with saved_only_guard() as guard:
        t, totals = saved_tables()
        missing, counterexamples, chains, review = targeted_review()
        require(not review['blocker_items'], 'RAW_ADAPTER_DISAGREEMENT_REQUIRES_EXPLICIT_CORRECTION')
        matrix = evidence_matrix()
        write_json('tables.json', t)
        write_csv('missingness_review.csv', missing)
        write_csv('normal_counterexamples.csv', counterexamples)
        write_csv('evidence_matrix.csv', matrix)
        (HERE/'REPORT.md').write_text(render_report(t, review, missing, counterexamples, matrix))
        (HERE/'REPORT_CORRECTION.md').write_text(render_correction(t))
    check = dict(reference_commit=REFERENCE, status='AGGREGATION_AND_TARGETED_REVIEW_PASS',
                 scope='saved-result aggregation + 9 unique missing records + 3 normal counterexamples',
                 saved_counts=totals, targeted_review=review,
                 targeted_binding_checks=[dict(sample_id=r['sample_id'],group=r['group'],bindings=r['bindings'],
                                              raw_p1_fields_match=all(p['p1_matches'] for p in r['fields'].values())) for r in chains],
                 execution_guard=guard, regression_tests='NOT_RUN_BY_BUILD',
                 source_protection='verify current git diff separately; no model or raw outputs written by this builder',
                 source_tables=[str(p.relative_to(ROOT)) for p in (APP/'results/summary', EXT/'results',
                                RESOURCE/'results/summary', CLOSE/'tables', VIEW/'results/summary')])
    write_json('CHECK.json', check)
    return check


if __name__ == '__main__':
    # The CLI has no legitimate network/process action; reject accidental additions.
    def audit(event, args):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise RuntimeError('SAVED_ONLY_EXTERNAL_ACTION_BLOCKED:' + event)
    sys.addaudithook(audit)
    result = build()
    print(json.dumps({'status':result['status'], **result['saved_counts']}, ensure_ascii=False))
