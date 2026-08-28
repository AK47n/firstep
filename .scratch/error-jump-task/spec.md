# 主推进入口未受监控的失败体验（error-jump-task）spec

## 问题陈述

任务执行失败（编译红）时，任务结果面板只显示「编译验证未通过」徽章 + diff，用户
看不到**具体错在哪一行**；要定位必须切到「编写代码」卡手动翻 main.c。主生成的
「编译修复中心」已有错误行点击跳转 main.c 的零件（工单 compile-error-jump/01：
`maincJumpToLine`），但它是 generate-fix.js 的私有函数，任务面板无法复用。

## 目标

任务执行失败时，结果面板直接列出编译错误（文件 / 行号 / 消息），点击行号跳转到
main.c 预览卡并选中该行文本高亮——与修复中心的跳转行为完全一致。

## 用户故事

1. 我点「做这一步」结果编译失败，结果面板里能看到每一条错误的文件:行号:消息。
2. 我点某条错误，页面自动切到 main.c 预览卡并滚动选中那一行（持续高亮）。
3. 错误行若在 main.c 之外（如头文件 / 模块文件），不跳转，行为与修复中心一致
   （展开源码行路径——任务面板不做源码行展开，只 toast 提示「该错误不在此
   main.c，请用修复中心查看」）。

## 实现决策

- **后端一处**：deepen.py `_compile_summary(build)` 返回加 `"parsed_errors":
  [{"path", "line", "message"}]`（parse_compile_errors 结果——`_compile_summary`
  里 parsed 已经解析了，只是没放进返回；`compile_runner.run_compile` 的 done
  载荷已带同款字段，两侧同源：`compile_runner.parse_compile_errors`）。所有走
  verify_compile_tail 的路径（任务 / 深化 / 参数修改 / 直接修正）自动获得。
  旧前端忽略新字段；`compile` dict 只追加不改既有键。
- **跳转单源迁移**：`maincScrollToRange` / `maincJumpToLine` 从
  ui/generate-fix.js 迁入 **fx/code.js**（code.js 已是 main.c 定位底座：
  maincLineOffsetRange / isMainCPath / maincContentEmpty）。迁移后
  `maincJumpToLine(line)` 返回 `null`（成功）或错误码字符串
  （"empty" | "out-of-range" | "no-textarea"），**toast 由调用方做**
  （fx 模块不 import app.js 的 toast——app.js 也不挂 window.toast）：
  - generate-fix.js：删私有两函数 + 导入新导出；fixToggleSource 调
    maincJumpToLine 后按错误码 toast（原三条消息语义逐字保留）。
  - code.js 依赖 `syncCollapseBtn`（fx/generate.js 导出，无环：generate.js
    无共享件依赖）。
- **任务面板**：fx/task.js 新增 `taskErrorsHTML(parsedErrors)` 纯函数（每个错误
  一行 `.task-err-row`：path:line（line 为 main.c 时才可点）+
  message，全部 esc）；generate-tasks.js `tasksRenderResult` 在徽章 detail 后
  插入（data.compile.parsed_errors 非空才渲染）；网格委托点击
  `.task-err-jump` → `maincJumpToLine(line)` + 错误码 toast。
  非 main.c 错误行 = 不可点（无 data-line），符合故事 3。

## 测试决策

- tests/js/task.test.mjs：taskErrorsHTML（转义 / 非 main.c 无跳转属性 /
  空数组空串 / 可点行带 data-line）。
- tests/js/code.test.mjs（若存在则扩展，否则 test 并入 task.test.mjs 或新建）：
  maincJumpToLine 错误码路径（需 DOM 桩——jsdom 无 textarea 布局，仅断言
  错误码分支：no-textarea / empty；成功分支有已加最简桩测试则保留）。
- pytest：test_task_progress.py / test_deepen.py 扩展断言 `compile.parsed_errors`
  形状（run_task 失败路径 done 载荷带 parsed_errors；_compile_summary 单测）。
- fx-guard：code.js 新导出登记；task.js taskErrorsHTML 登记。

## 范围外

- 任务面板不做「错误行展开源码行 / 单轮修复」——那是修复中心（10 卡）的能力，
  任务面板只做跳转；重复接入修复循环会模糊「一步一验证」语义。
- 不改 compile_runner.run_compile（已有 parsed_errors）。
