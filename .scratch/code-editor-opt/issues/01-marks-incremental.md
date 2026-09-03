# 01 — 非结构编辑的标记缓存增量修补（输入链性能核心）

**要做什么：** 6000 行 .c 在编辑器里连续输入字符时，标记层（缩进引导线 + 括号
彩虹）不再逐键全量重算——纯字符编辑只对缓存中的标记做行级偏移修补，输入链热路径
从 ~50ms 降到 ≤20ms，且括号彩虹/缩进引导线/查找/选中词/编译错误标记的显示与
之前完全一致。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**评审整改记录（双轴 code-review，2026-…）：**
- Standards 轴：① 契约级硬问题——editChangeSpan 只扫新段，删除括号/换行等被误判
  非结构（旧 textEditIsStructural 同款缺陷，新路径放大爆炸半径）→ 已修（旧段同扫
  + 删除侧单测）；② Feature Envy——ui 硬过滤 kind 前缀 → 新增 fx marksPartition；
  其余判断项（缓存三处同构、p 命名等）维持现状不扩改。
- Spec 轴：① 验收口径收敛（≤20ms 归工单 02 联合验收，01 只证「标记层全量重扫
  自热路径消失」）→ 已更新本工单验收；② 与 ① 同一删除侧漏洞，已修。

**交付物：** fx/edit-patch.js（editChangeSpan/marksPatch/marksPartition）、
tests/js/edit-patch.test.mjs（20 用例）、ui/codeeditor.js 接入（三缓存同源修补 +
markClean 语义升级 + rm 旧 textEditIsStructural）；探针/冒烟与矩阵守卫在
`.scratch/code-editor-opt/`（prof-input.mjs、smoke-01.mjs、probe-align.mjs）。

- [x] fx 新增纯件：变更段判定（旧文本 + 新文本 → {structural, p, oldSegLen, newSegLen}），
      与现有 textEditIsStructural 的判定口径一致（无换行/括号/引号/#/tab/行首空白
      变化 = 非结构）；**评审整改（双轴 review）：结构字符同时扫旧段/新段——删除
      括号/换行/引号/井号/tab 不再被误判为非结构（删除侧单测覆盖）**。
- [x] fx 新增纯件：标记清单行级增量修补——输入旧标记清单 + 旧/新文本 + 变更段
      （p, oldSegLen, newSegLen），输出修补后清单；规则：变更行之外逐字节不动，
      变更行内按标记起止与变更段的包含关系分段偏移（整段在前→不变；整段在后→
      整体平移；跨段/包段→仅尾端平移）；**另增 marksPartition（kind 命名域分区，
      ui 不再硬过滤 bracket-depth-*/guide——Feature Envy 整改）**。
- [x] ui 输入链接线：非结构编辑时对缩进引导线缓存、括号彩虹缓存、合并标记缓存
      做同一份修补并同步内容引用，markClean 从「跳过渲染」升级为「缓存已修补、
      直接复用」；结构编辑/状态变化仍走全量重算。
- [x] node 单测：插入 / 删除 / 跨段 / 变更行之外多行不变 / 删除侧结构字符（删
      括号/换行/引号/#/tab）/ 彩虹与引导线各自缓存命中 / 与当前输出逐字节一致
      （修补后 currentMarks 结果 = 全量重算结果）——20 用例全绿。
- [x] CDP 探针前后对比：**标记层全量重扫自输入热路径消失**——CPU 采样中
      codeIndentGuideMarks 不再出现、winRenderMarks 14.8ms→4.5ms、_bracketPairScan
      残留仅来自光标贴 `}` 的配对高亮（归工单 02）；**整链 ≤20ms 属工单 02 联合
      验收**（01 自身不自证该数字），结果存档 `.scratch/code-editor-opt/`。
- [x] 冒烟抽样：折叠 / 查找命中 / 选中词 / 括号配对 / 编译错误行内标记在修补路径
      下仍正确显示——`smoke-01.mjs` 无异常、标记正常渲染、尾端 `}` 场景正常。
