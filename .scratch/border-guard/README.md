# border-guard —— 描边那条线的机器守卫（把「哪些框算例外」变成可对账的数据）

> 立项 2026-09-29。上游：`.scratch/ui-density-sitewide/`（全站密度轮，01–12 全 resolved，
> 已随 v1.4.0 上线）——那一轮把**字号**那条线做干净了（裸 px 字号 0），
> 但**描边**那条只有「逐条申报的例外清单 + 人眼看图」（08 账第 1 条）。
> 流程照 `docs/agents/workflow.md`：clarify → spec → 工单 → 逐单实现 + 双轴 code-review → resolved。

## 一句话

`index.html` 样式块里那 **115 处整圈完整框**、以及 `static/js/**` 里那 **10 处内联整圈框**，
从此都是**登记在册的数据**：盘上 ↔ 登记簿**双向对账**，多一条、少一条、改名、
透明占位偷偷变成真框——**当场判红**。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `spec.md` | 需求 spec（问题陈述 / 方案 / 实现决策 / 测试决策 / 范围外 / 拍板记录 / 被否掉的三种方案） |
| `issues/01-register-and-leg6.md` | 样式块面：登记簿（115 条）+ 类别表（10 类）+ 守卫**腿⑥** + 合成红证 |
| `issues/02-render-side-leg7.md` | 渲染方面：内联框登记（10 条）+ 守卫**腿⑦** + 跨语言镜像第 5 条 |
| `issues/03-closeout.md` | 收口：读数落盘 + 三套门禁 + 文档回改 + 双轴评审整改 |
| `probe-00-borders.py` | 施工前侦察：115 处整圈完整框逐条 dump（按作用域分组） |
| `probe-02-caliber-styleblock.py` | **解析口径对账**：守卫的整文件解析 vs `scope_lib` 的 `<style>` 块解析 |
| `probe-03-register.py` | **样式块面读数**：登记簿 ↔ 盘上双向差 + 每类条数 + 口径分列 + 悬停态脚注 |
| `probe-04-js-register.py` | **渲染方面读数**：双向差 + 每类条数 + 逐条清单 + 单边分隔线脚注 + **覆盖审计** |
| `probe-05-mirror-red.py` | 反证：跨语言镜像守卫**判不判得红**（5 处注入） |
| `probe-06-generator-check-red.py` | 反证：两支生成器的 `--check` **判不判得红**（4 处注入） |
| `probe-07-guard-scale.py` | 收口体检：守卫的规模与各表条数（**按脚本复算**，票面/README 里的数从这来） |
| `probe_lib.py` | 反证探针的**公共骨架**：`inject_and_check()`（注入 → 跑判据 → **`finally` 复原**）。03 单评审点过"两支探针各抄 30 行 + 复原不在 finally" |
| `probe-08-upstream-compare.py` | 收口对拍：本轮读的**上一轮那三支探针**与上一轮落盘基线比（00/01 比 **sha256**；04 上一轮没落盘，**只能比数**） |
| `generate-01-register.py` / `generate-02-js-register.py` | **一次性**施工脚本（生成那两张表）。带 `--check` 可复核"守卫那张表还是不是生成时那张" |
| `register-block.js.txt` / `register-js-block.js.txt` | 上面两支脚本的**生成物快照**（已消费） |
| `after-01-*.txt` / `after-02-*.txt` / `after-03-*.txt` | 门禁与上一轮探针的读数（**每轮改动后重跑**，不是结论是照片） |

## 这一轮立起来的两条腿

守卫是 `tests/js/css-tokens.test.mjs`（**不另起文件**——sitewide 轮定过这条）。
它现在有**七条腿**，这一轮加的是最后两条：

| 腿 | 管什么 | 判据 |
|---|---|---|
| **⑥** | `index.html` 样式块 | `BORDER_REGISTER`（115 条）↔ 盘上**双向**对账 + `placeholder` ⟺ 含 `transparent` + 类别表形状 |
| **⑦** | `static/js/**` 内联框 | `JS_BORDER_REGISTER`（10 条，认人键 = 文件 + 行内锚点）↔ 盘上**双向**对账 |

