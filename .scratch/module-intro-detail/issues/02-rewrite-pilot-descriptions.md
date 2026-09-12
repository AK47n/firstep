# 02 — 简介改写成能看懂的四拍（pilot 批次，含 ir_beam）

**要做什么：** 推荐链路高频／易误解的一批模块，简介按四拍口语顺序重写——用户打开
说明就能看懂「这是什么 / 怎么接 / 怎么用 / 什么时候用」，而不是一上来读函数名。

**被谁阻塞：** 01（04 的分段标题要有东西可分段）。

**状态：** resolved

- [x] 书写顺序固定四拍：① 这是什么东西、量什么／② 怎么接线（线制、占几个脚、默认脚）／
      ③ 怎么用（init/read 函数 + 返回什么 + 默认极性）／④ 什么时候用（适用赛题功能）。
- [x] 保留简介既有硬约束：无题号/年份/题名（`library.BANNED_TOPIC_WORDS`）、
      声明能力方向（`CAPABILITY_WORDS`）、与代码一致。
- [x] ir_beam 作为样板：物理是什么 → 三线制接线与默认脚 → `ir_beam_init`/`ir_beam_read`
      与 1=遮挡 → 适用功能，四拍齐全。
- [x] 结构测试：pilot 模块简介满足四拍顺序守卫（首拍讲东西、含接线拍、含接口拍、
      含场景拍），防回退。
- [x] `pytest tests/test_library_invariants.py tests/test_module_ir_beam.py` 绿；
      全量 pytest 无新增红（4161 passed）。

**pilot 批次（9 个）**：ir_beam / sr04 / servo / step_motor / led / beep / pid / xunji /
ws2812——推荐链路高频、最容易「看到 slug 不知道是什么」的一批。

**接口名逐个对源码核过**（AI 一致性校验之外的第二道）：xunji 实际是 `xunji_read_gray()` /
`xunji_centroid(gain)`（不是初稿写的 `xunji_read`）、pid 的灰度初始化是 `gray_init()`
（不是 `pid_init()`）、beep 是 `beep_beep(次数, 响毫秒, 停毫秒)` 三参。写错接口名比写不出
说明更糟——用户照抄就编译不过。

