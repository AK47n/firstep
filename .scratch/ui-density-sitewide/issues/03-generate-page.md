# 03 — 生成页（做题主页面）复用同一套令牌与描边

**要做什么：** 用户每天待得最久的那一页——8 个步骤卡、推荐区、引脚配置、结果面板、任务卡、
准备度与交付——与检测页长成同一套：四级字号分得清、一屏只有一层完整描边、
"该点哪里 / 下一步看哪里"一眼可见。

**被谁阻塞：** 02（地基两单；页面单彼此独立，可与 04–07 任意顺序做）。

**状态：** resolved（2026-09-29；读数、逐层清单、门禁与双轴评审的账见文末「结论」）

## 这一页的家底（改前读数，2026-09-28）

| 项 | 实测 |
|---|---|
| 带页面前缀规则 | 212 条 |
| 裸 px 字号 | **134 处**（全站最大的一页） |
| 完整描边 | **82 处** |
| 裸令牌间距值 | 117 处 |
| DOM | 590 行（12 个页签里最厚） |
| 主要家族 | `.step-` / `.stepper` / `.task-` / `.tasks-` / `.res-` / `.pin-` / `.sugg-` / `.ov-` / `.score-` / `.param` / `.group-` / `.mainc-` / `.revise` / `.quick-` / `.wiring` / `.gen-` / `.gp-` / `.preread` / `.recent-` / `.rec-` / `.rc-` / `.fix-` / `.sp-` / `.draft-` / `.instance-` / `.readiness-check` |

> **口径更正（施工时按脚本复算，票面开工时那几个数含三处混算）**：
> ① 裸字号 **110 处**（不是 111）——探针当时算 111，含 `.recent-wf-summary` 那一处，
> 它渲染方是**设置页**（`ui/settings.js`），本单把谓词按渲染方改对后归还给 05；
> ② 裸令牌间距 **106 处**（探针那 109 里同样含 `.recent-wf-*` 的 3 处）；
> ③ 描边那一栏要分三个口径说：探针的"border 声明"口径 **74 → 57**（含单边分隔线与
> `border: 0`），其中**整圈完整框**（施工脚本口径）= **53 → 31**，改 24 条、留 29 条。


**不归这一单的**（归属由守卫的分区表说了算，别按"看着像哪页"改）：
`.mi-` / `.mc-` / `.module-card`（模块卡与模块说明弹窗 → 06 单一并改到位，见 06 票面）、
不带页面前缀的一次性 `#id` 规则（落在兜底 `shell`，01 已处理）。

**02 单移交过来的两笔**（写在这里免得漏）：

- **`.btn` 一族的另一半**：凡是选择器里带 `.param` / `.sugg-` / `.task-` / `.draft-` 字样的按钮
  （`.btn-params-*` / `.btn-task-dialog-*` / `.btn-task-edit-*` / `.btn-task-more` / `.btn-draft-*`
  / `.btn-global-chat-*`）按分区表归本单——02 只做完了判给 `components` 的那批
  （基类 / `--pill` / `--icon` / `.danger` / `.ghost` / `.mini`）。
- **`.task-dialog-box`**：任务卡里的对话面板，是**卡片内的整圈描边**（一屏一层要求内层去框 →
  留 `--panel` 底 + 一条上分隔线即可）。

## 验收标准

- [x] 本页作用域裸 px 字号 = 0（全走 `--fs-*` 六档，按角色判而不是按数值换算）——110 处逐条换令牌，
      复扫 0（`apply-03a-fonts.py` 的改后复扫 + `probe-01` 的 `generate` 行）。
- [x] 本页作用域"等于令牌却裸写"的 padding / margin / gap = 0——94 条声明（106 处取值）令牌化，
      复扫 0（`apply-03b-spaces.py`）。
- [x] **四级可辨**：卡片标题 20 / 小节标题 16 / 正文 14 / 说明 13 在本页成立（逐条见「结论 · 四级可辨」）；
      步骤标题（`1. 目标平台` 这一类）是全局 `.card h2` 的 `--fs-page` 20px、正文色，不再是灰字小字。
