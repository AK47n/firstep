# ui-density-sitewide —— 界面「呼吸感」全站推广轮

> 立项 2026-09-28。上一轮 `.scratch/ui-density/`（检测页样板，01–05 全 resolved，`1db62b01`）
> 已定稿并获用户认可（原话「我现在觉得不错」）。本轮把那套令牌与规矩推给**其余十二个页签**。
> 流程：`docs/agents/workflow.md` 的 clarify → spec → 工单 → 逐张实现。

## 一句话

检测页那一版不再是个孤岛：**全站一套字号角色表（20/16/14/13/12/22）+ 一屏一层完整描边**，
`FROZEN_FONT_SIZES` 从 13 条摘到 0 条（条目数就是进度尺）。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `spec.md` | 需求 spec（问题陈述 / 方案 / 决策 / 测试决策 / 范围外 / 拍板记录） |
| `issues/01-role-scale-and-guard.md` | 地基 A：字号角色表 + 守卫分区骨架 + 全局文本基类 |
| `issues/02-shared-components.md` | 地基 B：全局组件与外壳（按钮 / 徽章 / chip / 提示条 / 空态 / 弹层） |
| `issues/03-generate-page.md` | 生成页（做题主页面） |
| `issues/04-code-page.md` | 代码页 |
| `issues/05-settings-page.md` | 设置页（含环境中心 / 更新 / 交付 / 资料库更新） |
| `issues/06-material-and-library-pages.md` | 模块库 + 参考文件库 + PDF + Markdown + 赛题库 |
| `issues/07-master-guide-changelog.md` | 母版库 + 使用指南 + 版本更新记录 |
| `issues/08-closeout.md` | 收尾：冻结清单清零 + 全站读数 + 浅色巡检 |
| `probe-00-survey.py` | 家底普查（字号 / 间距取值分布 + 内联 style 口径） |
| `probe-01-scope-draft.py` | **分区读数与明细**（总账 / 某作用域的字号·间距·描边明细 / 内联取值）——分区表从守卫源码解析，单一出处 |
| `probe-02-shot.mjs` | 逐页截图（真浏览器 + 真后端夹具；`node probe-02-shot.mjs <tag> <dark\|light> [页签,页签]`） |
| `probe-02b-shot-generated.mjs` | **「已生成」态整页图**（03 单立）：真发一次生成（题面留空 = 零 LLM）再拍；`SHOT_AT="#card-revise,…"` 可按选择器补分段图 |
| `probe-02c-shot-code-open.mjs` | **「打开了一个工程」态整页图**（04 单立）：真生成一个最小工程 → 代码页自己导出的桥 `openCodeViewer(dir)` 载入树 → 点开一个 `.c` → 拍（含快捷键浮层那一张）。**前置不成立会 throw，不静默拍空页** |
| `probe-04-scope-calibers.py` | **三条口径一次算清**（04 单立，取代 `recon-04-code.py`）：规则数 / 裸 px 字号 / 裸令牌间距 / **整圈完整框**；`--scope X [--kind fonts\|spaces\|borders]` 出明细。口径全部 `from scope_lib import …`（与探针、守卫同源）；要看完整声明体用 `dump-03-rules.py` |
| `probe-04-measure-treepane.mjs` | 树面板标题行**装不装得下**的量具（04 单立）：按 rect 量 `.code-pane-title` 的行内溢出与每个按钮越界多少像素——"看着像被裁"不算证据 |
| `probe-red-shell.py` | 判据强度自证：往 shell 塞越界字号 → 守卫必须红 → 复原转绿 |
| `scope_lib.py` | **施工脚本与工具共用的作用域解析 + 口径**（单一出处；口径与 `probe-01` 逐项对齐）——04–07 单直接 import；`full_borders`（整圈完整框）也在这里 |
| `dump-03-rules.py` | 把某作用域的规则逐条打出来（选择器 + 完整声明体 + 行号）；`--grep` 看某族、`--out` 落盘 |
| `apply-01a/01b/01c-*.py` | 工单 01 的三支施工脚本（逐条显式锚点 + 断言，改完打印逐行摘要） |
| `apply-02a/02c/02d/02e-*.py` | 工单 02 的四支施工脚本 |
| `apply-03a-fonts.py` / `apply-03b-spaces.py` / `apply-03c-borders.py` / `apply-03d-title-roles.py` / `apply-03e-review-fixups.py` | 工单 03 的五支施工脚本（字号 / 间距 / 描边 / 小节标题档 / 评审整改）。**`apply-03c` 的 `FIX`+`KEEP` 两张表 + "改前改后行号集合对账"就是下一单的模板** |
| `apply-04a-fonts.py` / `apply-04b-spaces.py` / `apply-04c-borders.py` / `apply-04d-review-fixups.py` | 工单 04 的四支施工脚本（字号 + 两处派生 / 间距 / 描边 / 评审与自查整改）。**`apply-04a` 的 docstring 记着一条教训：锚点唯一 ≠ 编辑区间不打架**（它第一版写出过 `;m;`） |
| `probe-05c-shot-settings-content.mjs` | **设置页「有内容」态整页图**（05 单立）：调**产品自己的纯渲染函数**（`fx/env.js` / `fx/update.js` / `fx/materials-update.js` / `fx/full-update.js`）+ 夹具数据，**零网络**造出体检三档 / 更新结果块 / 下载进度；保存成功态也拍一张（`:not(.ok)` 的证据） |
| `apply-05a-fonts.py` / `apply-05b-spaces.py` / `apply-05c-borders.py` / `apply-05d-new-rules.py` / `apply-05e-review-fixups.py` | 工单 05 的五支施工脚本（字号 / 间距 / 描边 / **新增规则与口径** / 整改）。`apply-05c` 是 04c 的加严版：对账**连取值一起比**、认人按选择器片段、口径用 `scope_lib.full_borders`；`apply-05e` 是"05d 之后再纠正它"的那一支（分组带 / 不可逆按钮的 `danger` / 空告警块的 `:not(:empty)` / 死类 `.warning`） |
| `probe-00-{before,after-01..05}.txt` / `probe-01-scope-{draft,after-01..05}.txt` / `probe-03-contract-{01..05}.txt` | 读数落盘（**每轮改动后重跑**，不是结论是照片） |
| `probe-red-shell-{in,out}.txt` | 守卫判据强度的红/绿读数 |
| `baseline-*.txt` | 改前门禁基线（读数小工具落的盘） |
| `shots/` | 对照图（每单该页暗色整页 + 收尾浅色巡检；**只入库结论点名的那几张**，见 `.gitignore` 白名单） |
| `readings.py` | 读数落盘小工具（照 `.scratch/hwcheck-hygiene/readings.py` 复制：剥 ANSI、UTF-8、带命令/时间/退出码头） |

