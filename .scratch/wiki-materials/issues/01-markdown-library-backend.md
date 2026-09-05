# 01 — Markdown 资料库后端（清单 + 全文端点）

**要做什么：** 素材根（sources/materials）下全量 .md 文件的浏览后端——清单可按名字串过滤、单文件全文读取：非法路径（绝对路径/盘符/反斜杠/.. /空段）、非 .md、超 1MB 均回 400 中文；素材根缺失回空清单不炸。让「Markdown 资料」前端 tab 有数据可拉端到端可见（模块库/素材库浏览不再只有 PDF）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

- [ ] 新域模块 `md_library.py`：`list_markdowns(root, name)` → `[{rel_path, name, batch, size_bytes, mtime}]`（递归收集 .md 扩展名大小写不敏感；批次 = 第一级目录；按 (batch, rel_path) 排序；素材根缺失 = 空清单；过滤命中文件名/批次/完整路径任一）
- [ ] `resolve_markdown(root, rel_path)`：`is_unsafe_path` 校验 + 存在性 + .md 后缀，失败抛 ReferenceError（webapp 映射 400，与 pdf_library 同通道）
- [ ] 正文读取：`read_markdown(root, rel_path)` → `{rel_path, name, size_bytes, content}`；`MD_FILE_MAX_BYTES = 1MB` 超限 400（照 codeview 先例）；utf-8 errors="replace" 读全文
- [ ] webapp 路由：`GET /api/materials-md`（清单 + name 过滤）、`GET /api/materials-md/{rel_path:path}`（全文 JSON）；路由注册位置与 pdf 路由区相邻
- [ ] `tests/test_md_library.py`：清单字段/批次推导/过滤/排序、路径安全拒绝面全覆盖、非 .md 拒绝、超限拒绝、素材根缺失空清单、webapp 两端点两态（正常 + 400 中文）
- [ ] 全文检索自查：`lckfb-地猛星移植手册/` 70 篇 + 2 篇索引在清单中，`sensor--mpu6050-six-axis-sensor.md` 可读全文
