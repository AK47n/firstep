# 06 — 素材与库页（模块库 / 参考文件库 / PDF / Markdown / 赛题库）复用同一套令牌与描边

**要做什么：** 五个"翻库"页面（模块库、参考文件库、PDF 资料库、Markdown 资料、赛题库）
共用一套列表 / 卡片 / 详情弹层，本轮把这**一套**统一到检测页那套台阶上——
做完之后五个页面同时变样，而且彼此长得一样。

**被谁阻塞：** 02（地基两单；页面单彼此独立）。

**状态：** resolved（2026-09-28；读数、逐层清单、门禁与双轴评审的账见文末「结论」）

## 这几页的家底（改前读数，2026-09-28）

| 页 | 家族 | 裸 px 字号 | 完整描边 |
|---|---|---|---|
| 模块库 | `.lib-` / `.module-` / `.mc-` / `.mi-` | 15 | 11 |
| 参考文件库 | `.ref-` | 14 | 7 |
| 赛题库 | `.topic-` | 15 | 5 |
| Markdown 资料 | `.md-` | 2 | 1 |
| PDF 资料库 | `.pdf-` | 1 | 0 |
| **合计** | | **47** | **24** |

**共同点（这一单的抓手）**：五页的内容都渲染在**同一套**列表骨架（`.lib-*`）与
**同一套**详情弹层里，所以"改一处、五页同时生效"；`module-card` 是模块库与生成页共用的组件，
**这一单要把它一次改到位**（生成页那一单不再重复改它）。

> **口径更正（开工时按脚本复算，README 坑 7；票面三处要分开读）**：
> ① 裸 px 字号按现表复算 = **63**（模块库 32 / 参考 14 / PDF 1 / MD 2 / 赛题 14）——
> 票面的"模块库 15"写在 03 单把 `.mi-` / `.mc-` / `.module-card` **判给本页之前**
> （03 票面点名"→ 06 单一并改到位"）；赛题 15 → 14 则差在 `.topic-preread` 那处被 03 归还给
> 生成页。**两句都在票面上，按现表算才对得上脚本。**
> ② 完整描边同样分两个口径：票面 24 是**探针"border 声明"口径**（含单边与 `border: 0`），
> 真正要处置的**整圈完整框** = **20** 处（library 12 / reference 3 / pdf 0 / md 1 / topic 4）。
> ③ **"模块卡三个消费点"要按渲染方数**：`fx/module.js` 的 `moduleGridHTML` 被
> `ui/generate-recommend.js`（生成页模块池）与 `ui/hwcheck-core.js`（检测页器件网格）调用
> ——**两处渲染 `.module-card`**；模块库页共用的是**详情弹窗**（`moduleInfoHTML` / `.mi-*`）
> 与里面的 `.mc-plat` 小胶囊。本单把三处都覆盖到了（同一批类名，改一处三处生效）。

## 验收标准

- [x] 五页作用域裸 px 字号 = 0；裸令牌间距值 = 0——**63 处字号**逐条换令牌、
      **47 条声明（51 处取值）**间距令牌化，复扫五页全 0（`apply-06a` / `apply-06b` +
      `probe-04-scope-calibers.py` 五个作用域）。
- [x] **列表 / 卡片 / 详情三层级分明**（见「结论 · 三级」）：列表走**全局 `table` 基类**
      （`--fs-body` 14 + 单边行分隔 + `thead th` 底纹，在 `shell` 作用域，01 单已做）；
      卡片的条目名 / 题号 / 预览 14、元信息 13、胶囊 12；详情弹层标题 16、正文 14、脚注 13。
- [x] **一屏一层描边**：逐层清单见「结论 · 逐层清单」；整圈完整框 **20 → 13**
      （去框 7 条：`.mi-reason` / `.mi-plat` / `.lib-edit-old` / `.add-section`（左条）/
      `.ref-scroll` / `.md-preview-body` / `.topic-detail-problem`；留 13 条逐条写理由）。
      **列表本身不套框**：它一直用的是全局 `table` 的单边行分隔 + `thead th` 底纹
      （`shell` 作用域，01 单已做）——本单只核了"没有页面自己再给表格加一圈框"
      （`#tab-*.card { overflow-x: auto }` 那几条只做横向滚动）。
