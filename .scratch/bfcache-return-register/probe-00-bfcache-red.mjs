// probe-00-bfcache-red.mjs —— bfcache 后退回来「没人补登记 ⇒ 服务已退出 ⇒ 死页面」的真浏览器红证。
//
// ## 这条探针要证什么
//
// 启动器模式（`FIRSTEP_LAUNCHER=1`，用户双击 start-app.vbs 的那条路）下：
//   · `src/contest_generator/static/js/app.js:131-135` 的 `pagehide` 监听器**不判 `event.persisted`**，
//     无条件 `navigator.sendBeacon("/api/tabs/bye", {tab_id, epoch})`；
//   · 页面被放进 **bfcache** 时同样触发 `pagehide`（`persisted === true`）⇒「导航离开」被当成「关闭」；
//   · 服务端（`webapp.py:517-527` unregister → `:565-583 _schedule_exit_if_idle`）见注册表空就布防，
//     `_EXIT_GRACE`（1.5s）后 `os._exit(0)`；
//   · bfcache 恢复的文档**不执行任何脚本**（`static/index.html` head 的内联登记不重跑），
//     全仓**没有 `pageshow` 监听** ⇒ 没人补登记 ⇒ 服务已退出 ⇒ 页面所有请求 `ERR_CONNECTION_REFUSED`。
//
// 红证 = 「导航走 → 宽限内后退回来 → 没看到新的 `POST /api/tabs/register` → 后端 exitCode=0
// → 页面上真 fetch 报 FETCH_FAIL」。**bfcache 是这条红证的必要条件**：若那一跳变成整页重载，
// 内联登记会重跑、服务就活着，缺陷在这一跳上根本不成立。
//
// ## ⚠ 为什么必须 `ignoreDefaultArgs`
//
// playwright **默认**给 chromium 传 `--disable-back-forward-cache`（实测：
// `node_modules/playwright-core/lib/coreBundle.js:34858` 的默认 args 列表里有这一条），
// 所以裸 `chromium.launch()` 下 bfcache **根本不会发生**——探针只会得到「整页重载」的读数。
// 要出 bfcache 必须 `ignoreDefaultArgs: ["--disable-back-forward-cache"]`；必要时再叠加
// `channel: "chromium"`（完整 chromium 而非 headless shell）或 `headless: false`。
// 哪一种真能出、哪一种出不来，四种模式各跑一遍，如实记账（见 `--mode`）。
//
// ## 依赖
//
//   · `tests/browser/server.mjs`（**相对本文件** `../../tests/browser/server.mjs`）——起真后端 +
//     开启动器模式（`startServer({ launcher: true })`），端口由内核分配（不写死）。
//     ⚠ 该夹具的 `REPO_ROOT` 由**它自己的 URL** 推出（`server.mjs:16`），所以脚本在哪个树里，
//     服务的就是哪个代的 `app.js` / `index.html` —— 这正是本探针要**在冻结的 base worktree 上跑**的原因。
//   · `playwright`（版本进读数）+ `%LOCALAPPDATA%\ms-playwright` 里已装的 chromium。
//   · 后端：`python -m contest_generator.webapp`，`PYTHONPATH=src`（夹具自己设）。
//
// ## 为什么第一次要在 base worktree 上跑
//
// 主树马上会被改（实现「补 `pageshow` 补登记」那条修法）。红证必须是**修前**那一代的读数，
// 所以配方是：`git worktree add .scratch/bfcache-return-register/base-worktree <base-sha>` →
// 给这个 worktree 建 `node_modules` junction 指回主树 → 把本文件拷进 worktree 的
// `.scratch/bfcache-return-register/` → **在 worktree 根作为 cwd** 跑它，输出 `--out-dir` 指回主树。
// 跑完 `git worktree remove --force`（worktree 留在 `.scratch/` 下会让 `tests/test_ps1_encoding.py`
// 扫到第三方 .ps1 报红）。
//
// ## 用法
//
//   node <本文件> --mode=default|bfcache|bfcache-channel|bfcache-headed|all
//   node <本文件> --mode=bfcache --out-dir=<主树 .scratch/bfcache-return-register>
//   node <本文件> --mode=bfcache --extra-args=--enable-features=BackForwardCache   # 临时探索用
//   node <本文件> --mode=all --repeat=2        # 整张矩阵连跑两轮（红证不该只跑一次）
//
// **同一支探针可复跑两次做前后对读**：修前在 base worktree 上跑 = 红（复现成立），
// 修后在主树跑 = 绿（`healed`：恢复时补登记，服务活着）；两份读数用 `--out-dir` 分开落盘，别互相覆盖。
//
// 输出：`probe-00-bfcache-red.txt`（人读，UTF-8，**由 node 自己 writeFileSync 写**——别用
// PowerShell 的 `>` / `Tee-Object`，那是 UTF-16LE）与 `probe-00-bfcache-red.json`（机器读）。
import { readFileSync, statSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium } from "playwright";
import { startServer } from "../../tests/browser/server.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------------------
// 参数
// ---------------------------------------------------------------------------
const argv = process.argv.slice(2);
const argOf = (name, dflt = null) => {
  const hit = argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : dflt;
};
const MODE_ARG = argOf("mode", "all");
const SELF_DIR = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(argOf("out-dir", SELF_DIR));
const EXTRA_ARGS = argOf("extra-args", "").split(",").map((s) => s.trim()).filter(Boolean);
// 整张矩阵连跑几轮（红证不该只跑一次；JSON 收全部轮次，txt 详列第 1 轮 + 逐轮对照表）
const REPEAT = Math.max(1, Number(argOf("repeat", "1")) || 1);

