# 03 — 浏览器门禁接进 prepush 与 CI

**要做什么：** `tests/browser/*.spec.mjs` 从"靠人记得手敲"变成**自动跑**：改动落在浏览器验收的
相关落点时，本地推送闸门会跑它、远端 CI 也会跑它；用例真红拒推，而闸门自己环境不齐时
（node 缺 / playwright 浏览器没装 / 清单为空）**打印原因并放行**——与既有前端门禁同一套政策。
端到端行为：改坏一个 ui 模块的绑定，`git push`（或开 PR）时当场被拦下并点名是哪条用例。

**被谁阻塞：** 01（先修绿——红的用例接进闸门等于把闸门常年染红）。

**状态：** claimed

- [x] `tools/prepush.py` 增加一支与前端门禁并列、相互独立的浏览器门禁：
      - `BROWSER_PREFIXES` = `tests/browser/`、`src/contest_generator/static/js/ui/`、
        `src/contest_generator/static/index.html`、`src/contest_generator/static/js/app.js`；
      - `Selection.browser` 标志 + `browser_test_files()` + `run_browser_tests()`；
      - 命令 `node --test --test-concurrency=1 <展开的文件>`（串行**刻意**：每个 spec 各起
        真后端 + 真 Chromium，跑同一份工作树与库；端口已各用各的，串行只为失败可归因）。
- [x] 失败语义：node 缺 / 清单空 / **playwright 或 chromium 不可用** → 打印原因返回 0；
      用例真红 → 非 0 拒推。实测三条都有用例钉住。
- [x] `describe()` / `--dry-run` 带上这一支（含 `--test-concurrency=1` 的字样）。
- [x] `tests/test_prepush.py` 补 9 条用例（落点正例 6 + 反例 3 + 放行两条 + 真红一条 +
      前端红时跳过一条 + 清单非空一条）。
- [x] `.github/workflows/ci.yml` 增加 job `browser-suite`（windows-latest）：
      checkout（`fetch-depth: 0`）→ setup-python 3.13 → setup-node 22 → `pip install -e ".[dev]"`
      → `npm install` → `npx playwright install chromium` → 跑浏览器门禁。
- [x] `tests/test_ci_workflow.py` 补用例钉住新 job 存在、命令与本地同一条、前置齐全、跑在 windows。
- [x] **顺带修那条已经失效的守卫**：action 白名单原先只列 checkout / setup-python，而 CI 里
      早有 `actions/setup-node@v4`（工单 module-hwcheck/01 加的）——它此前能绿只是因为没人
      再动那段。已把三种官方 action 明确列入，并把「不联网」的真实边界写进 docstring
      （**测试不打网络**；CI 装依赖要联网），另把「不许出现 `secrets.`」的判据保留。
- [x] 本机实测：`python tools/prepush.py --changed tests/browser/hwcheck.spec.mjs` 端到端跑通
      （读数见 `## Comments`）。
- [x] `python -m pytest` 全绿 + `node --test "tests/js/*.test.mjs"` 全绿；提交信息中文。

## Comments

### 一、两支门禁的分工（写进 `tools/prepush.py` 文件头，判据只有一份）