## 改前基线（2026-09-28 实测）

| 面 | 读数 |
|---|---|
| 全站裸 px 字号 | **387 处 / 13 种**（= `FROZEN_FONT_SIZES` 那 13 条）；其中 221 处在全局/组件规则里 |
| 完整描边（1px 全框） | **209 处** |
| 裸令牌间距值 | 351 处 |
| `--fs-*` 令牌引用 | 45 处（全部在检测页段） |
| 全量 pytest | **5656 passed + 11 skipped**（113s） |
| 前端门禁 | **1836 passed / 0 fail** |
| 浏览器门禁 | **61 passed / 0 fail**（上一轮 05 的读数，改动后再量） |

## 怎么复跑

```powershell
# 家底普查（改前 / 改后同一把尺子）
$env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density-sitewide\probe-00-survey.py --out 读数.txt

# 排版碎片化读数（上一轮那支，含 --rev 从 git 对象读改前那一版）
$env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-01-type-census.py --out 读数.txt

# 契约对账（基线钉死 bd478720，不依赖工作树干净）
$env:PYTHONIOENCODING='utf-8'; python .scratch\ui-density\probe-03-contract.py --out contract.txt

# 门禁（浏览器门禁**不要**与全量 pytest 并跑）
python .scratch\ui-density-sitewide\readings.py js -- node --test "tests/js/*.test.mjs"
python .scratch\ui-density-sitewide\readings.py browser -- node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
python .scratch\ui-density-sitewide\readings.py pytest -- python -m pytest -n auto -q
```

