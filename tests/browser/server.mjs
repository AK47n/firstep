// 真机验收的服务夹具：起**真后端**（真 /api/modules 投影：真库 93 个模块 +
// 真 intro 拆段），前端静态资源也由它托管——cookie/CORS/StaticFiles/middleware
// 全是真实路径，不手搓 mock 服务器（手搓的 mock 会把「后端投影写错」这类 bug
// 一起 mock 掉）。
//
// 端口：**每个 spec 各要一个空闲端口**（默认由内核分配，`requestedPort` 可指定钉死
// 的端口），不动用户默认的 8000/4002，验收自己的服务自己起自己收。
//
// 唯一被拦的端点 = /api/recommend（见 spec）：跑一次真推荐要花 LLM 额度，
// 验收不该有额度成本。
import { spawn } from "node:child_process";
import { createWriteStream, existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = fileURLToPath(new URL("../../", import.meta.url));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// seedConfig()：给子进程写一份**指向检出内库**的配置文件，并返回它的路径
// （工单 ci-gate-fixes/02）。
//
// **为什么必须有它**：后端只从 `~/.contest_generator/config.json` 取"库在哪"。开发机上那份
// 配置指到本仓 `library/`，所以本机全绿；而 CI runner 上**没有那份文件** ⇒ 库解析不出来 ⇒
// 库相关的只读端点答 400「未配置 AI API」⇒ 端点哨兵如实判"端口上是旧后端"并把刚起的后端
// 杀掉。于是这条 CI 腿从加上那天起就没真跑过（`ui-dom-contract-gate/03` 之后 main 一直没推，
// 直到 v1.3.0 才第一次跑，run 36154463953 当场红）。
//
// **做法**：写临时配置 + 用产品的显式覆盖口 `FIRSTEP_CONFIG_PATH` 指过去（工单
// ci-gate-fixes/01 引入）。刻意**不伪造 `HOME` / `USERPROFILE`**——那会连带改掉数据目录、
// 最近工程等一串路径推导，把一个显式契约换成全局副作用。
//
// **api_key 给一个夹具专用的假值**：库端点已经不再需要它（工单 ci-gate-fixes/04 把
// 「库在哪」与「AI 配了没」拆成两道闸，上面那条 400 从此不会再出现）；现在它保的是
// **AI 面与前端读到的「已配置」态**——`api_configured` 为真时，设置页环境体检那行显示
// 「已保存（模型 …）」而不是「未保存主 API key」、欢迎卡走"已配置"分支
// （`fx/env.js` / `ui/welcome.js`），验收跑的才是"用户已配好"那条路
// （spec 自己 `page.route` 挡掉真调用）。**它保不了 `#gen-banner`**：那条横幅只在
// 保存设置后被 toggle，首屏本来就不出现（工单 04 探针的既有观察）。
//
// **base_url 指向本机一个没人听的端口**（本单评审整改）：种子配置漏写它就会落到
// `DEFAULT_BASE_URL = https://api.deepseek.com`，于是一条**没被 spec 的 `page.route` 拦住**的
// LLM 路径会真出网（拿假 key 换回 401）。注意**拦截不在本夹具里**——`/api/recommend` 是各 spec
// 自己 `page.route` 挡的（`module-intro.spec.mjs` / `code-tree-click.spec.mjs`），夹具没有、
// 也不该有"拦端点"这个职责。指到死端口后，漏拦的路径**立刻连接被拒**：既不出网，也大声失败。
let seededConfigPath = null;

// extraConfigKeys()：`FIRSTEP_BROWSER_CONFIG_EXTRA`（JSON 对象）里那几个键**并进**种子配置
// （工单 ci-gate-fixes/08）。
//
// **为什么要有它**：CI runner 上没有 Keil UV4、也没有 CCS 自带的 gmake，而开发机上两件都有
// ——于是"**没有工具链**"这个前提在本机**造不出来**，依赖它的那条门在本机永远绿、一推上去
// 才红（本单就是 CI 上 3 条红暴露出来的）。工具链的探测本来就有**配置覆盖口**
// （`config.json` 的 `uv4_path` / `gmake_path`，`compile_runner.find_uv4` 明写"非空但指向
// 不存在的文件按未找到处理"），所以造这个前提不需要新概念，只要把这两个键指到不存在的路径：
//
//     FIRSTEP_BROWSER_CONFIG_EXTRA='{"uv4_path":"C:/__none__/UV4.exe",
//                                    "gmake_path":"C:/__none__/gmake.exe"}'
//
// **缺省（未设 / 空串）= 与从前逐字节一致**；**解析失败大声失败**——静默忽略会让人以为
// "前提造出来了"，而实际跑的还是普通那一态，那正是本单最怕的假绿。
function extraConfigKeys() {
  const raw = (process.env.FIRSTEP_BROWSER_CONFIG_EXTRA || "").trim();
  if (!raw) return {};
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(`FIRSTEP_BROWSER_CONFIG_EXTRA 不是合法 JSON：${e.message}`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("FIRSTEP_BROWSER_CONFIG_EXTRA 必须是 JSON 对象（例：{\"uv4_path\":\"…\"}）");
  }
  return parsed;
}

function seedConfig() {
  if (seededConfigPath) return seededConfigPath;
  const modules = join(REPO_ROOT, "library", "modules");
  const masters = join(REPO_ROOT, "library", "masters");
  // 布局改名 / 检出里没有库时**当场大声失败**：否则后端起得来但库解析不出来 ⇒ 库相关端点答 400
  // ⇒ 端点哨兵误报「端口上是旧后端」——正是这段注释开头最怕的那种误导性假红。
  for (const dir of [modules, masters]) {
    if (!existsSync(dir)) {
      throw new Error(`夹具种子配置指向的目录不存在：${dir}`
        + `（检出里没有 library/？布局改名了？）`);
    }
  }
  const dir = mkdtempSync(join(tmpdir(), "firstep-browser-fixture-"));
  const path = join(dir, "config.json");
  writeFileSync(path, JSON.stringify({
    api_key: "sk-browser-fixture",           // 夹具专用假 key（见上）
    base_url: "http://127.0.0.1:9/v1",       // 死端口：漏拦的 LLM 路径立刻连接被拒（见上）
    module_library_dir: modules,
    masters_dir: masters,
    ...extraConfigKeys(),                    // 本机造 CI 前提的口（见 extraConfigKeys）
  }, null, 2), "utf8");
  seededConfigPath = path;
  // 收临时目录：`exit` 覆盖正常结束，信号覆盖 Ctrl-C / 被强杀（排查时正是在反复 Ctrl-C）。
  // 两个钩子里都只做同步事（来不及做异步）。
  const cleanup = () => {
    try { rmSync(dir, { recursive: true, force: true }); } catch { /* 收不掉不影响验收结论 */ }
  };
  process.on("exit", cleanup);
  for (const sig of ["SIGINT", "SIGTERM"]) {
    process.on(sig, () => { cleanup(); process.exit(130); });
  }
  return path;
}

/** 服务在答话吗（`/api/health` 200）。**导出**给 spec 用：用例要判"服务还活着吗"，
 *  各自再抄一份 fetch + try/catch 就是第二份同形实现（工单 launcher-exit-race/04 评审）。
 *  夹具内部沿用旧名 `healthy`。 */
export async function serverAlive(url) {
  try {
    const resp = await fetch(`${url}/api/health`);
    return resp.ok;
  } catch (e) {
    return false;
  }
}

const healthy = serverAlive;

// 端点哨兵（工单 gen-chain-audit/06 的现场教训）：`startServer` 之前只等健康检查，
// 端口上**已有一个旧后端**时 `spawn` 静默失败、健康检查却立刻通过 → 整轮验收跑在
// 旧代码上（本轮就踩过：判据端点 404，审计报的还是修前那 115 条）。
// 判据：起服务后必须真答一个**较新**端点（`/api/bindings/matrix`），否则大声失败。
async function endpointSentinel(url) {
  try {
    const resp = await fetch(`${url}/api/bindings/matrix`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: "mspm0", slugs: [] }),
    });
    return resp.ok;
  } catch (e) {
    return false;
  }
}

