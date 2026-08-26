# 06 — 疑似重复文件回收删除

**要做什么：** 数据健康从「只警示不删」升级为「可回收删除」（用户裁决 r2）：
疑似重复组内文件提供**行内单文件删除**与**详情弹窗组级「保留一份删其余」**，
删除 = 移入回收目录 `sources/.trash-pdf/<YYYY-MM-DD>/<rel_path 镜像>`（不真删，
git 忽略，可手动恢复 / git 历史双保险）；删除前弹窗确认（文件名 + 完整路径
+ 大小 + 回收去向说明）；仅重复组成员可删（f.isDup 命中），损坏 / 健康文件
不可删。

**被谁阻塞：** 04（重复组判据与行内徽章）

**状态：** resolved

- [x] 后端 `trash_pdf(root, rel_path, trash_dir)`：resolve_pdf 校验（非法 /
      缺失 → ReferenceError 中文）→ 移动（目标 = trash_dir/日期/rel_path 镜像，
      同名冲突 `_1/_2` 后缀，父目录自动创建）→ 返回相对 trash 根 POSIX 路径；
      素材根缺失 / trash 根不可写 → 明确错误（不裸 500）
- [x] config.py `pdf_trash_dir(materials)`（materials 兄弟 .trash-pdf，同源
      推导不新增配置项）；.gitignore 加 `sources/.trash-pdf/`
- [x] webapp `POST /api/pdfs/{rel_path:path}/trash`（注册在文件路由**之前**，
      与 /pages 同规则；ReferenceError → 400；返回 {"rel_path", "to"}）
- [x] 前端行内：重复组成员行操作列「删除」按钮（data-pdf-trash，仅
      f.isDup 命中渲染）+ 详情弹窗「删除此文件」「保留此文件，删除其余 N 份」
      （组级，列出组内成员）
- [x] 确认弹窗（复用 .ref-files-overlay）：文件名 / 完整路径 / 大小 /
      回收去向（sources/.trash-pdf/<日期>/）+ 参考镜像提示（「若被参考库
      条目引用，条目文件将无法打开」）+ 取消 / 确认；确认 → POST trash →
      toast「已移入回收目录」→ loadPdfs 重拉 + pdfPageCache.delete(rel_path)
- [x] tests/js：pdfTrashConfirmHTML / pdfDupRemainText / 组级成员清单纯函数
      子串断言（URL 编码、转义、组计数）
- [x] pytest：trash_pdf 全场景（移动 / 非法 400 / 缺失 400 / 冲突后缀 /
      trash 不入 list_pdfs）+ webapp 端点（200/400 + 路由顺序回归：
      trash 请求不被 file 路由吞掉）
- [x] 冒烟：自助一对同内容小 PDF → 出重复组 → 行内单删 → trash 落盘核对 +
      列表消失 + 组级「保留其余删」→ 脚本清理回收文件与恢复（真实素材
      零触碰）；全冒烟绿
- [x] 全量回归：tests/js / pytest / 冒烟

**实现说明：**
- 参考条目镜像边界：materials 内部分文件被参考库条目引用（resolve_entry_file），
  删除后该条目文件访问变 400——由确认弹窗文案提示，不自动解除引用（范围外，
  spec「需求变更」已注明）。
- 安全：rel_path 走 resolve_pdf（is_unsafe_path 防逃逸）；trash 根是服务端
  推导路径非用户输入；镜像保留批次层级 → 手动恢复直观（mv 回 materials）。

**评审结论（双轴）：**
- Standards：无硬违反。采纳 2 条值得修——.gitignore 新增条目补中文注释（GBK
  编码文件，原有中文行本就 GBK 并非乱码）；test_webapp.py 删函数内冗余
  `import time as _time`（模块级已有）。另 webapp.py /trash 路由注释收紧为
  诚实表述（POST 不被 GET 文件路由吞噬，与 /pages 同纪律注册防未来改动）。
  保留 1 条不修：前端提示文案硬编码 `sources/.trash-pdf/` + 日期（已注明
  「提示性，服务端实际路径为准」——加端点暴露 trash_dir 属过度设计）。
- Spec：忠实无 creep（删除目标语义 confirmTrashGroup=组-当前文件 / 确认弹窗
  四要素齐 / 仅重复组可删 / 去向与冲突后缀正确）。轻级观察 3 条（成员清单
  放确认弹窗属风格选择、标签「完整路径」= rel_path 领域语义、组级函数仅
  冒烟覆盖与工单清单一致）。
- 调试中确认的 3 个冒烟级 bug 均已修：确认后弹窗未关闭（残留遮挡）→ close
  入参；组级确认误 POST 保留对象 → confirmTrashGroup 删其余成员；fitz 句柄
  WinError 32（假 PDF 失败路径残留）→ pdf_page_count 显式 doc.close() +
  trash_pdf rename 5×200ms 短重试。
