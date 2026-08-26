# 01 — 后端：列表加 mtime + 新增页数端点

**要做什么：** PDF 资料库页拿到两个新数据能力——列表每条目带修改时间
（mtime，UNIX epoch 秒），以及按文件路径查询页数（页数端点，PyMuPDF 按需
读取单文件）。页数端点对损坏 / 0 字节 / 不存在的 PDF 返回 400 中文报错，
与 resolve_pdf 同通道；页数路由必须注册在文件预览路由
`/api/pdfs/{rel_path:path}` **之前**（path 贪婪匹配会吞掉 `xxx.pdf/pages`），
并补路由注册顺序回归测试。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] `list_pdfs` 返回条目含 `mtime`（int，epoch 秒，`path.stat().st_mtime`
      取整）；排序键 (batch, rel_path) 不变；素材根缺失仍返回 []
- [x] 新增 `pdf_page_count(root, rel_path)`（pdf_library.py）：resolve_pdf 校验
      路径安全与存在性（复用，非法/不存在 → ReferenceError）→ PyMuPDF
      `fitz.open` 读页数；0 字节/损坏 → ReferenceError（中文文案）；
      软导入 fitz（ImportError = 服务器环境缺陷 → RuntimeError 500，spec 已
      注明与 extraction 静默降级语义区分——页数无处可降）
- [x] 新增路由 `GET /api/pdfs/{rel_path:path}/pages` → `{"pages": N}`；
      **注册在文件路由之前**；错误经 error_to_http 映射 400
- [x] pytest：test_pdf_library.py（mtime 字段存在且为 int / pdf_page_count
      合法多页 PDF 用 topic_pdf_fakes.make_multi_page_pdf 构造断言页数 /
      0 字节与损坏 → ReferenceError / 不存在 → ReferenceError / 非法路径 →
      ReferenceError）；test_webapp.py（/api/pdfs 带 mtime / 页数路由成功 /
      非法路径 400 / 损坏 400 / 不存在 400 **且文件预览路由仍正常**
      ——路由注册顺序回归）
- [x] 既有端点零改动回归：`GET /api/pdfs`（含 `?name=` 子串参数）、
      `GET /api/pdfs/{rel_path:path}`（预览）行为不变
- [x] 全量 pytest 绿（2393 → 2402，新增 9 项不倒退）

**评审结论（code-review 双轴）：**

- Spec 轴：缺失 0 / 范围蔓延 0 / 偏差 1——ImportError 语义与 spec 原文
  「与 extraction 先例一致」相悖（实现为 RuntimeError→500）。决议：保留
  大声失败（PyMuPDF 是声明依赖，缺库 = 部署缺陷，伪装 400「文件损坏」会
  误导排查），spec 措辞已修订注明（评审定稿）。
- Standards 轴：文档化标准 0 硬违规；两条判断句已修复——① `except
  Exception` 过宽掩码 → 收窄为 `fitz.FileDataError`（含子类
  EmptyFileError，0 字节与损坏实测均归此类），其余异常放行 → 真 bug 500；
  ② 路由函数名 `pdf_pages` 语义错位（返回页数非页列表）→ 改名
  `pdf_pages_count`。第三条判断句（fitz 软导入第三份拷贝、语义已分叉）经
  权衡保留：跨模块提取共享接缝是投机泛化，extraction 与 pdf 的降级/抛错
  语义差异真实，docstring 已说明理由。
- 遗留说明：工作区另有一批与工单无关的暂存/未暂存改动（参考库锚定治理
  提交 e8b8d90 / 8db9d67 已花掉暂存区；CHANGELOG 自动提交钩子产生的杂项），
  本轮提交只含本工单文件，不碰其它。
