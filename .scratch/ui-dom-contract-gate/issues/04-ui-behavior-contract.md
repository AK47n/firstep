# 04 — ui 层第二层缝：DOM 行为契约（真浏览器，3 条）

**要做什么：** 给 ui 层立起第二层缝——**行为契约**：在真页面（`index.html` 当夹具）+ 真后端上，
对选定的 ui 模块断言"用户做一个动作 → 看到什么结果"，包括**跨刷新的持久化契约**。
端到端行为：把某个 ui 模块的绑定摘掉（或改坏它写 localStorage 的那个键），
`tests/browser/ui-contract.spec.mjs` 当场变红并点名是哪条契约——而不是等人肉点页面。

**被谁阻塞：** 01（用例要在一个不自杀的夹具上跑）。

**状态：** resolved

- [x] 新文件 `tests/browser/ui-contract.spec.mjs` + 共用助手 `tests/browser/ui-contract-fixture.mjs`
      （开页 / 等启动完成 / 切页签 / 控制台噪声过滤）。夹具服务沿用 `tests/browser/server.mjs`。
- [x] 文件头写清**选件口径**（下一个人据此扩展）：① 监听器密度高；② 交互是**纯本地**的
      （只有 DOM + localStorage，不起 LLM、不编译、不生成）；③ 一个模块一条用例，
      断言"用户动作 → 可观察结果"，不绑内部函数名。
- [x] 本轮取到 **5 条契约 / 3 个模块**（都满足口径；welcome 拆成三条更细的契约）：
      1. **`ui/guide.js` 子页签**：点页签 → `.active` / `aria-selected` / `hidden` / `tabindex`
         四态一致；方向键与 Home/End 循环切换且焦点跟随。
      2. **`ui/step-state.js` 卡片折叠**：点卡头 → `.collapsed` 翻转 + 记忆键写入；
         **刷新后记忆生效**；再点展开时记忆也跟着变（两向都落盘）。
      3. **`ui/welcome.js` 欢迎卡**：compact 态可见 + 「打开新手指引」真的切页签；
         「不再显示」写记忆 + 隐藏 + 清空 + **刷新后不再出现**；预置 dismissed 的**冷启动**
         首屏就不渲染。
- [x] **每条都要红证**（`probe-ui-contract-red-proof.mjs`，4/4 成立）：摘掉绑定 → 该条红且
      **只红那一条**；逐字节复原 + 前置干净性检查 + 事后 sha256/git 复核。读数留 `## Comments`。
- [x] 用例**自清且互不污染**：不留下 localStorage 键（`finally` 清）、不改别的用例依赖的状态。
- [x] 断言**不绑文案全文**（只取关键短语），不绑内部函数名与 DOM 结构细节——判的是行为。
- [x] 跑法写进文件头：`node --test --test-concurrency=1 tests/browser/ui-contract.spec.mjs`
      （或与其他 spec 在同一条命令里一起跑——每个 spec 各起自己的服务与端口，见工单 01）。
- [x] `node --test "tests/js/*.test.mjs"` 全绿（本条没动 `tests/js/` 面）；提交信息中文。

## Comments

### 一、落地的五条契约（+ 1 个共用助手）

`tests/browser/ui-contract.spec.mjs` + `tests/browser/ui-contract-fixture.mjs`（开页 / 等启动完成 /
切页签 / 控制台噪声过滤）。选件口径写在文件头：**监听器密度高 × 交互纯本地 × 一条用例一个模块**。

