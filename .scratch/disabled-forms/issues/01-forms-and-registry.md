# 01 — 三处不可选形态改灰底灰字 + 判据⑥认人面扩成登记表

**要做什么：** 浅色主题下三处"这个组合不成立"的形态不再用 `opacity` 整体变淡，改成**读得清**的形态
（灰底灰字或形状信号）——「需切换平台」的模块卡、引脚菜单里「不兼容：…」的行、锚失效的参数卡，
它们的字从 2.16–3.40 抬到 5.25 以上；不可选的辨识改由**形状**承担（虚线 / `not-allowed` / 无 hover /
既有警示标签）。同时把判据⑥的认人面从"写死两个类名"扩成**登记表 + 反向嫌疑面**：盘上再有人用
`opacity` 表达"不可选"，前端门禁当场红，且文案点名选择器。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-10-01；结论与双轴评审处置见文末）

## 一、产品面（`src/contest_generator/static/index.html` 样式块）

- [x] **`.module-card.off`**：删 `opacity: .55`；底 `--panel-2` → **`--panel`**（与所在 `.card` 同底 =
      "退到背景里"）；**`border-style: dashed`**（形状信号，宽/色沿用 `.module-card` 的 `1px solid --border`
      那条，不新造颜色）；`cursor: not-allowed` 保留。**不声明 `color`**——卡内文字各自声明色照旧
      （slug `--text` on `--panel` = 浅 15.80 / 暗 14.64；`.mc-desc` 的 `--muted` = 浅 6.59 / 暗 6.06），
      彩色徽章保留原色。
- [x] **`.module-card.off .mc-info`**（连带，防糊成一片）：off 卡上「详情」按钮的底从 `--panel` 改
      `--panel-2`——它**仍是可用**的（看模块说明与"能不能用"无关），不许跟着一起弱化。
      ⚠ 位置**排在同权重的 `.mc-info:hover` 之前**（两条都是 (0,3,0)，靠后者胜）——否则悬停反馈被吃掉。
- [x] **`.pin-menu-list li.cant`**：`opacity: .5` → **`background: var(--panel-2)` + `color: var(--muted)`
      + `cursor: not-allowed`**（与 `button:disabled` 同一对色：浅 **5.25** / 暗 **5.67**）。
- [x] **`.pin-menu-list li.can:hover`**（连带）：底从 `--panel-2` 改 **`--accent-dim`**——否则悬停时
      与不可选行的静底同色，读起来像"这行也不能点"（`--accent-dim` 是仓里既有的 hover 语汇：
      `.mc-info:hover` / `button.ghost:hover`）。
- [x] **`.param-stale`**：删 `opacity: .65`（卡面本来就是 `--panel-2`，字各自声明色：`--text` 12.59 /
      `--muted` 5.25）；加 **`outline: 1px dashed var(--warn-border)`**（形状信号，与 off 卡的虚线同语言；
      `outline` 不吃布局、不入描边登记簿）+ 徽章保留。
- [x] **`aria-disabled="true"`**：`fx/module.js` 的 `moduleGridHTML` 在 `off` 卡上加这个属性
      （仍可聚焦、仍可点、点了仍弹那句 toast——语义由 aria 承担，类名继续表示"这个组合不成立"）。
      一处渲染、两个页面（生成页 + 检测页器件网格）同时生效。

## 二、判据扩面（`tests/js/css-tokens.test.mjs` 腿⑧）

- [x] **登记表**：`CONTRAST_DISABLED_FORMS` = `[作用域, 剥注释的选择器, 类别, 理由]`；
      类别词表 `CONTRAST_DISABLED_FORM_KINDS = ["disabled", "dim"]`。首批 **7 条**（现算复核过）。
- [x] **正向判据（⑥延伸）**：认人面（`:disabled` / `.disabled` 原样 + 登记表里 `disabled` 类）命中的规则里
      出现 `opacity: <1` ⇒ 红。
- [x] **反向判据（新）**：**活规则**（排除 `@keyframes` 帧）里出现 `opacity: <1`，且命中任一嫌疑信号——
      ① 同规则有 `cursor: not-allowed`；② 选择器里的类名逐字命中 `CONTRAST_DISABLED_HINTS`
      ——**必须**落在认人面里，否则红，文案点名选择器并指路"登记进 `CONTRAST_DISABLED_FORMS`"。
- [x] **双向对账** + 类别表形状（每类至少一条 / 不重复登记 / 理由非空 / 作用域非空）。
- [x] **边界（写进注释）**：`@keyframes` 帧不判 / `:not(…)` 剥掉再判 / 判据宁可过宽（`dim` 也接受）/
      ⑥的旧边界就此闭合 / 14 条不在射程 + 为什么。⚠ **正反两半的认人面不是同一张**（正向只收
      `disabled` 档，反向两档都收）——合成一个会把 `.pin-dim` 这类合法弱化误判成红（实施期实测踩到）。
