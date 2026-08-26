// 阶段 2 工单 09：赛题库 tab + 拆条校对迁 ui/topic.js（15 函数 + 9 状态 +
// initTopicToolbar() 顶层调用 + btn-topic-split / btn-topic-confirm 监听）。
// 顺带修正 pdfFileUrl 单源（05 迁移悬空 → fx/pdf.js 导出，ui/pdf.js 改 import）。
// 删除段（物理升序）：赛题库整簇（区段头 4933 → btn-topic-confirm 监听末）。
// host 顶部 import 追加 topic.js 代理 7 名；generate-recommend 代理行裁 useTopic
// （调用点 5035/5094 随簇迁入 topic.js，host 不再用）。全程 CRLF 感知。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/topic.js"'))) throw new Error("topic import already present");

// ---- 1) host import：reference import 之后追加；generate-recommend 代理行裁 useTopic
{
  const ri = must(lines.findIndex((l) => l.includes('from "/js/ui/reference.js"')), "reference import");
  lines.splice(ri + 1, 0,
    'import { loadTopics, loadTopicGroupVocabulary, initTopicToolbar, viewTopicDetail, viewTopicEdit, deleteTopic, renderProofreadRows } from "/js/ui/topic.js";');
}
{
  const gi = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-recommend.js"')), "recommend import");
  if (!lines[gi].includes("useTopic,")) throw new Error("useTopic not in recommend import?");
  lines[gi] = lines[gi].replace("useTopic, ", "");
  if (lines[gi].includes("useTopic")) throw new Error("useTopic still in import");
}

// ---- 2) 赛题库整簇 → 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("// 赛题库页：浏览 / 过滤 / 拆条录入（逐条校对）/ 删除")), "topic section header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before topic header not found");
  const b = must(lines.findIndex((l) => l.startsWith('$("btn-topic-confirm").addEventListener("click"')), "btn-topic-confirm");
  let e = b;
  while (e < lines.length && lines[e] !== "});") e++;
  if (e >= lines.length) throw new Error("btn-topic-confirm end not found");
  const next = lines[e + 1];
  if (!/^\/\/ -+$/.test(next) && next !== "") {
    throw new Error("unexpected boundary after btn-topic-confirm: " + JSON.stringify(next));
  }
  const removed = lines.slice(dashA, e + 1).join(eol);
  for (const n of ["topicRows", "topicPdfFile", "topicArchiveLoaded", "loadTopicArchiveLink", "topicUI", "topicEntries", "topicGroupVocab", "topicSearchTimer", "topicLoading", "topicFilterContext", "renderTopicYearChips", "renderTopicStats", "renderTopics", "topicPageCache", "loadTopicPageState", "renderTopicPages", "viewTopicDetail", "viewTopicEdit", "clearTopicFilter", "initTopicToolbar", "loadTopicGroupVocabulary", "loadTopics", "deleteTopic", "renderProofreadRows"]) {
    if (!new RegExp("(function|const|let)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n);
  }
  if (!removed.includes("useTopic(")) throw new Error("useTopic call sites not in span");
  if (!removed.includes("initTopicToolbar();")) throw new Error("top-level initTopicToolbar call not in span");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 赛题库页：浏览 / 过滤 / 拆条录入（逐条校对）/ 删除（已迁 ui/topic.js）",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/topic.js（阶段 2 工单 09）：topicRows / topicPdfFile /",
    "// topicArchiveLoaded / topicUI / topicEntries / topicGroupVocab /",
    "// topicSearchTimer / topicLoading / topicPageCache 状态 + loadTopicArchiveLink /",
    "// topicFilterContext / renderTopicYearChips / renderTopicStats / renderTopics /",
    "// loadTopicPageState / renderTopicPages / viewTopicDetail / viewTopicEdit /",
    "// clearTopicFilter / initTopicToolbar / loadTopicGroupVocabulary / loadTopics /",
    "// deleteTopic / renderProofreadRows + 拆条录入监听（btn-topic-split /",
    "// btn-topic-confirm）。纯件在 fx/topic.js（工单 04 迁）；「用此题生成」",
    "// useTopic 归 ui/generate-recommend.js（工单 12 迁），本模块 import 调用",
    "// （卡片与详情弹窗两处）。host 页签分发器经顶部 import 调 loadTopics /",
    "// loadTopicGroupVocabulary（见 import 行）。",
    "",
  ];
  lines.splice(dashA, e - dashA + 1, ...note);
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["loadTopicArchiveLink", "topicFilterContext", "renderTopicYearChips", "renderTopicStats", "renderTopics", "loadTopicPageState", "renderTopicPages", "viewTopicDetail", "viewTopicEdit", "clearTopicFilter", "initTopicToolbar", "loadTopicGroupVocabulary", "loadTopics", "deleteTopic", "renderProofreadRows"]) {
  if (new RegExp("(function|const|let)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
if (/^(let|const)\s+(topicRows|topicPdfFile|topicArchiveLoaded|topicUI|topicEntries|topicGroupVocab|topicSearchTimer|topicLoading|topicPageCache)$/m.test(out)) throw new Error("residual topic state");
for (const frag of ['loadTopics(); loadTopicGroupVocabulary();', 'from "/js/ui/topic.js"']) {
  if (!out.includes(frag)) throw new Error("host call site / import vanished: " + frag);
}
if (out.includes("useTopic(")) throw new Error("useTopic call site still in host");
if (out.includes("pdfFileUrl(")) throw new Error("pdfFileUrl call site still in host (moved to topic.js)");
if (out.includes("function pdfFileUrl")) throw new Error("residual pdfFileUrl def in host");

writeFileSync(p, out, "utf8");
console.log("OK: topic cluster moved; host rewired; lines now", lines.length);
