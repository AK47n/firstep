# 02 — 文件树浏览：母版全部文件树 + 树内文件内容预览

**要做什么：** 母版详情弹窗加「全部文件」区——后端提供平台目录下全部文件
清单（统一噪音跳过 + 一次算好 size）与树内文件内容端点（平台目录内 +
路径安全 + 二进制拒绝 + 超 1MB 拒绝，三类中文 400）；前端渲染为递归可收起
树（原生 details/summary，零 JS 收起逻辑），点树内文本文件即加载全文到
既有内容箱（复用 memo 与三态）；关键文件清单保留为快捷入口，两条路线并存。

**被谁阻塞：** 01（同改详情弹窗 / masterDetailHTML，先 01 后 02 防冲突；
且树文件内容端点与 01 的 stats 同吃目录遍历口径）

**状态：** resolved

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

（2026-08-27 完成）

- 后端：master_store.py 新增 TreeFileInfo + `master_tree_files`（统一噪音跳过、
  全路径排序确定性）+ `read_master_tree_file`（路径安全拒绝面与
  entry_store.is_unsafe_path 对齐：`..` 任意层级 / 空段 / 首字符 `/` / 反斜杠 /
  冒号（NTFS ADS），另有 resolve 后必须落平台目录内的兜底；NUL 二进制拒绝；
  超 TREE_FILE_MAX_PREVIEW_BYTES = 1MB 拒绝；utf-8 errors="replace" + 换行
  归一化（与 read_master_file 同读法））；webapp 新增 GET
  /api/masters/{platform}/tree 与 /tree/{path:path}（既有 /files 白名单端点
  零改动）。
- 前端：fx/master.js 新增 masterTreeFileURL / buildMasterTree / masterTreeNodeHTML
  （目录 = 原生 details/summary 零 JS 收起；兄弟排序目录在前、同级按码点序
  ——确定性，不用 localeCompare）；masterFileURL 与 masterTreeFileURL 收敛进
  共享 helper _masterFileURL（评审去重）；masterDetailHTML 关键文件清单后加
  「全部文件」段（data-master-tree 容器）；ui/master.js 新增
  loadMasterTreeState（platform 级 memo，business 400 缓存）/ renderMasterTree /
  wireMasterTree，点树文件 → 与关键文件共用同一内容箱（memo key =
  platform/path 不变，openMasterPath 共享三态）；loadMasters 成功拉新列表
  时 masterTreeCache 整体失效（库变树不旧）；index.html 树样式。
- 测试：test_master_store.py 增 9 例（清单噪音跳过/确定性、内容读取、穿越
  六形态、二进制、超限、缺失、平台不存在）；test_webapp.py 增 7 例（tree
  清单 / 内容 200 / 穿越与二进制与超限与平台缺失 400——穿越用例须 safe=""
  编码斜杠：裸 `..` 段会被 httpx 归一化删掉变 404 绕过路由）；test_autocommit.py
  登记 master_tree_files/read_master_tree_file（read）；tests/js 增 4 例
  （树构建嵌套/排序、树 HTML 递归与转义、URL 拼装）。
- 回归：pytest 全量 2491 绿、node --test 458/458；真实库实扫（stm32 42 文件 /
  mspm0 9 文件，ml_libs/ml_adc.c 与 targetConfigs/readme.txt 读取成功，
  穿越路径 400）。
- 评审：code-review 双轴——Standards 硬缺陷 1（路径安全弱于 is_unsafe_path
  先例：补 `:`/`\\`/首字符 `/` 拒绝面，已修）+ 判断项 3（URL helper 共形重复
  → _masterFileURL 收敛已修；openMasterFile 转发层保留——一行的命名转发器
  可读性优于调用点内联；memo 键双端点共享经评估无害——同一磁盘文件同换行
  归一化，注释已说明）；Spec 无缺项（树排序「目录在前」口径写入 spec 明示；
  树错误文案删误导句；master_tree_files docstring 措辞修正为全路径排序）。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