- [x] **镜像**：`CONTRAST_DISABLED_FORMS` / `CONTRAST_DISABLED_HINTS` / `CONTRAST_DISABLED_FORM_KINDS`
      / `CONTRAST_DISABLED_RE` / `KEYFRAME_SEL_RE` 同批写进 `.scratch/light-contrast/probe_lib.py`，
      `tests/test_contrast_mirror.py` 加四条断言（25 → 29 条）。
- [x] **冻结数复算**：`CONTRAST_PAIR_COUNT` **392 → 394**（现算复核，正是票面预期）；
      族面格数 **172 不变**；例外表**无新增**；`CONTEXT.md` 的「对比度契约」行同批回改。
      另加 `test_pair_count_freeze_matches_python`（机械面配对数的跨语言现算复核）——
      **这一条超出票面字面**（票面只要 FORMS/HINTS 的镜像），但它是"394 以现算为准"这条纪律的
      唯一执行者（与既有 ⑦′ 族面格数同一物种），理由记在票尾。

## 三、证据与门禁

- [x] **红证** n1–n6（照 `code-contrast/03` 的 n 系列写法）：n1 放回 `opacity: .55` → 正向红；
      n2 `.tmp-probe.off{opacity:.4}` → 反向红（词法）；n3 `.tmp-probe.k{opacity:.4;cursor:not-allowed}`
      → 反向红（光标）；n4 表里塞一条盘上没有的选择器 → 双向对账红；n5 `:not(.off)` 与 `@keyframes`
      帧里的 `opacity` **不**红；n6 `dim` 档带 `opacity` **不**红、改登成 `disabled` 就红。
      每条都带"锚点/注入没生效"的断言（含两条"注入真的进了解析面"的断言）。
- [x] **`probe-00-inventory.py` 复跑入库**：§1 现算 23/5/18/4 并**并列 recon 基线** 26/5/21/7（差 −3）；
      §2 三处目标的"改后"列与票面逐格一致；§4 现算 **394 / 172**。
- [x] **前端门禁**：`node --test "tests/js/*.test.mjs"` **1845 / 0**；**浏览器门禁**（单独跑）
      **61 / 0**——⚠ 见票尾第 3 条（它先红过一次，红得有价值）。
- [x] **读数落盘**：`probe-01-inventory-after.txt` / `probe-01-js-gate.txt` / `probe-01-browser-gate.txt`
      （recon 那张改前照片 `probe-00-inventory.txt` 原样保留）。

## 结论（读数与账）（2026-10-01）

### 1. 三处形态：改前 → 改后（口径 = `probe-00-inventory.py` §2，两模型都报）

| 形态 · 文字 | 改前（浅色）模型 A / B | 改后 浅 / 暗 |
|---|---|---|
| `.module-card.off` 说明字 | 2.16 / 2.24 | **6.59 / 6.06**（`--muted` on `--panel`） |
| `.module-card.off` slug | 3.22 / 3.40 | **15.80 / 14.64**（`--text` on `--panel`） |
| `.pin-menu-list li.cant` 原因行 | 2.23 / 2.23 | **5.25 / 5.67**（与按钮禁用态同一格） |
| `.pin-menu-list li.cant` 角色名 | 3.16 / 3.16 | **12.59 / 13.70** |
| `.param-stale` 提示行 | 2.59 / 2.65 | **5.25 / 5.67** |
| `.param-stale` 参数名 | 4.32 / 4.53 | **12.59 / 13.70** |

**模型口径（spec §4 要求写明）**：A = 整块（字 + 自己的底）一起压到祖先底上（probe-08 的几何）；
B = 字往元素自己声明的底上拉平、底不动（票面 `浅 3.40 / 2.24` 那个口径）。**两者别混着读**；
真像素以 02 号单为准。
**连带两处**（`probe-00` §5 现算）：off 卡上 `.mc-info` 的 `--accent-text` on `--panel-2` = 浅 5.53 /
暗 9.14（仍可用、仍达标）；`.mc-plat.un` 徽章（底是 `rgba(139,148,158,.15)`）在 off 卡换底前后
浅 4.68 → **5.72**、暗 4.52 → **4.85**（都过 4.5，换底没把它压暗）。

### 2. 判据与冻结数

| 项 | 读数 |
|---|---|
| 认人面 | 登记表 7 条（`disabled` 3 + `dim` 4）＋ 原 `:disabled` / `.disabled` 正则那半 |
| 反向嫌疑面 | 现算 4 条（改前 7 条），**全部在册**；正向认人面里带 `opacity` 的规则 **0 条** |
| 机械面配对数 | 392 → **394**（`.pin-menu-list li.cant` 从"只有 `opacity`"变成"既有 `color` 又有 `background`"，两主题各 +1 对） |
| 族面格数 | **172 不变**（用的两对早已在 `code-contrast/03` 建的禁用底族里） |
| 例外表 | **0 条新增**（新对 5.25 / 5.67 达标） |
| 跨语言镜像 | 25 → **29 条**（本单 +4） |