**不判"这条框该不该留"**（机器判不了——那正是 08 账第 1 条说的判据问题）。
改判**"这条框是不是被登记过的"**：新增必须显式登记并挑一个类别，去掉必须摘掉登记项。
**产品面零改动**——这一轮只立数据与判据，不动一格观感。

## 当前读数（2026-09-29 收口）

| 面 | 读数 | 出处 |
|---|---|---|
| `index.html` 整圈完整框 | **115** 条（= 94 可见框 + 21 非框：12 placeholder + 9 nonbox） | `probe-03-register.txt` |
| 样式块面双向差 | **0 / 0** | 同上 |
| 渲染方内联整圈框 | **10** 条，双向差 **0 / 0 / 0** | `probe-04-js-register.txt` |
| 渲染方覆盖审计 | 含 `border…:` 的行 15 = 入册 10 + 撤框 0 + 单边 5，**0 处没归类** | 同上 |
| 非框里状态态会上色的 | **10 / 21**（全是 placeholder；nonbox 9 条 0 条） | `probe-03-register.txt` |
| 上一轮那三支探针 | 14 个作用域 0/0、页面尺 0 条、`fullBoxes` 115（**不退化**） | `after-03-probe-00.txt` / `-01.txt` / `-04.txt`（正文另落 `-body.txt`） |

> **"不退化"这条是怎么判的（口径说清）**：`probe-00` / `probe-01` 有上一轮的落盘基线可比
> （`ui-density-sitewide/probe-00-after-09.txt` / `probe-01-scope-after-09.txt`）——
> `probe-08-upstream-compare.py` 实测 **sha256 逐字节相同**；
> **`probe-04` 在上一轮没有落盘读数**（它当时是"跑一次看表"），所以只能**比数**
> （十四页 0/0、`fullBoxes` 115）——**别把它读成"逐字相同"**（03 单评审点过这条）。
| 前端门禁 | **1842 / 0**（起点 1840；+2 = 腿⑥腿⑦ 两条用例） | `after-03-js.txt` |
| 浏览器门禁 | **61 / 0**（201s，**单独跑**） | `after-03-browser.txt` |
| 全量 pytest | **5664 passed + 11 skipped**（起点 5659；+5 = 跨语言镜像守卫 5 条 —— pytest 面**看不见** `tests/js/**`，所以腿⑥腿⑦ 的用例只体现在前端门禁那一行） | `after-03-pytest.txt` |

## 怎么复跑

**都在仓库根跑。** 探针自己 `reconfigure` stdout，所以本目录的探针不必设环境变量；
但**上一轮那三支**（`ui-density-sitewide/probe-00/01/04`）没有 reconfigure，
在本机 GBK 控制台下必须带 `PYTHONIOENCODING=utf-8`，否则读数里带数字的行会乱码。

```powershell
# 本目录的探针（读 + 写本目录的读数文件）
python .scratch\border-guard\probe-03-register.py      # 样式块面：双向差 / 每类条数 / 口径分列
python .scratch\border-guard\probe-04-js-register.py   # 渲染方面：双向差 / 逐条 / 覆盖审计
python .scratch\border-guard\probe-07-guard-scale.py   # 守卫规模与各表条数（票面/文档里的数从这来）
python .scratch\border-guard\probe-05-mirror-red.py    # 反证：镜像守卫判得红吗（会就地改守卫，try/finally 复原）
python .scratch\border-guard\probe-06-generator-check-red.py   # 反证：两支生成器 --check 判得红吗（同上）
python .scratch\border-guard\generate-01-register.py --check   # 守卫那张表还是生成时那张吗（只读）
python .scratch\border-guard\generate-02-js-register.py --check

# 上一轮那三支（不退化读数）——**必须带 PYTHONIOENCODING**，且 --out 要**绝对路径**
#（那两支探针把 --out 按自己的目录解析，相对路径会落错地方）
$env:PYTHONIOENCODING='utf-8'
$d = "$PWD\.scratch\border-guard"
python .scratch\ui-density-sitewide\probe-00-survey.py     --out "$d\re-probe-00-body.txt"
python .scratch\ui-density-sitewide\probe-01-scope-draft.py --out "$d\re-probe-01-body.txt"
python .scratch\ui-density-sitewide\probe-04-scope-calibers.py

# 三套门禁（**浏览器门禁不与全量 pytest 并行**）
# ⚠ `readings.py` 用**第一个参数当读数文件名**，所以名字自己起；`after-03-*` 是收口那一轮起的名字
python .scratch\ui-density-sitewide\readings.py re-js      --out-dir .scratch\border-guard -- node --test "tests/js/*.test.mjs"
python .scratch\ui-density-sitewide\readings.py re-browser --out-dir .scratch\border-guard -- node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
python .scratch\ui-density-sitewide\readings.py re-pytest  --out-dir .scratch\border-guard -- python -m pytest -n auto -q
```

