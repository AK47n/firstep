# 03 — 禁用态：灰底灰字、去掉 opacity（有余力才做）

**要做什么：** 全站最低的那两处（人眼复核实测 hwcheck「带进生成页」**2.66**、
master「AI 提炼报告」**2.06**）不再靠"整体变淡"表达不可点——改成**灰底灰字**：
文字走 `--muted`、底走 `--panel-2`、描边走 `--border`，去掉 `opacity`。
做完之后禁用按钮的文字对比度是**可现算、可守卫**的，而不是"看它压在谁身上"。

**被谁阻塞：** 01（判据面共用腿⑧ 的族表；禁用态的格子走同一个函数）。

**状态：** resolved（2026-09-30；结论见文末）

- [x] **去掉三处 opacity**：`button:disabled { opacity: .45 }`、
      `textarea:disabled, input:disabled, select:disabled { opacity: .6 }`，
      以及组件级那几处覆盖（`.master-file-btn:disabled .55` / `.code-statusbar button:disabled .55` /
      `#btn-code-ai-send:disabled .5` / `.wait-cancel:disabled .6` / `.code-change-item.disabled .65` /
      `.platform-card.disabled .5`）——**共 8 条规则**，页面上 `opacity` 形式的禁用态归零
      （判据 ⑥ 钉住；`.off` / `.cant` 两个**别的类名**的形态不在票面射程，见文末边界）。
- [x] **统一口径**：`background: var(--panel-2)` + `color: var(--muted)` + `border-color: var(--border)`；
      `box-shadow: none`（去掉主按钮的外光/呼吸动画）；主 / 危险 / 幽灵三类形态一视同仁
      （禁用时不再保留各自的语义色）。`cursor: not-allowed` 保留（组件级那几处原本就是 `cursor: default`
      的**按原样保留**——它们是"动作进行中"而不是"不可点"，见文末）。**写法（双轴评审整改）**：
      禁用态只剩**一条通用规则**，形态规则各自用 `:not(:disabled)` 声明"那是启用态的外观"。
- [x] **判据进腿⑧ 的族面**（不新起腿）：加两格——「`--muted` × `--panel-2`」与
      「`--muted` × `--panel`」，两主题各算一遍，`text` 档 4.5。格数冻结 168 → **172**。
- [x] **结构判据**：页面上不许再出现 `opacity` 形式的禁用态（判据 ⑥）；**另加一条**（整改）：
      涂色的形态规则必须表态 `:not(:disabled)`（判据 ⑦）——不然它自己的底色会盖掉灰底灰字。
- [x] **渲染面证据**：`probe-07` 的禁用桶改成**不被祖先渐变滤掉**（禁用控件的底是元素自己那层，
      祖先渐变影响不到这个比值），并新增 `probe-08` 真元素截图 + 读像素（真像素比值）；
      **没量到的逐条记账**（`不可见 / 零尺寸 / 无文字 / 超过上限`），不许拿"扫描看不见"当达标。
- [x] **合成红证**：① `opacity: .45` 放回去 → 判据 ⑥ 红；② `--muted` 改浅 → 族面红；
      ③ `.disabled` 类选择器带 `opacity` → 红；另补 ④ 涂色形态不表态 → 判据 ⑦ 红 + 两条"判据不许过宽"
      的边界（`:not(:disabled)` / `.x-disabled` 不误判）。**真文件反证**另跑一支（2/2 判红、sha256 复原）。
- [x] **读数**：禁用按钮的实测比值（真元素 + 真像素），与旧读数 2.66 / 2.06 对照——见文末。
- [x] **门禁**：前端门禁全绿；全量 pytest 全绿；**浏览器门禁单独跑**。

## 结论（读数与账）

### 改了什么

