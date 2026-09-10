// B24（revise-deepen/05 收口·可确定性验证的部分）：修订阶段卡的两条入口 + 加载态 + 错误路径。
//
// 源工单六条验收里，**分析 / 执行 / 回滚**三步要真实 LLM 与工具链（属 C 组「真实额度」），
// 这里钉死不依赖 LLM 的部分：
//   ① 阶段卡入口齐备：「从当前会话加载」(#btn-revise-session) +「历史目录选择」(#btn-revise-dir-input / 加载目录)；
//   ② 历史目录加载成功 → 上下文卡渲染（来源=历史目录反推、平台、模块、题面缺失提示）；
//   ③ 错误路径：目录不存在 / 不含工程配置文件 → 中文错误提示（行内 #revise-load-msg），
//      状态行清空（不留在「加载中…」）；
//   ④ 三条阶段槽位（分析 / 执行 / 结果）与回滚按钮初始隐藏。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。零写库：只用临时目录构造假工程。
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const PORT = 9251;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const FAKE = join(tmpdir(), "dsh-b24-revise-proj");

const t = await rebuildTab({ port: PORT });
if (!t) { console.error("重建标签页失败"); process.exit(1); }
const c = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => c.Eval(e);

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};

for (let i = 0; i < 120; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('revise-dir-input')`)) break;
  await sleep(250);
}

// 造一个「历史工程」：工程配置文件（认平台）+ modules/<slug>/（认模块）+ main.c
rmSync(FAKE, { recursive: true, force: true });
mkdirSync(join(FAKE, "modules", "led"), { recursive: true });
mkdirSync(join(FAKE, "user"), { recursive: true });
writeFileSync(join(FAKE, "user", "Project.uvprojx"),
  '<?xml version="1.0" encoding="UTF-8"?>\n<Project><Targets><Target><TargetName>smoke</TargetName></Target></Targets></Project>\n', "utf8");
writeFileSync(join(FAKE, "main.c"), "#include \"led.h\"\nint main(void) { led_init(); return 0; }\n", "utf8");

const entries = await Eval(`({
  session: !!document.getElementById('btn-revise-session'),
  dirInput: !!document.getElementById('revise-dir-input'),
  loadBtn: !!document.getElementById('btn-revise-load-dir'),
  analysisHidden: document.getElementById('revise-analyze-box').classList.contains('hidden'),
  execHidden: document.getElementById('revise-exec-box').classList.contains('hidden'),
  rollbackHidden: document.getElementById('btn-revise-rollback').classList.contains('hidden'),
  contextHidden: document.getElementById('revise-context').classList.contains('hidden'),
})`);
check("B24 阶段卡两条入口齐备（从当前会话加载 / 历史目录加载）", entries.session && entries.dirInput && entries.loadBtn, JSON.stringify(entries));
check("B24 初始态：分析 / 执行 / 结果槽位与回滚按钮均隐藏",
  entries.analysisHidden && entries.execHidden && entries.rollbackHidden && entries.contextHidden, JSON.stringify(entries));

// ② 历史目录加载
await Eval(`(() => { const el = document.getElementById('revise-dir-input');
  el.value = ${JSON.stringify(FAKE.replace(/\\/g, "/"))};
  el.dispatchEvent(new Event('input', { bubbles: true }));
  document.getElementById('btn-revise-load-dir').click(); })()`);
let loaded = null;
for (let i = 0; i < 40; i++) {
  loaded = await Eval(`({ status: document.getElementById('revise-load-status').textContent.trim(),
    msg: document.getElementById('revise-load-msg').textContent.trim(),
    hidden: document.getElementById('revise-context').classList.contains('hidden'),
    source: document.getElementById('revise-context-source').textContent,
    platform: document.getElementById('revise-platform').textContent.trim(),
    slugs: document.getElementById('revise-slugs').textContent.trim(),
    problem: document.getElementById('revise-problem').textContent.trim(),
    warn: document.getElementById('revise-missing-warn').textContent.trim(),
    warnHidden: document.getElementById('revise-missing-warn').classList.contains('hidden') })`);
  if (loaded.status === "加载完成" || loaded.msg) break;
  await sleep(250);
}
check("B24 历史目录加载成功（状态行「加载完成」+ 上下文卡可见）",
  loaded.status === "加载完成" && !loaded.hidden, JSON.stringify(loaded));
check("B24 上下文内容：来源=历史目录反推 + 平台词表识别 + 模块识别",
  loaded.source.includes("历史目录反推") && loaded.platform.length > 0 && loaded.slugs.includes("led"),
  JSON.stringify({ source: loaded.source, platform: loaded.platform, slugs: loaded.slugs }));
check("B24 题面缺失提示（无清单反推不出题面 → 补题面入口可见）",
  loaded.problem.includes("缺失") && !loaded.warnHidden, JSON.stringify({ problem: loaded.problem, warn: loaded.warn.slice(0, 60) }));

// ③ 错误路径一：目录不存在
await Eval(`(() => { const el = document.getElementById('revise-dir-input');
  el.value = ${JSON.stringify(join(tmpdir(), "dsh-b24-does-not-exist").replace(/\\/g, "/"))};
  document.getElementById('btn-revise-load-dir').click(); })()`);
let err1 = null;
for (let i = 0; i < 40; i++) {
  err1 = await Eval(`({ msg: document.getElementById('revise-load-msg').textContent.trim(),
    status: document.getElementById('revise-load-status').textContent.trim(),
    hidden: document.getElementById('revise-context').classList.contains('hidden') })`);
  if (err1.msg) break;
  await sleep(250);
}
check("B24 错误路径①：目录不存在 → 中文提示 + 状态行不残留「加载中」",
  err1.msg.includes("加载失败") && err1.status === "" && err1.hidden, JSON.stringify(err1));

// ③ 错误路径二：目录存在但没有工程配置文件（判不出平台）
const NO_CFG = join(tmpdir(), "dsh-b24-no-config");
rmSync(NO_CFG, { recursive: true, force: true });
mkdirSync(NO_CFG, { recursive: true });
writeFileSync(join(NO_CFG, "main.c"), "int main(void) { return 0; }\n", "utf8");
await Eval(`(() => { const el = document.getElementById('revise-dir-input');
  el.value = ${JSON.stringify(NO_CFG.replace(/\\/g, "/"))};
  document.getElementById('btn-revise-load-dir').click(); })()`);
let err2 = null;
for (let i = 0; i < 40; i++) {
  err2 = await Eval(`document.getElementById('revise-load-msg').textContent.trim()`);
  if (err2) break;
  await sleep(250);
}
check("B24 错误路径②：无工程配置文件 → 中文提示（判不出平台）",
  err2.includes("加载失败") && (err2.includes("工程配置") || err2.includes("平台")), JSON.stringify(err2));

// 收尾：清掉假工程，避免留在磁盘上
rmSync(FAKE, { recursive: true, force: true });
rmSync(NO_CFG, { recursive: true, force: true });
console.log("---- B24（可确定性验证部分）总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
