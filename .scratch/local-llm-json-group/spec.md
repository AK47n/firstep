# 本地 JSON 组解锁：剥围栏 + 扩本地组（local-llm-json-group）

## Problem Statement

本地 7B 模型的「围栏包 JSON」格式漂移把整个 JSON 组卡死：输出被 ```` ```json ````
包裹，项目严格解析器（`json.loads` 直读）不接受，失败重试仍失败、大声抛错。
few-shot 实验（`.scratch/local-llm-spike/probe-fewshot.py`）证明 few-shot **只能
减速、不能根治**——漂移是随机的（clarify 带示例两轮 3/3→2/3、validate 带贴合
示例 2/3），模型同一提示词时好时坏。既有重试能兜底大部分，但 validate 这类
1/3 成功率的调用有小概率 5 连败硬挂。格式障碍不除，澄清 / 简介校验 / 归档判定
等调用就无法安全转本地。

## Solution

1. **解析层剥围栏（确定性根治）**：json_mode 接缝单点剥掉 ```` ``` ```` 外层围栏。
   围栏问题从此消失，与模型心情无关；对 DeepSeek 零影响（从不包围栏，剥 = no-op）。
2. **扩本地组（3 → 6）**：格式障碍移除后，把 spike 已验证内容合理的
   clarify / validate_module_description / reference_judge_archivable 加进本地
   方法集——更多调用不花 API 钱。

## User Stories

1. As 用户，I want 本地模型输出被 ```` ```json ```` 围栏包裹时工具仍能正确解析，so that JSON 调用不被格式漂移卡死。
2. As 用户，I want 澄清 / 简介一致性校验 / 归档判定走本地，so that 更多调用不花 API 钱。
3. As 用户，I want 模块推荐 / 提炼判定 / 编译修复 / 骨架生成仍走 DeepSeek，so that 质量不受 7B 能力上限拖累。
4. As 用户，I want 剥围栏对 DeepSeek 路径零影响，so that 现有云端行为逐字节不变。
5. As 用户，I want 某个新转本地的调用真机表现不佳时能容易退回 DeepSeek，so that 方法集可调。

## Implementation Decisions

- **`_unwrap_json_fence(content)` 辅助**（llm.py，唯一出处）：仅当整个输出就是
  一个 Markdown 代码围栏块（开头 ```` ``` ```` 或 ```` ```json ```` 等 + 结尾
  ```` ``` ````）时剥掉外层，返回内部 JSON 文本；非围栏 / 只有开头没结尾 /
  内部含围栏的内容一律原样返回（绝不错伤合法内容）。剥完仍不是 JSON → 交给
  既有 `_retry_parse` / `_retry_batch` 重试兜底。
- **应用点 = `DeepSeekLLM._chat` 的 json_mode=True 分支**：返回 content 前先
  `_unwrap_json_fence`——单点覆盖全部 json_mode 调用（含既有与将来）；文本模式
  调用（json_mode=False）输出原样不动（骨架 ```c 围栏等合法内容不被 mangle）。
- **`LOCAL_LLM_METHODS` 3 → 6**：+clarify / validate_module_description /
  reference_judge_archivable（spike 验证：clarify 内容合理、validate 判定合理、
  归档判定为简单二值判断）。`_delegate` 读常量派发不变，扩集合即扩派发。
- **保持远程**：select_modules / generate_main_skeleton / generate_smoke_main /
  fix_compile_errors / distill_master / topic_split_topics / topic_extract_number
  ——能力上限（推荐/提炼/修复/骨架）或未 spike 验证（拆条/编号提取），保守。
- **不引入 few-shot / 低温采样**：剥围栏后围栏不再产生重试，既有重试兜底残余
  畸形足够；少动共享提示词与请求体（DeepSeek 行为零扰动）。

## Testing Decisions

- **测试缝**：llm.py 单元（test_llm.py），沿用既有假 transport / 假 LLM 注入。
- `_unwrap_json_fence` 单元：围栏 json / 围栏无语言标注 / 非围栏原样 / 半截围栏
  不剥 / 内部含 ``` 不误伤 / 空内容。
- `_chat` json_mode 集成：注入假 transport 返回围栏包裹 JSON → 解析成功（用任一
  真实 parse 函数）；文本模式调用输出原样（围栏代码不 mangle 断言）。
- **回归**：既有 DeepSeek JSON 解析测试全部原样通过（剥 = no-op）；无本地配置
  路径逐字节不变。
- LOCAL_LLM_METHODS 扩充：更新「落 local 的方法集 = 常量」行为断言（02 已建）+ 每
  新方法派发用例（fake 记录）；未扩方法仍落 remote 断言。
- 真机复核（验收项）：配置本地端点，真实跑一次澄清 + 简介校验 + 归档判定，
  输出可用（人工/脚本验证）。
- 全量 pytest + mypy 绿。

## Out of Scope

- few-shot 示例注入 / 低温采样（剥围栏后非必需；如需降延迟留后续）。
- select_modules / distill_master / fix_compile_errors / 骨架本地化——7B 能力
  上限，剥围栏救不了格式之外的问题。
- topic_split_topics / topic_extract_number 本地化——未 spike 验证，保守留远程。
- 围栏之外的其他畸形输出——既有重试机制已兜底。

## Further Notes

- 实验证据：`.scratch/local-llm-spike/probe-fewshot.py`（两轮对照：clarify 无示例
  0/3 → 带示例 3/3→2/3；validate 无示例 0/3 → 带示例 1/3 → 带贴合示例 2/3——
  漂移随机性实锤，few-shot 只作减速带不可作门禁）。
- 剥围栏是共享解析缝改动，同时影响 DeepSeek 与本地两条路径；设计为仅剥"整体围栏
  块"，对合法 JSON 与文本模式零影响——这是确定性根治，不依赖模型配合。
- 前置 feature：local-llm-routing（01 配置 / 02 路由 / 03 设置页 UI）已全闭；
  本 spec 在其基础上扩展。
