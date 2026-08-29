# 01 — 关键文件目录单源 + 浏览列表字段

**要做什么：** `GET /api/masters` 每条目带 `platform_label`（平台展示名，如
「STM32F103C8T6 最小系统板 · Keil5」）与 `key_files`（关键文件目录：相对路径 /
中文标签 / 大小字节 / 是否存在，**不含内容**），母版库卡前端可据此渲染清单与
「详情」入口；关键文件白名单成为服务端单源（后续内容端点复用）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `master_store.MASTER_KEY_FILES` 单源：stm32 四条（main.c 模板 main.c /
      pin_config.h 板级引脚宏 / led_instances.h LED 多实例通道宏 / user/Project.uvprojx
      Keil 工程配置），mspm0 三条（main.c / mspm0.syscfg SysConfig 配置 /
      .cproject CCS 工程配置），label 中文
- [x] `master_key_files(masters_dir, platform)`：按磁盘实况返回
      （path/label/size_bytes/exists）有序元组；平台不在库 → MasterError 400 中文
- [x] `GET /api/masters` 每条补 `platform_label`（webapp PLATFORM_DISPLAY_NAMES
      单源，缺省回退 platform）+ `key_files`（无 content）；`MasterMeta.to_dict()`
      保持三字段既有契约不破
- [x] `test_master_store.py` 增目录形状 / exists 实况三态（正常 / 缺失 / 无此文件）/
      大小字节数用例；`test_webapp.py` 增列表字段断言（platform_label / key_files
      形状、不带 content）——临时母版目录注入，不碰真实库
- [x] 结构测试补登：`test_autocommit.py` 注册表 master_key_files → ("read", "")
- [x] pytest 全量绿（现状 2446 → 2455）

**评审结论（2026-08-27）：** standards + spec 双轴。spec 轴结论「整体达标，findings 轻微」：白名单七条逐条吻合、错误语义与 get_master 同口径、to_dict 三字段未动、测试覆盖验收标准；唯一偏离 = label 措辞（「LED 通道宏 led_instances.h」vs spec「LED 多实例通道宏」）——已修正为 spec 原文并同步测试断言。standards 轴：硬违规 1 条 = CONTEXT.md 词表未回填——归属工单 05（验收标准已含 CONTEXT.md 更新），非本单范围；Speculative Generality = 已知平台无白名单配置时静默回空清单——已改为大声失败（MasterError「关键文件白名单未配置」）+ 新增 monkeypatch 测试（白名单漏配 = 开发错误，杜绝静默误导）。评审时另发现上一轮 topic-detail.test.mjs 遗漏 13 行用例（功能已随 index.html 提交）——单独提交 6d51982 补记。pytest 全量 2455 绿、mypy 干净。

**备注（2026-xx-xx 收尾）：** 原文件末尾重复粘贴的「状态：resolved」行删除（模板状态字段仅顶部一处）；本工单此前已完成后未及时标记，现统一改 resolved 并提交（实现提交 95fa5ee，含 02 内容端点 195cd6b、05 收尾 00e806c）。