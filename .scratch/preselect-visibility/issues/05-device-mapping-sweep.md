# 05 — 器件模块映射补齐（全库覆盖转绿）

**要做什么：** 把剩余 54 个器件模块（有 lckfb 移植手册的传感器 / 显示 / 执行 / 通信件，如 ads1115、aht10、dht11、hc05、l298n、max7219、sr04、ws2812、ml_mpu6050 等）从「既无映射也未豁免」变成「有映射且关联得到例程」，使 `tests/test_skeleton_mapping_coverage.py` 的「全库每个模块有映射或显式豁免」那条 xfail 转 XPASS——骨架阶段选中任意库内模块都能关联到至少一条例程，或明确豁免。

**被谁阻塞：** 04 — 器件级参考条目入库、死映射复活（条目与词项扩展的路子先跑通）。

**状态：** ready-for-agent

- [ ] 盘点剩余未映射模块（`python .scratch/library-audit/probe_unmapped.py`），逐模块归到「可映射（有手册/有例程）」或「豁免（协议/板载件，入 `SKELETON_MAPPING_EXEMPT`）」
- [ ] 词项扩展：按器件类别补 `PERIPHERAL_TERMS`（温湿度 / 气压 / 光照 / 颜色 / 气体 / 测距 / 称重 / 姿态 / 指纹 / 语音 / 触摸 / 摇杆 / 彩屏 / 数码管 / 灯带 / 无线数传 / 蓝牙 / LoRa 等），**每个新词项必须至少命中一条参考条目标题**（判据同 03/04）
- [ ] 参考条目补录：类别合集的条目承载多个模块（如「气体传感器器件手册合集」承载 mq2…mq9/mq135/ms1100/ags10/sgp30），避免逐器件建条目造成库膨胀；条目素材取自 lckfb 手册原文
- [ ] `MODULE_PERIPHERAL_TERMS` 按模块补映射；豁免表补齐协议 / 板载件
- [ ] `tests/test_skeleton_mapping_coverage.py` 第二条 xfail 摘掉转常规守卫
- [ ] 词表预算复核：`PERIPHERAL_TERMS` / `MODULE_PERIPHERAL_TERMS` 变化是否影响推荐提示词预算（`WORDLIST_PROMPT_BYTES` 余量已吃紧——加词前先看 `probe_budget_headroom.py`）
- [ ] `python -m pytest -q` 全绿
