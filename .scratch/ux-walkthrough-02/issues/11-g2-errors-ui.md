# 11 — G2 前端错误可复制 + SSE 兜底统一（parseError）

**要做什么：** ①500/长错误不再只用 2.5s 即逝的 toast：改常驻内联块（可选中复制）或 toast 加「复制」按钮并延长停留（至少 6s）；②既有 toast-only 调用点（交付/参考/PDF/模块库/最近记录等）对长错误走新路径；③SSE 流终态统一走共享错误解析（含 HTTP 状态）替换 6 处内联 `err.detail || "请求失败（HTTP …）"`；④内部错误提示沿用既有「这是工具内部问题，请复制反馈」意图且必须可复制。

**被谁阻塞：** 10（G1 后端错误人话化）——文案源对齐后做前端展示路径。

**状态：** resolved

- [x] 长错误（长度阈值/500）渲染为常驻错误块（toast ms=0 常驻 + 复制按钮，点 ✕ 关闭），可选中复制；短错误仍可用 toast
- [x] toast 支持「复制」按钮（长错误场景），常驻不自动消失（剪贴板守卫 + execCommand 回退）
- [x] 全部 SSE 流（推荐/修订/修复/任务/参数/母版）预流 !resp.ok 与流内 error 终态走同一解析函数（parseHttpError/parseError），消息含 HTTP 状态
- [x] parseError 为 fx/ 纯函数并有 tests/js 用例（HTTP NNN / detail / 超时 / 网络断 / 未知 / 悬空冒号）
- [x] node --test + pytest 全量通过
