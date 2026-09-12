// 生成链路真机审计（playwright）：**换面**——不碰「模块说明 / 推荐区」（那面已由
// tests/browser/module-intro.spec.mjs + deep-audit.mjs 覆盖，9 验收 + 25 审计断言全绿）。
//
// 本脚本审的是**生成链路**，按收益排序：
//   P 引脚分配 / 冲突消解 / 多实例
//   R 编译 → 错误跳行 → 修复轮
//   W 生成 → 输出目录 → 覆盖确认
//   X 模块库 CRUD
//   Y 代码编辑器 / AI 面板的失败路径
//
// 运行：node tests/browser/gen-chain-audit.mjs          ← 全部节
//       node tests/browser/gen-chain-audit.mjs P W      ← 只跑指定节（调试）
// 依赖：python 后端可起（server.mjs 夹具）+ playwright chromium + Keil UV4（R 节；
//       无工具链时 R 节自动降级为「无工具链回退」判据，不报假红）。
//
// **零 LLM 额度**：只拦真会花钱的端点。经实测（webapp 路由逐条读源码确认）：
//   · /api/recommend、/api/skeleton、/api/fix-errors、/api/tasks/* 等 = 必调 LLM；
//   · /api/generate **problem_text 为空时零 LLM**（report_draft 短路）；
//   · /api/compile、/api/bindings/validate|auto、/api/selection/expand、
//     /api/code/*、/api/modules 的 platform-files / platform-identity / DELETE = 零 LLM。
// 需要 LLM 的端点一律由节内 route 拦截（注入 502/500）——**顺带就是它们的失败路径判据**。
//
// ⚠ **宣称 bug 之前的三步自检**（deep-audit.mjs 文件头的教训，本轮继续遵守）：
//   ① 把嫌疑逻辑改回原实现形状，确认现象仍在；
//   ② 读一遍真正执行路径的源码，确认时序；
//   ③ 判据只描述「绝不该出现的事实」，不描述「我以为应该出现却没出现」。
// 本脚本第一版有两条 FAIL 犯了第 ③ 条（把「手动目录」按「桌面同名工程」判、把
// 异步树渲染当同步读），已改——教训记在各节注释里。
import { chromium } from "playwright";
import { startServer } from "./server.mjs";
import { mkdtempSync, rmSync, writeFileSync, readFileSync, existsSync, readdirSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const findings = [];
const note = (level, area, detail) => {
  findings.push({ level, area, detail });
  console.log(`[${level}] ${area} :: ${detail}`);
};

let server = null;
let browser = null;
let TMP = null;                     // 本轮的临时工程根（结束即删，不污染桌面/仓库）

// ---------------------------------------------------------------------------
// 页面夹具：真后端 + 真渲染；LLM 端点默认按「未配置凭据」的真实形态 502 拦截。
// ---------------------------------------------------------------------------
const LLM_ENDPOINTS = [
  "**/api/recommend", "**/api/skeleton", "**/api/fix-errors",
  "**/api/tasks/plan", "**/api/tasks/execute", "**/api/tasks/idea/analyze",
  "**/api/tasks/params/scan", "**/api/topic/preread", "**/api/revise/analyze",
  "**/api/revise/deepen", "**/api/revise/apply", "**/api/masters/distill",
  "**/api/params/chat/send", "**/api/topics/split",
];
const LLM_STUB = { status: 502, contentType: "application/json",
  body: JSON.stringify({ detail: "LLM 调用失败（审计注入 502）：本机未配置可用凭据" }) };

async function newPage(opts = {}) {
  const page = await browser.newPage({ viewport: opts.viewport || { width: 1440, height: 900 } });
  const problems = [];
  const calls = [];
  page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const t = m.text();
    // 已知噪声：审计**自己注入**的 4xx/5xx 会让浏览器留一条 resource 错误（证物非缺陷）；
    // preview-dir 的无编号题面 400 是产品既有行为（注释写明「静默降级」）。
    if (/status of (400|402|500|502|503)/.test(t)) return;
    problems.push("console: " + t);
  });
  page.on("dialog", (d) => d.dismiss());
  page.on("request", (r) => {
    const u = r.url();
    if (u.includes("/api/")) calls.push({ method: r.method(), path: u.replace(server.url, ""), body: r.postData() });
  });
  for (const pat of LLM_ENDPOINTS) await page.route(pat, (route) => route.fulfill(LLM_STUB));
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  return { page, problems, calls };
}

// 选平台（真卡片点击）
async function pickPlatform(page, label) {
  await page.locator("#platforms .platform-card", { hasText: label }).first().click();
  await page.waitForFunction(() => document.querySelectorAll("#module-grid .module-card").length > 0);
}

// 切到「手输输出目录」模式（真点 checkbox：桌面默认勾选时 #output-dir 是禁用的）。
// 手输目录 = 生成写进临时根，不碰用户桌面；也是真实用户会走的路径。
async function manualOutput(page) {
  const on = await page.locator("#desktop-topic-output").isChecked().catch(() => false);
  if (on) await page.locator("#desktop-topic-output").uncheck();
  await page.waitForFunction(() => !document.getElementById("output-dir").disabled, undefined, { timeout: 5000 }).catch(() => {});
}

// 点「生成工程」并等到真终态。返回 { blocked, msg, cls, resDir, status }。
// blocked = 前置校验拦下（**没发请求**）——此时按钮从未变 disabled，所以判「有没有发
// 请求」只能看 calls，不能看按钮态（第一版在这里吃过 30s 超时）。
async function runGenerate(page, calls) {
  const n0 = calls.filter((c) => c.path === "/api/generate").length;
  await page.click("#btn-generate");
  await page.waitForTimeout(900);
  const sent = calls.filter((c) => c.path === "/api/generate").length > n0;
  if (!sent) {
    return { blocked: true, msg: (await page.locator("#generate-msg").innerText().catch(() => "")).trim(), cls: "", resDir: "", status: "" };
  }
  await page.waitForFunction(
    () => !document.getElementById("btn-generate").disabled, undefined, { timeout: 180000 },
  ).catch(() => {});
  await page.waitForTimeout(300);
  return {
    blocked: false,
    msg: (await page.locator("#generate-msg").innerText().catch(() => "")).trim(),
    cls: await page.locator("#generate-msg").getAttribute("class").catch(() => ""),
    resDir: (await page.locator("#res-dir").innerText().catch(() => "")).trim(),
    status: (await page.locator("#gen-status").innerText().catch(() => "")).trim(),
  };
}

// 从模块池真点击加模块（走 addModule → runExpand 真链路），并等展开收敛
async function addModules(page, slugs) {
  for (const slug of slugs) {
    const card = page.locator(`#module-grid .module-card[data-add="${slug}"]`);
    if (!(await card.count())) { note("FAIL", "夹具", `模块池里没有 ${slug} 卡片（真库缺件？）`); continue; }
    await card.click();
    await page.waitForTimeout(120);
  }
  await page.waitForFunction(
    () => !document.getElementById("btn-expand").disabled, undefined, { timeout: 30000 },
  ).catch(() => {});
  await page.waitForFunction(
    () => !document.getElementById("selected-list").innerText.includes("未展开依赖"),
    undefined, { timeout: 30000 },
  ).catch(() => {});
}

// 展开结果（真 /api/selection/expand 载荷，经页面 fetch 现取——与页面看到的是同一份）
async function expandOf(page, platform, slugs) {
  return page.evaluate(async ([p, s]) => {
    const r = await fetch("/api/selection/expand", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: p, slugs: s }),
    });
    return { status: r.status, json: await r.json() };
  }, [platform, slugs]);
}

