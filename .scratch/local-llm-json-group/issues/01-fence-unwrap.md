# 01 — 解析层剥围栏：json_mode 输出不再被 Markdown 围栏卡死

**What to build:** 本地模型把 JSON 输出包进 ```` ``` ```` Markdown 代码围栏时，
工具仍能正确解析（不再因围栏包裹而大声失败）。这是确定性根治，不依赖模型
心情；对 DeepSeek 路径零影响（从不包围栏，剥 = no-op）。

**Blocked by:** 无（可立即开始）

**Status:** resolved

## 验收

- [x] `_unwrap_json_fence(content)` 辅助（llm.py 唯一出处）：仅当**整个输出**
      就是一个 Markdown 代码围栏块（开头 ```` ``` ```` 或 ```` ```json ```` 等 +
      结尾 ```` ``` ````）时剥掉外层返回内部文本；非围栏 / 只有开头没结尾 /
      内部含围栏 / 空内容一律原样返回（绝不错伤合法内容）。
- [x] `DeepSeekLLM._chat` 的 json_mode=True 分支：返回 content 前先
      `_unwrap_json_fence`——单点覆盖全部 json_mode 调用；文本模式调用
      （json_mode=False）输出原样不动（骨架 ```` ```c ```` 围栏等合法内容不被
      mangle）。
- [x] 测试：`_unwrap_json_fence` 单元（围栏 json / 围栏无语言标注 / 非围栏原样 /
      半截围栏不剥 / 内部含 ``` 不误伤 / 空内容）；`_chat` json_mode 集成
      （假 transport 返回围栏包裹 JSON → 用任一真实 parse 函数解析成功）+ 文本
      模式不剥断言。
- [x] 回归：既有 DeepSeek JSON 解析测试全部原样通过（剥 = no-op）；无本地配置
      路径逐字节不变。
- [x] 全量 pytest + mypy 绿。

## 结论

`_unwrap_json_fence` 独立实现（首行 ```/```lang + 末行 ``` + 内部无围栏行才剥，
整体围栏块判定，非 clex 的首尾围栏行剥离——判据不同，docstring 已写明分工）；
`_chat` json_mode 单点接线。test_llm.py +12（含真实 parse 集成 + 文本模式不剥）。
全量 1827 绿 + mypy 47 文件干净 + node:test 17 绿。code-review 双轴过：
Standards 两判例（clex 复用 / 命名族）均被 spec「llm 唯一出处 + 文件名必改」覆盖，
已修唯一可执行项（测试裸名导入去未用 import）；Spec 无缺失/越界/实现错误。

## 文件边界

- llm.py：`_unwrap_json_fence` 辅助 + `_chat` json_mode 分支（一处调用点）。
- 测试：test_llm.py。
- 不动路由方法集（02 的边界）、不动 config、不动 webapp、不动前端。
