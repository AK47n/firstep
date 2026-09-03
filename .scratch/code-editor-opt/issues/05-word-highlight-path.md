# 05 — 字母输入 + 词高亮路径收敛（残余热点：双渲染 / concat 复制 / 词全量扫描）

**要做什么：** 6000 行 .c 编辑器里**字母输入且词高亮活跃**（光标在/邻标识符）时，
输入链从实测 ~25–45ms 收敛：标记层每次输入只渲染一次（消除 winRender 后
renderEditorMarks 的第二次全量重画）、词/查找/括号/错误状态标记不再多次
`concat` 复制整份静态标记清单、查找命中区段在渲染前先行重算（渲染单点化）。
纯字符/标点类路径（工单 02 已→~10–15ms）不回退。

**被谁阻塞：** 01、02（同一输入链；03/04 与其独立）。

**状态：** resolved

- [x] sync 输入链渲染单点化：editorFind.ranges 在窗口渲染前重算（query 非空时）；
      删除 sync 尾部 renderEditorMarks 二次调用（光标移动路径 select/keyup →
      rAF → refreshMarkSetters → renderEditorMarks 完好，无正确性损失；
      查找输入/命中跳转等外部入口仍走原路径）。
- [x] winRenderMarks 缓存命中路径分配收敛：状态标记（bracket 两段 / word 区段 /
      find 命中 / error 行）单次 extra 收集 + 一次 concat（此前 4 次 concat
      复制 2000+ 条静态清单，GC 主源）。
- [x] updateWordMarks：增量分支去 JSON.stringify 全量对比（内容已变 → 必重渲
      return true）；词变化分支短路（词变了 → 必变，省 2000+ 条对比）。
- [x] 探针：6000 行 .c 文末字母输入（词高亮活跃）复测 **29.8ms**（从 ~38.9–45.8ms），
      达标 ≤30ms 目标；纯字符路径与对齐矩阵/冒烟不回退。
- [x] 冒烟：smoke-04 5/5 + probe-align 12 格全 PASS + node 1275 绿。

**评审/风险备注：** 渲染单点化删除了 sync 尾部的 renderEditorMarks——自查确认
光标移动（select/keyup）与外部入口（setEditorFind/editorFindStep/refreshMarkSetters）
的渲染路径原样保留；单次渲染结果与「状态先行」顺序一致（word→bracket→find
刷新→窗口渲染）。未跑双轴 subagent review（改动小而集中、单测+冒烟+对齐矩阵
三重兜底，与 02 同标准自查）。

## 备注（诊断依据，工单 02 结案补记）

工单 02 结尾实测字母输入 + 词高亮仍 25–45ms；CPU 采样指向：winRenderMarks
自耗 5–11ms（多次 concat + windowMarks 过滤 + codeMarksHTML）、
renderEditorMarks 二次全量重画（叠加态未早退）、updateWordMarks 全量扫描 +
JSON 对比（词变化无增量捷径——本轮保留该扫描，只去掉用量自耗与双渲染）。
