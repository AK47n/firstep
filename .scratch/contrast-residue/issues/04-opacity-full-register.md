# 04 — 全量登记：每条 `opacity<1` 都要在册（14 条补登 + 3 条抬值）

**要做什么：** 不可选形态登记表从"**嫌疑面驱动**"（类名词法 + `cursor: not-allowed` 两个代理信号）
改成"**全量驱动**"——样式块里每一条**活规则**只要写了 `opacity: <1`，就必须在登记表里有一条
带中文理由的记录。本轮补齐 **14 条**（全部 `dim`）；其中**三条是真文字、登记成"合法弱化"之后
实测仍低于 AA**，按拍板**去掉 `opacity`、字直接用 `--muted`**（浅 5.25 / 暗 5.67，与按钮禁用态同一格）。
同时把**词法嫌疑面整条退役**（全量登记之后它不再有判据用途）。

**用户可见变化：有**（三条文字比以前清楚：`.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-10-01；读数与红证见文末）

⚠ **票面修正（实施期实测）**：补登记的是 **11 条**而不是 14 条——三条抬值的规则**不再有
`opacity` 那一格，自然也不再登记**（留着会是"这条允许弱化"的误导行）。14 条是"改前未在册"的条数。

## 落地读数（2026-10-01）

**改了什么**（4 个文件 + 证据）：
- `tests/js/css-tokens.test.mjs`：**判据②改成全量**（活规则里任何 `opacity<1` 都必须在册，
  不再要求"命中嫌疑信号"）；`CONTRAST_DISABLED_FORMS` **+11 条**（全部 `dim`，逐条中文理由）；
  **词法嫌疑面整条退役**（`CONTRAST_DISABLED_HINTS` / `classHintHits` / `CONTRAST_HINT_VECTORS`
  连同判据⓪ 的自证一起删）；红证 n2/n3/n3b/n5/n7 按新口径重写（n3b = 中性名字、n7 = 改名后
  照样要求登记 + 旧登记项过期）。
- `.scratch/light-contrast/probe_lib.py`：登记表同批 +11 条；删 `CONTRAST_DISABLED_HINTS` /
  `class_hint_hits`。
- `tests/test_contrast_mirror.py`：删 `test_hint_vectors_match` 整条腿 + 登记表腿里的词法断言。
- `.scratch/disabled-forms/probe-00-inventory.py`：取数口径跟着走（删 `HINT_WORDS` 与"词法命中"列，
  §1 改报"活规则 / 未在册"）。
- `src/contest_generator/static/index.html`：三条真文字**去掉 `opacity`**（`.res-soft` / `.sugg-count` /
  `.chip.rec.unsel .reason`），每条上方注释写清实测比值与"为什么降到 AA 以下"。

**读数 1 · 全量登记闭合**（`probe-08-opacity-inventory-after.txt`，现算）：
样式块 `opacity<1` 共 **20** 条 = 动画帧 **5**（判据排除）+ 活规则 **15**，**未在册 0 条**。
（对照：本单之前 18 条活规则 / 只有 4 条在册；三条抬值后活规则 18 → 15。）
正向认人面里带 `opacity` 的规则 = **0 条**。渲染方登记 **19 条**、机械面对数 **394**、族面 **172** 不变。

**读数 2 · 三条真文字的真像素**（`probe-07-compare.txt`；改前那一发用 `git show HEAD:<页面>`
（sha256 `E099ECAD…`）现跑，读完复原并核 sha256 一致（`028E5A27…`）：

| 主题 | 规则 | 改前（opacity 合成） | 改后 | 底 |
|---|---|---|---|---|
| light | `.chip.rec.unsel .reason` | **3.52** | **5.25** | `#e1e6ec` |
| dark | 同上 | **4.10** | **5.67** | `#1c2128` |
| light | `.sugg-count` | **4.18** | **5.72** | `#eeeff0` |
| dark | 同上 | **3.91** | **4.85** | `#282d35` |
| 两主题 | `.res-soft` | **没量到** | —— | —— |

⚠ `.res-soft` **没量到真像素**：它住在资源总览（纯前端聚合）里，要一份**带 AI 洞察的任务计划**
才渲染得出来，本次流程到不了那里。替代依据：① 改动本身只有"删掉 `opacity: .75`"一句，
声明的 `color: var(--muted)` 一字未动；② 同一对色（`--muted` × `--panel-2` / `--panel`）已在族面
与按钮禁用态上量过（浅 5.25 / 暗 5.67）；③ 探针把"没量到"连同原因写进了 JSON。**这张账没抹平。**