// ---------------------------------------------------------------------------
// 四种 launch 配置（矩阵的每一格都跑一遍，哪种出得来 bfcache 由读数说话）
// ---------------------------------------------------------------------------
const MODES = {
  default: {
    label: "playwright 默认 launch（默认 args **含** --disable-back-forward-cache）",
    launch: { headless: true },
  },
  bfcache: {
    label: "去掉 --disable-back-forward-cache（默认 headless = chromium_headless_shell）",
    launch: { headless: true, ignoreDefaultArgs: ["--disable-back-forward-cache"] },
  },
  "bfcache-channel": {
    label: "去掉该 flag + channel=chromium（完整 chromium，非 headless shell）",
    launch: {
      headless: true,
      channel: "chromium",
      ignoreDefaultArgs: ["--disable-back-forward-cache"],
    },
  },
  "bfcache-headed": {
    label: "去掉该 flag + headless:false（有头真窗口）",
    launch: { headless: false, ignoreDefaultArgs: ["--disable-back-forward-cache"] },
  },
};

const MODE_ORDER = Object.keys(MODES);
const MODES_TO_RUN = MODE_ARG === "all" ? MODE_ORDER : [MODE_ARG];
for (const m of MODES_TO_RUN) {
  if (!MODES[m]) throw new Error(`未知 --mode=${m}（可选：${MODE_ORDER.join(" / ")} / all）`);
}

// ---------------------------------------------------------------------------
// 仓库根：本探针所在树（`--out-dir` 与它无关）。base sha 自解析（worktree 的 `.git`
// 是**文件**不是目录，所以要走 `gitdir:` 那条路，否则在 worktree 上会读不到 sha）
// ---------------------------------------------------------------------------
const REPO_ROOT = path.resolve(SELF_DIR, "../..");

function readGitHead(root) {
  const dotGit = path.join(root, ".git");
  let gitDir = dotGit;
  try {
    if (statSync(dotGit).isFile()) {
      const m = /^gitdir:\s*(.+)$/m.exec(readFileSync(dotGit, "utf8"));
      if (m) gitDir = path.resolve(root, m[1].trim());
    }
  } catch { /* 交给下面统一兜底 */ }
  try {
    const head = readFileSync(path.join(gitDir, "HEAD"), "utf8").trim();
    if (!head.startsWith("ref:")) return head;              // detached（worktree 就是这条）
    const ref = head.slice(4).trim();
    try { return readFileSync(path.join(gitDir, ref), "utf8").trim(); } catch { /* packed 兜底 */ }
    const packed = readFileSync(path.join(gitDir, "packed-refs"), "utf8");
    const esc = ref.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const hit = new RegExp(`^${esc}\\s+([0-9a-f]{40})`, "m").exec(packed);
    return hit ? hit[1] : `(HEAD 指向 ${ref}，但读不到 sha)`;
  } catch { return "(读不到 git HEAD)"; }
}

