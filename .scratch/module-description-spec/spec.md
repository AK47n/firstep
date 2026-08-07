Status: ready-for-agent

# 模块简介规范 — 三要素判据落地

## Problem Statement

模块库的简介无法支撑两个判断：**"能不能嵌入母版"**——简介没有套件/版本身份（哪个套件、哪个版本、去哪买），只有人能确认的硬件身份信息无处安放；**"该不该选它"**——逻辑绑定具体赛题的模块（如 2026C 数字钥匙题的锁逻辑）没有专用性标注，选模块 AI 可能把它推荐给别的赛题。同时，用户要能自己补写简介文本（套件名、题号等只有人知道的信息），但选模块 AI 必须**读得懂**这些信息、推荐时据此判断——现在喂给 AI 的候选清单只有 `- slug: 简介（依赖: ...）`，身份字段就算存在也不会被 AI 看到。

## Solution

简介判据三要素落地到机制里：

1. **与代码一致**（保留现有 AI 校验）
2. **硬件身份可确认**——manifest 平台条目新增 `kit`（套件/型号）+ `source_url`（购买链接）字段；新录入强制必填 + URL 格式校验；由人补填，AI 不猜
3. **专用性标注**——逻辑绑定具体赛题的模块，简介必须写明"XX 题专用"；选模块 AI 的候选摘要行带上 `kit`，让推荐读得懂身份与专用性

存量 6 个模块按新规范迁移：AI 出草稿 → 用户确认/补身份字段 → 专用性标注落进简介。

## User Stories

1. As an 电赛参赛者, I want to 录入新模块时填写套件型号（kit）, so that 库里的每个模块都有可确认的硬件身份
2. As an 电赛参赛者, I want to 录入新模块时填写购买链接（source_url）, so that 我能通过链接确认到底是哪个版本
3. As an 电赛参赛者, I want to 链接格式非法的 source_url 在入库时被拒绝, so that 库里不会有笔误和死链接
4. As an 电赛参赛者, I want to 身份字段由我填写而 AI 不猜, so that 硬件身份永远是人确认过的事实
5. As an 电赛参赛者, I want to 存量没有身份字段的模块仍能正常读取和展示, so that 迁移不打断现有库
6. As an 电赛参赛者, I want to 给存量模块的平台条目补填 kit 和 source_url, so that 旧模块也能逐步达标
7. As an 电赛参赛者, I want to 选模块 AI 的候选清单里能看到每个模块的套件信息, so that AI 推荐时能分辨"哪个套件的 UWB"并据此判断
8. As an 电赛参赛者, I want to 逻辑绑定具体赛题的模块在简介中写明"XX 题专用", so that 我和 AI 都不会把它选给别的赛题
9. As an 电赛参赛者, I want to AI 一致性校验能发现"简介声称题专用但代码看不出"的矛盾, so that 简介声明保持可信
10. As an 电赛参赛者, I want to 选模块 AI 能理解简介中的赛题专用性并据此推荐, so that 2026C 的锁逻辑不会被推荐给巡线题
11. As an 电赛参赛者, I want to 按新规范重写存量 6 个模块的简介（AI 草稿 + 我确认 + 我补身份）, so that 全库简介达标
12. As an 电赛参赛者, I want to 编辑模块身份字段时不走 AI 一致性校验（身份是事实，AI 判不了真假）, so that 改错能立即发现但不被无谓拦截
13. As an 电赛参赛者, I want to 模块列表数据里能看到每个模块的套件与链接, so that 浏览时一眼确认身份（页面装配归端到端工单）

## Implementation Decisions

- **manifest.py**：`PlatformEntry` 增加 `kit: str = ""` 与 `source_url: str = ""`。`from_dict` 容忍缺省（存量 manifest 无此字段仍能加载），类型非字符串抛 `ManifestError`；`to_dict` 序列化新字段。
- **library.py 写入强制**：`add_module` / `add_platform_files` 对**新增平台条目**强制——`kit` 非空、`source_url` 非空且 URL 格式（scheme + host 的简单校验）；不满足抛 `LibraryError` 带中文说明，**不落盘**（沿用"任何校验失败都在落盘前"不变量）。存量条目的补填走结构编辑路径，只做格式校验、不做 AI 一致性校验——身份是事实信息，AI 判不了真假。
- **llm.py 摘要行扩展**：`build_manifest_summaries` 行格式改为 `- slug: description（套件: kit; 依赖: ...）`，让选模块 AI 读到套件身份；`_summary_slugs` 反向解析必须同步（两处格式耦合，改动须同步）。`source_url` 不进摘要行（供人工核对，避免 prompt 膨胀）。
- **一致性校验提示词**：`_validation_user_prompt` 补充要求——简介中的"XX 题专用 / 出身"声明必须与代码可观察内容一致（简介称专用但代码是通用驱动 → 拒绝；代码明显是赛题专用逻辑但简介未标 → 提示补充）。
- **存量迁移**：机制复用现有 draft → validate → save 流程；身份字段走编辑路径补填。迁移清单（6 模块）与专用性标注建议：`lock_control`/`zone`→2026C 数字钥匙题专用、`pid`→巡线题专用、`filter`→出身 2026C 逻辑通用、`uwb_uart`→套件身份由用户填、`ml_mpu6050`/`motor`→通用驱动。最终标注由用户逐条确认。

## Testing Decisions

- **主缝 = 模块库服务层**（`library.py` + `manifest.py`），纯逻辑 + FakeLLM 注入，沿用 `tests/test_library.py`（47 例）与 `tests/fakes.py` 的既有模式。只测外部行为（错误信息、落盘与否、摘要行内容），不测实现细节。
  - manifest 新字段：序列化/反序列化往返、缺省兼容、类型错抛 `ManifestError`（`test_manifest.py` 先例）
  - `add_module` / `add_platform_files`：缺 kit/source_url → `LibraryError`；URL 非法 → `LibraryError`；拒绝后磁盘无残留
  - 存量条目编辑补填：成功写回、非法格式拒绝
- **llm.py**：摘要行新格式 + `_summary_slugs` 反向解析一致性（`test_llm.py`，FakeLLM 断言）；校验提示词扩展后，FakeLLM 下"简介称专用但代码通用"路径被拒绝
- **webapp**：新字段载荷透传 + 错误响应（`test_webapp.py`），薄层

## Out of Scope

- zone 补录（独立工单，源码在 2026C/code，恢复 lock_control 可用）
- uwb_uart 可选化（条件编译 + 生成器可选依赖机制；含普适 filter 将来方向）
- 母版 ml_i2c 注释 GBK→UTF-8 转码（小活）
- 模块页 UI 装配（列表/录入/编辑页面归端到端装配工单；本 spec 只保证 API/数据层可见）
- 选模块 AI 的推荐算法本身（只保证它读得到身份与专用性信息）
- 普适巡线逻辑（将来方向）

## Further Notes

- `build_manifest_summaries` 与 `_summary_slugs` 格式耦合，改格式必须两处同步（代码注释已有警告）。
- ADR 0005（`docs/adr/0005-module-library-description-spec.md`）已记录判据决策与功能库归属母版。
- 依赖方向已修：逐飞库（功能库）归属母版，模块 manifest 不得声明对其依赖；本 spec 的录入校验不涉及依赖机制。
- 存量 6 模块：`filter` / `lock_control` / `ml_mpu6050` / `motor` / `pid` / `uwb_uart`；`lock_control` 保留对 `zone` 的依赖，待补录后可用。
- 真机录入流程（真实 DeepSeek）已确立：草稿 → 用户确认 → 校验 → 入库；身份字段沿用该流程的"用户确认"步。