## 进度（每单做完就更新这里）

| 单 | 状态 | 一句话 | 读数变化 |
|---|---|---|---|
| 01 地基 A：角色表 + 守卫分区 + 全局文本基类 | **resolved**（`a73c22ce`） | 守卫从"只守检测页"变"每页一条腿 + 进度清单"；全局外壳与文本基类落地 | 裸字号 387 → 319；`--fs-*` 45 → 101；页面尺 13 → 12 |
| 02 地基 B：全局组件与外壳 | **resolved**（`854aeee6`） | 动作三级升到全局（危险 = 红描边淡红底）、空态安静、三段重复按钮收成单源 | 裸字号 319 → 288；`--fs-*` 101 → 130；页面尺 12 → 11；**取值尺 13 → 11**（摘掉 16 / 30） |
| 03 生成页 | **resolved**（2026-09-29） | 最大一单：110 处裸字号 + 106 处裸令牌间距清零、24 处内层整圈框换语言；02 移交的 `.btn-*` 另一半与 `.task-dialog-box` 落地；双轴评审又揪出**两处分区表漏判**与**三处语义回归** | 裸字号 288 → 175；`--fs-*` 130 → 245；页面尺 11 → **10**；取值尺 11 → 11 |
| 04 代码页 | **resolved**（2026-09-29） | `.code-*` 一族 66 处裸字号清零（+ 编辑器字号基准 `--code-font-size` 与 md 预览根字号改从台阶派生）、84 处取值（64 条声明）裸令牌间距清零、**5 处内层整圈框去框**（整圈完整框 24 → 19，19 条全在申报的例外里）；**另接 03 挪过来的 `.quick-open-*`**——它们早就是令牌形态，本单只把它们算进本页的账 | 裸字号 175 → **109**；`--fs-*` 245 → **314**；页面尺 10 → **9**；取值尺 11 → **10**（摘掉 `8`） |
| 05 设置页 | **resolved** | 10 处裸字号 / 9 条声明（10 处取值）裸令牌间距清零；卡内小节标题升到 `--fs-block` 并转正文色；**2 处内层整圈框去框** + **1 条新告警块**（整圈完整框 4 → 3 = 例外①）；**8 条新规则**（体检失败行重量 / 更新与进度结果块 / 失败告警块 / 死类 `.warning` 补实 / 分组带）+ **5 条分组标题元素** + 不可逆按钮补 `class="danger"` | 裸字号 109 → **99**；`--fs-*` 314 → **327**；页面尺 9 → **8** |
| 06 素材与库五页 | 待做 | 模块库 / 参考 / PDF / MD / 赛题库共用一套列表与弹层 | — |
| 07 母版 + 指南 + 版本记录 | 待做 | 顺带把 `16.5px` 这类"只剩一页在用"的取值清掉 | — |
| 08 收尾 | 待做 | 冻结清单清零 + JS 内联 7 处 + 浅色全站巡检 + 双轴评审收口 | — |

**当前读数（改到哪儿了，一目了然）**：全站裸字号 **99 处 / 10 种**（起点 387 / 13）；
页面尺 **8 条**（起点 13）；取值尺 **10 条**（起点 13）；`--fs-*` 引用 **327 处**（起点 45）。