| 契约 | 断言什么（用户动作 → 可观察结果） |
|---|---|
| `ui/guide.js` 子页签 | 点页签与方向键 / Home / End 都切面板，`.active` / `aria-selected` / `hidden` / roving `tabindex` **四态一致**，焦点跟随 |
| `ui/step-state.js` 卡片折叠 | 点卡头 → `.collapsed` 翻转 + 记忆键落盘；**刷新后记忆生效**；再点展开时记忆也跟着变（两向都落盘） |
| `ui/welcome.js` compact 态 | 卡片可见；点「打开新手指引」**真的**切到 guide 页签（导航按钮也被点亮） |
| `ui/welcome.js` 不再显示 | 点「不再显示」→ 立刻隐藏 + 清空内容 + 写记忆；**刷新后不再出现** |
| `ui/welcome.js` 冷启动 | 干净上下文里预置 dismissed → 首屏就**不渲染**卡片（读记忆那条路） |

存储键**从产品源码里抠出来**（不手抄，C5a 两条裸镜像的教训）。

### 二、过程中撞到的三件事（都写进了代码注释，别重踩）

1. **往 `#welcome-card` 里塞标记没用**：`initWelcome()` 会按 `welcomeMode()` **重新渲染**，
   塞进去的按钮连同接线一起被覆盖（第一版就是这么写的：断言"有「不再显示」按钮"直接红）。
   改法 = 走产品真实路径（把 `state.api_configured` 置假 → full 态）。
2. **真后端在测试态必然回 400**：没配 AI key / 没填题面时 `/api/generate/preview-dir` 等端点
   如实 400，浏览器打 `Failed to load resource`。那是**既有产品行为**，不是接线问题——
   `problems` 收集器按 `module-intro.spec.mjs` 的 KNOWN_NOISE 先例只过滤这一类，
   **pageerror 照收**（真接线错误会以它出现）。
3. **键值不是这条契约钉得住的**：用例与产品读同一个常量 → "把键改个名"两侧一起漂、契约照样绿
   （红证实测确认）。键值冻结归 `tests/js/card-collapse.test.mjs:91`（折叠键）与
   `tests/js/welcome-responsive.test.mjs`（welcome 键），**本文件只管行为**。

### 三、红证（`probe-ui-contract-red-proof.mjs`，4/4 成立）

口径：在**真源码**上做一处最小注入（摘掉模块的绑定），跑一遍契约，断言"该红的那条红、
且**只红那一条**"，然后**逐字节复原**并复核。为什么必须真源码：这一层测的就是真页面 + 真事件，
而 `webapp.STATIC_DIR` 是模块级常量，没法从外面重定向——**不为测试改产品**，
探针改用"注入 + 复原"，照 `probe-09-guard-strength.py` 先例。

```
✔ 反证：无注入 → 5 条契约全绿  —— 0 条红
✔ guide：摘掉子页签点击委托  —— 红了「契约：新手指引子页签——点击与方向键都切面板…」
✔ step-state：摘掉卡头折叠监听  —— 红了「契约：生成页卡片折叠——点卡头翻转 .collapsed 并落盘…」
✔ welcome：摘掉「不再显示」的接线  —— 红了「契约：欢迎卡「不再显示」——写记忆、立刻隐藏…」
PASS：4/4 条成立
复原复核：静态目录与跑之前逐字节一致（git 干净）
```

**注入只取"绑定"这一类**（摘监听器）——那是 ui 层唯一无法用纯函数用例覆盖的东西，
也正是这一层存在的理由。存储键那类**不**当红证（见上第 3 条）。

### 四、读数

| 项 | 读数 |
|---|---|
| `tests/browser/ui-contract.spec.mjs` | **5 passed / 0 fail** |
| 四个 spec 全跑（`--test-concurrency=1`） | **26 passed / 0 fail**，77.9s |
| 前端门禁 `node --test "tests/js/*.test.mjs"` | **1715 passed / 0 fail** |

### 五、没做的（如实记账，别当已做）

- 只覆盖 3 个模块 / 5 条契约；57 个 ui 模块里其余按同一形制**增量添加**（选件口径在文件头）。
- 「卡片折叠记忆」那条用第 3 步卡当样本；样本的定位写法是"按 `.step-no` 文本找那张卡"
  （不是硬编码 nth-child），步骤卡增删时可能要跟着换。
