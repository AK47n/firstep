# 02 — 文件树浏览：母版全部文件树 + 树内文件内容预览

**要做什么：** 母版详情弹窗加「全部文件」区——后端提供平台目录下全部文件
清单（统一噪音跳过 + 一次算好 size）与树内文件内容端点（平台目录内 +
路径安全 + 二进制拒绝 + 超 1MB 拒绝，三类中文 400）；前端渲染为递归可收起
树（原生 details/summary，零 JS 收起逻辑），点树内文本文件即加载全文到
既有内容箱（复用 memo 与三态）；关键文件清单保留为快捷入口，两条路线并存。

**被谁阻塞：** 01（同改详情弹窗 / masterDetailHTML，先 01 后 02 防冲突；
且树文件内容端点与 01 的 stats 同吃目录遍历口径）

**状态：** ready-for-agent

## 验收标准

- [ ] master_store 域函数：`master_tree_files(masters_dir, platform)` 返回
  TreeFileInfo 元组（path / size_bytes，iter_project_files 同源噪音跳过、
  排序确定性；平台不存在同 get_master 文案）；`read_master_tree_file`：
  路径安全（父目录解析落平台母版目录内，任意层级 `..` 拒绝）、NUL 二进制
  拒绝、超 TREE_FILE_MAX_PREVIEW_BYTES（1MB）拒绝——三类均中文
  MasterError；utf-8 errors="replace" 读取
- [ ] API：GET /api/masters/{platform}/tree（文件清单一次算好）；
  GET /api/masters/{platform}/tree/{path:path}（内容 200 / 穿越与二进制与
  超限与平台不存在 400 中文）；既有 /files/{path} 白名单端点零改动
- [ ] fx 纯函数：`buildMasterTree(files)`（扁平清单 → 嵌套节点）与
  `masterTreeNodeHTML(nodes)`（递归 details/summary，文件行带 data 属性、
  目录与文件按路径排序）；`masterTreeFileURL(platform, path)`（逐段
  encodeURIComponent，与 masterFileURL 同拼法）
- [ ] UI：详情弹窗在关键文件清单后加「全部文件」段（树默认展开、噪音目录
  不出现）；点树文件行加载到内容箱（memo 复用，key = platform/path），
  加载失败中文原因 + 可重试
- [ ] pytest：test_master_store.py（tree 清单形状与噪音跳过 / 树文件读取
  三态 400：穿越、二进制、超限 / 平台不存在）+ test_webapp.py（tree 与
  tree 文件端点 200/400）
- [ ] tests/js：master-ext-browser.test.mjs（树构建嵌套正确性、树 HTML
  递归渲染与排序、URL 拼装）
- [ ] 冒烟：真实母版详情 → 树展开（目录数 / 文件数实况断言）→ 点一个非
  关键文件（如 stm32 user/ 下源文件）加载成功子串断言 → 点二进制/缺失
  路径得 400 中文（探针亦可）
- [ ] 中文提交

## 实施记录

（待实施）