- [x] **一屏一层描边**：改前 / 改后逐层清单见「结论 · 逐层清单」；整圈完整框 **53 → 31**，
      31 条全部落在申报的例外里（语义告警块 / 可点控件 / 弹层外壳 / 单边 / 非框 / 顶层块）。
      **票面点名的那处硬骨头 `.card-group` 已处理**（整圈 → 3px 左条 + 淡底）。
- [x] **重点会跳**：选中 / 未选中的差别不依赖读文字（`.pin-role.bound` 的 3px accent 左条在
      底框改透明之后**更跳**；`.group-member.checked` / `.revise-tab.active` / `.ov-chip.current` /
      `.chip.rec` 各自有底色，见「结论 · 重点会跳」）；危险操作与主操作不撞色（口径单源 = 全局那三条，02 单已立）。
- [x] **空态安静**：能看见的四类空态（`.recent-empty` / `.revise-empty-hint` / `.quick-open-empty` /
      `.wiring-empty`）都退到 `--fs-note` + muted、且**没有整圈框**（`.revise-empty-hint` 改虚线左条），
      文案一字未删（`#generate-result` 那一批未生成时整块 `hidden`，不渲染）。
- [x] 契约：id 集合（569 = 569）/ 既有元素顺序 / 既有类名计数不变；中文文案零删除
      （`probe-03-contract-03.txt`）。
- [x] `SITEWIDE_BACKLOG` 摘掉 `generate` 那一条；守卫四条腿全绿（15/15；`generate` 现已是"已完工"作用域）。
- [x] 读数与截图落盘：`probe-00-after-03.txt` / `probe-01-scope-after-03.txt` /
      `probe-03-contract-03.txt` / `after-03-{js,browser,pytest}.txt`；
      **本页暗色整页图**入库，含"未生成"（`03-after-dark-generate-{top,full}.png`）与
      "已生成"（`03-after-dark-generate-generated-{result,full}.png`，由新探针
      `probe-02b-shot-generated.mjs` 真发一次生成拍出来）+ 改前对照 `03-before-dark-generate-full.png`。
- [x] 门禁：前端门禁零回归（1839 / 0）；浏览器门禁零回归（61 / 0，190s，**单独跑**）；
      另跑一次全量 pytest 复核 5656 + 11 skipped 不变（spec 说它只在 08 跑，本单改了
      `tests/js/**` 与探针，顺手证一遍）。

## 结论（形状、读数、逐层清单、账）

**形状。** 五件事，全在 `index.html` 的 `<style>` 块里（**`static/js/**` 一个字节没动**）：

1. **字号按角色就地上令牌**（`apply-03a-fonts.py`，110 处）：取值给基准档、角色定档，
   徽章/标签/图例→`--fs-tag`、说明/元信息→`--fs-note`、正文→`--fs-body`、小节标题→`--fs-block`、
   ✕ 这类行内图标随正文。**不做覆盖层**（上一轮 01 的账）。
2. **间距令牌化**（`apply-03b-spaces.py`，94 条声明 / 106 处取值）：保值变换，只动
   `padding` / `margin` / `gap`，`calc()` 跳过。施工方式是**扫描 + 整条声明当锚点 + 唯一命中断言
   + 复扫 0**，不是逐条手抄表（理由与偏离见「账」第 5 条）。
3. **内层完整描边换语言**（`apply-03c-borders.py`，24 条）：分组/面板 → `3px 左条 + 淡底`；
   "还没确认"这一档 → `3px 虚线左条`；条目盒 → 去框留淡底；整宽可点行 → `1px solid transparent`
   （悬停染色保留）。保留 29 条并逐条写理由（脚本里的 `KEEP` 表 = 下表）。
4. **补上"小节标题"那一档**（`apply-03d-title-roles.py`）：`.score-panel .title` / `.group-card .title`
   补 `--fs-block`（这一页没有 `<h3>`，`.pin-subtitle` / `.gen-recent-title` 已在 1 里升到 16）。