> 05 单之后**仍然停在 12px 以下或等于令牌的裸值**都只剩未开工的页：`library` 32 / `master` 20 /
> `topic` 14 / `reference` 14 / `guide` 10 / `changelog` 6 / `md` 2 / `pdf` 1
> ——**已完工的六个作用域（`code` / `settings` / `generate` / `hwcheck` / `components` / `shell`）全是 0/0**。
> （按页数一遍：`python .scratch\ui-density-sitewide\probe-04-scope-calibers.py`。）

## 下一单怎么开工（五步套路，01/02/03 都是这么走的）

1. **取证**：`python probe-01-scope-draft.py --show <作用域> --kind fonts|spaces|borders` 列清单；
   `--kind inline` 看标记上的内联取值；要看**完整声明体**用 `dump-03-rules.py --scope <作用域> --grep <族>`。
   **开工前先核一眼归属**：拿 `static/js/**` 的实际渲染处对一遍（03 单又抓到两族判错，见下面的坑 4）。
2. **施工**：写一支 `apply-NNa-*.py`——**逐条显式锚点 + 断言"命中恰好一次"**，
   行号按**规则块区间**定位（声明块常跨行），改完打印逐行摘要；不确定的先 `--dry-run`。
   ⚠ **替换串也要按文件实际换行**（`\r?\n`）——02 单就是替换侧写了 `\n`，把 8 行裸 LF
   写进了 CRLF 的 `index.html`（`fix-crlf.py` 可归一，但**别制造**）。
   ✅ **公共件从 `scope_lib.py` import**（`load_scopes` / `scope_of` / `rules_of` / `bare_fonts` /
   `bare_token_spaces` / `read_page` / `write_page`），**别再各抄一份**（03 单评审的账）。
   ✅ **描边单照 `apply-03c-borders.py` 写**：`FIX` + `KEEP` 两张表 + "改前集合 == FIX∪KEEP、
   改后集合 == KEEP∪(改成透明框的)"双向对账——这是"改完了没有"的机器证明。
   ⚠ **按行号挑规则会挑错人**：同一行常落两条规则（`.ov-chips`/`.ov-chip`、`.task-card-highlight`/
   `.task-meta`、`.sugg-discuss-note`/`.task-dialog-box`）。**扫每一条规则体、锚点在谁身上命中就算谁的**
   （键取 `(行号, 取值)` 或 `(行号, 选择器片段)`）。
3. **读数**：重跑 `probe-00` / `probe-01` / `probe-03`（`probe-03` 的 `--out` 落在它自己目录，
   跑完 `Move-Item` 过来），文件按单编号（`*-after-NN.txt`）。
   ⚠ **整改过一轮就要再跑一遍**：03 单评审整改动了 8 处 CSS 之后，`generate` 的裸令牌间距
   从 0 变回 1（一条规则随面板改了归属）——只跑一次读数就漏过去了。
4. **门禁与截图**：前端门禁 + 浏览器门禁（**单独跑，不与全量 pytest 并行**）+
   该页暗色整页图（`probe-02-shot.mjs <tag> dark <页签>`；要"有内容"那一态用
   `probe-02b-shot-generated.mjs`）；读数走 `readings.py`。
   ⚠ **入库的图要真的过了 `.gitignore` 白名单**——`git check-ignore -v <图>` 核一眼
   （03 单评审抓到"已生成整页图"其实还被 `shots/*` 吞着）。
5. **收口**：`code-review` 双轴 → 逐条整改 → 票尾写「结论（形状 / 读数 / 逐层清单 / 门禁 /
   评审处置 / 账）」→ `Status: resolved` → 提交（中文提交信息，post-commit 自动补 CHANGELOG）。

**摘进度尺**：一页做完就把它从守卫的 `SITEWIDE_BACKLOG` 里摘掉；某个字号取值**全站彻底消失**
才从 `FROZEN_FONT_SIZES` 摘（摘了就等于立"不许再回来"的闸）。

## 判据边界（别误读）

