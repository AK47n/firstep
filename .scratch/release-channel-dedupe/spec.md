# spec — 发布通道公共件收回 update.py（release-channel-dedupe）

## 问题陈述

应用里有**三条**发布/更新通道：小发版（`update.py`）、完整包（`full_update.py`）、资料库
（`materials_update.py`）。三条的**载荷形状确实不同**（小发版四件套 / 分卷表 / 批次差异），
但它们在做的**机制**是同一件事，而这份机制被抄了多份：

- 按资产名取下载地址（`_asset_url`）：完整包与资料库两个模块里**逐字两份**。
- 清单资产名定位（`_manifest_asset_url`）：两份（各自拼名后调上面的取址）。
- 找"版本最大的 release"：两份近乎相同的循环（只差一个过滤谓词与"取来比较的版本串"），
  各自带一遍"版本号非法就降级字符串比较"的兜底。
- 版本比较降级兜底（`(b > a) - (b < a)` 那类写法）：收走前**5 处**，散在三个模块里。
- GitHub HTTP 面：资料库模块的 `_fetch_releases` / `_fetch_text` 与小发版模块的
  `http_json` / `http_text` 是同一套 urllib 实现——**而完整包模块直接 import 资料库模块的
  私有名**（连列表端点也是函数内 import 的）：两个功能模块早就是"同一个模块"，
  只是没人把这条缝画出来。
- `error` 码：`network` / `no-release` / `bad-manifest` 各定义一遍。**这不是内部细节**——
  前端的两个更新面板直接按这些字符串分支（`baseline-missing` / `network` / `no-release` /
  `bad-manifest` / `no-asset`），所以它们是**线上契约**，两边漂了就是静默改 UI 行为。
- 通道区分字面量（`materials-` 前缀）：完整包要按它排除、资料库要按它筛选、比较版本前还要剥它，
  而两个模块各定义了一份。

注意 `update.py` 里**已经有**这套公共件（`http_json` / `http_text` / `compare_versions` /
`normalize_version` / `MSG_BAD_VERSION`），所以这不是"要不要抽一个模块"，而是"公共件早就在了，
两个功能模块各自又写了一遍"。

## 方案

把"找 release / 取资产地址 / 版本比较降级 / 错误码"这四件**机制**收回 `update.py`（既有的共享
发布模块），三个功能各自只留"把自己的载荷翻译出来"的那层：

- 三条通道的**载荷形状、中文文案、reason 语义继续各写各的**（差异是真的，不参数化）。
- `full_update` 不再 import `materials_update` 的任何名字——跨功能私有依赖退场。
- 错误码单源，并由一条守卫把它与前端 switch 用的字面量对账（防静默漂移）。

对用户：**行为零变化**（同一个 release、同一份载荷、同一句中文），改变的是以后改发布通道只需
改一处。

## 用户故事

1. 作为维护者，我想让"按资产名取地址 / 找最新 release / 版本比较降级"只有一处实现，
   以便修一次三个通道都受益。
2. 作为维护者，我想让 `full_update` 不再 import `materials_update` 的私有名，
   以便依赖方向是画出来的缝而不是既成事实。
3. 作为维护者，我想让 `error` 码单源、并与前端按码分支的字面量对账，
   以便发布通道的错误语义漂移会在闸门里变红。
4. 作为维护者，我想让三条通道各自继续保留自己的载荷形状与中文文案，
   以便这次收敛不变成"为了共用而把三种东西塞进一个形状"。
5. 作为用户，我想让检查更新 / 完整包 / 资料库三个入口的提示与行为一字不变，
   以便感觉不到这次改动。
6. 作为维护者，我想让既有注入缝（`fetch_json` / `fetch_text`）与公开名保持可用，
   以便既有测试与端点是回归网而不是被一起重写。

## 实现决策

- **收敛到**：`update.py` 新增/成为单源的四件——`RELEASES_URL`（列表端点）、
  `asset_url(release, name)`、`latest_release(releases, matches, version_of=None)`、
  `compare_versions_or_text(a, b) -> (结果, 是否降级)`；另加通道区分字面量
  `MATERIALS_TAG_PREFIX`；错误码
  `ERROR_NETWORK` / `ERROR_NO_ASSET` / `ERROR_NO_RELEASE` / `ERROR_BAD_MANIFEST` 在 `update.py` 定义。
- **`version_of` 是必需参数不是投机抽象**：资料库 tag 形如 `materials-v1.1.0`，比较前必须剥前缀
  （不剥就退化成字符串比较，`v1.10.0` 会被判成小于 `v1.9.0`）；完整包用原始 tag。谓词与
  "取来比较的版本串"是三条通道仅有的两处差异，故都在调用侧注入。
- **降级比较按原样字符串**（不 normalize）：三条通道历史上各自按自己传进来的形态比
  （小发版传归一化后的 latest、完整包传原始 tag、资料库传剥过前缀的版本串）。在这里统一
  normalize 会**把非法版本号下的判定方向翻过来**（`("1.0-Release", "1.0-beta")` 原样比 = 1，
  归一化后 = -1）——评审抓到的真回归，已由
  `tests/test_update_check.py::test_compare_versions_or_text_keeps_raw_string_fallback` 钉住。
