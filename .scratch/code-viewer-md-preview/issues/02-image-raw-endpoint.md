# 02 — 后端图片二进制端点

**要做什么：** 新增代码查看器图片读取端点 `GET /api/code/raw?dir=&path=`：返回打开目录内图片文件的字节（供 .md 预览的 `<img>` 直接引用）。安全判定与既有文件端点同一组（路径安全单源 + resolve 在根内 + 文件存在）；仅服务图片扩展名白名单（png/jpg/jpeg/gif/webp/bmp/ico/svg）；大小上限 8MB 超限 400 中文；media_type 手写映射（不依赖 platform mimetypes）；成功响应带 Cache-Control private max-age=3600。错误统一 400 中文（复用 CodeViewError）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `GET /api/code/raw?dir=&path=` 返回图片字节 + 正确 media_type（png/jpg/jpeg/gif/webp/bmp/ico/svg 各一断言）。
- [x] 路径安全：首字符 `/`、`:`、`\`、`..`、空段及 resolve 后越出根目录 → 400 中文（与 read_code_file 同一拒绝面）。
- [x] 非图片扩展名 / 文件缺失 / 超过 8MB / 目录不存在 → 400 中文；图片文件内的 NUL 字节不拒绝（二进制读取语义）。
- [x] 端点只读、零写侧；响应头含 Cache-Control: private, max-age=3600。
- [x] tests/test_codeview.py 新增域函数用例（白名单命中/非图片拒绝/穿越/超限/缺失）；tests/test_webapp.py 新增端点用例（200 + media_type + 400 中文）。
- [x] 全量 pytest 绿（既有代码查看器用例不回退）。

## Comments

- 实施（TDD）：先补 tests/test_codeview.py（code_raw_media_type 8 扩展名映射 + 大小写宽容 + 非图片拒绝；read_code_file_bytes 命中/非图片/穿越 6 例/缺失/根缺失/超限）与 tests/test_webapp.py（200+media_type+cache-control / 穿越 / 缺失 / 非图片 / 缺参 422），红 → 实现域函数与端点 → 绿。
- 双轴评审：Standards——无硬违反；按建议抽 `_resolve_in_root`（read_code_file 与 read_code_file_bytes 共用安全前置，消除 7 行同构漂移风险）；命名保留 spec 定名 read_code_file_bytes（docstring 已注明图片语义）；端点对 code_raw_media_type 的二次调用保留（域内白名单先行 = 非图片不读盘的安全时序，端点再取一次 media_type 为字典查找，代价可忽略）。Spec——唯一留白：NUL 字节图片放行无测试，已补 test_read_code_file_bytes_allows_nul_inside_image；缺参 422 与 /api/code/file 同口径并注明有意为之。
- 验证：定向 pytest 42 项绿；全量 pytest 3007 项绿（含新 NUL 用例）。