- **门禁只证明"没改坏"**；"好不好看"只有**用户看对照图**作数。
- **两条进度尺**：页面尺（`SITEWIDE_BACKLOG`，前段单调下降）与取值尺（`FROZEN_FONT_SIZES`，
  某个取值在全站彻底消失才摘得掉，故主要在收尾单清零）。
- **读数不是结论，是那一刻的照片**：每轮改动后都要重跑（上一轮两条假账都源于"读数过期"）。

## 三条纪律（上一轮踩过的坑）

1. 读数每轮重跑。
2. 浏览器门禁**不**与全量 pytest 并跑；同一个 spec 文件里**别混用**整页 `goto` 与路由桩
   （会让文件级抛 `unhandledRejection`，而每条用例自己全绿）。
3. `ui/` 四件有形状钉（入口只有接线 + 两个导出，按行多重集对账）——
   纯呈现优先用 CSS（`:target` / `:has()` / 原生锚），别往那份台账里加页。

## 本轮又踩到的三条（01/02 的账，下一单直接用）

1. **施工脚本的"替换侧"也要按文件实际换行走**（02：8 行裸 LF 混进 CRLF 文件）。
2. **守卫按"原始选择器"判归属会漏水**（02 评审抓到）：这段样式块大量规则写成「注释 + 选择器」，
   注释里提到别的页的类名 → 规则被判到那一页、腿静默放行。
   现在 `scopeOf` 与 Python 探针都**先剥注释再判**；改分区谓词时照旧按**渲染方**写。
3. **"标记里有、样式里没有"的死类没有任何守卫会报**（02：`class="ghost"` 两处）——
   只有人眼看得见"这按钮怎么这么重"。遇到就补实或删掉，并在票尾记一笔。

## 03 单又添的五条（下一单直接用）

4. **类名前缀不是归属判据。** 03 单评审一次揪出两族判错：`.topic-preread*` 是**生成页第 2 步**那块
   预读面板（前缀像赛题库页），`.quick-open-*` 是**代码页**的 Ctrl+P 浮层（前缀像"快速操作"）。
   两族都因为前缀被别的页"代管"，于是**那一页的腿一直是绿的**（假绿）。
   → 新页面单开工前，拿 `static/js/**` 的渲染处逐个对一遍谓词；
   **反面同样要防**：改完发现某族其实不归自己，**如实记账别回头撤**（撤了下一单还得再改一遍）。
5. **"改框"会顺手留下一批死声明，机器不报。** 03 单把 `.rc-summary` 去框之后，
   `.rc-summary.ok { border-color: … }` 成了永不生效的死声明（只有人眼/评审核得到）。
   → 去框之后**扫一遍同一个族里所有 `border-*-color` 声明**，逐个问"它还有框可染吗"；
   语义告警块（"必须显眼"那一类）**本来就该留框**，别一刀切。
6. **换掉整圈框 → 悬停反馈会静默失效**：`.score-panel:hover { border-color: var(--border-strong) }`
   与新的左条同色 ⇒ 悬停前后一模一样。→ 改了框就要**逐个核一遍 `:hover` 那几条**，
   看不见变化就换成"左条转 accent"这类别的信号。
7. **"票面的数"要按脚本复算再写进注释**：03 票面写 111 处裸字号 / 74 处描边，脚本复算是
   110 / 53（另外两个口径各自不同）——差在"一处随归属改判归还了设置页"和
   "探针把单边分隔线与 `border: 0` 也算进描边那一栏"。**注释里写错数，下一个读的人就会按错的尺子量。**
8. **截图入库要过白名单**：`shots/*` 是 ignore-all + 白名单，**新图不加白名单就等于没入库**
   （`git status` 里看不见，评审一 `git check-ignore` 就露）。收口前核一眼。

## 04 单又添的五条（下一单直接用）

