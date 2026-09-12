// 功能组卡「必须由用户显式选择」的**真机冒烟**（工单 group-choice-required/01）。
//
// 跑在真服务（8000）+ 真 Chrome（CDP 9251）+ 真页面模块上，载荷用真库现算的 fixture
// （`.scratch/group-choice-required/payload.json`，由 make-payload.py 生成）——零额度、
// 不需要真 LLM 就能验「用户看得见的那部分」：
//   ① 卡里没有任何勾选 + 标题挂「请选择」 + 需求句灰注写「（请选择）」
//   ② 点一下成员 → 选中它、徽标消失、集合换成它、灰注改说「已由…替代」
//   ③ 未选时：就绪检查单把它列为未就绪项（点生成会被拦在这里）
//   ④ 未选时直接打后端 /api/generate → 400（服务端同源守门），且不产生输出目录
//   ⑤ 换选后生成集合不带同组旧成员
//
// 退出码：0 全绿 / 1 断言失败 / 2 传输层或脚本异常（与仓库其它冒烟脚本同口径）。
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { connect, pageTarget, rebuildTab } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const CDP = 9251;
const PAGE = "http://127.0.0.1:8000/";
const OUT = join(ROOT, "group-choice-required");
const payload = JSON.parse(readFileSync(join(OUT, "payload.json"), "utf8"));

const EXIT_ASSERT_FAIL = 1;
const EXIT_TRANSPORT = 2;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const bail = (kind) => (e) => {
  console.error(`TRANSPORT(${kind}) ${String((e && e.stack) || e).split("\n").slice(0, 4).join("\n  ")}`);
  process.exit(EXIT_TRANSPORT);
};
process.on("unhandledRejection", bail("unhandledRejection"));
process.on("uncaughtException", bail("uncaughtException"));

let pass = 0;
let fail = 0;
const check = (name, ok, detail = "") => {
  if (ok) { pass += 1; console.log(`PASS ${name}${detail ? "  " + detail : ""}`); }
  else { fail += 1; console.log(`FAIL ${name}${detail ? "  " + detail : ""}`); }
};

