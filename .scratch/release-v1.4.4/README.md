# release-v1.4.4 —— 发版收口（小发版 + 完整包）

> 立项 2026-10-02。上游：`main` 上**一批**未发布的改动 —— `pin-type-contrast`（01–05，全 resolved）。
> 版本号用户拍板 = **v1.4.4**（照 `releasing.md` 的 SemVer 表：小修小补 → 修订号 +1；
> 先例 v1.4.3 / v1.4.2 / v1.4.1 三条对比度修复批）。
> 流程照 `docs/agents/releasing.md`（三处版本号同步 → preflight → 版本单测 → 门禁三连 → 打包 →
> tag/推送 → Release → 上传 → 八件对账 → 联网自检 → 账）。
> **本轮不跑沙箱真机验收**（用户拍板③；证据由本批真像素读数 ＋ 三套门禁承担）。

## 这一版带走的（用户可见影响）

| 批次 | 用户可见影响 |
|---|---|
| `pin-type-contrast/01` | 无（真像素基线与新量具：改前 121 格读数） |
| `pin-type-contrast/02` | 无（`PIN_TYPE_STYLE` → `PIN_TYPE_FAMILY` + `data-pin-family`；**逐格与基线逐位相同**） |
| `pin-type-contrast/03` | **浅色主题下引脚卡片配色变清楚**：类型标 / `已绑 / 现绑` 状态文字 / 板图上已绑引脚的名字 / 图例与菜单色点（spi / exti 1.45、i2c 1.40 → 文字最低 **4.70**、非文字最低 **3.76**）；**暗色只动 enc / uart**（文字档提亮一档） |
| `pin-type-contrast/04` | 无（新腿⑪：颜色族亮色覆盖必须成套；豁免表为空） |
| `pin-type-contrast/05` | 无（收口；改后真像素 **变好 77 / 没变 43 / 变差 0**） |

**发布说明要点名的一句**：**浅色主题下引脚卡片的配色变清楚了**——见 `release-notes-v1.4.4.md` 第一条。

## 文件索引

| 文件 | 是什么 |
|---|---|
| `spec.md` | 拍板记录（版本号 / 范围外 / 不跑沙箱）与范围边界 |
| `issues/01-version-sync-and-selfcheck.md` | 三处版本号同步 ＋ `preflight.ps1` ＋ 版本相关单测 |
| `issues/02-gates-and-readings.md` | 门禁三连（浏览器**单独跑**，三段串行） |
| `issues/03-pack-publish-and-ledger.md` | 打包（更新包 ＋ 完整包）→ tag/推送 → Release → 八件对账 → 联网自检 → 账 |
| `release-notes-v1.4.4.md` | Release 说明定稿（上传用的就是这一份；留档副本在 `firstep-pack\`） |
| `_bump_version.py` | 版本号同步施工脚本（锚点逐条断言命中 1 次） |
| `check-packs.py` / `verify-assets.py` | 包内抽检 / 服务端八件对账（都能复跑） |

## 读数（发版那一刻，2026-10-02）

| 项 | 值 | 落点 |
|---|---|---|
| 三处版本号同步 + `preflight` | 四项全绿（当前版本 v1.4.4） | `preflight-01.txt` |
| 版本相关单测 | **86 passed**（15.11 s） | `pytest-version-01.txt` |
| 门禁三连（本机现跑，三段串行） | 前端 **1848 / 0**（9.76 s）、浏览器 **61 / 0**（182.8 s，单独跑）、pytest **5695 passed + 11 skipped**（114.1 s） | `js-gate.txt` / `browser-gate.txt` / `pytest.txt` |
| 打包 | 更新包 **302,015,729 B**（288.0 MB，2939 产品文件 / 删除清单 2231 条）/ 完整包 **791,875,154 B**（755.2 MB，8212 文件 / 资料库 12 批次 5066 文件） | `pack-01-update.txt` / `pack-02-full.txt` |
| 包内抽检 | **全过**（版本块 v1.4.4 / `__version__ = 1.4.4` / 禁止面 0 / `00-START-HERE.txt` 在场 / 两个 sha256 实算一致） | `pack-03-inspect.txt` |
| 打 tag 时 pre-push 闸门 | 前端 **1848 / 0**、浏览器 **61 / 0**（182.3 s）、pytest **5695 passed + 11 skipped**（112.1 s） | `push-01.txt` |
| 八件对账 | **8 / 8 一致**（服务端 size 与本地逐件相同） | `verify-01-assets.txt` |
| 联网自检 | **PASS**（三组全 `[OK]`） | `post-publish-check.txt` |

**逐张单的结论与落地事实**在 `issues/01`–`03` 各自的文末；本表只放汇总指针。
