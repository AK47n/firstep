# 04 — 读数行不许超板上行缓冲（守卫扩到全量配方）

**要做什么：** 板上那条 128 字节的行缓冲不再被任何一格读数行撑爆——
学生不会再看到"行尾巴被截掉、中文只剩半个"的乱码；而且这条守卫**管全量配方**，pilot 格不再是盲区。

**被谁阻塞：** **03**（03 收窄表达式横幅，行宽清单会变；先落 03 再量）。

**状态：** claimed

- [x] 逐格重量全量读数行（按 03 落地的**值优先**格式：`<值> <单位> (<表达式>)`，数值按 12 位十进制算）。
      实测超限 **5 条**（全在 pilot，与立项读数一致）：`debug_uart × stm32` 249B、`adc × mspm0` 162B、
      `beep × stm32` 156B、`adc × stm32` 149B、`adc × mspm0` 149B——比 `.scratch/backlog.md` §21 记的
      1 条多 4 条（§21 是逐格自查时顺手撞到的，只记了 `debug_uart`）。
- [x] 5 条的长说明挪进该格平台说明（**倒数第二条**，末条仍留给「未上板」自述），行上留短量纲：
      debug_uart→110B、adc×mspm0→87B/74B、beep→93B、adc×stm32→82B。落地脚本 = `apply-04-units.py`
      （纯文本替换 + 锚点唯一性校验，不重排 JSON；复核 57/57 格的末条仍是「未上板」）。
- [x] 新守卫吃**全量配方（含 pilot）**：`test_every_real_read_line_fits_the_device_line_buffer`
      （地板 165 条读数行 + 逐条最坏宽度 < 128 字节）。既有那条扩张格守卫**保留不缩小**。
- [x] **反证**：`probe-04-red.py` → 把 `debug_uart` 那条 249B 长量纲塞回行上 → 守卫 exit=1（红）；
      复原后 sha256 逐字节相同、再跑 exit=0。读数 `probe-04-red.txt`。
- [x] 两平台真编译矩阵复跑（改的是配方文本，必须证"还能编"）：`--slugs adc,beep,debug_uart`
      = **6 格全 PASS**（编译器 0 error / 0 warning、链接器告警 0），页面标记 `[专精]` 仍在。
      读数 `.scratch/hwcheck-hardening/probe-04-compile-matrix.txt`。
- [x] 相关面全绿：见提交信息里的 pytest 读数。