- [x] **健康 / 状态徽章统一**（见「结论 · 徽章统一」）：三类落点——徽章（`.badge` 基类 +
      五种语义色对）、统计条（`.lib-stats-red` / `.ref-dangling-count` 本就是同一条规则；
      **`.lib-dangling-count` 本单并入同一套表达**——它此前是一条独立规则）、
      **行内 ⚠ 警示标**（`.dangling-tag` / `.ref-dangling-tag` / `.topic-warn`：本单把字号
      `--fs-tag`、字重 600、颜色 `--danger` 三项对齐成同一套表达）。
      **「模块的身份缺失」这一类如实记账**（见「账」第 4 条）：票面点的四类里，PDF 损坏 / 疑似重复、
      参考缺失、赛题程序悬空**三类真有"⚠ 徽章 + 统计条"**；模块身份那类**没有徽章**——
      器件缺 `kit` / 来源链接时按 identity-fields/05 的口径**零渲染**（不标豁免、不摆空行），
      内部件 / 协议切片才标「无需购买链接」。本单只改了 `.mi-note` 那一行的字号与间距，
      **没碰任何词表、文案与判据**（造一个新徽章要改渲染方 = JS，超出本轮契约）。
- [x] **`module-card` 改到位**：`.module-card` / `.mc-*` 在**生成页模块池**与**检测页器件网格**
      两处渲染（同一个 `moduleGridHTML`），模块库页共用**详情弹窗**（`.module-info-*` / `.mi-*`，
      弹窗里的平台胶囊复用 `.mc-plat`）——三处走同一批类名，本单一次改完，
      形态由同一组规则保证（`…-library-modal.png` 是弹窗那一张的证据）。
- [x] 契约：五个页签的 id 集合 / 既有元素顺序 / 既有类名计数不变；中文文案零删除
      （`probe-03-contract-06.txt`：全部通过）。
- [x] `SITEWIDE_BACKLOG` 摘掉这五条（现 **3** 条：master / changelog / guide）；守卫四条腿全绿（15/15）。
      顺带：取值尺 **10 → 7**（`11.5` / `15` / `18` 三个取值在本单之后**全站彻底消失**，
      照 02/04 先例摘条）。
- [x] 读数与截图落盘：`probe-00-after-06.txt` / `probe-01-scope-after-06.txt` /
      `probe-03-contract-06.txt` / `after-06-{js,browser}.txt`；**五页各一张暗色整页图**
      （`06-after-dark-{library,reference,pdf,md,topic}-full.png`）+ **详情弹层一张**
      （`06-after-dark-library-modal.png`，`probe-06-shot-modal.mjs` 点真行打开、
      并断言"四问分段有内容 + 平台小卡已去框"）。
      另立一支**死类普查**（`probe-06-dead-classes.py`）：五页相关类名 150 个里 36 个
      CSS 从未出现——逐个看过，**全是 JS 挂钩类名**（表单字段 / 按钮，形状由标签与全局
      `button` 规则给），不需要补形状（结论与名字见「账」第 5 条）。
- [x] 门禁：前端门禁零回归（**1839 / 0**）；浏览器门禁零回归（**61 / 0**，**单独跑**）。

## 结论（形状、读数、逐层清单、账）

**形状。** 五件事，四件在 `src/contest_generator/static/index.html` 的 `<style>` 块里
（**`static/js/**` 一个字节没动**），一件在守卫：

1. **字号按角色就地上令牌**（`apply-06a-fonts.py`，63 处）：五页共用一套判定——
   条目主字 / 正文 / 要读的内容（含 mono 代码与路径）→ `--fs-body`(14)；
   说明 / 元信息 / 表头 / 提示 / 统计 → `--fs-note`(13)；徽章 / 胶囊 / chip / 箭头 /
   行内警示标 / 小按钮 → `--fs-tag`(12)；**弹层与区块的标题（独占一行、给一整块命名）→
   `--fs-block`(16)**（`.module-info-title .slug`、`.ref-detail-title`、`.add-section-head`、
   `.topic-detail-*title`）。