**红证**（都在守卫末尾那条"合成红证"里，改前各判一次红）：
n2 `.tmp-probe.off{opacity:.4}` → 红；n3 `.tmp-probe.k{opacity:.4;cursor:not-allowed}` → 红；
**n3b `.tmp-probe-quiet{opacity:.4}`（中性名字 + 无光标）→ 红**（旧口径的漏网形态，本单的要害）；
n5 `:not(:disabled)` → 正向面**不**误判，但全量面**照样要求登记**；`@keyframes` 帧 → 不红；
n6 `dim` 档带 opacity 不红、改登 `disabled` 就红；**n7 把已登记规则改名成中性名字 → 新名字照样
要求登记 + 旧名字那条登记项被判过期**。

**门禁**（读数晚于最后一次改动）：前端 **1847 / 0**；浏览器门禁（单独跑）**61 / 0**；
全量 `pytest -n auto -q` **5694 passed + 11 skipped**（比上一单少 1：镜像腿 `test_hint_vectors_match`
随词法表退役）。

**没做**：`.res-soft` 的真像素（原因见上）。

## 一、判据改造（守卫 + 两侧同步）

- [x] **反向判据改成全量**：**活规则**（排除 `@keyframes` 帧）里出现 `opacity: <1` ⇒
      **必须**落在登记表里（两档都算），否则红，文案点名选择器。
      **旧口径的漏**要写进注释：旧口径下"换个不命中词法的类名"就没人管。
- [x] **自检**（证明"不再依赖代理信号"）：给一条**已登记的规则改个名字**（改成不含任何嫌疑词、
      也不带 `cursor: not-allowed` 的选择器）——全量口径下**照样必须在册**（旧口径会漏）。
      这条自检要能在红证里复现。
- [x] **词法嫌疑面退役**：`CONTRAST_DISABLED_HINTS`、`classHintHits`、`CONTRAST_HINT_VECTORS`
      **连同 Python 侧同名物、镜像腿、`probe-00-inventory.py` 的取数口径**一起走
      （不许留第二套口径；`tests/test_contrast_mirror.py` 的腿数与文件头说明同批改）。
- [x] **正向判据不动**：`disabled` 档仍**不许**出现 `opacity`（认人面只收 `disabled` 档那半张表——
      与反向面不是同一张，这条边界是上一轮的要害，别合并）。

## 二、14 条补登记（全部 `dim`，逐条理由必须具体）

二档语义不变：`disabled` = 不可选形态（不许用 opacity）；`dim` = 允许保留 opacity，理由写清。
**本轮 14 条没有一条是 `disabled`**——最容易误判的两条已排除：`.chip.rec.unsel .reason` 是
"点一下加回"的**开关状态**，`.res-soft` 是"AI 误标资源"的降级展示（那里没有任何可选控件）。

| 选择器 | opacity | 是什么 | 理由要点（实施时写全） |
|---|---|---|---|
| `.welcome-card .welcome-sub` | .92 | 欢迎卡说明副标题 | 与标题同底的次要文字；弱化语气不是可用性；实测仍 ≥AA（浅 4.88–5.16 / 暗 5.30） |
| `.welcome-card .welcome-line` | .92 | compact 欢迎卡那一行 | 同上一条同档（同底同字号，同一理由） |
| `.chip.rec .chip-x` | .6 | 已选 chip 尾部的 ✕ 符号 | **非文字符号**；hover 升到 1 并转 `--danger-text`，chip 本体才是按钮 |
| `.chip.rec.unsel .reason` | .8 | 未选（已移除）chip 里的推荐理由 | `unsel` = 用户点掉了它、**点一下加回**（`cursor:pointer` / `role=button` / `aria-pressed=false`）⇒ 开关状态，不是不可用 |
| `.sugg-count` | .85 | 库外建议 chip 的「⤵ N 方案」计数 | 可展开选型面板的计数标签，chip 本体可点；弱化的是一行最小字号小字 |
| `.sugg-msg .muted` | .75 | 气泡尾部时间戳 | 次要小字，颜色继承气泡的 `--text`（**不是** `--muted`），实测浅 6.08 / 暗 8.27。⚠ 别与 `.sugg-msg.muted`（引导气泡，无 opacity）混键 |
| `#tab-hwcheck .empty-state .es-icon` | .5 | 检测页空态 emoji | 非文字装饰（意思由同块 `.es-title`/`.es-hint` 承担）。⚠ 与下面那条**是同一视觉物的两条规则**，各占一行、别合并 |
| `.empty-state .es-icon` | .5 | 全站空态 emoji | 非文字装饰，底下永远跟着完整文案；`.5` 只为"空态安静下来" |
| `.code-crumb-sep` | .55 | 面包屑段间「›」 | `aria-hidden="true"` + `user-select:none` 的纯标点装饰；相邻段各自可点 |
| `.code-tab.dragging` | .55 | 被拖拽的页签 | 拖拽中的**瞬态**（半透明 + z-index 置顶，落点由 `.drop-before/after` 的 accent 竖线表达），松手即消失 |
| `.code-zoom-badge` | **0** | 缩放浮标 | **显隐机制，不是弱化**：`0` 是默认隐藏，可见态是兄弟规则 `.show { opacity: 1 }`，JS 每次缩放加 `.show`、1200ms 后摘掉。⚠ **绝不能**按 `disabled` 处置（去掉 opacity 会让浮标常驻右上角）——理由里必须写明，否则下一位读者会误改 |
| `.card-details > summary::before` | .75 | 折叠说明行前的「ⓘ」 | `::before` 装饰符号；同行摘要文字是 `--muted` 全强度，summary 可点展开 |
| `.res-soft` | .75 | "非硬件资源"降级行 / chip | AI 把模块名/函数名误标成资源时的降级展示，整组在默认收起的 details 里；**无可选控件** |
| `.card-collapse` | .35 | 卡片右上折叠 ▾ | 常驻弱化（hover 升 1 + accent）；**真正主入口是整行 h2**，▾ 只是"能折"的状态指示 |

