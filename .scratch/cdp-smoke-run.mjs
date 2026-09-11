// 批跑器（工单 code-editor-cdp-hang/01 验收项 ④ + batch-runner-self-heal/01 自助复判）：
// 按「每支前重建标签页」约定批量跑 CDP 冒烟脚本。
//
// 约定落地方式：**不改各脚本**——由本 runner 在每支脚本启动前用 CDP 重建标签页
// （json/close/<id> + PUT json/new?<url>），保证每支脚本拿到的都是干净页（无脏缓冲 →
// 不会弹 beforeunload 对话框 → 不会挂死）。`--no-rebuild` 用于对照复现挂死。
//
// 自助复判（第十三轮新增，判定口径见 cdp-harness.mjs 的 classifyAttempt/runVerdict）：
//   ① **非绿即单支复跑一次**（复跑前同样重建标签页）——首红复绿判为**偶发（flake）**，
//      不算批失败、单独列进汇总；两次都红判为**真红**。口径保守：只回答「这一支现在能不能过」。
//   ② **非绿支次自动落盘事件序列**：批跑器自己维持一条常驻 CDP 连接收集
//      `Runtime.exceptionThrown` / `Page.javascriptDialogOpening` / 导航事件，
//      按「支次」切片归拢后写 `.scratch/cdp-smoke-runs/<时间戳>-r<轮>-<脚本>.json` + `.txt`
//      （两类文件同内容不同呈现：json 供机读、txt 直接打开看现场）。绿支次不落盘。
//
// 用法：
//   node .scratch/cdp-smoke-run.mjs --port=9251 --scripts=a.mjs,b.mjs [--timeout=90] [--no-rebuild] [--rounds=1]
//   node .scratch/cdp-smoke-run.mjs --batch=overhaul          # 预置批次
//   node .scratch/cdp-smoke-run.mjs --batch=refine --retry=1  # 非绿复跑一次（默认）
//   node .scratch/cdp-smoke-run.mjs --batch=refine --retry=0  # 对照：单次判定，不复跑
//   node .scratch/cdp-smoke-run.mjs --batch=refine --no-diag  # 不起常驻监听（不落盘事件序列）
//
// 输出：逐支 PASS/FAIL/偶发/挂死 + 汇总（偶发支清单）；非绿时打印现场摘要并落盘事件序列；
//       挂死时打印现场并自动重建标签页恢复。
//
// 写脚本前先读两条（工单 real-acceptance/07，坑的全文见 `.scratch/browser-harness.mjs`
// 头部与挂账单 01 的「B 组统一前置 · 姿势清单」）：
//   · playwright `waitForFunction(fn, arg, options)` —— **超时是第三个参数**，写第二个会被
//     当 arg ⇒ 拿到默认 30s（表现为「我写了 15 分钟却 30 秒就红」）；
//   · 长流程别在 `page.evaluate` 里 await（单次 CDP 调用挂几十秒，看着像渲染进程挂死）——
//     kick off 不 await + 用 `.scratch/browser-harness.mjs` 的 `pollUntil()` 轮询 DOM。
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync, mkdirSync, existsSync } from "node:fs";
import {
  rebuildTab, pageTarget, connect,
  classifyAttempt, runVerdict, retryDecision, digestEvents, diagFileName, renderDiagText,
} from "./cdp-harness.mjs";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));   // 仓库根（本文件在 .scratch/ 下，往上两级）
const OUT = join(ROOT, ".scratch", "cdp-smoke-runs");
mkdirSync(OUT, { recursive: true });
const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const PORT = Number(argOf("port", "9251"));
const PAGE_URL = argOf("page", "http://127.0.0.1:8000/");
const TIMEOUT_S = Number(argOf("timeout", "90"));
const ROUNDS = Number(argOf("rounds", "1"));
const RETRY = Number(argOf("retry", "1"));                      // 允许的复跑次数（0 = 对照）
const NO_REBUILD = argv.includes("--no-rebuild");
const NO_DIAG = argv.includes("--no-diag");
const BATCH = argOf("batch", "");