// ===========================================================================
// P. 引脚分配 / 冲突消解 / 多实例
// ===========================================================================
// 本节判据核心：**前端的能力判定与后端校验必须同口径**。
// 前端判据**不再由本脚本镜像**（工单 gen-chain-audit/06 整改）：板图判据已单源为
// 后端下发的判据模型（`/api/bindings/matrix`），前端只求值——所以本脚本直接求值
// 前端**真**函数 `fx/pin-model.js`（与页面同实现）。
// 历史教训：本脚本原来照抄了一份 `pinCanHost` 镜像；前端修好之后它照样报 115 条
// （镜像没修）——审计判据必须指向真件，否则它和产品各漂各的。
async function testP() {
  console.log("\n=== P. 引脚分配 / 冲突消解 / 多实例 ===");
  for (const [platLabel, platform, slugs] of [
    ["STM32", "stm32", ["ir_beam", "pid", "motor", "led_beep"]],
    ["地猛星", "mspm0", ["step_motor", "huidu", "motor", "led_beep"]],
  ]) {
    const { page, problems, calls } = await newPage();
    await pickPlatform(page, platLabel);
    await addModules(page, slugs);
    const exp = await expandOf(page, platform, slugs);
    if (exp.status !== 200) { note("FAIL", `P 展开失败 ${platform}`, JSON.stringify(exp.json).slice(0, 200)); await page.close(); continue; }
    const board = await page.evaluate(async (p) => (await (await fetch("/api/boards?platform=" + p)).json()).boards[0], platform);
    const mods = exp.json.modules;
    // 判据模型（与页面同一份载荷：同一端点、同一 slugs、同为空绑定）
    const matrix = await page.evaluate(async ([p, s]) => {
      const r = await fetch("/api/bindings/matrix", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform: p, slugs: s }),
      });
      if (!r.ok) return { __status: r.status };
      return await r.json();
    }, [platform, slugs]);
    if (matrix.__status) {
      note("FAIL", `P 判据模型端点不可用 ${platform}`,
        `POST /api/bindings/matrix → ${matrix.__status}；前端只能降级为「类型级」显示，本节判据不成立`);
      await page.close(); continue;
    }

    // ---- P1 能力判定前后端一致性（逐角色 × 逐脚，跑真 /api/bindings/validate）----
    const cands = await page.evaluate(async ([boardObj, modules, p]) => {
      const ioPins = (boardObj.pins || []).filter((x) => x.kind === "io");
      const out = [];
      for (const m of modules) {
        const entry = (m.platforms || {})[p]; if (!entry) continue;
        for (const decl of entry.pins || []) {
          for (const pin of ioPins) {
            // 菜单第一层过滤（列不列这个角色）：只看类型 token——与 pinListsType 同口径
            const prefix = decl.type + ":";
            if (!(pin.capabilities || []).some((t) => t === decl.type || t.startsWith(prefix))) continue;
            out.push({ slug: m.slug, role: decl.id, type: decl.type, pin: pin.name });
          }
        }
      }
      return out;
    }, [board, mods, platform]);

    // UI 判据 = 真函数（`/js/fx/pin-model.js`，页面用的同一份）在页面里求值。
    // 工单 mspm0-slot-conflict/05 起，判据还含**成对跟随**（uart/i2c/pwm 的成对角色
    // 点一脚 = 两脚一次提交）——所以本节的对照口径必须跟着变成「用户点下去之后
    // **整份** bindings」（单绑定回验会把合法的一次点击误判成假绿：C0→PA0 单看
    // 后端拒，但界面上点它 = {C0: PA0, C1: PA1} 整对搬，后端收）。
    // 这一次点击之后的**整份 bindings**（缺省全默认 + 本次写下的 key）：
    // 成对角色点一脚 = 两脚一次写（工单 05），所以 trial 可能有两个 key。
    // 每个候选独立构造（与既有单绑定对照同口径：一次点击就是一份提交），
    // 不做「跨候选累积」——那种模拟会把每个角色的隐式默认脚也算成显式条目，
    // 引入与「一次点击」无关的槽位/端口组纠缠。
    const uiCalc = await page.evaluate(async ([model, boardObj, list]) => {
      const mod = await import("/js/fx/pin-model.js");
      const idx = {}; for (const pin of boardObj.pins || []) idx[pin.name] = pin;
      return list.map((c) => {
        const key = `${c.slug}.${c.role}`;
        const pin = idx[c.pin];
        const verdict = mod.pinModelVerdict(model, boardObj, key, pin, {});
        if (!verdict) return { verdict: false, trial: null };
        const follow = mod.pinPairFollow(model, boardObj, key, pin, {});
        const trial = { [key]: c.pin };
        if (follow && !follow.same) trial[follow.mate] = follow.to;
        return { verdict: true, trial };
      });
    }, [matrix, board, cands]);

    const uiOk = cands.filter((v, i) => uiCalc[i].verdict);
    const uiMiss = cands.filter((v, i) => !uiCalc[i].verdict);
    const budgetMs = 120000;
    const t0 = Date.now();
    let tested = 0, skipped = 0;
    const beRejects = [];      // UI 说行、后端拒 —— 假绿：配得出来但生成必炸
    const beAcceptsMiss = [];  // UI 说不行、后端收 —— 假红：合法脚被白挡
    for (const v of [...uiOk, ...uiMiss]) {
      if (tested >= uiOk.length && Date.now() - t0 > budgetMs) { skipped++; continue; }
      const i = cands.indexOf(v);
      const payload = uiCalc[i].trial || { [`${v.slug}.${v.role}`]: v.pin };
      const r = await page.evaluate(async ([p, s, b]) => {
        const resp = await fetch("/api/bindings/validate", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ platform: p, slugs: s, bindings: b }),
        });
        return await resp.json();
      }, [platform, slugs, payload]);
      tested++;
      const ui = uiCalc[i].verdict;
      if (ui && r.ok === false) beRejects.push({ ...v, error: r.error, payload });
      if (!ui && r.ok === true) beAcceptsMiss.push(v);
    }
    console.log(`  ${platform}：候选 (角色×脚) ${cands.length} 条；实测 ${tested} 条（预算外跳过 ${skipped}）`
      + `；UI 说行 ${uiOk.length} / UI 说不行 ${uiMiss.length}`);
    if (beRejects.length) {
      const e = beRejects[0];
      note("FAIL", `P1 ${platform} UI 放行但后端拒收`, `${beRejects.length} 条：例 ${e.slug}.${e.role}(${e.type}) → ${e.pin}，后端：「${String(e.error).slice(0, 150)}」`
        + ` —— 板图上配得出的绑定，生成时必 400`);
    } else note("PASS", `P1 ${platform} UI 放行的绑定后端全收`, `${uiOk.length} 条 UI 可配绑定实测后端 ok`);
    if (beAcceptsMiss.length) {
      note("WARN", `P1b ${platform} UI 灰显但后端收`, `${beAcceptsMiss.length} 条：例 ${beAcceptsMiss[0].slug}.${beAcceptsMiss[0].role} → ${beAcceptsMiss[0].pin}`
        + ` —— 用户点不了本来合法的脚（判据模型偏严，体验面）`);
    } else if (uiMiss.length && tested > uiOk.length) {
      note("PASS", `P1b ${platform} UI 灰显的后端也拒`, `实测 UI 说不行 ${tested - uiOk.length} 条，后端全部一致拒收`);
    }

    // ---- P2 一键自动配置：结果必须真的过校验，且与界面口径一致 ----
    await page.click("#btn-pin-auto");
    await page.waitForFunction(() => !document.getElementById("btn-pin-auto").disabled, undefined, { timeout: 20000 });
    await page.waitForTimeout(250);
    const autoMsg = await page.locator("#pin-config-msg").innerText().catch(() => "");
    const uiBindings = await page.evaluate(() => {
      const out = {};
      document.querySelectorAll("#pin-role-items .pin-role").forEach((el) => {
        const s = el.querySelector(".role-status").innerText.replace(/\s+/g, " ").trim();
        const m = s.match(/已绑\s+(\S+)/);
        if (m) out[el.dataset.role] = m[1];
      });
      return out;
    });
    const revalidate = await page.evaluate(async ([p, s, b]) => {
      const r = await fetch("/api/bindings/validate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform: p, slugs: s, bindings: b }),
      });
      return await r.json();
    }, [platform, slugs, uiBindings]);
    console.log(`  ${platform} 自动配置：界面绑定 ${JSON.stringify(uiBindings)}；msg=「${autoMsg.replace(/\n/g, " | ").slice(0, 170)}」`);
    if (revalidate.ok === false) {
      note("FAIL", `P2 ${platform} 自动配置产物未过校验`, `界面显示的绑定被后端拒：「${String(revalidate.error).slice(0, 160)}」——一键配置修完还是不能生成`);
    } else note("PASS", `P2 ${platform} 自动配置产物过校验`, `${Object.keys(uiBindings).length} 条界面绑定逐条回验 ok`);
    if (/→/.test(autoMsg)) {
      const moved = autoMsg.split("\n").filter((l) => l.includes("→"))
        .map((l) => (l.match(/^\s*✓?\s*([\w.]+)\s*→/) || [])[1]).filter(Boolean);
      const notOnUI = moved.filter((k) => !(k in uiBindings));
      if (notOnUI.length) {
        note("FAIL", `P2 ${platform} 说明条与实际绑定不符`, `说明条声称移开了 ${notOnUI.join("、")}，但界面上这些角色没有「已绑」状态`);
      } else if (moved.length) note("PASS", `P2 ${platform} 说明条与绑定一致`, `${moved.length} 条「已移开」在界面都真变成了已绑`);
    }

    // ---- P3 多实例：配置必须逐字进 /api/generate 载荷，且产物与实例数对齐 ----
    const instCard = page.locator("#card-instance-config");
    if (!(await instCard.isVisible().catch(() => false))) {
      note("FAIL", `P3 ${platform} 多实例卡未显示`, `选中集含 led_beep（依赖 led）却没看到实例配置卡 —— 多实例配置无处可做`);
    } else {
      const ledMod = mods.find((m) => m.slug === "led");
      const maxN = (ledMod && ledMod.multi_instance && ledMod.multi_instance.max) || 8;
      const before = await page.locator('#instance-config [data-del][data-slug="led"]').count();
      for (let i = before; i < maxN; i++) {
        const btn = page.locator('#instance-config [data-add="led"]');
        if (await btn.isDisabled().catch(() => true)) break;
        await btn.click(); await page.waitForTimeout(70);
      }
      const atMax = await page.locator('#instance-config [data-del][data-slug="led"]').count();
      const addDisabled = await page.locator('#instance-config [data-add="led"]').isDisabled().catch(() => false);
      const maxHint = await page.locator("#instance-config").innerText();
      console.log(`  ${platform} 多实例：起始 ${before} 个 → 加到 ${atMax} 个（上限 ${maxN}）；添加按钮 disabled=${addDisabled}`);
      if (atMax > maxN) note("FAIL", `P3 ${platform} 实例超上限`, `配到 ${atMax} 个 > manifest max ${maxN}`);
      else note("PASS", `P3 ${platform} 实例上限生效`, `${atMax}/${maxN}，按钮禁用=${addDisabled}（提示「${maxHint.includes("已达上限") ? "已达上限 " + maxN : "无"}」）`);

      await page.locator('#instance-config [data-field="name"][data-slug="led"]').first().fill("探照灯");
      await page.locator('#instance-config [data-field="variant"][data-slug="led"]').first().fill("red");
      await page.waitForTimeout(120);

      // 选脚：真点板图（cap 含 gpio_out 的脚才可点）
      await page.locator('#instance-config [data-pick][data-slug="led"]').first().click();
      await page.waitForTimeout(150);
      const gpioOut = board.pins.filter((p) => p.kind === "io" && (p.capabilities || []).includes("gpio_out"));
      const pinned = gpioOut[0].name;
      await page.evaluate((pinName) => {
        const c = document.querySelector(`#pin-board-svg circle[data-pin="${pinName}"]`);
        if (c) c.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      }, pinned);
      await page.waitForTimeout(250);
      const rowText = await page.locator('#instance-config [data-del][data-slug="led"]').first()
        .locator("xpath=ancestor::div[contains(@class,'instance-row')]").innerText();
      console.log(`  选脚：点 ${pinned} → 行文本「${rowText.replace(/\s+/g, " ")}」`);
      if (!rowText.includes(pinned)) {
        note("FAIL", `P3 ${platform} 板图选脚未落到实例`, `点了 ${pinned} 但实例行仍显示「${rowText.replace(/\s+/g, " ")}」`);
      } else note("PASS", `P3 ${platform} 板图选脚落到实例`, `实例行显示 ${pinned}`);

      // 真正发一次生成（走真 UI 按钮），抓请求体看 instances 是否逐字带上
      await page.fill("#problem", "");     // 题面留空 = /api/generate 零 LLM
      await page.fill("#main-c", "int main(void) { return 0; }");   // main_c 必填（留空 400）
      const outDir = join(TMP, `P-${platform}`);
      await manualOutput(page);
      await page.fill("#output-dir", outDir);
      await page.waitForTimeout(250);
      const g = await runGenerate(page, calls);
      console.log(`  生成：blocked=${g.blocked} msg=「${g.msg.slice(0, 170)}」`);
      if (g.blocked) {
        note("WARN", `P3 ${platform} 生成被前置校验拦下`, `#generate-msg=「${g.msg.slice(0, 160)}」（载荷取证跳过）`);
      } else {
        const genReq = calls.filter((c) => c.path === "/api/generate").pop();
        const payload = (genReq && JSON.parse(genReq.body || "{}")) || {};
        const inst = (payload.instances && payload.instances.led) || null;
        const actual = inst ? inst.length : 0;
        console.log(`  generate 载荷 instances.led = ${JSON.stringify(inst)}`);
        if (!inst) {
          note("FAIL", `P3 ${platform} instances 没进载荷`, `界面配了 ${atMax} 个 led 实例，请求体里 instances=${JSON.stringify(payload.instances)}`);
        } else if (actual !== atMax) {
          note("FAIL", `P3 ${platform} instances 载荷与界面不一致`, `界面配了 ${atMax} 个实例，请求只带 ${actual} 个`);
        } else if (inst[0].name !== "探照灯" || inst[0].pin !== pinned) {
          note("FAIL", `P3 ${platform} 实例内容未逐字带上`, `界面「探照灯 / ${pinned}」→ 载荷 ${JSON.stringify(inst[0])}`);
        } else {
          note("PASS", `P3 ${platform} instances 载荷逐字一致`, `${actual} 个实例（首个 ${inst[0].name}/${inst[0].variant}/${inst[0].pin}）`);
        }
        // 产物：渲染出来的通道表必须覆盖全部实例，且首个实例的脚真落到盘上。
        // 落点按平台不同（CONTEXT.md「多实例」行）：stm32 = 工程根；mspm0 = 模块 code 目录。
        const ledPaths = [join(outDir, "led_instances.h"), join(outDir, "modules", "led", "code", "led_instances.h")];
        const ledPath = ledPaths.find((p) => existsSync(p));
        if (!ledPath) {
          note("FAIL", `P3 ${platform} 产物缺 led_instances.h`, `生成成功却在 ${ledPaths.join(" 与 ")} 都找不到多实例渲染产物`);
        } else {
          const txt = readFileSync(ledPath, "utf8");
          const channels = (txt.match(/#define\s+LED_\w+\s+\d+/g) || []).length;
          const body = txt.split("\n").filter((l) => l.trim() && !l.trim().startsWith("//"));
          console.log(`  led_instances.h（${ledPath.slice(TMP.length + 1)}）：${body.length} 行；通道/引脚相关行：`);
          body.filter((l) => /LED|GPIO|Pin_|$assign/.test(l)).slice(0, 6).forEach((l) => console.log(`      ${l.trim().slice(0, 130)}`));
          // 脚落盘的形态：stm32 是两列宏 GPIO_<端口字母> + Pin_<号>（instance_render
          // 的 _stm32_port/_stm32_pin），mspm0 是 syscfg 的 $assign 引脚名——判据不能
          // 只 grep 引脚名（第一版就是这么误报的）
          const port = "GPIO_" + pinned[1];
          const pinNo = pinned.replace(/^P[A-Z]/, "");
          // mspm0：通道 0 的脚落 **syscfg 的 $assign**（led_instances.h 只引用
          // LED_BEEP_* 宏，见 instance_render._mspm0_pin_macro）——判据要看盘上的
          // syscfg.c 而不是头文件（第一版 grep 头文件，属误报）
          const syscfg = ["mspm0.syscfg", "mspm0.syscfg.json", "Debug/syscfg/mspm0.syscfg"]
            .map((r) => join(outDir, r)).find((p) => existsSync(p));
          const footOnDisk = platform === "stm32"
            ? (txt.includes(port) && new RegExp("Pin_?" + pinNo + "\\b").test(txt))
            : !!(syscfg && readFileSync(syscfg, "utf8").includes('"' + pinned + '"'));
          if (channels < atMax) {
            note("FAIL", `P3 ${platform} 通道表少于实例数`, `${atMax} 个实例却只渲染出 ${channels} 个 LED_* 通道宏`);
          } else if (!footOnDisk) {
            note("FAIL", `P3 ${platform} 通道表/SysConfig 没有界面选的脚`,
              `界面把实例 1 绑到 ${pinned}，盘上找不到（stm32 查 led_instances.h 的 ${port}/Pin_${pinNo}；`
              + `mspm0 查 ${syscfg ? syscfg.slice(TMP.length + 1) : "（没找到 mspm0.syscfg）"} 的 $assign）`);
          } else {
            note("PASS", `P3 ${platform} 通道表覆盖全部实例且带界面的脚`,
              `${channels} 个通道宏，${pinned} 落盘（${platform === "stm32" ? port + " Pin_" + pinNo : "syscfg $assign"}）`);
          }
        }
      }
    }
    if (problems.length) note("FAIL", `P ${platform} 控制台/页面错误`, problems.join(" | "));
    await page.close();
  }
}

