# 02 — 用户侧：完整包检查端点（含双轨判定）

**要做什么：** 用户在设置页能问「有没有完整包更新 / 我该下哪个」：后端读取本地已装完整包版本与线上最新完整包清单，给出「当前版本 → 最新版本、总量、分卷表、是否可下」，并在网络 / 无资产 / 清单损坏等情况下给中文提示而不是报错。同时，资料库检查在**本地缺基线**时明确标记「需要完整包」，让前端能把主按钮切成「一键下载完整 firstep」，而不是只显示一句文字指引。

**被谁阻塞：** 01（完整包清单契约）

**状态：** resolved

- [x] 新端点契约落地：`GET /api/update/full/check` →
      `{current_version, latest_version, update_available, total_bytes, parts: [{name, size, sha256, url}], reason, error, message}`
- [x] 线上取源：从 GitHub releases 列表按软件 tag 前缀过滤取最新版，再取该 Release 的完整包清单资产（注入 fetch 可测，不碰网络）
- [x] 本地已装版本：读用户数据目录下的已装标记（缺失 = 未知）；全新机器首次检查时提示可下载完整包而不是报错
- [x] 四态均有断言：有新完整包（`update_available=true` + 总量与分卷表） / 已是最新（提示无需下载，仍允许主动重下） / 该 Release 无完整包资产（中文提示） / 网络不可达（中文提示，不 500）
- [x] 清单解析失败、版本号非法、分卷表为空：一律 200 级 + 中文 `message`，不抛异常
- [x] `reason` 明确区分「无基线 / 主动重下 / 有新版本」，供前端决定文案
- [x] 资料库检查端点在缺基线时带上「需要完整包」标记（既有响应字段向后兼容，不破坏现有前端与测试）
- [x] 全部下载地址为绝对 URL 且文件名与清单一致（防下载端拼错）
- [x] 端点测试：注入假 fetch 覆盖上述全部状态；既有资料库检查测试保持全绿

## 实施记录（2026-09-13）

**实现面**
- 新增 `src/contest_generator/full_update.py`：`full_manifest_asset_name`、`load_installed_marker`（缺失/损坏/空值 = None）、`find_latest_full_release`（过滤 `materials-` 前缀 + 版本最大）、`resolve_part_url`、`check_for_full_update`；HTTP 面复用 `materials_update` 的 `_fetch_releases` / `_fetch_text`（同一仓库、同一超时与 UA 策略，不重复实现）。
- `webapp.py` 新增 `GET /api/update/full/check`（薄调：已装标记来自 `context.config_path.parent / "updates"`）。
- 测试 `tests/test_full_update.py` 19 例（19 passed）。

**双轨判定的落点（有意简化）**
- 资料库检查在缺基线时回的 `error == "baseline-missing"` **已经就是**「需要完整包」的标记，前端既有代码就在读它；本工单**不再往该响应里加字段**（避免动一个已被多处消费的契约），双轨选路由前端按该标记分流。原验收项「带上标记、向后兼容」按此口径满足。

**额外收获**
- 「清单列了分卷但 Release 上没有该资产」原本会给出空 URL 让前端拼出死链，现改为整体判 `no-asset` + 中文提示（专项测试钉住）。

**真机验证**
- 对**真实 GitHub API** 跑一次端点：正确地认出最新软件 Release `v1.0.0`、发现它没有完整包资产，返回 200 级中文提示「该版本的 Release 上没有完整包资产，请联系发布者」——发布侧链路尚未发过完整包，故 `no-asset` 正是当前应有的答案；不 500、不抛异常。
