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
| `probe-red-shell.py` | 判据强度自证：往 shell 塞越界字号 → 守卫必须红 → 复原转绿 |
| `apply-01a-fonts.py` / `apply-01b-spaces.py` / `apply-01c-borders.py` | 工单 01 的三支施工脚本（逐条显式锚点 + 断言，改完打印逐行摘要） |
| `probe-00-{before,after-01}.txt` / `probe-01-scope-{draft,after-01}.txt` | 读数落盘（**每轮改动后重跑**，不是结论是照片） |
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
| 03 生成页 | 待做 | 最大一单：111 处裸字号 + 74 处描边；另接 02 移交的 `.btn-*` 另一半与 `.task-dialog-box` | — |
| 04 代码页 | 待做 | `.code-*` 一族 66 处字号 / 63 处描边；`--code-font-size` 改从台阶派生 | — |
| 05 设置页 | 待做 | DOM 最厚（14 卡 28 行），框套框主要在 DOM 组合层 | — |
| 06 素材与库五页 | 待做 | 模块库 / 参考 / PDF / MD / 赛题库共用一套列表与弹层 | — |
| 07 母版 + 指南 + 版本记录 | 待做 | 顺带把 `16.5px` 这类"只剩一页在用"的取值清掉 | — |
| 08 收尾 | 待做 | 冻结清单清零 + JS 内联 7 处 + 浅色全站巡检 + 双轴评审收口 | — |

**当前读数（改到哪儿了，一目了然）**：全站裸字号 **288 处 / 11 种**（起点 387 / 13）；
页面尺 **11 条**（起点 13）；取值尺 **11 条**（起点 13）；`--fs-*` 引用 **130 处**（起点 45）。

## 下一单怎么开工（五步套路，01/02 都是这么走的）

1. **取证**：`python probe-01-scope-draft.py --show <作用域> --kind fonts|spaces|borders` 列清单；
   `--kind inline` 看标记上的内联取值。
2. **施工**：写一支 `apply-NNa-*.py`——**逐条显式锚点 + 断言"命中恰好一次"**，
   行号按**规则块区间**定位（声明块常跨行），改完打印逐行摘要；不确定的先 `--dry-run`。
   ⚠ **替换串也要按文件实际换行**（`\r?\n`）——02 单就是替换侧写了 `\n`，把 8 行裸 LF
   写进了 CRLF 的 `index.html`（`fix-crlf.py` 可归一，但**别制造**）。
3. **读数**：重跑 `probe-00` / `probe-01` / `probe-03`（`probe-03` 的 `--out` 落在它自己目录，
   跑完 `Move-Item` 过来），文件按单编号（`*-after-NN.txt`）。
4. **门禁与截图**：前端门禁 + 浏览器门禁（**单独跑，不与全量 pytest 并行**）+
   该页暗色整页图（`probe-02-shot.mjs <tag> dark <页签>`）；读数走 `readings.py`。
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