// ===========================================================================
// R. 编译 → 错误跳行 → 修复轮
// ===========================================================================
// 判据核心：编译错误必须**真的能跳到出问题的那一行**。这段的真实内容是
// editJumpToFile → 打开 tab → setSelectionRange → 行高亮，只有真浏览器能作证。
// 取证方式：生成时把 main.c 写成第 5 行 `int x = ;`（硬语法错），编译 → 点错误行
// → 读编辑器里真实的光标行。
async function testR() {
  console.log("\n=== R. 编译 → 错误跳行 → 修复轮 ===");
  const outDir = join(TMP, "R-stm32");
  const { page, problems, calls } = await newPage();
  await pickPlatform(page, "STM32");
  await addModules(page, ["ir_beam", "motor"]);

  await page.fill("#problem", "");
  await manualOutput(page);
  const broken = [
    '#include "headfile.h"',
    "int main(void)",
    "{",
    "    ir_beam_init();",
    "    int x = ;",
    "    return 0;",
    "}",
    "",
  ].join("\n");
  await page.fill("#output-dir", outDir);
  await page.fill("#main-c", broken);
  await page.waitForTimeout(200);
  const g = await runGenerate(page, calls);
  console.log(`  生成：blocked=${g.blocked} msg=「${g.msg.slice(0, 200)}」`);
  if (!existsSync(join(outDir, "main.c"))) {
    note("FAIL", "R 前置：生成没落地", `#generate-msg=「${g.msg}」(blocked=${g.blocked})，${outDir}\\main.c 不存在`);
    await page.close(); return;
  }

  // 打开代码栏（真实入口 = 最近记录卡「查看代码」；这里走它用的同一个导出桥，
  // 避开原生目录对话框）——两个 await：目录标签先就位、树随后才出（异步基线探测）
  await page.evaluate(async (dir) => {
    const mod = await import("/js/ui/codeview.js");
    mod.openCodeViewer(dir);
  }, outDir);
  await page.waitForFunction(
    (d) => document.getElementById("code-dir-label").textContent === d, outDir, { timeout: 15000 },
  ).catch(() => {});
  await page.waitForFunction(
    () => !document.getElementById("code-tree").innerText.includes("加载中"), undefined, { timeout: 20000 },
  ).catch(() => {});
  const compileDisabled = await page.locator("#btn-code-compile").isDisabled().catch(() => null);
  console.log(`  代码栏：目录=「${await page.locator("#code-dir-label").innerText().catch(() => "")}」编译按钮 disabled=${compileDisabled}`);

  // 编译（真 UV4）
  const nCompile = () => calls.filter((c) => c.path === "/api/compile").length;
  await page.click("#btn-code-compile");
  await page.waitForFunction(() => !document.getElementById("btn-code-compile").disabled, undefined, { timeout: 240000 });
  await page.waitForTimeout(500);
  const status = await page.locator("#code-compile-status").innerText().catch(() => "");
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll("#code-compile-errors .code-compile-error")].map((el) => ({
      path: el.dataset.compilePath || "", line: el.dataset.compileLine || "",
      text: el.innerText.replace(/\s+/g, " ").trim().slice(0, 130),
    })));
  console.log(`  编译状态行 = 「${status}」；结构化错误 ${rows.length} 条`);
  rows.slice(0, 8).forEach((r) => console.log(`    · ${r.path}:${r.line} ${r.text.slice(0, 110)}`));

  if (/未检测到|回退贴文本/.test(status)) {
    note("WARN", "R0 本机无编译工具链", `状态行=「${status}」——R 节降级为失败路径判据（编译主链未实测）`);
    if (nCompile() !== 1) note("FAIL", "R0 无工具链时的请求次数", `点了 1 次编译却打了 ${nCompile()} 次 /api/compile`);
    await page.close(); return;
  }
  if (/编译通过/.test(status)) {
    note("FAIL", "R1 故意写坏的 main.c 却编译通过", `状态行=「${status}」——第 5 行 int x = ; 是硬语法错，UV4 不可能给 0 error`);
    await page.close(); return;
  }
  note("PASS", "R1 编译失败被如实呈现", `状态行=「${status.slice(0, 130)}」`);
  if (!rows.length) {
    note("FAIL", "R1b 失败但无结构化错误行", "状态行说失败，错误列表为空 —— 用户拿不到可点的行");
    await page.close(); return;
  }
  note("PASS", "R1b 结构化错误行就位", `${rows.length} 条可点行`);

  // 找 main.c 的**错误**行（path 字段是"../main.c"这类原始形态，line 字段常为空——
  // 行号落在行文本里，形如 `../main.c:5  ..\main.c(5): error: #29: expected an expression`）。
  // 第一版拿 line 字段比 5，比出来是空 → 误判"行号不符"；判据改从行文本里取。
  const errRowRe = /\.c:(\d+)\s+.*error:/i;
  const mainErr = rows.find((r) => /main\.c/.test(r.path) && errRowRe.test(r.text));
  const errLine = mainErr ? Number((mainErr.text.match(errRowRe) || [])[1]) : NaN;
  if (!mainErr) {
    note("FAIL", "R2 错误行里没有 main.c 的 error 条目", `行清单：${rows.map((r) => r.path + ":" + r.line + " " + r.text.slice(0, 60)).join(" | ")}`);
  } else if (errLine !== 5) {
    note("WARN", "R2 错误行号与注入位置不符", `注入在第 5 行（int x = ;），报告第 ${errLine} 行：${mainErr.text.slice(0, 130)}`);
  } else note("PASS", "R2 错误行号准确", `${mainErr.text.slice(0, 110)}`);

  // 点错误行 → 真跳行：读编辑器（.code-ta）里真实的光标位置
  if (mainErr) {
    // 注意：rows 是 evaluate 出来的**普通对象**，indexOf 拿不到 DOM 行的引用（第一版
    // 传 -1 → nth(-1) 落到第一条 = warning 行，于是"跳错行"是脚本自己的错）。
    const errIdx = rows.indexOf(mainErr);   // mainErr 就是 rows 里的元素，引用相等成立
    const clickRow = () => page.locator("#code-compile-errors .code-compile-error").nth(errIdx).click();
    if (errIdx < 0) {
      note("FAIL", "R3 找不到要点的错误行", `rows=${JSON.stringify(rows).slice(0, 200)}`);
    } else {
    await clickRow();
    await page.waitForTimeout(1500);
    const after = await page.evaluate(() => {
      const ta = document.querySelector("#code-viewer .code-edit .code-ta");
      const tabs = [...document.querySelectorAll("#code-tabs .code-tab-name")].map((b) => b.textContent.trim());
      return {
        hasEditor: !!ta,
        caret: ta ? ta.selectionStart : null,
        value: ta ? ta.value : null,
        tabs,
        gutterErrLines: document.querySelectorAll("#code-viewer .code-gutter-line.code-err-line").length,
      };
    });
    console.log(`  跳行后：编辑器=${after.hasEditor} tabs=${JSON.stringify(after.tabs)} 光标=${after.caret} gutter 错误行=${after.gutterErrLines}`);
    if (!after.hasEditor) {
      note("FAIL", "R3 点错误行没打开编辑器", `tabs=${JSON.stringify(after.tabs)} —— 错误行点下去没有把出错文件打开`);
    } else {
      const caretLine = (after.value || "").slice(0, after.caret).split("\n").length;
      if (caretLine !== 5) {
        note("FAIL", "R3 跳行落了错行", `光标在第 ${caretLine} 行（期望 5，注入位置）；gutter 错误行 ${after.gutterErrLines}`);
      } else note("PASS", "R3 跳行落到出错行", `光标第 ${caretLine} 行 = 注入位置；gutter 错误行 ${after.gutterErrLines}`);
      if (after.gutterErrLines === 0) note("WARN", "R3b gutter 无错误行色点", "当前文件有编译错误但行号栏没有色点（错误行标记可能没接上）");
      else note("PASS", "R3b gutter 错误行色点", `${after.gutterErrLines} 个色点`);
    }
    }
  }

  // 修复轮：LLM 端点被拦（502）→ 修复必须停住、报错可见、按钮可再点（不自激）
  const fixBtn = page.locator("#btn-code-compile-fix-here");
  if (await fixBtn.isVisible().catch(() => false)) {
    const n0 = calls.filter((c) => c.path.startsWith("/api/fix-errors")).length;
    await fixBtn.click();
    await page.waitForTimeout(3500);
    const n1 = calls.filter((c) => c.path.startsWith("/api/fix-errors")).length;
    await page.waitForTimeout(3000);
    const n2 = calls.filter((c) => c.path.startsWith("/api/fix-errors")).length;
    console.log(`  修复轮：fix-errors 请求 ${n0} → (3s) ${n1} → (再 3s) ${n2}`);
    if (n2 - n1 > 1) {
      note("FAIL", "R4 修复轮失败后自激重试", `LLM 端点恒 502 时后 3s 又打了 ${n2 - n1} 次 /api/fix-errors —— 与工单 09 的 expand 自激同型`);
    } else note("PASS", "R4 修复轮失败不自激", `6s 共 ${n2 - n0} 次请求`);
  } else {
    note("INFO", "R4 修复入口不可见", "「在此修复」按钮隐藏（判据 = 失败且非超时）；本轮无可测修复轮");
  }
  if (problems.length) note("FAIL", "R 控制台/页面错误", problems.join(" | "));
  await page.close();
}

