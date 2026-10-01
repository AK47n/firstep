# 04 — 全量登记：每条 `opacity<1` 都要在册（14 条补登 + 3 条抬值）

**要做什么：** 不可选形态登记表从"**嫌疑面驱动**"（类名词法 + `cursor: not-allowed` 两个代理信号）
改成"**全量驱动**"——样式块里每一条**活规则**只要写了 `opacity: <1`，就必须在登记表里有一条
带中文理由的记录。本轮补齐 **14 条**（全部 `dim`）；其中**三条是真文字、登记成"合法弱化"之后
实测仍低于 AA**，按拍板**去掉 `opacity`、字直接用 `--muted`**（浅 5.25 / 暗 5.67，与按钮禁用态同一格）。
同时把**词法嫌疑面整条退役**（全量登记之后它不再有判据用途）。

**用户可见变化：有**（三条文字比以前清楚：`.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`）。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

## 一、判据改造（守卫 + 两侧同步）

- [ ] **反向判据改成全量**：**活规则**（排除 `@keyframes` 帧）里出现 `opacity: <1` ⇒
      **必须**落在登记表里（两档都算），否则红，文案点名选择器。
      **旧口径的漏**要写进注释：旧口径下"换个不命中词法的类名"就没人管。
- [ ] **自检**（证明"不再依赖代理信号"）：给一条**已登记的规则改个名字**（改成不含任何嫌疑词、
      也不带 `cursor: not-allowed` 的选择器）——全量口径下**照样必须在册**（旧口径会漏）。
      这条自检要能在红证里复现。
- [ ] **词法嫌疑面退役**：`CONTRAST_DISABLED_HINTS`、`classHintHits`、`CONTRAST_HINT_VECTORS`
      **连同 Python 侧同名物、镜像腿、`probe-00-inventory.py` 的取数口径**一起走
      （不许留第二套口径；`tests/test_contrast_mirror.py` 的腿数与文件头说明同批改）。
- [ ] **正向判据不动**：`disabled` 档仍**不许**出现 `opacity`（认人面只收 `disabled` 档那半张表——
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

- [ ] **键格式**（照 `contrastRules` 归一化后的选择器原文）：`#tab-hwcheck .empty-state .es-icon`
      与 `.empty-state .es-icon` 是**两行**；`.card-details > summary::before` 的 `>` 与 `::before`
      原样；`.sugg-msg .muted`（后代）别写 `.sugg-msg.muted`。
- [ ] **两侧钉死**：登记表要**同时**改守卫与 Python 口径（镜像腿逐条比 `(作用域, 选择器, 类别)`，
      两侧理由都必须非空）。别只改一侧——那正是本仓最怕的"腿绿而读数红"。
- [ ] **两处注释/基线回改**：守卫里那段「够不着的那 14 条（明写的边界）」（它现在要改成
      "已全量登记"）+ `probe-00-inventory.py` 的 `RECON_BASELINE` 口径说明。

## 三、三条抬值（产品面 + 真像素）

- [ ] `.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`：**去掉 `opacity`**，文字用
      `--muted`（与按钮禁用态同一格；浅 5.25 / 暗 5.67）。改完它们**不再有 `opacity`** ⇒
      按判据③ 双向对账，这三条要不要留在登记表里（留 = 死条会被判红；不留 = 它们不再有 opacity、
      本来也不该在册）——**按盘上事实定**，红证里把这条走通。
- [ ] **真像素改前 / 改后**（两主题）：三条各出一组，证明"字变清楚了、没有别的变化"。
      探针**先量改前**（用改动前的 `index.html`，读完复原并核 sha256），再量改后。
- [ ] 三条的底各不相同（`.res-soft` 行无底色 / chip 是 `--panel-2`；`.chip.rec.unsel .reason`
      底 `transparent`；`.sugg-count` 压在 `rgba(139,148,158,.15)` 合成底上）——读数里**逐个写清
      量的是哪一层**（上一轮"量具文件名也是判据"的教训）。

## 四、红证与读数

- [ ] **红证**：① 摘掉一条登记 → 红；② 新加 `.tmp-probe{opacity:.4}`（不命中任何词法）→ 红
      （旧口径漏、新口径抓）；③ `@keyframes` 帧里的 `opacity` → **不**红；④ `disabled` 档带
      `opacity` → 正向红；⑤ 登记一条盘上没有的选择器 → 双向对账红。
- [ ] **读数落盘**（本目录）：现算 **18 条活规则 / 在册 18 / 未在册 0**（对照改前 18 / 4 / 14）；
      `@keyframes` 帧 5 条仍排除；冻结数（机械面对数 / 族面格数 / 例外表）复算并解释。
- [ ] 三套门禁：前端、浏览器门禁**单独跑**、全量 `pytest -n auto`。
- [ ] 守卫头部"腿目录"注释：把腿⑧ 那句"禁用态 / 不可选形态不许用 `opacity` 表达"改写成
      **全量登记**口径（含"词法嫌疑面已退役"一句）。