| 面 | 内容 |
|---|---|
| 产品面（8 条规则） | `button:disabled`（含 `:hover` 与 `.btn:disabled`）／`textarea,input,select:disabled`／`.platform-card.disabled`／`.master-file-btn:disabled`／`.code-statusbar button:disabled`／`#btn-code-ai-send:disabled`／`.code-change-item.disabled`／`.wait-cancel:disabled` → 灰底灰字 |
| 形态侧（整改后） | 11 处选择器补 `:not(:disabled)`：`button.primary`（基类 + 渐变块 + `:hover` + `:active`）、`button.danger`、`button.accent`、`button.ghost:hover`、`button.pin-overview-on`、`button.code-change-item:hover`、`.task-card .btn-task-run` / `.btn-task-flash` / `.btn-task-dialog` |
| 判据（腿⑧） | 族面新增「--muted × 禁用态底（panel-2 / panel）」4 格（`CONTRAST_FAMILY_CELL_COUNT` 168 → **172**）；机械面 376 → **392** 对；结构判据 ⑥（禁用态不许 `opacity`）与 ⑦（涂色形态必须表态）；红证 n1–n6；镜像（`probe_lib` + `test_contrast_mirror` 族数 4 → 5、禁用态族 4 格断言） |
| 量具 | `probe-08-disabled-state{,-read}`（真元素截图 + 读像素，`--tag before/after` 逐格对照）＋ `pixel_lib.py`（读像素公共半，probe-02 读数半改用）＋ `probe-07` 禁用桶改造（不被祖先渐变滤掉、达标也逐条打出来）＋ `probe-04-real-file-red-proof.py`（真文件反证） |

### 读数（树冻结后整套重跑）

| 面 | 读数 | 出处 |
|---|---|---|
| **真像素：禁用控件（before → after）** | 浅 **2.65 / 2.06 → 5.25**；暗 **3.93 / 2.36 → 5.67**；**8/8 格变好**（其余几格同值）；预测（静态声明 + opacity 合成）与实测像素**逐格距离 0** | `probe-08-readings.txt` |
| 旧读数的复现 | 本探针的 before 一发把 `light-contrast/05` 人眼复核那两个数**复现到 0.01**：hwcheck「带进生成页」2.65（人眼 2.66）、master「AI 提炼报告」2.06 | 同上 |
| 全站扫描：禁用桶 | 两主题各 **5 处，低于阈值 0 处**，最低 浅 5.25 / 暗 5.67（改前那个桶是**空的**——被祖先渐变滤掉） | `probe-07-rendered-sweep.txt` |
| 静态族面两格 | `--muted` 压 `--panel-2`：浅 **5.25** / 暗 **5.67**；压 `--panel`：浅 6.59 / 暗 6.07 | `probe-00-inventory.txt` §8（172 格，新族 4 格） |
| 例外表 / 机械面 | 例外表仍 **7 条**；机械面 **392** 对，不达标/死条/过期 **0 / 0 / 0**；生成器 `--check` OK | `probe-03-contrast.txt` |
| 真文件反证 | ① `opacity: .45` 放回、③ 注入 `.disabled { opacity }` → 前端门禁**退出码 1** 且文案逐字点名；复原后 sha256 一致 | `probe-04-real-file-red-proof.txt` |
| 改前那一轮的像素读数 | 刷新 `probe-02-pixels.txt`（读数半改了：改用 `pixel_lib`）——与旧读数**逐行只差**脚本后来补的那句"旧 tag"提示，数值逐字节相同 | `probe-02-pixels.txt` |
| 三套门禁 | 前端 **1845 / 0**；浏览器 **61 / 0**（单独跑，222.9s）；pytest **5689 passed + 11 skipped** | `after-03-{js-all,browser,pytest}.txt` |

### 口径边界（明写在案）

1. **真像素覆盖到哪**：初始态**可见**的禁用控件 = 5 格/主题（generate 的目录输入 + 「选择文件夹」、
   hwcheck「带进生成页」+「让 AI 分析」、master「AI 提炼报告」）。本单改的其余几条
   （`.master-file-btn` / `.code-statusbar button` / `#btn-code-ai-send` / `.code-change-item` /
   `.wait-cancel` / `.platform-card.disabled`）在初始态不出现或**零尺寸**（probe-08 的"没量到"账：
   code 页 4 条**零尺寸**；`.platform-card.disabled` 与 `.master-file-btn` 要靠"某平台不可用 / 打开母版详情"
   才出现）——它们的达标依据是**静态族面**（八条规则声明的是同一对 `--muted` on `--panel-2`）+ 判据 ⑥⑦。
