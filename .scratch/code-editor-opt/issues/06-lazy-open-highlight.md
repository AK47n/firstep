# 06 — 大文件打开延迟：窗口惰性高亮（消除全量 tokenize + 冗余 currentMarks）

**要做什么：** 打开 6000 行 .c 从实测 ~227ms 降到目标 ≤80ms：打开时不再对全文
6000 行一次性 `highlightCodeLines` tokenize + 构建 6000 条高亮 span（窗口化渲染
只画 ~56 行，其余行的高亮是白算），改为窗口行**惰性现算**（滚动即补，缓存命中
后零成本）；同时消除 `renderPane` 给 windowed 模式预计算的 `currentMarks()`
（codeEditorHTML 在 windowed 下根本不用该参数，白扫一次全库引导线 + 括号）。

**被谁阻塞：** 01、02（静态缓存 / 窗口缓存）；05（同一输入链，先合 05）。

**状态：** resolved

- [x] winBuild：hl 数组惰性占位（null）+ hlLineHtml 单行现算回填（lang 存缓存）；
      winRender 切片与 winPatchRow 取用前现算——打开不再全量 tokenize 6000 行。
- [x] renderPane：windowed=true 时不再预计算 currentMarks()/marksForView()
      （codeEditorHTML windowed 分支不消费；marksCache 由 winRenderMarks 正常构建）。
- [x] winApplySize 宽度探针脱离文档流（固定定位单行 span + 计算样式字体拷贝）——
      消除在 12.6 万 px 高滚动容器里 getBoundingClientRect 的整树深布局。
- [x] 探针（probe-open.mjs 精确 await 计时 + 阶段拆解）：打开 6000 行 .c =
      **fetch ~58ms + 渲染 ~195ms ≈ 253ms**（100KB 文件 + outline 服务端扫描 +
      **108KB textarea 全量 + 12.6 万 px 高巨盒布局 = 渲染大头，属「三明治
      textarea 全量」架构固有成本**）；全量 tokenize 与冗余 currentMarks 已移除
      （首帧窗口 56 行、滚动到中/底部窗口行正常补缺、无 6000 行预高亮）。
      **≤80ms 目标未达标**——已证实剩余成本不在前端的预计算，而是 textarea 全量
      + 巨高布局，需 textarea 视口化（大改，不在本轮）——如实记录，不虚标。
- [x] 回归：node 1275 绿 + smoke-04 5/5 + probe-align 12 格全 PASS（惰性高亮
      下窗口/标记/行号三层 1:1，滚动补缺无损）。
