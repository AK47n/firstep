# 01 — 口径补齐：七层底 + 叠放几何 + 代码页高亮色令牌（产品面观感零变化）

**要做什么：** 让「代码页上文字会压到的底」在判据里**是盘上真实的那七层**，并且**按真渲染算**——
高亮层压在字上时字形本身也被染色（实测见 `probe-02`）。做完这一单：

- 探针（`probe_lib`）与守卫腿⑧（`tests/js/css-tokens.test.mjs`）两侧都按「层 + 几何 + alpha」算，
  镜像守卫钉住；`--tok-*` 那族从五层扩到七层（+ `.38` 当前命中、+ `--danger-dim` 错误行），
  另立一条括号彩虹族（只与 `--code-text` 配对）。
- 代码页的高亮填充改走**自己的令牌** `--code-hl-rgb`（两主题都先取**现值** = 现在的 accent-rgb）。
- **本单结束时观感逐像素不变**：层 alpha 不动、令牌值不动，样例文件的截图像素逐字节相同
  （这是"口径改造"与"改观感"分开做的那条纪律）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09-30；结论见文末）

- [x] **`probe_lib.py` 的层表换成三元组**：`CODE_LAYERS = [(名字, alpha, 几何), …]`，七条
      （`--code-bg` / `+hl.当前行 .07` / `+hl.词命中 .12` / `+hl.搜索命中 .18` / `+hl.选区 .32` /
      `+hl.当前命中 .38` / `+--danger-dim`），几何 ∈ `behind|over`；新增
      `CONTRAST_CODE_HL_TOKEN = "--code-hl-rgb"`。
- [x] **`layer_color` / 判据函数支持两种配方**：`<底>+hl.<角色>` = `rgba(var(--code-hl-rgb), α)` 叠在底上；
      `<底>+--<rgba 令牌>` = 该令牌按自带 alpha 叠在底上（`--danger-dim` 就是这条）。
- [x] **`over` 几何进比值**：`contrast(over(tint, fg), over(tint, base))`；`behind` 层仍
      `contrast(fg, over(tint, base))`。探针读数里 `--tok-com` 在浅色 `.38` 层应给出 **2.69**
      （旧算法 3.10）——这是几何生效的判据。
- [x] **守卫腿⑧ 同源改造**：JS 侧同名常量（`CONTRAST_CODE_HL_TOKEN`、七行层表、几何）+
      `layerColor` 的两条配方 + 族格按几何算；`CONTRAST_FAMILY_KINDS` 词表不动。
- [x] **家族格数冻结** `CONTRAST_FAMILY_CELL_COUNT`（令牌数 × 层数 × 主题数，现算值写死）——防
      "表里少了一层而腿照绿"；读法与 `CONTRAST_PAIR_COUNT` 同一条纪律，注释里写清怎么复算。
- [x] **族里的层解不出色 = 红**（评审整改）：`contrastProblems` 逐条检查"族表里每个层名在这两主题下
      都解得出色"——不然把层名写成 `+hl.选区.20` 那种（两边都不认）会让**整格静默消失**。
- [x] **几何默认取严格那侧**（评审整改）：**带 tint 的配方**若不在 `CODE_LAYERS` 里 → 按 `over`，
      不按 `behind`。乐观的默认正是这一轮踩的坑：括号彩虹 8 层没登记进层表，按 `behind` 算出的
      7.70–10.03 比实测（**压在字上**：6.57–7.37）乐观 ≈2.5——两侧都过所以**不红**，
      "不许它悄悄变坏"被打折。
- [x] **括号彩虹立族**：`["--code-text × 括号彩虹底（8 色）", "=--code-text", [8 个彩虹层], "text", 理由]`
      ——它只压括号字形（括号没有 token 类），实测 6.6–7.4 ✅；登记为"已覆盖"，不许它悄悄变坏。
- [x] **`--code-hl-rgb` 落地**（值 = 现值）：`:root` = `0, 212, 255`（= 暗色 accent-rgb）、
      `html[data-theme="light"]` = `0, 150, 199`；代码页所有**高亮填充**改走它——
      `.code-pre-line.active` / `.code-hl-line.active` / `.code-pre-line.flash` / `.code-hl-line.flash` /
      `.code-gutter-line.flash` / `.code-mark-word` / `.code-mark-hit` / `.code-mark-current` /
      `.code-mark-bracket` 的淡底 / `.code-mark-guide` 的渐变 / `.code-ta::selection`。
      **装饰与前景不动**（滚动条 thumb 与 hover、`caret-color`、括号描边 ring 保持 `--accent`）。
