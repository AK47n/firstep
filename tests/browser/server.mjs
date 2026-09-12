// 真机验收的服务夹具：起**真后端**（真 /api/modules 投影：真库 93 个模块 +
// 真 intro 拆段），前端静态资源也由它托管——cookie/CORS/StaticFiles/middleware
// 全是真实路径，不手搓 mock 服务器（手搓的 mock 会把「后端投影写错」这类 bug
// 一起 mock 掉）。
//
// 端口用 FIRSTEP_LAUNCHER_PORT 覆盖（与 start-app.bat / webapp.resolve_port
// 同口径）——不动用户默认的 8000/4002，验收自己的服务自己起自己收。
//
// 唯一被拦的端点 = /api/recommend（见 spec）：跑一次真推荐要花 LLM 额度，
// 验收不该有额度成本。
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const REPO_ROOT = fileURLToPath(new URL("../../", import.meta.url));
export const TEST_PORT = 8791;
export const BASE_URL = `http://127.0.0.1:${TEST_PORT}`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function healthy(url) {
  try {
    const resp = await fetch(`${url}/api/health`);
    return resp.ok;
  } catch (e) {
    return false;
  }
}

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

// startServer()：起服务并等健康检查通过；返回 { proc, url, stop() }。
// 启动失败（30s 内没活）抛错——验收环境问题要当场红，不要静默跳过。
export async function startServer({ timeoutMs = 30000 } = {}) {
  const env = {
    ...process.env,
    PYTHONPATH: "src",
    PYTHONIOENCODING: "utf-8",
    FIRSTEP_LAUNCHER: "1",
    FIRSTEP_LAUNCHER_PORT: String(TEST_PORT),
  };
  const proc = spawn("python", ["-m", "contest_generator.webapp"], {
    cwd: REPO_ROOT,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let log = "";
  proc.stdout.on("data", (d) => { log += d.toString(); });
  proc.stderr.on("data", (d) => { log += d.toString(); });

  const deadline = Date.now() + timeoutMs;
  let sawStale = false;
  while (Date.now() < deadline) {
    if (await healthy(BASE_URL)) {
      if (await endpointSentinel(BASE_URL)) {
        return {
          proc,
          url: BASE_URL,
          log: () => log,
          stop: () => stopServer(proc),
        };
      }
      // 健康检查过了但端点哨兵不过 = 端口上是别的东西（多半是上一轮没收干净的
      // 旧后端）；等它一会儿，仍不过就大声失败而不是静默跑在旧代码上。
      if (!sawStale) {
        sawStale = true;
        await sleep(2000);
        continue;
      }
      await stopServer(proc);
      throw new Error(
        `端口 ${TEST_PORT} 上已有一个不进贡新版端点的服务（旧后端？）——验收会跑在旧代码上。\n`
        + `请先收掉它：Get-NetTCPConnection -LocalPort ${TEST_PORT} -State Listen | `
        + `ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }\n`
        + `（本进程日志：${log || "（空：说明真正在答的是别的进程）"}）`
      );
    }
    if (proc.exitCode !== null) {
      throw new Error(`后端启动即退出（exit ${proc.exitCode}）：\n${log}`);
    }
    await sleep(300);
  }
  await stopServer(proc);
  throw new Error(`后端 30s 内未就绪（${BASE_URL}/api/health）：\n${log}`);
}

// stopServer(proc)：收服务。Windows 上 python 是 uvicorn 的父进程，
// taskkill /T 连子进程一起收（脱离进程树的服务 taskkill /T 打不到——
// 仓库既有判例，故这里按进程树收并等它真退）。
export function stopServer(proc) {
  if (!proc || proc.exitCode !== null) return Promise.resolve();
  return new Promise((resolve) => {
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
