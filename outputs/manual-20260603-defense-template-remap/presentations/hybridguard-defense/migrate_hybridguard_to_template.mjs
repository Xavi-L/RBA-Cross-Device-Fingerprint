#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";

import {
  ensureArtifactToolWorkspace,
  importArtifactTool,
  readImageBlob,
  saveBlobToFile,
  padSlideNumber
} from "/Users/xavier/.codex/plugins/cache/openai-primary-runtime/presentations/26.521.10419/skills/presentations/scripts/artifact_tool_utils.mjs";

const workspace = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/outputs/manual-20260603-defense-template-remap/presentations/hybridguard-defense";
const repo = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint";
const starterPptxPath = path.join(workspace, "template-starter.pptx");
const outputDir = path.join(workspace, "output");
const previewDir = path.join(workspace, "preview", "final");
const layoutDir = path.join(workspace, "layout", "final");
const finalPptxPath = path.join(outputDir, "HybridGuard毕业论文答辩_新版模板适配.pptx");
const deliveryPptxPath = path.join(repo, "presentaion", "HybridGuard毕业论文答辩_新版模板适配.pptx");

const images = {
  architecture: path.join(repo, "thesis_materials/top_journal_figures/fig2-1_system_architecture.png"),
  offline: path.join(repo, "thesis_materials/top_journal_figures/fig2-2_offline_label_training_flow.png"),
  onDevice: path.join(repo, "thesis_materials/top_journal_figures/fig3-1_on_device_module_structure.png"),
  data: path.join(repo, "ablation/figures/figure_01_source_distribution.png"),
  grouped: path.join(repo, "ablation/figures/figure_04_grouped_main_results.png"),
  importance: path.join(repo, "ablation/figures/figure_05_consistency_feature_importance.png")
};

function slidesFromPresentation(presentation) {
  return Array.isArray(presentation.slides?.items)
    ? presentation.slides.items
    : Array.from({ length: presentation.slides.count }, (_, index) => presentation.slides.getItem(index));
}

function elementById(slide, id) {
  return slide.elements.items.find((element) => String(element.id) === String(id) || String(element.aid) === String(id));
}

function setText(slide, id, value, options = {}) {
  const element = elementById(slide, id);
  if (!element) throw new Error(`Missing text element ${id} on slide ${slide.index + 1}`);
  element.text = value;
  if (options.fontSize) element.text.fontSize = options.fontSize;
  if (options.bold !== undefined) element.text.bold = options.bold;
  if (options.color) element.text.color = options.color;
  if (options.alignment) element.text.alignment = options.alignment;
  if (options.verticalAlignment) element.text.verticalAlignment = options.verticalAlignment;
  return element;
}

function deleteElements(slide, ids) {
  for (const id of ids) {
    const element = elementById(slide, id);
    if (!element) continue;
    if (typeof element.delete === "function") {
      element.delete();
    } else {
      if (element.text !== undefined) element.text = "";
      setPosition(element, [-5000, -5000, 1, 1]);
    }
  }
}

function setTable(slide, id, values, fontSize = 18) {
  const table = elementById(slide, id);
  if (!table) throw new Error(`Missing table ${id} on slide ${slide.index + 1}`);
  const rowCount = Number.isInteger(table.rowCount) ? table.rowCount : values.length;
  const columnCount = Number.isInteger(table.columnCount)
    ? table.columnCount
    : Math.max(...values.map((row) => row.length));
  const normalized = Array.from({ length: rowCount }, (_, row) =>
    Array.from({ length: columnCount }, (_, col) => values[row]?.[col] ?? "")
  );
  table.setValues(normalized);
  try {
    for (let row = 0; row < table.rowCount; row += 1) {
      for (let col = 0; col < table.columnCount; col += 1) {
        const cell = table.getCell(row, col);
        if (cell?.text) cell.text.fontSize = fontSize;
      }
    }
  } catch {
    // Some imported tables expose setValues but not cell-level text access.
  }
  return table;
}