2. **间距令牌化**（`apply-06b-spaces.py`，47 条声明 / 51 处取值）：保值变换；本趟带
   **覆盖率断言**（每页取值数必须与申报一致，05 单评审点名的那条）。
3. **内层整圈框换语言**（`apply-06c-borders.py`，7 条）：去框留淡底 6 条 + `.add-section`
   换左条（它是"三块表单的分组"，照 03 单 `.card-group` 先例）；保留 13 条逐条写理由。
4. **行内 ⚠ 警示标统一**（`apply-06d-new-rules.py`）：`.dangling-tag` / `.ref-dangling-tag` /
   `.topic-warn` 的字号（`--fs-tag`）、字重（600）、颜色（`--danger`）三项对齐，
   并把"这一族是同一套表达"写进注释（**不合并成一条规则**——分属两个作用域，
   合并会动分区表归属与两条腿的射程）。
5. **守卫**（`tests/js/css-tokens.test.mjs`）：摘掉页面尺的五个作用域 + 注释里记下 20 → 13
   与"去框 7 条"；**取值尺摘掉 `11.5` / `15` / `18`**（本单之后全站彻底消失）。

**读数。**

| 面 | 改前 | 改后 |
|---|---|---|
| 全站裸 px 字号 | 99 处 / 10 种 | **36 处 / 7 种**（−63） |
| `--fs-*` 令牌引用 | 327 处 | **391 处**（+64） |
| 五页裸字号 / 裸令牌间距 | 63 / 51 处取值（47 条声明） | **0 / 0** ✅ |
| 五页整圈完整框 | 20 | **13**（去 7） |
| 页面尺 `SITEWIDE_BACKLOG` | 8 条 | **3 条**（摘掉五条） |
| 取值尺 `FROZEN_FONT_SIZES` | 10 条 | **7 条**（摘 `11.5` / `15` / `18`） |

**三级（列表 / 卡片 / 详情，不靠逐字读就能分辨）。**

| 级 | 落点 |
|---|---|
| 页面标题 20 `--fs-page` | 五页的 `.card h2`（全局基类，01 单已做） |
| 弹层 / 区块标题 16 `--fs-block` | `.module-info-title .slug`、`.ref-detail-title`、`.add-section-head`、`.topic-detail-problem-title` / `.topic-detail-pages-title` |
| 正文 / 条目 14 `--fs-body` | 全局 `table`（列表单元格）、`.ref-pick-title`、`.ref-detail-row`、`.topic-key` / `.topic-preview` / `.topic-detail-problem`、`.module-info-body`、`.mi-plat h4`、`.lib-edit-old`、`.ref-files-list li`、`.ref-files-filter`、`.topic-edit-field textarea`…… |
| 说明 / 元信息 13 `--fs-note` | `.muted` 一族、表头 `.ref-pick-head`、`.topic-meta`、`.lib-stats`、`.mc-desc`、`.mc-head .slug`、`.mi-row` / `.mi-files` / `.mi-file` / `.mi-note` / `.mi-pins`、`.pdf-trash-members`、`.ref-files-viewer pre`…… |
| 徽章 / 胶囊 / 标记 12 `--fs-tag` | `.mc-plat` / `.mc-offtag` / `.mc-deps` / `.mc-pa` / `.mc-info`、`.lib-chip`、`.topic-year`、`.dangling-tag` / `.ref-dangling-tag` / `.topic-warn`、`.add-section-arrow`、`.topic-page figcaption`、**`.md-row-file`（列表行第二行的小字——13 会与主行 14 并平，评审实测后改回 12）**…… |

**徽章统一（三类落点，一处定义）。**

