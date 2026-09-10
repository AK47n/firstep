// .scratch/cdp-harness.mjs —— CDP 冒烟共用工具（工单 code-editor-cdp-hang/01 收口）
//
// 存在的理由（根因见 .scratch/code-editor-cdp-hang/issues/01-reload-renderer-hang.md）：
//   编辑器有未保存标签（tab.content !== tab.savedContent）时，`beforeunload` 退出保护
//   会让 Chrome 在 `Page.reload` / `Page.navigate` 前弹**原生 beforeunload 对话框**；
//   对话框未被应答时渲染进程卡住 —— 此后所有「渲染进程侧」CDP 命令
//   （Runtime.evaluate / DOM.* / Page.navigate）永不返回（浏览器进程侧的
//   Input.dispatchKeyEvent / Page.handleJavaScriptDialog 仍能应答，据此可与崩溃区分）。
//   这不是产品缺陷（真实浏览器里用户点「离开」即继续；对话框被应答后页面完全恢复，
//   见 verify-recovery-clean.mjs 9/9），而是自动化侧没应答对话框。
//
// 因此本模块提供两件事：
//   1. rebuildTab()  —— 每支脚本前重建标签页（clean 页 = 无脏缓冲 = 无对话框），最省事的约定；
//   2. connect()     —— 挂 `Page.javascriptDialogOpening` → 立即
//                       `Page.handleJavaScriptDialog{accept:true}` 自动应答，
//                       并给每个命令加超时守卫（挂死显式报错，不静默卡住）。
//
// 用法：
//   import { rebuildTab, connect, ensureReady } from "<相对路径>/cdp-harness.mjs";
//   await rebuildTab({ port: 9251 });                       // 每支脚本前
//   const cdp = await connect({ port: 9251 });              // cdp.cdp / cdp.Eval / cdp.close
//   await cdp.cdp("Page.reload", { ignoreCache: true });    // 对话框自动应答
//
// 零依赖：Node 内置 fetch + WebSocket（Node ≥ 22）。
export const DEFAULT_PAGE_URL = "http://127.0.0.1:8000/";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function fetchT(url, ms = 5000, opts = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
}

export async function listTargets(port) {
  try { return await (await fetchT(`http://127.0.0.1:${port}/json/list`)).json(); }
  catch { return []; }
}

export async function pageTarget({ port, pageUrl = DEFAULT_PAGE_URL, anyPage = false }) {
  const list = await listTargets(port);
  if (!Array.isArray(list)) return null;
  const hit = list.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
  if (hit) return hit;
  return anyPage ? list.find((t) => t.type === "page") || null : null;
}

