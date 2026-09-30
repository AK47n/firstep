# code-contrast —— 代码配色族 `--tok-*` 修到 WCAG AA（七层底全包）

> 立项 2026-09-30。上游：`.scratch/light-contrast/`（浅色调色板 + 对比度守卫，01–05 全 resolved）——
> 它把 `--tok-*` 语法高亮族记成「**只量不修**」的债，本轮把这笔债还掉，顺手把口径补正
> （层 5 → 7、补上**叠放几何**）。
> 流程照 `docs/agents/workflow.md`：clarify → spec → 工单 → 逐单实现 + 双轴 code-review → resolved。

## 一句话

代码页上「文字会压到的底」**是七层不是五层**，而且高亮层**压在字上**（字形也被染）——
按真渲染算，十个 `--tok-*` 在两主题 × 七层上全部 ≥ 4.5:1；代价是选区/当前命中各降一档
（`.32→.20` / `.38→.24`），暗色语法色只动两个、其余逐字节不动。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `spec.md` | 需求 spec（问题陈述 / 方案 / 用户故事 / 实现决策 / 测试决策 / 范围外 / 拍板记录 / 被否掉的五种方案） |
| `issues/01-seven-layers-and-geometry.md` | 口径补齐：七层 + 叠放几何 + `--code-hl-rgb`（**观感零变化**） |
| `issues/02-land-values.md` | 落值：高亮降一档 + 十个令牌（`--tok-*` 族债还清） |
| `issues/03-disabled-state.md` | 禁用态（灰底灰字、去掉 `opacity`）——**未做**，「有余力才做」 |
| `issues/04-closeout.md` | 收口：真像素证据 + 三套门禁 + 人眼 + 文档与账 |
| `probe-00-inventory.py` | **侦察/主探针**：层表 ↔ 盘上对账（含 alpha）+ 新旧算法矩阵 + 层侧扫描 + 叠加态 + 落定读数 + 族面格数 |
| `probe-02-paint-order.mjs` | **真像素**：高亮层压在字上还是垫字下（`--tag before/after` 各拍一套，供"观感零变化"取证） |
| `probe-02-paint-order-read.py` | 上者的读数半：读 PNG → 字形像素 → 与两侧预测对差 + **实测比值** + 多 tag 逐格对照 |
| `probe-03-shots.mjs` | **人眼复核截图**：代码页 × 两主题 × 两种源（.c / .syscfg）× 三态（原样/选中/查找命中） |
| `probe-0*.txt` / `after-0*.txt` | 读数（**照片，不是结论**——每轮改动后重跑） |

## 口径三条（别混着读）

1. **层是七层**：代码底 / `+hl.当前行 .07` / `+hl.词命中 .12` / `+hl.搜索命中 .18` /
   `+hl.选区 .20` / `+hl.当前命中 .24` / `+--danger-dim 错误行`。上一轮只登记了前五层里的四层
   （没有 `.38`、没有错误行）。
2. **几何**：`.code-marks` 与 `.code-ta::selection` **画在字上**（真像素实测）⇒ `over` 层的比值是
   `contrast(over(tint,fg), over(tint,base))`；只有行元素自己那两层（`.active`/`.flash`）是 `behind`。
   **带 tint 的配方没登记进层表 → 按 `over` 算**（默认取严格那侧）。
3. **边界**：口径是**每层单独**算；真实使用里层会**叠**（双击选词 = 词命中 + 选区），
   落定档下叠词命中 浅 4.15 / 暗 4.02、叠当前命中 浅 3.42 / 暗 3.11——**不进判据**。

## 怎么复跑

**都在仓库根跑**，用**系统 `python`**（不是 `.venv\Scripts\python.exe`——那是应用运行时，没有 pytest）。

