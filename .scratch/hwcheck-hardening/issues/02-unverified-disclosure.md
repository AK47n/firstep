# 02 — 「未上板」说到每一格 + 页面上有一句总口径

**要做什么：** 学生打开检测页时，**每一格配方都如实写着自己有没有上过板**，
页面上另有一句总口径说明"这批检测还没在真板上跑过"——不拿编译绿当板上证据。

**被谁阻塞：** 无——可立即开始。执行纪律：与 01/03/04 同改配方数据文件，按编号顺序落地。

**状态：** resolved

- [x] 缺自述的格补全——实测是 **17 格**（`.scratch/hwcheck-hardening/apply-02-disclosure.py` 落地）：
      `led / oled / debug_uart / key / beep / sr04 / jy61p / adc / ml_mpu6050` 两平台 16 格 + `xunji × mspm0`
      （它只在正文里提了一句"未上板"，没有那句标记，末条不是自述）。
- [x] 措辞与扩张批同源，按"这一件在板上**有没有 OK / FAIL**"分两个变体（判据 = `probe.expect` 是否有值）：
      有判定的 3 格用扩张批原句（「编译矩阵绿 + 驱动实现的返回码判据」）；其余 14 格把中间那句如实换成
      「编译矩阵绿 + 页面清单与探头调用的静态核对（本件不在板上打 OK / FAIL）」——`xunji` 的平台说明
      自己就写着"板上不打 OK / FAIL"，套原句会自相矛盾。
- [x] 数据守卫（读真库）：**57/57 格**的平台说明**末条**含「**未上板**」，并区分三种坏法
      （没有说明 / 埋在中间 / 完全没有）分别点名（`test_every_real_recipe_cell_discloses_its_on_board_status`）。
- [x] 页面总口径：`hwcheckUnverifiedNoteHTML()`（fx 单源）+ `#hwcheck-unverified-note` 落点（卡片正文里，
      在 Ⅰ 平台选择之前）+ ui 初始化时渲染一次。文案：「本栏目的配方与探测小节尚未在真板上验证过：
      现有证据只到「能生成 + 能编译」。板上判 FAIL 先按下面的清单查接线；判 OK 也只说明通信走通了，
      不等于型号对、读数准。」（**无 markdown 星号**——HTML 串里不写粗体标记）
- [x] README 同步**同一句核心措辞**（「常见问题」新增一条「『硬件检测』的结论可信到什么程度」）。
- [x] **反证**：`.scratch/hwcheck-hardening/probe-02-red.py` → 撤掉 ui 那一行渲染 → 结构钉 exit=1（红）；
      复原后 sha256 逐字节相同、再跑 exit=0。读数 `probe-02-red.txt`。
- [x] 相关面全绿：`tests/test_hwcheck_recipe.py`（含新守卫）、`node --test tests/js/hwcheck.test.mjs`
      = **159 passed**；README 面守卫 `test_readme / test_onboarding_docs / test_preflight / test_repo_language`
      = **70 passed**。