- [x] **镜像守卫补判据**：`CODE_LAYERS` 三元组逐条一致、`CONTRAST_CODE_HL_TOKEN` 两侧一致、
      新配方正则两侧一致、`CONTRAST_FAMILY_CELL_COUNT` 两侧一致（`tests/test_contrast_mirror.py`）。
- [x] **例外表由生成器重算**（`generate-01-contrast-register.py --write`）：形状不变；
      本单落地后 `--tok-*` 那条族债的**冻结比值要跟着新算法更新**（`--tok-kw` on 当前命中那格由
      2.22 → 2.07，不许手抄）。
- [x] **合成红证**（腿⑧ 是纯函数，走内存注入）：① 层表少一条 → 红；② 几何写反（over 改 behind）→ 红；
      ③ `CONTRAST_FAMILY_CELL_COUNT` 与现算不符 → 红；④ `--code-hl-rgb` 缺失 → 红；
      ⑤ 族表里某个层名解不出色（配方写错）→ 红。
- [x] **观感零变化证据**：`probe-02-paint-order.mjs` 的样例在改动前后各采一遍像素，
      字形像素逐字节相同（浅/暗各一轮）；`probe-00` 的矩阵**新旧算法各落一张**
      （新 = 判据；旧 = 上一轮的账，"旧算 3.10 / 真渲染 2.69"那句要能一条命令复算）。
- [x] **门禁**：前端门禁全绿（腿⑧ 的用例数不变或 +1）；全量 pytest 全绿（含镜像守卫）；
      **浏览器门禁单独跑**（改了 `index.html` 的样式块）。

## 结论（形状 / 读数 / 门禁 / 评审处置）

### 形状

- **口径单源扩形**（`probe_lib.py` + 守卫腿⑧ 两侧同源，镜像守卫钉住）：
  `CODE_LAYERS = [(名字, alpha, 几何), …]` **七条**；`CONTRAST_CODE_HL_TOKEN = "--code-hl-rgb"`；
  层配方正则 `^(--[a-z0-9-]+)\+(hl|--[a-z0-9-]+)(?:\..+)?$`（尾段只是**角色名**，alpha 一律查层表——
  名字里写数字不算数，省得两侧各写一套数字谓词）。
- **几何进比值**：`over` 层 = `contrast(over(tint,fg), over(tint,base))`；`behind` 层 = `contrast(fg, bg)`。
  **默认取严格那侧**：带 tint 的配方若不在层表里 → 按 `over`（乐观的默认正是本单踩的坑）。
- **族表**：`--tok-* × 代码底（含 5 层高亮 + 错误行）`（10 令牌 × 7 层 × 2 主题 = 140 格）
  + 新立 `--code-text × 括号彩虹底（8 色）`（16 格）；`CONTRAST_FAMILY_CELL_COUNT = 168` 冻结
  （复算口 = `probe-00` §8）。
- **产品面接线**：新增 `--code-hl-rgb`（暗 `0, 212, 255` / 浅 `0, 150, 199` = 两主题 accent-rgb 现值）；
  代码页 11 条高亮填充 + md 预览的跳行闪烁改走它；**装饰与前景不动**（滚动条 thumb/hover、
  `caret-color`、括号描边 ring 仍 `--accent`）；选区 `.32` 与当前命中 `.38` **未动**（02 单的事）。

### 读数

| 面 | 读数 | 出处 |
|---|---|---|
| 几何（真像素） | 选区 / 标记层**压在字上**：浅 `#1a7f37→#118665`（over 预测 `#128665`）；括号彩虹暗 `#e9b6b9` = over 预测**逐字节** | `probe-02-pixels.txt` |
| 七层 × 两主题矩阵 | 浅色 10/10 掉线（最狠 `+hl.当前命中`：`--tok-kw` **2.07**）；暗色 9/10（最狠同层：`--tok-pre` **3.04**） | `probe-00-inventory.txt` §3 |
| 旧算法对照 | 例：浅 `--tok-com` @ 当前命中 = 旧算 **3.10** / 真渲染 **2.69** | 同上 §3"旧算法"那张 |
| 括号彩虹 | 新几何 6.57–7.37（旧算法口径 7.70–10.03，**偏乐观 ≈2.5**） | 同上 §2 |
| 族面格数 | **168**（140 + 16 + 6 + 6） | 同上 §8 |
| 层表 ↔ 盘上 | 七层的 alpha 逐条对上 | 同上 §1 |
| **观感零变化** | **14/14 格**逐字节相同（`--tag before`（`git stash` 出的旧树）vs `--tag after`） | `probe-02-pixels.txt` |
| 例外表 | 9 条（机械 1 + 族 3 + 令牌 5），生成器 `--check` OK——`--tok-*` 族债的**冻结值已按新几何更新**（`--tok-kw` 2.22 → 2.07） | `generate-01-contrast-register.py --check` |

