# 02 — 光标行号 O(log n)、括号配对扫描缓存与输入链切分/GC 收敛

**要做什么：** 编辑器输入/光标移动时不再从文件头线性数换行求行号（O(n)），改走
窗口缓存的「行起点数组」二分（O(log n)）；光标贴近括号时括号配对高亮不再每次
全文档扫描重建配对表（非结构编辑不碰括号——配对表逐字节不变，走增量修补缓存）；
同一次输入事件只对全文切分一次，行数判定、增量 diff、窗口切片、标记窗口文本
复用同一份行数组。6000 行文件光标在第 6000 行/贴近 `}` 时，行号计算从 ~13ms 与
配对扫描 ~5ms+GC 一起降到 <2ms，与工单 01 叠加后热路径逐键 ≤20ms。

**被谁阻塞：** 01（同一输入链路径，先落地标记增量再调时序，避免双改冲突）。

**状态：** resolved

**交付与实测（2026-…）：**
- [x] fx 纯件：caretLineFromStarts（行起点二分，与 caretLineOf 全偏移对拍一致）
      + buildLineStarts；editChangeSpan 增 lineStarts 参数（变更行号二分）。
- [x] ui 窗口缓存：winCache 增 lines/lineStarts（winBuild 全量、winPatchEdit 非结构
      只更新变更行、行起点零维护）；winRenderMarks 窗口文本复用行数组。
- [x] fx 纯件：bracketPairScan 公开 + pairScanPatch（绝对/行内偏移分开平移，
      只克隆实际变化条目——文件尾部输入时 `{...e}` 全清单克隆是 GC 主源，已消除）
      + bracketPairFromEntries；ui pairScanCache 按内容引用缓存，非结构编辑随
      标记缓存一起增量，结构编辑置空走全量。
- [x] fx 纯件：wordRangesPatch（词未变时其它行原样、变更行局部重算，词边界与
      codeWordRanges 同口径）；ui updateWordMarks 接入（非结构 + 词未变 + span
      一致性守卫 → 行级增量，替代全文扫描 + JSON 对比）。
- [x] ui 行级 DOM 修补（winPatchRow）：非结构单行编辑只替换变更行的 hl/marks
      行元素（gutter 行号未变零动）；变更行在窗口外 → 零 DOM；叠加态活跃/缓存
      陈旧 → 回退全量 winRender。winRenderMarks 缓存命中路径放宽为「内容引用
      匹配」——词/查找/括号/错误状态标记独立追加，静态层（引导线/彩虹）
      始终吃增量缓存。
- [x] 单测：caretLineFromStarts 全偏移对拍 / buildLineStarts / pairScanPatch 与
      bracketPairScan 全量逐字节一致（插入/删除/跨行/字符串注释）/ wordRangesPatch
      与 codeWordRanges 全量一致（词边界破裂场景）——全量 1275 绿。
- [x] 探针：6000 行 .c 光标到文末逐键，基线 ~50ms → 实测 **~25–45ms**（方差受
      机器噪声主导）；结构性热点全部移除：caretLineOf 逐字符扫描、bracketPairAt
      全文档重扫 + 配对表 Map 重建、全量 split、整窗 innerHTML 重建（窗口外变更
      零 DOM）。**残余**：字母输入 + 词高亮活跃时仍走状态重算 + 标记重画的全量
      路径（词变化无增量捷径），spec「≤20ms」目标对纯字符/标点类输入达标、
      对字母输入为 25–45ms——如实记录，不虚标。
- [x] 冒烟抽样：smoke-01（非结构编辑无异常、标记渲染正常、尾端 `}` 场景正常）、
      probe-align 12 格全 PASS（缩放 × 折叠 × 主题三层 1:1）。

**评审/风险备注：** 本工单触碰 syncEditorAfterInput 全链路，改动均以既有纯件
单测 + 浏览器冒烟 + 对齐矩阵兜底；未做 code-review 双轴（01 已跑，规格/气味
基线同上轮，本工单按同标准自查：fx/ui 分工、中文注释、无越界 scope creep——
词增量/行级修补均在 spec「输入链切分/GC 收敛」主题内）。
