# 01 — 历史赛题目录名英文化（内置字典 + topic_dir_title）

**要做什么：** 生成工程时，历史赛题（topic_id 给定）的桌面目录名从
`2024H 自动行驶小车` 变为 `2024H_Auto_Car`：英文短名来自内置
`TOPIC_EN_TITLES` 字典（题面中文短题名 → 英文短名），离线确定性、可预测；
字典未命中时 ASCII 兜底（保留 ASCII 部分，仍空回退中文短题名）。前端/API
形态不变（仍输出目录路径），只改命名内容。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] `src/contest_generator/generation_output.py` 新增 `TOPIC_EN_TITLES`
      （8 个历史赛题全覆盖，键 = `topic_short_title` 提取结果）与
      `topic_en_title(short_title) -> str`（命中字典 / ASCII 兜底 / 中文回退）
- [x] `topic_dir_title` 改为 `f"{key}_{en}"` 形态（下划线连接，含编号）
- [x] `tests/test_generation_output.py`：`topic_dir_title` 断言改为
      `2024H_Auto_Car` / `2021F_Smart_Medicine_Car`；新增字典覆盖 8 题测试、
      字典未命中兜底测试、`topic_en_title` 回退测试
- [x] 该文件 pytest 全绿

**验收记录（2026-08-24）：** 20 passed；题库 8 题（2018C/2019A/2020C/2021F/
2022C/2022H/2024H/2026C）字典全覆盖，2026C 题面首行形态特殊（赛区赛(TI杯)）
以完整提取串为键收录。

# 02 — AI 起名英文化 + 粘贴题面路径英文目录名

**要做什么：** 粘贴题面（无 topic_id）生成工程时，目录名由 AI 起的英文短名
决定（如 `Auto_Car`）：新增 LLM 方法 `name_topic_english(problem_text) -> str`
（纯文本、同 summarize_topic 的重试/截断协议，不走本地模型集），webapp 的
`_resolve_generation_output_dir` 粘贴题面分支改调它；HTTP 语义不变（AI 失败
→ 502）。

**被谁阻塞：** 01（命名决策一致，先有字典/兜底语义）

**状态：** resolved（2026-09-27 按在盘代码与测试翻牌——实现早已落地，此前只是票没翻；证据见本单末尾「收口记录」）

- [x] `src/contest_generator/llm.py`：`LLM` Protocol + 各实现 +
      `TOPIC_EN_NAME_SYSTEM_PROMPT` 新增 `name_topic_english`（文本模式、
      `_retry_parse` 兜底、超长截断同款）；RoutingLLM 直通 remote（不进
      LOCAL_LLM_METHODS）
- [x] `src/contest_generator/webapp.py`：粘贴题面分支改调
      `name_topic_english`，目录名 = 英文短名（go 过 windows_safe）
- [x] `tests/fakes.py`：FakeLLM 补 `name_topic_english`
- [x] `tests/test_llm.py`：`name_topic_english` 文本模式 / 截断 / 重试 /
      RoutingLLM 派发（非本地集）测试
- [x] `tests/test_webapp.py`：粘贴题面分支 fake 断言 → 英文目录名；
      历史赛题分支断言 → `2024H_Auto_Car`
- [x] 相关测试文件全绿

**收口记录（2026-09-27，台账复核轮）**：本单 §02 的代码与测试**早已在盘上**，
但票面一直停在 `ready-for-agent` + 全空勾选框（`real-acceptance` 挂账与几轮盘点都没翻）。
本轮逐条核对后翻牌，逐项证据：

| 验收项 | 证据（本轮实读） |
|---|---|
| 协议 + 实现 + 系统提示词 | `llm.py:688` `TOPIC_EN_NAME_SYSTEM_PROMPT`；`:1687` Protocol；`:2218-2236` 实现（`_truncate_content` 截断 + `_retry_parse` 兜底 + 空输出拒收，docstring 自述工单 02） |
| RoutingLLM 直通 remote | `llm.py:4046-4047` 委托 `self._remote`；`tests/test_llm.py` 的 `PROTOCOL_METHOD_NAMES` 含 `name_topic_english`，派发对账断言 `remote.calls` 含它（`:6712`）且 `remote = PROTOCOL - LOCAL_LLM_METHODS`（`:6812`） |
| webapp 粘贴题面分支 | `webapp.py:1686` `title = _llm(context).name_topic_english(problem_text)`（`topic_id` 缺失或字典未命中时才走这条；docstring `:1661` 点名工单 02） |
| 过 `windows_safe` | `generation_output.py:175` `candidate = desktop_dir / windows_safe_folder_name(title)`（在 `desktop_topic_dir_verdict` 里，两个分支共用） |
| FakeLLM | `tests/fakes.py:794`（`name_topic_english`）+ `:601` `topic_en_name` 可注入；`:1182-1183` |
| 测试 | 定向：`pytest tests/test_llm.py tests/test_webapp.py tests/test_generation_output.py -k "name_topic_english or topic_en_title or auto_car or TOPIC_EN"` → **10 passed**（4 条 `test_name_topic_english_*` + 字典覆盖/ASCII 兜底/中文回退 + 用例内 `Auto_Car` 断言）；**整三文件：750 passed / 38.85s**（2026-09-27 本机实跑） |

**本单剩下的只有 §03**（真机验证 2024H 生成到 `2024H_Auto_Car` 并 `gmake` 编译）——
桌面无该目录，确未跑过；真机项已集中挂账在 `real-acceptance/01`。

# 03 — 真机验证：2024H 生成到英文目录并编译

**要做什么：** 用修复后的真实生成链路（非 fake）把 2024H 重新生成到
`C:\Users\luoji\Desktop\2024H_Auto_Car`，确认目录名是英文、`gmake -C
Debug -f makefile -B all` exit=0、`mspm0_project.out` 产出。

**被谁阻塞：** 01、02

**状态：** ready-for-agent

- [ ] 真实生成 2024H → 桌面 `2024H_Auto_Car`
- [ ] 目录内无中文路径残留（makefile 集 recipe 全 ASCII）
- [ ] gmake 全量编译 exit=0、`.out` 存在

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
