# 04 — 端到端验收 + 文档 + 全量回归

**要做什么：** 全量 pytest + js 测试绿；CONTEXT.md 词条与 README/文档按需更新（zigbee_link 模块、ZIGBEE_UART 消费者、双车无线通信命中路径）；CHANGELOG 条目随中文提交自动补录；手工验收说明（重跑 2021F 推荐预期由 NRF24L01 库外建议变 zigbee_link 库内命中，LLM 非确定性不保证逐字）。

**被谁阻塞：** 01 + 02 + 03

**状态：** resolved

**验收记录（2026-09-05）：**
- 全量 pytest 3180 passed（含新增 zigbee_link 相关用例；3 条 warning 为既有，非本特性引入）
- 全量 js（node --test tests/js/*.test.mjs）1307 passed
- CONTEXT.md 更新：协议串口默认实例分配行补 zigbee_link 通用收发共享 + zigbee-rx 互斥说明
- CHANGELOG 由各工单中文提交自动补录；tests/test_repo_language.py 兜底绿（含在全量中）

**手工验收说明（真实 LLM 路径，费用自理）：**
- 2021F 重推预期：功能需求「两小车无线通信」（句子 83）由「库内无命中 + NRF24L01 库外建议」变为 **zigbee_link 库内命中**（可勾选进工程）；买件指引「无线通信模块」面板出现「Zigbee 模块（DL-20 串口透传）」行并带「库内已有：zigbee_link」徽标。
- 不保证项：LLM 覆盖检查非确定性，命中与否取决于模型对简介/题面的语义判断；若模型仍判 NRF24L01 更贴题（如题面点名 2.4G 信道/特定型号），不视为缺陷——库内命中只保证「语义匹配时可达」，不保证必选。
- 此前缓存的 2021F 推荐（~/.contest_generator/cache/recommend_2021F.json）因 stm32 库指纹未变仍会命中旧结果；想看新结果需先清推荐缓存（设置页「重置本地记录」或删除该缓存文件）——但**当前代码重跑即会重推**（指纹一致才复用，库变会失效）。

- [x] 全量 pytest 绿（含新增 zigbee_link 相关用例）
- [x] 全量 js 测试绿
- [x] CONTEXT.md 词表行更新（ZIGBEE_UART 共享实例说明）
- [x] 中文提交信息自动补录 CHANGELOG；`tests/test_repo_language.py` 兜底绿
- [x] 手工验收说明写好（2021F 重推预期 + 不保证项 + 缓存注意）
