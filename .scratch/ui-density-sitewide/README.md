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
| `probe-00-survey.py` | 家底普查（按页面作用域分组：规则数 / 裸字号 / 裸令牌间距 / 描边） |
| `probe-00-before.txt` | 上面那支探针的改前读数 |
| `baseline-pytest.txt` / `baseline-js.txt` | 改前门禁基线（读数小工具落的盘） |
| `shots/` | 对照图（每单该页暗色整页 + 收尾浅色巡检） |
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
