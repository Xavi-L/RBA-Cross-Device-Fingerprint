import fs from "node:fs/promises";
import path from "node:path";

import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspace = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/outputs/019e88df-d9ac-79f3-8168-fb1d9041f45f/presentations/hybridguard-defense";
const repo = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint";
const starterPptxPath = path.join(workspace, "template-starter.pptx");
const finalPptxPath = path.join(repo, "presentaion", "HybridGuard毕业论文答辩_模板版.pptx");
const finalPreviewDir = path.join(workspace, "preview", "final");
const finalLayoutDir = path.join(workspace, "layout", "final");

const BLUE = "#1f5fae";
const DARK = "#111827";
const MUTED = "#4b5563";
const RED = "#d71920";
const TEAL = "#008c8c";
const TRANSPARENT = "#00000000";
const TITLE_FONT = "PingFang SC";
const BODY_FONT = "PingFang SC";

const assets = {
  architecture: path.join(repo, "thesis_materials/top_journal_figures/fig2-1_system_architecture.png"),
  offlineFlow: path.join(repo, "thesis_materials/top_journal_figures/fig2-2_offline_label_training_flow.png"),
  onDeviceFlow: path.join(repo, "thesis_materials/top_journal_figures/fig2-3_on_device_scoring_flow.png"),
  consistency: path.join(repo, "thesis_materials/top_journal_figures/fig2-4_cross_layer_consistency_analysis.png"),
  module: path.join(repo, "thesis_materials/top_journal_figures/fig3-1_on_device_module_structure.png"),
  sourceDist: path.join(repo, "ablation/figures/figure_01_source_distribution.png"),
  holdoutGrouped: path.join(repo, "ablation/figures/figure_03_holdout_vs_grouped_mae.png"),
  groupedMain: path.join(repo, "ablation/figures/figure_04_grouped_main_results.png"),
  featureImportance: path.join(repo, "ablation/figures/figure_05_consistency_feature_importance.png"),
};

function slide(n, presentation) {
  return presentation.slides.getItem(n - 1);
}

function snap(element) {
  return element.toSnapshot?.() || {};
}

function findByAid(slideObj, aid) {
  return slideObj.elements.items.find((element) => snap(element).aid === aid);
}

function isTitleElement(element) {
  const s = snap(element);
  const f = s.frame || {};
  return s.name === "标题 1" || (s.kind === "shape" && f.top < 170 && f.left < 1200 && String(s.text || "").trim());
}

function isHeaderChrome(element) {
  const s = snap(element);
  const f = s.frame || {};
  if (!f) return false;
  if (f.top < 170 && s.kind === "image") return true;
  if (f.top <= 190 && f.height <= 12 && f.width > 1000) return true;
  return false;
}

function clearBody(slideObj) {
  const items = [...slideObj.elements.items].reverse();
  for (const element of items) {
    if (isTitleElement(element) || isHeaderChrome(element)) continue;
    const s = snap(element);
    const f = s.frame || {};
    if (!f.top && f.top !== 0) continue;
    if (f.top > 190) {
      if (typeof element.delete === "function") {
        element.delete();
      } else {
        const ids = [s.aid, s.id, element.id].filter(Boolean);
        for (const collection of [slideObj.elements, slideObj.shapes, slideObj.images, slideObj.tables]) {
          if (typeof collection?.deleteById !== "function") continue;
          for (const id of ids) {
            try {
              collection.deleteById(id);
            } catch {
              // Some imported elements expose both an aid and an OOXML id; try all known ids.
            }
          }
        }
      }
    }
  }
}

function setText(element, text, options = {}) {
  if (!element) return;
  element.text = text;
  const target = element.text;
  target.fontSize = options.fontSize ?? 30;
  target.color = options.color ?? DARK;
  target.typeface = options.typeface ?? BODY_FONT;
  target.bold = Boolean(options.bold);
  target.alignment = options.align ?? "left";
  target.verticalAlignment = options.valign ?? "top";
  target.insets = options.insets ?? { left: 0, right: 0, top: 0, bottom: 0 };
}

function title(slideObj, text) {
  const titleShape = slideObj.elements.items.find((element) => snap(element).name === "标题 1");
  setText(titleShape, text, { fontSize: 54, color: BLUE, bold: true, typeface: TITLE_FONT });
}

