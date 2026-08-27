# 题型决策骨架模板（topic-framework）— spec

> 来源：docs/improvement-feasibility-analysis.md B2 + 决策点 3（2026-08-18 已拍板：载体 = 参考库条目加 `topic_type` 标记 + 按题型结构化注入；不新建库）。本 spec 实现该决策点，并在其约束内定形态。

## 问题陈述

新题（尤其巡线小车类）的决策逻辑（状态机 / 路由 / 调度结构）目前每次由 AI 从零现写：骨架 prompt 里只有「参考实现全文」（`reference_fulltexts`——21F / 26H / car-1-1 决策例程的整段代码），模型要在几十 KB 全文里自己提炼「这道题应该用什么框架」，质量波动大、容易跑偏（状态机写得零散、调度器忘了 10ms 周期、决策分支互相打架）。

现状证据（代码侧）：`llm._skeleton_user_prompt` 把 reference_fulltexts 作为「参考资料（可作实现草稿）」整段注入——参考全文是**约束弱的学习素材**，不是**强约束的框架模板**；`skeleton.py` / `generator.py` 均无「题型」概念。用户故事：同一道 2021F 巡线题，AI 每次生成的决策结构不同，返工率高。

## 方案

**题型 = 参考库条目的结构化标记 + 按题型确定性注入框架段。** 参考库条目（21F / 26H / car-1-1）加 `topic_type` 词表字段；骨架 / 深化 / 任务推进的 LLM 调用，若当前上下文命中带 `topic_type` 的参考条目，**确定性**读该条目目录内的 `framework/` 子目录下约定文件（`framework/main.c`：纯 C、平台中立、接口名用注释占位约定，如 `// TODO: <接口> 由接口块替换`），裁掉平台 / 接口相关的噪音后作为「题型框架段」注入 prompt——框架段带强指令：**main.c 必须保留框架结构（状态机枚举 / 调度循环命名不动），只在 TODO 位填实现**。

- **注入位置**：`llm._skeleton_user_prompt` 新增 `topic_framework: str | None` 参数（在 reference_fulltexts 段之前插入「题型框架（必须保留的结构）」段）；`generate_main_skeleton` 协议方法同步加参。**deepen / task-execute 复用同一注入**（它们的 user prompt 均以 main.c + 接口块为底，框架段追加同样适用）——但分解：本期只做骨架主链路 + LLM 协议参数贯通；deepen / task-execute 的注入留一个开关（见工单 03 决策）。
- **框架文件规范**：参考条目目录 `framework/main.c`（纯文本；`topic_type` 非空但文件缺失 = 降级只注入条目全文，不报错——框架是增强不是闸门）。版本化：写库动作自动 git 提交（lib-autocommit 既有）。
- **词表（topic_type）首批**：`line_follow`（巡线/循迹决策类：21F 送药、26H 滚球、car-1-1 巡线模板）+ `generic`（通用决策结构——状态机枚举 + 主循环调度骨架，不限巡线）。留扩展：词表 = `reference_library.TOPIC_TYPES` 单源常量，加新题型 = 加常量 + 条目标记。
- **条目元数据**：`ReferenceEntry` 加 `topic_type: str = ""`（空 = 未标记题型，向后兼容；词表外值 = 元数据损坏大声失败，与 platform 同款）。校验与读写经 `add_reference` / `update_reference` / `from_dict` / `to_dict`。**前端参考库编辑弹窗加「题型」下拉（词表来自 /api/references 每条的 topic_type + GET 常量端点或前端常量表——选前端常量表 + 后端校验双源，照 kit 词表先例）。**
- **注入判据**：`topic_framework` 由调用方（webapp `/api/skeleton` / deepen / tasks）在装配参考时就地计算——遍历 `topic.references`，取第一个 `topic_type` 非空的条目，调新纯函数 `build_topic_framework(reference_root, entry) -> str | None`（读 `framework/main.c`，缺失 / 不可读 = None 降级）；**平台过滤复用 `_platform_matches`**（条目标 topic_type 但平台不匹配 = 不注入框架段，仍走全文注入）。
- **确定性注入 vs LLM 段**：框架代码段 = 确定性（从库文件读，不经 LLM 改写，注入 prompt 原样给出）；「学习说明」（框架怎么用、填什么）= LLM 段（骨架出稿本来就带题面 / 接口 / TODO，模型消化框架段后按接口块填实现）。与决策点 3「框架代码段走确定性注入、学习说明走 LLM 段」逐字对齐。
- **防漂移兜底**：`sanitize_skeleton` 会拦截「接口块不存在的调用」——框架段里的注释占位约定（`// TODO: <function> 由接口块替换`）天然避免幻觉调用；框架段不参与 sanitize（它是 prompt 文本）——LLM 输出的 main.c 仍走 sanitize（拦截列表照旧）。
- **前端**：骨架出稿后展示「题型框架已注入：<topic_type>（来源 <entry 标题>）」提示（步骤 8 加一行，纯展示）；参考库表格加「题型」列（可见性 filter 沿用既有风格）。
- **新题库入口**：无（2026A-H 已拆条入库；新题优先用库内命中走 workflow，B2 是机制不是素材库扩充——素材（21F/26H/car-1-1 标 tipy_type + 写 framework/main.c）作为工单 04 一并做）。

