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

const workspace = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/outputs/manual-20260602-rba-ppt-template/presentations/rba-defense-template-migration";
const repo = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint";
const starterPptxPath = path.join(workspace, "template-starter.pptx");
const outputDir = path.join(workspace, "output");
const previewDir = path.join(workspace, "preview", "final");
const layoutDir = path.join(workspace, "layout", "final");
const finalPptxPath = path.join(outputDir, "RBA多端关联设备身份交叉验证机制答辩_模板迁移版.pptx");
const deliveryPptxPath = path.join(repo, "presentaion", "RBA多端关联设备身份交叉验证机制答辩_模板迁移版.pptx");

const images = {
  architecture: path.join(repo, "thesis_materials/top_journal_figures/fig2-1_system_architecture.png"),
  scoring: path.join(repo, "thesis_materials/top_journal_figures/fig3-1_on_device_module_structure.png"),
  data: path.join(repo, "ablation/figures/figure_01_source_distribution.png"),
  grouped: path.join(repo, "ablation/figures/figure_04_grouped_main_results.png"),
  importance: path.join(repo, "ablation/figures/figure_05_consistency_feature_importance.png"),
  introTitle: path.join(workspace, "assets/xulun-title.png")
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
    if (element) element.delete();
  }
}

function setTable(slide, id, values, fontSize = 18) {
  const table = elementById(slide, id);
  if (!table) throw new Error(`Missing table ${id} on slide ${slide.index + 1}`);
  table.setValues(values);
  try {
    for (let row = 0; row < table.rowCount; row += 1) {
      for (let col = 0; col < table.columnCount; col += 1) {
        const cell = table.getCell(row, col);
        if (cell?.text) cell.text.fontSize = fontSize;
      }
    }
  } catch {
    // Table value update is more important than style-level cell access.
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

// 3. Intro divider
setText(slides[2], "18", "绪论", { fontSize: 60, bold: true, alignment: "center" });
await addImage(slides[2], images.introTitle, [760, 450, 460, 190], "contain");

// 4. Compressed introduction
setText(slides[3], "8", "绪论：研究背景、意义与研究内容", { fontSize: 34, bold: true });
setText(slides[3], "3", [
  "移动端RBA场景",
  "登录、交易等关键环节需要判断访问环境是否可信",
  "Hybrid App一次会话同时经过Android Native、WebView宿主和Web前端",
  "局部字段可能被伪造、重放或遮蔽，单端指纹难以判断同一设备身份",
  "",
  "核心问题",
  "同一会话中的多端证据是否相互一致，能否暴露伪造、重放和容器绕过风险"
].join("\n"), { fontSize: 24 });
setText(slides[3], "4", [
  "研究目标",
  "围绕“同一会话是否来自同一可信设备环境”，完成三端关联验证机制",
  "",
  "研究内容",
  "三端指纹采集与session_id会话对齐",
  "跨层语义规则知识库与离线标签",
  "Android端侧轻量评分闭环",
  "消融实验与分组验证"
].join("\n"), { fontSize: 24 });
deleteElements(slides[3], ["19", "20", "14", "15", "16"]);

// 5-6. Related technology
setText(slides[4], "18", "相关技术介绍", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[5], "8", "相关技术介绍：国内外研究现状", { fontSize: 34, bold: true });
setText(slides[5], "22", [
  "Hybrid App与WebView安全研究",
  "Android-Web混合应用广泛使用WebView和JSBridge。已有研究主要关注WebView配置、JavaScript interface、native bridge暴露和跨语言信息流等安全问题。"
].join("\n"), { fontSize: 24 });
setText(slides[5], "13", [
  "已有研究关注点",
  "WebViewClient与本地内容加载的边界安全",
  "Java/JavaScript交互导致的信息流和权限边界",
  "不安全JSBridge可能暴露原生能力"
].join("\n"), { fontSize: 21 });
setText(slides[5], "15", [
  "本文承接与差异",
  "不把WebView只当漏洞入口，而作为独立指纹层",
  "采集provider、默认UA、JSBridge、安装来源、debuggable等宿主证据",
  "与Native和Web前端形成同一会话内的跨层一致性校验"
].join("\n"), { fontSize: 21 });
deleteElements(slides[5], ["26", "27"]);

// 7-8. System design
setText(slides[6], "18", "系统设计与总体架构", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[7], "8", "系统设计与总体架构：离线提炼规则，端侧完成评分", { fontSize: 32, bold: true });
await replaceImage(slides[7], "12", images.architecture, [115, 250, 1700, 760]);

// 9-12. Key modules
setText(slides[8], "18", "关键模块设计与实现", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[9], "8", "关键模块设计与实现：三端采集与会话对齐", { fontSize: 32, bold: true });
setText(slides[9], "5", [
  "三端采集",
  "Android Native：33个字段，覆盖型号、系统、屏幕、电池、传感器、ADB",
  "WebView宿主：14个字段，覆盖JSBridge、provider、安装来源、debuggable",
  "Web前端：18个字段，覆盖UA、DPR、WebGL、Canvas、时区、算力"
].join("\n"), { fontSize: 21 });
setText(slides[9], "6", [
  "会话对齐",
  "三端数据异步到达，后端以session_id作为会话键",
  "FastAPI接口接收并增量合并非空字段",
  "保留原始嵌套JSON用于审计，展开JSONL用于标注、训练和消融实验"
].join("\n"), { fontSize: 21 });
setTable(slides[9], "16", [
  ["特征层", "字段数", "代表字段", "风控意义"],
  ["Native", "33", "型号、系统、屏幕、电池、传感器、ADB", "底层设备真实性"],
  ["WebView", "14", "JSBridge、Provider、安装来源、debuggable", "宿主容器可信性"],
  ["Web", "18", "UA、DPR、WebGL、Canvas、时区", "前端运行环境"]
], 16);

setText(slides[10], "8", "关键模块设计与实现：规则知识库与离线标注", { fontSize: 32, bold: true });
setText(slides[10], "4", [
  "规则知识库",
  "将屏幕、UA、JSBridge、传感器和WebGL等关系提炼为跨层一致性规则",
  "作用一：给离线标签生产提供统一判断边界",
  "作用二：让模型风险分能够回溯到具体异常关系"
].join("\n"), { fontSize: 22 });
setTable(slides[10], "15", [
  ["规则类别", "风险含义"],
  ["屏幕一致性", "Native物理屏幕与Web逻辑屏幕×DPR应近似对应"],
  ["UA一致性", "Native Build、WebView UA与Web UA应相互呼应"],
  ["宿主真实性", "Web页面应能通过JSBridge获取同一session_id"]
], 16);
setTable(slides[10], "16", [
  ["离线链路", "输入", "输出"],
  ["规则约束", "三端样本 + 规则知识库", "结构化风险判断边界"],
  ["标签生产", "本地LLM离线分析", "risk_score / risk_reason"],
  ["模型训练", "带标签JSONL", "端侧轻量评分器"]
], 16);
setText(slides[10], "12", "规则类别示例", { fontSize: 18, bold: true, alignment: "center" });
setText(slides[10], "13", "离线标注训练链路", { fontSize: 18, bold: true, alignment: "center" });

setText(slides[11], "8", "关键模块设计与实现：端侧评分闭环", { fontSize: 32, bold: true });
setText(slides[11], "22", [
  "端侧闭环",
  "Native、WebView与Web探针在App内形成同一会话输入",
  "RiskFeatureEncoder固化训练阶段65维字段顺序、类别映射和缺失值策略",
  "DeviceRiskScorer由m2cgen导出的随机森林Java代码实现",
  "运行时仅上传风险分、风险等级和解释摘要，减少原始三端指纹外传"
].join("\n"), { fontSize: 23 });
await replaceImage(slides[11], "24", images.scoring, [1500, 235, 360, 610]);

// 13-18. Experiments
setText(slides[12], "18", "实验分析", { fontSize: 60, bold: true, alignment: "center" });
setText(slides[13], "8", "实验分析：数据来源与分组验证设计", { fontSize: 32, bold: true });
setText(slides[13], "22", [
  "实验数据",
  "1323条带风险标签样本，来源包括真实设备、云测环境和脚本攻击模板",
  "三类来源规模为286 / 737 / 300",
  "",
  "验证策略",
  "使用分组交叉验证控制同源设备和攻击模板泄漏，使测试更接近未见设备与未见模板场景",
  "后续主结论以Grouped结果为准"
].join("\n"), { fontSize: 23 });
deleteElements(slides[13], ["24", "25", "26", "27", "28", "17", "18", "19", "20"]);
await addImage(slides[13], images.data, [1120, 265, 690, 610]);

setText(slides[14], "8", "实验分析：评分器选型", { fontSize: 32, bold: true });
setText(slides[14], "22", [
  "目标是在端侧部署约束下承接离线规则语义。",
  "随机森林更适合当前小样本结构化特征，并可直接导出Java推理代码。"
].join("\n"), { fontSize: 23 });
setTable(slides[14], "24", [
  ["模型", "样本数", "MAE", "中位误差", "P90误差", "最大误差"],
  ["随机森林", "265", "1.14", "1.11", "2.25", "6.42"],
  ["浅层MLP", "265", "2.42", "2.04", "5.23", "13.29"]
], 16);
setTable(slides[14], "25", [
  ["选择随机森林的原因", "说明"],
  ["部署直接", "m2cgen导出Java，便于接入Android端"],
  ["结构化数据稳定", "小样本、多类别/布尔字段下表现更稳"],
  ["解释性较好", "可用特征重要性反查风险来源"]
], 16);

setText(slides[15], "8", "实验分析：三端原始特征消融", { fontSize: 32, bold: true });
setText(slides[15], "22", [
  "先按Native、WebView、Web三端粗粒度删减，观察不同证据源对评分结果的影响。",
  "结果说明：三端原始字段之间存在代理关系，简单拼接全部字段并不一定最稳。"
].join("\n"), { fontSize: 22 });
setTable(slides[15], "25", [
  ["配置", "特征数", "Holdout MAE", "Grouped MAE", "解释"],
  ["WebView only", "14", "1.139", "1.541", "宿主强规则信号明显"],
  ["Native + WebView", "47", "1.129", "2.202", "底层设备+宿主覆盖大量标签逻辑"],
  ["Native + WebView + Web", "65", "1.140", "2.642", "完整基线但含冗余与噪声"],
  ["Web only", "18", "1.416", "12.188", "未见设备/模板下最不稳定"]
], 15);
setTable(slides[15], "26", [
  ["结论", "三端融合价值不只是字段更多，而是把冗余字段转化为可互证、可发现矛盾的关系特征。"]
], 17);

setText(slides[16], "8", "实验分析：一致性特征与分组主结果", { fontSize: 32, bold: true });
setText(slides[16], "22", [
  "一致性特征把原始字段转换为关系信号。",
  "Native-Web：18个；Native-WebView：8个；WebView-Web：5个；Tri-layer semantic：7个。",
  "",
  "分组验证下，7个Tri-layer semantic特征的MAE为2.281，优于65维Raw all的2.642；RMSE为3.358，也优于Raw all的4.455。"
].join("\n"), { fontSize: 23 });
deleteElements(slides[16], ["24", "25", "26", "27", "28", "17", "18", "19", "20"]);
await addImage(slides[16], images.grouped, [990, 245, 835, 650]);

setText(slides[17], "8", "实验分析：特征重要性与不足展望", { fontSize: 32, bold: true });
setText(slides[17], "22", [
  "高权重特征主要集中在跨层失败信号和宿主真实性信号上。",
  "传感器、JSBridge、UA、安装来源和ADB等关系特征可以回溯到规则知识库中的具体一致性判断。"
].join("\n"), { fontSize: 22 });
setTable(slides[17], "24", [
  ["解释方向", "含义"],
  ["跨层失败信号", "前端、宿主和Native环境之间出现不一致"],
  ["宿主真实性", "WebView容器与Native环境的匹配关系是主要判别依据"],
  ["规则可回溯", "风险分可以关联到具体失败关系"]
], 15);
setTable(slides[17], "25", [
  ["不足与展望", "后续改进"],
  ["真实设备覆盖有限", "扩大品牌、系统、WebView内核和网络环境"],
  ["LLM标签需复核", "加入抽样审核、规则版本和冲突处理"],
  ["端侧开销测试不足", "补充采集耗时、推理耗时、内存和稳定性"]
], 15);
await addImage(slides[17], images.importance, [1010, 310, 780, 315]);

// 19. Conclusion
setText(slides[18], "8", "结论", { fontSize: 36, bold: true });
setText(slides[18], "4", [
  "本文完成了一套面向移动端RBA的多端关联设备身份交叉验证机制。",
  "",
  "采集：Android Native、WebView宿主、Web前端三端分层指纹采集",
  "对齐：session_id合并异步上报，保留原始数据和训练数据",
  "规则化：规则知识库约束离线标注，形成可解释风险标签",
  "端侧化：随机森林Java推理，App本地输出风险分和摘要",
  "",
  "谢谢各位老师，欢迎批评指正。"
].join("\n"), { fontSize: 27 });

await renderFinal(presentation, slides);

await fs.mkdir(outputDir, { recursive: true });
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(finalPptxPath);
await fs.copyFile(finalPptxPath, deliveryPptxPath);

console.log(JSON.stringify({ finalPptxPath, deliveryPptxPath, slideCount: slides.length }, null, 2));