- [x] **键格式**（照 `contrastRules` 归一化后的选择器原文）：`#tab-hwcheck .empty-state .es-icon`
      与 `.empty-state .es-icon` 是**两行**；`.card-details > summary::before` 的 `>` 与 `::before`
      原样；`.sugg-msg .muted`（后代）别写 `.sugg-msg.muted`。
- [x] **两侧钉死**：登记表要**同时**改守卫与 Python 口径（镜像腿逐条比 `(作用域, 选择器, 类别)`，
      两侧理由都必须非空）。别只改一侧——那正是本仓最怕的"腿绿而读数红"。
- [x] **两处注释/基线回改**：守卫里那段「够不着的那 14 条（明写的边界）」（它现在要改成
      "已全量登记"）+ `probe-00-inventory.py` 的 `RECON_BASELINE` 口径说明。

## 三、三条抬值（产品面 + 真像素）

- [x] `.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`：**去掉 `opacity`**，文字用
      `--muted`（与按钮禁用态同一格；浅 5.25 / 暗 5.67）。改完它们**不再有 `opacity`** ⇒
      按判据③ 双向对账，这三条要不要留在登记表里（留 = 死条会被判红；不留 = 它们不再有 opacity、
      本来也不该在册）——**按盘上事实定**，红证里把这条走通。
- [x] **真像素改前 / 改后**（两主题）：三条各出一组，证明"字变清楚了、没有别的变化"。
      探针**先量改前**（用改动前的 `index.html`，读完复原并核 sha256），再量改后。
- [x] 三条的底各不相同（`.res-soft` 行无底色 / chip 是 `--panel-2`；`.chip.rec.unsel .reason`
      底 `transparent`；`.sugg-count` 压在 `rgba(139,148,158,.15)` 合成底上）——读数里**逐个写清
      量的是哪一层**（上一轮"量具文件名也是判据"的教训）。

## 四、红证与读数

- [x] **红证**：① 摘掉一条登记 → 红；② 新加 `.tmp-probe{opacity:.4}`（不命中任何词法）→ 红
      （旧口径漏、新口径抓）；③ `@keyframes` 帧里的 `opacity` → **不**红；④ `disabled` 档带
      `opacity` → 正向红；⑤ 登记一条盘上没有的选择器 → 双向对账红。
- [x] **读数落盘**（本目录）：现算 **18 条活规则 / 在册 18 / 未在册 0**（对照改前 18 / 4 / 14）；
      `@keyframes` 帧 5 条仍排除；冻结数（机械面对数 / 族面格数 / 例外表）复算并解释。
- [x] 三套门禁：前端、浏览器门禁**单独跑**、全量 `pytest -n auto`。
- [x] 守卫头部"腿目录"注释：把腿⑧ 那句"禁用态 / 不可选形态不许用 `opacity` 表达"改写成
      **全量登记**口径（含"词法嫌疑面已退役"一句）。