async function main() {
  let target = null;
  for (let i = 0; i < 50 && !target; i++) {
    target = await pageTarget({ port: CDP, pageUrl: PAGE, anyPage: true });
    if (!target) await sleep(300);
  }
  if (!target) { console.error("CDP 不可达（期望 9251 上有 Chrome）"); process.exit(EXIT_TRANSPORT); }
  await rebuildTab({ port: CDP, pageUrl: PAGE });
  const cdp = await connect({ port: CDP, pageUrl: PAGE, timeoutMs: 20000 });
  const { Eval } = cdp;
  const waitFor = async (expr, ms = 8000) => {
    for (let i = 0; i < ms / 200; i++) {
      try { if (await Eval(expr)) return true; } catch { /* 未就绪 */ }
      await sleep(200);
    }
    return false;
  };

  // 前置：页面就绪（app.js 起来了 / 生成页 DOM 在位）
  const ready = await waitFor(`document.readyState === 'complete' && !!document.getElementById("rec-list")`);
  check("前置：页面就绪（#rec-list 在位）", ready);
  if (!ready) { console.log(`合计：PASS ${pass} / FAIL ${fail}`); return EXIT_ASSERT_FAIL; }

  // 注入载荷并渲染（真模块：ui/generate-recommend.js 的 renderRecommendResult）。
  // 注意：应用启动区（index.html）在用户操作时才把 clusterDeps 注册进去，直接调本函数时
  // 它还是空的 → 渲染路径里的 `clusterDeps.scheduleDraftSave()` 会抛错。冒烟里补一小撮
  // **只读/记账型**替身（不改变被测行为：草稿只是记下来，供断言"选完确实落了草稿"）。
  const rendered = await Eval(`(async () => {
    const m = await import('/js/ui/generate-recommend.js');
    const saved = [];
    m.setClusterDeps({
      scheduleDraftSave: () => { saved.push({ slugs: [...m.selectedSlugs], choices: { ...m.groupChoices } }); },
      updateFixCenterAvailability: () => {},
      backfillInstances: () => {},
    });
    window.__groupSmokeDraft = saved;
    globalThis.__groupSmokePayload = ${JSON.stringify(payload)};
    // 起手态 = 真实流程里 autoAdd 之后的形态（真机里是 renderRecommendResult(data) 带 autoAdd）：
    // 集合 = 载荷 modules 的 slug（AI 收敛后每个功能组只留一件）。
    m.setSelectedSlugs(globalThis.__groupSmokePayload.modules.map((x) => x.slug));
    m.setGroupChoices({});
    m.renderRecommendResult(globalThis.__groupSmokePayload, false);
    await new Promise((r) => setTimeout(r, 60));
    return { slugs: [...m.selectedSlugs], modules: globalThis.__groupSmokePayload.modules.map((x) => x.slug) };
  })()`);
  check("注入真库载荷并渲染成功（集合 = 载荷 modules）",
    JSON.stringify(rendered.slugs) === JSON.stringify(rendered.modules), JSON.stringify(rendered));

  const snapshot = () => Eval(`(() => {
    const cards = [...document.querySelectorAll('.group-card')].map((c) => ({
      title: c.querySelector('.title') ? c.querySelector('.title').textContent.trim() : "",
      checked: [...c.querySelectorAll('input[type=radio]')].filter((i) => i.checked)
        .map((i) => i.dataset.groupSlug),
      needsChoice: c.classList.contains('needs-choice'),
    }));
    const notes = [...document.querySelectorAll('#rec-list .muted')].map((n) => n.textContent.trim());
    return { cards, notes };
  })()`);

  // ① 未选：不预选 + 「请选择」
  const s1 = await snapshot();
  const att1 = s1.cards.find((c) => c.title.includes("航向保持")) || {};
  check("① 组卡渲染出「航向保持 / 姿态传感器」", !!att1.title, JSON.stringify(s1.cards.map((c) => c.title)));
  check("① 未选时没有任何 radio 被勾选", Array.isArray(att1.checked) && att1.checked.length === 0,
    JSON.stringify(att1.checked));
  check("① 未选卡挂「请选择」提示", att1.needsChoice === true && att1.title.includes("请选择"), att1.title);
  check("① 需求句灰注写「（请选择）」", s1.notes.some((n) => n.includes("请选择")),
    JSON.stringify(s1.notes.slice(0, 4)));

  // ③ 收敛态（常态）下「必须选择」**不该**拦：同组已经被收敛成一件 = 没有歧义可拍板
  //    （组卡照样不预选、照样挂「请选择」，用户随时可以改选）。真正的硬拦见 ⑥ 歧义态。
  const readiness = await Eval(`(async () => {
    const rec = await import('/js/ui/generate-recommend.js');
    rec.setChosenPlatform('mspm0');
    const steps = await import('/js/ui/step-state.js');
    steps.markStepDone(5);   // 真实流程里 renderRecommendResult 会标第 5 步完成（这里显式补上）
    document.getElementById('problem').value = '设计一个沿直线与半圆弧行驶并保持航向的小车';
    document.getElementById('output-dir').value = 'C:\\\\tmp\\\\group-choice-smoke';
    const m = await import('/js/ui/generate-readiness.js');
    const st = m.readinessState();
    const fx = await import('/js/fx/readiness.js');
    const bad = fx.generateReadinessChecks(st).filter((c) => !c.ok).map((c) => c.reason);
    return { groupChoiceReason: st.groupChoiceReason, bad,
      diag: { gap: rec.groupChoiceGap().map((g) => g.id), slugs: [...rec.selectedSlugs],
              cards: ((rec.lastRecommend || {}).exclusive_groups || []).map((c) => [c.id, c.recommended]) } };
  })()`);
  check("③ 收敛态：同组已收敛成一件 → 「必须选择」不拦（就绪全绿）",
    readiness.groupChoiceReason === "" && (readiness.bad || []).length === 0,
    JSON.stringify(readiness.diag) + " / " + JSON.stringify(readiness.bad));
  check("③ 但组卡仍是不预选 + 「请选择」（用户随时可改选）",
    (await snapshot()).cards.some((c) => c.needsChoice === true),
    JSON.stringify((await snapshot()).cards.map((c) => c.title)));

  // ④ 未拍板时直接打后端 → 400（服务端同源守门，且不落盘）。
  //    请求用**歧义态**的集合（组内两件都在）——那才是门禁该拦的形态；收敛态（每组一件）
  //    服务端本来就不该拦（口径见 spec「方案 3」）。这里也顺手证明了「拦在落盘之前」。
  const backendMissing = await Eval(`(async () => {
    const r = await fetch('/api/generate', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ platform: 'mspm0', slugs: ['pid', 'jy61p', 'imu_uart'], main_c: 'int main(void){}',
        output_dir: '${(join(OUT, "should-not-exist")).replace(/\\/g, "\\\\")}' }) });
    return { status: r.status, detail: (await r.json()).detail || '' };
  })()`);
  check("④ 未选直接生成 → 服务端 400", backendMissing.status === 400, JSON.stringify(backendMissing));
  check("④ 400 文案含组名与出路", backendMissing.detail.includes("航向保持")
    && backendMissing.detail.includes("还需要你选择一项"), backendMissing.detail.slice(0, 90));
  // 门禁必须拦在落盘之前：这次 400 之后不该留下输出目录（曾经真被写出来过 —— 那次是因为
  // 门禁没触发，服务端默默生成了工程，正是本单要防的事）
  check("④ 400 之后没有产生输出目录", !existsSync(join(OUT, "should-not-exist")));

  // ② 点一下成员（可信点击路径：直接派发 click，与用户点 radio 同一条监听）
  const clicked = await Eval(`(async () => {
    const input = document.querySelector('.group-card input[data-group-slug="jy61p"]');
    if (!input) return 'no-input';
    input.click();
    await new Promise((r) => setTimeout(r, 80));
    const m = await import('/js/ui/generate-recommend.js');
    return { selected: [...m.selectedSlugs], choices: { ...m.groupChoices } };
  })()`);
  check("② 点选后集合换成所选成员（pid + jy61p）",
    JSON.stringify(clicked.selected) === JSON.stringify(["pid", "jy61p"]), JSON.stringify(clicked));
  check("② 点选写进 groupChoices", clicked.choices && clicked.choices["attitude-hold"] === "jy61p",
    JSON.stringify(clicked.choices));

  const s2 = await snapshot();
  const att2 = s2.cards.find((c) => c.title.includes("航向保持")) || {};
  check("② 点选后该成员带 checked", (att2.checked || []).includes("jy61p"), JSON.stringify(att2.checked));
  check("② 点选后「请选择」徽标消失", att2.needsChoice === false, att2.title);
  check("② 灰注改说「已由…替代」", s2.notes.some((n) => n.includes("替代")), JSON.stringify(s2.notes.slice(0, 4)));

  const readiness2 = await Eval(`(async () => {
    const m = await import('/js/ui/generate-readiness.js');
    return m.readinessState().groupChoiceReason;
  })()`);
  check("③ 选齐后拦截文案清空（可以生成）", readiness2 === "", JSON.stringify(readiness2));

  // ⑤ 换成同组另一个成员 → 生成集合不带旧的那一个
  const swapped = await Eval(`(async () => {
    const input = document.querySelector('.group-card input[data-group-slug="imu_uart"]');
    if (!input) return 'no-input';
    input.click();
    await new Promise((r) => setTimeout(r, 80));
    const m = await import('/js/ui/generate-recommend.js');
    return { selected: [...m.selectedSlugs], choices: { ...m.groupChoices } };
  })()`);
  check("⑤ 换选 imu_uart 后集合不再含 jy61p",
    JSON.stringify(swapped.selected) === JSON.stringify(["pid", "imu_uart"]), JSON.stringify(swapped));

  // -------------------------------------------------------------------------
  // ⑥ 歧义态（用户现场那张图的形态）：**同一功能的两件同时在集合里** —— 这才是
  //    「必须由用户拍板」真正要拦的态。生产路径上它 = 收敛前的旧缓存载荷 /
  //    同组互斥没生效的库（本次 jy61p 那一半就属后者）。
  // -------------------------------------------------------------------------
  const ambiguous = JSON.parse(readFileSync(join(OUT, "payload-ambiguous.json"), "utf8"));
  const gated = await Eval(`(async () => {
    const m = await import('/js/ui/generate-recommend.js');
    m.setSelectedSlugs(${JSON.stringify(ambiguous.modules.map((x) => x.slug))});
    m.setGroupChoices({});
    m.renderRecommendResult(${JSON.stringify(ambiguous)}, false);
    await new Promise((r) => setTimeout(r, 60));
    const steps = await import('/js/ui/step-state.js');
    steps.markStepDone(5);
    document.getElementById('problem').value = '设计一个沿直线与半圆弧行驶并保持航向的小车';
    document.getElementById('output-dir').value = 'C:\\\\tmp\\\\group-choice-smoke';
    const rd = await import('/js/ui/generate-readiness.js');
    const st = rd.readinessState();
    const cards = [...document.querySelectorAll('.group-card')].map((c) => ({
      title: c.querySelector('.title').textContent.trim(),
      checked: [...c.querySelectorAll('input[type=radio]')].filter((i) => i.checked).map((i) => i.dataset.groupSlug),
    }));
    return { reason: st.groupChoiceReason, cards, slugs: [...m.selectedSlugs], choices: { ...m.groupChoices } };
  })()`);
  check("⑥ 歧义态：组卡不预选（两件都在集合里也没勾）",
    (gated.cards.find((c) => c.title.includes("航向保持")) || {}).checked.length === 0,
    JSON.stringify(gated.cards));
  check("⑥ 歧义态：就绪检查单拦住生成",
    typeof gated.reason === "string" && gated.reason.includes("还需要你选择一项"), gated.reason || "(空)");

  const gatedBackend = await Eval(`(async () => {
    const r = await fetch('/api/generate', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ platform: 'mspm0', slugs: ${JSON.stringify(ambiguous.modules.map((x) => x.slug))},
        main_c: 'int main(void){}', output_dir: '${(join(OUT, "should-not-exist-2")).replace(/\\/g, "\\\\")}' }) });
    return { status: r.status, detail: (await r.json()).detail || '' };
  })()`);
  check("⑥ 歧义态：未拍板直接生成 → 服务端 400", gatedBackend.status === 400, JSON.stringify(gatedBackend));

  const narrowed = await Eval(`(async () => {
    const input = document.querySelector('.group-card input[data-group-slug="imu_uart"]');
    if (!input) return 'no-input';
    input.click();
    await new Promise((r) => setTimeout(r, 80));
    const m = await import('/js/ui/generate-recommend.js');
    const rd = await import('/js/ui/generate-readiness.js');
    return { slugs: [...m.selectedSlugs], reason: rd.readinessState().groupChoiceReason };
  })()`);
  check("⑥ 拍板后：集合收敛成用户选的那一件（不再两件并存）",
    JSON.stringify(narrowed.slugs) === JSON.stringify(["pid", "imu_uart"]), JSON.stringify(narrowed));
  check("⑥ 拍板后：拦截文案清空（可以生成）", narrowed.reason === "", JSON.stringify(narrowed.reason));

  console.log(`合计：PASS ${pass} / FAIL ${fail}`);
  return fail === 0 ? 0 : EXIT_ASSERT_FAIL;
}

process.exit(await main());
