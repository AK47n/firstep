# release-v1.4.1 —— 发版收口（小发版 + 完整包）

> 立项 2026-09-30。上游：`main` 上三批未发布的改动 —— `border-guard`（产品面零改动）、
> `light-contrast`（全站颜色，浅色为主）、`code-contrast`（**代码页语法色与高亮强度** + 禁用态）。
> 版本号用户已拍板 = **v1.4.1**（修订号 +1：小修小补，无新增功能）。
> 流程照 `docs/agents/releasing.md`（三处版本号同步 → preflight → 打包 → tag/推送 → Release → 联网自检 → 账）。

## 这一版带走的（用户可见影响）

| 批次 | 用户可见影响 |
|---|---|
| `border-guard` | **无**（纯内部：描边登记簿 + 跨语言镜像守卫） |
| `light-contrast` | 全站颜色（浅色为主）：浅色主题的正文 / 说明 / 五个语义色压到 AA 以上、卡片淡底加深；焦点环提到 3:1 以上；暗色只有几处实心块上的字 |
| `code-contrast` 01/02/04 | **代码页的语法色深浅与高亮强度变了**（十个语法色 × 两主题 × 七层底全部 ≥ 4.5；选区 `.32→.20`、当前命中 `.38→.24`） |
| `code-contrast` 03 | 禁用态从"整体变淡"改成**灰底灰字**（实测 2.06 → 5.25） |

## 文件索引

| 文件 | 是什么 |
|---|---|
| `issues/01-version-sync-and-selfcheck.md` | 三处版本号同步 + `preflight.ps1` + 版本相关单测 |
| `issues/02-pack-and-publish.md` | 打包（更新包 + 完整包）→ 打 tag 推送 → Release 上传 → 联网自检 |
| `issues/03-ledger-and-handoff.md` | 账：`local-environment.md` §0 / `backlog.md` / 本目录读数 |

## 读数（发版那一刻）

见 `issues/02-pack-and-publish.md` 文末的读数表（打包体积 / sha256 / 上传件数 / 联网自检）。
