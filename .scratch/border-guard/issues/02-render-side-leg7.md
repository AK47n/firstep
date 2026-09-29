# 02 — 渲染方面：10 处内联整圈框登记 + 守卫腿⑦ + 合成红证

**要做什么：** 把 `static/js/**` 里**内联写出来的整圈完整框**也纳入机器守卫。
那 10 处（`fx/flash.js` / `fx/task.js` / `ui/codeeditor.js` / `ui/generate-recommend.js` /
`ui/generate-pins.js`）逐条登记为 `[文件, 锚点片段, 类别]`，守卫加**腿⑦**双向对账 + 合成红证；
读数里出渲染方面。**不改一行渲染方代码**——腿⑦ 只读。

**被谁阻塞：** 01（沿用同一张类别表 `BORDER_KINDS` 与同一套对账原语）。

**状态：** resolved（2026-09-29；结论 / 读数 / 双轴评审处置见文末）

## 验收标准

- [ ] **渲染方登记簿落地**：`JS_BORDER_REGISTER`，**恰好 10 条**（盘上现算的实况，不许照票面抄），
      每条 `[文件, 锚点, 类别]`；锚点是**该声明所在行的可认片段**（类名 / id / 变量名），
      **不取行号**——行号会随插行漂。
- [ ] **腿⑦ 判据（纯函数，两条方向）**：盘上渲染方完整框 **⊆** 登记簿；登记簿 **⊆** 盘上。
      只认 `border:` **简写**且值非 `none`/`0`（`border-top` / `border-bottom` 这类单边分隔线
      **不在射程内**，与样式块面的口径一致）；`font-size` 那条既有腿的两种拼法先例照抄。
- [ ] **合成红证**：往一个假 JS 源里塞一条未登记的内联框 → 判红；锚点不匹配 → 判红；
      只写 `border-top` 的源 → **不判红**（口径边界要自证）；复原转绿。
      锚点取自真实源码并断言锚点还在。
- [ ] **读数复算**：探针能报渲染方面的双向差与逐条清单（从守卫源码解析登记簿）；
      读数落盘，时间戳晚于最后一次改产品面。
- [ ] **产品面零改动的机器证明**：`git status src/contest_generator/static` 为 **0 行**。
- [ ] **门禁**：前端门禁全绿且比本单前多出本单的用例。
- [ ] **双轴评审**跑过，发现逐条处置并在票尾记账。

## 备注

- 为什么单独一单：这是**另一个面**（另一份登记簿、另一条腿、另一组红证），
  与 01 的 115 条不重叠——08 单给「内联字号」补第五条腿时也是先有样式块面、后有渲染方面。
- 口径边界要写进守卫文件头：**渲染方里动态拼出来的取值**（如 `border:1px solid ${st[0]}`）
  锚点只能取到拼接前的那一段字面量——如实写明射程到哪。

## 结论（形状 / 读数 / 门禁 / 评审处置 / 账）

### 形状

- 守卫新增 `JS_BORDER_REGISTER`（10 条 `[文件, 行内锚点, 类别]`，与样式块面**共用** `BORDER_KINDS`）
  + 腿⑦ 判据 `jsInlineBorderEntries()` / `jsBorderRegisterProblems()` + 一条腿⑦ 用例 + 合成红证。
- **抽出两个公共件**（01 评审点的"腿⑥腿⑦ 逐行重复"）：`borderKindProblems()`（类别值校验）与
  `multisetBorderProblems()`（多重集双向对账骨架，两条腿共用）。**顺带堵掉一个对称的洞**：
  01 给腿⑥ 补的"同一认人键不止一条"分支，腿⑦ 原来只判 `m < n`（漏"多"）——
  现在两个方向都在公共骨架里，一次修好两条腿。
- 认人键 = `(文件, 行内锚点)`；`want`/`got` 是 `Map<键, {count, label}>`——
  **键只用于查表、不再拆回来**（01 评审点的 Primitive Obsession：拼 `\u0000` 再 split）。
- `scope_lib.py` 追加 Python 侧镜像：`js_files` / `js_inline_border_entries` / `load_js_border_register`；
  `tests/test_border_register_mirror.py` 加**第 5 条**（钉渲染方那条正则，与样式块面那条**分开钉**）。
- 新增探针 `probe-04-js-register.py`（双向差 + 每类条数 + 逐条清单 + 单边分隔线脚注 + **覆盖审计**）。
- **产品面零改动**：`git status --porcelain src/contest_generator/static` = **0 行**（一行 JS 都没碰）。

### 读数（落盘在 `.scratch/border-guard/`，时间戳晚于最后一次改动）

| 面 | 读数 | 出处 |
|---|---|---|
| 盘上渲染方内联整圈框 | **10** 条 | `probe-04-js-register.txt` |
| 渲染方登记簿 ↔ 盘上 | **0 / 0 / 0**（未登记 / 过期 / 锚点歧义） | 同上 |
| 类别分布（共用 `BORDER_KINDS`） | alert 3 / nonbox 3 / tag 2 / float 1 / doc 1 | 同上 |
| **覆盖审计** | 含 `border…:` 的行 **15** = 入册 10 + 撤框 0 + 单边分隔线 5，**0 处没归类** | 同上 |
| 样式块面（01）不退化 | 115 / 双向差 0/0 | `probe-03-register.txt` |
| 解析口径对账 | 规则 1607 vs 1593、描边面逐条相同 | `probe-02-caliber-styleblock.txt` |

