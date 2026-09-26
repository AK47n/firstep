# 01 — 配方不许再教学生改生成代码（并把守卫扩到整个配方文件）

**要做什么：** 学生在检测页上**再也读不到"去 main.c 把某一行的注释去掉"这类指令**——
那一行从 `hwcheck-acceptance/01` 起已经是活代码，学生照做会找不到；而且这类文案回潮要**当场红**。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `key × mspm0` 的平台说明改成与 `xunji × mspm0` / `adc × mspm0` **同口径**：
      「检测程序开头**已经调了** `SYSCFG_DL_init()`（那一行是活代码，不需要你改 main.c）：它负责把
      KEY 的输入方向配好——没配上的话读数不可信，那不是按键坏。」（「读数不可信」那半句保留）
- [x] 新增守卫：读**真库那一份**配方文件**全文**，出现 `取消注释` / `注释去掉` / `注释状态` 即红
      （`test_real_recipe_file_never_asks_students_to_edit_generated_code`）；配一条"该在的在了"的
      反向守卫（`test_key_recipe_note_says_the_init_line_is_already_live`，并断言它进 `sections_payload`
      ——页面读的就是那份载荷）。既有清单级断言**未动**。
- [x] **反证**：`.scratch/hwcheck-hardening/probe-01-red.py` → 把旧句以**合法 JSON** 形态塞回，
      用例 exit=1（红）；复原后 sha256 `886d9d09…` **逐字节相同**，再跑 exit=0。读数落
      `.scratch/hwcheck-hardening/probe-01-red.txt`。
- [x] 相关面全绿：`pytest tests/test_hwcheck_recipe.py tests/test_hwcheck.py -q -n auto` = **332 passed / 10 skipped**。
- [x] 页面渲染确认：`sections_payload([section])[0]["note"]` 含那句实话（用例内断言）。
