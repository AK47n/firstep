# 06 — 列表中文标题（后端 title 字段 + 前端行渲染）

**要做什么：** 让「Markdown 资料」列表每行一眼可读：`list_markdowns` 每条新增 `title`
（首 8KB 内首个 `^# ` 标题，非本批产物回退文件名）；前端行渲染改为中文标题为主行
（点击打开原文）、文件名小字第二行（muted），打开/预览/复制路径按钮不变。

**被谁阻塞：** 无——列表 title 取自文件内容，不依赖重抓（05 后标题更准，滚动兼容）。

**状态：** resolved

**结论：** 2026-09 完成并提交。md_library.first_heading_title（首 8KB 首个 `^# ` 行，围栏 #include 不误判）；list_markdowns 每条加 `title`（无标题回退空串）；mdRowHTML 主行 = 中文标题 + 文件名小字第二行（md-row-file CSS；title==name 时不显示第二行）；后端 39 相关测试 + JS 行渲染测试通过。

- [x] `list_markdowns` 输出含 `title`：读首 8KB，取首个 `^# ` 标题；无 → 回退 `name`；
      断言不影响既有字段与排序。
- [x] `fx/md.js mdRowHTML`：主行 = title（data-open-md 不变），文件名第二行小字 muted；
      空态/预览壳不动。
- [x] 后端测试（test_md_library/test_webapp 清单断言）+ JS 测试（行渲染含标题、回退文件名）。
- [ ] 浏览器验证：批量列表首列显示中文标题、文件名小字；预览/打开不受影响。（待用户刷新核验）

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
