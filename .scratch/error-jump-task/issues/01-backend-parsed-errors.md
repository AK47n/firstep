# 错误行跳转：后端编译摘要带 parsed_errors（error-jump-task/01）

## 状态
Status: resolved

## 目标
deepen.py `_compile_summary(build)` 返回加 `parsed_errors` 字段
（[{"path", "line", "message"}]，parse_compile_errors 结果——parsed 已在
函数内解析，只差放进返回）。所有 walk verify_compile_tail 的路径（任务 /
深化 / 参数修改 / 直接修正）自动获得；compile dict 只追加不改既有键
（passed / exit_code / summary），旧前端忽略新字段。

## 实现
- `_compile_summary`（src/contest_generator/deepen.py:344-353）返回 dict 加：
  `"parsed_errors": [{"path": e.path, "line": e.line, "message": e.message}
  for e in parsed]`（无 build（build 为 None 的降级分支）→ []）。
- docstring 更新（compile dict 形状）。

## 测试
- tests/test_deepen.py：test_compile_summary_includes_parsed_errors（构造
  SimpleNamespace run.output 含两错误 → 断言 parsed_errors 形状）；
  build None → 空列表。
- 顺带断言 compile 既有键不变（passed/exit_code/summary 仍存在）。

## 交付
- 双轴评审 → 整改 → 全量 pytest → 提交（中文提交信息，spec/issues 随提）。