⚠ **跑门禁用系统 `python`，别用 `.venv\Scripts\python.exe`**——那是应用运行时，里面**没有 pytest**
（01 单踩过：拿它跑 pytest 会得到一份"退出码 1 但没有失败用例"的假读数）。

⚠ **`probe-05` / `probe-06` 会就地改 `tests/js/css-tokens.test.mjs`**（注入 → 跑判据 → 复原，
复原在 `try/finally` 里）。它们跑完守卫文件的 **mtime 会晚于读数**，但**内容与 HEAD 同哈希**——
"读数必须晚于最后一次改产品面"这条纪律看的是**内容**，不是 mtime（03 单评审点过这一条）。

## 判断边界（别误读）

1. **「整圈完整框 115」是声明数口径**（样式规则里的完整 `border:` 声明），
   **不是**"渲染出来的框元素数"——两把尺别混着读（`local-environment` 记过这条）。
2. **那 115 条不是漏网**：每一条都在登记簿里、都带一个类别；21 条压根不是"框"（透明占位 / 圆点 / 字形 / 滚动条）。
3. **悬停 / 选中态才出现的框不在射程内**：`border-color` 是单声明、不是"完整框"。
   读数量到非框 21 条里 10 条有状态上色——那是「一屏一层」的**合法逃逸**，不是漏网。
4. **单边分隔线（`border-top` / `border-bottom`）不在射程内**：那是"一条线"，不是"一圈框"。
5. **渲染方的锚点不是行号**：锚点是该行的一段可认片段（行号会随插行漂）。
   ⚠ 选锚点的规矩：**锚点所在的那段文本必须与这条框声明本身有关**——
   `max-width:640px` 那种锚点会让纯布局编辑误红（02 单双轴评审实测）。
6. **登记簿的"类别"是人判后写进数据的**，守卫**不重推类别**（"这是语义告示还是内层框"机器判不了）；
   守卫只保证它被显式判过一次、且不会静默变化。

## 留给下一轮

- `--accent` 小字在浅色下 **3.39:1**（低于 AA）与"去框留淡底"×1.06 —— 调色板级决定，
  改它要过颜色守卫（`backlog.md` §27 另一条账，本轮没碰）。
- `.pdf-*` / `.lib-*` 两处跨页前缀的**谓词归属**按第一命名页保留现状（sitewide 08 账第 8 条）——
  要动的唯一理由是"哪条腿看着它"，属另一轮的口径讨论。
- 渲染方的已知留白：**跨行拼出来的**内联声明（`'…' + 'border:…'`）抓不到
  （与守卫第五条腿的已知留白同类）。探针的「覆盖审计」盯着它有没有被撞上。
- **`.code-view::-webkit-scrollbar-thumb` 的类别是"不变量优先"的结果**（01 票尾账第 3 条）：
  它既像 `nonbox`（滚动条）又含 `transparent`（不变量管的 `placeholder`）。
  本轮选了不变量——**要改就改那条不变量本身**（`placeholder` ⟺ 含 `transparent`），不是改这一条登记项。
- **`register-block.js.txt` / `register-js-block.js.txt` 与 `apply-01-register.py` 里那几段文本
  是双轴评审整改前的快照**，与守卫**不再逐字相同**（各文件头都显著标注了）。
  复核走 `probe-03` / `probe-04`（从守卫读）或 `generate-0{1,2} --check`（复核生成关系）。
- 「基线」没有独立落点：本轮的读数锚是 **`08e5d524`**（`main` 上开工那一点），
  与上一轮的 `bd478720` 不是同一个点——要比"字号线"用上一轮的基线，要比"描边线"用这个。
