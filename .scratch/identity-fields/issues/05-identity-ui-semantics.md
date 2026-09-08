# 05 — 内部件/协议切片的身份字段 UI 语义

**要做什么：** 模块详情弹窗对内部件 / 协议切片不再显示两行空的「套件：」「来源：」
（现状让用户以为「待补」，实际语义是「无实物、不需要购买链接」）——判据单源
`library.MODULE_KIND` 已就位，本工单只做展示形态。

**被谁阻塞：** 01（判据单源）——已 resolved，可立即开始

**状态：** resolved

- [x] 先定措辞口径（本工单 Comments 记录用户裁决）：隐藏两行 vs 显示「无需购买链接
      （内部件）」——两种都行，但必须与 `MODULE_KIND` 同源取判据
- [x] `fx/module.js` 详情渲染按判据分支（前端无法 import Python 常量——沿用既有
      「同构镜像 + 跨语言同步测试」先例，如 `fx/module.js` 的 wiki 前缀镜像）
- [x] 后端列表载荷带上判据（`/api/library` 每条带 kind 或 `requires_identity`），
      避免前端再写一份 slug 名单（**判据仍单源**）
- [x] 测试：内部件/协议切片条目在载荷里标为「无身份字段语义」、器件条目标为「可补填」；
      前端渲染函数的纯函数单测
- [x] 若涉及 UI 渲染改动：`stop-firstep` + `start-app` 重启 4003 后验证（端口 4003
      `PYTHONPATH=src` 直跑，uvicorn 不带 reload）

## Comments

- 为什么单独开工单：本工单改动 manifest 渲染 / 前端 / 后端载荷三处，与
  identity-fields 主线的「库数据 + 判据 + 测试」正交；且措辞口径需要用户拍板。
- 用户故事出处：spec「用户故事 9」与「问题陈述 1」（详情弹窗两行空内容）。

### 措辞裁决（用户 2026 选定：隐藏空行 + 单条豁免标注）

内部件 / 协议切片的平台区块**不显示**「套件：」与来源链接两行（它们没有实物，
显示空行会被读成「待补」），改为一条灰字标注：

- 内部件 → `无需购买链接（内部件）`
- 协议切片 → `无需购买链接（协议切片）`

器件侧语义不变：有 `kit` / `source_url` 才显示「套件：」/「来源（立创 wiki）」
「购买链接」；**器件缺字段（待补）同样不渲染空行**，也**不误标豁免**（缺口由
测试与审计脚本报，不在 UI 里用一句「无需购买」把缺口说成正常）。

### 实现（判据单源不变）

- **后端载荷投影**：`GET /api/modules` 每条加 `kind`（`device` / `internal` /
  `protocol`，取 `library.module_kind(slug).value`）与 `requires_identity`
  （`library.requires_identity(slug)`）——判据仍在 `library.MODULE_KIND`，
  webapp 只做投影，前端不写 slug 名单。
- **前端分支**：`fx/module.js` 新增 `moduleRequiresIdentity(m)`（旧载荷无字段 =
  保守按器件，行为与改动前逐字一致）与 `identityExemptLabel(kind)`；
  `moduleInfoHTML` 按前者决定是否渲染套件 / 来源行，非器件渲染豁免标注。
- **跨语言镜像守卫**：`tests/test_library_invariants.py::test_js_module_kind_vocabulary_mirrors_python_enum`
  ——单源里每个 `ModuleKind` 值必须出现在 `fx/module.js`（照 `test_lckfb_attribution.py`
  的 wiki 前缀镜像先例；改任一侧即红）。

### 验证

- Python：`tests/test_webapp.py::test_modules_list_carries_module_kind_for_identity_semantics`
  （载荷投影与单源逐条一致 + `delay` = internal / `dht11` = device）；
  `tests/test_library_invariants.py` 新增镜像守卫；全量 **3892 passed**。
- JS：`tests/js/module-info-dialog.test.mjs` 新增 6 组（内部件 / 协议切片 /
  器件有值 / 器件待补 / 旧载荷 / 真实 slug delay）；`node --test "tests/js/*.test.mjs"`
  全量 **1364 passed**。
- 实况：本机起服务探活 `GET /api/modules`（uvicorn 无 reload）→
  `delay kind=internal requires_identity=false`、`zigbee_link kind=device
  requires_identity=true` + kit / source_url 已回填（探测后已停服，8000 端口无残留）。
  未做浏览器截图：本机无 CDP 调试端口在听（9251 无监听），纯函数单测 + 载荷契约
  已覆盖渲染分支；前端为静态文件改动，无需重建。
