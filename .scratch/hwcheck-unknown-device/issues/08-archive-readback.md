# 08 — 定义 / 资料 / 草稿归档 + 回读以快照为准

**要做什么：** 检测工程目录里留下**本次用到的自建件定义、资料副本与抽取草稿**；回读（刷新 / 点最近一次）**以工程内快照为准**，并标出它来自哪个「我的器件」条目。

**被谁阻塞：** 02（定义与资料落点）、03（生成链）

**状态：** resolved

- [x] 生成时把定义快照 + 资料副本 + 草稿写进工程目录（`custom_device/<id>/`），上下文清单记下本次用到的自建件 id
- [x] 回读：用户之后**改了或删了**「我的器件」，已生成工程的回读结果**不变**（用例：删掉数据目录里的定义再回读，计划仍完整）
- [x] 页面标出「来自我的器件 <id>」；该条目已不存在时如实说明（不静默、不报错）
- [x] 载荷向后兼容：没有自建件的旧工程，回读结果逐字与改动前一致
- [x] 归档文件本身**不进最近工程记录**那条赛题链路（检测工程不与赛题工作流互扰这条不变量不破）

---

## 结论（2026-09-23，工单 08 已 resolved）

### 一句话

检测工程第一次自带"档案"：生成成功后把本次用到的自建件**定义快照 + 资料副本 +
抽取草稿**复制进工程 `custom_device/<id>/`；回读**以工程内快照为准**——之后改 /
删「我的器件」都不影响已生成的工程，行上如实标「来自我的器件 <id>」（条目已删时
再补一句，不静默、不报错）。

### 一条需要记账的口径补全（资料 / 草稿的源头）

票面说"生成时把**资料副本 + 草稿**写进工程目录"，但 07 的草稿是**瞬态**的
（未确认前不落盘）。本单的补全：**用户确认保存时**，前端把资料原文与草稿随定义
发给保存端点（可选键 `material_text` / `draft`），`save_device` 把它们落进数据
条目（`materials/material.txt` / `draft.json`）——**幂等更新没再给就原样保留旧
的**（改个名字不抹掉"当时凭什么填了那个地址"）；生成时 `archive_custom_devices`
把数据条目整份复制进工程。判断：这是实现票面的**必要口径**，不是偏离——07 的
"草稿一律不落盘生效"指的是"存草稿不等于定义生效"，留档的正是"确认时随定义
留底的那份"，CONTEXT.md 那半句已加限定词。

### 交付物

| 落点 | 是什么 |
|---|---|
| `src/contest_generator/my_devices.py` | `save_device` 加可选 `material_text` / `draft`（给了就落盘、没给就 `_carry_over_provenance` 原样保留、**空白视同没给**——两态选一）；`MATERIAL_TEXT_FILENAME` / `DRAFT_FILENAME` 常量；`load_device_entry`（快照与数据目录共用同一条解析 + 校验） |
| `src/contest_generator/hwcheck_store.py` | `CUSTOM_DEVICE_DIRNAME`、`archive_custom_devices`（生成成功后整条目复制进工程；**定义不见了大声报错**；零自建件不建目录；id 先过文法再拼路径）、`read_custom_snapshots`（只收真有快照的；坏快照大声点名；文法不过的 id 直接跳过——id 从盘上清单进来，手改 `.contest_context.json` 即可控） |
| `src/contest_generator/hwcheck_board.py` | `hwcheck_view` 加 `custom_snapshot_dir`；`_custom_devices_for` 改返回 `(定义, 快照 id 集)`，**快照门只判自建件子集**（`mine_` 前缀）；计划行加 `snapshot` / `stored` 两个出处标记 |
| `src/contest_generator/webapp.py` | 生成端点在 `generate_project` 成功后调 `archive_custom_devices`（**只传 `view.custom_plan` 的 slug 集**）；回读端点传 `custom_snapshot_dir=path`；保存端点透传可选键；排障端点留 09 记账注释（它的重投影还没吃快照，09 动 triage 时带上） |
| `static/js/fx/hwcheck.js` | 计划行快照出处标记：「来自我的器件 <id>」+ 已删时补一句（现读行不画标） |
| `static/js/ui/hwcheck.js` | `saveMyDevice` 把 `myMaterial` / `myDraft` 随保存发出；`closeMyDeviceForm` / `openMyDeviceForm`（编辑分支）**清掉这两个状态**——不给下一件（尤其是编辑另一件）带走上一件的来源 |
| `tests/test_hwcheck_assembly_home.py` | import 白名单加 `archive_custom_devices`（落盘原语，与 `write_hwcheck_record` 同族；理由写在判据旁） |
| `tests/test_my_devices.py` +4 / `tests/test_hwcheck_store.py` +4 / `tests/test_my_devices_endpoint.py` +8 / `tests/js/hwcheck.test.mjs` +4 | 归档三样文件、空集不建目录、大声报错、快照读取、混选归档与回读、**改定义后回读仍是旧事实**、部分快照回退、零自建件顶层净空、保存透传、空白视同没给、前端标记三态、结构钉（表单切换清残留） |
| `.scratch/hwcheck-unknown-device/probe-08-guard-strength.py` / `.mjs` | 反证探针（4 条后端注入 + 1 条前端注入） |