## 用户故事

1. 作为学生，我生成 2021F 巡线题骨架时，main.c 里已有按 21F 决策例程提炼的巡线状态机框架（十字路口检测 → 路由表 → 送药判定），AI 只填 TODO，不用重新发明决策结构。
2. 作为学生，我生成 2026H 滚球题骨架时，自动命中 26H 条目的巡航框架；若我选了 stm32 平台而框架条目是 mspm0/any 之外——不匹配不注入（或按平台过滤规则），不硬塞强约束。
3. 作为学生，我在参考库编辑一个文献条目时，下拉框只能选已注册题型（line_follow / generic），填不了自由文本——词表外值同步被后端拒绝。
4. 作为 AI，我在骨架 / 深化 / 任务推进调用中出现题型框架段时，按「保留框架结构、填 TODO 实现」稳定出稿，决策结构的一致性与可维护性显著提升。
5. 作为 AI，我读 `ReferenceEntry.topic_type` 与 `framework/main.c` 时知道它们的语义（题型标记 + 确定性框架段），不会把它当普通文件读进全文。

## 实现决策

1. **`topic_type` 词表单源**：`reference_library.TOPIC_TYPES`（常量元组：`line_follow`、`generic`）+ `TOPIC_TYPE_LINE_FOLLOW` / `TOPIC_TYPE_GENERIC` 常量 + `validate_topic_type`（词表外 → ReferenceError「非法题型：…（应为 …）」）。`ReferenceEntry.from_dict`：`topic_type = data.get("topic_type", "")`，非空时校验词表，词表外 = 元数据损坏大声失败（与 platform / anchor_kind 同款）。
2. **框架文件规范**：条目目录 `framework/main.c`（相对条目根）。`build_topic_framework(reference_root: Path, entry: ReferenceEntry) -> str | None`：`topic_type` 空 → None；`framework/main.c` 不存在 / 不可读（OSError/UnicodeDecodeError）→ None（降级，不抛错）；成功 = 返回文件全文。读取编码 utf-8。
3. **注入提示词**：`_skeleton_user_prompt(problem_text, module_interfaces, reference_fulltexts, topic_framework=None)`——框架段插入位置 = 参考段之前；文案模板：
   ```
   题型框架（<topic_type>，来源 <entry.id>）——必须保留的 main.c 结构：
   ```c
   <framework 全文>
   ```
   按此框架写 main.c：枚举 / 调度循环 / 状态机函数名保持原样，只在 `// TODO:` 处填当前所选模块接口的实现；框架里出现的调用若接口块中不存在，写成注释占位。
   ```
4. **协议贯通**：`LLM.generate_main_skeleton(problem_text, module_interfaces, reference_fulltexts=None, topic_framework=None)`；DeepSeek 实现 + RoutingLLM 转发（remote 方法一并加参）+ `fakes.py` FakeLLM/RecordingLLM 同步（照 plan_tasks / execute_task 先例）。`_generate_main_c` 加参透传。**出稿后 main.c 仍走 sanitize_skeleton（拦截列表照旧）；框架段不参与 sanitize（它是 prompt 文本）。**
5. **webapp 装配**：`/api/skeleton` 装配点（`_assemble_topic_context` 后）新增 `framework = build_topic_framework(_reference_root, first_topic_type_entry)`，平台过滤 = `_platform_matches(entry, platform)`（any 全进 / 空 = 不过滤 / 匹配才进——照既有）。注入 `run_skeleton(..., topic_framework=framework)`。返回体加 `{"topic_framework": {"topic_type": …, "source": …, "injected": bool}}`（前端展示 + 测试断言）。
6. **deepen / task-execute 延伸**（本期只做开关键，不做全套）：`TopicContext` 不存框架（build_topic_framework 是独立纯函数，deepen/tasks 需要时各自调用）——**不做**，保持本期 scope = 骨架主链路 + 协议参数贯通。deepen/task 的框架注入留后续工单（spec 范围外注明）。
7. **前端**：
   - 参考库 tab：表格加「题型」列（`topic_type` 空 = `—`）；编辑弹窗加「题型」下拉（`<option value="">未标记</option>` + 词表），PUT payload 加 `topic_type`；新增表单加同样下拉。
   - 生成页步骤 8（骨架）：出稿结果面板加「题型框架已注入：xxx（来源：xxx）」提示行（`data.topic_framework.injected` 为真才显示）。
   - fx-guard / ui-cycle 新函数按既有规范进对应文件（`fx/reference.js` + `ui/reference.js` + `ui/generate-mainc.js`）。
8. **API 契约**：
   - `POST /api/references` / `PUT /api/references/{id}`：payload 加可选 `topic_type`（缺省 ""）；非法词表 → 400（域层 ReferenceError）。
   - `GET /api/references`：条目 dict 已含 topic_type（to_dict 加字段即自然带出）。
   - `POST /api/skeleton`：返回体加 `topic_framework` 字段（见 5）。
   - `POST /api/tasks/execute` / `POST /api/revise/deepen`：**不改**（范围外）。
9. **词表**：「题型」「题型框架」进 CONTEXT.md（生成后阶段词表续行——B2 词条，含 topic_type 词表与 framework/main.c 规范）。

## 测试决策

- **模型与校验**：`ReferenceEntry.from_dict` 已知 / 未知 topic_type；`add_reference` / `update_reference` 词表外 400；`to_dict` 含字段；向后兼容（无 topic_type 的旧 JSON = 空串）。
- **build_topic_framework**：topic_type 空 → None；文件缺失 → None（不抛）；UTF-8 读取成功 → 全文；词表外（不经过——from_dict 已拦，直接传构造 entry 不测）。
- **协议注入**：`_skeleton_user_prompt` 带 topic_framework → 输出含框架段（文案断言）；None → 逐字节不变（既有断言先例）；框架段在 reference_fulltexts 段**之前**（位置断言）。
- **webapp**：/api/skeleton 命中 21F 条目（fakellm）→ 返回 topic_framework；无标记条目 → None；`GET /api/references` 载荷含 topic_type。
- **深层回归**：无 topic_type 条目 / 无 framework 文件 / 无参考条目 → 骨架生成行为与现行为一致（既有 2465+ 回归 + 新增断言）。
- **前端纯函数**：题型下拉渲染 / 表格列渲染（`table_row` 改）+ 断言；步骤 8 提示行渲染函数。

## 范围外

- 不做 topic_type 的「自动识别」：条目标题型 = 人工 / AI 录入时显式选择（不 Ocr 题面推导题型）。
- 不做框架文件的自动生成：`framework/main.c` = 人写 / AI 草稿 + 人确认（素材整理类工单 04 独立做，与代码工单不可混批）。
- 不做 deepen / task-execute 的框架注入（本期代码只通骨架主链路；协议参数先贯通到 `generate_main_skeleton`，其它调用方后续接）。
- 不新建库：框架段 = 参考条目目录内文件（`framework/main.c`），不另立「题型库」目录（决策点 3）。
- 不做「同一题命中多个 topic_type 条目」的合并：取第一个匹配（保序），其余条目仍走全文注入。
- 不改 sanitize_skeleton 语义（框架段不进自检，main.c 照旧）。

## 补充说明

- 决策点 3 原文：「题材载体 = 参考库条目加 `topic_type` 标记 + 按题型结构化注入（框架代码段走确定性注入、学习说明走 LLM 段）。独立模板库留给素材量大了之后的 expand-contract。」——本 spec 与之一致。
- 术语命名：用户口语「题型决策骨架模板」；spec 定名「题型框架」（topic framework）。落 CONTEXT.md。
