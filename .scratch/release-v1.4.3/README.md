# release-v1.4.3 —— 发版收口（小发版 + 完整包）

> 立项 2026-10-01。上游：`main` 上**一批**未发布的改动 —— `contrast-residue`（01–06，全 resolved）。
> 版本号用户拍板 = **v1.4.3**（照 `releasing.md` 的 SemVer 表：小修小补 → 修订号 +1；先例 v1.4.2 / v1.4.1）。
> 流程照 `docs/agents/releasing.md`（三处版本号同步 → preflight → 门禁三连 → 沙箱验收 → 打包 →
> tag/推送 → Release → 联网自检 → 账）。

## 这一版带走的（用户可见影响）

| 批次 | 用户可见影响 |
|---|---|
| `contrast-residue/01` | 无（令牌解析面扩到全部 `:root` 块；新解出 19 个令牌，读数口径变准） |
| `contrast-residue/02` | 无（`.pin-subtitle` 的 `var(--fg)` 笔误修掉——浏览器本来就按 `inherit` 渲染，观感零变化） |
| `contrast-residue/03` | **浅色主题板图「固定/电源」焊盘换色**：近黑 `rgb(23,27,33)` → 与「空闲 IO」一套的浅灰 `rgb(175,184,193)`；暗色不变 |
| `contrast-residue/04` | **三条被 `opacity` 压到 AA 以下的文字变清楚**：`.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`——浅 3.52 / 4.18 → **5.25 / 5.72**，暗 4.10 / 3.91 → **5.67 / 4.85** |
| `contrast-residue/05` | 无（`.pin-menu-list li.cant` 真像素取证：整行浅 5.25 / 暗 5.67） |
| `contrast-residue/06` | 无（两笔明账进守卫注释；台账与交接区回改） |

**发布说明要点名的两句**：**三条话变清楚了** ＋ **浅色主题「固定/电源」焊盘换色**——
见 `release-notes-v1.4.3.md` 前两条。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `spec.md` | 拍板记录（版本号 / 范围外 / 沙箱口径）与范围边界 |
| `issues/01-version-sync-and-selfcheck.md` | 三处版本号同步 ＋ `preflight.ps1` ＋ 版本相关单测 |
| `issues/02-gates-and-readings.md` | 门禁三连（浏览器单独跑）＋ 对比度冻结读数 ＋ 全站不退化 |
| `issues/03-sandbox-acceptance.md` | 沙箱「模拟用户机」重造 ＋ 真 Chromium 验收 ＋ 回写第 1 节 |
| `issues/04-pack-and-publish.md` | 打包（更新包 ＋ 完整包）→ tag/推送 → Release → 八件对账 → 联网自检 |
| `issues/05-post-publish-and-ledger.md` | 发布后对账 ＋ 回改 `local-environment.md` §0/§1/§2/§3 ＋ `backlog.md` §34 |
| `release-notes-v1.4.3.md` | Release 说明定稿（上传用的就是这一份） |

## 读数（发版那一刻）

见 `issues/04-pack-and-publish.md` 文末的读数表（门禁三连 / 打包体积 / sha256 / 上传件数 / 联网自检）
与 `issues/03-sandbox-acceptance.md` 文末的真机验收表。
