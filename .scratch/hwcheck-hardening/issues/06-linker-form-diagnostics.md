# 06 — 链接器形态的诊断要看得见（"0 warning" 不再漏）

**要做什么：** 工程带链接器告警时，**编译面板如实显示它**，不再报"0 warning"——
学生与维护者看到的读数与真日志一致。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

- [x] 解析器新增一类「**没有文件引用的工具链诊断**」：`<warning|error> #<数字>-<字母>:` 形态，
      warning 与 error 都收（真例 `warning #10210-D: creating ".sysmem" section …`）。
      严重度**按行首那个词判**（尾巴的字母是工具链自己的分类位，不猜）。常量
      `TOOLCHAIN_DIAG_KIND = "toolchain_diag"`；`path=""`、`line=0` —— 没有文件引用就**不编一个**。
- [x] 归类与落点照既有先例：载荷里带 `kind`（`parsed_error_entries` 本来就为"非源码级"补 kind，
      零改动就通）；前端新增 `isToolchainDiag` + `isUnjumpable`，渲染成**不可点击行 + 「工具链诊断」标签**
      （配色用 `--warn`，与「配置冲突」的 `--danger` 分开），并补 CSS 三条。
- [x] 汇总如实：`summarize_compile_output` 的行级回退按 message 计数，新条目含 `warning` ⇒
      `warnings = 1`（此前 0）。用例直测这一条。
- [x] 用例：`test_parse_linker_form_diagnostic_without_file_reference`（真日志原文进 → 1 条 warning、
      kind / path / line 三个字段、汇总 = {0,1}）与 `test_parse_linker_form_diagnostic_keeps_error_severity`
      （error 形态 → {1,0}）；JS 两条（不可跳转 + 混排 + 不标源码行）。
      **既有 UV4 / CCS / gmake / SysConfig 四类形态的用例全绿**（`tests/test_fix_errors.py` 104 passed，
      含"无文件引用降级"那条——`error #20:` 没有 `-X:` 尾巴，照旧降级不误收）。
- [x] **反证**：`probe-06-red.py` → 把新形态的识别换成永不命中的正则 → 用例 exit=1（红）；
      复原后 sha256 逐字节相同、再跑 exit=0。读数 `probe-06-red.txt`。
- [x] 账本如实记账：`ml_mpu6050 × mspm0` 那格的 `.sysmem` 告警**属工具链行为**
      （`inv_mpu.c` 的 `log_i/log_e` 定义成 `printf` → TI 运行时 stdio 要堆 → 链接器建 `.sysmem`
      时按默认值告警），**本单不修驱动**——只保证它被看见。想让那一格真到 0 warning 得另开单改驱动，
      属"库内驱动修正"的家（`.scratch/driver-defect-fixes/`）。
- [x] 相关面全绿：见提交信息里的读数。