9. **"锚点唯一" ≠ "编辑区间不打架"。** `apply-04a` 把 `.code-err-line::after` 的 `8px → .62em`
   列了两次（一次在字号表里、一次在派生清单里），两条编辑**各自**"锚点恰好命中一次"，
   却在同一个字节区间上互相啃，写出 `font-size: .62em;m;` —— **CSS 非法声明，浏览器丢弃，
   两道门禁全绿**（双轴评审才抓到）。→ 编辑表建好后加一条**区间不重叠**断言
   （`apply-04a` 的 `main()` ③b 就是写法）；**同一处只许列一次**（派生清单只放 calc 里的、
   探针看不见的那两条）。
10. **探针口径 ≠ 施工口径，票面的数要按脚本复算。** 票面写的"63 处描边"是探针那一栏
    （含单边分隔线与 `border: 0`），真正要处置的**整圈完整框**是 **24** 处 —— 差一倍以上。
    04 单把这条口径提到 `scope_lib.full_borders`，并立了 `probe-04-scope-calibers.py`
    **同时报三条口径**（裸字号 / 裸令牌间距 / 整圈完整框）。
11. **合成红证的锚点别带令牌值。** 04 单整改把 `.code-pane-title` 的 `--fs-block` 换成 `--fs-note`，
    守卫里那条带令牌的锚点**当场判红**（"这条自检会静默空转"——它做得对），但下次换令牌还会误报。
    → 锚点取**规则头**（`.code-pane-title { font-weight: 650;`），注入一条新的 `font-size`。
12. **"人眼看图"要配一把量具，并且把"看着像"与"量出来"分开写。** 树面板标题行看着被挤成两行、
    第三个按钮看着被裁——量出来的事实是：**两样改前就有**（折叠 11px 时也折、按钮越界 32px），
    本单各 +4px / +9px。→ `probe-04-measure-treepane.mjs` 按 rect 量；票尾别把既有的拥挤
    记成自己引入的，也别把自己的 +9px 说成"没有影响"。
13. **共享件改了要跨页记账。** `.diff-hunk`（代码页 + 生成页的"本轮变化"/参数 diff 都用）与
    `.code-md-preview`（代码页 + md 资料预览弹窗）是**跨页共享件**：本单按"第一命名页"归
    `code` 就地改，**生成页 / md 页那一侧没有对照图**（04 票尾的「账」写明了这一笔，
    08 收尾的浅色全站巡检顺手看一眼）。

## 05 单又添的十一条（下一单直接用）

14. **`git checkout <commit> -- <path>` 会把旧版写进暂存区。** 05 单做"全量重放"验证时踩到：
    `git checkout HEAD -- index.html` 之后又 `Copy-Item` 还原工作树，**暂存区里留的还是旧版**
    —— `git diff` 当场把 04 整单的改动重新算成本单的（39 行变 313 行）。
    → 重放/换版本之后补一句 `git reset -q -- <path>`；**看 diff 之前先确认它是不是你要比的那一版**。
15. **插入块也要按文件实际换行换算（04 账第 9 条的姊妹条）。** `apply-05d` 的三引号块里是裸 LF，
    直接拼进 CRLF 的文件就是 16 行裸 LF（`fix-crlf.py` 当场报出来）。**匹配侧、替换侧、插入侧**
    三处都要走 `replace("\n", CRLF)`；重放验证里也要把"重放后 0 裸 LF"当成一条判据。
16. **改样式之前先读渲染方怎么写那个类。** `#settings-msg` 的初始类就是 `error`，而
    `ui/settings.js` 保存成功那条路径只 `classList.add("ok")`、**不摘 `error`** —— 不做
    `:not(.ok)` 就会把"已保存，立即生效。"装进红框里（门禁全绿，只有人眼/评审看得见）。
    同理：`.update-result` 这个类**早就渲染出来了**，只是从来没有样式——**先 grep 渲染方**，
    再决定"加类名"还是"给已有类名写规则"（后者不用碰 JS）。