const BATCHES = {
  overhaul: [1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => `.scratch/code-page-vscode-overhaul/smoke-0${i}.mjs`),
  polish: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => `.scratch/code-editor-vscode-polish/smoke-0${i}.mjs`),
  refine: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => `.scratch/code-editor-refine/smoke-${String(i).padStart(2, "0")}.mjs`),
  viewer: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map((i) => `.scratch/code-viewer-editor/smoke-${String(i).padStart(2, "0")}.mjs`),
  ideai: [5, 6, 7, 8].map((i) => `.scratch/code-ide-ai/smoke-0${i}.mjs`),
  treeops: [".scratch/code-tree-ops/smoke.mjs"],
  ideflow: [2, 3, 4].map((i) => `.scratch/code-ide-flow/smoke-0${i}.mjs`),
  bridge: [1, 2, 3, 4, 5].map((i) => `.scratch/mainc-codeview-bridge/smoke-0${i}.mjs`),
  libui: [
    ".scratch/master-library-ui-2/smoke.mjs",
    ".scratch/reference-library-ui/smoke.mjs",
    ".scratch/pdf-library-ui/smoke.mjs",
    ".scratch/module-library-ui/smoke.mjs",
  ],
  fem: [".scratch/frontend-es-modules/smoke.mjs"],
};

let SCRIPTS = argOf("scripts", "").split(",").map((s) => s.trim()).filter(Boolean);
if (!SCRIPTS.length && BATCH) {
  if (!BATCHES[BATCH]) { console.error(`未知批次 ${BATCH}（可选：${Object.keys(BATCHES).join(", ")}）`); process.exit(2); }
  SCRIPTS = BATCHES[BATCH];
}
if (!SCRIPTS.length) { console.error("请给 --scripts=a.mjs,b.mjs 或 --batch=<名>"); process.exit(2); }

// ---- 常驻监听：一条连接收全场事件，按支次切片（非绿才落盘） ----
// 域已在 connect() 内无条件 Page.enable + Runtime.enable（第十二轮修复），故这里能稳定收到
// 对话框与异常事件；命令级 20s 超时 + 自动应答也一并继承（本连接不主动导航，只旁听）。
// `watchTargets`：脚本自己 rebuildTab() 会关掉本连接所在的标签页 —— 第十三轮实测下这会让
// 旁听连接**一个事件都收不到**（事件全跑到新 target 上）。打开跟随即可自动改挂到新标签页。
let watcher = null;
let currentTargetId = null;
if (!NO_DIAG) {
  try {
    watcher = await connect({
      port: PORT, pageUrl: PAGE_URL, timeoutMs: 20000, watchTargets: true,
      onTargetChange: (nt) => { if (nt) currentTargetId = nt.id; },
    });
    console.log(`[diag] 常驻监听已建立（target ${String(watcher.target?.id).slice(0, 8)}，跟随标签页 + 非绿落盘）`);
  } catch (e) {
    console.log(`[diag] 常驻监听建立失败，本次不落盘事件序列：${String(e && e.message || e)}`);
    watcher = null;
  }
}
const drainEvents = () => (watcher ? watcher.events.splice(0, watcher.events.length) : []);

// settleEvents：给监听连接一点时间把 socket 里排队的事件解析进缓冲。
// **必须**：本批跑器用 spawnSync 同步等子进程 ⇒ 整个等待期间主线程被阻塞，WebSocket 的
// message 回调跑不了，事件只排在 socket 缓冲里（第十三轮实测：这就是「监听已对齐、事件恒为 0」
// 的真因；`await sleep(0)` 不够，要给足一个窗口并轮询确认）。
async function settleEvents({ ms = 1200, step = 150 } = {}) {
  if (!watcher) return 0;
  const deadline = Date.now() + ms;
  let n = watcher.events.length;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, step));
    if (watcher.events.length === n) {
      if (n > 0) break;                        // 已有事件且不再增长 → 认为送达完毕
    } else n = watcher.events.length;
  }
  return watcher.events.length;
}