function addShape(slideObj, frame, options = {}) {
  const shape = slideObj.shapes.add({
    geometry: "rect",
    position: frame,
    fill: options.fill ?? TRANSPARENT,
    line: options.line ?? { style: "solid", fill: TRANSPARENT, width: 0 },
  });
  return shape;
}

function addText(slideObj, text, frame, options = {}) {
  const shape = addShape(slideObj, frame, options);
  shape.text = text;
  shape.text.fontSize = options.fontSize ?? 28;
  shape.text.color = options.color ?? DARK;
  shape.text.bold = Boolean(options.bold);
  shape.text.typeface = options.typeface ?? BODY_FONT;
  shape.text.alignment = options.align ?? "left";
  shape.text.verticalAlignment = options.valign ?? "top";
  shape.text.insets = options.insets ?? { left: 8, right: 8, top: 6, bottom: 6 };
  return shape;
}

async function imageBlob(imagePath) {
  const bytes = await fs.readFile(imagePath);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

async function addImage(slideObj, imagePath, frame, alt, fit = "contain") {
  const image = slideObj.images.add({ blob: await imageBlob(imagePath), fit, alt });
  image.position = frame;
  return image;
}

async function replaceImage(slideObj, aid, imagePath, frame, alt, fit = "contain") {
  const image = findByAid(slideObj, aid);
  if (!image) return addImage(slideObj, imagePath, frame, alt, fit);
  await image.replace({ blob: await imageBlob(imagePath), fit, alt });
  image.position = frame;
  return image;
}

function addKeyLine(slideObj, text, frame, color = BLUE) {
  addText(slideObj, text, frame, { fontSize: 32, color, bold: true });
}

function addSmall(slideObj, text, frame, color = MUTED) {
  addText(slideObj, text, frame, { fontSize: 22, color });
}

function addColumn(slideObj, heading, body, frame, color = BLUE) {
  addText(slideObj, heading, { left: frame.left, top: frame.top, width: frame.width, height: 58 }, {
    fontSize: 30,
    color,
    bold: true,
  });
  addText(slideObj, body, { left: frame.left, top: frame.top + 70, width: frame.width, height: frame.height - 70 }, {
    fontSize: 25,
    color: DARK,
  });
}

function addMetric(slideObj, value, label, frame, color = BLUE) {
  addText(slideObj, value, { left: frame.left, top: frame.top, width: frame.width, height: 58 }, {
    fontSize: 34,
    color,
    bold: true,
    align: "center",
  });
  addText(slideObj, label, { left: frame.left, top: frame.top + 54, width: frame.width, height: 78 }, {
    fontSize: 20,
    color: MUTED,
    align: "center",
  });
}

async function renderFinal(presentation) {
  await fs.mkdir(finalPreviewDir, { recursive: true });
  await fs.mkdir(finalLayoutDir, { recursive: true });
  for (let index = 0; index < presentation.slides.count; index += 1) {
    const current = presentation.slides.getItem(index);
    const padded = String(index + 1).padStart(2, "0");
    const preview = await presentation.export({ slide: current, format: "png", scale: 1 });
    await fs.writeFile(path.join(finalPreviewDir, `slide-${padded}.png`), Buffer.from(await preview.arrayBuffer()));
    const layout = await presentation.export({ slide: current, format: "layout" });
    await fs.writeFile(path.join(finalLayoutDir, `slide-${padded}.layout.json`), await layout.text(), "utf8");
  }
}

const presentation = await PresentationFile.importPptx(await FileBlob.load(starterPptxPath));

setText(findByAid(slide(1, presentation), "sh/cvixczed"), "RBA中基于Web-WebView-Android\n多端关联的设备身份交叉验证机制研究", {
  fontSize: 45,
  color: BLUE,
  bold: true,
  align: "center",
  typeface: TITLE_FONT,
});
setText(findByAid(slide(1, presentation), "sh/udg7adsj"), "梁骁\n指导老师：李巍\n2026年6月", {
  fontSize: 24,
  color: DARK,
  align: "center",
});

clearBody(slide(4, presentation));
title(slide(4, presentation), "绪论：研究背景");
addKeyLine(slide(4, presentation), "移动端RBA需要识别跨层设备身份异常", { left: 110, top: 265, width: 780, height: 60 });
addText(slide(4, presentation), "Android Native、WebView宿主和Web前端分别暴露不同身份线索。\n\n单端字段可能被伪造、重放或遮蔽；同一会话内的跨层关系更能反映设备环境是否可信。\n\n本文关注：同一次访问是否来自同一可信移动设备环境。", { left: 110, top: 345, width: 800, height: 520 }, { fontSize: 30 });
await addImage(slide(4, presentation), assets.consistency, { left: 990, top: 300, width: 760, height: 560 }, "跨层一致性分析流程");

clearBody(slide(5, presentation));
title(slide(5, presentation), "绪论：研究现状");
addColumn(slide(5, presentation), "单字段设备指纹", "依赖UA、屏幕、Canvas、WebGL等字段，容易受到局部伪造与代理字段影响。", { left: 120, top: 270, width: 470, height: 470 }, BLUE);
addColumn(slide(5, presentation), "移动端WebView割裂", "Native、宿主容器与Web脚本处在不同层级，数据上报存在时序差异。", { left: 735, top: 270, width: 470, height: 470 }, TEAL);
addColumn(slide(5, presentation), "端侧风控约束", "完整原始指纹外传成本高，答辩口径应强调摘要评分与可解释风险原因。", { left: 1350, top: 270, width: 470, height: 470 }, RED);
addText(slide(5, presentation), "本文的切入点不是提出新的机器学习算法，而是打通三端采集、会话对齐、规则知识库和端侧轻量评分闭环。", { left: 170, top: 815, width: 1580, height: 110 }, { fontSize: 30, color: DARK, align: "center" });

clearBody(slide(6, presentation));
title(slide(6, presentation), "绪论：研究目标");
addText(slide(6, presentation), "本毕业设计面向RBA移动端风控场景，设计并实现一种多端关联设备身份交叉验证机制。\n\n1. 建立 Android Native、WebView宿主、Web前端三端分层采集方案。\n2. 通过 session_id 完成异步上报数据的会话对齐与持久化。\n3. 构建跨层语义规则知识库，用于离线标签生产与风险解释。\n4. 将规则语义压缩为端侧轻量随机森林评分器，实现本地采集、本地推理和摘要上报。", {
  left: 130,
  top: 285,
  width: 1650,
  height: 620,
}, { fontSize: 35 });

clearBody(slide(8, presentation));
title(slide(8, presentation), "相关技术介绍：RBA与设备指纹");
addText(slide(8, presentation), "基于风险的认证根据访问环境动态调整认证强度。\n\n移动端设备身份不只由单个字段决定，而是由底层设备、App宿主和网页运行时共同构成。", { left: 110, top: 240, width: 620, height: 320 }, { fontSize: 30 });
await addImage(slide(8, presentation), assets.consistency, { left: 760, top: 245, width: 1040, height: 700 }, "跨层一致性特征构造");
addSmall(slide(8, presentation), "核心思想：从字段值转向字段关系，用跨层互证和矛盾发现支撑风险判断。", { left: 110, top: 675, width: 620, height: 120 }, RED);

title(slide(9, presentation), "相关技术介绍：端侧轻量评分");
setText(findByAid(slide(9, presentation), "sh/dg7adsji"), "离线阶段：规则知识库约束大模型标注，生成 risk_score 与 risk_reason。\n\n训练阶段：使用65维三端原始特征与一致性特征进行随机森林消融评估。\n\n部署阶段：通过 m2cgen 将随机森林导出为 Java，在 Android 端完成0-100风险分推理。\n\n工程取舍：随机森林不是算法创新点，但在小样本结构化数据、端侧部署成本和解释性上更适合本系统。", {
  fontSize: 32,
  color: DARK,
});

clearBody(slide(11, presentation));
title(slide(11, presentation), "系统设计与总体架构");
await replaceImage(slide(11, presentation), "im/knih4byh", assets.architecture, { left: 110, top: 245, width: 1700, height: 790 }, "HybridGuard系统总体架构");

clearBody(slide(13, presentation));
title(slide(13, presentation), "关键模块设计与实现：三端采集与会话对齐");
addColumn(slide(13, presentation), "Android Native", "设备型号、系统版本、物理屏幕、电池、传感器、ADB状态等底层信息。\n\n33个字段", { left: 120, top: 250, width: 460, height: 440 }, BLUE);
addColumn(slide(13, presentation), "WebView宿主", "JSBridge、Provider、系统UA、安装来源、debuggable等宿主真实性信号。\n\n14个字段", { left: 720, top: 250, width: 460, height: 440 }, TEAL);
addColumn(slide(13, presentation), "Web前端", "Navigator、DPR、WebGL、Canvas、时区和算力表现等脚本可见环境。\n\n18个字段", { left: 1320, top: 250, width: 460, height: 440 }, RED);
addText(slide(13, presentation), "三端异步上报后由 FastAPI 按 session_id 增量合并，保留原始 JSON，同时展开为训练 JSONL。", { left: 160, top: 810, width: 1580, height: 110 }, { fontSize: 30, align: "center" });

clearBody(slide(14, presentation));
title(slide(14, presentation), "关键模块设计与实现：跨层规则知识库");
addText(slide(14, presentation), "规则知识库把孤立字段异常转化为可解释的关系判断：", { left: 120, top: 240, width: 900, height: 60 }, { fontSize: 30, bold: true, color: BLUE });
addText(slide(14, presentation), "屏幕一致性：Native物理屏幕与Web逻辑屏幕×DPR应近似对应\nUA一致性：Build信息、WebView UA、Web UA应相互呼应\n宿主真实性：Web页面应能通过JSBridge获取同一会话\n物理可信性：传感器、电池、ADB与安装来源共同解释环境风险\n渲染环境：WebGL、GPU族、Headless/SwiftShader反映运行环境", { left: 130, top: 335, width: 900, height: 500 }, { fontSize: 28 });
addText(slide(14, presentation), "作用一\n约束离线标注边界", { left: 1180, top: 310, width: 420, height: 110 }, { fontSize: 30, color: BLUE, bold: true, align: "center" });
addText(slide(14, presentation), "作用二\n生成一致性特征", { left: 1180, top: 500, width: 420, height: 110 }, { fontSize: 30, color: TEAL, bold: true, align: "center" });
addText(slide(14, presentation), "作用三\n支撑风险原因解释", { left: 1180, top: 690, width: 420, height: 110 }, { fontSize: 30, color: RED, bold: true, align: "center" });

clearBody(slide(15, presentation));
title(slide(15, presentation), "关键模块设计与实现：离线标注训练流程");
addText(slide(15, presentation), "大模型只参与离线标签生产，端侧运行时不依赖大模型服务。\n\n规则知识库将屏幕、UA、JSBridge、传感器和WebGL等关系注入提示词，输出结构化 risk_score 与 risk_reason。", { left: 90, top: 255, width: 520, height: 500 }, { fontSize: 28 });
await addImage(slide(15, presentation), assets.offlineFlow, { left: 650, top: 240, width: 1200, height: 730 }, "离线标注训练流程");

clearBody(slide(16, presentation));
title(slide(16, presentation), "关键模块设计与实现：端侧评分闭环");
addText(slide(16, presentation), "运行时在App内完成：\n\n1. 三端本地采集\n2. 65维特征编码\n3. 随机森林Java推理\n4. 风险分、等级和摘要上报\n\n原始三端指纹不出端，降低传输与合规压力。", { left: 110, top: 245, width: 560, height: 650 }, { fontSize: 29 });
await addImage(slide(16, presentation), assets.onDeviceFlow, { left: 725, top: 250, width: 1080, height: 720 }, "端侧评分运行流程");

clearBody(slide(17, presentation));
title(slide(17, presentation), "关键模块设计与实现：65维特征约束");
addText(slide(17, presentation), "RiskFeatureEncoder 固化训练侧字段顺序、类别编码、布尔转换和缺失值策略。\n\nDeviceRiskScorer 由 m2cgen 导出的随机森林 Java 代码实现。\n\n关键约束：训练阶段看到的特征语义与端侧输入数组必须一致。", { left: 110, top: 245, width: 620, height: 610 }, { fontSize: 29 });
await addImage(slide(17, presentation), assets.module, { left: 760, top: 255, width: 1040, height: 700 }, "端侧评分模块结构");

clearBody(slide(18, presentation));
title(slide(18, presentation), "关键模块设计与实现：一致性特征解释");
addText(slide(18, presentation), "38个 consistency_* 特征分为四组：\n\nNative-Web：18个\nNative-WebView：8个\nWebView-Web：5个\nTri-layer semantic：7个\n\n特征重要性显示，模型主要依赖传感器与桥接完整性、debug/cleartext张力、Native型号与Web UA匹配等跨层语义信号。", { left: 110, top: 245, width: 610, height: 690 }, { fontSize: 27 });
await addImage(slide(18, presentation), assets.featureImportance, { left: 760, top: 250, width: 1060, height: 720 }, "一致性特征重要性");

clearBody(slide(20, presentation));
title(slide(20, presentation), "实验分析：数据来源与分组验证");
addMetric(slide(20, presentation), "1323", "带风险标签样本", { left: 110, top: 255, width: 230, height: 140 }, BLUE);
addMetric(slide(20, presentation), "286 / 737 / 300", "真实设备 / 云测设备 / 脚本攻击", { left: 380, top: 255, width: 430, height: 140 }, TEAL);
addMetric(slide(20, presentation), "3折", "按 group_id 分组交叉验证", { left: 850, top: 255, width: 250, height: 140 }, RED);
addText(slide(20, presentation), "为什么不用随机切分作为主结论：同一设备扩充样本、同一云测环境或同一攻击模板可能同时进入训练集与测试集，导致泛化指标偏乐观。", { left: 110, top: 450, width: 620, height: 270 }, { fontSize: 28 });
await addImage(slide(20, presentation), assets.sourceDist, { left: 800, top: 420, width: 980, height: 570 }, "数据来源构成");

clearBody(slide(21, presentation));
title(slide(21, presentation), "实验分析：随机留出与分组验证对比");
addText(slide(21, presentation), "随机holdout指标整体较低，但不能排除同源样本记忆。\n\n分组后部分配置误差明显上升，尤其是仅Web配置；因此本文以分组交叉验证作为更严格的主实验口径。", { left: 90, top: 255, width: 580, height: 360 }, { fontSize: 29 });
addText(slide(21, presentation), "典型变化：\n仅Web：1.416 → 12.188\n仅一致性：1.103 → 3.388\n三端语义：1.111 → 2.281", { left: 100, top: 650, width: 550, height: 210 }, { fontSize: 28, color: RED });
await addImage(slide(21, presentation), assets.holdoutGrouped, { left: 690, top: 235, width: 1180, height: 760 }, "随机留出与分组交叉验证MAE对比");

clearBody(slide(22, presentation));
title(slide(22, presentation), "实验分析：分组一致性消融主结果");
addText(slide(22, presentation), "核心结论：三端融合的价值不只是采集更多字段，而是形成可对齐、可互证、可发现矛盾的语义关系。", { left: 95, top: 230, width: 650, height: 145 }, { fontSize: 29, color: DARK });
addMetric(slide(22, presentation), "2.281", "Tri-layer semantic MAE\n7个三端语义特征", { left: 105, top: 430, width: 270, height: 160 }, RED);
addMetric(slide(22, presentation), "2.642", "Raw all MAE\n65维原始三端特征", { left: 410, top: 430, width: 270, height: 160 }, BLUE);
addMetric(slide(22, presentation), "2.608", "Native-WebView consistency MAE\n8个宿主真实性特征", { left: 245, top: 650, width: 330, height: 170 }, TEAL);
await addImage(slide(22, presentation), assets.groupedMain, { left: 760, top: 235, width: 1070, height: 760 }, "分组版一致性消融主结果");

title(slide(23, presentation), "结论");
clearBody(slide(23, presentation));
title(slide(23, presentation), "结论");
addText(slide(23, presentation), "本文完成了面向RBA移动端场景的多端关联设备身份交叉验证原型系统。\n\n1. 采集：实现 Android Native、WebView宿主、Web前端三端指纹采集。\n2. 对齐：以 session_id 合并异步上报数据，形成可训练样本。\n3. 规则化：构建跨层语义规则知识库，约束离线标签并支撑解释。\n4. 端侧化：将随机森林导出到 Android 端，实现本地评分与摘要上报。\n\n实验表明，在更严格的分组交叉验证下，少量三端语义一致性特征优于完整原始三端特征，说明跨层一致性建模具备实际价值。", {
  left: 130,
  top: 235,
  width: 1680,
  height: 760,
}, { fontSize: 30 });

setText(findByAid(slide(24, presentation), "sh/p0bi9s36"), "2026年6月", {
  fontSize: 24,
  color: "#ffffff",
  align: "center",
});
setText(findByAid(slide(24, presentation), "sh/0fepkzup"), "请批评指正！", {
  fontSize: 58,
  color: BLUE,
  bold: true,
  align: "center",
  typeface: TITLE_FONT,
});

await renderFinal(presentation);
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(finalPptxPath);
console.log(JSON.stringify({ finalPptxPath, finalPreviewDir, finalLayoutDir, slideCount: presentation.slides.count }, null, 2));
