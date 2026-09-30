# light-contrast —— 浅色调色板 + 对比度守卫（把「哪些颜色对算达标」变成可对账的数据）

> 立项 2026-09-30。上游：`.scratch/border-guard/`（描边守卫，01–03 全 resolved）——
> 它收尾时把两条尾巴写进了 `backlog.md` §29：**`--accent` 小字浅色 3.39:1（低于 AA）**
> 与**「去框留淡底」×1.06**。本轮就是把这两条尾巴做成一轮，并顺手把**对比度**这条线
> 从"人眼 + 散文账"升级成"现算 + 可对账"（照描边那轮的形状）。
> 流程照 `docs/agents/workflow.md`：clarify → spec → 工单 → 逐单实现 + 双轴 code-review → resolved。

## 一句话

浅色主题下**每一个「文字色 × 它自己的底」都过 AA**（小字 4.5 / 大字 3.0），
「去框留淡底」的块与页面底分得开（×1.065 → ×1.18），**暗色零变化**（除两处 1.77:1 的白字）；
而"过不过 AA"从此是**守卫现算的**——新增一条不达标的组合当场判红，记账的债不许静默恶化。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `spec.md` | 需求 spec（问题陈述 / 方案 / 用户故事 / 实现决策 / 测试决策 / 范围外 / 拍板记录 / 被否掉的三种方案） |
| `issues/01-guard-leg8-and-data.md` | 腿⑧：机械抽取 + 例外表（118 条）+ 跨语言镜像 + 合成红证（**产品面零改动**） |
| `issues/02-light-six-families.md` | 浅色六族落地：`--accent-text` + ok/warn/danger/info/purple 微调 |
| `issues/03-panel2-and-dark.md` | `--panel-2` 加深（×1.18）+ 暗色 16 处 + 非文字 3:1 |
| `issues/04-render-side-leg9.md` | 腿⑨：`static/js/**` 19 处内联取色入册 |
| `issues/05-closeout.md` | 收口：量具跨页重跑 + 三套门禁 + 人眼复核 + 文档回改 |
| `probe_lib.py` | **口径单源**（阈值 / 亮度公式 / 合成 / 规则切分 / 族表）+ 从守卫源码解析例外表 |
| `probe-01-inventory.py` | 侦察：机械配对清单（376 对，两主题）+ 候选值格网（`--accent-text` × `--panel-2`） || `probe-02-js-inline.py` | 侦察：渲染方内联取色（19 处令牌 + 5 处裸值/透明 + 0 处跨行拼接） |
| `probe-03-contrast.py` | **读数**：例外表 ↔ 盘上双向对账 + 族面最坏格 + **覆盖审计**（跨规则配对） |
| `probe-04-family-candidates.py` | 选值：六族各自"改文字令牌还是改淡底 alpha"（两条路的数都算出来） |
| `probe-05-mirror-and-check-red.py` | **反证**：镜像守卫与生成器 `--check` 判不判得红（八处注入，复原走 sha256 校验） |
| `generate-01-contrast-register.py` | 例外表的**生成器**（`--write` 写入守卫 / `--check` 复核"还是生成时那张吗"） |
| `probe-0*.txt` / `after-0*.txt` | 读数（**照片，不是结论**——每轮改动后重跑） |

## 口径三条（别混着读）

1. **底 = 元素自己那层背景合成到 `--panel` 上**——`rgba` 淡底要叠上去，**不是**祖先底。
   上一轮那三个乐观数（`.ref-none` 6.11 / `.ref-kit` 5.19 / `.ref-topic` 3.39）量的是祖先底，
   按真实合成底是 **4.50 / 4.38 / 2.95**（本轮更正）。
2. **阈值按该规则自己的 `font-size` / `font-weight` 定**：≥24px 或 ≥18.66px+bold ⇒ 3.0，否则 4.5；
   未声明 = 继承 body 14px = 小字。族面 / 令牌面的 `nontext`（焦点环 / 语义左条 / 装饰字形）走 3.0。