// ===========================================================================
// W. 生成 → 输出目录 → 覆盖确认
// ===========================================================================
async function testW() {
  console.log("\n=== W. 生成 → 输出目录 → 覆盖确认 ===");
  const { page, problems, calls } = await newPage();
  await pickPlatform(page, "STM32");
  await addModules(page, ["motor"]);
  await manualOutput(page);
  await page.fill("#problem", "");           // 零 LLM
  await page.waitForTimeout(200);

  // ---- W0 前置：就绪检查单（真点「检查能否生成」，判据来自真 DOM）----
  await page.click("#btn-readiness-check");
  await page.waitForTimeout(700);
  const readiness = await page.evaluate(() =>
    [...document.querySelectorAll("#readiness-check .rc-row")].map((r) => ({
      step: r.dataset.step, cls: r.className, text: r.innerText.replace(/\s+/g, " ").trim().slice(0, 100),
    })));
  console.log(`  就绪检查单 ${readiness.length} 行：`);
  readiness.forEach((r) => console.log(`    [${r.cls.includes("bad") ? "✗" : r.cls.includes("soft") ? "⚠" : "✓"}] ${r.step} ${r.text}`));

  const outDir = join(TMP, "W-manual");
  await page.fill("#output-dir", outDir);
  await page.waitForTimeout(700);

  // ---- W1 首次生成：真落盘 ----
  await page.fill("#main-c", "int main(void) { return 0; }");
  await page.waitForTimeout(200);
  const g1 = await runGenerate(page, calls);
  const files = existsSync(outDir) ? readdirSync(outDir).sort() : [];
  console.log(`  首次生成：blocked=${g1.blocked} res-dir=「${g1.resDir}」msg=「${g1.msg.slice(0, 150)}」产物 ${files.length} 项`);
  if (g1.blocked) {
    note("FAIL", "W1 生成被前置校验拦下", `#generate-msg=「${g1.msg}」——就绪检查单与生成前置同源，说明步骤前置条件没满足`);
    await page.close(); return;
  }
  if (g1.resDir !== outDir) note("FAIL", "W1 结果区目录 ≠ 请求目录", `请求 ${outDir}，显示「${g1.resDir}」`);
  else note("PASS", "W1 结果区目录一致", g1.resDir);
  if (!existsSync(join(outDir, "main.c"))) note("FAIL", "W1 产物缺 main.c", `目录里：${files.join(", ")}`);
  else note("PASS", "W1 产物落地", `${files.length} 项，含 main.c`);

  // ---- W2 手动目录二次生成：必须拒绝 + 不静默改名 ----
  // 口径（源码确认 webapp._resolve_generation_output_dir:1097）：手动目录 verdict 恒为
  // "manual"，**覆盖确认分支只对桌面 verdict=="exists" 生效**——手动目录非空 =
  // generate_project 非空检查兜底 400。所以判据是「拒绝 + 不改名 + 有说明」，
  // 不是「弹覆盖确认」（第一版按后者写，属误报）。
  const dirsNow = existsSync(TMP) ? readdirSync(TMP).filter((n) => n.startsWith("W-manual")) : [];
  const g2 = await runGenerate(page, calls);
  console.log(`  手动目录二次生成：msg=「${g2.msg.slice(0, 200)}」；目录=${JSON.stringify(dirsNow)}`);
  if (dirsNow.length > 1) note("FAIL", "W2 静默改名攒目录", `同名生成后出现 ${dirsNow.length} 个目录：${dirsNow.join(", ")} —— 护栏失效`);
  else note("PASS", "W2 未静默改名", `仍只有 ${dirsNow.join(", ")}`);
  if (!g2.msg) note("FAIL", "W2 手动目录被拒却无说明", "第二次生成失败但 #generate-msg 为空");
  else if (!/已存在|非空|拒绝/.test(g2.msg)) note("WARN", "W2 拒绝原因不明", `#generate-msg=「${g2.msg.slice(0, 160)}」`);
  else note("PASS", "W2 拒绝原因如实呈现", `「${g2.msg.slice(0, 150)}」`);
  // 旧工程必须没被动过
  if (!existsSync(join(outDir, "main.c"))) note("FAIL", "W2 被拒却破坏了原目录", "main.c 不见了");
  else note("PASS", "W2 被拒后原工程完好", "main.c 仍在");

  // ---- W2b 桌面模式覆盖确认链路：注入真实冲突 400 → 必须弹确认 ----
  // 为什么不真在桌面造目录：会往用户桌面写东西（工作区规范禁止）。注入的 400 文案
  // 逐字取自 webapp.GenerationConflictError 模板（前缀与 fx/generate.js 的
  // CONFLICT_MSG_PREFIX 单源锚定，有 tests/test_webapp.py 结构测试兜底）；第二次
  // 请求放行到真后端（写临时目录）——前端「识别冲突 → 弹确认 → 重发」三步全真。
  const injectDir = join(TMP, "W-inject");
  const conflictDetail = "桌面上已有同名工程「" + injectDir.split(/[\\/]/).pop() + "」：为避免覆盖你的已有工程，"
    + "请先删除该目录或修改题名后再生成（不会自动改名或覆盖）。";
  let injected = 0;
  await page.unroute("**/api/generate");
  await page.route("**/api/generate", async (route) => {
    if (injected === 0) {
      injected++;
      return route.fulfill({ status: 400, contentType: "application/json", body: JSON.stringify({ detail: conflictDetail }) });
    }
    return route.continue();
  });
  await page.fill("#output-dir", injectDir);
  await page.waitForTimeout(250);
  await page.click("#btn-generate");
  await page.waitForTimeout(3000);
  const injectMsg = (await page.locator("#generate-msg").innerText().catch(() => "")).trim();
  const lastBody = ((calls.filter((c) => c.path === "/api/generate").pop() || {}).body) || "{}";
  const gateHit = injected > 0 && JSON.parse(lastBody).output_dir === injectDir;
  console.log(`  注入闸门：命中=${gateHit}（injected=${injected}）；#generate-msg=「${injectMsg.slice(0, 200)}」`);
  await page.waitForSelector(".ref-files-overlay [data-confirm-ok]", { timeout: 6000 }).catch(() => {});
  const modalOpen = await page.locator(".ref-files-overlay").count();
  if (!gateHit) {
    note("FAIL", "W2b 注入闸门没命中", "请求体 output_dir 不是注入目录 —— 弹窗判据不成立（脚本问题，非产品问题）");
  } else if (!modalOpen) {
    note("FAIL", "W2b 冲突 400 未弹覆盖确认", `注入真冲突文案（与 webapp.GenerationConflictError 逐字同形）没触发确认弹窗，`
      + `#generate-msg=「${injectMsg.slice(0, 220)}」—— isConflictError 前缀判据或弹窗链路断了：桌面同名工程将无法覆盖生成`);
  } else {
    const modalText = await page.locator(".ref-files-overlay").first().innerText().catch(() => "");
    console.log(`    确认弹窗文案：「${modalText.replace(/\s+/g, " ").slice(0, 260)}」`);
    if (!/\.bak/.test(modalText)) note("WARN", "W2b 弹窗未说明备份去向", `文案里没有 .bak：「${modalText.replace(/\s+/g, " ").slice(0, 160)}」`);
    else note("PASS", "W2b 弹窗说明了 .bak 去向", "");
    // 取消支路
    const before = calls.filter((c) => c.path === "/api/generate").length;
    await page.locator("[data-confirm-cancel]").first().click();
    await page.waitForTimeout(900);
    const after = calls.filter((c) => c.path === "/api/generate").length;
    const msgCancel = (await page.locator("#generate-msg").innerText().catch(() => "")).trim();
    if (after !== before) note("FAIL", "W2b 取消覆盖仍重发了生成", `取消后 /api/generate 请求数 ${before} → ${after}`);
    else note("PASS", "W2b 取消覆盖不重发", "取消后没有第二次生成请求");
    if (!msgCancel) note("FAIL", "W2b 取消后界面无说明", "取消覆盖后 #generate-msg 为空");
    else note("PASS", "W2b 取消后有说明", `「${msgCancel.slice(0, 160)}」`);
    // 确认支路：重发必须带 overwrite:true，且真写盘
    // 注意：注入闸门只吃**第一次**请求（`injected` 只在 0 时改写），用户的第二次
    // 尝试同样会撞上真冲突 400 → 必须再弹一次确认。所以这里不重置 `injected` ——
    // 重置会让第二次请求直奔后端（那是另一种用例：确认之后的重发本身）。
    // 第 2 次：注入闸门已放行 → 这次请求直奔真后端，用真实「目录已存在且非空」400
    const n2 = calls.filter((c) => c.path === "/api/generate").length;
    await page.click("#btn-generate");
    await page.waitForTimeout(3000);
    const modal2 = await page.locator(".ref-files-overlay").count();
    const msg2 = (await page.locator("#generate-msg").innerText().catch(() => "")).trim();
    console.log(`  第 2 次尝试：请求数 +${calls.filter((c) => c.path === "/api/generate").length - n2}；确认弹窗=${modal2}；msg=「${msg2.slice(0, 200)}」`);
    if (modal2) {
      // 又弹了 = 用户还能继续选择覆盖；按确认走完，验重发带 overwrite:true
      await page.locator("[data-confirm-ok]").first().click();
      await page.waitForFunction(() => !document.getElementById("btn-generate").disabled, undefined, { timeout: 180000 });
      await page.waitForTimeout(700);
    } else {
      note("INFO", "W2c 第 2 次未再弹确认（真后端拒绝的原因不必覆盖）",
        `msg=「${msg2.slice(0, 180)}」—— 手动目录的拒绝理由是「目录已存在且非空」，不是「桌面同名工程」，`
        + `故 isConflictError 不命中，属实（覆盖通道只服务桌面模式）`);
    }
    const reqs = calls.filter((c) => c.path === "/api/generate").map((c) => JSON.parse(c.body || "{}"));
    const last = reqs[reqs.length - 1];
    const wrote = existsSync(join(injectDir, "main.c"));
    console.log(`  确认覆盖支路终态：最后一次请求 overwrite=${last && last.overwrite}；写盘=${wrote}`);
    if (modal2) {
      if (!last || last.overwrite !== true) note("FAIL", "W2c 确认覆盖未带 overwrite:true", `最后一次请求体：${JSON.stringify(last).slice(0, 300)}`);
      else note("PASS", "W2c 确认覆盖带了 overwrite:true", "");
    }
  }
  await page.unroute("**/api/generate");

  // ---- W3 输出目录预览：落盘前不得有副作用 ----
  const previewDir = join(TMP, "W-preview");
  const pre = await page.evaluate(async (d) => {
    const r = await fetch("/api/generate/preview-dir", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ output_dir: d }),
    });
    return { status: r.status, json: await r.json() };
  }, previewDir);
  if (existsSync(previewDir)) note("FAIL", "W3 预览端点有副作用", `/api/generate/preview-dir 把目录建出来了：${previewDir}`);
  else note("PASS", "W3 预览端点无副作用", `verdict=${pre.json && pre.json.verdict}，目录未创建`);

  if (problems.length) note("FAIL", "W 控制台/页面错误", problems.join(" | "));
  await page.close();
}