function setPosition(element, box) {
  if (!element) return;
  const rect = { left: box[0], top: box[1], width: box[2], height: box[3] };
  if (element.position?.set) element.position.set(rect);
  else element.position = rect;
}

async function replaceImage(slide, id, imagePath, box, fit = "contain") {
  let image = elementById(slide, id);
  if (!image || typeof image.replace !== "function") {
    image = slide.images.add({ blob: await readImageBlob(imagePath), fit, alt: path.basename(imagePath) });
  } else {
    image.replace({ blob: await readImageBlob(imagePath), fit, alt: path.basename(imagePath) });
  }
  setPosition(image, box);
  return image;
}

async function addImage(slide, imagePath, box, fit = "contain") {
  const image = slide.images.add({ blob: await readImageBlob(imagePath), fit, alt: path.basename(imagePath) });
  setPosition(image, box);
  return image;
}

async function renderFinal(presentation, slides) {
  await fs.rm(previewDir, { recursive: true, force: true });
  await fs.rm(layoutDir, { recursive: true, force: true });
  await fs.mkdir(previewDir, { recursive: true });
  await fs.mkdir(layoutDir, { recursive: true });
  for (let index = 0; index < slides.length; index += 1) {
    const slide = slides[index];
    const padded = padSlideNumber(index + 1);
    await saveBlobToFile(await presentation.export({ slide, format: "png", scale: 1.2 }), path.join(previewDir, `final-slide-${padded}.png`));
    await saveBlobToFile(await presentation.export({ slide, format: "layout" }), path.join(layoutDir, `final-slide-${padded}.layout.json`));
  }
}

await ensureArtifactToolWorkspace(workspace);
const { FileBlob, PresentationFile } = await importArtifactTool(workspace);
const presentation = await PresentationFile.importPptx(await FileBlob.load(starterPptxPath));
const slides = slidesFromPresentation(presentation);

// 1. Cover
setText(slides[0], "2", "RBA中基于Web-WebView-Android\n多端关联的设备身份交叉验证机制研究", { fontSize: 45, bold: true, alignment: "center" });
setText(slides[0], "4", "答辩人：梁骁\n本科毕业论文答辩\n2026年6月", { fontSize: 24, alignment: "center" });

// 3-5. 绪论
setText(slides[2], "18", "绪论", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[3], "8", "绪论：研究背景", { fontSize: 34, bold: true });
setText(slides[3], "4", [
  "移动端RBA场景",
  "用户登录、交易等关键环节需要判断访问环境是否可信",
  "Hybrid App一次会话会同时经过Android Native、WebView宿主和Web前端",
  "局部字段可能被伪造、重放或遮蔽，单端指纹难以判断同一设备身份",
  "",
  "核心问题",
  "同一会话中的多端证据是否相互一致，能否暴露伪造、重放和容器绕过风险",
  "",
  "研究主张",
  "三端融合的价值不只是采集更多字段，而是建立可互证、可发现矛盾的跨层关系"
].join("\n"), { fontSize: 25 });

setText(slides[4], "8", "绪论：研究意义、目标与内容", { fontSize: 34, bold: true });
setText(slides[4], "4", [
  "研究意义",
  "在低打扰、少外传、可解释的前提下，为移动端RBA提供跨端互证能力。",
  "",
  "研究目标",
  "围绕“同一会话是否来自同一可信设备环境”，完成多端关联验证机制，并在Android端侧形成轻量评分闭环。",
  "",
  "研究内容",
  "1. 三端设备指纹采集与session_id会话对齐",
  "2. 跨层语义规则知识库与离线标签生成",
  "3. 端侧65维特征编码和随机森林Java推理",
  "4. 三端消融、跨层一致性消融和分组验证"
].join("\n"), { fontSize: 25 });