| 类 | 现状 | 本单动作 |
|---|---|---|
| 徽章 | `.badge` 是全局基类；五页的具体徽章**只声明语义色对**（`--danger-dim/--danger`、`--warn-dim/--warn`、`--accent-dim/--accent`、`--info-dim/--info`、`--ok-dim/--ok-bright`）：`.badge.pdf-broken` / `.pdf-dup`、`.badge.ref-topic` / `.ref-kit` / `.ref-none`、`.mc-plat.ok/hw/un/embed` | **不改**（已经是一处定义；`grep` 复核过没有自造颜色值） |
| 统计条 | `.lib-stats-red` / `.ref-dangling-count` **本来就是同一条规则**（选择器组共用）；`.lib-dangling-count` 此前是**独立规则**（颜色/字重逐字相同、字号裸着） | **并入同一套表达**（补 `--fs-note` + 注释写明"它不可点"——`ui/library.js` 那句「点击详情确认」指的是点行进详情） |
| 行内 ⚠ 警示标 | `.dangling-tag` / `.ref-dangling-tag`（400 重）与 `.topic-warn`（600 重）**字重不一致** | **对齐**（字号 / 字重 / 颜色三项同一套表达，`cursor` 按语义分） |

**逐层清单（"一屏一层完整描边"到底留了哪一层）。** 整圈完整框 20 → 13：

| 层 | 改前 | 改后 |
|---|---|---|
| 列表（五页的表格） | 全局 `table` + `th, td` 单边下分隔 + `thead th` 底纹（**本来就没有整圈框**） | 原样（本单只核，不改——它在 `shell` 作用域，01 单已做） |
| `.mi-reason`（推荐理由块） | 1px 整圈 | **去框** → `ok-dim` 淡底 |
| `.mi-plat`（平台小卡） | 1px 整圈 | **去框** → `panel-2` 淡底（块间 10px 间距） |
| `.lib-edit-old`（「当前简介」原文块） | 1px 整圈 | **去框** → `panel-2` 淡底 |
| `.add-section`（「添加模块」三个分区） | 1px 整圈 | **左条 3px + 淡底**（照 03 单 `.card-group`） |
| `.ref-scroll`（步骤 4 参考资料滚动清单） | 1px 整圈 | **去框** → `panel-2` 淡底 |
| `.md-preview-body`（md 预览内容面） | 1px 整圈 | **去框** → `code-bg` 淡底（文档面照样板 `pre.result`） |
| `.topic-detail-problem`（题面全文阅读面） | 1px 整圈 | **去框** → `--bg` 淡底 |
| **保留 · ② 可点卡片 / 控件 / 标签胶囊** | `.module-card`（生成页模块池 + 检测页器件网格共用）、`.mc-info`、`.lib-chip`（**过滤 chip 与表格里的批次胶囊两处都在用**——留框按"控件形状"那一档申报）、`.topic-card`、`.topic-year`（**同理：它是纯 `<span>`，不是可点控件；按"标签胶囊一族"的控件形状保留**，同 04 单 `.code-kbd` 键帽先例）、`.ref-files-filter` | 原样 |
| **保留 · ① 语义告警** | `.mc-offtag`（平台不兼容）、`.module-info-off` | 原样 |
| **保留 · ③ 弹层外壳** | `.module-info-modal`、`.lib-edit-modal`、`.ref-files-modal`（**跨页共享**：6 个 `ui/*.js`） | 原样 |
| **保留 · ⑤ 表格网格 / 文档渲染** | `.mi-pins th, td`（引脚表）、`.topic-page img`（扫描件图片框） | 原样 |

**门禁读数。**

| 闸门 | 改前基线 | 改后读数 |
|---|---|---|
| 前端门禁 | 1839 / 0 | **1839 / 0** |
| 浏览器门禁 | 61 / 0 | **61 / 0**（**单独跑**，不与全量 pytest 并行） |
| 守卫本体 | 15 / 0 | **15 / 0**（四条腿 + 合成红证） |
| 契约对账（`probe-03`，基线钉死 `bd478720`） | — | id **569 = 569**、既有元素顺序逐项相等、中文文案删除 **0 行**、`static/js/**` 一个字节没动 |

**双轴评审（`code-review`：Standards + Spec 并行）的发现与处置。**

