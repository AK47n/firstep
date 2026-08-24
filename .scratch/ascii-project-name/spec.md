# 工程目录名英文化（ascii-project-name）

## 问题陈述

firstep 生成的桌面工程目录名默认含中文（如 `2024H 自动行驶小车`）。CCS(Theia)
与 GNU make 在这台机器上对中文路径支持有缺陷：CCS IDE 用 `.cproject` 重新生成
makefile 集时写工程绝对路径（含中文），gmake 经 `SHELL = cmd.exe` 按 ANSI 代码页
(GBK/936) 转码 → 乱码 → `Error: File "...msmp0.syscfg" does not exist`；母版空工程
（`C:\Users\luoji\workspace_ccstheia\empty`，纯 ASCII 路径）无此问题，已真机对照
验证（第一轮工单 mspm0-cjk-path-fix/01 修的是 firstep 模板，管不住 CCS IDE 自行
重建 makefile 的行为）。用户决策：**生成的工程目录名改为纯英文（ASCII）**，从根
上绕开编码链路；AI 起名同样输出英文。

## 方案

- **历史赛题**（topic_id 给定，现走 `topic_dir_title`）：目录名 = `编号_英文短名`，
  英文短名来自**内置英文字典**（题面中文短题名 → 英文短名，确定性、离线、可预测，
  不依赖 AI）。例：`2024H 自动行驶小车` → `2024H_Auto_Car`。
- **粘贴题面**（无 topic_id，现走 `topic_title_from_summary` + LLM）：新增一次 LLM
  调用 `name_topic_english`（题面 → 英文短名），目录名 = AI 英文短名（如
  `Auto_Car`）；AI 不可用/失败时 502（与现有 summarize_topic 失败行为一致）。
- 字典未命中（新增赛题未收词）时确定性兜底：英文短名 = 保留 ASCII 部分去分隔
  空格，仍为空则回退原中文短题名（保底可生成；提示用户补词）。
- `windows_safe_folder_name` / `unique_desktop_topic_dir` 不变（继续承接清洗与
  唯一化）。

## 用户故事

1. 作为电赛学生，我从历史题库选 2024H 生成工程，桌面出现 `2024H_Auto_Car`
   目录（纯 ASCII），CCS 打开直接能编译，不再乱码。
2. 作为电赛学生，我粘贴自定义题面生成工程，目录名为 AI 起的英文短名
   （如 `Auto_Car`），同样纯 ASCII 可编译。
3. 作为 firstep 作者，我用字典/逻辑覆盖现题库全部 8 个历史赛题
   （2018C/2019A/2020C/2021F/2022C/2022H/2024H/2026C），生成稳定可预期。
4. 作为 firstep 作者，字典未命中新题时行为确定（ASCII 兜底），不崩坏。

## 实现决策

- 修改模块：
  - `src/contest_generator/generation_output.py`：新增 `TOPIC_EN_TITLES` 字典
    （中文短题名 → 英文短名，覆盖现题库 8 题）、`topic_en_title(short_title)`
    查找+兜底、`topic_dir_title` 改为 `f"{key}_{en}"` 形态；`topic_title_from_summary`
    保留（/api/topic/summarize 展示仍用）。
  - `src/contest_generator/llm.py`：`LLM` Protocol 加 `name_topic_english(problem_text)
    -> str`（纯文本单次调用，同 summarize_topic 的 `_retry_parse` 兜底）；新增
    `TOPIC_EN_NAME_SYSTEM_PROMPT`；`RoutingLLM`/实现类照抄 summarize_topic 模式
    （**不**进 LOCAL_LLM_METHODS——本地模型命名质量不可控，方法与本地集语义无关，
    保持现有派发，remote 侧实现；若无 local 配置天然走 remote）。
  - `src/contest_generator/webapp.py` `_resolve_generation_output_dir`：历史赛题分支
    不变（走字典）；粘贴题面分支改调 `name_topic_english` 结果做目录名。
- 字典内容（短题名 → 英文）：
  - `自动行驶小车` → `Auto_Car`
  - `智能送药小车` → `Smart_Medicine_Car`
  - `小车跟随行驶系统` → `Car_Following_System`
  - `无线充电电动小车` → `Wireless_Charging_Electric_Car`
  - `电动小车动态无线充电系统` → `Dynamic_Wireless_Charging_System`
  - `坡道行驶电动小车` → `Slope_Driving_Electric_Car`
  - 2026C 首行形态特殊（`# 2026年全国大学生电子设计竞赛赛区赛(TI杯)`），
    `topic_short_title` 提取后以「2026 全国...」开头，字典键 = 提取结果；
    未命中时兜底必须保证 `2026C` 前缀可用（兜底文本允许含编号）。
- API 契约：`name_topic_english` 与 `summarize_topic` 同款（系统提示词 + 用户题面
  文本，返回纯文本短名；输出过长/空 → 解析失败重问，上限同
  `SUMMARY_RETRY_LIMIT`）。

## 测试决策

- `tests/test_generation_output.py`：
  - `topic_dir_title` 断言改为 `2024H_Auto_Car` / `2021F_Smart_Medicine_Car` 形态；
  - 新增：字典覆盖现题库全部短题名（遍历 8 个真实短题名断言命中）；
  - 新增：字典未命中 → ASCII 兜底（如 `2026C_2027_...` 形态/回退中文短题名）；
  - 新增：`topic_en_title` 未命中回退语义。
- `tests/test_llm.py`：`name_topic_english` 单测（prompt 进入文本模式、超长截断、
  瞬时失败重试同 summarize_topic 先例）；RoutingLLM 派发断言（不属于本地集）。
- `tests/test_webapp.py`：`_resolve_generation_output_dir` 粘贴题面分支（fake LLM
  返回英文短名 → 目录名 = 英文短名）；历史赛题分支（topic_dir_title 直取）。
  FakeLLM 补 `name_topic_english`。
- 既有先例：test_generation_output.py 现断言形态改写即可；test_llm.py
  `test_summarize_topic_*` 系列为 `name_topic_english` 模板。

## 范围外

- 不改 Windows 系统代码页/CCS 配置；第一轮 makefiles.py 相对路径修复保持原样。
- 不改 2024H 现有桌面工程（用户已保留中文目录，另行生成英文目录新工程）。
- 不把 `name_topic_english` 加入 LOCAL_LLM_METHODS（本地模型命名不可控，见实现
  决策）；stm32/Keil 线命名同样受益（同一 output_dir 决策点），但不做任何
  Keil 特有改动。
- 不动 `.contest_context.json` 的编码误解码旁证问题（另行排查，非本工单）。

## 补充说明

- 真实验证：修复完成后用真实生成器（调用链 pipeline）对 2024H 重生成到
  `C:\Users\luoji\Desktop\2024H_Auto_Car`，跑 gmake 全量编译 exit=0。