// 6-7. 相关技术介绍
setText(slides[5], "18", "相关技术介绍", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[6], "8", "相关技术介绍：Hybrid App、WebView 与 RBA 风控", { fontSize: 32, bold: true });
setText(slides[6], "22", [
  "移动端RBA需要在会话级别判断设备身份、宿主容器和前端运行环境是否一致。",
  "已有研究分别关注设备指纹、WebView安全和JSBridge风险；本文将这些线索放到同一会话中做跨层交叉验证。"
].join("\n"), { fontSize: 23 });
setText(slides[6], "13", [
  "设备指纹与RBA",
  "设备型号、系统版本、屏幕、WebGL、Canvas、UA等字段可辅助风险识别",
  "挑战在于局部字段容易被伪造，单端证据缺少互证关系"
].join("\n"), { fontSize: 21 });
setText(slides[6], "15", [
  "WebView与JSBridge安全",
  "Hybrid App中WebView承载业务页面，也暴露宿主配置和桥接能力",
  "Provider版本、默认UA、debuggable、安装来源和JSBridge可作为容器真实性信号"
].join("\n"), { fontSize: 21 });
deleteElements(slides[6], ["26", "27"]);

// 8-10. 系统设计与总体架构
setText(slides[7], "18", "系统设计与总体架构", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[8], "8", "系统设计与总体架构：四层闭环", { fontSize: 32, bold: true });
await replaceImage(slides[8], "12", images.architecture, [110, 255, 1720, 735]);

setText(slides[9], "8", "系统设计与总体架构：离线标注训练链路", { fontSize: 32, bold: true });
await replaceImage(slides[9], "12", images.offline, [130, 255, 1680, 735]);

// 11-14. 关键模块设计与实现
setText(slides[10], "18", "关键模块设计与实现", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[11], "8", "关键模块设计与实现：三端采集与会话对齐", { fontSize: 32, bold: true });
setText(slides[11], "5", [
  "三端采集",
  "Android Native采集底层设备、系统、物理屏幕与安全配置",
  "WebView宿主采集provider、默认UA、JSBridge、安装来源与debuggable",
  "Web前端采集Navigator、DPR、WebGL、Canvas、时区与算力挑战"
].join("\n"), { fontSize: 21 });
setText(slides[11], "6", [
  "会话对齐",
  "三端数据异步到达，后端以session_id作为会话键",
  "FastAPI接口接收并增量合并非空字段",
  "原始嵌套JSON用于审计，展开JSONL用于离线标注、训练和消融实验"
].join("\n"), { fontSize: 21 });
setTable(slides[11], "16", [
  ["特征层", "字段数", "代表字段"],
  ["Native", "33", "型号、系统、屏幕、电池、传感器、ADB"],
  ["WebView", "14", "JSBridge、Provider、安装来源、debuggable"],
  ["Web", "18", "UA、DPR、WebGL、Canvas、时区"],
  ["Raw all", "65", "训练侧完整原始字段"],
  ["", "", ""],
  ["会话键", "session_id", "合并异步上报"],
  ["存储", "JSON/JSONL", "审计与训练并行"],
  ["风险输入", "三端payload", "规则标注与模型训练"],
  ["端侧输入", "65维编码", "随机森林推理"]
], 16);

setText(slides[12], "8", "关键模块设计与实现：规则知识库与离线标注", { fontSize: 32, bold: true });
setText(slides[12], "4", [
  "规则知识库",
  "将屏幕、UA、JSBridge、传感器和WebGL等关系提炼为跨层一致性规则",
  "作用一：给离线标签生产提供统一判断边界",
  "作用二：让模型风险分能够回溯到具体异常关系"
].join("\n"), { fontSize: 22 });
setText(slides[12], "12", "规则类别示例", { fontSize: 18, bold: true, alignment: "center" });
setText(slides[12], "13", "离线标注训练链路", { fontSize: 18, bold: true, alignment: "center" });
setTable(slides[12], "15", [
  ["规则类别", "核心含义"],
  ["屏幕/UA一致性", "跨层字段应相互呼应"]
], 14);
setTable(slides[12], "16", [
  ["阶段", "输入", "输出", "位置"],
  ["离线标注", "三端样本+规则库", "risk_score/risk_reason", "训练侧"]
], 13);

