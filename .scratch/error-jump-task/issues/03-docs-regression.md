# 错误行跳转：文档回归（error-jump-task/03）

## 状态
Status: resolved

## 目标
CONTEXT.md 记录 parsed_errors 载荷与跳转单源，全量回归。

## 实现
- CONTEXT.md 任务推进行补「错误行跳转」：compile 摘要带 parsed_errors（与
  compile_runner 同源）；任务结果面板错误行点击跳 main.c 高亮（fx/code.js
  maincJumpToLine 单源，修复中心与任务面板共用；toast 由调用方做）。
- 全量 pytest（2734+ 新增）+ JS（585+ 新增）+ 语言/PS1/CHANGELOG 检查。

## 交付
- 提交（中文，spec/issues 随提）。