| # | 发现 | 处置 |
|---|---|---|
| Std-1 / Spec-c1 | **跨页副作用没记账**（README 04 账第 13 条）：① `.ref-files-close` 18 → 14 是**全站弹层的 ✕**（exit-guard / overlay / confirm / codeeditor / codeview / master / md / pdf / topic / 设置页各弹层都在用）；② `.ref-pick-*` / `.ref-scroll` 的渲染方是 `ui/generate-recommend.js`（**生成页第 4 步**的参考资料选择器，DOM 在 `#tab-generate` 里），只因前缀被判给 `reference`；③ `.topic-detail-problem-title` 也被 `ui/master.js` 用（母版库，07 单未开工）。票尾原句"这一族在别的页面上没有副作用"**只对描边口径成立** | ✅ 本票新增「账」第 2 条**逐条点名这三处**（改动是**统一**的：所有弹层 ✕ 同步小 4px、生成页第 4 步的选择器跟五页同一套档位），并写明**哪些侧没有对照图、留给 08 收尾的浅色巡检** |
| Spec-a1 | **合成红证没给新摘的五条腿补注入行**（05 给 `settings` 补过"摘尺 ≠ 腿跟着走"；本单一次摘五页却只证绿、没证"判得红"） | ✅ 守卫的注入清单**补五行**（library / reference / pdf / md / topic，各取一条真实规则头当锚点）；守卫 15/15 复跑绿 |
| Spec-a2 | 「模块的身份缺失」**未落地**：器件缺身份字段时 `fx/module.js` 零渲染，全站没有这条 ⚠ 徽章 | ✅ 如实记账（见验收那一条与「账」第 4 条）：四类里三类真有那套表达；这一类**没有**，本单**不造新徽章**（要动 JS，超出契约） |
| Spec-a3 | 契约条写"五个页签"，而 `probe-03-contract.py` 的顺序/类名计数**只有检测页一节**（spec 早写"扩成每页一节"，一直没扩） | ⚖ 记账（「账」第 6 条）：这是**探针的历史口径**（01 单立的），本单没扩；五页的 id 集合/顺序/文案实际是**整文件**比对的（第 1/4 节覆盖全站） |
| Spec-b1 | README 进度表出现**两行 07**（我插入新行时没删旧行） | ✅ 合并成一行 |
| Spec-b2 | 另立两支 spec 未点名的量具（死类普查 / 弹层截图） | ⚖ 保留并记账（「账」第 5 条）：都是本轮的取证需要，且都不进产品面 |
| Spec-c2 | `.topic-year` 按"② 可点控件"留框，而它是纯 `<span>`（不是可点控件） | ✅ 理由改准确：**按"标签胶囊一族"的控件形状保留**（同 04 单 `.code-kbd` 键帽先例），票面与脚本同步 |
| Spec-c3 / Std-b3 | 「统计条本来就是同一条规则」**不实**：`.lib-dangling-count` 是独立规则（无 `cursor` / 无 `.on` 态） | ✅ 两处都改：脚本把 `.lib-dangling-count` **并入同一套表达**（补 `--fs-note` + 注释写明"它不可点"——`ui/library.js` 那句「点击详情确认」指的是点行进详情）；票面措辞改成"哪两段本来就是一条规则、哪一段是独立规则" |
| Spec-c4 | 层级别只列字号档位，**没证明"不靠逐字读"**；`.md-row-file` 11 → 13 使 md 列表两行并平（与 spec 拍板"11 → `--fs-tag`"也不符） | ✅ `.md-row-file` **改回 12**（`--fs-tag`）——主行 14 / 次行 12 分得开；「三级」那张表也补了"每一级的落点 + 差几档" |
| Std-a2 | **spec 拍板记录没回写**：三处按角色判与拍板"11 / 11.5 → tag、12 / 12.5 → note"方向相反 | ✅ **spec 已补口径更正**（`.lib-chip` / `.topic-meta` + `.topic-detail-count` / `.md-row-file` 三条逐条写清"为什么按角色判"） |
| Std-b1 | 「五页清单」在四支脚本/探针里各抄一份（`SCOPES` / `EXPECT_VALUES` / `PREFIXES`） | ⚖ 记账（「账」第 7 条）：那是**本单的切片清单**（不是口径），且四支脚本已执行完（03 账第 6 条）；真要提公共件，下一单起在 `scope_lib` 里加 `SCOPE_GROUPS` |
| Std-b2 | `.dangling-tag` 与 `.topic-warn` 现在逐字相同，靠注释手工同步、**没有机器判据** | ⚖ 记账（「账」第 8 条）：合并会动分区表归属（两个作用域），加一条新守卫又超出本单；如实写明风险 |
| Std-3（会骗人的地方） | `apply-06d` 的"已应用"分支是全轮**唯一的静默路径**（只比 60 字符片段、无复扫，锚点还带令牌值、隐含"必须先跑 06a"） | ⚖ 记账（「账」第 9 条）并写进脚本 docstring；`apply-06e`（本单新那一支）**不重复这个毛病**：两条都做"旧形态不在 + 新形态在"的双向复扫 |
| Std-4 | `probe-06-dead-classes.py` 的类名是在**含注释**的 `<style>` 全文里抓的（注释里提一句就算"有样式"），且恒退出 0 | ✅ **先剥注释再收类名**（重跑：仍然 36 个，说明那 36 个不是被注释掩盖的）；并在输出里写明"这是取证不是闸门" |
| Std-5 | `probe-06-shot-modal.mjs` 的弹层边框**只打印不断言**；7 处去框只有 `.mi-plat` 一处有机器证据 | ✅ 补两条断言（弹层外壳必须是 `1px`、`.mi-reason` 必须是 `0px`）；其余 4 处（`.lib-edit-old` / `.add-section` / `.ref-scroll` / `.md-preview-body` / `.topic-detail-problem`）**只有 06c 的一次性双向对账**——如实记账（「账」第 10 条） |