| 支 | 落点 | 跑什么 | 成本 |
|---|---|---|---|
| 前端门禁（工单 module-hwcheck/01） | `static/` 任意 + `tests/js/` | `node --test "tests/js/*.test.mjs"` | 秒级，零 npm 依赖 |
| **浏览器门禁**（本工单） | `tests/browser/`、`static/js/ui/`、`static/index.html`、`static/js/app.js` | `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | ~35s，要 playwright + Chromium |

**为什么不并成一支**：前端那支的前提是"只吃 `node:` 内置模块、零 npm 依赖、几秒跑完"，
浏览器用例三条都不满足。混进同一个 glob 会让**每次改前端都多一个浏览器前提**——
那正是"闸门太贵于是被人绕过"的开始。

`fx/` **不列入**浏览器门禁落点：浏览器用例不直接断言 fx（纯函数面归 `tests/js/` 那支）。

### 二、失败语义（三条"放行" + 一条"拒推"，全部有用例钉住）

| 情形 | 行为 |
|---|---|
| node 不在 PATH | 打印原因，返回 0（闸门能力缺失不该把维护者堵在门外） |
| `tests/browser/` 下没有 `*.spec.mjs` | 打印原因，返回 0（**不许**静默跑 0 个用例装作通过） |
| playwright / chromium 不可用（新 clone 没装） | 打印原因 + **告诉怎么装**（`npm install` + `npx playwright install chromium`），返回 0 |
| **用例跑了但红了** | 返回非 0，**拒推** |

另有一条顺序纪律：前端门禁先跑，**它红了就跳过浏览器门禁**（最贵那支没必要再付），
但**必须打印一行说明为什么跳过**——"少跑"长得像"全绿"，静默跳过是这道门禁最坏的失效方式。

### 三、`--full` / 推 tag 的口径

「整套」现在 = pytest 全套 + 前端门禁 + **浏览器门禁**：整套的意义就是"不看改动、全都跑一遍"，
不带上它反而会在发版前漏掉真浏览器那一层。

### 四、本机端到端实测

```
$ python tools/prepush.py --changed tests/browser/hwcheck.spec.mjs
[prepush] 改动 1 个文件 → 整套 pytest + 浏览器门禁（tests/browser/*.spec.mjs）
[prepush] 执行：node --test --test-concurrency=1 tests/browser/code-tree-click.spec.mjs \
                tests/browser/hwcheck.spec.mjs tests/browser/module-intro.spec.mjs
ℹ pass 21   ℹ fail 0
[prepush] 执行：python -m pytest -q -p no:cacheprovider -n auto
5042 passed, 1 skipped, 32 warnings in 115.41s (0:01:55)
exit=0
```

`--changed` 给的是 `tests/browser/*.spec.mjs` → 按既有规则 pytest 倒向整套（"`tests/` 下但认不出"），
同时浏览器门禁那一支起（它在 `tests/js/` 的 glob 之外，前端门禁那支没跑）。

`tests/test_prepush.py` **51 passed**；`tests/test_ci_workflow.py` + `test_prepush*.py` **67 passed**。

### 五、CI 契约的顺带修正（旧账，如实记账）

`test_workflow_does_not_use_secrets_or_network_steps` 的 action 白名单原先**只列了
`actions/checkout` 与 `actions/setup-python`**，而 `ci.yml` 里早就有 `actions/setup-node@v4`
（工单 module-hwcheck/01 加的）——这条守卫此前能绿，只是因为之后没人再动那段。本轮新增
`npm install` / `npx playwright install chromium` 两步正好把它暴露出来，于是：

- 白名单改成明确列三个官方 action（多一个就多一处供应链面）；
- docstring 写清「不联网」的**真实边界**：说的是**测试本身不打网络**（走 `tests/fakes.py` 的桩），
  而 CI **装依赖本来就要联网**——别把两件事混起来读；
- 「不许出现 `secrets.`」的判据原样保留。

新增 `test_browser_suite_job_runs_the_same_command_as_local`：钉住 CI 的浏览器 job 存在、
命令与本地同一条（含 `--test-concurrency=1`）、前置齐全（npm install / playwright install chromium）、
且跑在 windows 上。

### 六、待真机确认的一处（如实记账，别当成已验证）

CI 那个 job 的**云端行为本轮没跑过**（本机没有 GitHub runner）。能静态确认的：
YAML 解析通过、job 结构完整（7 steps）、命令与本地字符串一致、四种 action 都是官方 action、
`npm install` 有 `package.json`（devDependencies: playwright ^1.63.0）兜底。
真正首次跑起来要等推上去才知道（`playwright install chromium` 在 windows runner 上的耗时是变量）。
