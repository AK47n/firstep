# 01 — 参考库文件名搜索 + 文件打开

**What to build:** 在参考文件库页搜文件名（如"TB6612"）能命中条目并直接打开文件（PDF 浏览器预览 / 文本内联 / 其他下载）。

**Status:** drafted（2026-08-11，主会话已核实现状，待用户开新终端执行）

## 现状（已核实）

- `search_references()`（reference_library.py:252）只按 title/type/anchor 子串过滤（keyword-only 参数，:267 全空提前返回全量），不搜文件名。
- `/api/references`（webapp.py:998-1011）只返回元数据；`FileResponse` / `StreamingResponse` 已导入（webapp.py:26），无需新增 import。
- 文件本体在两处：`library/references/<id>/<rel>`（文本）、`sources/materials/<title>/<rel>`（PDF 等备份，backup 脚本镜像相对路径）。
- **素材清单.txt 只存在于 `library/references/<id>/素材清单.txt`（不在 sources/materials 镜像里，已核实）**；是 reference.json `files` 之一。行格式：首行表头 `素材目录（<源绝对路径>）文件清单：` + 空行，之后每行 `相对路径  大小 bytes`（路径相对 sources/materials/<title>/；路径可含空格，解析须用 `^(.*?)\s+(\d+)\s+bytes$` 锚尾）。
- 路径安全原语已存在：`is_unsafe_path`（entry_store.py:145）——拒绝 `/` 开头、含 `:`、含 `\`、空段、`..`。
- 目录推导：`reference_library_dir = module_library_dir.parent / "references"`（config.py:122）；materials 备份根 = `module_library_dir.parent / "sources" / "materials"`（同源推导，webapp 无现成 helper，实施时局部取）。
- 真机目标已核实存在：`sources/materials/塔克R3两驱小车底盘资料/6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf`；`7 AT8236电机驱动资料` 目录同层级。
- 前端：筛选行 index.html:337-343（ref-filter-title/type/anchor）、filters 数组 :1292、清空 :1318、条目行渲染 :1300-1310（删除按钮在 :1307，查看按钮加其旁）、`formatSize` 帮助函数 :1280。
- 测试样板：test_reference_library.py:659 `test_search_references_filters_by_title_type_anchor`（`_reference_root(tmp_path)` + `add_reference(...)`）；test_webapp.py `client, context` fixture（:1989+）。
- ReferenceError 已在 webapp 错误映射登记（条目不存在 → 404 透传）。

## 实施

1. `search_references` 加 keyword 参数 `filename: str = ""`：子串匹配（大小写不敏感）该条目素材清单.txt 内容行 + files 中的路径；:267 提前返回条件纳入 filename。空 = 不过滤（向后兼容）。
2. 新端点 `GET /api/references/{entry_id}/files` → `list[{"path", "size_bytes"}]`：解析素材清单.txt 每行（跳过表头，正则锚尾取 size）；并入条目目录实际存在的文本文件（rglob，排除 reference.json，size 取真实 stat）；同路径条目目录文件优先（可服务副本）。
3. 新端点 `GET /api/references/{entry_id}/files/{path:path}`（**必须 `:path` 转换器，路径含子目录**）：is_unsafe_path 拒绝 → 400；先试 `library/references/<id>/<path>` 命中即 FileResponse（文本内联），不存在再试 `sources/materials/<title>/<path>`（PDF 带 media_type="application/pdf" 浏览器预览，zip 等走下载）；materials 根不存在 = 404 不炸；都找不到 404。错误映射走既有 ReferenceError → 404。
4. 前端：筛选行加 `ref-filter-filename` 输入框（placeholder"文件名 / 型号"），filters 数组 :1292 加 `["filename", "ref-filter-filename"]`，清空 :1318 补上。
5. 条目行 :1307 删除按钮旁加"查看"→ GET files 弹列表（path + formatSize）→ 点击按扩展名分流：.pdf 新窗口打开；.txt/.c/.h/.md 等 fetch 文本内联（esc）；其他触发下载。URL 按段 encodeURIComponent（路径含中文和斜杠）。
6. 测试：search filename 命中（素材清单行）/ 命中（files 路径）/ 不命中 / 空串向后兼容；files 列表解析（表头跳过 + 并入条目目录文件）；文件服务三路（条目文本 / materials PDF / 404）；穿越（`../`、`\`、绝对路径）被拒。

## 验收

- `python -m pytest` 全绿 + `mypy src` 干净。
- 真机：搜"TB6612" → 命中塔克条目 → 打开 TB6612FNG Datasheet.pdf 浏览器可预览；搜"AT8236"同样命中。

## 文件边界

`src/contest_generator/webapp.py`、`src/contest_generator/reference_library.py`、`src/contest_generator/static/index.html`、`tests/test_webapp.py`、`tests/test_reference_library.py`

**明确不动的：** entry_store.py（is_unsafe_path 只读）、reference_library.py 既有函数语义（add_reference / list_references / read_fulltext）、config.py、sources/materials 与 library/references 磁盘内容。