// rebindWatcher：换标签页后把监听重挂到新 target（跟随能力仍在，此处是确定性重挂）。
async function rebindWatcher(targetId) {
  if (NO_DIAG) return;                       // --no-diag：不起监听（也就不落盘事件序列）
  const old = watcher;
  try {
    watcher = await connect({
      port: PORT, pageUrl: PAGE_URL, timeoutMs: 20000, targetId, watchTargets: true,
      onTargetChange: (nt) => { if (nt) currentTargetId = nt.id; },
    });
    if (old) old.close();
  } catch { watcher = null; }
}

// postMortem：支次结束后，若监听**没收到任何事件**（典型：脚本自己 rebuildTab 换了标签页、
// 而跟随轮询在 spawnSync 阻塞期间跑不动 —— 见 settleEvents 注释），就追挂到新的页面 target
// 上，反射一次现场（就绪状态 / 关键节点 / 页面内错误），至少给非绿支次留下可查证据。
// 注意这是「反射」不是「实录」：事件序列仍可能有缺口，要完整序列请让脚本用 `CDP_BATCH_TARGET`。
async function postMortem() {
  if (!watcher) return null;
  try {
    const list = await listTargets(PORT);
    const pages = (Array.isArray(list) ? list : []).filter((x) => x.type === "page" && String(x.url).startsWith(PAGE_URL));
    const live = pages.find((x) => x.id === currentTargetId);
    if (live) return null;                              // 监听所在的页还活着：无需追挂
    const nt = pages[pages.length - 1];
    if (!nt) return null;
    await ensureAttached(`${nt.id.slice(0, 8)} 追挂`, { force: true, targetId: nt.id });
    await settleEvents({ ms: 600 });
    const snap = await watcher.Eval(`JSON.stringify({
      readyState: document.readyState,
      url: location.href,
      hasTabCode: !!document.getElementById('tab-code'),
      title: document.title,
    })`, 5000).catch((e) => `反射失败：${String(e && e.message || e)}`);
    return { reattachedTo: nt.id, snapshot: snap };
  } catch (e) {
    return { reattachError: String(e && e.message || e) };
  }
}


// 第十三轮实测教训：批跑器里跟随轮询与重挂并发时会互相打架——跟随可能把连接挪到残留/旧标签页上，
// 于是整个批跑的事件数恒为 0（而单跑复刻完全正常）。这里做成**每支次前强制对齐**，并在
// `force` 时把旧连接（连同它的跟随轮询）关掉重挂，保证任一时刻只有一套轮询在跑。
// ensureAttached：支次开始前核对「监听挂在的 target」＝「脚本要用的 target」。
// 第十三轮实测教训：批跑器里跟随轮询与重挂并发时会互相打架——跟随可能把连接挪到残留/旧标签页上，
// 于是整个批的事件数恒为 0（而单跑复刻完全正常）。这里做成**每支次前强制对齐**，并在
// `force` 时把旧连接（连同它的跟随轮询）关掉重挂，保证任一时刻只有一套轮询在跑。
const DEBUG_WATCH = argv.includes("--debug-watch");
async function ensureAttached(label, { force = false, targetId = null } = {}) {
  if (NO_DIAG) return false;
  const want = targetId || currentTargetId;
  if (!want) return false;
  if (!watcher) { await rebindWatcher(want); return !!(watcher && watcher.target); }
  const pre = { target: watcher.target && watcher.target.id, buf: watcher.events.length };
  if (!force && watcher.target && want && watcher.target.id === want) {
    if (DEBUG_WATCH) console.log(`      [watch] @${label} 已对齐 ${String(pre.target).slice(0, 8)}（缓冲 ${pre.buf}）`);
    return true;
  }
  if (DEBUG_WATCH) console.log(`      [watch] @${label} ${force ? "强制" : "未对齐"}重挂（监听 ${String(pre.target).slice(0, 8)} vs 目标 ${String(want).slice(0, 8)}）`);
  await rebindWatcher(want);
  const ok = !!(watcher && watcher.target && watcher.target.id === want);
  if (!ok && DEBUG_WATCH) console.log(`      [watch] 重挂后仍未对齐：监听 ${String(watcher && watcher.target && watcher.target.id).slice(0, 8)} vs 目标 ${String(want).slice(0, 8)}`);
  return ok;
}

