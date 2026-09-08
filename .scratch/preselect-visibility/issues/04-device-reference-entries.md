# 04 — 器件级参考条目入库、死映射复活

**要做什么：** 把 `beep` / `key` / `led` / `led_beep` / `oled` / `servo` 这 6 个「死映射」救活——它们的词项在参考库 148 条标题里 0 命中，选中这些模块时骨架关联不到任何例程。做法是把 Markdown 资料库里已有的器件级移植手册（`sources/materials/lckfb-地猛星移植手册/`，含 0.96 寸 IIC/SPI 单色屏、0.96/1.3 寸彩屏、8 位 LED 数码管、WS2812 幻彩灯带、SG90 舵机、按键摇杆等）做成参考条目入库，使这些词项在标题里命中。做完后 `tests/test_skeleton_mapping_coverage.py` 的「每个有映射的模块至少一个词项命中」那条 xfail 转 XPASS。

**被谁阻塞：** 03 — 骨架映射判据与显式豁免（契约 + 机制）。

**状态：** ready-for-agent

- [ ] 盘点 6 个死映射模块各自可用的手册（`sources/materials/lckfb-地猛星移植手册/*.md`），逐条对应关系落进本工单答复
- [ ] 参考条目入库（走既有 `add_reference` 路径，素材 = 手册 markdown 原文，平台属性按手册平台，锚定 kit 或 none；不手工改库目录结构）
- [ ] 6 个模块的词项在新条目标题里命中（`beep`/`key`/`led`/`servo` 直接命中；`oled` 由「0.96 寸 IIC 单色屏」类标题承载——命中判据按同义词组整体算，必要时把 `oled`/`led`/`key`/`beep`/`servo` 与中文词项组进 `PERIPHERAL_SYNONYM_GROUPS`）
- [ ] `tests/test_skeleton_mapping_coverage.py` 该条 xfail 摘掉转常规守卫
- [ ] 新增参考条目进全库不变量测试（文件存在、锚定合法、平台属性合法），且不破坏既有预算断言（参考候选清单段 `REFERENCE_SUGGESTIONS_MAX_WIRE_BYTES` / 全文段相关回归）
- [ ] `python -m pytest -q` 全绿；`python .scratch/library-audit/probe_term_effect.py` 复测显示这 6 个模块不再 0 命中
