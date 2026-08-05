# 05 — main.c 骨架生成 + 函数自检

**What to build:** 用户拿到生成的工程时，main.c 已由 AI 排好初始化调用序列：只调用所选模块头文件中真实存在的函数，带注释与预留编写区，不确定处注释占位，保证可编译。

**Blocked by:** 01 — 生成器核心骨架 + fixture 测试基座

**Status:** done

- [x] LLM 基于所选模块的头文件接口生成 main.c 骨架：初始化序列、注释、预留编写区
- [x] 静态自检：main.c 引用的每个函数都存在于所选模块头文件中；不存在的调用被拦截（改为注释占位或明确报错）
- [x] 占位处理：AI 不确定的调用以注释形式标注，不凭空造函数
- [x] fixture 假 LLM 下测试全绿：断言骨架结构与自检行为

## Comments

- 2026-08-05: 工单 05 完成。新增 `skeleton.py`：`build_skeleton_interfaces` 按目标平台收集所选模块的头文件内容（只取平台条目里的 `.h`），`extract_header_functions` 从接口块提取函数声明/定义与函数式宏（自检只认喂给 LLM 的同一份接口），`find_undefined_calls` 静态自检（注释/字符串/控制关键字/main.c 自建函数不计），`sanitize_skeleton` 把不存在的调用改写为占位、语句保持可编译，`generate_skeleton` 组合 LLM 出稿 + 自检。`llm.py` 的 `generate_main_skeleton` 输入从模块摘要改为头文件接口块，系统提示明确：只调真实接口、不确定写注释占位、绝不凭空造函数。
- 对"不存在的调用被拦截"的两个分支都做了实现：骨架阶段（sanitize）注释占位，生成器落盘前再做一遍同样的静态校验（`UndefinedCallsError` 明确报错，`generator._check_main_calls`）——后者也兑现了 spec 的"生成后自检"与"全功能只通过生成器接缝测试"。
- 占位实现注意：语句位置的整段调用替换为"TODO 注释 + 空语句"，表达式（赋值/条件/实参）里的调用替换为 `0` 占位——整行注释会连单行 `int main(void) { ... }` 一起干掉，违反"保证可编译"。
- fixture 修正：假模块库 `delay.h` 补上 `void delay_ms(int ms);` 声明（头文件必须声明接口，自检才有意义）；`MAIN_SKELETON` 改为只调所选模块头文件里真实存在的函数（生成器现在会校验）。`FakeLLM` 增加骨架调用记录。
- 测试：新增 tests/test_skeleton.py（19 例：接口收集、函数提取、自检边界、占位改写、假 LLM 全流程 + 骨架→生成器落盘集成），test_llm.py 骨架用例更新，全量 137 通过。