function spawnOnce(script) {
  const t0 = Date.now();
  if (argv.includes("--debug-path")) console.log(`      spawn: ${JSON.stringify(join(ROOT, script))} cwd=${JSON.stringify(ROOT)} exists=${existsSync(join(ROOT, script))}`);
  const r = spawnSync(process.execPath, [join(ROOT, script)], {
    encoding: "utf8", timeout: TIMEOUT_S * 1000, cwd: ROOT,
    // CDP_BATCH_TARGET：把「本支次所用的标签页」告诉脚本（约定：脚本若支持就复用它、
    // 不再自己 rebuildTab）。这样脚本与旁听连接在**同一个** target 上，事件才收得到；
    // 不支持该约定的脚本行为不变（自己换标签页 → 旁听靠 watchTargets 跟随，
    // 但换页瞬间的事件会漏，见 cdp-harness.mjs 注释）。
    env: { ...process.env, PYTHONIOENCODING: "utf8", ...(currentTargetId ? { CDP_BATCH_TARGET: currentTargetId } : {}) },
  });
  const ms = Date.now() - t0;
  const out = (r.stdout || "") + (r.stderr || "");
  return {
    ms, exit: r.status, out, t0,
    stdout: r.stdout || "", stderr: r.stderr || "",
    tail: (r.stdout || "").trim().split("\n").slice(-2).join(" | "),
    stdioTail: { stderr: (r.stderr || "").trim().split("\n").slice(-12).join("\n       "),
                 stdout: (r.stdout || "").trim().split("\n").slice(-6).join("\n       ") },
    timedOut: !!(r.error && r.error.code === "ETIMEDOUT"),
  };
}

// tailText：取文本末尾 n 行（第十四轮补：非绿支次要能自己说清「哪几条断言红了」，
// 此前落盘只有 tail 两行，而 tail 往往来自复跑那次，真现场反而丢了）。
const tailText = (s, n) => {
  const lines = String(s || "").replace(/\r/g, "").trimEnd().split("\n");
  return lines.slice(-n).join("\n");
};

// 现场判定：命令还回不回来（决定「挂死」与「只是断言红」）
async function forensic() {
  const t = await pageTarget({ port: PORT, pageUrl: PAGE_URL, anyPage: true });
  try {
    const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 6000 });
    const v = await c.Eval("1+1", 6000);
    c.close();
    return { eval_1plus1: v, target: t && t.id.slice(0, 8), unresponsive: null };
  } catch (e) {
    return { unresponsive: String(e), target: t && t.id.slice(0, 8) };
  }
}

async function attemptOnce(script, t0Outer) {
  await ensureAttached(script);                       // 支次前对齐「监听 target = 脚本 target」
  if (DEBUG_WATCH) console.log(`      [watch] spawn 前：监听=${String(watcher && watcher.target && watcher.target.id).slice(0, 8)} 脚本=${String(currentTargetId).slice(0, 8)} 缓冲=${watcher ? watcher.events.length : "n/a"}`);
  const raw = spawnOnce(script);
  const cls = classifyAttempt({ exit: raw.exit, timedOut: raw.timedOut, out: raw.out });
  await settleEvents();                               // 同步等待后必须让事件解析进缓冲（见函数注释）
  let seen = drainEvents();
  let pm = null;
  if (!seen.length && !cls.pass) {                    // 一条事件都没收到：追挂新页面反射现场
    pm = await postMortem();
    seen = drainEvents();
  }
  let forensics = null;
  if (!cls.pass) forensics = await forensic();        // 非绿才花代价探现场
  const rec = {
    attemptMs: raw.ms, exit: raw.exit, timedOut: cls.timedOut,
    pageUnresponsive: !!(forensics && forensics.unresponsive),
    tail: raw.tail, reasons: cls.reasons, pass: cls.pass, hung: cls.hung,
    events: seen, forensics, stdioTail: raw.stdioTail, t0: raw.t0 || t0Outer, postMortem: pm,
    stdoutTail: tailText(raw.stdout, 80), stderrTail: tailText(raw.stderr, 40),
  };
  return rec;
}