### 门禁

| 门禁 | 读数 |
|---|---|
| 前端门禁 | **1842 / 0**（01 收口 1841，+1 = 腿⑦ 用例） |
| 全量 pytest | **5664 passed + 11 skipped**（01 收口 5663，+1 = 镜像第 5 条） |
| 反证：镜像守卫 | **5 处**注入全红、复原 sha256 逐字节相同（`probe-05-mirror-red.py`） |
| 反证：两支生成器 `--check` | **4 处**注入全红、复原逐字节相同（`probe-06-generator-check-red.py`） |

### 双轴评审（`code-review`：Standards + Spec 并行）的发现与处置

| # | 发现 | 处置 |
|---|---|---|
| Std-1 / Spec-c1 | **多重集只判单向**：`if (m < n)` 漏掉"盘上多出一条"（01 给腿⑥ 补过对称分支，腿⑦ 没补）——Spec 轴实测：同行再写一条完整框 → 判据返回 `[]` | ✅ 抽公共骨架 `multisetBorderProblems`（`g.count !== w.count` 两个方向都报）+ 补红证 (d2)（真给 `ui/codeeditor.js` 复制一行 → "登记了 1 条、盘上有 2 条"） |
| Std-2 | 注释写"腿⑦ 两条判据"，实际三条（多一条类别校验） | ✅ 注释改成"三条"并逐条列出 |
| Std-3 | 02 票备注要求把"动态拼接取值"的射程写进守卫文件头，没落实 | ✅ `JS_BORDER_REGISTER` 说明块写明 `border:1px solid ${st[0]}` 的锚点取到的是**拼接前的字面量** |
| Std-4 / Spec-b | 01 的整改没延续到 02：`generate-02` **没有 `--check`**、生成物**没有"已消费"标注** | ✅ 都加上；`probe-06` 扩成**两支各证一遍** |
| Std-5 | `generate-02` 重抄了 `js_files` / 正则 / `DEAD_BORDER`（同单的 probe-04 却是 import 的） | ✅ 全部改成从 `scope_lib` import |
| Std-6 | `probe-04` 里的 `FULL_RE` + `("none","0")` 是口径的第三四份副本，落在对拍守卫射程外 | ✅ 改成 import `JS_BORDER_LINE_RE` / `DEAD_BORDER`；保留的两条正则**明写是"更宽的审计网"**、不是口径 |
| Std-7 | 腿⑥/腿⑦ 的对账原语逐行重复 | ✅ 抽 `borderKindProblems` + `multisetBorderProblems` |
| Std-8 | `borderKey` 拼 `\u0000` 再 split 拆回（Primitive Obsession） | ⚖ 复合键保留（JS 的 Map 只吃字符串键），但**不再拆回来**：改为 `Map<键, {count, label}>`，印给人看的那一行跟着数据走 |
| **Spec-a1** | 工单要求"照抄 `font-size` 腿的**两种拼法**先例"，腿⑦ 只认 `border:` 字面——驼峰 `el.style.border = "…"` 与 `border :` 都扫不到 | ✅ 正则加两种拼法（CSS 串 + JS 属性），并补红证；盘上今天各 0 处，**认它们是为了"以后写了也进得来"** |
| **Spec-c2** | 红证"单边分隔线不判红"喂的是 `x.style.borderTop = "…"`——那串**根本不含 `border:`**，对任何正则都返回空 ⇒ **空断言**，什么都没证明 | ✅ 注入串改成真有 `border-top:` 的形态；并补正例（真有一条内联框时判据必须认出来），免得"不判红"只是因为判据整个不工作 |
| **Spec-c3** | 锚点 `max-width:640px` 是 9 个里唯一不含 border 文本的——纯布局编辑会让判据误红 | ✅ 换成 `border:1px solid var(--border,#ccc)`（同样唯一命中那一行） |
| Spec-b | 票面只要 4 件，实际多带 `generate-02` + `register-js-block.js.txt`；另改了 `probe-05`（不在给的 diff 面里） | ⚖ 记账：前两个是"生成物 + 一次性脚本"的既定形态（已加"真源是守卫"抬头 + `--check`）；`probe-05` 加第 5 条注入是**镜像第 5 条的必要配对**，属本单范围（评审面是我给的，给漏了） |
| Spec-b | 多了一条"类别值必须在 `BORDER_KINDS` 里"的检查，票面只要求两条方向 | ⚖ 记账：spec 用户故事 6 支撑（"每条登记项都带一个类别"），且已抽成两条腿共用的 `borderKindProblems` |

### 账（留给下一轮）

1. **渲染方的锚点必须"含 border 文本"**：`max-width:640px` 那种锚点会让**纯布局编辑**误红
   （Spec 轴实测）。选锚点的规矩：**锚点所在行的那段文本必须与这条框声明本身有关**。
2. **`generate-02 --check` 与 `generate-01 --check` 是同构的**：改动 `JS_BORDER_REGISTER` 之后
   跑一下就能知道"守卫那张表还是不是生成时那张"（`probe-06` 两支都证过）。
3. **PowerShell 5.1 的 `Get-Content` 会吞换行**（本单踩到，见 `local-environment`）：
   读 UTF-8 无 BOM 的源码文件必须 `-Encoding UTF8` 或用 Python——否则**行号会错**
   （`ui/codeeditor.js` 实测 2711 行 vs 真实 3231 行）。这也是"锚点不取行号"这条设计的实证。