5. **双轴评审的 8 处整改**（`apply-03e-review-fixups.py`）：两处**分区表漏判**（见「评审处置」A1/A2）
   + 三处**语义回归**（`.rc-summary` 的死声明、悬停反馈静默失效、发送胶囊主次倒挂）
   + 两处**一致性**（`needs-choice` 琥珀告警恢复整圈框、`.recent-chip` 与同类可点行对齐）。

**读数。**

| 面 | 改前 | 改后 |
|---|---|---|
| 全站裸 px 字号 | 288 处 / 11 种 | **175 处 / 11 种**（−113） |
| `--fs-*` 令牌引用 | 130 处 | **245 处** |
| `generate` 裸字号 / 裸令牌间距 | 110 / 106 | **0 / 0** ✅ |
| `generate` 整圈完整描边 | 53 | **31**（全在申报的例外里） |
| 页面尺 `SITEWIDE_BACKLOG` | 11 条 | **10 条**（摘掉 `generate`） |
| 取值尺 `FROZEN_FONT_SIZES` | 11 条 | 11 条（取值尺**后段**才降：`11`/`11.5`/`12`/`12.5`… 要全站消失才摘得掉） |

**四级可辨（这一页每一层现在都能指出来）。**

| 档 | 这一页的落点 |
|---|---|
| 20 `--fs-page` | 12 张步骤卡的 `.card h2`（全局基类，01 单已做）+ `.gen-overview` 的标题级元素 |
| 16 `--fs-block` | `.pin-subtitle`（卡 7 分区名）、`.gen-recent-title`、`.score-panel .title`、`.group-card .title` |
| 14 `--fs-body` | 卡片说明（`.card-purpose` 走 13 那一档）、条目正文、`.sugg-msg`、`.score-row`、`.group-member`、`.rc-row`、`.sp-line`、结果块 `.res-value` |
| 13 `--fs-note` | `.muted` 一族、提示行、元信息、`.card-details`、空态、`.task-meta`、`.res-*` 说明 |

**重点会跳（选中 / 未选中的差别不靠读字）。**

| 那"一件" | 载体 | 本单做了什么 |
|---|---|---|
| 引脚角色行 | `.pin-role.bound` 的 3px accent 左条 | **变强**：底框改透明后，左条与"没绑"的差别更明显 |
| 功能组成员行 | `.group-member.checked` = `--accent-dim` 底 | 未动（已成立） |
| 卡内页签 | `.revise-tab.active` = accent 底 + accent 描边 + 600 | 未动（已成立） |
| 就绪 chip | `.ov-chip.current` / `.done` / `.warn` 三态底色 + 圆点 | 未动（已成立） |
| 推荐 chip | `.chip.rec` = `--ok-dim`（02 单复核过"与自建件行同一表达"） | 未动（已成立） |
| 悬停 | `.score-panel` / `.group-card` 左条转 accent；`.fix-row` / `.pin-role` / `.recent-chip` 透明框染色 | **本单新立/修复**（评审 B2） |
| 主 / 危险不撞色 | 全局三条口径（02 单单源），本页零副本 | 未动 |

**空态安静。** `.recent-empty`（"还没有生成记录——完成一次生成后会出现在这里"）13px muted；
`.revise-empty-hint`（"尚未加载输出目录——请先在「修订」页签加载当前会话或历史目录"）去掉整圈虚线框
只留虚线左条；`.quick-open-empty` / `.wiring-empty` 13px muted；`.res-board-msg` / `.res-board-missing`
13px muted。四类各自说清"生成后会出现什么 / 先做什么"，文案零删除。

**逐层清单（"一屏一层完整描边"到底留了哪一层）。** 整圈完整框 53 → 31，改 24 条：