// freePort()：向内核要一个当前空闲的端口（bind :0 读出实际端口后立刻放开）。
// 窗口内被别人抢走由 startServer 的重试兜住（最多三次，每次重新要一个）。
function freePort() {
  return new Promise((resolve, reject) => {
    const probe = createServer();
    probe.unref();
    probe.on("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

// portListening(port)：该端口上现在有监听者吗（Windows 走 netstat，其余走 ss——
// 不引依赖；node:net 的 connect 探法在 TIME_WAIT 期会给出误导性结果）。
//
// 判据 = 该行听着 LISTEN，且行里出现 `:port` 且**它后面不是数字**。两点都是踩出来的：
//   · 不能取"第一列"当本地地址（netstat 的第一列是协议 `TCP`）——本轮自检抓到这个错法
//     会让它**恒判空闲**（收服务时以为端口已释放，直接埋下"跑在旧服务上"的假红）；
//   · 不能用 `includes(":port ")`——IPv6 行是 `[::]:8791` 行尾无空格，会漏判；
//     而 `:87910` 这类不同端口必须排除，所以要求 `:port` 后面不是数字（行尾/空白都行）。
function portListening(port) {
  const win = process.platform === "win32";
  const re = new RegExp(`:${port}(?![0-9])`);
  return new Promise((resolve) => {
    const child = spawn(win ? "netstat" : "ss", win ? ["-ano", "-p", "TCP"] : ["-lnt"],
      { stdio: ["ignore", "pipe", "ignore"] });
    let out = "";
    child.stdout.on("data", (d) => { out += d.toString(); });
    child.on("error", () => resolve(false));     // 探不到就当空闲（别卡住验收）
    child.on("exit", () => {
      resolve(out.split(/\r?\n/).some((line) => /LISTEN/i.test(line) && re.test(line)));
    });
  });
}

// killListeners(port)：收掉占用该端口的遗留进程（**只对验收自己的端口动手**）。
// 用途见 startServer 里那段"为什么端口必须每次都是干净的"。
function killListeners(port) {
  if (process.platform !== "win32") return false;
  const script = `Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction `
    + `SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force `
    + `-ErrorAction SilentlyContinue }`;
  const child = spawn("powershell", ["-NoProfile", "-Command", script],
    { stdio: "ignore" });
  return new Promise((resolve) => {
    child.on("error", () => resolve());
    child.on("exit", () => resolve());
  });
}

// **默认不主动设 FIRSTEP_LAUNCHER**（工单 ui-dom-contract-gate/01）：设了它，服务就进了启动器的
// "关浏览器 = 停服务"模式——前端每次 `page.goto` / `reload` 都 `pagehide` → `POST /api/tabs/bye`，
// 服务见"最后一个标签走了"就起宽限准备 `os._exit`。验收根本不需要产品侧的自动退出：本夹具
// 自己 `stop()` 收服务（**服务生命周期归夹具**，不归产品），去掉这个开关 = 整类假红消失，
// 且服务行为与"手动跑源码"完全一致。
//
// ⚠ 措辞要说准：**"不主动设"不等于"保证不设"**——`env` 是 `{...process.env}` 展开的，
// 外壳里若已有 `FIRSTEP_LAUNCHER=1` 会照样透给子进程（`.scratch/launcher-exit-race/probe-00-order.mjs`
// 正是靠这条进启动器模式）；要显式开就传 `launcher: true`。
//
// ⚠ 这条决策**不因产品侧那半张修好而改变**（工单 launcher-exit-race/01-03 已把"F5 会被应用
// 自己关掉"那条竞态修掉：登记提前到 index.html head 的内联脚本、旧文档迟到的告别不再注销新
// 登记、退出调度幂等）——服务生命周期归夹具这条理由与竞态无关。启动器模式本身（含"最后一个
// 页面离开 → 服务自己停"这个功能）由 `launcher-reload.spec.mjs` 用
// `startServer({ launcher: true })` 专门验（**其余 spec** 一律不设；一次性探针可以自己开）。
//
// ⚠ 副作用要认下来：默认不自杀 ⇒ spec 崩溃时可能留下**孤儿 python**。所以 startServer
// 自己保证"端口是干净的"（见下），不指望上一轮收干净。

// startServer(opts)：起服务并等健康检查通过；返回 { proc, port, url, log(), stop() }。
//
// **端口策略**（工单 ui-dom-contract-gate/01，本夹具最要紧的一条）：
//   ① 默认**由内核分配空闲端口**（不再用固定的 8791）。三个 spec 连跑时，上一个的
//      `after` 收完服务、下一个的 `before` 立刻起新服务——taskkill 返回 ≠ 端口已释放，
//      实测下一个后端 bind 失败（`[Errno 10048]`，exit 3），而**端口上那个还没死透的
//      旧服务照样答健康检查与端点哨兵**（同一份代码）→ 夹具"起服务成功"、测试跑在
//      不属于自己的服务上，等旧服务咽气就满屏 `ERR_CONNECTION_REFUSED`（看着像产品坏了）。
//      本机实测复现两次，排查代价很高。
//   ② `requestedPort` 给的是**钉死的端口**（排查"就想用 8791 复现"这类场景）：端口上
//      有监听者先收掉它——那是上一轮留下的本应用服务，继续跑就等于跑在旧代码上；
//      收不干净就大声失败，**不静默换端口**（那会让"钉死"这个意图失效）。
//   ③ 每次起服务前后都判"**我起的这个进程**还活着吗"：端口上答话的可能是别人。
//
// `FIRSTEP_BROWSER_SERVER_LOG=<路径>`：把后端 stdout/stderr **边跑边追加**到该文件
// （排查用：验收中途服务没了时，`log()` 里的最后一段常常拿不到——异常已经抛出来了）。
// 不设 = 只留在内存里，零影响。
//
// `launcher`（工单 launcher-exit-race/04）：置 true 时给子进程加 `FIRSTEP_LAUNCHER=1`
// —— 服务进"关浏览器 = 停服务"模式。**只有 `launcher-reload.spec.mjs` 用它**（那条 spec
// 要的就是产品侧的自动退出行为）；其余 spec 一律不设（理由见上）。
export async function startServer({ timeoutMs = 30000, requestedPort = 0, launcher = false } = {}) {
  if (requestedPort) return spawnOn(requestedPort, timeoutMs, { reclaim: true, launcher });
  // 内核分配的空闲端口有"要完到用上"的窗口：抢输了就再要一个（最多三次）
  let lastError = null;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      return await spawnOn(await freePort(), timeoutMs, { reclaim: false, launcher });
    } catch (e) {
      lastError = e;
      if (!/EADDRINUSE|10048|已被占用/.test(String(e && e.message))) throw e;
    }
  }
  throw lastError || new Error("起服务失败（重试用尽）");
}

/** 在指定端口上起服务。reclaim=true 时先收掉端口上的遗留进程（钉死端口的场景）。 */
async function spawnOn(port, timeoutMs, { reclaim, launcher }) {
  if (await portListening(port)) {
    if (!reclaim) throw new Error(`端口 ${port} 已被占用（EADDRINUSE）`);
    await killListeners(port);
    const until = Date.now() + 5000;
    while (Date.now() < until && await portListening(port)) await sleep(150);
    if (await portListening(port)) {
      throw new Error(`端口 ${port} 上的遗留服务收不掉——请手动收掉再跑`);
    }
  }
  return spawnServer({ port, url: `http://127.0.0.1:${port}`, timeoutMs, launcher });
}

async function spawnServer({ port, url, timeoutMs, launcher }) {
  const env = {
    ...process.env,
    PYTHONPATH: "src",
    PYTHONIOENCODING: "utf-8",
    FIRSTEP_LAUNCHER_PORT: String(port),
    // 库指向**检出内**那份，而不是操作用户主目录里可能存在的真配置（工单 ci-gate-fixes/02）：
    // 验收结果因此与"这台机器上装过什么"解耦，干净 runner 上也一样跑得起来。
    FIRSTEP_CONFIG_PATH: seedConfig(),
    // 不缓冲：**服务被自己关掉**（或崩掉）时，uvicorn 的 access log 若还压在块缓冲里，
    // 就随进程一起没了——而那正是这套日志最要被读到的时候（工单 launcher-exit-race/04
    // 实测：`FIRSTEP_BROWSER_SERVER_LOG` 只收到 8 行、一条请求都没有）。
    PYTHONUNBUFFERED: "1",
  };
  if (launcher) env.FIRSTEP_LAUNCHER = "1";
  const proc = spawn("python", ["-m", "contest_generator.webapp"], {
    cwd: REPO_ROOT,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const logPath = (process.env.FIRSTEP_BROWSER_SERVER_LOG || "").trim();
  const sink = logPath ? createWriteStream(logPath, { flags: "a" }) : null;
  let log = "";
  const absorb = (d) => {
    const text = d.toString();
    log += text;
    if (sink) sink.write(text);
  };
  proc.stdout.on("data", absorb);
  proc.stderr.on("data", absorb);
  proc.on("exit", (code, signal) => {
    const line = `\n[fixture] 后端进程退出（端口 ${port}）code=${code} signal=${signal}\n`;
    log += line;
    if (sink) sink.write(line);
  });

  const deadline = Date.now() + timeoutMs;
  let sawStale = false;
  while (Date.now() < deadline) {
    if (await healthy(url)) {
      // **先判新进程还活着**：端口上答话的可能是别人（上一轮的遗留服务照样能过
      // 健康检查与端点哨兵——同一份代码），于是夹具"起服务成功"、测试跑在错的
      // 服务上。判据只能是"**我起的这个进程**还活着"：它死了 = 这一次没起来。
      if (proc.exitCode !== null) {
        await stopServer(proc);
        throw new Error(
          `端口 ${port} 上已有一个服务在答，而本次新起的后端进程已经退出`
          + `（exit ${proc.exitCode}）——十有八九是端口被占（EADDRINUSE）。\n`
          + `日志：\n${log}`
        );
      }
      if (await endpointSentinel(url)) {
        return {
          proc,
          port,
          url,
          log: () => log,
          stop: () => stopServer(proc, port),
        };
      }
      // 健康检查过了但端点哨兵不过 = 端口上是别的东西（多半是上一轮没收干净的
      // 旧后端）；等它一会儿，仍不过就大声失败而不是静默跑在旧代码上。
      if (!sawStale) {
        sawStale = true;
        await sleep(2000);
        continue;
      }
      await stopServer(proc, port);
      throw new Error(
        `端口 ${port} 上已有一个不进贡新版端点的服务（旧后端？）——验收会跑在旧代码上。\n`
        + `（本进程日志：${log || "（空：说明真正在答的是别的进程）"}）`
      );
    }
    if (proc.exitCode !== null) {
      // bind 失败（端口被抢）由调用方换端口重试；其余原样上报
      throw new Error(`后端启动即退出（端口 ${port}，exit ${proc.exitCode}）：\n${log}`);
    }
    await sleep(250);
  }
  await stopServer(proc, port);
  throw new Error(`后端 ${timeoutMs}ms 内未就绪（${url}/api/health）：\n${log}`);
}

// stopServer(proc, port)：收服务。Windows 上 python 是 uvicorn 的父进程，
// taskkill /T 连子进程一起收（脱离进程树的服务 taskkill /T 打不到——
// 仓库既有判例，故这里按进程树收并等它真退）。
//
// **必须等到端口真的空出来才返回**：spec 连跑时下一个 `before` 紧接着起服务，
// taskkill 返回 ≠ 端口已释放（判据 = 端口上真的没有 LISTEN 了）。端口是**入参**
// 而不是模块级状态——同时起两个服务时，各自的 stop 只动各自的端口。
export async function stopServer(proc, port) {
  if (proc && proc.exitCode === null) {
    await new Promise((resolve) => {
      const done = () => resolve();
      proc.once("exit", done);
      if (process.platform === "win32") {
        spawn("taskkill", ["/pid", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
      } else {
        proc.kill("SIGTERM");
      }
      setTimeout(done, 5000);   // 兜底：5s 没退也别卡住验收
    });
  }
  if (!port) return;
  const deadline = Date.now() + 10000;   // 端口释放（bounded）
  while (Date.now() < deadline) {
    if (!await portListening(port)) return;
    await sleep(150);
  }
  // 收不干净就**收掉它**（端口是本轮验收自己挑的，上面只可能是本应用的服务）：
  // 留着它，下一轮若被内核分到同一个端口就会跑在旧代码上（那是最难查的一类假红）
  await killListeners(port);
}