// ---------------------------------------------------------------------------
// 宽限窗口**从产品源码里抠**，不手抄（先例 `tests/browser/launcher-reload.spec.mjs:56-60`：
// 抄一份 1500 在产品改值以后会让读数静默失真）
// ---------------------------------------------------------------------------
const WEBAPP_PY = path.join(REPO_ROOT, "src", "contest_generator", "webapp.py");
const graceMatch = /^_EXIT_GRACE\s*=\s*([0-9.]+)/m.exec(readFileSync(WEBAPP_PY, "utf8"));
if (!graceMatch) throw new Error("webapp.py 里找不到 `_EXIT_GRACE = <数字>`");
const GRACE_MS = Number(graceMatch[1]) * 1000;

const PW_VERSION = JSON.parse(readFileSync(
  path.join(REPO_ROOT, "node_modules", "playwright", "package.json"), "utf8")).version;

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------
/** 每个 pw 动作都带显式超时；再给整轮一个总闸——探针**不许挂着不动**。 */
function withTimeout(promise, ms, label) {
  let timer = null;
  return Promise.race([
    promise,
    new Promise((_, rej) => { timer = setTimeout(() => rej(new Error(`超时：${label}（${ms}ms）`)), ms); }),
  ]).finally(() => { if (timer) clearTimeout(timer); });
}

/** 错误记成可读的一行（goBack 可能抛，且抛什么本身就是读数）。 */
const errLine = (e) => (e && e.name ? `${e.name}: ${e.message}` : String(e));
const oneLine = (s) => String(s).replace(/\s*\n\s*/g, " ⏎ ");

/** 服务端日志尾段（异常时一起打，不然只剩一句 playwright 超时）。 */
const logTail = (server, lines = 10) =>
  server.log().split("\n").slice(-lines).join("\n");

/** 日志里与标签会话有关的行（服务端日志每人一个 /js 模块一行，全量尾段读不出东西）。 */
const apiLines = (seg) => seg.split("\n")
  .filter((s) => s.includes("/api/tabs/") || s.includes("[fixture]") || s.includes("ERROR"))
  .join("\n") || "（这一轮没有任何 /api/tabs/ 行）";

/** 等页面可用：平台卡渲染出来 ⟺ 装载根启动区跑过（判据照夹具先例）。 */
async function waitReady(page, server, timeoutMs = 90000) {
  try {
    await page.waitForFunction(
      () => document.querySelectorAll("#platforms .platform-card").length > 0,
      undefined, { timeout: timeoutMs });
  } catch (e) {
    throw new Error(`等页面可用超时（${timeoutMs}ms）：${e.message}`
      + `\n（服务端日志尾段：\n${logTail(server)}\n）`);
  }
}

/** 等日志里出现某个字样 → 观测到的时刻（Date.now()）；超时返回 null。 */
async function waitLog(server, needle, fromIndex, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (server.log().slice(fromIndex).includes(needle)) return Date.now();
    await sleep(10);
  }
  return null;
}

/** 等后端进程真退出 → 观测时刻；超时返回 null。**可以提前启动**（与别的 await 并发），
 *  这样"离开 → 进程咽气"的耗时是量出来的，不是事后推断的。 */
async function exitObservedAt(server, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (server.proc.exitCode !== null) return Date.now();
    await sleep(25);
  }
  return null;
}

/** 在页面里读一组探针值；单点失败不影响其余（每一跳都可能把页面弄成不可评估状态）。 */
async function readPage(page, fn, label) {
  try {
    return await withTimeout(page.evaluate(fn), 15000, label);
  } catch (e) {
    return `EVAL_ERROR: ${errLine(e)}`;
  }
}

