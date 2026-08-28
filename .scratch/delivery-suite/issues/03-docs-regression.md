# 交付集成：文档回归（delivery-suite/03）

## 状态
Status: resolved

## 目标
CONTEXT.md 记录交付域词条，全量回归。

## 实现
- CONTEXT.md 新增「交付」词条行：/api/delivery/open-ide|check|package +
  delivery.py（open_project_dir 平台分流：stm32 UV4.exe 优先 / explorer
  兜底；delivery_check 状态统计 + 未完成清单；package_project 排除
  .contest_* + .tmp/.bak，时间戳 zip 不覆盖）+ fx/delivery.js 三导出；
  任务推进行/任务序号行指向。
- 全量 pytest + JS + 语言/PS1/CHANGELOG 检查。

## 交付
- 提交（中文，spec/issues 03 随提）。
