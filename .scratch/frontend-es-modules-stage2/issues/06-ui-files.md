# 06 — 共用文件件：static/js/ui/files.js（文件行增删 + 读取 + 选择器）

**要做什么：** 模块库（newModulePayload 弹窗「文件增删」）与参考库（editReference 文件增删）共用的文件行 UI 件迁入 `static/js/ui/files.js`：addFileRow / collectFiles / readPickedText / pickFilesInto / bindFilePicker。library 与 reference 两模块 import 共用（跨簇共享件，非 tab 专属）。`newModulePayload`（6132）留 library 簇（它组合 collectFiles + 元数据）。

**被谁阻塞：** 02（app.js 提供 `$`）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- addFileRow 6062 / collectFiles 6078 / readPickedText 6096 / pickFilesInto 6103 / bindFilePicker 6122（区段 6062-6131，含 6090-6091 区段注释「选择文件 / 文件夹 → 读为文本填入文件行（模块库 / 参考库共用）」）。
- 引用方：library 簇（editModule 5876 / newModulePayload 6132 等）+ reference 簇（refCollectFiles 6583 —— 即 `collectFiles($("ref-files"))`）。
- 依赖：`$`、esc（fx/core.js）、handle（app.js，readPickedText 或 pickFilesInto 内 fetch 读文件？实施时 grep 确认）。

## 检查表

- [ ] 新建 `static/js/ui/files.js`：5 函数逐字搬移 + export + 头部注释（共用件、两引用方、源自工单 06）
- [ ] index.html：CRLF 感知行区间删除（6062-6131；**物理升序**）+ 顶部 import 行追加
- [ ] library / reference 两簇工单实施时 import 自 files.js（本票先迁，若两簇未迁仍在 index.html 则主体 import files.js 即可——window 无桥，内联调用点引用主体作用域……**注意**：本票迁移后，index.html 内联主体（尚未拆的 library/reference 胶水）不能裸引用 files.js 函数——需在主体 import 行把 5 名一并 import（阶段 1 桥接约定 2：顶部静态 import 后主体裸引用即绑定）
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11（模块库/参考库编辑弹窗打开一次）
- [ ] grep 零残留：index.html 无 `function addFileRow(` 等 5 名定义
- [ ] 中文提交

## 风险点

- 本票与 07/08 有顺序耦合：files.js 先迁、主体 import 5 名暂时代理；07/08 迁 library/reference 簇后，主体 import 行删去代理名（收尾工单核对）。
- addEventListeners 若在文件行上 top-level 绑定（addFileRow 内 per-row 绑定），逐字搬移无碍。