// ---------------------------------------------------------------------------
// 单组 launch 配置的完整一轮读数
// ---------------------------------------------------------------------------
async function runMode(modeName, runIndex = 1) {
  const mode = MODES[modeName];
  const launchOpts = { ...mode.launch };
  if (EXTRA_ARGS.length) launchOpts.args = [...(launchOpts.args || []), ...EXTRA_ARGS];
  const rec = {
    mode: modeName,
    runIndex,
    label: mode.label,
    launchOptions: launchOpts,
    ranAt: new Date().toISOString(),
    graceMs: GRACE_MS,
    steps: {},
  };

  let server = null;
  let browser = null;
  try {
    server = await startServer({ launcher: true });
    rec.server = { url: server.url, port: server.port, launcherMode: true };
    console.log(`[${modeName}] 夹具后端已起：${server.url}（启动器模式，宽限 ${GRACE_MS}ms）`);

    browser = await withTimeout(chromium.launch(launchOpts), 60000, "chromium.launch");
    rec.steps.launch = { ok: true, browserVersion: browser.version() };
    console.log(`[${modeName}] 浏览器已起：${browser.version()}`);

    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await withTimeout(
      page.goto(server.url + "/", { waitUntil: "domcontentloaded" }), 30000, "goto 首页");
    await waitReady(page, server, 90000);
    console.log(`[${modeName}] 页面可用`);

    // ① 装探针：pageshow 的 persisted 序列 + 文档身份 + 初始 epoch
    //    `__psAt` 记每次 pageshow 的 `performance.now()`：同一文档里它从 timeOrigin 起算，
    //    于是 `timeOrigin + performance.now()` = 恢复那一刻的墙钟 ⇒ 能**量出**"离开后多久回来的"，
    //    不必靠 goBack 何时返回去推断（bfcache 恢复时 playwright 的 goBack 根本不会返回，见下）。
    rec.steps.probeInstalled = await readPage(page, () => {
      window.__ps = [];
      window.__psAt = [];
      window.__docId = Math.random().toString(36).slice(2);
      window.addEventListener("pageshow", (e) => {
        window.__ps.push(e.persisted);
        window.__psAt.push(performance.now());
      });
      const nav = performance.getEntriesByType("navigation")[0];
      return {
        docId: window.__docId,
        timeOrigin: performance.timeOrigin,
        navType: nav ? nav.type : null,
      };
    }, "安装探针");

    // ② 标记 + 离开前状态
    const logMark = server.log().length;
    rec.steps.beforeLeave = {
      logLength: logMark,
      exitCode: server.proc.exitCode,
      doc: rec.steps.probeInstalled,
    };

    // ③ 真导航离开（产品会发 bye）
    const tLeave = Date.now();
    let leaveError = null;
    try {
      await withTimeout(page.goto("about:blank"), 30000, "goto about:blank");
    } catch (e) {
      leaveError = errLine(e);
    }
    // 退出计时**从这一刻开始跑**（与后面的 goBack 并发），这样"离开 → 咽气"是量出来的
    const exitPoll = exitObservedAt(server, GRACE_MS + 5000);

    // 判据前置：bye 必须**在后退之前**到达服务端，否则「注册表空 ⇒ 布防退出」这个前提不成立，
    // 这一轮读数不可用（本地 127.0.0.1 一般几十 ms；超时如实记，不掩饰）。
    const byeAt = await waitLog(server, "POST /api/tabs/bye", logMark, 300);
    rec.steps.leave = {
      error: leaveError,
      byeSeenBeforeBack: byeAt !== null,
      byeLatencyMs: byeAt === null ? null : byeAt - tLeave,
    };

    // ④ **尽快**后退回来（目标 ≤300ms；goBack 可能抛，抛什么记什么）
    const tBack0 = Date.now();
    let goBackError = null;
    let goBackResult = null;
    try {
      goBackResult = await withTimeout(page.goBack({ waitUntil: "domcontentloaded" }), 8000, "goBack");
    } catch (e) {
      goBackError = errLine(e);
    }
    const backElapsed = Date.now() - tBack0;
    rec.steps.goBack = {
      error: goBackError,
      returnedUrl: goBackResult ? goBackResult.url() : null,
      elapsedMs: backElapsed,
      sinceLeaveMs: tBack0 - tLeave,
    };
    console.log(`[${modeName}] 后退：${goBackError ? `抛了 ${goBackError}` : "成功"}`
      + `（耗时 ${backElapsed}ms，离开后 ${tBack0 - tLeave}ms 发起）`);

    // ⑤ 后退后的页面读数（bfcache 判据全在这里）
    rec.steps.afterBack = await readPage(page, () => {
      const navs = performance.getEntriesByType("navigation");
      const nav0 = navs[0];
      const navLast = navs[navs.length - 1];
      return {
        pageshowPersisted: window.__ps === undefined
          ? "NO_WINDOW___ps（整页重载 = 新文档，探针变量不存在）" : window.__ps,
        pageshowAt: window.__psAt === undefined ? null : window.__psAt,
        docId: window.__docId === undefined
          ? "NO_WINDOW___docId（整页重载 = 新文档）" : window.__docId,
        timeOrigin: performance.timeOrigin,
        navType0: nav0 ? nav0.type : null,
        navCount: navs.length,
        navTypeLast: navLast ? navLast.type : null,
        // activationStart 是 bfcache 恢复的规范判据之一（Page Lifecycle API）
        activationStart0: nav0 ? nav0.activationStart : null,
        activationStartLast: navLast ? navLast.activationStart : null,
        url: location.href,
      };
    }, "后退后读数");
    // 量出"离开后多久真的回到了本文档"（bfcache 恢复的墙钟时刻 − 离开时刻）
    {
      const ab = rec.steps.afterBack;
      if (ab && typeof ab === "object" && Array.isArray(ab.pageshowAt)
          && ab.pageshowAt.length && typeof ab.timeOrigin === "number") {
        ab.restoreElapsedMs = Math.round(
          (ab.timeOrigin + ab.pageshowAt[ab.pageshowAt.length - 1]) - tLeave);
        ab.withinGraceWindow = ab.restoreElapsedMs <= GRACE_MS;
      } else {
        ab.restoreElapsedMs = null;
        ab.withinGraceWindow = null;
      }
    }

    // ⑥ 让"整页重载那一跳"的 register 有机会落地（400ms 静默），再数服务端收到了什么
    await sleep(400);
    const seg = server.log().slice(logMark);
    rec.steps.afterBackLog = {
      newRegisterCount: (seg.match(/POST \/api\/tabs\/register/g) || []).length,
      newByeCount: (seg.match(/POST \/api\/tabs\/bye/g) || []).length,
      apiLines: apiLines(seg),
    };

    // ⑦ 等整个宽限窗口过去 + 2s，收退出计时
    const exitedAt = await exitPoll;
    rec.steps.afterGrace = {
      exitCode: server.proc.exitCode,
      exitTimestampMs: exitedAt === null ? null : exitedAt - tLeave,
      exitedWithinWindow: exitedAt !== null,
    };
    const tWait = Date.now();
    while (Date.now() - tWait < GRACE_MS + 2000 && server.proc.exitCode === null) await sleep(50);
    rec.steps.afterGrace.waitedExtraMs = Date.now() - tWait;
    rec.steps.afterGrace.exitCode = server.proc.exitCode;

    // ⑧ 页面上再做一次真请求：死在哪儿、报什么
    rec.steps.afterGrace.pageFetch = await readPage(page, () =>
      fetch("/api/health").then((r) => `HTTP_${r.status}`).catch((e) => `FETCH_FAIL:${e.name}`),
    "后退后真请求");
    rec.steps.afterGrace.reload = await (async () => {
      try {
        await withTimeout(page.reload({ waitUntil: "domcontentloaded" }), 15000, "reload");
        return "reload 成功";
      } catch (e) {
        return `RELOAD_FAIL: ${oneLine(errLine(e))}`;   // 折成一行（playwright 的 Call log 很长）
      }
    })();

    rec.steps.endLog = { exitCode: server.proc.exitCode, logLength: server.log().length };
  } catch (e) {
    rec.fatalError = errLine(e);
    rec.steps.fatalStack = String((e && e.stack) || "").split("\n").slice(0, 6).join(" | ");
    console.log(`[${modeName}] 本轮异常：${errLine(e)}`);
  } finally {
    try { if (browser) await browser.close(); } catch (e) { rec.steps.browserCloseError = errLine(e); }
    try { if (server) await server.stop(); } catch (e) { rec.steps.serverStopError = errLine(e); }
  }

  // -------------------------------------------------------------------------
  // 判定（判据写死在这里，不为了结论好看而改）
  // -------------------------------------------------------------------------
  const ab = rec.steps.afterBack;
  const ps = ab && typeof ab === "object" ? ab.pageshowPersisted : undefined;
  const bfcacheUsed = Array.isArray(ps) && ps.includes(true);
  const fullReload = typeof ps === "string" && ps.startsWith("NO_WINDOW");
  const newRegisters = rec.steps.afterBackLog ? rec.steps.afterBackLog.newRegisterCount : null;
  const exitCode = rec.steps.afterGrace ? rec.steps.afterGrace.exitCode : null;
  const fetchResult = rec.steps.afterGrace ? rec.steps.afterGrace.pageFetch : null;
  const byeBefore = rec.steps.leave ? rec.steps.leave.byeSeenBeforeBack : null;

  rec.verdict = {
    readingsUsable: !rec.fatalError,
    bfcacheUsed,
    fullReload,
    persistedSequence: ps,
    restoreElapsedMs: ab && typeof ab === "object" ? ab.restoreElapsedMs : null,
    returnWithinGraceWindow: ab && typeof ab === "object" ? ab.withinGraceWindow : null,
    newRegistersAfterBack: newRegisters,
    exitCodeAfterGrace: exitCode,
    pageFetchAfterGrace: fetchResult,
    byeSeenBeforeBack: byeBefore,
    reproduced: null,
    healed: false,
    text: "",
  };
  if (rec.fatalError) {
    rec.verdict.text = `本组配置**跑不出可用读数**（${rec.fatalError}）——不当作「没缺陷」。`;
  } else if (fullReload) {
    rec.verdict.reproduced = false;
    rec.verdict.text = "本组配置下**这一跳是整页重载**（探针变量消失 = 新文档，内联登记会重跑）"
      + `⇒ **复现不成立**（新 register ${newRegisters} 次、退出码 ${exitCode}）`
      + "：缺陷需要一个 bfcache 恢复的文档才谈得上。";
  } else if (!bfcacheUsed) {
    rec.verdict.reproduced = false;
    rec.verdict.text = `本组配置下 pageshow.persisted 序列 = ${JSON.stringify(ps)}（没有 true）`
      + `⇒ **这一跳没走 bfcache ⇒ 复现不成立**（新 register ${newRegisters} 次、退出码 ${exitCode}）。`;
  } else if (newRegisters === 0 && exitCode === 0 && String(fetchResult).startsWith("FETCH_FAIL")) {
    rec.verdict.reproduced = true;
    rec.verdict.text = "**复现成立**：走了 bfcache（persisted=true）→ 后退后**没有**新的 "
      + "`POST /api/tabs/register` → 宽限到点后端 exitCode=0（产品把自己关了）→ "
      + `页面上真请求 ${fetchResult} = 死页面。`;
  } else if (newRegisters > 0) {
    // 补登记发生了 ⇒ 这一跳不再是缺陷。分两种：服务活着且页面能用 = 已修（绿）；
    // 服务仍然退了 = 另有原因（比如补登记太晚），如实标红让人去查。
    const healed = exitCode === null && String(fetchResult).startsWith("HTTP_");
    rec.verdict.reproduced = false;
    rec.verdict.healed = healed;
    rec.verdict.text = healed
      ? `**已修（绿）**：走了 bfcache（persisted=true）→ 恢复时**补登记 ${newRegisters} 次** `
        + `→ 后端没退（exitCode=${exitCode}）、页面真请求 ${fetchResult} ⇒ 这一跳被补登记救回。`
      : `走了 bfcache、后退后也收到 ${newRegisters} 次新 register，但服务没能保住 `
        + `（退出码 ${exitCode}、页面请求 ${fetchResult}）⇒ **仍需查**（补登记是不是太晚 / 没生效）。`;
  } else {
    rec.verdict.reproduced = false;
    rec.verdict.text = `走了 bfcache、也没有新 register，但后端没在宽限后退出`
      + `（退出码 ${exitCode}、页面请求 ${fetchResult}）⇒ **复现不成立**（另有原因，需查）。`;
  }
  return rec;
}