| 层 | 改前 | 改后 |
|---|---|---|
| 步骤卡 `.card`（每屏那一条） | 1px `--border` | **保留**（"唯一那一层"） |
| 顶层块 `.gen-overview` / `.gen-recent` | 1px | **保留**（与 12 张卡同级，不是"卡里套面板"） |
| 修复中心错误条目 `.fix-row` | 1px 整圈 | 透明框（可点行）+ `--panel-2` 底 |
| 选型参考面板 `.sugg-panel` | 1px 虚线整圈 | 虚线左条 3px + 淡底 |
| 方案计数 `.sugg-count` / 选型元信息 `.sugg-meta` | 1px 整圈 | 去框（chip 内小字 / mono 元信息自己说话） |
| 商量面板 `.sugg-discuss-box` | 1px 整圈 | 去框 → `--panel` 底 |
| 对话气泡 `.sugg-msg.user` / `.ai` | 1px（accent / border） | 去框 → 靠 `--accent-dim` / `--panel-2` 底色分 |
| **任务卡商量面板 `.task-dialog-box`（02 移交）** | 1px 整圈 | 去框 + 一条上分隔线 + `--panel` 底 |
| 任务微编辑表单 `.task-edit-form` | 1px 整圈 | 去框 → `--panel-2` 底 |
| 参数卡 `.param-card`（参数表网格，一格一张） | 1px 整圈 | 去框 → `--panel-2` 底 |
| 评分点面板 `.score-panel` / 功能组卡 `.group-card` | 1px 整圈 | 左条 3px + 淡底 |
| main.c 磁盘状态行 `.mainc-disk-state` | 1px 整圈 | 去框 → `--panel-2` 底 |
| 结果块 `.res-block`（卡里并排 6 个） | 1px 整圈 | 左条 3px + 淡底 |
| 引脚角色行 `.pin-role` | 1px 整圈 | 透明框（`.bound` 的 3px accent 左条照旧） |
| **卡内分组 `.card-group`（01 结账时点名）** | 1px 整圈 | 左条 3px + `--panel-2` 底 |
| 页签空态引导 `.revise-empty-hint` | 1px 虚线整圈 | 虚线左条 3px + 淡底 |
| 资源总览表 `.res-table` / 评分点覆盖表 `.score-point-table` | 1px 整圈 | 去框 → 淡底（行间已有虚线分隔） |
| 板图包裹 `.res-board-wrap` | 1px 整圈 | 去框 → 淡底 |
| 上板自检折叠 `.task-check-details` | 1px 整圈 | 去框 → `--panel` 底（`.card-details` 同款） |
| 轮次记录 `.task-iteration` | 1px 整圈 | 去框 → `--panel` 底 |
| 「本轮变化」区 `.task-changes` | 1px 整圈 | 去框 → `--panel-2` 底 |
| 最近记录条目 `.recent-chip` | 1px 整圈 | 透明框（评审整改：与 `.fix-row` 同类） |
| 就绪摘要条 `.rc-summary` | 1px 整圈 | **保留**（评审整改：语义状态条，例外①；`.ok` 的绿框因此复活） |
| **保留 · 语义告警 / 状态条（例外①）** | `.preread-slot`（amber）/ `.pin-warn-list .wx` / `.task-phase` / `.task-next-hint` / `.res-board-legend .res-legend-conflict` / `.group-card.needs-choice`（评审整改后恢复整圈琥珀框） | 原样 |
| **保留 · 可点控件与控件形状（例外②）** | 按钮 / 输入框 / chip / 页签 / 胶囊 / 图例点 / spinner 圆环 / `.param-unit-chip` / `.pin-legend .lg` / `.recent-platform` / `.revise-tab-badge` | 原样 |
| **保留 · 弹层外壳（例外③）** | `.pin-menu`（含 head/list 的单边）/ `.quick-open-box` / `.task-more-menu` | 原样 |
| **保留 · 单边分隔线（例外④）** | `.fix-row .fix-source` / `.sugg-row` / `.sugg-discuss` / `.instance-row + .instance-row` / `.ov-summary` / `.card-group-title` / `.res-row` / `.res-group-title` / `.task-changes[open] > summary` / `.rc-row + .rc-row` / `.pin-role.bound` | 原样 |
| **保留 · 非框（例外④）** | `.quick-open-input` / `.quick-open-close`（`border: 0`）、`.sp-item` / `.step-nav .step-dot`（transparent） | 原样 |

**门禁读数。**

