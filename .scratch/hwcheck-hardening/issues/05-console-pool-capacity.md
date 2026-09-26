# 05 — 字符池：勾满专精件也能生成 + 报错说真话 + 页面上事先提醒

**要做什么：** 学生把库里该平台的专精件**全勾上也能生成**（不再必然 400）；
真勾太多时，**生成之前**页面就提醒；万一还是排不下，报错里的数字是**真实的可用数**。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 数据侧**纯追加**候选池位：给 57 个 `candidates` 数组各补 `4 5 6 7 8 9`
      （既不是保留字、也不是任何一件首选）；**已有候选一个不删、顺序不动**——沿用批次 E/F 的共享后备池先例。
      落地脚本 = `apply-05-pool.py`（按数组块精确追加，不重排 JSON）。追加后**声明面并集 = 命令池 31 个**。
- [x] **核心判据（新用例）**：`test_the_whole_specialized_set_of_one_platform_builds_one_console_table`
      ——stm32 27 件 / mspm0 30 件一次全勾，表建得出且字符互不相同（此前 stm32 第 23 件、mspm0 第 26 件就红）。
- [x] 报错说真话：新增守卫 `test_command_pool_size_in_the_error_copy_is_the_real_allocatable_count`
      ——真库声明面并集必须**等于**命令池（此前只声明 25 个而文案印 31，把池子说大 6 个）；
      `_pool_description` 的 docstring 同步写明"这个数必须是真能分配的字符数"。
- [x] 不回退：既有小规模判据照旧绿（`|S| ≤ 2..3` 全子集 + 固定种子抽样到 8 件，两个平台）。
- [x] 页面**事前**提示：`console_capacity_note()`（域层单源，余量 ≤ `CONSOLE_CAPACITY_WARN_REMAINING`=3
      时才吭声，建不出表时返回空串——那条路走 400 的完整点名）+ 载荷键 `console_note`
      + `hwcheckConsoleNoteHTML` + `#hwcheck-console-note` 落点 + 载荷键契约守卫。
- [x] 前端用例：fx 三态（空串不吭声 / 服务端那句原样带出 / 载荷缺键保留旧值 + 从没有过是空串）
      + 结构钉（容器在 + ui 真调它）。
- [x] **反证**：`probe-05-red.py` → 撤掉追加的池位 → 两平台"全勾满"用例都红（stm32 `servo` /
      mspm0 同款点名）；复原后 sha256 逐字节相同、再跑 exit=0。读数 `probe-05-red.txt`。
- [x] 相关面全绿：见提交信息里的读数（pytest hwcheck 族 + 前端门禁）。
