# 04 — ui 层第二层缝：DOM 行为契约（真浏览器，3 条）

**要做什么：** 给 ui 层立起第二层缝——**行为契约**：在真页面（`index.html` 当夹具）+ 真后端上，
对选定的 ui 模块断言"用户做一个动作 → 看到什么结果"，包括**跨刷新的持久化契约**。
端到端行为：把某个 ui 模块的绑定摘掉（或改坏它写 localStorage 的那个键），
`tests/browser/ui-contract.spec.mjs` 当场变红并点名是哪条契约——而不是等人肉点页面。

**被谁阻塞：** 01（用例要在一个不自杀的夹具上跑）。

**状态：** ready-for-agent

- [ ] 新文件 `tests/browser/ui-contract.spec.mjs` + 共用助手 `tests/browser/ui-contract-fixture.mjs`
      （开页 / 等启动完成 / 切页签 / 读 localStorage / 契约失败时的报错文案）。夹具服务沿用
      `tests/browser/server.mjs`。
- [ ] 文件头写清**选件口径**（下一个人据此扩展）：① 监听器密度高；② 交互是**纯本地**的
      （只有 DOM + localStorage，不起 LLM、不编译、不生成）；③ 一个模块一条用例，
      断言"用户动作 → 可观察结果"，不绑内部函数名。
- [ ] 本轮取三条（都满足口径）：
      1. **`ui/guide.js` 子页签**：点页签 → `.active` / `aria-selected` / `hidden` / `tabindex`
         四态一致；方向键与 Home/End 循环切换且焦点跟随。
      2. **`ui/step-state.js` 卡片折叠**：点卡头 → `.collapsed` 翻转 + `localStorage` 记忆键写入；
         **刷新后记忆生效**（跨刷新持久化契约）。
      3. **`ui/welcome.js` 欢迎卡**：首屏可见 → 点"不再显示" → 卡片隐藏且写入
         `WELCOME_DISMISS_KEY`；刷新后不再出现（持久化契约）。
- [ ] **每条都要红证**：临时摘掉该模块的绑定 / 改坏它写的存储键 → 用例必须变红**且点名是哪条契约**；
      逐字节复原后变绿。三条的红/绿读数留 `## Comments`。
- [ ] 用例**自清且互不污染**：不留下 localStorage 键、不改别的用例依赖的状态；单文件连跑 5 次全绿。
- [ ] 断言**不绑文案全文**（只取关键短语），不绑内部函数名与 DOM 结构细节——判的是行为。
- [ ] 跑法写进文件头：`node --test --test-concurrency=1 tests/browser/ui-contract.spec.mjs`
      （或与另两个 spec 在同一条命令里一起跑——每个 spec 各起自己的服务与端口，见工单 01）。
- [ ] `node --test "tests/js/*.test.mjs"` 全绿（本条不该动 `tests/js/` 面）；提交信息中文。

## Comments
