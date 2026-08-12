# 01 — 更新记录栏目（第 8 个 tab）：手工维护 CHANGELOG.md + 后端薄路由 + 前端时间轴

**What to build:** 新增「更新记录」栏目——类似 GitHub releases/changelog，按时间点展示"什么时候做了什么改进"。**数据源 = 手工维护的仓库根 `CHANGELOG.md`**（用户定案：不用 git log 自动生成，不纯前端写死——想要什么写什么，不受 commit 格式约束）。后端加 `GET /api/changelog` 薄路由解析该文件，前端加新顶级 tab（nav 第 8 个，放「设置」之前）时间轴渲染（按天分组 + 条目列表 + 空状态）。范围外：版本号/发布粒度、git 集成、任何生成/推荐/编译逻辑——全部不动。

**Status:** resolved（2026-08-12 实施完成：1241 绿 + mypy 干净 + node 过；真机数据面三验（200/8 组 37 条/临删空列表）已过；视觉点击待用户浏览器验收）

## 决策记录（grilling 2026-08-12，用户定案）

1. **数据源**：手工维护 `CHANGELOG.md`（仓库根，GitHub 惯例位置）。用户要求"只要记录在哪个时间点做出了什么样的改进"，手工文件自由度最高；git log 自动生成（commit 原文措辞不可控）与纯前端写死（更新要动内联 HTML）均否。
2. **入口形态**：**新顶级 tab**（`<button data-tab="changelog">更新记录</button>`，放「设置」前，共 8 个 tab）——不是生成页内横向栏（"第 N 栏"约定指生成页内分区，更新记录是全工具级视角）。
3. **数据流**：照抄现有"纯展示"模式（`/api/topics` 样板）——点击 tab → `loadChangelog()` → `fetch('/api/changelog')` → 渲染。页面加载不嵌数据。
4. **健壮性**：CHANGELOG.md 缺失 / 解析异常 → 路由返回 `[]`（前端显示「暂无更新记录」），**不因展示数据损坏阻塞工具**——这是纯展示数据，不走"大声失败"。docstring 注明。
5. **格式**（新记录插最前，日期组倒序）：

   ```markdown
   # 更新记录

   （格式说明：`## YYYY-MM-DD` + `- 描述`，新记录插最前面。以下为示例）

   ## 2026-08-12
   - 新增更新记录栏目（第 8 个 tab）
   - 编译错误列表支持点击展开源码行

   ## 2026-08-11
   - ...
   ```

   解析规则：`^## (\d{4}-\d{2}-\d{2})$` 开新组（**日期严格格式**，防说明文字里的 `##` 小节误判）；组内 `^\- (.+)$` 是条目；`# ` 大标题 / 说明段落 / 空行 / 无日期组时的 `- ` 行一律跳过。返回 `[{date, items: [...]}]` 按文件顺序。

## 实施

1. **新建 `CHANGELOG.md`（仓库根）**：初始内容按天提炼（08-05 ~ 08-12），素材见本工单「初始内容素材」——直接落盘，可自行增删措辞。顶部保留 `# 更新记录` + 格式说明（会被解析器跳过）。
2. **新建 `src/contest_generator/changelog.py`**（解析域深模块，~40 行）：
   - 纯函数 `parse_changelog(text: str) -> list[dict]`——按上「格式」规则解析；日期行正则严格 `\d{4}-\d{2}-\d{2}`；无当前日期组时的 `- ` 行忽略；条目只取 `- ` 后内容（去首尾空白）。docstring 写格式契约。
   - `load_changelog(path: Path) -> list[dict]`——文件不存在 → `[]`；读失败/解析异常 → `[]`（docstring 注明"纯展示数据，损坏不阻塞"）。
