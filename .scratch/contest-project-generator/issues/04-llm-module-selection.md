# 04 — LLM 赛题→模块选择 + 依赖解析 + 配置

**What to build:** 用户粘贴赛题后，系统调用可配置的 AI（默认 DeepSeek），基于模块库清单选出推荐模块并附理由，递归带上依赖模块；用户可在生成前增删选择。API 配置存本机。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座

**Status:** resolved

- [x] LLM 客户端抽象为协议：生产实现调用 DeepSeek（base_url / key / 模型可配置，存本机配置文件，不入版本库）；测试注入固定返回的假实现
- [x] 赛题 + 模块库 manifest 摘要 → 结构化输出：推荐模块列表 + 每条理由
- [x] 依赖解析：按 manifest 递归带入依赖模块，无环
- [x] 平台警告：推荐模块缺少目标平台版本时输出两类提示——"未验证"与"硬件绑定"
- [x] 选择结果可在生成前由用户增删

## Comments

- 2026-08-05: 工单 04 完成。`llm.py` 补上生产实现 DeepSeekLLM（base_url/api_key/模型来自 `config.py` 的本机配置文件 `~/.contest_generator/config.json`，版本库之外；HTTP 传输可注入，测试用 FakeTransport 假件，网络不进测试）。`selection.py` 新增两个纯函数：`resolve_dependencies`（按 manifest 递归展开依赖、环检测带路径、未知 slug 报错）与 `check_platform_warnings`（缺版本 / 未验证 / 硬件绑定三类警告，增删选择后重跑即可，为工单 09 的编辑 UI 留好入口）。
- 对工单清单的两处偏差，均以 spec.md 为准并已在代码注释说明：① 平台警告做成三类而非两类——"缺版本"（missing，对应 US8"缺少目标平台版本时收到明确警告"）之外的"未验证"与"硬件绑定"正是工单说的两类风险提示；② `ModuleSelection` 的"已按依赖递归展开"文档改为"AI 原始推荐"——AI 输出后用户还会增删（清单第 5 项），展开必须在最终选择上做，契约由 `selection.py` 流程承接。
- 测试：新增 tests/test_config.py（8 例）、test_llm.py（17 例）、test_selection.py（15 例），全量 113 通过。