// ===========================================================================
// X. 模块库 CRUD
// ===========================================================================
async function testX() {
  console.log("\n=== X. 模块库 CRUD ===");
  const { page, problems, calls } = await newPage();
  const slug = "zz_audit_probe_mod";
  const modDir = join(server.repoRoot, "library", "modules", slug);
  rmSync(modDir, { recursive: true, force: true });       // 上一轮残留兜底

  // ---- X1 录入表单的失败路径（LLM 校验端点被拦 → 502/400）----
  await page.locator('nav button[data-tab="library"]').click();
  await page.waitForTimeout(500);
  await page.fill("#new-slug", slug);
  await page.fill("#new-desc", "审计探针模块：仅用于真机审计，用后即删。适用于验证模块库 CRUD 链路。");
  await page.waitForTimeout(200);
  await page.evaluate(() => {
    // 文件行形态（ui/files.js addFileRow）：容器内 `input[placeholder^="文件名"]` +
    // `textarea[placeholder^="文件内容"]`。第一版用 `#new-files input` 撞上了别的节点，
    // 结果 collectFiles 收空 → 表单本地拦下（"至少需要一个源文件"），X1 变成假红。
    const nameI = document.querySelector('#new-files input[placeholder^="文件名"]');
    const bodyT = document.querySelector('#new-files textarea[placeholder^="文件内容"]');
    if (nameI) { nameI.value = "probe.c"; nameI.dispatchEvent(new Event("input", { bubbles: true })); }
    if (bodyT) { bodyT.value = "int probe(void){return 1;}\n"; bodyT.dispatchEvent(new Event("input", { bubbles: true })); }
    window.__probeFileRow = { name: !!nameI, body: !!bodyT };
  });
  const fileRow = await page.evaluate(() => window.__probeFileRow);
  if (!fileRow || !fileRow.name || !fileRow.body) {
    note("FAIL", "X1 录入表单的文件行没填上", `name=${fileRow && fileRow.name} body=${fileRow && fileRow.body}（选择器口径需确认）`);
  }
  await page.waitForTimeout(200);
  await page.click("#btn-add-module-submit");
  // 等真终态：入库走 LLM 一致性校验（`_retry_parse` 会整次重试），502 也可能要
  // 好几秒才回到界面 —— 固定 sleep 会把"还在路上"读成"没提示"（第一版就误报过）。
  await page.waitForFunction(
    () => document.getElementById("add-msg").textContent.trim().length > 0
      || document.querySelectorAll("#toast-root .toast").length > 0,
    undefined, { timeout: 30000 },
  ).catch(() => {});
  await page.waitForTimeout(300);
  const addMsg = (await page.locator("#add-msg").innerText().catch(() => "")).trim();
  const toastTxt = (await page.locator("#toast-root").innerText().catch(() => "")).replace(/\s+/g, " ").trim();
  const addReq = calls.filter((c) => c.method === "POST" && c.path === "/api/modules").pop();
  console.log(`  提交后 #add-msg=「${addMsg.slice(0, 180)}」toast=「${toastTxt.slice(0, 120)}」`);
  console.log(`  POST /api/modules 载荷 = ${addReq ? addReq.body.slice(0, 260) : "（没发请求）"}`);
  if (!addReq) note("FAIL", "X1 提交没发请求", `#add-msg=「${addMsg}」——表单校验拦在本地了还是没绑上？`);
  else if (!addMsg) note("FAIL", "X1 入库失败无提示", "POST /api/modules 失败但 #add-msg 与 toast 都为空");
  else note("PASS", "X1 入库失败有中文提示", `「${addMsg.slice(0, 150)}」`);
  const submitDisabled = await page.locator("#btn-add-module-submit").isDisabled().catch(() => false);
  if (submitDisabled) note("FAIL", "X1b 入库失败后按钮卡禁用", "用户无法重试");
  else note("PASS", "X1b 入库失败后按钮可点", "");

  // ---- X2 造库 + 列表可见（走文件系统：POST /api/modules 必调 LLM，不为测验烧额度）----
  // 「目录即数据库」是这个库的设计（CONTEXT.md 词表：库目录即数据库），所以手工放一个
  // 最小模块目录等价于真实场景。
  try {
    mkdirSync(join(modDir, "code"), { recursive: true });
    writeFileSync(join(modDir, "code", "probe.c"), "int probe(void){return 1;}\n");
    writeFileSync(join(modDir, "manifest.json"), JSON.stringify({
      slug,
      description: "审计探针模块（真机审计用，结束即删）：验证模块库列表 / 编辑 / 删除链路。适用于审计用例。",
      dependencies: [],
      platforms: { stm32: { files: ["code/probe.c"], verified: true, hardware_bound: false, notes: "", pins: [] } },
    }, null, 2));
  } catch (e) { note("FAIL", "X2 造库失败", e.message); }
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator('nav button[data-tab="library"]').click();
  await page.waitForTimeout(900);
  await page.fill("#lib-search", slug);
  await page.waitForTimeout(700);
  const searchText = (await page.locator("#lib-rows").innerText().catch(() => "")).replace(/\s+/g, " ");
  console.log(`  搜索「${slug}」→「${searchText.slice(0, 220)}」`);
  if (!searchText.includes(slug)) note("FAIL", "X2 新模块未出现在列表", `磁盘上模块已就位（目录即数据库），列表里搜不到 —— 模块库要重启才认？`);
  else note("PASS", "X2 新模块进了列表", `搜到「${slug}」`);

  // ---- X3 编辑简介的失败路径：LLM 校验 502 → 就地报错、弹窗不关、磁盘不动 ----
  // ⚠「校验失败不写回」这件事本身由 tests/test_library.py 的确定性用例守着，本脚本
  // 只是不花额度地再确认 UI 面（弹窗/提示/按钮三态）。
  const editBtn = page.locator(`#lib-rows button[data-edit-desc="${slug}"]`);
  if (!(await editBtn.count())) {
    note("WARN", "X3 新模块没有「改简介」按钮", "列表行里找不到 data-edit-desc");
  } else {
    await editBtn.first().click();
    await page.waitForSelector(".lib-edit-overlay .lib-edit-text", { timeout: 8000 }).catch(() => {});
    const ta = page.locator(".lib-edit-overlay .lib-edit-text");
    if (!(await ta.count())) {
      note("WARN", "X3 编辑弹窗没有 .lib-edit-text", "选择器口径需确认");
    } else {
      await ta.fill("审计改写后的简介（不应落盘，因为 AI 校验端点被拦）。适用于审计用例。");
      await page.locator(".lib-edit-overlay .lib-edit-save").click();
      // 同 X1：等真终态（失败就地报错 → 保存按钮复位），别用固定 sleep
      await page.waitForFunction(
        () => {
          const o = document.querySelector(".lib-edit-overlay");
          if (!o) return true;
          const btn = o.querySelector(".lib-edit-save");
          return (o.querySelector(".lib-edit-msg").textContent.trim().length > 0)
            || (btn && !btn.disabled);
        }, undefined, { timeout: 30000 },
      ).catch(() => {});
      await page.waitForTimeout(300);
      const msg = (await page.locator(".lib-edit-overlay .lib-edit-msg").innerText().catch(() => "")).trim();
      const stillOpen = await page.locator(".lib-edit-overlay").count();
      const saveDisabled = await page.locator(".lib-edit-overlay .lib-edit-save").isDisabled().catch(() => null);
      const manifestNow = JSON.parse(readFileSync(join(modDir, "manifest.json"), "utf8"));
      console.log(`  编辑简介失败：弹窗仍在=${stillOpen} 保存 disabled=${saveDisabled}；msg=「${msg.slice(0, 160)}」；磁盘 description 开头=「${manifestNow.description.slice(0, 26)}」`);
      if (!msg) note("FAIL", "X3 AI 校验失败无就地提示", "PUT 打 502/400，弹窗里 .lib-edit-msg 为空 —— 用户按了保存没有任何反馈");
      else note("PASS", "X3 AI 校验失败有就地提示", `「${msg.slice(0, 130)}」`);
      if (!stillOpen) note("FAIL", "X3 校验失败却关闭了弹窗", "失败时弹窗被关掉，用户的输入丢了（成功/失败无法区分）");
      else note("PASS", "X3 失败时弹窗保留", "输入还在，可改后重试");
      if (saveDisabled) note("FAIL", "X3 校验失败后保存按钮卡禁用", "无法重试");
      else note("PASS", "X3 失败后保存按钮可点", "");
      if (manifestNow.description.startsWith("审计改写后")) note("FAIL", "X3 AI 校验失败却写回了简介", "磁盘 description 被改了 —— 一致性校验形同虚设");
      else note("PASS", "X3 AI 校验失败未写回", "磁盘 description 未被改动");
      await page.locator(".lib-edit-overlay .lib-edit-cancel").click().catch(() => {});
      await page.waitForTimeout(300);
    }
  }

  // ---- X4 删除：二次确认 + 真删目录 ----
  const delBtn = page.locator(`#lib-rows button[data-del="${slug}"]`);
  if (!(await delBtn.count())) {
    note("WARN", "X4 新模块没有删除按钮", "找不到 data-del");
  } else {
    await delBtn.first().click();
    await page.waitForSelector(".ref-files-overlay [data-confirm-ok]", { timeout: 8000 }).catch(() => {});
    const confirm = page.locator(".ref-files-overlay [data-confirm-ok]").first();
    if (await confirm.count()) {
      const dlg = (await page.locator(".ref-files-overlay").first().innerText().catch(() => "")).replace(/\s+/g, " ");
      console.log(`  删除确认弹窗：「${dlg.slice(0, 170)}」`);
      await confirm.click();
      await page.waitForTimeout(2000);
      if (existsSync(modDir)) note("FAIL", "X4 确认删除后目录还在", modDir);
      else note("PASS", "X4 确认删除真删了目录", modDir);
    } else {
      note("FAIL", "X4 删除没有确认弹窗", "危险动作没有二次确认 —— 误点即永久丢失模块");
    }
  }
  rmSync(modDir, { recursive: true, force: true });   // 兜底：探针目录绝不留在真库

  if (problems.length) note("FAIL", "X 控制台/页面错误", problems.join(" | "));
  await page.close();
}