// ---------------------------------------------------------------------------
// 跑 + 落盘
// ---------------------------------------------------------------------------
const base = {
  probe: "probe-00-bfcache-red",
  baseSha: argOf("base-sha", null) || readGitHead(REPO_ROOT),
  repoRootUsed: REPO_ROOT,
  runAt: new Date().toISOString(),
  nodeVersion: process.version,
  playwrightVersion: PW_VERSION,
  exitGraceMs: GRACE_MS,
  extraArgs: EXTRA_ARGS,
  modes: MODES_TO_RUN,
  repeat: REPEAT,
  results: [],
};

console.log(`探针启动：base=${base.baseSha} node=${base.nodeVersion} playwright=${base.playwrightVersion}`);
console.log(`仓库根（= 服务的那一代代码）= ${REPO_ROOT}`);
console.log(`待跑配置：${MODES_TO_RUN.join(", ")}（共 ${REPEAT} 轮）\n`);

for (let run = 1; run <= REPEAT; run++) {
  for (const m of MODES_TO_RUN) {
    const rec = await runMode(m, run);
    base.results.push(rec);
    console.log(`[第${run}轮 ${m}] 判定：${rec.verdict.text}\n`);
    // **每跑完一组就落盘一次**：中途崩了也留得下已得的读数
    writeFileSync(path.join(OUT_DIR, "probe-00-bfcache-red.json"),
      JSON.stringify(base, null, 2), "utf8");
  }
}

