// 工单 real-acceptance/06 体检页渲染探针：**真端点载荷 + 真渲染函数**。
// 取线上 /api/env/status（本机实况：三件跨 ccs2050 / ccs2051）→ 直接喂
// fx/env.js 的 envCheckStatusHTML（页面就是 innerHTML 这一段）→ 打印 CCS 相关
// 行的人可读文本，证明「体检页能看到说明 + 三件来源根」。
//
// 用法：node .scratch/real-acceptance/probe-06-env-render.mjs
import { envCheckStatusHTML, ccsSourceText } from "../../src/contest_generator/static/js/fx/env.js";

const BASE = "http://127.0.0.1:8000";
const status = await (await fetch(`${BASE}/api/env/status`)).json();
const html = envCheckStatusHTML(status, null, null);

// 行切分（data-env-row="<key>"）→ 去标签 → 压空白，便于人眼核对
const rows = html.split('<div class="env-row" data-env-row="').slice(1).map((chunk) => {
  const key = chunk.slice(0, chunk.indexOf('"'));
  const body = chunk.slice(chunk.indexOf(">") + 1).split("</div>")[0];
  return { key, text: body.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim() };
});

const ccsRows = rows.filter((r) => r.key.startsWith("ccs-"));
for (const r of ccsRows) console.log(`[${r.key}] ${r.text}`);
console.log(`\n来源一句话（纯函数）：${ccsSourceText(status.ccs_tools)}`);

const note = ccsRows.find((r) => r.key === "ccs-note");
const fail = [];
if (!note) fail.push("缺 ccs-note 说明行");
if (note && !note.text.includes("三件逐件独立探测")) fail.push("说明行缺「三件逐件独立探测」");
if (note && !note.text.includes("可能来自不同 CCS 安装目录")) fail.push("说明行缺「可能来自不同 CCS 安装目录」");
if (note && !note.text.includes("编译器 ccs2050")) fail.push("说明行缺本机编译器来源根");
if (note && !note.text.includes("（跨安装目录）")) fail.push("说明行缺跨目录判定");
for (const k of ["ccs-sdk", "ccs-compiler", "ccs-sysconfig"]) {
  const row = ccsRows.find((r) => r.key === k);
  if (!row) fail.push(`缺 ${k} 行`);
  else if (!row.text.includes("（安装根 ")) fail.push(`${k} 行缺安装根`);
}
console.log(fail.length ? `FAILURES: ${fail.length}（${fail.join("；")}）` : "ALL PASS");
process.exit(fail.length ? 1 : 0);
