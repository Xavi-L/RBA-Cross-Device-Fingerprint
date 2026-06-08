import fs from "node:fs/promises";
import path from "node:path";

import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspace = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint/outputs/019e88df-d9ac-79f3-8168-fb1d9041f45f/presentations/hybridguard-defense";
const repo = "/Users/xavier/毕业设计/RBA-Cross-Device-Fingerprint";
const starterPptxPath = path.join(workspace, "template-starter.pptx");
const finalPptxPath = path.join(repo, "presentaion", "HybridGuard毕业论文答辩_旧版迁移模板版.pptx");
const finalPreviewDir = path.join(workspace, "preview", "old-migration");
const finalLayoutDir = path.join(workspace, "layout", "old-migration");
const cropDir = path.join(workspace, "assets", "old-body-crops");

const BLUE = "#1f5fae";
const DARK = "#111827";
const TITLE_FONT = "PingFang SC";
const BODY_FONT = "PingFang SC";
const TRANSPARENT = "#00000000";

const bodyFrame = { left: 135, top: 238, width: 1650, height: 727 };

const slideMap = {
  4: { old: "02", title: "研究背景：RBA移动应用需要识别跨层设备身份异常" },
  5: { old: "03", title: "研究意义与目的：让移动端RBA具备跨端互证能力" },
  6: { old: "04", title: "本文完成三端关联验证机制的设计、实现与验证" },
  8: { old: "05", title: "技术路线：离线提炼规则，端侧完成轻量评分" },
  9: { old: "13", title: "随机森林满足端侧部署约束" },
  11: { old: "06", title: "三端采集覆盖底层设备、宿主容器和前端运行时" },
  13: { old: "07", title: "session_id 将异步上报合并成同一会话证据" },
  14: { old: "08", title: "规则知识库把跨层异常转化为可解释判断" },
  15: { old: "09", title: "离线标注将规则语义转化为可训练标签" },
  16: { old: "10", title: "编码应用完成本地采集、编码和风险分输出" },
  17: { old: "11", title: "训练侧与端侧共享同一套65维特征约束" },
  18: { old: "15", title: "一致性特征把原始字段转换成关系信号" },
  20: { old: "12", title: "实验围绕数据来源、分组策略和评价指标展开" },
  21: { old: "14", title: "三端消融说明原始字段存在代理关系" },
  22: { old: "16", title: "分组验证下，三端语义特征优于65维Raw all" },
  23: { old: "19", title: "本研究完成了多端关联设备身份交叉验证机制" },
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
  setText(titleShape, text, {
    fontSize: 44,
    color: BLUE,
    bold: true,
    typeface: TITLE_FONT,
  });
}

function isTitleElement(element) {
  const s = snap(element);
  const f = s.frame || {};
  return s.name === "标题 1" || (s.kind === "shape" && f.top < 175 && String(s.text || "").trim());
}

function isHeaderChrome(element) {
  const s = snap(element);
  const f = s.frame || {};
  if (f.top < 175 && s.kind === "image") return true;
  if (f.top <= 195 && f.height <= 12 && f.width > 1000) return true;
  return false;
}

function deleteElement(slideObj, element) {
  if (typeof element.delete === "function") {
    element.delete();
    return;
  }
  const s = snap(element);
  const ids = [s.aid, s.id, element.id].filter(Boolean);
  for (const collection of [slideObj.elements, slideObj.shapes, slideObj.images, slideObj.tables]) {
    if (typeof collection?.deleteById !== "function") continue;
    for (const id of ids) {
      try {
        collection.deleteById(id);
      } catch {
        // Imported PPTX objects can expose different ids across collections.
      }
    }
  }
}

function clearBody(slideObj) {
  const items = [...slideObj.elements.items].reverse();
  for (const element of items) {
    if (isTitleElement(element) || isHeaderChrome(element)) continue;
    const f = snap(element).frame || {};
    if (f.top > 190) deleteElement(slideObj, element);
  }
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

function addQuietBorder(slideObj) {
  slideObj.shapes.add({
    geometry: "rect",
    position: {
      left: bodyFrame.left - 2,
      top: bodyFrame.top - 2,
      width: bodyFrame.width + 4,
      height: bodyFrame.height + 4,
    },
    fill: TRANSPARENT,
    line: { style: "solid", fill: "#d8e3f3", width: 1.25 },
  });
}

async function migrateOldSlide(presentation, targetSlide, oldSlide, slideTitle) {
  const slideObj = slide(targetSlide, presentation);
  clearBody(slideObj);
  title(slideObj, slideTitle);
  addQuietBorder(slideObj);
  await addImage(
    slideObj,
    path.join(cropDir, `old-slide-${oldSlide}-body.png`),
    bodyFrame,
    `旧版PPT第${Number(oldSlide)}页主体内容`,
  );
}

async function renderFinal(presentation) {
  await fs.rm(finalPreviewDir, { recursive: true, force: true });
  await fs.rm(finalLayoutDir, { recursive: true, force: true });
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

for (const [target, entry] of Object.entries(slideMap)) {
  await migrateOldSlide(presentation, Number(target), entry.old, entry.title);
}

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