### 3. ⚠ 浏览器门禁先红过一次——红得有价值（本轮新踩，值得记）

第一发整支浏览器门禁 **60 / 1**：`hwcheck.spec.mjs:612` 点 `[data-add="sr04"]` 那张 off 卡时
**30.9 s 超时**，日志原文 `element is not enabled`。根因不是产品坏了，而是
**Playwright 的 actionability 检查把 `aria-disabled="true"` 当"不可点"**（`aria-disabled` 与
`disabled` 属性不同：它不拦事件、不夺焦点，真人点击与键盘回车照旧，产品侧照旧弹解释）。
处置：那一步明写 `{ force: true }` 并把原因写进用例注释（断言一个字没放宽——它要证的
"点了会点名「无法检测」"仍然真跑）。**判读纪律**：下次遇到"`aria-disabled` 元素点不动"，
先想到这条，别去查产品。复跑：整支 **61 / 0**。

### 4. 双轴 `code-review` 处置

| # | 轴 | 发现 | 处置 |
|---|---|---|---|
| 1 | Std + Spec | `CONTEXT.md` 写镜像守卫 **28** 条，实测 **29**（本单 +4，却只写"加两条"） | ✅ 回改成 29 并逐条列出四条；同一句把"加两条"改成"加四条" |
| 2 | Std | 守卫注释里那组 `26 / 5 / 21 / 7` 没标口径，按纪律③复算（现算 23/5/18/4）对不上 | ✅ 改写成"**recon 那一刻**（`RECON_BASELINE`）26/5/21/7 ↔ **本单落地后现算** 23/5/18/4，两种读法下不命中信号的**都是 14 条**" |
| 3 | Std | `tests/test_contrast_mirror.py` 头注释仍写「**九组**」，编号表已列到第 10 条 | ✅ 改「十组」 |
| 4 | Std | `浅 2.16–3.40` 横跨两个模型（A：3.22/2.16，B：3.40/2.24），spec §4 自己要求写明模型 | ✅ `CONTEXT.md` 与守卫注释两处都拆成"模型 A … / 模型 B …" |
| 5 | Std（判断项） | `probe-00` 里 `hint_hits()` 纯转发 `plib.class_hint_hits`、`split_rules()` 是 `plib.css_rules` 的薄适配、`CLASS_RE` 死常量 | ✅ 三处都去掉，直接调 `plib`（`css_rules` 的空白归一比原来更贴守卫口径） |
| 6 | Std（判断项） | `probe-00` 注释把本机环境文件写成 `.scratch/local-environment.md`（无此文件） | ✅ 改成 `docs/agents/local-environment.md` §0 |
| 7 | Spec | 票面「§1 活规则 21 条不变、嫌疑面 7 条全在认人面里」按字面**已经不成立**（改完三处就没有 `opacity` 了） | ⚖ **不回改票面**：票面是"当时的要求"，改后必然变小 3；探针并排打印 recon 基线 + 现算差（−3），并在守卫注释里写明"这是改对了的样子，不是探针坏了" |
| 8 | Spec | `test_pair_count_freeze_matches_python` 超出票面字面（票面只要 FORMS/HINTS 一组镜像断言） | ⚖ **保留**：本单动了 `CONTRAST_PAIR_COUNT` 这个跨语言口径数（394），而它此前只有 JS 侧自证；这条与既有 ⑦′（族面格数）同一物种，正是"口径单源两份拷贝 → 加镜像断言"那条硬约束的落点 |
| 9 | Std（判断项） | 守卫注释 3 处指路 `backlog.md §33`，而 §33 还没开（现止 §32） | ⚖ 悬空只在 01 落地到 03 之间；**03 号单同批开 §33**，并在守卫注释里注明"开之前这两处是悬空的" |
| 10 | Std（判断项） | `26/5/21/7` 这组数在 spec / 工单 / 守卫注释 / 探针 `RECON_BASELINE` 共四份 | ⚖ spec 与工单是**当时的要求**（档案，不回改）；活的四份里守卫注释已改成指向 `RECON_BASELINE` 这个单源，03 的 `backlog §33` 写同一份 |

### 5. 范围外（逐条）

改名 `.disabled`（用户拍板不改，语义由 `aria-disabled` 承担）；全站 `opacity` 全量登记（腿⑩，
14 条不在射程的理由写进守卫注释与 03 的 §33）；JS 内联 `opacity` 与 SVG `fill-opacity`；
真像素与人眼截图（02 号单）；三套门禁与文档收口（03 号单）。**后端与 AI 路径零改动**，
用户可见文案**一个都没改**。

**范围外**（本单不做，别顺手）：改名 `.disabled`（用户拍板不改）；全站 `opacity` 全量登记（腿⑩）；
JS 内联 `opacity` 与 SVG `fill-opacity`；真像素与人眼截图（02 号单）；三套门禁与文档收口（03 号单）。