// ===========================================================================
// Y. 代码编辑器 / AI 面板的失败路径
// ===========================================================================
async function testY() {
  console.log("\n=== Y. 代码编辑器 / AI 面板失败路径 ===");
  const outDir = join(TMP, "Y-stm32");
  const { page, problems, calls } = await newPage();
  await pickPlatform(page, "STM32");
  await addModules(page, ["motor"]);
  await page.fill("#problem", "");
  await manualOutput(page);
  await page.fill("#output-dir", outDir);
  await page.fill("#main-c", "int main(void) { return 0; }");
  await page.waitForTimeout(200);
  const g = await runGenerate(page, calls);
  console.log(`  Y 前置生成：blocked=${g.blocked} msg=「${g.msg.slice(0, 160)}」`);
  if (!existsSync(join(outDir, "main.c"))) { note("FAIL", "Y 前置生成失败", outDir + " 无 main.c"); await page.close(); return; }

  // 打开代码栏：目录标签先就位、树随后才出（异步基线探测）——两段都等
  await page.evaluate(async (dir) => {
    const mod = await import("/js/ui/codeview.js");
    mod.openCodeViewer(dir);
  }, outDir);
  const dirLoaded = await page.waitForFunction(
    (d) => document.getElementById("code-dir-label").textContent === d, outDir, { timeout: 15000 },
  ).then(() => true).catch(() => false);
  const compileDisabled = await page.locator("#btn-code-compile").isDisabled().catch(() => null);
  console.log(`  代码栏：目录标签 loaded=${dirLoaded}；编译按钮 disabled=${compileDisabled}`);
  if (!dirLoaded) note("FAIL", "Y0 代码栏打不开生成的工程目录", "目录标签没跟上 —— 树/编译/编辑全部走不下去");
  if (compileDisabled) note("FAIL", "Y0b 目录已打开但「编译」按钮仍禁用", "用户点不了编译");
  await page.waitForFunction(
    () => !document.getElementById("code-tree").innerText.includes("加载中"), undefined, { timeout: 20000 },
  ).catch(() => {});
  await page.waitForTimeout(400);
  const treeTxt = (await page.locator("#code-tree").innerText().catch(() => "")).replace(/\s+/g, " ");
  console.log(`  树：「${treeTxt.slice(0, 140)}」`);

  // 打开 main.c（真点树；编辑器 = .code-edit .code-ta）
  // 两级策略：先用**真鼠标在文件名上点**（最贴近用户动作：hover 让行操作按钮显形，
  // 再点名字），超时 → 诊断命中点元素，再退到 JS 委托点击兜底。
  const treeItem = page.locator('#code-tree .code-tree-btn[data-code-file="main.c"]').first();
  if (!(await treeItem.count())) {
    note("WARN", "Y1 树上没有 main.c 节点", "data-code-file 选择器未命中（树结构或文件名口径需确认）");
  } else {
    // ① 真鼠标路径：hover 行 → 点文件名文字区（playwright 的 hover/click 自带
    //    可操作性检查 —— 被别的元素接走就超时，这本身就是「点不开」的证据）
    let mouseOpened = false;
    let blocked = "";
    try {
      await treeItem.hover({ timeout: 6000 });
      await page.waitForTimeout(200);
      const box = await treeItem.boundingBox();
      const pt = box ? { x: box.width * 0.4, y: box.height / 2 } : { x: 10, y: 8 };
      await treeItem.click({ position: pt, timeout: 8000 });
      // 点击是同步派发、编辑器是**异步**加载（loadFileState → fetch → 渲染），
      // 所以必须等编辑器出现，不能点完立刻查 DOM（第一版就栽在这：判成"打不开"）
      mouseOpened = await page.waitForSelector("#code-viewer .code-edit .code-ta", { timeout: 10000 })
        .then(() => true).catch(() => false);
      if (!mouseOpened) {
        await treeItem.click({ position: pt, timeout: 8000 }).catch(() => {});
        mouseOpened = await page.waitForSelector("#code-viewer .code-edit .code-ta", { timeout: 10000 })
          .then(() => true).catch(() => false);
        if (!mouseOpened) blocked = "点两次都没反应（无报错但编辑器没出）";
      }
    } catch (e) {
      blocked = (e.message || String(e)).split("\n")[0];
    }
    if (!mouseOpened) {
      const why = await page.evaluate(() => {
        const el = document.querySelector('#code-tree .code-tree-btn[data-code-file="main.c"]');
        if (!el) return { miss: "节点不在" };
        const r = el.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width * 0.4, r.top + r.height / 2);
        const row = el.closest(".code-tree-file");
        const act = row ? row.querySelector(".code-tree-actions") : null;
        const ar = act ? act.getBoundingClientRect() : null;
        return {
          hit: hit ? hit.tagName + "." + String(hit.className || "").split(" ")[0] : "（无）",
          rowRect: { x: Math.round(r.x), w: Math.round(r.width) },
          actionsRect: ar ? { x: Math.round(ar.x), w: Math.round(ar.width), h: Math.round(ar.height) } : null,
          coverPct: ar ? Math.round(Math.max(0, Math.min(ar.right, r.right) - ar.left) / r.width * 100) : 0,
        };
      });
      note("FAIL", "Y1 鼠标点文件名打不开文件", `hover/click 被拦（${blocked}）；行内 40% 处的命中元素 = ${why.hit}`
        + `；行宽 ${why.rowRect && why.rowRect.w}px，行内操作按钮容器 ${JSON.stringify(why.actionsRect)}`
        + `（横向覆盖行的 ${why.coverPct}%）—— 用户点文件名没有任何反应`);
      await treeItem.click({ force: true });   // 兜底：JS 派发走同一委托，继续验后面的判据
      await page.waitForTimeout(1400);
    } else {
      note("PASS", "Y1 鼠标点文件名打得开", "hover → 点文件名文字区 → 编辑器就位");
    }
  }
  const editor = "#code-viewer .code-edit .code-ta";
  const editorOpen = await page.evaluate((sel) => !!document.querySelector(sel), editor);

  // ---- Y1/Y2 保存失败：/api/code/save 拦成 500 → 必须报错、内容不丢、盘上确实没写 ----
  await page.route("**/api/code/save", (route) => route.fulfill({
    status: 500, contentType: "application/json", body: JSON.stringify({ detail: "磁盘写入失败（审计注入）" }),
  }));
  if (!editorOpen) {
    note("FAIL", "Y1 编辑器没打开", "点树上的 main.c 之后 #code-viewer 里没有 .code-ta —— 保存失败路径测不到");
  } else {
    await page.evaluate((sel) => {
      const ta = document.querySelector(sel);
      ta.focus();
      ta.value = ta.value + "\n// 审计注入的一行\n";
      ta.dispatchEvent(new Event("input", { bubbles: true }));
    }, editor);
    await page.keyboard.press("Control+s");
    await page.waitForTimeout(2200);
    const afterVal = await page.evaluate((sel) => {
      const ta = document.querySelector(sel);
      return ta ? ta.value : null;
    }, editor);
    const toastTxt = (await page.locator("#toast-root").innerText().catch(() => "")).replace(/\s+/g, " ").trim();
    const disk = readFileSync(join(outDir, "main.c"), "utf8");
    console.log(`  保存失败：toast=「${toastTxt.slice(0, 150)}」；磁盘含注入行=${disk.includes("审计注入的一行")}`);
    if (!toastTxt) note("FAIL", "Y1 保存失败无任何提示", "Ctrl+S 打后端 500，界面上既没 toast 也没行内提示");
    else note("PASS", "Y1 保存失败有提示", `「${toastTxt.slice(0, 130)}」`);
    if (afterVal == null || !afterVal.includes("审计注入的一行")) {
      note("FAIL", "Y2 保存失败后编辑内容被吞", "保存 500 之后编辑器里的未保存内容丢了（用户白改）");
    } else note("PASS", "Y2 保存失败不丢内容", "编辑器里仍保留未保存的一行");
    if (disk.includes("审计注入的一行")) note("FAIL", "Y2b 保存声明失败但盘上真写了", "500 之后磁盘上出现了注入行（失败语义不诚实）");
    else note("PASS", "Y2b 保存失败盘上确实没写", "");
  }
  await page.unroute("**/api/code/save");

  // ---- Y3 编译失败：/api/compile 500 → 状态行有原因、按钮可点、不自激 ----
  // 前置：编辑器/沙盒状态可能已被 Y1 的失败带歪（树点不开 → 没有目录上下文），
  // 此时点编译只会 30s 超时——那是级联噪声，不是新事实，故先探测可点性。
  const compileClickable = await page.locator("#btn-code-compile").isEnabled().catch(() => false);
  if (!compileClickable) {
    note("WARN", "Y3 编译按钮不可点", "前置步骤没把目录/编辑器就绪 —— 编译失败路径本轮未测（级联，非新事实）");
    if (problems.length) note("FAIL", "Y 控制台/页面错误", problems.join(" | "));
    await page.close(); return;
  }
  await page.route("**/api/compile", (route) => route.fulfill({
    status: 500, contentType: "application/json", body: JSON.stringify({ detail: "编译启动失败（审计注入）" }),
  }));
  const c0 = calls.filter((c) => c.path === "/api/compile").length;
  await page.click("#btn-code-compile");
  await page.waitForTimeout(2500);
  const c1 = calls.filter((c) => c.path === "/api/compile").length;
  await page.waitForTimeout(2500);
  const c2 = calls.filter((c) => c.path === "/api/compile").length;
  const st = (await page.locator("#code-compile-status").innerText().catch(() => "")).trim();
  const cdisabled = await page.locator("#btn-code-compile").isDisabled().catch(() => false);
  console.log(`  编译 500：请求 ${c0} → (2.5s) ${c1} → (再 2.5s) ${c2}；状态行=「${st}」；按钮 disabled=${cdisabled}`);
  if (!st) note("FAIL", "Y3 编译失败状态行为空", "点了编译打 500，面板状态行没有任何文字");
  else note("PASS", "Y3 编译失败有状态行", `「${st.slice(0, 150)}」`);
  if (cdisabled) note("FAIL", "Y3b 编译失败后按钮卡禁用", "用户无法重试");
  else note("PASS", "Y3b 编译失败后按钮可点", "");
  if (c2 - c1 > 1) note("FAIL", "Y3c 编译失败自激重试", `后 2.5s 又打了 ${c2 - c1} 次 /api/compile`);
  else note("PASS", "Y3c 编译失败不自激", `5s 共 ${c2 - c0} 次请求`);
  await page.unroute("**/api/compile");

  // ---- Y4 推荐（AI 面板）失败：LLM 502 → 必须报错、按钮恢复、不自激、横幅收起 ----
  const r0 = calls.filter((c) => c.path === "/api/recommend").length;
  await page.locator('nav button[data-tab="generate"]').click();
  await page.fill("#problem", "1. 检测物体是否经过。2. 沿黑线行驶。");
  await page.waitForTimeout(300);
  await page.click("#btn-recommend");
  await page.waitForTimeout(3000);
  const r1 = calls.filter((c) => c.path === "/api/recommend").length;
  await page.waitForTimeout(3000);
  const r2 = calls.filter((c) => c.path === "/api/recommend").length;
  const recDisabled = await page.locator("#btn-recommend").isDisabled().catch(() => false);
  const recMsg = (await page.evaluate(() => {
    const el = document.querySelector("#rec-list, #recommend-msg, #generate-msg");
    return el ? el.innerText.replace(/\s+/g, " ") : "";
  })).trim();
  const banner = await page.locator(".ai-action-banner:not(.hidden), #ai-action").count();
  console.log(`  推荐 502：请求 ${r0} → (3s) ${r1} → (再 3s) ${r2}；按钮 disabled=${recDisabled}；横幅在=${banner}`);
  console.log(`    界面文本=「${recMsg.slice(0, 200)}」`);
  if (!recMsg) note("FAIL", "Y4 推荐 LLM 失败无任何界面反馈", "点了推荐打 502，界面上没有报错文本");
  else note("PASS", "Y4 推荐失败有反馈", `「${recMsg.slice(0, 150)}」`);
  if (recDisabled) note("FAIL", "Y4b 推荐失败后按钮卡禁用", "用户无法重试");
  else note("PASS", "Y4b 推荐失败后按钮可点", "");
  if (r2 - r1 > 1) note("FAIL", "Y4c 推荐失败自激重试", `后 3s 又打了 ${r2 - r1} 次 /api/recommend`);
  else note("PASS", "Y4c 推荐失败不自激", `6s 共 ${r2 - r0} 次请求`);
  if (banner) note("FAIL", "Y4d 失败后 AI 横幅没收起", "推荐已终态（502）但「AI 行动中」横幅仍在 —— 界面谎报忙");
  else note("PASS", "Y4d 失败后横幅已收起", "");

  if (problems.length) note("FAIL", "Y 控制台/页面错误", problems.join(" | "));
  await page.close();
}