setText(slides[13], "8", "关键模块设计与实现：端侧评分闭环", { fontSize: 32, bold: true });
setText(slides[13], "22", [
  "端侧运行时在App内完成三端采集、特征编码和模型推理。",
  "",
  "RiskFeatureEncoder固化训练阶段65维字段顺序、类别映射和缺失值策略，保证训练侧与端侧输入语义一致。",
  "",
  "DeviceRiskScorer由m2cgen导出的随机森林Java代码实现，运行时只上传风险分、风险等级和解释摘要，减少原始三端指纹外传。"
].join("\n"), { fontSize: 23 });
await replaceImage(slides[13], "24", images.onDevice, [1120, 260, 760, 610]);

// 15-21. 实验分析
setText(slides[14], "18", "实验分析", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[15], "8", "实验分析：数据来源与分组验证设计", { fontSize: 32, bold: true });
setText(slides[15], "22", [
  "数据覆盖真实设备、云测环境和脚本攻击模板，共1323条带风险标签样本。",
  "",
  "三类来源规模为286 / 737 / 300。完整原始字段为65维，后续实验同时比较原始字段、跨层一致性特征和三端语义规则特征。",
  "",
  "分组交叉验证按真实设备、云测设备和脚本攻击模板构造group_id，用来控制同源泄漏，主结论以Grouped结果为准。"
].join("\n"), { fontSize: 22 });
setPosition(elementById(slides[15], "22"), [130, 260, 900, 320]);
deleteElements(slides[15], ["17", "18", "19", "20", "24", "25", "26", "27", "28"]);
await addImage(slides[15], images.data, [1120, 275, 700, 600]);

setText(slides[16], "8", "实验分析：评分器选型", { fontSize: 32, bold: true });
setText(slides[16], "22", [
  "目标：端侧承接离线规则语义。",
  "随机森林误差低，可导出Java。"
].join("\n"), { fontSize: 21 });
setPosition(elementById(slides[16], "22"), [130, 290, 850, 150]);
setTable(slides[16], "24", [
  ["模型", "MAE", "端侧适配"],
  ["随机森林", "1.14", "Java导出"],
  ["浅层MLP", "2.42", "误差较高"]
], 14);
setTable(slides[16], "25", [
  ["选择原因", "工程含义", "答辩口径"],
  ["部署直接", "m2cgen导出Java", "接入Android端"],
  ["结构化稳定", "适合小样本字段", "不是算法创新"],
  ["解释性较好", "可看重要性", "反查风险来源"],
  ["", "", ""],
  ["", "", ""],
  ["", "", ""],
  ["", "", ""],
  ["", "", ""]
], 14);

setText(slides[17], "8", "实验分析：三端原始特征消融", { fontSize: 32, bold: true });
setText(slides[17], "22", [
  "先按三端粗粒度删减。",
  "结论：字段更多不等于更稳。"
].join("\n"), { fontSize: 21 });
setPosition(elementById(slides[17], "22"), [130, 290, 850, 150]);
setTable(slides[17], "24", [
  ["配置", "特征数", "Holdout MAE"],
  ["WebView only", "14", "1.139"],
  ["Raw all", "65", "1.140"]
], 14);
setTable(slides[17], "25", [
  ["配置", "Grouped MAE", "解释"],
  ["WebView only", "1.541", "宿主信号较强"],
  ["Native+WebView", "2.202", "覆盖大量标签逻辑"],
  ["Raw all", "2.642", "完整但含冗余"],
  ["Web only", "12.188", "未见分组不稳定"],
  ["结论", "", "字段更多不等于更稳"],
  ["方向", "", "转向关系特征"],
  ["", "", ""],
  ["", "", ""]
], 15);

setText(slides[18], "8", "实验分析：一致性特征与分组主结果", { fontSize: 32, bold: true });
setText(slides[18], "22", [
  "一致性特征把原始字段转换为关系信号。",
  "Native-Web：18个；Native-WebView：8个；WebView-Web：5个；Tri-layer semantic：7个。",
  "",
  "分组验证下，7个Tri-layer semantic特征的MAE为2.281，优于65维Raw all的2.642；RMSE为3.358，也优于Raw all的4.455。"
].join("\n"), { fontSize: 22 });
setPosition(elementById(slides[18], "22"), [130, 260, 850, 260]);
deleteElements(slides[18], ["23", "25", "26"]);
await addImage(slides[18], images.grouped, [990, 275, 820, 610]);