### 门禁（树冻结后重跑）

| 门禁 | 读数 | 出处 |
|---|---|---|
| 前端门禁 | **1845 / 0** | `after-01-js-all.txt` |
| 浏览器门禁（单独跑） | **61 / 0**（188.9s） | `after-01-browser.txt` |
| 全量 pytest | **5688 passed + 11 skipped**（+2 = 镜像守卫新增两条） | `after-01-pytest.txt` |

### 双轴评审处置（10 条，逐条落地）

| # | 轴 | 发现 | 处置 |
|---|---|---|---|
| 1 | Spec | 票要求"新旧算法矩阵各落一张"，只落了新的 | ✅ `probe-00` §3 现在两张都打（旧算法明确标"不是判据"） |
| 2 | Spec | 票面写 `CONTRAST_FAMILY_CELLS`，实现叫 `..._COUNT` | ✅ 票面改名并对齐 |
| 3 | Spec | `.code-md-preview [data-md-line].flash` 是清单外多做 | ✅ 保留 + 票面登记理由（同一观感的跳行闪烁，两个色源会在 02 单分叉） |
| 4 | Spec/Std | **括号彩虹几何错**：8 层不在层表 → 默认 `behind` → 登记格比实测乐观 ≈2.5 且不红 | ✅ 默认改 `over`（严格那侧）+ 探针彩虹段改走 `contrast_on_layer`（两侧同源） |
| 5 | Std | **`probe-01-inventory.py:118` 二元组解包** → 实跑 ValueError（口径改形下游漏改） | ✅ 改三元组解包；跑通（七层表正常打印） |
| 6 | Std | 读数早于最后一次改 `probe_lib.py`（纪律①） | ✅ 全部读数在树冻结后重跑（本票"读数"一节的时间戳都晚于最后一次改动） |
| 7 | Std | 像素探针**自造口径**（自写 `over()`、硬编码 α、取 `--accent`）+ shots.json 里的死副本 | ✅ 重写：预测走 `probe_lib`（层配方 + alpha + `--code-hl-rgb`），删掉死键 |
| 8 | Std | 守卫注释里的边界数对不上读数、没写叠哪层 | ✅ 换成现算值（落定档 叠词命中 浅 4.15 / 暗 4.02…）+ 指名来源 §6 |
| 9 | Std | 冻结值的"复算方式"不可执行（手数） | ✅ `probe-00` §8 直接打印它（+ 镜像测试现算复核） |
| 10 | Std | `index.html` 三处注释仍写「`--accent-dim .12` / 淡 accent 底 / 随 `--accent` 自适应」 | ✅ 三处同步（含 `.code-mark-bracket` 那条） |

### 留给 02 单

- 层 alpha 降档（选区 `.32→.20`、当前命中 `.38→.24`）+ `--code-hl-rgb` 暗色取 `0, 190, 230`
  + 十个令牌换值——本单**只把口径与接线做对**，观感一个字没动。
- **叠加态仍是边界**（本单量过：现状 叠词命中 浅 4.36 / 暗 4.31、叠当前命中 **2.77 / 2.53**；
  落定档会是 4.15 / 4.02 与 3.42 / 3.11）——不进口径，读数在 `probe-00` §6。

## 备注

- 层的**名字用语义**（`hl.选区`）而不是 alpha 数字：02 单要改 alpha，改名会让例外表与认人键
  无谓 churn。
- 本单**不动** `.code-ta::selection` 的 `.32` 与 `.code-mark-current` 的 `.38`——降档是 02 单的事。
- 几何这件事的实测证据在 `probe-02-*`（真 Chromium 像素），票尾要把四条读数抄进来。
- **票面之外多做的一条**（Spec 轴评审点名，在此登记）：`.code-md-preview [data-md-line].flash`
  （代码页里 markdown 预览的"跳行闪烁"）也一并改走 `--code-hl-rgb`。理由：它就是代码页的跳行闪烁，
  与 `.code-pre-line.flash` 同一观感；留两个色源会在 02 单改暗色值时当场分叉。像素上本单无差别
  （两 rgb 现值相同）。
