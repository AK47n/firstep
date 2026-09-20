# 03 — 浏览器门禁接进 prepush 与 CI

**要做什么：** `tests/browser/*.spec.mjs` 从"靠人记得手敲"变成**自动跑**：改动落在浏览器验收的
相关落点时，本地推送闸门会跑它、远端 CI 也会跑它；用例真红拒推，而闸门自己环境不齐时
（node 缺 / playwright 浏览器没装 / 清单为空）**打印原因并放行**——与既有前端门禁同一套政策。
端到端行为：改坏一个 ui 模块的绑定，`git push`（或开 PR）时当场被拦下并点名是哪条用例。

**被谁阻塞：** 01（先修绿——红的用例接进闸门等于把闸门常年染红）。

**状态：** ready-for-agent

- [ ] `tools/prepush.py` 增加一支**与前端门禁并列、相互独立**的浏览器门禁（照 `Selection.js` 的形制）：
      - `BROWSER_PREFIXES` = `tests/browser/`、`src/contest_generator/static/js/ui/`、
        `src/contest_generator/static/index.html`、`src/contest_generator/static/js/app.js`；
      - `Selection.browser` 标志 + `browser_test_files()`（清单在 Python 侧展开，**不把 glob 交给 node**）
        + `run_browser_tests()`；
      - 命令 `node --test --test-concurrency=1 <展开的文件>`——**串行是刻意的**：每个 spec
        各起真后端与真 Chromium、跑同一份工作树与库（端口已经各用各的，见工单 01），
        串行是为了失败可归因；命令里的这一条要有注释说明理由。
- [ ] 失败语义三分层照 `run_js_tests()`：node 不在 PATH → 打印原因返回 0；清单为空 → 打印原因返回 0；
      **playwright 的浏览器不可用**（`require("playwright")` 抛错 / 浏览器二进制缺失）→
      打印原因返回 0；**用例跑了且红了** → 非 0，拒推。
- [ ] `describe()` / `--dry-run` / `--explain` / `--no-js` 的既有输出要如实带上这一支
      （新增一支就不能在"会说要跑什么"的地方消失）。
- [ ] `tests/test_prepush.py` 补用例钉住新选择器：命中 / 不命中 / 与 js 支独立 /
      `--dry-run` 会说 / node 缺失时放行（沿用该文件既有的纯函数 + 桩风格）。
- [ ] `.github/workflows/ci.yml` 增加 job `browser-suite`（windows-latest，与本地同一条命令）：
      checkout（`fetch-depth: 0`）→ `actions/setup-python@v5`（3.13，cache pip）→
      `pip install -e ".[dev]"` → `actions/setup-node@v4`（22）→ `npm install` →
      `npx playwright install chromium` → 跑浏览器门禁。
- [ ] `tests/test_ci_workflow.py` 补用例钉住新 job 存在、且跑的命令与本地同一条。
- [ ] **顺带修一条已经失效的守卫**（必须在本次改动里明说，不许静默绕过）：
      `test_workflow_does_not_use_secrets_or_network_steps` 的 action 白名单**只列了
      checkout / setup-python**，而 CI 里早已有 `actions/setup-node@v4`（工单 module-hwcheck/01 加的）
      ——它现在能绿只是因为没人再动那段。把 setup-node 纳入白名单，并把「不联网」的真实边界
      写进 docstring（**测试不打网络**；CI 装依赖与浏览器要联网），另补一条「CI 里不许出现
      `secrets.`」的判据（保留原意）。
- [ ] 本机实测：改一个 `ui/` 文件 → `python tools/prepush.py --changed <文件> --dry-run`
      如实报出会跑浏览器门禁；真跑一遍，读数（通过数 / 耗时）留 `## Comments`。
- [ ] `python -m pytest` 全绿 + `node --test "tests/js/*.test.mjs"` 全绿；提交信息中文。

## Comments