setText(slides[19], "8", "实验分析：特征重要性与风险解释", { fontSize: 32, bold: true });
setText(slides[19], "22", [
  "高权重特征主要集中在跨层失败信号和宿主真实性信号上。",
  "传感器、JSBridge、UA、安装来源和ADB等关系特征可以回溯到规则知识库中的具体一致性判断。"
].join("\n"), { fontSize: 22 });
setPosition(elementById(slides[19], "22"), [130, 260, 850, 210]);
setTable(slides[19], "25", [
  ["解释方向", "含义", "示例"],
  ["跨层失败", "环境不一致", "UA/屏幕"],
  ["宿主真实性", "容器匹配", "JSBridge"]
], 13);
setTable(slides[19], "26", [
  ["风险来源", "代表信号", "层级", "解释", "用途"],
  ["Native", "传感器/ADB", "底层", "物理环境", "安全"],
  ["WebView", "JSBridge", "宿主", "容器真实性", "对齐"],
  ["Web", "UA/WebGL", "前端", "暴露不一致", "识别"],
  ["Tri-layer", "failure count", "三端", "关系失败", "评分"],
  ["", "", "", "", ""]
], 12);
await replaceImage(slides[19], "23", images.importance, [910, 300, 920, 360]);

setText(slides[20], "8", "实验分析：不足与展望", { fontSize: 32, bold: true });
setText(slides[20], "22", [
  "当前结论成立在原型数据和离线消融边界内。",
  "后续工作重点是扩大真实设备覆盖、补充人工复核标签，并增加端侧运行开销测试。"
].join("\n"), { fontSize: 22 });
setPosition(elementById(slides[20], "22"), [130, 260, 850, 210]);
setTable(slides[20], "24", [
  ["方向", "当前不足", "后续改进"],
  ["数据覆盖", "真实设备仍不足", "扩大品牌和系统"],
  ["标签质量", "LLM标签需复核", "加入抽样审核"]
], 13);
setTable(slides[20], "25", [
  ["方向", "当前不足", "改进方式"],
  ["端侧性能", "开销未系统量化", "补充耗时/内存"],
  ["真实业务", "原型边界明显", "接入更多场景"],
  ["保守结论", "不能替代大规模验证", "作为RBA补充信号"],
  ["应用价值", "可解释关系信号", "辅助风控判断"],
  ["", "", ""],
  ["", "", ""],
  ["", "", ""],
  ["", "", ""]
], 15);

// 22-23. 结论与致谢
setText(slides[21], "8", "结论", { fontSize: 36, bold: true });
setText(slides[21], "4", [
  "本文完成了一套面向移动端RBA的多端关联设备身份交叉验证机制。",
  "",
  "采集：Android Native、WebView宿主、Web前端三端分层指纹采集",
  "对齐：session_id合并异步上报，保留原始数据和训练数据",
  "规则化：规则知识库约束离线标注，形成可解释风险标签",
  "端侧化：随机森林Java推理，App本地输出风险分和解释摘要",
  "验证：分组交叉验证中，三端语义规则特征优于65维原始字段基线",
  "",
  "核心结论：三端融合的价值不是简单增加字段，而是构建可对齐、可互证、可解释的跨层关系。"
].join("\n"), { fontSize: 25 });

setText(slides[22], "14", "2026年6月", { fontSize: 22, alignment: "center" });
setText(slides[22], "15", "请批评指正！", { fontSize: 58, bold: true, alignment: "center" });

await renderFinal(presentation, slides);

await fs.mkdir(outputDir, { recursive: true });
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(finalPptxPath);
await fs.copyFile(finalPptxPath, deliveryPptxPath);

console.log(JSON.stringify({ finalPptxPath, deliveryPptxPath, slideCount: slides.length }, null, 2));