**账（留给后面的人）。**

1. **一次改五页靠的是"共用骨架"**：全局 `table` 基类（shell 作用域，01 单做的）、
   `.lib-table` / `.lib-toolbar` / `.lib-stats`、`.ref-files-*`（6 个 `ui/*.js` 共用）、
   `.module-info-*` / `.mi-*`（模块详情，三处渲染）、`.dangling-tag` / `.ref-dangling-tag`。
   **下一单（07 母版库 + 指南 + 版本记录）大概率也是这个形状**：先 `grep` 渲染方量清
   "谁被几处用"，再决定改哪儿。
2. **跨页副作用三处（逐条点名，照 04 账第 2 条的写法）**——这三处的**改动方向是统一的**
   （跟五页同一套档位），但**它们各自的页面没有新对照图**，留给 08 收尾的浅色全站巡检：
   · **`.ref-files-close`（全站弹层的 ✕）18 → 14**：`exit-guard` / `overlay` / `confirm` /
     `codeeditor` / `codeview` / `master` / `md` / `pdf` / `reference` / `topic` /
     `generate-pins` / `generate-recommend` / `full-update` / `materials-update` ——
     **每个弹层的关闭钮同步小 4px**（口径：行内图标随所附那一面；18 也是全站最后一处 18px，
     本单顺手摘掉了 `18` 这一档）。
   · **`.ref-pick-*` / `.ref-scroll`（生成页第 4 步的参考资料选择器）**：渲染方
     `ui/generate-recommend.js`、DOM 在 `#tab-generate`（`index.html:3772`），只因前缀被判给
     `reference` —— 本单改了它 4 处字号 + 4 处取值 + 1 处去框，**等于改了 03 单已验收的生成页**；
     `#ref-picker` 那一块现在与五页同一套档位。
   · **`.topic-detail-problem-title` / `.topic-detail-pages-title` 12 → 16**：`ui/master.js` 也用它
     （母版库详情弹窗）——**07 单会看到同一条规则已经升过档**。
3. **`.pdf-*` 与 `.lib-*` 两个前缀都不是"一页专属"**：`.pdf-box` / `.pdf-viewer` / `.pdf-zoom*`
   是**生成页的 PDF 上传预览**（本单复核：那一族没有裸字号 / 裸间距 / 整圈框，所以没动它们）；
   `.lib-table` 是五页共用的列表类名、`.lib-stats` 是库页与参考库共用的统计条。**要改判谓词的话
   两处一起看。**
