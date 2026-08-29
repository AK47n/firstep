# 01 — 生成接线快照落盘

**要做什么：** 生成工程时，把「板定义 + 接线行」快照随工程落盘——后续任务推进环节读它画接线图，且行数据与 README「引脚接线表」同源，图与表永不漂移。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] 生成含接线模块的工程（如灰度 / OLED / 电机）后，工程目录出现接线快照文件（.contest_wiring.json）
- [x] 快照内容 = {version, platform, board_id, board（板定义内嵌：引脚坐标/丝印/固定资源与 /api/boards 同平台板一致）, rows}；rows 与 README「引脚接线表」行逐行一致（含多实例通道行；未声明 pins 的模块不产生行——与 README 行为一致）
- [x] 无任何接线模块的工程也落盘（rows 为空数组，行为与 README 空表一致）
- [x] 既有生成产物零变化：README / 工程文件逐字节不变（快照为纯新增文件）
- [x] pytest：快照落盘（正常 / 空接线）、rows 与 README 同源一致性、board 内嵌字段齐全，全部成文（tests/test_wiring.py）

**完成纪要：** readme._pin_rows 内部重构为 _pin_row_items（结构化推导：slug/role_id/role_label/pin/remark），接线表与快照共用同一推导（图与表永不漂移）；wiring.py 只做生产侧（构建/写盘，含 WIRING_SNAPSHOT_FILENAME / VERSION 常量），读取侧与校验协议留待工单 02；generator.py 在 README 写盘同一位置落快照，board 缺失（BoardError）不写块——前端走退化路径。评审两轴通过（标准轴：读取侧/02 层捆绑已按工单边界拆分；规格轴：无缺口）。

**备注：** 数据源 = 生成路由写 README 的同一批数据（平台、模块清单、已解析绑定、实例计划），复用既有 `_pin_rows` 推导函数；board 对象 = 生成流程既有绑定校验同款。旧目录无快照 = 向后兼容场景（后续工单按退化路径处理，本工单不涉及读取侧）。
