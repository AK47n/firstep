# 01 — 生成后磁盘同步状态行

**要做什么：** 生成工程成功后，生成页步骤 8（main.c 骨架）卡片里出现常驻状态行：「已生成到 <dir> · main.c 已写入磁盘」+「从磁盘重新加载」按钮；点击重新加载把磁盘上的 main.c 读入编辑框（行号列 / 高亮层 / 草稿保存全部同步），加载后状态行切换为「已同步到磁盘版本」。刷新页面（草稿恢复）后也能看到此前生成的目录与同步状态。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 生成成功后，步骤 8 出现状态行，包含输出目录路径与「从磁盘重新加载」按钮；未生成过工程时不显示（原有 UI 不变）。
- [x] 点击「从磁盘重新加载」→ 编辑框内容 = 磁盘 main.c，行号列与高亮层同步（编程赋值不触发 input 事件，须显式走同步路径）。
- [x] 加载后草稿保存生效：刷新页面恢复草稿后，步骤 8 编辑框与状态行仍反映磁盘版本。
- [x] 上下文目录（生成成功的 output_dir）持久化到草稿：刷新后状态行能显示此前生成的目录（无草稿时回退到最近生成记录）。
- [x] 加载失败（目录不存在 / main.c 被删）：中文提示，编辑框内容不被清空。

## 实现说明

- 新增 fx/mainc-sync.js（maincDiskState / maincDiskStateHTML / maincDiffers 纯函数 + window 桥）与 ui/generate-mainc-sync.js（diskDir / diskState 模块态；setMainCDiskContext / refreshMainCDiskState / loadDiskMainC / initMainCDiskSync；复用 GET /api/code/file 读 main.c，零新后端）。
- 生成成功挂 setMainCDiskContext(data.output_dir) + scheduleDraftSave()（评审整改：生成成功不触发输入防抖，无后续编辑则 outputDir 即刻入草稿，刷新仍可恢复状态行）。
- 草稿契约扩展：draftState 第 7 参 outputDir；draftRestoreMeta 白名单 + outputDir；DRAFT_FIELDS 同步（fx/draft.js + ui/generate-steps.js + draft-memory 测试同步更新）。
- 无草稿回退：ui/recent.js refreshRecent 在生成上下文目录为空时用最近一条记录补位（草稿已恢复上下文时不覆盖）。
- 加载路径：textarea 编程赋值后 dispatch input（一次性触发既有监听：高亮同步 + 草稿防抖），无跨模块循环 import。
- 双轴评审整改记录：spec 轴——生成成功即持久化 outputDir（scheduleDraftSave）；standards 轴——diskText 缓存态删除（只写不读）、fx 补齐 window 桥（fx 模块统一约定）、测试调用签名与 fx 定义对齐。
- node --test 963 项全绿（新增 mainc-sync.test.mjs 5 测试 + draft-memory 断言更新）。