3. **判据分三面**（各管一段，别互相外推）：
   **机械面** = 同一条规则里既有 `color:` 又有 `background:`（376 对，现算 + 只登记债）；
   **族面** = 底在代码页那几层的族（`--tok-*`、焦点环），取最坏格；
   **令牌面** = **无底规则里的文字令牌**（390 条，底在基类或祖先）——令牌级、不是选择器级。
   认人键 = `(主题, 剥注释后的选择器)` / `(主题, 族：标签)` / `(主题, 令牌：字面)`，
   解析面 = **剥掉 CSS 注释的 `<style>` 块**（描边那条腿**故意不同**：它按"不剥注释的历史口径"
   认人，115 条登记簿不动）。

## 怎么复跑

**都在仓库根跑**，用**系统 `python`**（不是 `.venv\Scripts\python.exe`——那是应用运行时，没有 pytest）。

```powershell
# 侦察与读数（探针自己 reconfigure stdout，不必设 PYTHONIOENCODING）
python .scratch\light-contrast\probe-01-inventory.py     # 机械清单 + 候选值格网
python .scratch\light-contrast\probe-02-js-inline.py     # 渲染方内联取色
python .scratch\light-contrast\probe-03-contrast.py      # 例外表 ↔ 盘上双向对账 + 覆盖审计

# 例外表的生成关系（读 + 可选写）
python .scratch\light-contrast\generate-01-contrast-register.py           # 打印表
python .scratch\light-contrast\generate-01-contrast-register.py --check    # 守卫那张表还是生成时那张吗

# 三套门禁（**浏览器门禁不与全量 pytest 并行**）
python .scratch\ui-density-sitewide\readings.py re-js      --out-dir .scratch\light-contrast -- node --test "tests/js/*.test.mjs"
python .scratch\ui-density-sitewide\readings.py re-browser --out-dir .scratch\light-contrast -- node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
python .scratch\ui-density-sitewide\readings.py re-pytest  --out-dir .scratch\light-contrast -- python -m pytest -n auto -q
```

⚠ 落盘读数请走 `.scratch/ui-density-sitewide/readings.py`：PowerShell 的 `>` / `Tee-Object` 写 UTF-16LE
（`read` 工具当二进制拒读），`Select-Object -First N` 会掐断上游留下孤儿后端。

## 判断边界（别误读）

1. **三面都只登记不达标与不适用**（达标的现算即可）——这与描边那轮"115 条全登记"**不是同一把尺**；
   闸门强度靠"抽得到、算得出"，不靠表的规模。
2. **例外表只该变小**：02/03/04 单每修好一族就摘掉对应行。它变大 = 有人把新的不达标登记成了债
   （守卫按三面分别卡上限：机械 ≤115 / 族 ≤3 / 令牌 ≤10）。
3. **静态面判不了渲染后的层叠**：`color:` 继承自祖先、JS 动态换色、跨行拼出来的声明都不在射程内；
   令牌面就是为"底在祖先"那 390 条规则立的（但它是**令牌级**：同一个令牌压在不同底上时，
   选择器级的精确配对仍归前两面）。渲染面由量具（05 单那支）作证，两面读数要对得上。
4. **覆盖审计目前两向差集为 0**：机械面（同规则配对）与"同选择器跨规则配对"在这个文件上
   **逐条相同**（376 ↔ 376、115 ↔ 115）——没有漏掉跨规则那种写法。
5. **`--tok-*` 语法高亮族是记在册的债**（浅色 8/10 个令牌低于 4.5），本轮只量不修：
   改它 = 改代码长什么样，属另一件事。
6. **`skip` 是后门，要有人看着**：它只该装"静态判不了"（`::selection` 反白块 / `inherit` /
   未定义令牌 / 已由族面覆盖）。新增 `skip` 必须同时写理由——评审时逐条问"这是判不了，还是不想判"。