function persistDiag(rec) {
  const digest = digestEvents(rec.events, { t0Ms: rec.t0 });
  const stamp = Date.now();
  const payload = {
    script: rec.script, round: rec.round, attempt: rec.attempt, ts: stamp,
    verdict: rec.verdict, exit: rec.exit, timedOut: rec.timedOut, hung: rec.hung,
    reasons: rec.reasons, tail: rec.tail, forensics: rec.forensics, postMortem: rec.postMortem || null, digest,
    stdoutTail: rec.stdoutTail || "", stderrTail: rec.stderrTail || "",
  };
  const base = diagFileName(rec.script, rec.round, { stamp });
  writeFileSync(join(OUT, base), JSON.stringify(payload, null, 2), "utf8");
  writeFileSync(join(OUT, base.replace(/\.json$/, ".txt")), renderDiagText({
    script: rec.script, round: rec.round, attempt: rec.attempt, ts: stamp, digest, attemptRecord: payload,
  }), "utf8");
  return { base, digest, forensicsOk: rec.forensics ? !rec.forensics.unresponsive : null };
}

const results = [];
let hangs = 0, fails = 0, passes = 0, flakes = 0;
const flakeList = [];

for (let round = 1; round <= ROUNDS; round++) {
  for (const script of SCRIPTS) {
    const name = script.replace(/^\.scratch\//, "");
    const tOuter = Date.now();
    if (!NO_REBUILD) {
      const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
      if (!t) { console.error(`!! 无法重建标签页（CDP ${PORT} 不可达？）`); process.exit(3); }
      currentTargetId = t.id;                         // 本支次所用标签页（随环境变量交给脚本）
      await ensureAttached(`${name} 首跑前`, { force: true });   // 唯一所有者：关旧轮询、挂新 target
    }
    drainEvents();                                    // 丢弃重建期自身的噪声事件

    // 首跑
    const first = await attemptOnce(script, tOuter);
    first.script = name; first.round = round; first.attempt = 1;
    const attempts = [first];
    let diagNote = null;

    // 非绿 → 单支复跑一次（复跑前重建标签页，与批跑一致）
    const decision = retryDecision(classifyAttempt({ exit: first.exit, timedOut: first.timedOut, out: first.tail }), { retry: RETRY, attemptIndex: 1 });
    let retryRec = null;
    if (decision.retry) {
      console.log(`      ↻ 非绿（${first.reasons.join("；")}）→ 复跑一次定性（${decision.reason}）`);
      if (!NO_REBUILD) {
        const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
        if (t) currentTargetId = t.id;
        await ensureAttached(`${name} 复跑前`, { force: true });
        drainEvents();
      }
      retryRec = await attemptOnce(script, Date.now());
      retryRec.script = name; retryRec.round = round; retryRec.attempt = 2;
      attempts.push(retryRec);
    }

    const verdict = runVerdict(first, retryRec);
    // 逐支次落盘：首跑非绿必落；复跑非绿也落（两次现场都要留）
    const diagFiles = [];
    for (const a of attempts) {
      if (a.pass) continue;
      a.verdict = verdict.verdict;
      const d = persistDiag(a);
      diagFiles.push(d.base);
      a.diagFile = d.base;                              // 按支次归属，避免复跑现场互相串号
      if (!diagNote) diagNote = d;
    }

    const last = attempts[attempts.length - 1];
    // 计数口径：passes/fails/hangs 只数「首次支次」，保持既有汇总语义
    if (first.hung) hangs++; else if (first.pass) passes++; else fails++;
    if (verdict.flake) { flakes++; flakeList.push(`${name} r${round}（首跑 exit=${first.exit} → 复跑 exit=${last.exit} 绿）`); }

    const mark = verdict.verdict === "pass" ? "PASS" : verdict.verdict === "flake" ? "偶发" : verdict.verdict === "hang" ? "挂死" : "FAIL";
    const retryNote = retryRec ? ` [复跑 exit=${retryRec.exit} ${retryRec.attemptMs}ms]` : "";
    console.log(`r${round} ${mark.padEnd(4)} ${name.padEnd(52)} exit=${String(first.exit).padStart(4)} ${String(first.attemptMs).padStart(6)}ms${retryNote} | ${last.tail}`);
    if (verdict.verdict !== "pass") {
      console.log(`      判定：${verdict.verdict}${verdict.flake ? "（首红复绿 = 偶发，不计失败）" : ""}；信号：${first.reasons.join("；") || "（无）"}${retryRec ? ` → 复跑信号：${retryRec.reasons.join("；") || "（无）"}` : ""}`);
      // 现场取**首跑**（红的那次）：复跑多半是绿的，拿它的输出会把真现场盖掉（第十四轮修正）。
      const showTail = first.pass ? last : first;
      if (showTail.stdioTail?.stderr) console.log(`      stderr（首跑）: ${showTail.stdioTail.stderr}`);
      if (showTail.stdioTail?.stdout) console.log(`      stdout（首跑）: ${showTail.stdioTail.stdout}`);
      if (diagNote) console.log(`      事件序列：[${diagNote.digest.kept.length} 关键事件 / ${diagNote.digest.total} 总事件] ${diagNote.digest.summary}`);
      if (diagFiles.length) console.log(`      已落盘（含该支次完整输出尾 80 行）：${diagFiles.map((f) => `.scratch/cdp-smoke-runs/${f}`).join(" , ")}`);
      if (first.forensics) console.log(`      现场：${JSON.stringify(first.forensics)}`);
    }
    if (verdict.verdict === "hang") {
      const t = await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
      if (t) currentTargetId = t.id;
      await ensureAttached(`${name} 挂死恢复`, { force: true });
      console.log(`      已重建标签页恢复：${t ? "OK" : "失败"}`);
    }

    results.push({
      round, script: name, ms: last.ms, exit: last.exit, timedOut: last.timedOut, hung: last.hung,
      pass: last.pass,                                     // 顶层语义不变 = 最后一次尝试
      verdict: verdict.verdict, flake: verdict.flake,
      attempts: attempts.map((a) => ({
        attempt: a.attempt, ms: a.attemptMs, exit: a.exit, timedOut: a.timedOut, hung: a.hung,
        pass: a.pass, reasons: a.reasons, diag: a.diagFile || null,
      })),
      retry: retryRec ? { exit: retryRec.exit, ms: retryRec.attemptMs, pass: retryRec.pass } : null,
      diagFile: diagFiles[0] || null, diagFiles,
      tail: last.tail, forensics: first.forensics,
    });
  }
}
if (watcher) watcher.close();

console.log(`\n---- 汇总 ----`);
console.log(`PASS ${passes} / FAIL ${fails} / 挂死 ${hangs}｜偶发 ${flakes}（共 ${results.length} 支次，${NO_REBUILD ? "未重建标签页（对照）" : "每支前重建标签页"}，--retry=${RETRY}${NO_DIAG ? "，--no-diag" : ""}）`);
// 退出码按**终局判定**算（第十四轮修正）：上面的 FAIL/挂死 计的是「首跑」，
// 而首跑红、复跑绿 = 偶发，按第十三轮口径「不计失败」——此前退出码仍取 fails，
// 于是「只有偶发」也会 exit 1，与记录里的口径自相矛盾。真失败 = verdict=fail/hang。
const realFails = results.filter((r) => r.verdict === "fail").length;
const realHangs = results.filter((r) => r.verdict === "hang").length;
console.log(`判定口径：FAIL/挂死 计首跑；真失败（复跑仍红）${realFails} / 真挂死 ${realHangs} ⇒ 退出码 ${realFails || realHangs ? 1 : 0}`);
if (flakeList.length) {
  console.log(`偶发支清单（首红复绿，不计失败）：`);
  for (const f of flakeList) console.log(`  - ${f}`);
}
writeFileSync(join(OUT, `run-${Date.now()}.json`), JSON.stringify({
  port: PORT, batch: BATCH || "(scripts)", noRebuild: NO_REBUILD, retry: RETRY, noDiag: NO_DIAG,
  summary: { passes, fails, hangs, flakes, realFails, realHangs }, flakeList, results,
}, null, 2), "utf8");
process.exit(realFails || realHangs ? 1 : 0);
