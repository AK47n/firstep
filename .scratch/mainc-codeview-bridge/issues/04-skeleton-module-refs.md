# 04 — 骨架引用模块锚定

**要做什么：** 骨架生成（或编辑框内容变化）后，步骤 8 编辑框下方出现「骨架引用的模块」chips——从骨架文本静态提取模块风格调用（`<slug>_init` / `<slug>_read` / `<slug>_update` 等）并与已选模块匹配（ident 以模块 slug 为前缀）；点击 chip 打开该模块的详情弹窗（元数据）。无法识别 = 该区隐藏（宁少标不错标，best-effort）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 骨架含 `led_init(...)` / `adc_init()` 且对应模块在已选列表中 → 显示「骨架引用的模块」chips。
- [x] 同一模块多次调用去重、按骨架出现顺序展示。
- [x] 点击 chip → 打开与推荐卡同款模块详情弹窗（元数据 + 文件名列表）。
- [x] 无命中（骨架里没有任何已选模块的调用）→ 该区隐藏。
- [x] 提取为纯函数并有单测（tests/js/*.test.mjs）：合法调用命中 / 关键字与字符串内不误收 / 无命中返回空。

## 实现说明

- fx/skeleton-refs.js：`skeletonModuleRefs(mainC, slugs)`（注释/字符串/字符字面量状态机剥离 + `ident(` 调用形态提取，ident === slug 或 slug+"_" 前缀，C 关键字表排除，每 slug 只记首次命中——去重保序）+ `skeletonRefsHTML(refs)`（chip 主标签 slug + reason 首命中调用，esc 转义）。
- ui/skeleton-refs.js：`renderSkeletonRefs()`（读 #main-c + selectedSlugs）+ `initSkeletonRefs()`（input 200ms 防抖 + chips 点击委托 openModuleInfo(slug, chosenPlatform)，与推荐卡同款弹窗）+ 首帧渲染；无命中整区隐藏。
- 触发齐备：骨架/自检生成成功（generate-core 显式调）、草稿恢复（generate-steps 显式调）、用户手输与磁盘加载（input 防抖——loadDiskMainC dispatch input 自动覆盖）。
- 前缀边界：slug=pid 不误收 pidx_init（ident.startsWith(slug + "_") 语义）。
- 验证：tests/js/skeleton-refs.test.mjs 6 项 + smoke-04.mjs 8 项（含弹窗打开与注释不误收）；node --test 969 全绿。
- 备注：弹窗打开要求 /api/modules 已加载（选中模块来自同一清单，正常路径一致）；关卡在「宁少标不错标」——匹配失败 = 隐藏而非报错。
