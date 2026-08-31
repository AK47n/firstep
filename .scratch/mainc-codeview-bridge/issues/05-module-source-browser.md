# 05 — 模块源码速查

**要做什么：** 新增只读端点 `GET /api/modules/{slug}/files/{path:path}` 读取模块库内文件内容（安全拒绝面与母版文件树同口径：`..` 任意层级 / 空段 / 首字符 `/` / 反斜杠 / 冒号 / resolve 后必须落在该模块目录内 / NUL 二进制 / 大小上限，全部 400 中文）；模块详情弹窗的清单文件行可点击，懒加载展示源码（行号 + 高亮，复用代码查看器渲染观感），带 memo 三态。元数据部分不变。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 端点可读取模块库平台条目内 .c/.h 文件内容（UTF-8 errors=replace + 换行归一化）。
- [x] 安全面：穿越路径 / 越出模块目录 / NUL 二进制 / 超限 / slug 不存在 → 400 中文（Python 侧有测试）。
- [x] 详情弹窗文件行点击 → 加载中 → 源码视图（行号 + 语法高亮，观感与代码查看器一致）；重复打开零重复请求（memo）。
- [x] 业务 400 缓存可重试；网络 / ≥500 不缓存。
- [x] 弹窗元数据区（简介 / 平台条目 / 硬件身份）保持不变。

## 实现说明

- 后端：library.py `read_module_file(library_root, slug, rel_path)`（拒绝面与 read_master_tree_file 同口径：首字符 `/` / `:` / `\` / 任意层级 `..` 与空段 + resolve 后必须在模块目录内兜底 / NUL 二进制 / MODULE_FILE_MAX_PREVIEW_BYTES=1MB；UTF-8 errors=replace + 换行归一化；返回 {path, size_bytes, content}）+ `GET /api/modules/{slug}/files/{path:path}`（LibraryError 既有 400 映射）。
- 前端：fx/module.js moduleInfoHTML 文件行渲染为可点击按钮（data-mi-file，esc 转义）+ 弹窗底部源码槽（data-module-source hidden 初始态）；ui/module-source.js `bindModuleSource(modal, slug)`（多平台每段 .mi-files 点击委托 → 懒加载 → codeViewHTML(languageOf) 渲染 = 代码查看器同观感；memo 缓存业务 400 / 网络 ≥500 不缓存可重试，对偶代码查看器先例）。
- 弹窗单入口 openModuleInfo（推荐卡 + 模块库 tab 共用）自动获得源码区（bindModuleSource 在 openModuleInfo 内接线），元数据区零改动。
- 测试：Python 11 项（单测 8 + 端点 3，穿越用编码形态 %2e%2e 送达服务端解码后判）；JS module-info-dialog 增 data-mi-file/源码槽断言；smoke-05.mjs 9 项（真实 led 模块弹窗 → 文件行点击 → 行号+高亮渲染 → 切换文件 → 端点穿越 400）；node --test 970 全绿。
- 踩坑记录：运行中的 webapp 服务是旧代码（无 --reload），新端点 404 → 重启后冒烟通过——改后端后需重启本地服务。
- 备注：真实模块库 led 的 stm32 段 files 为空（实现内嵌母版语义）——弹窗只在有文件的平台段显示可点击行，空段保持「实现内嵌母版」文案（冒烟改用 mspm0 段路径验证）。
