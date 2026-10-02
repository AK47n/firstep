# contrast-residue —— 对比度残余面收口（2026-10-01）

**这一批收的是** `backlog.md` §33 末「仍开着的」**六条**（A1–A6）：全站 `opacity` 全量登记、
`.pin-menu-list li.cant` 的真像素、叠加态定价、`--accent` 非文字 3:1、`.pin-subtitle` 的 `var(--fg)`
笔误、两个图例色点的令牌归属。**本轮不发版。**

入口：[`spec.md`](spec.md)（含拍板记录）· 六张工单在 [`issues/`](issues/) · 上游账本 `backlog.md` §34。

## 六张单

| 单 | 状态 | 一句话 | 关键读数 |
|---|---|---|---|
| [01 令牌解析面扩到全部定义块](issues/01-token-face-all-blocks.md) | resolved | 合并全部 `:root`（后者覆盖前者）+ 定义面 + 两侧共用行为向量表 | 新解出 **19** 个令牌；机械面 394 / 族面 172 不动 |
| [02 `--fg` 笔误 + 腿⑩](issues/02-undefined-token-leg.md) | resolved | 改 `var(--text)`；新腿"无兜底的 `var()` 必须有定义" | 真笔误 **1 → 0**；计算样式两主题**逐字节相同** |
| [03 色点归属 + 亮色补焊盘](issues/03-legend-dots-and-fixed-pad.md) | resolved | 两个色点 `skip` → `surface-bordered`；亮色补 `--pin-fixed-pad` | 浅色固定焊盘 `rgb(23,27,33) → rgb(175,184,193)`；暗色不变 |
| [04 opacity 全量登记 + 三条抬值](issues/04-opacity-full-register.md) | resolved | 判据②全量驱动；+11 条登记；词法嫌疑面退役 | 活规则 15 条、**未在册 0**；三条文字 3.52/4.10/4.18/3.91 → 5.25/5.67/5.72/4.85 |
| [05 `li.cant` 真像素](issues/05-pin-cant-pixels.md) | resolved | 量具改口径：MSPM0 + `step_motor` + 等判据模型 | 整行 **浅 5.25 / 暗 5.67**（与静态族面逐位对得上） |
| [06 记债与收口](issues/06-debt-and-closeout.md) | resolved | 两笔明账进守卫注释；台账 + 交接区回改；三套门禁 | 见下 |

## 探针与读数（都能复跑）

| 文件 | 干什么 | 关键读数 |
|---|---|---|
| `probe-00-recon.py` | recon：令牌块盘点 + 未定义令牌面 | `:root` 块 2 个；真笔误只有 `--fg` 一处 |
| `probe-01-token-face.py` / `.txt` | 解析面扩面前后对照 | 暗色 95 → **114**（+19）；亮色 74 → 74 |
| `probe-02-page-injection.py` / `probe-02-red-proof.txt` | 真文件反证（第二个 `:root` 改名） | 门禁红 → 复原 sha256 `3A1EC757…` 一致 |
| `probe-03-subtitle-color.mjs` / `probe-03-compare.py` | `.pin-subtitle` 零观感取证（真 Chromium） | 两主题 computed `color` 相同 |
| `probe-04-fg-red-proof.txt` | `var(--fg)` 放回去 | **两条腿各红各的** |
| `probe-05-pin-pad-colors.mjs` / `probe-05-compare.txt` | 板图焊盘 / 图例色点改前改后 | 浅色 `rgb(23,27,33) → rgb(175,184,193)` |
| `probe-06-register-readings.py` | 渲染方登记表形状 | 19 条（text 16 / surface-bordered 3）；`skip` **0** |
| `probe-07-muted-text-pixels.mjs` / `probe-07-compare.txt` | 三条真文字的真像素（改前用 HEAD 版页面现跑） | 见工单 04 表；`.res-soft` **没量到**（账没抹平） |
| `probe-08-opacity-inventory-after.txt` | `disabled-forms` 那支盘点探针（口径已跟改） | 20 = 帧 5 + 活规则 15；未在册 **0** |
| `probe-09-cant-readings.py` / `.txt` | `li.cant` 真像素读数 | 整行 5.25 / 5.67；**新账：`.role-type` 浅 3.54** |
| `run-before-after.py` | 通用「改前/改后」两发跑法（换 HEAD 版页面 + 核 sha256 复原） | —— |
| `probe-10-closeout-red-proofs.py` / `probe-10-red-proofs.txt` | **收口三发真文件反证**（`opacity` 没登记 / `var(--fg)` / 第二个 `:root` 改名） | 三发全部按预期红、复原 sha256 一致、复原后转绿 |
| `check-encoding.py` / `tick-ticket.py` | 本机卫生小工具（BOM 体检 / 勾选工单） | 多余 BOM **0** |

## 双轴评审（`code-review`，base `01beebce`）

Spec 轴 5 条 / Standards 轴 5 条：**7 条已改**（补第三类真文件反证 + sha256、删越界杂物
`.scratch/release-v1.4.2/push-02-ledger.txt`、注释里的数按落盘读数改正、`probe-00-recon.py` 改单源
并修掉"没剥注释"的假读数、镜像文件头"十组"→"十一组"），**3 条有意保留**（探针脚手架重复、
5 元位置数组的向量表、`surface-bordered` 的名字）。逐条处置见
[`issues/06-debt-and-closeout.md`](issues/06-debt-and-closeout.md) 的「双轴评审处置」表。

## 本轮的三处用户可见变化

1. 三条被 `opacity` 压到 AA 以下的文字变清楚（`.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`）。
2. 浅色主题里「固定/电源」焊盘从**近黑**变成与「空闲 IO」焊盘一套的浅灰。
3. 两笔债有了明账（无观感变化，但下一轮不必重新发现）。

## 仍开着的（去向写清）

- ✅ **`.role-type` 角色类型标浅色 3.54**（暗 4.94）：模板变量拼出来的内联取色，腿⑨ 认不到——
  **那一族的文字色从没被任何对比度判据看过**。**2026-10-01 已收**（`pin-type-contrast` 一批：
  取色还给样式块 + 腿⑨ 正向判据「内联 `style` 里不许模板变量拼取色」+ 八族两主题成套
  + 腿⑪「颜色族的亮色覆盖必须成套」；读数见 `.scratch/pin-type-contrast/README.md`）。
- **叠加态定价**（浅 3.42 / 暗 3.11）与 **`--accent` 非文字 3:1**（2.70）：明账，**不收**（理由在守卫注释）。
- ✅ **亮色覆盖完整性立腿**：**2026-10-01 已立腿⑪**（颜色族必须两主题成套 + 豁免登记表双向对账，
  今天盘上唯一判红面 `--pin-*` 已由同批 03 单修完成套）。
- ~~**发版**：本批未发版。~~ ✅ **已发 v1.4.3**（2026-10-01；八件套上线、8/8 对账、联网自检 PASS，
  账本在 `.scratch/release-v1.4.3/`）。⚠ 其后 `main` 上另有 `pin-type-contrast` 一批（**未发版**）。
- 等人的四单不变（`hwcheck-acceptance/05` / `hwcheck-hardening/08` / `identity-fields/06` / `real-acceptance/01`）。