17. **票面说"大工程"时先量。** 05 票面写"框套框主要在 DOM 组合层"，实测 `#tab-settings` 的
    14 张卡**全是同级**（DOM 里没有卡中卡、JS 也不渲染 `class="card"`），真正的内层整圈框只有
    **2 处**。把这句判断纠正过来、写进票尾，比顺着票面的暗示去大改 DOM 强。
18. **要"有内容"态而它必须联网时：调产品自己的纯渲染函数 + 夹具。** 设置页的体检 / 更新 /
    下载进度都要点按钮 + 打网络；`probe-05c-shot-settings-content.mjs` 直接
    `import("/js/fx/…")` 调导出函数喂夹具数据（渲染路径是产品的、数据是夹具、**零网络**），
    并把"这一段不是产品渲染路径"（`ui/settings.js` 内联产出的 wf 标记）如实写在文件头。
    **别为了拍图去点真按钮**（那会真的打网络）。

19. **默认态（要素为空时）也要拍 / 也要看。** 05 单给 `#tab-settings .error` 写了告警块，
    而 `#settings-msg` 的初始类就是 `error`、内容为空 —— 页面一打开就挂着一条 1358×18 的
    **空红框**（评审实测；本单入库的整页图底下那条就是它）。`probe-05c` 只造了"失败态"与
    "成功态"，**空态漏在射程外**。→ 新规则先问三句：**空的时候长什么样？初始类是什么？
    另一态（成功/禁用/折叠）会不会带上同一个类？**（`probe-05c` 现在两态都拍。）
20. **改属性值会被"中文文案零删除"误报成删文案。** 05 单给「清空本地记录」那个按钮补了
    `class="danger"`（文案一个字没动），`probe-03-contract.py` 当场报"删了一行中文"。
    → 口径补一条：diff 前把 `class="…"` **整条属性**去掉（**不是**把取值抹空——新增属性时
    取值抹空仍然对不上，本单第一版就踩了）。这与 03 账第 8 条（内联 `style=`）同类：
    **判据要比文字，不比属性**；类名的变动由第 3 节"被点名的类名出现次数"看着。
21. **"分组靠大间距 + 分组标题"= 插标题元素，不是把卡间距调大。** 02 单 `.hwcheck-band`
    就是先例（"只插入标题元素"，DOM 顺序与 id 一个不动）——05 单照它给 14 张卡插了 5 条
    `.settings-band`。**照抄先例时要挑掉不适用的那几条**：`.hwcheck-band:first-child
    { margin-top: 0 }` 在设置页永远是死规则（带前面还有页首工具栏），没抄。
22. **同一块面板里的死类要顺手补实。** `fx/materials-update.js` 与 `fx/full-update.js` 一直在
    渲染 `.warning`（弱网重试 / 整批将被移除），全站却**从来没有过** `.warning` 规则（坑 3）。
    → 补一条最小样式（警示色文字），并在票尾说清 `.full-confirm` 那种"结构壳"不算死类
    （弹层外壳已经给了形状）。
23. **页作用域 vs 全局类：** `.error` 是全局类（`shell` 作用域），设置页要给它形状就必须写成
    `#tab-settings .error…`（页作用域）——**别直接改全局 `.error`**（别处是行内红字）。
    新规则落到哪个作用域，先拿守卫的 `PAGE_SCOPES` 对一眼（本单的 `#tab-settings …` 落在
    `settings` ✅）。
24. **重放验证要连"中间态"一起说清。** 05 单的最终产物是 `apply-05d`（原形态）+ `apply-05e`
    （纠正）两步合出来的：`git checkout HEAD -- index.html` 之后按 a→e 顺序重跑，产物与工作树
    **逐字节相同**（CRLF 5089 行、裸 LF 0）。**别只重放一半**——04 单是"a→c 之后只差 d 一处"，
    05 单是"a→e 全链一致"，两种说清都行，含糊不行。