// rebuildTab：关掉现有页面标签 → 新开一个（`json/new` 必须 PUT）。返回新 target 或 null。
// 这是「每支脚本前重建标签页」约定的实现；挂死现场也可用它恢复。
export async function rebuildTab({ port, pageUrl = DEFAULT_PAGE_URL, settleMs = 1500 } = {}) {
  const t = await pageTarget({ port, pageUrl, anyPage: true });
  if (t) {
    await fetchT(`http://127.0.0.1:${port}/json/close/${t.id}`, 5000).catch(() => {});
    await sleep(400);
  }
  await fetchT(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(pageUrl)}`, 8000, { method: "PUT" }).catch(() => {});
  await sleep(settleMs);
  return pageTarget({ port, pageUrl, anyPage: true });
}

// connect：连上 page target；每个命令带超时守卫；对话框自动应答。
//   opts.port         CDP 端口（脚本各异：9251 / 9231 …）
//   opts.pageUrl      页面地址（默认 8000）
//   opts.timeoutMs    单命令超时（默认 20000，与既有 overhaul 守卫同值）
//   opts.autoDialog   是否自动应答对话框（默认 true）
//   opts.onEvent      事件回调（可选，收全部 CDP 事件）
//   opts.targetId     指定 target id（可选；重建标签页后旁听用，见下）
//   opts.watchTargets 跟随标签页变化（可选；旁听用）：脚本自己 `rebuildTab()` 会把 target
//                     换掉（旧 target 被关），此时原连接收不到任何新事件 —— 打开本项后
//                     connect 会自动改挂到「最新的 page target」，并回调 opts.onTargetChange(newTarget)
export async function connect({
  port, pageUrl = DEFAULT_PAGE_URL, timeoutMs = 20000, autoDialog = true, onEvent,
  targetId = null, watchTargets = false, onTargetChange,
} = {}) {
  // targetId 优先：批跑器重建标签页后会**换 target**，按 URL 轮询可能命中残留/其他标签页，
  // 于是旁听连接收不到任何事件（第十三轮实测：常驻监听总事件数为 0）。有了 targetId 就能
  // 确定性挂到「刚重建出来的那一个」。
  // 显式给了 targetId 就不再兜底换页：兜底会静默挂到**别的**标签页上，比报错更难查。
  let t = null;
  if (targetId) {
    const list = await listTargets(port);
    t = Array.isArray(list) ? list.find((x) => x.id === targetId && x.type === "page") || null : null;
    if (!t) throw new Error(`指定的 target 不存在或已关闭（${targetId}，端口 ${port}）`);
  }
  if (!t) t = await pageTarget({ port, pageUrl });
  if (!t) t = await rebuildTab({ port, pageUrl });
  if (!t) throw new Error(`CDP 不可达或无 page target（端口 ${port}）`);

  let ws = new WebSocket(t.webSocketDebuggerUrl);
  let seq = 0;
  let switching = false;                    // 跟随标签页时的重入保护
  let knownTargetIds = new Set([t.id]);     // 已知页面 target（识别「新出现」的页面用）
  const pending = new Map();
  const events = [];
  let dialogsAccepted = 0;

  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("CDP ws error")); });

  const send = (method, params = {}) => { try { ws.send(JSON.stringify({ id: ++seq, method, params })); } catch {} };
  const onMessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); return; }
    if (msg.method) {
      events.push({ t: Date.now(), method: msg.method, params: msg.params });
      if (typeof onEvent === "function") onEvent(msg);
      // 关键：对话框一到就应答（不等调用方）
      if (autoDialog && msg.method === "Page.javascriptDialogOpening") {
        dialogsAccepted++;
        send("Page.handleJavaScriptDialog", { accept: true });
      }
    }
  };
  ws.onmessage = onMessage;

  const cdp = (method, params = {}, timeout = timeoutMs) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const to = setTimeout(() => {
        if (pending.has(id)) {
          pending.delete(id);
          reject(Object.assign(new Error(`CDP 无响应（${timeout}ms）: ${method} —— 页面可能已挂死`), { hung: true, method }));
        }
      }, timeout);
      pending.set(id, (msg) => { clearTimeout(to); resolve(msg); });
      try { ws.send(JSON.stringify({ id, method, params })); } catch (e) {
        clearTimeout(to); pending.delete(id); reject(e);
      }
    });

  // 必须开域（第十二轮实测补上）：`Page.javascriptDialogOpening` 是 **Page 域事件**，
  // 不 `Page.enable` 就收不到 —— 那样下面的「自动应答」是**静默失效**的：对话框照弹、
  // 无人应答、渲染进程停在等应答态，下一次 `Runtime.evaluate` 直接撞 20s 超时（实测形态：
  // 脚本前一步还好好的，某一步「脏页 → 导航」之后突然整片命令超时）。
  // 域状态是**连接级**的：同一浏览器上另一条连接 enable 过，这条连接却收不到事件，
  // 于是自动应答时灵时不灵 —— 故在 connect() 里无条件打开。
  // `Runtime.enable` 顺带开，让 `Runtime.exceptionThrown` 诊断事件也稳定上报。
  // 用带超时的 send 而不是 cdp()：受限 target 上这两个域可能不支持，不能让 connect 失败。
  const enableDomainOn = (wsOf, name) => Promise.race([
    new Promise((res) => { const id = ++seq; pending.set(id, (msg) => res(msg)); try { wsOf().send(JSON.stringify({ id, method: name })); } catch { res(null); } }),
    sleep(3000).then(() => null),
  ]).catch(() => null);
  const enableDomain = (name) => enableDomainOn(() => ws, name);
  await enableDomain("Page.enable");
  await enableDomain("Runtime.enable");

  const Eval = async (expr, timeout) => {
    const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout);
    if (r.result?.exceptionDetails) {
      throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
    }
    return r.result?.result?.value;
  };

  const waitFor = async (expr, ms = 10000) => {
    for (let i = 0; i < ms / 200; i++) {
      try { if (await Eval(expr)) return true; } catch {}
      await sleep(200);
    }
    return false;
  };

  // 就绪判据：新文档 + 关键节点在场（脚本可传自己的表达式）
  const ready = async (expr, ms = 20000) =>
    waitFor(expr || `document.readyState === 'complete' && !!document.getElementById('tab-code')`, ms);

  // 跟随标签页（旁听用）：脚本自己 rebuildTab() 会关掉本连接所在的 target，旧连接就此哑掉。
  // 第十三轮实测形态：批跑器旁听连接收到的事件数恒为 0（脚本换标签页后事件全跑到新 target 上），
  // 于是「自动落盘事件序列」落的是空序列。watchTargets=true 时改挂到最新 page target。
  // 已知限制（实测）：改挂是 300ms 级轮询，**改挂之前**发生的事件收不到 ——
  // 若脚本一换标签页就弹对话框，那条 `Page.javascriptDialogOpening` 会漏（异常与导航事件
  // 不受影响，它们在脚本中后段持续产生）。要一条不漏，得让脚本复用批跑器的标签页，见 runner
  // 的 `--target=` 约定。
  let currentTarget = t;
  let pingTimer = null;
  let closed = false;                        // close() 之后不再改挂
  let failedSwitches = 0;
  knownTargetIds.add(t.id);
  const switchTarget = async (nt) => {
    const old = ws;
    let nws;
    try {
      nws = new WebSocket(nt.webSocketDebuggerUrl);
      await new Promise((res, rej) => { nws.onopen = res; nws.onerror = () => rej(new Error("CDP ws error(跟随)")); });
    } catch (e) {
      // 连接失败只作废这一条，不能把调用方（批跑器）拖崩：监听是旁路，永远不该致命
      try { nws && nws.close(); } catch {}
      failedSwitches++;
      throw e;
    }
    try { old.onmessage = null; old.onclose = null; old.onerror = null; old.close(); } catch {}
    ws = nws; currentTarget = nt;
    failedSwitches = 0;
    ws.onclose = () => { try { onTargetChange && onTargetChange(null); } catch {} };
    ws.onmessage = onMessage;
    await enableDomainOn(() => nws, "Page.enable");
    await enableDomainOn(() => nws, "Runtime.enable");
    try { onTargetChange && onTargetChange(nt); } catch {}
  };
  const findReplacement = async () => {
    const list = await listTargets(port);
    if (!Array.isArray(list)) return null;
    const pages = list.filter((x) => x.type === "page" && String(x.url).startsWith(pageUrl));
    // 优先挑「上次清点时还不存在」的页面（= 刚被脚本重建出来的那个）。
    // 第十三轮实测教训：若只挑「URL 对得上的任意页面」，会挑到现场残留的孤儿标签页
    // （诊断脚本留下的旧页），监听就此挂在一个与脚本无关的页上 —— 整批事件数恒为 0。
    const fresh = pages.filter((x) => x.id !== currentTarget.id && !knownTargetIds.has(x.id));
    if (fresh.length) return fresh[0];
    const others = pages.filter((x) => x.id !== currentTarget.id);
    return others[0] || null;
  };
  // 已知 target 集合：每次轮询都刷新，用于识别「新出现」的页面
  const refreshKnown = async () => {
    const list = await listTargets(port);
    knownTargetIds = new Set((Array.isArray(list) ? list : []).filter((x) => x.type === "page").map((x) => x.id));
  };
  if (watchTargets) {
    await refreshKnown();
    pingTimer = setInterval(async () => {
      if (switching || closed || failedSwitches >= 3) return;   // 连续失败 3 次就放弃跟随（保住调用方）
      switching = true;
      try {
        const list = await listTargets(port);
        if (Array.isArray(list) && !list.some((x) => x.id === currentTarget.id)) {
          // 等目标稳定再挂：目标正在被反复替换时，早挂会挂到一个马上又被关掉的标签页上
          const first = await findReplacement();
          await sleep(400);
          const second = await findReplacement();
          const nt = second && (!first || second.id === first.id) ? second : first;
          if (nt) await switchTarget(nt);
        }
        await refreshKnown();
      } catch {} finally { switching = false; }
    }, 300);
    if (pingTimer.unref) pingTimer.unref();
  }

  return {
    get ws() { return ws; },
    get target() { return currentTarget; },
    cdp, Eval, waitFor, ready, events,
    get dialogsAccepted() { return dialogsAccepted; },
    close: () => { closed = true; if (pingTimer) clearInterval(pingTimer); try { ws.close(); } catch {} },
  };
}

// ensureReady：连上 + 就绪（常用组合）
export async function ensureReady({ port, pageUrl = DEFAULT_PAGE_URL, expr, timeoutMs = 20000, waitMs = 20000 } = {}) {
  const c = await connect({ port, pageUrl, timeoutMs });
  const ok = await c.ready(expr, waitMs);
  if (!ok) { c.close(); throw new Error("页面未就绪"); }
  return c;
}

// ---------------------------------------------------------------------------
// 判定与归拢（工单 batch-runner-self-heal/01）
//
// 分工：**「什么算绿」的口径只在本文件定义一次**，批跑器（cdp-smoke-run.mjs）只调用，
// 不自己写第二份。判定全部是纯函数 —— 输入一次「支次记录」，输出判定 / 是否复跑 / 可读事件序列，
// 因此可以用 `node --test` 直接单测，不必起 Chrome。
// ---------------------------------------------------------------------------

// 传输层/挂死类信号：冒烟脚本的约定是「这类异常 → exit 2 + TRANSPORT 前缀」
// （见 code-editor-refine/14）；其余几条是脚本与批跑器自己的挂死措辞。
export const TRANSPORT_SIGNAL_RE = /TRANSPORT|CDP 无响应|页面可能已挂死|页面未就绪|CDP 不可达/;

// classifyAttempt：一次支次的判定。rec 形如
//   { exit, timedOut, pageUnresponsive, out }        — 批跑器给的原始观测
//   out = 子进程 stdout+stderr 合并文本（用于识别挂死/传输层信号）
// 返回 { exitCode, timedOut, hung, pass, reasons }。
// 注意 exitCode 单独不足以判绿：冒烟脚本会刻意用「非 0 退出 + 无 FAIL 行」表示传输层问题，
// 也可能出现「exit 0 但整片命令超时」的现场劣化 —— 故挂死/传输层信号优先于退出码判定。
export function classifyAttempt(rec = {}) {
  const exitCode = typeof rec.exit === "number" ? rec.exit : null;
  const out = String(rec.out ?? rec.tail ?? "");
  const timedOut = !!rec.timedOut;
  const hangSignal = TRANSPORT_SIGNAL_RE.test(out);
  const hung = timedOut || (hangSignal && !!rec.pageUnresponsive);
  const reasons = [];
  if (timedOut) reasons.push("脚本超时被杀");
  if (hangSignal) reasons.push(`传输层/挂死信号${rec.pageUnresponsive ? "（页面确已无响应）" : "（页面仍可应答，未定性为挂死）"}`);
  if (exitCode !== 0 && exitCode !== null) reasons.push(`退出码 ${exitCode}`);
  if (hung) reasons.push("判定：挂死");
  return { exitCode, timedOut, hung, pass: !hung && exitCode === 0, reasons };
}

// runVerdict：由「首次 + 复跑」两次支次判定终局。
//   pass  两次都绿
//   flake 首红复绿（偶发）—— **不算失败**
//   hang  任一次是挂死（挂死无法用「再跑一次」洗掉，优先于 fail 报告）
//   fail  最后一次仍红
export function runVerdict(first = {}, retry = null) {
  const a = first.pass !== undefined ? first : classifyAttempt(first);
  const b = retry ? (retry.pass !== undefined ? retry : classifyAttempt(retry)) : null;
  const attempts = b ? [a, b] : [a];
  const conclusive = b || a;
  let verdict;
  if (attempts.some((x) => x.hung)) verdict = "hang";
  else if (a.pass) verdict = "pass";          // 首跑即绿 = 绿（复跑只是留痕，不改变判定）
  else if (conclusive.pass) verdict = "flake";
  else verdict = "fail";
  return {
    verdict,
    flake: verdict === "flake",
    attempts,
    firstPass: a.pass,
    retried: !!b,
    reasons: attempts.flatMap((x) => x.reasons || []),
  };
}

// retryDecision：是否复跑这一支。口径（保守）：**只有非绿才复跑**，且最多一次。
//   retry = 允许的复跑次数（默认 1，0 = 永不复跑，用于对照复现）
export function retryDecision(a, { retry = 1, attemptIndex = 1 } = {}) {
  const first = a && a.pass !== undefined ? a : classifyAttempt(a);
  if (first.pass) return { retry: false, reason: "首跑已绿" };
  if (attemptIndex > retry) return { retry: false, reason: `复跑次数用尽（--retry=${retry}）` };
  if (retry <= 0) return { retry: false, reason: "--retry=0：按单次判定，不自动复跑" };
  return { retry: true, reason: first.hung ? "首跑挂死，复跑一次确认" : "首跑红，复跑一次定性" };
}

// 事件分桶：关键事件逐条保留，噪声折叠成计数，与判定无关的中间事件只计数。
const EVENT_BUCKETS = [
  [/^Runtime\.exceptionThrown$/, "exception"],
  [/^Page\.javascriptDialogOpening$/, "dialog"],
  [/^Page\.(frameNavigated|frameStartedNavigating|frameStoppedLoading|loadEventFired|domContentEventFired)$/, "navigation"],
  [/^Log\.entryAdded$/, "log"],
  [/^Page\.javascriptDialogClosed$/, "dialogClosed"],
  [/^Runtime\.executionContext/, "contextNoise"],
  [/^Network\./, "networkNoise"],
];
const BUCKET_LABEL = {
  exception: "异常", dialog: "对话框", dialogClosed: "对话框关闭",
  navigation: "导航", log: "日志", contextNoise: "上下文噪声", networkNoise: "网络噪声", other: "其他",
};

// digestEvents：把 CDP 事件数组归拢成「人可读 + 机可查」的结构。
//   t0Ms 该支次的起点时刻（取相对时间）；events 为 connect() 事件缓冲的切片（{t, method, params}）。
// 保留：异常（带文本）/ 对话框（带类型）/ 导航 / 日志 / 对话框关闭；
// 折叠：上下文、网络等噪声只留计数；未知事件计数并点名（最多 10 个）。
export function digestEvents(events = [], { t0Ms = 0 } = {}) {
  const kept = [];
  const counts = {};
  const unknown = new Map();
  for (const ev of events) {
    const method = ev && ev.method ? ev.method : "(unknown)";
    let bucket = "other";
    for (const [re, name] of EVENT_BUCKETS) if (re.test(method)) { bucket = name; break; }
    counts[bucket] = (counts[bucket] || 0) + 1;
    if (bucket === "contextNoise" || bucket === "networkNoise") continue;
    if (bucket === "other") {
      unknown.set(method, (unknown.get(method) || 0) + 1);
      continue;
    }
    const dtMs = typeof ev.t === "number" && t0Ms ? ev.t - t0Ms : null;
    const item = { dtMs, method };
    if (bucket === "exception") {
      const d = ev.params?.exceptionDetails;
      item.text = String(d?.exception?.description ?? d?.text ?? "").split("\n")[0].slice(0, 300);
    }
    if (bucket === "dialog") item.dialogType = ev.params?.type ?? null;
    if (bucket === "log") item.text = String(ev.params?.entry?.text ?? "").slice(0, 200);
    kept.push(item);
  }
  const folded = Object.entries(counts)
    .filter(([k]) => k.endsWith("Noise"))
    .map(([k, n]) => `${BUCKET_LABEL[k]} ×${n}`);
  const unknownList = [...unknown.entries()].slice(0, 10).map(([m, n]) => `${m} ×${n}`);
  return {
    total: events.length,
    kept,
    counts,
    folded,
    unknown: unknownList,
    summary: kept.length
      ? kept.map((k) => `${k.dtMs == null ? "?" : `+${k.dtMs}ms`} ${k.method}`).join(" → ")
      : "（无关键事件）",
  };
}

// diagFileName：落盘文件名（含脚本短名 + 轮次 + 时间戳），便于在记录与现场之间来回对照。
export function diagFileName(script, round = 1, { stamp = Date.now(), ext = "json" } = {}) {
  const short = String(script)
    .replace(/^\.scratch\//, "")
    .replace(/\.mjs$/, "")
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return `${stamp}-r${round}-${short || "script"}.${ext}`;
}

// renderDiagText：事件序列的纯文本呈现（落盘文件名同名 .txt），便于直接打开看现场。
export function renderDiagText({ script, round, attempt, ts, digest, attemptRecord = {} } = {}) {
  const lines = [
    `# 非绿支次现场 —— ${script}`,
    `轮次 r${round} ｜ 支次 attempt=${attempt} ｜ 落盘 ${new Date(ts || Date.now()).toISOString()}`,
    `结果：verdict=${attemptRecord.verdict ?? "?"} exit=${attemptRecord.exit ?? "?"} timedOut=${!!attemptRecord.timedOut} hung=${!!attemptRecord.hung}`,
    `信号：${(attemptRecord.reasons || []).join("；") || "（无）"}`,
    attemptRecord.tail ? `输出尾行：${attemptRecord.tail}` : null,
    "",
    `## 关键事件序列（${digest?.kept?.length ?? 0} 条 / 共收 ${digest?.total ?? 0} 个 CDP 事件）`,
  ].filter((x) => x !== null);
  if (!digest?.kept?.length) lines.push("（该支次没有收到关键事件：脚本可能未连 CDP，或挂在传输层）");
  for (const k of digest?.kept || []) {
    const when = k.dtMs == null ? "?" : `+${k.dtMs}ms`;
    lines.push(`- ${when} ${k.method}${k.dialogType ? ` type=${k.dialogType}` : ""}${k.text ? ` :: ${k.text}` : ""}`);
  }
  if (digest?.folded?.length) lines.push("", `折叠计数：${digest.folded.join(" / ")}`);
  if (digest?.unknown?.length) lines.push(`未归类事件：${digest.unknown.join(" / ")}`);
  lines.push("", `一行摘要：${digest?.summary ?? ""}`);
  if (attemptRecord.postMortem) {
    const pm = attemptRecord.postMortem;
    lines.push("",
      `## 支次后反射（非实录；脚本自己换过标签页时用它兜底）`,
      pm.reattachedTo ? `追挂到 target：${pm.reattachedTo}` : (pm.reattachError ? `追挂失败：${pm.reattachError}` : "监听所在页仍存活，未追挂"),
      pm.snapshot ? `现场快照：${pm.snapshot}` : null);
  }
  return lines.filter((x) => x !== null).join("\n") + "\n";
}