// ---- JSON ----
const jsonPath = path.join(OUT_DIR, "probe-00-bfcache-red.json");
writeFileSync(jsonPath, JSON.stringify(base, null, 2), "utf8");

// ---- 人读 txt ----
const L = [];
const line = (s = "") => L.push(s);
line("probe-00-bfcache-red —— bfcache 后退回来「没人补登记 ⇒ 服务已退出 ⇒ 死页面」真浏览器红证");
line("=".repeat(100));
line(`base sha         : ${base.baseSha}`);
line(`跑的时刻         : ${base.runAt}（本机时区 ${Intl.DateTimeFormat().resolvedOptions().timeZone}）`);
line(`Node 版本        : ${base.nodeVersion}`);
line(`playwright 版本  : ${base.playwrightVersion}`);
line(`_EXIT_GRACE      : ${base.exitGraceMs}ms（从 src/contest_generator/webapp.py 抠出，非手抄）`);
line(`服务的那一代代码 : ${base.repoRootUsed}（= 本探针所在树；夹具 REPO_ROOT 由它自己的 URL 推出）`);
line(`跑过的配置       : ${base.modes.join(", ")}（共 ${base.repeat} 轮）`);
if (EXTRA_ARGS.length) line(`额外 launch args : ${EXTRA_ARGS.join(" ")}`);
line("");
line("判据（写死在探针里，不为了结论好看而改）：");
line("  · bfcache 走了吗 = pageshow 的 persisted 序列里有 true（且 window 探针变量还在 = 还是同一个文档）");
line("  · 复现成立 = 走了 bfcache + 后退后**零**新 register + 宽限后 exitCode=0 + 页面真请求 FETCH_FAIL");
line("  · 整页重载（window.__ps 变 NO_WINDOW…）= 这一跳**根本没走 bfcache** ⇒ 复现不成立，如实记");
line("  · ⚠ bfcache 恢复时 `page.goBack()` **不会返回**（playwright 等不到它认得的导航事件，8 秒超时抛错）"
  + "——读数照旧有效：页面侧判据是 pageshow.persisted，服务端判据是日志与退出码");
