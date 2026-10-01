# release-v1.4.2 —— 发版收口（小发版 + 完整包）

> 立项 2026-10-01。上游：`main` 上**一批**未发布的改动 —— `disabled-forms`（01–03，全 resolved；
> 本轮**无代码改动**，纯样式 + 属性 + 守卫/文档）。
> 版本号用户已拍板 = **v1.4.2**（修订号 +1：三处形态的对比度修复，无新增功能、无破坏性变更）。
> 流程照 `docs/agents/releasing.md`（三处版本号同步 → preflight → 门禁三连 → 打包 → tag/推送 →
> Release → 联网自检 → 账）。

## 这一版带走的（用户可见影响）

| 批次 | 用户可见影响 |
|---|---|
| `disabled-forms/01` | **三处「不可选」形态的样子变了**：`.module-card.off`（需切换平台）/ `.pin-menu-list li.cant`（不兼容行）/ `.param-stale`（位置已变）从整块 `opacity` 改成**灰底灰字 + 虚线描边**；off 卡加 `aria-disabled="true"`（读屏念「不可用」）；引脚菜单不可绑行加禁止光标 |
| `disabled-forms/02` | 无（真像素量具与读数：46 格变好 40 / 没变 6 / 变差 0） |
| `disabled-forms/03` | 无（守卫登记表 + 文档回改；盘上再出现「用变淡表达不可选」当场红） |

**发布说明要点名的那句**（用户交接要求）：**不可选形态三处（需切换平台的模块卡、引脚菜单里不兼容的行、
锚失效的参数卡）的样子变了**——见 `release-notes-v1.4.2.md` 第一条。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `issues/01-version-sync-and-selfcheck.md` | 三处版本号同步 + `preflight.ps1` + 版本相关单测 |
| `issues/02-pack-and-publish.md` | 门禁三连 → 打包（更新包 + 完整包）→ 打 tag 推送 → Release 上传 → 联网自检 |
| `issues/03-ledger-and-handoff.md` | 账：`local-environment.md` §0 / `backlog.md` §33④ / 上游工单状态 |
| `release-notes-v1.4.2.md` | Release 说明定稿（上传用的就是这一份） |

## 读数（发版那一刻）

见 `issues/02-pack-and-publish.md` 文末的读数表（门禁三连 / 打包体积 / sha256 / 上传件数 / 联网自检）。