| 闸门 | 改前基线 | 改后读数 |
|---|---|---|
| 前端门禁 | 1839 / 0 | **1839 / 0**（两条既有断言按令牌形式改口径，见「账」第 7 条） |
| 浏览器门禁 | 61 / 0 | **61 / 0**（190s；**单独跑**，不与全量 pytest 并行） |
| 全量 pytest | 5656 + 11 skipped | **5656 + 11 skipped**（120s；spec 说它只在 08 跑，本单顺手复核） |
| 契约对账（`probe-03`，基线钉死 `bd478720`） | — | id **569 = 569**、检测页既有元素顺序逐项相等、中文文案删除 **0 行**、前端 JS 一个字节没动 |

**双轴评审（`code-review`：Standards + Spec 并行）的发现与处置。**

| # | 发现 | 处置 |
|---|---|---|
| Spec-A1 | **`generate` 的"裸字号 = 0"是假绿**：步骤 2 预读面板 `.topic-preread*` 由 `ui/generate-recommend.js` + `fx/topic-preread.js` 渲染**进生成页**，却按类名前缀 `\.topic-` 判给了赛题库 → 腿③放行 | ✅ 谓词按渲染方改（`\.topic-(?!preread)` + `\.topic-preread` 挂 `generate`），三条裸字号补令牌 → 复扫 0 |
| Spec-A2 | `.quick-open-*`（Ctrl+P 浮层）渲染方是**代码页**（`ui/quick-open.js` 的 `if (!codeTabActive()) return`），却归 `generate` 被本单改了 | ✅ `\.quick-` 挪到 `code`（04 单的腿）；**本单已改的那几处留着**（重做无谓返工）——如实记账（账第 3 条） |
| Spec-A3 | 「重点会跳」无证据 | ✅ 「结论 · 重点会跳」逐条点名载体；本单实际**新立/修复**的是悬停那三处 + `.bound` 的对比度 |
| Spec-C1 / Std-4 | `.rc-summary` 改 `border: none` 后 `.rc-summary.ok { border-color }` 成**死声明** | ✅ 恢复语义状态条的边框（例外①），`.ok` 绿框复活 |
| Spec-C2 | `.score-panel:hover` / `.group-card:hover` 与新的 3px 左条**同色** ⇒ 悬停静默失效 | ✅ 悬停时左条转 accent |
| Spec-C2b | `.group-card.needs-choice` 的琥珀告警由整圈框降成 3px 左条 | ✅ 恢复整圈琥珀框 + 加粗左条（例外①） |
| Spec-C3 | 四个发送胶囊 13px → `--fs-tag`(12)，与 `.btn-task-dialog-adopt` 同级 = 主次倒挂 | ✅ 改 `--fs-note`(13)：比紧凑胶囊高一档，也不把 16 塞进输入行 |
| Std-1 | 「已生成」态**整页**图被 `.gitignore` 吞掉（只入了视口图） | ✅ 补白名单 `03-after-dark-generate-generated-full.png` |
| Std-2 | 票面/守卫注释的「111 处」与脚本复算的 110 对不上；「74 处描边」与整圈口径 53 对不上 | ✅ 票面加「口径更正」，守卫注释改 110/106/53→31 并注明差在哪一处 |
| Std-3 | `apply-03a` 的覆盖率对账有**静默缝**：两边差集都空时列表不等却不报 | ✅ 改用 `Counter` 比重数（同一行两条规则同值也能判出） |
| Std-4 | 五支脚本各抄一份 `load_scopes` / `scope_of` / `rules_of`（Duplicated Code） | ✅ 新增 `scope_lib.py` 作单一出处（与探针口径逐项对齐：`generate` 409 / `shell` 228 / `components` 95），`dump-03-rules.py` 改为 import；**已跑完的四支不回头重写**（账第 6 条） |
| Std-5 | `apply-03a` docstring 写"相邻一档之内"，与 `.pin-subtitle` 12→16 的跳级自相矛盾 | ✅ 改成"按角色可跳级、理由逐条写"；停 13 的三处 caption 逐条写明判断 |
| Std-7 | `probe-03-contract.py` 的 diff 里混进一处与口径无关的空行删除 | ✅ 还原 |

**账（留给后面的人）。**