4. **「模块的身份缺失」这一类没有徽章**（票面 L32 点的四类里的第四类）：器件缺 `kit` / 来源链接时
   `fx/module.js` **零渲染**（identity-fields/05 的口径：不标豁免、不摆空行）；`libStats` 也不计这个数。
   → 本单**没有**给它造新徽章（那要改渲染方 = JS，超出"一行 JS 不动"的契约）。
   四类里另外三类（PDF 损坏 / 疑似重复、参考缺失、赛题程序悬空）**确实共用同一套表达**。
5. **死类普查（新立的量具）**：`probe-06-dead-classes.py` 在五页相关类名里查出 36 个
   "渲染方在输出、CSS（**已剥注释**）里从未出现"的类名——逐个看过，**全是 JS 挂钩**：
   `lib-edit-*` / `lib-mod-*` / `ref-edit-*`（表单字段与按钮，形状由标签、`label` 与全局
   `button` 规则给）、`proofread-category`（select）、`pdf-detail-copy-msg`。
   **不需要补形状**。下一单可以拿它再扫一遍（`.warning` 那种"该补形状却没人给"的，
   就是被同一类扫描抓出来的）；**它是取证不是闸门**（恒退出 0，判"该补还是该删"的是人）。
6. **契约探针的"每页一节"一直没扩**（spec 早写着扩成每页一节）：`probe-03-contract.py` 的
   第 2/3 节只覆盖检测页的 id 顺序与十一个点名的类名计数；第 1 节（id 集合）与第 4 节
   （中文文案）是**整文件**口径，所以本单的五页契约是有效的。**要扩成每页一节是独立的一笔活**，
   留给 08 或后续单（本单没扩，如实记）。
7. **"五页清单"抄了四份**（`apply-06a` / `06c` 的 `SCOPES`、`06b` 的 `EXPECT_VALUES`、
   死类探针的 `PREFIXES`）：那是**本单的切片清单**（不是口径函数），且四支脚本已执行完、
   锚点已消费（03 账第 6 条不回头改写）。**真要提公共件，07 起在 `scope_lib` 里加
   `SCOPE_GROUPS`**（例如 `PAGE_GROUPS["materials-five"]` + `CALIBERS`），别在每支脚本里再抄。
8. **"同一套表达"目前靠注释手工同步**：`.dangling-tag, .ref-dangling-tag`（`reference` 作用域）
   与 `.topic-warn`（`topic` 作用域）的声明逐字相同，但**没有机器判据**盯着它们别漂移。
   合并成一条规则会动分区表归属（第一命中）与两条腿的射程，本单不做；
   **下一轮若要立判据**：加一条"这三个类名的 font-size / font-weight / color 取值必须相等"的
   结构守卫（照 `actionWeightProblems` 的形状写）。
9. **`apply-06d` 的"已应用"分支是全轮唯一的静默路径**：它只比一个 60 字符片段、没有改后复扫，
   锚点还带令牌值（踩 04 账第 11 条）、并隐含"必须先跑 06a"。**实做时它跑对了**
   （锚点那版因为 CRLF 判红过一次、当场停手），但下一单别照抄这个形状——
   `apply-06e`（本单最后那一支）就是正确写法：**旧形态不在 + 新形态在，双向复扫**。
10. **7 处去框里只有 2 处有可复跑的机器证据**（`.mi-plat` / `.mi-reason` 在弹层截图探针里断言为
    `0px`；弹层外壳断言为 `1px`）。其余 5 处（`.lib-edit-old` / `.add-section` / `.ref-scroll` /
    `.md-preview-body` / `.topic-detail-problem`）**只有 `apply-06c` 的一次性双向对账**——
    守卫明文不判描边（spec：那条靠每单的逐层清单 + 人眼看图）。**谁把框加回来，两条闸门都不会红**，
    这是本轮既定边界，如实记在这里。
11. **票面日期按 git 提交时间写**（`git log -1 --format=%ci`）。

## 备注

- 详情弹层里那些"点一行加载 / 重试 / 缓存"的三态是行为，只改呈现。
- 来源标签、身份字段这类**有结构守卫钉着**的东西（判据单源在 Python 侧）只改样式，
  不改任何词表或文案。