line("");

for (const r of base.results) {
  if (r.runIndex !== 1) continue;           // 详列第 1 轮；其余轮次进下面的对照表
  const ab = r.steps.afterBack;
  line("-".repeat(100));
  line(`【配置 ${r.mode}】${r.label}`);
  line(`  launchOptions       : ${JSON.stringify(r.launchOptions)}`);
  line(`  夹具后端            : ${r.server ? r.server.url : "(没起来)"}`);
  if (r.steps.launch) line(`  浏览器              : ${r.steps.launch.browserVersion}`);
  const inst = r.steps.probeInstalled;
  if (inst && typeof inst === "object") {
    line(`  离开前（本文档）    : docId=${inst.docId} timeOrigin=${inst.timeOrigin} navType=${inst.navType}`);
  } else {
    line(`  离开前（本文档）    : ${JSON.stringify(inst)}`);
  }
  const lv = r.steps.leave || {};
  line(`  离开（goto blank）  : ${lv.error ? `抛错 ${lv.error}` : "成功"}`
    + `｜bye 在后退前到达服务端 = ${lv.byeSeenBeforeBack}（离开后 ${lv.byeLatencyMs}ms 看到）`);
  const gb = r.steps.goBack || {};
  line(`  goBack              : ${gb.error ? `抛错 ${oneLine(gb.error)}` : `成功（URL=${gb.returnedUrl}）`}`
    + `｜耗时 ${gb.elapsedMs}ms｜离开后 ${gb.sinceLeaveMs}ms 发起`);
  if (ab && typeof ab === "object") {
    line(`  ★ pageshow.persisted: ${JSON.stringify(ab.pageshowPersisted)}`);
    line(`  ★ 文档身份          : docId=${ab.docId} timeOrigin=${ab.timeOrigin}`);
    line(`  ★ navigation.type   : 共 ${ab.navCount} 条｜[0]=${ab.navType0}（activationStart=${ab.activationStart0}）`
      + `  last=${ab.navTypeLast}（activationStart=${ab.activationStartLast}）`);
    line(`  ★ 回到本文档的时刻  : 离开后 ${ab.restoreElapsedMs}ms（宽限 ${GRACE_MS}ms 内 = ${ab.withinGraceWindow}）`
      + `｜URL=${ab.url}`);
  } else {
    line(`  ★ 后退后读数        : ${JSON.stringify(ab)}`);
  }
  const lg = r.steps.afterBackLog;
  if (lg) {
    line(`  ★ 后退后**新**register 次数: ${lg.newRegisterCount}（新 bye ${lg.newByeCount} 次）`);
    line(`  ── 这一段里的 /api/tabs/ 行 ──`);
    for (const s of String(lg.apiLines).split("\n")) line(`     ${s}`);
  }
  const ag = r.steps.afterGrace;
  if (ag) {
    line(`  ★ 后端退出          : exitCode=${ag.exitCode}｜观测到退出 = ${ag.exitedWithinWindow}`
      + `｜离开后 ${ag.exitTimestampMs}ms 咽气`);
    line(`  ★ 页面上真请求      : ${JSON.stringify(ag.pageFetch)}`);
    line(`  ★ 整页 reload       : ${ag.reload}`);
  }
  if (r.fatalError) line(`  ✗ 本轮异常          : ${r.fatalError}`);
  line(`  判定                : ${r.verdict.text}`);
  line("");
}