1. **探针的"border 声明"口径 ≠ "整圈完整框"。** 探针把 `border-top: 1px dashed`（单边分隔线，
   本轮明令保留）和 `border: 0` 都算进那一栏，所以 74 那个数**从来不是"74 个盒子"**。
   本单立的施工脚本口径（`full_border_lines`：完整 `border:` 且值不是 `none`/`0`）才好用
   ——04–07 单直接抄 `apply-03c` 的 `FIX`/`KEEP` 两张表 + 改前/改后集合对账那套。
2. **`.recent-wf-*` 三处（1 处字号 + 1 处整圈框 + 3 处令牌间距）转给了 05 单**：渲染方是
   `ui/settings.js`（设置页「最近 LLM 工作流」卡）。触发这次改判的正是 `.recent-wf-list{gap:8px}`
   ——它若留在 `generate`，腿②当场红。**05 单记得接这三处**。
3. **本单越界改了 `.quick-open-*`（4 处字号 + 5 处间距）**：它归代码页（04）。按 01 单账第 1 条
   的先例**如实记账、不回头撤**（撤了还得 04 再改一遍）。04 单接手时注意：这些已经是令牌形态了。
4. **`.llm-telemetry` 是跨页共享件**（生成页 5 处 + 母版库 `prog-llm-telemetry` 1 处），按分区表
   归 `generate`，本单统一成一档 `--fs-note`。05/07 复核时别当成"自己页面的漏网"。
5. **`apply-03b` 的施工方式与 README「逐条显式锚点」有偏离**：它是**保值变换**（`12px` →
   `var(--space-3)` 像素值不变），逐条手抄 100+ 条同形状的表只会增加抄错风险，所以改成
   "扫描取值 + 整条声明当锚点 + 唯一命中断言 + 改完复扫 0"。**这是判断，不是省事**：
   复扫用的判据与守卫/探针**同一处**（漏一条就停手，一个字节不写）。
6. **五支脚本的公共助手已经抽到 `scope_lib.py`**，但**已执行完的四支（03a–03d）没有回头改写**
   ——它们的锚点已被消费，重写等于把"可复算的证据"变成"只能读的中间态"（双轴评审没法再复算）。
   04 单起的新脚本一律 `from scope_lib import …`。
7. **动了两条既有断言的口径**（都是"等于令牌的数值必须走令牌"这条新纪律的必然结果，语义没变）：
   `tests/js/task-changes-refs.test.mjs` 的 `.task-changes { … border: 1px solid … }` → `border: none`；
   `tests/js/welcome-responsive.test.mjs` 的窄屏 `#tab-generate .gen-steps > .card { padding: 14px 16px }`
   → `14px var(--space-4)`。两处都在断言里写明了为什么。
8. **`probe-03-contract.py` 的口径补丁要单独记一笔**：它原先按**原始行**挑"删掉且含中文"的行，
   于是 01 单把 31 处内联 `font-size` 换成令牌之后，14 行"同一行既有中文文案又有内联取值"的行
   被报成删了文案 —— **01/02 两份读数里都挂着「契约对账 失败」**，而两张票尾写的是"0 行"，
   两者对不上。本单补上 `blank_inline_styles`（抹掉内联 `style="…"` 的值再 diff，与 spec
   「剥掉内联 style= 串之后逐字节相同」同口径），并在 docstring 里写明这条来龙去脉。
   **顺着这条看**：08 单重跑契约对账时，01/02 的结论这时才是机器可验的。
9. **读数每轮重跑这条纪律本单真咬到人**：评审整改动了 8 处 CSS 之后，`generate` 的裸令牌间距
   从 0 变回 1（`.topic-preread .preread-group-title` 的 `margin: 8px 0 2px` 随面板一起归回本页）
   ——只跑一次读数就会把它漏过去。

## 备注

- 这一页的选择态与展开收口有并发纪律（令牌 / 请求体快照 / 在途排队），**一行 JS 都不许动**。
- 分组与分段靠**新增类名 + 间距**表达，不搬 DOM（`tests/js/` 里按源码文本钉了 id 与顺序）。
- 若某条"重点会跳"只能靠改标记拿到，**停下来记账**（写清哪一条、为什么、代价），
  不要顺手把回归面从"样式"扩到"行为"。