3. **`src/contest_generator/webapp.py`**：`GET /api/changelog`（照 `/api/topics` 样板：`@app.get` + `@_map_errors` + 返回 `list[dict]`）——`load_changelog(Path(__file__).resolve().parents[2] / "CHANGELOG.md")`（repo 根）。docstring：格式契约 + 缺失/损坏返回空列表的原因。
4. **`src/contest_generator/static/index.html`**：
   - nav（约 338-346 行）：「设置」前插 `<button data-tab="changelog">更新记录</button>`。
   - `<main>` 内「设置」section 前加 `<section id="tab-changelog" class="page">`：卡片布局照 `tab-topic`/`tab-settings` 骨架（`.card` 标题 + `.muted` 副题 + `#changelog-list` 容器）。复用现有主题令牌（`--border`/`--muted`/`--accent`），**不新增样式**（如需时间轴竖线等装饰，用内联样式 token，克制）。
   - tab 切换分发（约 813-818 行）：加 `if (btn.dataset.tab === "changelog") loadChangelog();`
   - 新函数 `loadChangelog()`：`apiGet('/api/changelog')` → 按日期组渲染（`h3` 日期 + `ul/li` 条目，`esc()` 转义条目文本）→ 空数组渲染「暂无更新记录」灰字；非 2xx 由 `apiGet` 统一弹 `data.detail`。
5. **测试（红证先行）**：
   - 新文件 `tests/test_changelog.py`：解析单测——标准多组多条目、`# ` 标题与说明段落跳过、空行跳过、说明里 `## 不是日期` 小节不误判、无日期组的 `- ` 行忽略、`- ` 条目去空白、文件缺失 → `[]`、load 异常路径（如传目录路径 → `[]`）。
   - `tests/test_webapp.py` 加 1 条：`GET /api/changelog` 200 且 `[{date, items}]` 结构（实施后真实文件存在，断言非空 + 首条 date 匹配 `\d{4}-\d{2}-\d{2}`）。红证：实施前 404 已验。
6. **不动**：生成器 / llm.py / sse.py / compile 域（compile_runner / fix_errors）/ 库数据 / 素材库 / 其它路由 / 后端其它模块。

## 初始内容素材（从 git log 提炼，按天；落盘时改写成一句句"做了什么"，去掉 commit 细节）

- **08-12**：编译体验展示层（结果横幅四态 + 结构化错误列表 + 点击展开源码行 + 耗时）；自动编译修复闭环（生成后自动编译 → 报错自动喂 AI 修复 → 重编译 ≤3 轮 + 回滚）；编译错误回填自愈（snippet 替换 + 备份回滚）；LLM 修复匹配容错（old_snippet 行首前缀归一化兜底，真机修复成功率提升）；生成页交接提示词栏 + 赛题库真题汇总 PDF 链接；全工具深色科技感换皮（近黑底 + 青色强调 + JetBrains Mono 自托管）；PDF 资料库新栏 + 素材收录 9 份 + 全库 PDF 改名 21 个；模块普适化（xunji/pid/ball_detect 剥离决策层为纯驱动、lock_control/zone 解散、config 决策参数剥离、六模块题词清理）；2024H 巡线 xunji 模块补录（MSPM0G3507）；DeepSeek 空内容偶发重试兜底（≤3 轮）
- **08-11**：推荐请求契约对偶（CLI/前端双客户端字段/词表一致）；推荐两阶段编排归位；生成门禁装配表驱动化 + 产物树门禁对偶；生成侧跨模块同名文件查重门；zigbee_uart_key 文件/符号唯一化（修双选 L6200E）；ball_detect NULL 修复；澄清历史收敛透传（AI 不重问已答问题）；2021F Keil 真机验收（UV4 0 错 0 警：EXTI 编码器 + TIM3 调度 + pin_config 宏集中）；在途清零（分支清理 + 工作区干净）
- **08-10**：stm32 电机链路可用性闭环（2021F 全链路可用）
- **08-09**：架构深化 v5 五工单闭环（master.py 三轴拆块 / 赛题入口单一接缝 / 模块摘要投影 / 蒸馏侧平台适配 / 参考全文归位）；架构评审 8 候选 + include 解析契约工单（find_project_file / resolve_include_entries 共享原语）；llm 拆层（域判决归 selection）；推荐层平台过滤（mspm0/stm32 模块各自可用）；题库真机入库 + 模块推荐工作流归位
- **08-08**：生成门禁合 main（main.c 围栏剥离 + include 解析校验）；工单 09 验收闭环（用户 Keil 复编 0 错 0 警）；SSE 流化运行器 / entry_store 原语补全 / 错误映射归位；架构深化 round2 六工单合 main
- **08-07**：模块推荐（第 10 栏？以实际为准）；赛题库 UI 新栏 + 题库真机入库 8 条
- **08-06**：参考库 UI 新栏；素材库批次 01/02/03 入库（含 PDF 资料、完整工程、源码文本）；工单 04 拆条分块
- **08-05**：项目启动——电赛工程生成器首个版本（赛题 → 完整工程生成）+ 工单体系建立

