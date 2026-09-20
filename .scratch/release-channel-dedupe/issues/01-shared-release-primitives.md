# 01 — 发布通道公共件收回 update.py（机制一处定义 + 前端错误码契约守卫）

**要做什么：** 三条发布通道（小发版 / 完整包 / 资料库）继续各自给出自己的载荷与中文文案，
但"找 release / 取资产地址 / 版本比较降级 / 错误码"这四件机制**只有一处定义**（`update.py`）；
`full_update` 不再 import `materials_update` 的私有名；前端按 `error` 码分支的字面量由守卫
与后端对账。对用户：三个入口的提示与行为一字不变。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

## 验收标准

- [x] `update.py` 成为单源：`RELEASES_URL` / `asset_url` / `latest_release` /
      `compare_versions_or_text` / 四个错误码（`network` / `no-asset` / `no-release` / `bad-manifest`）
      只在此定义；通道区分字面量 `MATERIALS_TAG_PREFIX` 亦收于此（评审整改 ③）
- [x] `full_update.py` / `materials_update.py` **不再实现** HTTP 面与取址机制：
      `_asset_url` 直接退场（改用 `update.asset_url`）；`_fetch_releases` / `_fetch_text`
      **保留为一行的委托壳**（实现搬进 `update.py`）——壳是端点的缺省注入缝，
      既有 6 条端点用例靠 patch 它替换网络（见下方「判据更正」）
- [x] 源码级可见的机制重复归零：两个模块不再 `import urllib`、
      不再出现版本比较降级 idiom（`(b > a) - (b < a)` 那类写法）
- [x] `full_update.py` **不再出现** `from .materials_update import …`（含函数内 import `RELEASES_URL`）
- [x] 既有公开名与导入面保持可用：`find_latest_full_release` / `resolve_part_url` /
      `full_manifest_asset_name` / `load_installed_marker` /
      `find_latest_materials_release` / `load_local_manifest` / `materials_library_dir`
      与四个错误码（后者的值取自 `update.py`，`is` 同一对象）
- [x] `tests/test_full_update.py` / `tests/test_materials_update.py` **一行未动**；
      `tests/test_update_check.py` **只新增 22 行**（一个新用例 + 一个 import），既有断言零改动
- [x] 新增结构钉 `tests/test_release_channel_home.py`（5 用例）：① 机制与通道字面量只在
      `update.py` 定义（源码级：不重新定义机制函数 / 不重新赋值字面量 / 不 `import urllib` /
      无降级 idiom）；② `full_update` 不 import `materials_update`；③ 错误码与 `RELEASES_URL`
      同一对象（`is`）；④ 前端 `error === "…"` 字面量 ⊆ 后端声明的码集合；⑤ 合成红证
- [x] 真红证留档：`.scratch/release-channel-dedupe/probe-01-pin-red-proof.py` + `red-proof.txt`
      （HEAD 版喂进同一套判据 → 6 条违规；当前树 → 0 条）
- [x] `python -m pytest -n auto -q` **5048 passed / 1 skipped**；
      `node --test "tests/js/*.test.mjs"` **1715 passed**（前端未改，回归确认）
- [x] 未改动：三条通道的载荷字段 / `reason` 取值 / 中文文案 / 前端任何代码 /
      `tools/update-app.py`（载荷形状抽样实测：11 / 8 / 7 个键，与各自契约一致）

## Comments

### 2026-09-20 双轴评审整改（规范轴 6 条，全部处理）

- **① 真行为回归（最该修）**：`compare_versions_or_text` 初版在字符串兜底前先 `normalize`，
  而三条通道历史上各自按**传进来的原样**比（小发版传归一化后的 latest、完整包传原始 tag、
  资料库传剥过前缀的版本串）。统一 normalize 会**翻掉非法版本号下的判定方向**——
  实证 `("1.0-Release", "1.0-beta")`：原样比 = 1（有更新），归一化后 = -1（无更新）。
  已改回按原样字符串比，并补回归用例
  `tests/test_update_check.py::test_compare_versions_or_text_keeps_raw_string_fallback`。
- **② spec 自相矛盾 + 易腐内容**：spec/工单里一度同时写着"不再定义 `_fetch_*`"与"壳是故意的"。
  已统一为"**不再实现**（壳保留 = 端点注入缝）"，并删掉 spec 里的行号与代码片段
  （`workflow.md:33`：路径/片段易腐），机制清单改成写签名与语义。
- **③ 漏收一个字面量**：`MATERIALS_TAG_PREFIX = "materials-"` 原先在两个功能模块各一份
  （正是区分两条通道的那个串）。已收进 `update.py`，结构钉与红证探针都覆盖它。
- **④ 壳外套壳**：`fetch_text = lambda url: _fetch_text(url)` 多包了一层；改回 `= _fetch_text`
  （同样吃 patch，与迁走前的写法一致）。
- **⑤ 形状型判据的假绿风险**：`version_fallback_sites` 是正则数 idiom，排版一变可能静默空转——
  已给它补合成红证（`test_pin_is_not_vacuous` 里三条：旧 idiom 数得出、调共享函数数不出），
  并在注释里标明它是形状型判据。
- **⑥ 与 `CONTEXT.md`「参数化劣于清晰重复」的关系**：评审确认本条的"不冲突"主张站得住
  （那条管**领域语义**：各库错误类型与文案；本条收的是**机制**，且 `full_update` 早已 import
  `materials_update` 私有名 = 机制同源实证）。唯一的参数化味道是 `latest_release` 的
  `version_of` 第三参——但它是**必需**的（资料库 tag 要先剥前缀，否则 `v1.10.0` 会被判成
  小于 `v1.9.0`），已把三参签名写进 spec 并说明理由。

### 已知限制（如实记账）

- push 闸门按"同名测试"映射：改 `full_update.py` / `materials_update.py` 时本地子集只跑各自的
  同名测试，**不会**自动跑本钉（新钉文件名与被守模块不同名）。改 `update.py` 会倒向整套（无同名
  测试），CI 也跑全套——所以这条不变量的兜底在 CI，不在本地子集。

## 注

- User-Agent 由 `firstep-materials-check` 变为 `firstep-update-check`（同一种请求头，
  行为无差）——如实记账在 spec 与提交信息里。
- **判据更正（本单实施中实测）**：初稿的验收标准写的是"`_fetch_releases` / `_fetch_text`
  不再定义"。真做下去发现 6 条端点用例正是靠 `monkeypatch.setattr(fu, "_fetch_releases", …)`
  替换网络的——**该改的是判据不是测试**：壳保留（一行委托），判据改成"实现只在 `update.py`"
  （源码级：不 `import urllib`、无降级 idiom、机制函数不在功能模块重新定义）。
