# 03 — 接线图渲染纯件

**要做什么：** 前端 fx 层新增接线图渲染纯函数：板图 + 模块端子列 + 引脚→端子连线 + 本步高亮 / 全量淡显 + 电源配色 + 空态文案——输成字符串，无副作用，tests/js 独立验证。

**被谁阻塞：** 无——可立即开始（fixture 板定义 + 行数据即可测试，不依赖后端）

**状态：** resolved

- [x] 新 fx 渲染模块导出接线图 SVG / 整块 HTML 纯函数：输入 {board, rows, highlight}，输出转义后的字符串
- [x] 板图几何与既有资源总览板图同常量（行高 / 板宽 / 焊盘坐标换算一致），沿用「两处同常量、交叉同步注释」约定
- [x] 每行 = 一个模块端子盒（模块名 + 端子名 + 说明）+ 一条从对应引脚焊盘到端子盒左侧中点的连线；引脚用板丝印名（PA0 / PB6…）
- [x] 本步高亮线彩色；「显示全部接线」时其余线淡显（默认只渲染高亮行）
- [x] 电源 / 地类引脚（3V3 / GND / 5V / VBAT…）连线独立配色，图例说明
- [x] 空 rows / 板定义缺失 / 全非法输入 → 中文空态文案（不崩溃、不空白）
- [x] tests/js：SVG 结构（端子盒齐全、每线一条边、高亮类名）、电源配色、空态输出、全部转义（无未转义注入，仿既有 resource-board.test.mjs 先例）

**答案：** 提交「任务卡接线图 03：接线图渲染纯件…」。fx/wiring.js（新，仅依赖 fx/core.js esc）：几何常量与 resource-board.js 交叉同步（rowH=22/topPad=46/BOARD_W=460/PAD_R=7/CHIP_X=100/CHIP_W=260/LABEL_FS=11）+ 端子列常量（TERM_X=BOARD_W+24/TERM_W=208/TERM_BOX_H=20）；highlightWiringLines（命中行含 label/remark/note；未命中 = 端子名 target 自身；非法丢弃；pin→target 去重；matchRow 收 role_id/role_label/role 渲染串——与 02 白名单同步）+ wiringAllLines（缺省 rows 全量，hl 标记）+ wiringDiagramHTML（SVG：板壳/地标/全部焊盘/每线一条 path（wiring-hl/wiring-dim/wiring-power 类）/端子盒/图例/显示全部接线开关，showAll 缺省 false；空态中文文案；全部转义）。fx/task.js：wiringSectionHTML 三级退化装配（wiring 合法 → wiringDiagramHTML；空+fallback → 资源板图；都没有 → 空串）+ taskNextActionHTML(task, opts) 图文并存（缺省 opts = 现状行为不变）+ taskStepReportHTML 报告头部插图。tests/js/wiring.test.mjs（7 测试）+ task.test.mjs 三输入域（任务卡 / 结果面板）成文；全量 JS 套件 652 passed，pytest 2787 passed（03 不动后端）。

**备注：** 本工单不动既有资源总览板图渲染器（范围外：后续三处几何常量抽取单源）。任务卡 / 结果面板装配在工单 04。