### 验收读数（2026-09-23 冻结版）

**三门禁**：

```
python -m pytest -n auto -q                   5338 passed + 1 skipped / 140.6s（07 轮 5322 + 本单 16）
node --test "tests/js/*.test.mjs"             1768 passed / 0 fail（07 轮 1764 + 本单 4）
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"   38 passed / 0 fail
```

**判据强度（反证）**——后端 4 条注入（读数 `probe-08-guard-strength.txt`）：

```
注入 A: 回读不再吃工程内快照                   → RED ｜ 复原 sha256 相等 ✓
注入 B: 归档时定义不见了就静默跳过             → RED ｜ 复原 sha256 相等 ✓
注入 C: 幂等保存不再带走上一次的资料与草稿     → RED ｜ 复原 sha256 相等 ✓
注入 D: 生成后不再调用归档                     → RED ｜ 复原 sha256 相等 ✓
复原后复跑：四条全 PASS（回绿）；收尾指纹 4 个文件逐字节未变 ✓
```

前端 1 条注入（读数 `probe-08-guard-strength-front.txt`）：标记改弱 → 门禁红 3 条，
首条红即宣称的守卫；逐字节复原 ✓。

### code-review 两轴结论与整改

**Standards 轴**（2 红 + 4 黄 → 全修）：

1. 🔴 **混选时快照分支永不生效**（最重要的一条）：快照门按**全量选中集**判
   `all()`，库内件没有快照 → 只要同趟勾了任何一件库内器件（UI 里同一个选择池，
   常态用法），整体回退数据目录——票面核心验收只在纯自建件形态成立。
   **已修**：快照门只判 `mine_` 前缀的自建件子集；补混选回归用例
   （归档只含自建件 + 混选删定义后回读仍完整）。
2. 🔴 **前端残留状态跨件污染**：`closeMyDeviceForm` / `openMyDeviceForm` 不清
   `myMaterial` / `myDraft` → 给 A 抽了草稿后改编辑 B，保存会把 A 的资料 / 草稿
   写进 B 的条目。**已修**：收起与编辑分支都清这两个状态；补结构钉用例。
3. 🟡 部分快照零用例 → **已补**（两件删一件归档 → 整体回退数据目录，行上
   `snapshot=False` 如实标）。
4. 🟡 `read_custom_snapshots` / `archive_custom_devices` 绕过 id 文法唯一拼接点
   （读侧 id 来自盘上清单，手改清单即可控）→ **已修**：两个函数各自过
   `DEVICE_ID_PATTERN`（读侧跳过、归档侧大声报错）。
5. 🟡 `material_text=""` 静默删旧资料且与 draft 不对称 → **已修**：空白视同没给
   （保留旧资料），docstring 写明两态。
6. 🟡 排障端点没吃快照 → **判为本单不动、留 09**：票面只点了回读端点，09 本来
   就要动 triage；已在 webapp 留 ⚠ 记账注释（"别留两条口径"）。
   判断题：归档挂 guard 之外（判为正确——guard 管同键生成互斥）；rmtree→rename
   窗口加宽（既有模式的既有窗口，观察者侧原子性不变）；归档报错话术（重试本来
   就是生成新工程，语义成立）。

**Spec 轴**（无破票面 / 无蔓延；3 缺失 → 全补）：

1. 票面第 2 条「改了**或**删了」的"改了"半边无用例 → **已补**
   （`test_readback_uses_the_snapshot_even_when_the_definition_was_later_edited`）。
2. 票面第 4 条"逐字一致"无直接证据 → **已补结构面**（零自建件回读顶层不新增
   任何键 + 不建归档目录 + 既有回读用例全绿；`custom` 键自 05 起常驻、空集
   无处加键）。
3. "库内器件不进归档"无显式断言 → **已补**（混选用例断言
   `custom_device/led` 不存在）。
   另：口径补全（资料 / 草稿随保存落盘）已记账（见上），CONTEXT.md 措辞已加限定。

### 范围外 / 留给后面的工单

- **排障端点吃快照** = 工单 09（webapp 已留记账注释）。
- **未上板**：本单是归档与回读，没有真机动作；照 spec 口径写"未上板"，不假装。
- **实施时的一课（过程事实）**：本单曾在保存胶水里造成 JS 重名声明（`saved`
  撞既有声明），js 门禁跑在该编辑之前没抓到、浏览器门禁 38 条全败才暴露——
  **改 JS 后必须先跑 js 门禁再跑浏览器门禁**；另一次把库内器件传给归档函数，
  被既有用例当场抓红。两次都被既有闸门接住，记录在此防止下次误读为"产品坏了"。
