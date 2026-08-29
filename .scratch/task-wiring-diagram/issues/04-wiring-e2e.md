# 04 — 接线图端到端上线

**要做什么：** 用户在任务卡与结果面板真实看到接线图（图 + 原文并存）；数据读不到时按三级退化，绝不出错或空白。

**被谁阻塞：** 01（接线快照落盘）、02（步骤报告接线引用协议）、03（接线图渲染纯件）

**状态：** resolved

- [x] 新增只读端点：output_dir → {platform, board, rows}；目录无快照文件 → 空载荷（200）；快照坏 JSON → 空载荷（不 500，条目级容错与既有任务数据读取风格一致）
- [x] 任务卡「下一步要做」粘性摘要框内：接线图置于顶部 + 原 user_action 文字保留在图下方（图文并存）
- [x] 结果面板步骤报告块内同样渲染（同一渲染函数、同一数据装配）
- [x] 三级退化（任一情况不报错、不空白）：① wiring 合法 → 接线图（本步高亮）；② wiring 空 / 校验失败 / 无快照但任务有 resources → 资源高亮板图（复用既有资源总览板图渲染器与 resourceIsHardware 判据）；③ 都没有 → 纯文字（现状行为）
- [x] 「显示全部接线」折叠开关：默认只显示本步高亮线；展开显示其余线（淡显）；开关状态不持久化（范围外）
- [x] 全量回归绿（pytest 既有套件 + tests/js 既有套件）；新增 pytest（端点三类输入：正常 / 无文件 / 坏 JSON）与 tests/js（任务卡 / 结果面板三输入域渲染）成文

**答案：** webapp.py GET /api/wiring（output_dir 查询参数 → {platform, board, rows}；缺参/无快照/坏 JSON/版本不符/目录不存在 → 200 空载荷 {platform:"", board:None, rows:[]}，read_wiring_snapshot 容错复用）；fx/task.js wiringSectionHTML 支持每任务装配 wiringOpts(task)（perComputed 三参避免 wiringOpts 双执行——评审整改）+ data-wiring-uid 占位 host（card:/result: 分开）；ui/wiring.js 新胶水（loadWiringAssets 快照 + /api/boards 回退两级缓存单飞、wiringOptsFor/attachWiringInputs/wireHosts、initWiringToggle 原位重渲委托、tier-2 退化图 = resourceBoardHTML 按本任务 resources 过滤 + conflictLegend:false 单任务视图）；ui/generate-tasks.js tasksRender/tasksRenderResult 接 wiringOpts + tasksWiringEnsure（就绪后单源刷新，lastWiringResult 按目录复插结果面板）；index.html .wiring-* CSS + initWiringToggle 启动挂载；测试：test_webapp.py 端点三类输入 + 目录不存在/缺参（2 项）、task.test.mjs wiringOpts/uid 三输入域、resource-board.test.mjs conflictLegend 图例回归；全量 pytest 2789 + tests/js 653 passed。

两轴评审记录：规格轴——三点可议均非阻断（首帧异步未就绪帧=纯文字、就绪即刷新补上——设计如是；lastWiringResult 复插属最小协同超出项，为结果面板单源刷新所需；tier-2 图例「多任务共享」在单任务视图误导 **已整改**（conflictLegend 开关））；标准轴——无硬性文档违反，整改 3 项：①wiringPer 哨兵 {} → null 单源化（wiringSectionHTML 真调用 wiringPer + perComputed 防双执行）；②webapp.py 空载荷字面量重复 → empty 单字面量；③per 变量更名 perTask（语义清晰）。其余判断项（boardsCache 双缓存注释自认、静默吞错按数据纪律设计、kind 裸串胶水私有）按判断接受。

**备注：** 数据装配走任务推进前端既有 outputDir 透传路径（与任务卡烧录按钮同款）。旧目录（无快照 / 无 wiring）自动落入退化路径，无需迁移。人工冒烟：临时实例 8011 验证 /api/wiring 正常/无文件/坏 JSON 三类 200 + /js/ui/wiring.js、/js/fx/wiring.js 静态可达；用户实例（8000）未动，重启后生效。