```powershell
# 主探针（层表对账 + 矩阵 + 叠加态 + 落定读数 + 族面格数）
python .scratch\code-contrast\probe-00-inventory.py

# 真像素（两半：先拍后读；多 tag 会逐格对照）
node   .scratch\code-contrast\probe-02-paint-order.mjs --tag after
python .scratch\code-contrast\probe-02-paint-order-read.py

# 人眼截图（代码页 × 两主题 × 两源 × 三态）
node   .scratch\code-contrast\probe-03-shots.mjs

# 例外表的生成关系 / 全站渲染面回归
python .scratch\light-contrast\generate-01-contrast-register.py --check
node   .scratch\light-contrast\probe-07-rendered-sweep.mjs

# 三套门禁（**浏览器门禁不与全量 pytest 并行**）
python .scratch\ui-density-sitewide\readings.py js      --out-dir .scratch\code-contrast -- node --test "tests/js/*.test.mjs"
python .scratch\ui-density-sitewide\readings.py browser --out-dir .scratch\code-contrast -- node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
python .scratch\ui-density-sitewide\readings.py pytest  --out-dir .scratch\code-contrast -- python -m pytest -n auto -q
```

⚠ 落盘读数请走 `.scratch/ui-density-sitewide/readings.py`：PowerShell 的 `>` / `Tee-Object` 写 UTF-16LE
（`read` 工具当二进制拒读），`Select-Object -First N` 会掐断上游留下孤儿后端。

## 当前读数（2026-09-30 收口）

| 面 | 读数 | 出处 |
|---|---|---|
| 层表 ↔ 盘上 | 七层的 alpha 逐条对上 | `probe-00-inventory.txt` §1 |
| 族面格数 | **168**（`--tok-*` 140 + 彩虹 16 + 两条 nontext 6+6） | 同上 §8 |
| 族面最坏格 | 浅 **4.66**（`--tok-pre` on 当前命中）／暗 **4.65**（`--tok-const`）——冻结进 `CONTRAST_TOK_WORST` | 同上 §7 |
| 旧算法对照 | 浅 `--tok-com` @ 当前命中：旧算 **3.10** / 真渲染 **2.69** | 同上 §3 |
| 括号彩虹 | 6.57–7.37（旧口径 7.70–10.03，**偏乐观 ≈2.5**） | 同上 §2 |
| 叠加态（边界） | 叠词命中 浅 4.15 / 暗 4.02；叠搜索命中 3.75 / 3.55；叠当前命中 3.42 / 3.11 | 同上 §6 |
| 例外表 | **9 → 7 条**（`--tok-*` 两条族债摘掉），生成器 `--check` OK | `generate-01-contrast-register.py` |
| **真像素（选区态）** | 浅 com **4.80** / str **4.68**；暗 com **4.90** / str **4.55**（改前 2.78 / 3.02 / 3.52 / 3.17） | `probe-02-pixels.txt` |
| **观感零变化**（01 单） | **14/14 格逐字节相同**（`--tag before` 是 `git stash` 出的旧树） | 同上 |
| 全站渲染扫描 | 浅 2 / 暗 2（与上一轮收口同数，不退化） | `after-02-probe-07.txt` |
| 前端门禁 | **1845 / 0** | `after-02-js-all.txt` |
| 浏览器门禁 | **61 / 0**（单独跑） | `after-02-browser.txt` |
| 全量 pytest | **5688 passed + 11 skipped** | `after-02-pytest.txt` |

## 判断边界（别误读）

1. **判据只判"过不过线"，不判"好不好看"**：本轮靠 `probe-03-shots.mjs` 的截图做人眼复核
   （机器证不了"刺不刺眼"）。
2. **叠加态是边界不是达标项**（见口径三条之 3）：要收它得让所有高亮淡到几乎看不见。
3. **"观感零变化"只属于 01 单**：02 单是**故意**改像素的（语法色深浅与高亮强度都变了）——
   拿 02 之后的树去跟 `--tag before` 比会得到"5/14 相同"，那是预期。
4. **几何是本轮更正的口径，不是新功能**：旧算法的账（"压在合成底上"）在 `probe-00` §3 仍会打出来，
   标着「**不是判据**」，用来复算"更正了多少"。
5. **`--code-hl-rgb` 是独立旋钮**：实测它就是"语法色能有多亮"的第一约束；`caret-color` /
   括号描边 ring / 滚动条仍走 `--accent`（那是前景与控件，不是代码高亮）。
6. **工单 03（禁用态）没做**：口径已拍板（灰底灰字、去掉 `opacity`），票在 `issues/03`——
   那笔账（实测 2.66 / 2.06）**仍然开着**。