// ===========================================================================
async function main() {
  server = await startServer();
  server.repoRoot = process.cwd();
  browser = await chromium.launch();
  TMP = mkdtempSync(join(tmpdir(), "firstep-gen-audit-"));
  console.log(`后端就绪：${server.url}\n临时工程根：${TMP}`);
  const only = process.argv.slice(2).map((s) => s.toUpperCase());
  const run = async (name, fn) => {
    if (only.length && !only.includes(name)) return;
    try { await fn(); }
    catch (e) { note("FAIL", `${name} 用例崩溃`, (e.message || String(e)).split("\n").slice(0, 4).join(" / ")); }
  };
  try {
    await run("P", testP);
    await run("R", testR);
    await run("W", testW);
    await run("X", testX);
    await run("Y", testY);
  } finally {
    await browser.close();
    await server.stop();
    // 临时目录清掉（不污染用户桌面 / 仓库）；失败也清，证据已打在 stdout。
    // Windows：刚 taskkill 掉的服务/浏览器进程句柄释放晚于本收尾（实测
    // `EPERM Permission denied`），node:fs 的 maxRetries 退避窗口不够 → 自己再退避重试。
    for (let i = 0; i < 10; i++) {
      try { rmSync(TMP, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }); break; }
      catch (e) {
        if (i === 9) console.log(`（临时目录清理失败，句柄未释放，可手动删：${TMP}）`);
        else await new Promise((r) => setTimeout(r, 300));
      }
    }
  }
  const bad = findings.filter((f) => f.level === "FAIL");
  const warn = findings.filter((f) => f.level === "WARN");
  const info = findings.filter((f) => f.level === "INFO");
  console.log("\n================ 结论 ================");
  console.log(`FAIL ${bad.length} 条 / WARN ${warn.length} 条 / INFO ${info.length} 条 / PASS ${findings.length - bad.length - warn.length - info.length} 条`);
  for (const f of [...bad, ...warn, ...info]) console.log(`- [${f.level}] ${f.area}：${f.detail}`);
  if (bad.length) process.exitCode = 2;
}

await main();