- **各功能保留的适配器**（一行委托，不是重复实现）：`full_update.find_latest_full_release`
  （谓词 = 非 `materials-` 前缀）、`full_update.resolve_part_url`、
  `materials_update.find_latest_materials_release`（谓词 = `materials-` 前缀）、
  `materials_update._manifest_asset_url` 等——**既有公开名与测试导入面保持可用**。
- **错误码的既有导出面保留**：`full_update.ERROR_NETWORK` 等仍可导入，但值取自 `update.py`
  （守卫按 `is` 同一性钉住，防以后在功能模块里重新定义）。
- **HTTP 面**：实现（urllib / 请求头 / 超时 / UA）搬进 `update.py`（`http_json` / `http_text`），
  两个功能模块只留**一行的委托壳** `_fetch_releases` / `_fetch_text`。**壳是故意的**：
  它是端点的缺省注入缝，既有端点用例靠 `monkeypatch.setattr(fu, "_fetch_releases", …)`
  替换网络——实测把壳直接删掉会让 6 条端点用例红，那就该改判据而不是改测试。
  副作用：User-Agent 从 `firstep-materials-check` 变成 `firstep-update-check`
  （同一种请求头，行为无差）——如实记账。
- **与 `CONTEXT.md` 既有先例的关系**：条目库原语那条写过「库的 StoreError 翻译骨架不参数化
  共享——参数化劣于清晰重复」，本条不与之冲突：那条的差异是**领域语义**（各库错误类型与文案），
  本条的差异只在**载荷**，收敛的是机制（取址 / 找最新 / 比较降级 / 错误码），而
  `full_update` 已经在 import `materials_update` 的私有名——证明两侧实际同源。
- **不动**：`tools/update-app.py`（独立进程的更新器，自己解析清单，属另一条路径）、
  三条通道的载荷字段、`reason` 取值、中文文案、前端任何代码。

## 测试决策

- **回归网 = 既有测试**：`tests/test_full_update.py` / `tests/test_materials_update.py` /
  `tests/test_update_check.py` 用注入的假 fetch 覆盖全部错误分支与载荷字段，
  本次**不改它们的断言**（只允许改 import 路径，若有必要）。先例：这三个文件本身就是契约测试。
- **新增结构钉**（照 `tests/test_hwcheck_assembly_home.py` 与 `tests/test_llm_run.py` 的先例）：
  一份 `tests/test_release_channel_home.py`，判的是**边界与契约**（不是载荷行为）：
  1. 机制与通道字面量只在 `update.py` 定义：`asset_url` / `latest_release` /
     `compare_versions_or_text` / `http_json` / `http_text` 不在功能模块重新定义；
     `MATERIALS_TAG_PREFIX` 不在功能模块重新赋值；两个模块不 `import urllib`；
     不再出现版本比较降级 idiom（形状型判据，带自己的合成红证）；
  2. `full_update` 不再 `from .materials_update import …`（跨功能私有依赖退场）；
  3. 两边导出的错误码与 `update.py` 的**同一对象**（`is` 判据，防重新定义漂移），
     列表端点 `RELEASES_URL` 同一个常量；
  4. 前端按码分支的字面量（从两个更新面板里抽 `error === "…"`）必须都在后端声明的码集合内
     ——**跨语言契约对账**，先例 `test_library_invariants.py` 的 JS 词表镜像守卫；
  5. **守卫不是摆设**：每条判据都喂合成片段证明它能红（先例 `test_hwcheck_assembly_home.py`），
     另有真红证探针把收走前的三个模块喂进同一套判据。
- **保留注入缝**：`_fetch_releases` / `_fetch_text` 以一行委托壳留在两个功能模块里——
  端点的缺省路径与 6 条既有端点用例靠 patch 它们替换网络，这是**既有测试面**，不动。
- **不测**：不写"某个函数在第几行"这类实现细节断言。

## 范围外

- 三条通道**载荷形状统一**（差异是真的，不做）。
- `tools/update-app.py` 的清单解析（独立更新的自家路径，另议）。
- 下载 / 重试 / 应用链路（`download_resume` / `task_download` / `full_task` / `materials_task`）——
  已共享原语，本次不动。
- `full_apply` / `materials_apply` 的差异（进程内 vs 拉起更新器，是**真实差异**，不做）。

## 补充说明

- 来源：架构评审报告（副本入库 `.scratch/ui-dom-contract-gate/architecture-review-20260920-1745.html`）
  复审结论里的 C4，`backlog.md` 第 11 节记着"仍挂账，未立项"。
- 判据口径：本条的验收不是"重复行数变少"，而是**同一机制只有一处定义 + 前端契约有守卫 +
  既有三个测试文件零断言改动**。
