# 06 — 共用文件件：static/js/ui/files.js（文件行增删 + 读取 + 选择器）

**要做什么：** 模块库（newModulePayload 弹窗「文件增删」）与参考库（editReference 文件增删）共用的文件行 UI 件迁入 `static/js/ui/files.js`：addFileRow / collectFiles / readPickedText / pickFilesInto / bindFilePicker + MAX_PICK_BYTES。library 与 reference 两模块 import 共用（跨簇共享件，非 tab 专属）。`newModulePayload` 留 library 簇（它组合 collectFiles + 元数据）。

**被谁阻塞：** 02（app.js 提供 `$`）

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、探针 06 通过）

## 实施记录

- **分裂裁定**：共享件 = 5 函数 + MAX_PICK_BYTES（6005-6070 一带）；**顶层的 4 个 bindFilePicker 调用（btn-pick-mod-files / btn-pick-mod-dir / btn-ref-pick-files / btn-ref-pick-dir）+ `$("btn-add-file-row")` 监听 + `addFileRow()` 初始行 留 host**——它们分别属 library（07）/ reference（08）簇接线，提前迁会断功能（bind 调用在 06→07/08 之间必须仍在主体生效）。host 顶部 import 5 名代理，簇迁移后收尾工单裁代理。
- **static/js/ui/files.js**（新建 ~90 行）：5 函数逐字搬移 + MAX_PICK_BYTES + 注释；import `{ $ } from "/js/app.js"` + `{ esc } from "/js/fx/core.js"`；readPickedText 无外部依赖（TextDecoder 内建）。模块头注释声明「文件行绑定时机 = 调用方弹窗打开时逐行绑定，顶部无跨域监听」。
- **index.html（apply-06.mjs 第二次运行通过，8001→7944）**：①host import（pdf.js 行后）5 名；②段 A（共用注释 + addFileRow 6005-6018）→2 行注记；③段 B（collectFiles → bindFilePicker 末 6070）→4 行注记——ⓘⓘ **首跑边界校验失败**：假设 bindFilePicker 后有空行再跟绑定调用，实况是 `}` 后**直接**跟 `bindFilePicker("btn-pick-mod-files"...`（无空行）——修正为 `lines[e+1]` 匹配该调用后通过（抛错在写盘前，未写坏）。ⓘⓘ 校验：6 名零残留、host 调用点全在（bindFilePicker 2 处 mod 2 处 ref、collectFiles()/collectFiles($("ref-files"))、addFileRow()、addFileRow(newfilesBox)、pickFilesInto(e.target, newfilesBox...)）。
- 验证：node --test 442 全绿（无新增测试——本票全是 DOM/file 胶水，无纯函数）；pytest 2465 全绿（bg 确认）；diag 零 EXC；smoke 11/11；探针 probe-06-files.mjs：导出面 5 名 ✓ host 无 addFileRow/collectFiles 定义 ✓ **浏览器内功能回路**（独立容器 addFileRow ×2 → collectFiles 取回 {a.c:"int x;", b.h:""} → 点 ✕ → collectFiles 只剩 b.h）✓ 4 个 bind 调用点仍在 host ✓。

## 检查表

- [x] `static/js/ui/files.js`：5 函数 + MAX_PICK_BYTES 逐字搬移 + export + 头部注释
- [x] index.html：apply-06.mjs（CRLF 感知；两段删除 + import 行；绑定调用留 host 防断功能）+ 6 名零残留
- [x] node --test 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + 探针 06（功能回路）通过
- [x] 中文提交 + CHANGELOG 记录

## 风险点 / 跟踪

- host import 的 addFileRow/collectFiles/pickFilesInto/bindFilePicker 为「代理名」：工单 07（library）迁出后裁 mod 相关代理、工单 08（reference）后裁 ref 相关——收尾工单 20 统一核对。
- readPickedText 无调用方限制（pickFilesInto 内部 + 可能外部）；用 File 对象测太费，浏览器功能回路已覆盖 pick 路径的主干。
