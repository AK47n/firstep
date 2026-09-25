# 01 — 配方命令字符让位：一件器件不再只能写死一个复测字符

**要做什么：** 学生一次勾两件以上专精器件时**不再因为两个配方都想用同一个字符而生成前 400**。
配方 `console` 段在"首选字符"之外允许声明**候选字符**，命令表按「配方顺序 + 首选优先」分配
第一个没被占用的字符；页面显示的就是板上认的那个字符（同一张表，单源不破）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

- [ ] `console` 段接受 `command`（首选）+ 可选的候选字符列表；**不带候选的老配方行为逐字不变**
      （向后兼容：只有一个首选时，分配结果与今天完全一致）
- [ ] 分配规则确定性：同一选中集、同一配方文件 → 恒定同一结果（禁止依赖字典序 / 时间 / 随机）
- [ ] 保留字（`r/y/g/o/b` 与帮助命令 `?`）**永不被抢**；已占用的字符不抢
- [ ] 分配不出来时**中文大声失败**：点名哪一件排不上号、池子多大、已被占几个、出路是什么
      （沿用 `_assign_custom_command` 的报错口径）
- [ ] 页面载荷（`console_payload`）与板上分派（`render_console_runtime`）读到的都是**分配后**的字符
- [ ] 纯函数直测：首选可用 → 用首选；首选被占 → 用候选；候选也用完 → 红；保留字不碰；
      两条配方声明同一组候选 → 各拿各的、不撞
- [ ] **反证**：把现有两件配方的字符改成同一个（不带候选）→ 命令表必须红；
      带上候选后 → 让位成功且页面显示让位后的字符（两条都要有实测读数）
- [ ] ADR `0016-hwcheck-render-plus-recipes.md` 补一笔：配方契约从"一个字符"变成"首选 + 候选"

---

## Comments

### 2026-09-25 立项依据（实测，不是推测）

- `.scratch/hwcheck-specialize/probe-console-space.txt`：
  ① 现有 17 格声明的字符在**同一平台内**互不冲突（mspm0 10 个、stm32 7 个，都不同）；
  ② 反证实测：把 `jy61p` 的字符改成 `ml_mpu6050` 的 `m` → `build_console_table` 当场抛
  `HwCheckError`「控制台命令字符 'm' 被 'ml_mpu6050' 与 'jy61p' 同时声明」——判据真实存在；
  ③ 容量：可用池 **31** 个（字母数字扣掉保留字 `?bgory`），现状已占 **10** 个。
- 为什么现在必须做：首批 20 件专精化后专精件达 30 件、字符占用逼近 31 个上限，
  而"首字母记法"必然撞车（`sht20` / `sht30` / `sgp30` / `servo` / `sr04` 都想用 `s`）。
  不做这一步，学生勾两件传感器就会撞上 400——那是把"专精面变宽"直接兑换成"组合变少"。
- 先例：自建件（`hwcheck-unknown-device`）早就有"从池子里分配字符"的机制
  （`_custom_candidates` / `_assign_custom_command`）。本单是把同一条思路搬到配方侧，
  **不是新造一套**；配方命令先分配、自建件后分配（自建件天然避开配方已占的）。
- 射程边界：本单只动命令表与配方 `console` 段的解析、页面载荷与文档；
  **不碰**已 resolved 的检测程序渲染框架、不动既有保留字语义、不给配方加别的字段。

### 2026-09-25 落地记录（实现 + 反证读数）

**实现**（`hwcheck_recipe.RecipeConsole` 加 `candidates` 字段 / `hwcheck_console._recipe_command`
分配 / `sections_payload(commands=…)` 让页面读到分配后的字符）：

- `console.candidates`：字符数组，与首选同款形状判据（单个字符，点名字段红）；缺省 = 空元组
  ⇒ **老配方逐字兼容**。首选自己 / 重复候选只是冗余，解析时去重。
