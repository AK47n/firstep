# 工单 03：文档回归（param-tune/03）

Status: pending

## 目标

CONTEXT.md 补「参数速调」词条行 + 全量回归 + 提交。

## 交付

- CONTEXT.md：新词条行「参数速调」（params.py / .contest_params.json /
  scan_params 协议 + 锚校验 / apply_param_change 确定性零 LLM / 三路由 /
  两事件 / fx/params.js + ui/params.js / 范围外：任务联动、批量、自动烧录）；
  任务推进行补一句「⚙️ 参数速调卡片（独立于清单）」。
- 全量回归：pytest（Remove-Item Env:FIRSTEP_LAUNCHER）+ JS + 语言/PS1/README/
  CHANGELOG 检查全绿。
- 中文提交；spec/issues 随提，探针不提交。

## 验收

词条与代码一致 / 全量绿 / 工作树干净。