2. **`.module-card.off`（"需切换平台"的模块卡）与 `.pin-menu-list li.cant` 仍是 `opacity` 形态**：
   票面的结构判据按定义只认 `:disabled` / `.disabled`，这两个**别的类名**够不着；本单**没动**它们。
   现算（`--text` / `--muted` 按各自 opacity 压各自底）：`.module-card.off` 浅 **3.40 / 2.24**、
   暗 **5.09 / 2.69**——**浅色那两格低于 AA**，比本单修掉的 2.66 还低。要收它得先决定
   "不可选卡片"要不要跟按钮同一口径（改名成 `.disabled` 才能进判据 ⑥），**另开单**（已记进 backlog）。
3. **`cursor` 按原样保留**：通用按钮 `not-allowed`；`.code-statusbar button` / `#btn-code-ai-send` /
   `.code-change-item` / `.wait-cancel` 原本是 `default`（"动作进行中"语义，不是"不可点"）——票面
   "`cursor: not-allowed` 保留"按"不动它"理解。
4. **族面那两格与令牌面重叠**：`var(--muted)` 在令牌表的假定底里本来就有 `--panel-2`——本单要的是
   "禁用态"**具名**的那一格（族名即契约，例外表将来点名它时读得出来），两侧都留着；改浅 `--muted`
   时两条会一起红（不是漏报）。
5. 叠加态（选区叠命中）、`--accent` 控件描边 2.70 等既有边界不在本单。

### 双轴评审处置（10 条，逐条落地）

| # | 轴 | 发现 | 处置 |
|---|---|---|---|
| 1 | Std | `CONTEXT.md` 的硬数（376 对 / 168 格）与 README 未回改，违纪律#3 | ✅ 回改 CONTEXT（392 / 172 + 族表 + 禁用态读数），并顺手订正镜像守卫条数（原写 24、实为 25） |
| 2 | Std | `after-03-js-all.txt` 未入库（前端门禁读数无凭据） | ✅ 本单全部读数一并入库 |
| 3 | Std | 红证 n4/n5 缺"注入没生效"断言（锚点漂移即空转） | ✅ 补 `assert.notEqual`，并新增 n6 三条（判据⑦ + 两条过宽边界） |
| 4 | Std | 禁用态靠**枚举形态**写选择器 = Shotgun Surgery | ✅ 改成"形态规则自己带 `:not(:disabled)`"，禁用态只剩一条通用规则；**判据⑦** 钉住这条纪律（不然又是一条无门禁的边界） |
| 5 | Std | `probe-08` 与 `probe-07` 的 JS 助手重复 | ⚖ 不改：`page.evaluate` 载荷会被序列化丢进浏览器、看不到模块作用域，助手**必须**随载荷自带；已在两处写明（Python 读数半那边能共用，已抽 `pixel_lib.py`） |
| 6 | Std | `probe-08` 读数半：死元组项 / 同一查找写两遍 / "没变好"误报 | ✅ 三条都改：去掉尾项、两张表同一把认人键、结论分 变好/没变/变差 三档 |
| 7 | Spec | 渲染面真像素只到 5 格（组件级那几条一格没量） | ⚖ 部分落地：probe-08 增"**没量到**"逐条记账（原因分类）+ 覆盖边界写进结论与 README；那几条在初始态不可达，达标依据 = 静态族面同一对色 |
| 8 | Spec | `.module-card.off` 没动（"不许再有 opacity 形式的禁用态"没兑现到它） | ⚖ 记在案（含现算数：浅 3.40 / 2.24）：判据按票面定义够不着它，改口径要另开单——已写进 backlog §32 |
| 9 | Spec | `.task-card .btn-task-run`（(0,2,0)）压得过 `button:disabled`，且这条边界无门禁 | ✅ 那三条补 `:not(:disabled)` + 判据⑦（真·无门禁 → 有门禁） |
| 10 | Spec | 越界：抽 `pixel_lib.py` 并改了 `probe-02` 读数半，且没重跑它的读数 | ✅ 重跑并落盘（与旧读数逐行只差脚本后补的提示句，数值相同）；抽公共半的理由 = probe-08 要读像素，不抽就是第二份（工单 03 的"另一条腿"改的是**读数半**，产品面零改动） |

## 备注

- 本单是**有余力才做**的部分（用户拍板口径已给："灰底灰字、去掉 opacity"）；若 01/02 的收口
  已经很紧，可以整单推迟到下一轮，但**口径已定**，别重新发明。
- `.platform-card.disabled` 是"不可选的卡片"不是按钮，形态上保留 `--panel-2` 底即可，
  文字同样走 `--muted`。