- 分配规则（`_recipe_command`，纯函数）：按「声明顺序（首选 → 候选）」取第一个**既不是保留字、
  也没被占用**的字符；保留字**声明即判**（不看这次轮不轮得到它——否则同一份配方会因为旁边勾了
  哪几件而时而红、时而静默通过）；候选也用尽 = 构建期红，报错带四样：哪一件排不上号、
  它声明的全部字符、池子多大（31）、已被谁占（`'l'（'led'）`），并给两条出路。
- `COMMAND_POOL` 抽成常量：配方让位与自建件分配**读同一个池子口径**（原来两处各算一遍）。
- `sections_payload(sections, commands=…)`：页面那一格的命令字符 = **分配后**的字符；
  `hwcheck_board` 把命令表里配方件的 `slug → command` 传进去（自建件不覆盖配方小节）。

**反证读数**（`.scratch/hwcheck-specialize/probe-console-fallback.txt`，真库真配方）：

| 形态 | 读数 |
|---|---|
| A) 把真库 `oled` 的字符改成与 `led` 相同的 `l`、**不带候选** | ✓ 构建期红：`配方件 'oled' 的控制台命令字符分不出来了：…（首选 'l'，没有声明候选）这一趟都已被占用：'l'（'led'）；可用字符一共 31 个…已经占了 1 个` |
| B) 同一处再声明候选 `["w","z"]` | ✓ 让位成功：`led='l'、oled='w'`；页面载荷 `commands` 与板上 `case` 都是 `w`（页面 = 板上同一个字符） |
| 现状 | stm32 7 件全用首选（空闲 24）；mspm0 10 件全用首选（空闲 21）——**老配方行为逐字不变** |

**测试**（TDD，先红后绿）：`tests/test_hwcheck_recipe.py` 新增 4 条（解析候选 / 老配方无候选 /
候选形状点名字段 / `sections_payload` 报分配后的字符），`tests/test_hwcheck_console.py`
新增 9 条（让位、声明顺序、两条配方声明同一组候选各拿各的、老配方照旧红、候选用尽的
数字与出路、保留字候选声明即判、纯函数确定性、页面 = 板上、**文件头配料行 = 命令表**），
`tests/test_hwcheck_board.py` 新增 1 条（**真装配那道接线**：临时配方文件造撞车现场 →
`board["sections"][].console.command` 与 `board["console"]["commands"]` 同字符）。
老判据一个没删：`test_two_devices_may_not_share_a_command_character` 仍然绿
（不带候选的撞车还是红）。

### 2026-09-25 评审整改（code-review 两轴，固定点 `HEAD`）

**Spec 轴**（3 条 + 1 条实测漏腿，全部已改）：

1. 「两条配方声明同一组候选 → 各拿各的」缺用例 → 补 `test_two_recipes_declaring_the_same_candidates_each_get_their_own`。
2. 「页面载荷读分配后的字符」只到纯函数层、**board 那道接线无用例** → 补
   `test_page_payload_shows_the_assigned_console_character`（直调 `hwcheck_view` + 临时配方文件）。
3. 报错出路漏了 spec 原话里的"换字符" → 补上（现在是"多加候选 / 换一个字符 / 去掉几件"）。
4. **实测漏一条腿**：`hwcheck._section_recipe_brief` 仍读**声明**的首选，产物文件头里
   同时出现"`w` 复测 oled"与"控制台命令 `'l'`" → 改成吃分配后的字符，并补
   `test_main_header_lists_the_assigned_console_character`。

**Standards 轴**（2 处硬违规，已改）：

1. `COMMAND_POOL` 漏登记进 `hwcheck_console.__all__` → 已补。
2. `tests/test_hwcheck_console.py` 模块 docstring 还写着"两件抢同一个字符必须构建期红"
   → 已改写成"先让位、让不开才红"，与实现同真。

判断性标签里采纳两条：池子说明文案两处逐字重复 → 抽 `_pool_description()` 单源；
测试里硬编码 `"31"` → 改为由 `len(COMMAND_POOL)` 推算（避免被别的数字巧合命中而假绿）。
其余（board 那次投影、`commands or {}`）判为不改，取舍记在这里。
