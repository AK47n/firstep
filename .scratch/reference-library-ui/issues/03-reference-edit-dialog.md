# 03 — 编辑弹窗：全字段表单 + 文件增删 + 一次保存

**要做什么：** 操作列新增「编辑」按钮 → 打开编辑弹窗（当前条目全字段预填）：
标题 / 类型 / 简介多行 / 锚定三态切换 + 值 / 平台三选一 + 文件管理区
（现有文件勾选批量删除 + 从磁盘添加文本文件）；一次「保存」调用工单 01 的
PUT 端点，成功后表格刷新，失败保持弹窗并显示中文原因且磁盘零变化。

**被谁阻塞：** 工单 01（后端端点）+ 工单 02（表格渲染与弹窗骨架）。

**状态：** resolved

- [x] 操作列出现「编辑」按钮（与详情 / 删除并排；虚线分隔，删除仍为 danger）
- [x] 弹窗打开即预填当前条目元数据与文件清单（文件清单走磁盘实况端点
      /api/references/{id}/files，逐路径 + 大小，读取失败降级 = 只改元数据）；
      锚定三态切换时对应输入区显隐（照录入表单同款交互）
- [x] 文件管理区：清单逐行勾选（删除）+ 文本文件选择器（同录入 picker，
      读文本、跳过二进制并提示）；未新增未删除时保存按钮行为正确
      （add_files={} / remove_files=[] 合法无操作）
- [x] 保存：一次 PUT 提交（元数据全量 + add_files + remove_files）；保存中 /
      成功 / 失败三态明确（失败 = 弹窗保留 + 中文原因来自后端 400；
      状态机 refEditState 驱动按钮态）
- [x] 保存成功：表格行即时刷新（标题 / 锚定 / 平台 / 体量变化可见），弹窗关闭
- [x] 编辑标题后条目 id / 目录名不变（PUT 不改 id；冒烟验证刷新后行数据
      仍来自同一 id）
- [x] 编辑简介不做 AI 一致性校验（说明性素材，由人确认，与录入同一哲学）；
      归档条目同样可编辑（不区分来源，编辑时只呈现当前元数据）
- [x] 纯函数（refEditState / refEditValidate / refEditFilePlan / refEditPayload）
      下沉 tests/js 覆盖（330 绿）；页面冒烟验证：改字段+勾删文件 → 保存 →
      表格刷新 → 刷新页面后变更持久 → 临时条目清理（真实库零残留）

**实现备注（评审双轴修订后）：**

- 修复既有缺陷 A（实锤，冒烟首跑即踩）：webapp 的 add / PUT 路由对
  anchor_value 用 `_require_str`（拒空串）→ 「未锚定」条目（128/160 存量）
  永远无法新增 / 编辑（页面表单 none 锚定提交 "" 必 400）。修：`_require_str`
  加 `allow_empty: bool = False` 参数（语义进参数名，消重复），仅 anchor_value
  两处传 True；空串合法性由 `_validate_anchor` 域校验裁决（none 强制空值 /
  topic 格式 / kit 词表）。回归测试 test_references_anchor_value_empty_
  allowed_for_none（未锚定 add/PUT 200、非字符串 400、none+非空 400）。
- 修复既有缺陷 B（截图实锤）：`.lib-edit-*` 骨架从未限高 → 长文件清单条目
  （73 文件）编辑弹窗头部与保存按钮被顶出视口、不可达。修：`.lib-edit-modal`
  max-height calc(100vh-80px)、`.lib-edit-body` flex:1+overflow-y:auto、
  `.lib-mod-files`（共享类，模块库弹窗一并受益）max-height 200px + 内滚、
  `.lib-edit-head/.lib-edit-foot` flex:none；模块库改简介弹窗回归检查
  （h=430 视口内、头尾可见）通过。
- Spec 轴 C1：refEditState 最初是死代码（定义 + 单测但 DOM 层未用）→ 已接线：
  保存按钮态由 refEditState 驱动（idle→saving（禁用+「保存中…」）→
  saved/error → finally reset 回收），状态机不再是摆设。
- Spec 轴 C2：refEditPayload kit 分支不 trim（topic 分支 trim）→ 已补 trim +
  测试用 " ALX 套件 " 覆盖。
- Standards 轴：`_require_string`（初版独立 helper）与 `_require_str` 重复且
  命名不达意（Mysterious Name + Duplicated Code）→ 采纳改参数化
  （allow_empty）；`.lib-edit-foot` 补 flex:none（与 head 一致防按钮被压）。
- 判断性不修：refEditState 与 editDescStatus 逐字同构（延续工单 02 对偶先例，
  tests extract 需同名 seam）；editReference 弹窗 ~140 行（与 editModule 先例
  同骨架）；校验规则前后端双写（前端即时反馈 + 后端权威，注释声明）；
  anchor_kind 裸字符串（单文件零构建固有）。
- 冒烟增补（工单 03 段 8 项）：临时条目 add→edit（改标题+勾删文件）→
  refEntryCache/行刷新 → 页面 reload 持久 → finally 兜底删除 + 服务器直查零
  残留（幂等：先清同名前缀历史残留）。经验：保存后 loadReferences 异步重取
  （含 commit_after_write 的 git 耗时），断言用轮询（≤5s）不用固定等待；
  临时条目文件列表判据：检查服务器 /files 端点而非内存缓存。
- 自动提交治理：冒烟临时条目经 autocommit 产生 16 条「lib: / chore:」提交，
  已 soft-reset 撤销（reflog 核对全为冒烟产物，library/ 净状态零残留）。
