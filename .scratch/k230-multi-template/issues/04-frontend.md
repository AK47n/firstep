# 04 — 前端模板下拉 + done 回显

**要做什么：** 步骤 6 模块卡：选中带多模板的模块（k230）时显示模板下拉（name + description 来自 manifest），默认选中 default；选择随生成请求 python_templates 透传；生成 done 载荷回显所选模板；模块库页展示多模板能力。

**被谁阻塞：** k230/02（模板选择请求管线）、k230/03（矩形识别模板落地）。

**状态：** resolved

- [ ] 模块卡渲染：python_artifact.templates 长度 > 1 时显示模板下拉（含 description 提示），默认 default
- [ ] 生成请求带 python_templates（仅当用户改过默认）；done 载荷回显所选模板
- [ ] 模块库页模块详情展示多模板清单（id/name/description）
- [ ] 不选模板（默认）路径零 UI 变化（回归护栏）
- [ ] 真机验收：浏览器手测 k230 模板切换 → 生成工程 main.py 内容随选择变化

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