## 验收标准

- [x] pytest 全绿（1241，+11）+ `mypy src` 干净（36 files）+ node 语法过（内联 JS node --check OK）
- [x] 解析单测全覆盖（红证先行：实施前 ImportError 已验）：标准格式 / 标题说明段落跳过 / 伪日期小节不误判 / 无日期组 `- ` 忽略 / 文件缺失与异常 → `[]`（另加严格日期残缺/行尾追加不建组 1 条）
- [x] `GET /api/changelog` 200 返回 `[{date, items}]`（实施前 404 红证已验；真机 8 组 35 条、严格倒序、逐字节同直接解析）
- [ ] 浏览器（headless 或用户浏览器）：nav 出现「更新记录」第 8 个 tab；点击渲染按天分组时间轴；条目文本转义；临删 CHANGELOG.md 重启 → 空状态「暂无更新记录」（验完恢复文件）——数据面已验（临删 → `[]` → 恢复 → 200/3136B），视觉点击待用户
- [x] 初始内容覆盖 08-05 ~ 08-12 逐天（素材按天落盘，8 组 35 条）

## 实施记录

2026-08-12 实施（本会话直接执行）：

- `CHANGELOG.md`（仓库根）初始内容 08-05 ~ 08-12 逐天落盘（8 组 37 条，素材改写为"做了什么"措辞，顶部 `# 更新记录` + 格式说明，解析器会跳过）；**时间精度升级（用户需求，2026-08-12 同会话）**：条目行首可选 `HH:MM` 时间前缀，08-11/08-12 两组按 commit 真实时间补全（组内按时间升序；"生成门禁装配表驱动化 + 产物树门禁对偶"拆两条分别落 21:19/22:20；DeepSeek 空内容重试按 merge 时间归 08-12 00:04）；08-10 及更早为合并概括无单一 commit 可映射，保持无时间前缀
- `src/contest_generator/changelog.py`：parse_changelog（`^## (\d{4}-\d{2}-\d{2})$` 严格锚定开组 + 组内 `^\- (?:(\d{1,2}:\d{2}) )?(.+)$` 可选时间前缀剥离为 {time, text}（无前缀 time=""）+ 标题/说明/空行/无日期组 `- ` 跳过）+ load_changelog（缺失/异常 → `[]`，docstring 注明纯展示数据不阻塞）
- `webapp.py` `GET /api/changelog`：照 /api/pdfs 样板，`@app.get` + `@_map_errors`，`load_changelog(Path(__file__).resolve().parents[2] / "CHANGELOG.md")`，docstring 注格式契约与空列表原因
- `index.html`：nav「设置」前插第 8 个 tab（共 8 个）；`tab-changelog` section（.card 骨架，复用令牌，零新增样式）；tab 分发加 `loadChangelog()`；按天分组渲染（h3 日期 + ul/li，esc() 转义，时间前缀 .slug 等宽 muted 色内联 token，无时间则不渲染），空数组 →「暂无更新记录」灰字，异常 → .error 红字
- 测试：`tests/test_changelog.py` 10 条（红证：实施前 ImportError；时间前缀剥离 + 无前缀兼容用例）；`test_webapp.py` +1 条（红证：实施前 404；断言 items 为 {time, text} 结构 + 首条时间格式）
- 真机：旧服务重启加载新代码，`/api/changelog` 8 组 37 条（21 条带时间）严格倒序、与直接解析逐字节一致；临删 CHANGELOG.md → `[]` → 恢复 → 200
- 不动：生成器 / llm / sse / compile 域 / 库数据 / 其它路由（diff 仅 3 改 + 3 新建）

## 文件边界

- **改**：`src/contest_generator/static/index.html`（nav + section + loadChangelog + tab 分发）、`src/contest_generator/webapp.py`（+1 路由）、`tests/`（+test_changelog.py、test_webapp.py +1）
- **新建**：`CHANGELOG.md`（仓库根，初始内容）、`src/contest_generator/changelog.py`（解析域）、`.scratch/changelog-tab/issues/01-changelog-tab.md`（本工单）
- **不动**：生成器 / llm.py / sse.py / compile 域（compile_runner / fix_errors）/ 库数据 / 素材库 / 其它路由