if (base.repeat > 1) {
  // 判据的短写：整页重载那一支的长句会把表挤歪
  const psShort = (v) => (typeof v === "string" && v.startsWith("NO_WINDOW")
    ? "NO_WINDOW(整页重载)" : JSON.stringify(v));
  line("=".repeat(100));
  line(`逐轮对照表（同一矩阵连跑 ${base.repeat} 轮：红证不该只跑一次）`);
  line("  · 「回到本文档」= pageshow 那一刻的墙钟 − 离开时刻；「宽限内」= 是否 ≤ _EXIT_GRACE"
    + "（这正对上工单的两种形态：① 宽限内回来 = 补登记救得回；② 晚于宽限回来 = 服务已退，任何补登记都救不回）");
  line(`  ${"轮".padEnd(4)}${"配置".padEnd(20)}${"persisted".padEnd(20)}${"回到本文档".padEnd(12)}`
    + `${"宽限内".padEnd(8)}${"新register".padEnd(12)}${"exitCode".padEnd(10)}`
    + `${"页面请求".padEnd(22)}判定`);
  for (const r of base.results) {
    const v = r.verdict;
    line(`  ${String(r.runIndex).padEnd(4)}${r.mode.padEnd(20)}`
      + `${psShort(v.persistedSequence).padEnd(20)}`
      + `${String(v.restoreElapsedMs === null ? "—" : v.restoreElapsedMs + "ms").padEnd(12)}`
      + `${String(v.returnWithinGraceWindow === null ? "—" : v.returnWithinGraceWindow).padEnd(8)}`
      + `${String(v.newRegistersAfterBack).padEnd(12)}${String(v.exitCodeAfterGrace).padEnd(10)}`
      + `${String(v.pageFetchAfterGrace).slice(0, 20).padEnd(22)}`
      + `${v.reproduced === true ? "复现成立" : v.reproduced === false ? "复现不成立" : "跑不出读数"}`);
  }
  line("");
}

line("=".repeat(100));
line("逐配置结论（一句话）");
for (const r of base.results) {
  if (r.runIndex !== 1) continue;
  const tag = r.verdict.reproduced === true ? "复现成立"
    : r.verdict.healed === true ? "已修（绿）"
    : r.verdict.reproduced === false ? "复现不成立" : "跑不出可用读数";
  line(`  · ${r.mode}：${tag}——${oneLine(r.verdict.text)}`);
}
line("");
writeFileSync(path.join(OUT_DIR, "probe-00-bfcache-red.txt"), L.join("\n") + "\n", "utf8");
console.log(`读数已写：${jsonPath}`);
console.log(`读数已写：${path.join(OUT_DIR, "probe-00-bfcache-red.txt")}`);

// 让退出码反映「这一轮跑到的是红还是绿」，方便外层判读（不改判定本身）
process.exitCode = base.results.some(
  (r) => r.verdict.reproduced === true || r.verdict.healed === true) ? 0 : 2;
