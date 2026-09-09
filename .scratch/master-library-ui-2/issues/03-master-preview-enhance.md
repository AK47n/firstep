# 03 — 预览增强：复制按钮 + 轻量语法高亮（C / XML）

**要做什么：** 母版内容箱（关键文件与树文件共用）加「复制」按钮（剪贴板
写入，成功/失败行内反馈 + toast）与轻量语法高亮——C（.c/.h）与 XML
（.syscfg/.uvprojx/.cproject）两类，先切 token 后逐段转义再拼 HTML（杜绝
注入），超大文件（>128KB）回退纯文本；纯函数可单测（fx/highlight.js +
fx/master.js 内容渲染纯件）。

**被谁阻塞：** 02（内容箱渲染在 02 已被树文件共用，本工单统一收口
masterContentHTML）

**状态：** resolved

## 验收标准

- [x] fx/highlight.js：`languageOf(path)`（.c/.h → C；.syscfg/.uvprojx/.cproject/.xml → XML；其余 → plain）；`highlightXml(text)` 返回转义安全 HTML；C 高亮**复用 fx/code.js 的 cHighlight 单源**（原写 `highlightC`，实施期按单源性改名）；超 `HIGHLIGHT_MAX_BYTES` 回退 esc 纯文本（阈值现 1MB，原 128KB 由 code-page-vscode-overhaul/09 放宽）。
- [x] 内容渲染统一 `masterContentHTML`（复制按钮 + 高亮内容 + 加载三态），
  关键文件与树文件共用；复制 = navigator.clipboard.writeText，失败 toast
  中文（非安全上下文 / 拒绝授权回退文案）
- [x] 既有约定不破：content 后端契约原样（高亮纯前端展示）；pre 类样式
  兼容既有 master-file-pre（高亮为内联 span 类，新增 CSS 令牌与既有暗色
  主题和谐）
- [x] tests/js：highlight.test.mjs（多类 token 断言 + 注入样本
  `<script>`/`&amp;` 转义 + languageOf 映射 + 超限回退）；master-ext-browser.test.mjs
  增内容渲染（复制钮存在 / 高亮类存在 / plain 无高亮）
- [ ] 冒烟：母版 key 文件（pin_config.h / mspm0.syscfg）打开 → 高亮 span
  计数 >0、复制按钮点击后剪贴板内容子串断言；全量 node --test 保持绿
- [x] 中文提交

## 实施记录

（2026-08-27 完成）

- 新建 fx/highlight.js：languageOf（.c/.h → c；.syscfg/.uvprojx/.cproject/.xml
  → xml；其余 plain，大小写不敏感）/ highlightXml（注释 / CDATA / 声明与
  PI / 标签名 / 属性名 / 引号值分类 tok-* 着色，先切 token 后逐段 esc，
  无注入面）/ highlightText（C 分发复用既有 fx/code.js 的 cHighlight 单源
  而非复制——spec 当时未见该先例，偏离「highlightC 命名」但单源性更优；
  >128KB 按 UTF-8 字节数（TextEncoder）回退纯文本，plain 恒 esc）。
- fx/master.js 增 masterContentHTML（null = 加载中 / ok = 复制按钮 +
  高亮 pre / 失败 = 中文原因 + 可重试，三态统一收口）；ui/master.js
  renderMasterFileContent 改调纯件，新增 copyMasterContent / writeClipboard
  （clipboard API → execCommand 回退 → toast 中文失败文案），成功行内
  「✓ 已复制」1.5s 还原；index.html 增 tok-tag/tok-attr/tok-val（暗/亮主题
  成对）+ .master-content-bar/.master-copy-btn。
- 测试：tests/js/highlight.test.mjs（languageOf 9 例映射、XML 五类 token、
  CDATA/DOCTYPE、注入转义、C 分发 tok-kw、plain 无高亮、超限回退）；
  master-ext-browser.test.mjs 增内容箱 4 例（成功高亮 / plain 转义 /
  失败可重试 / 加载中占位）。
- 回归：node --test 468/468、pytest 2491（本工单零 Python 改动）；真实
  文件冒烟：library/masters/stm32/pin_config.h → c 语言 113 个高亮 span、
  mspm0/mspm0.syscfg → 0 span（.syscfg 实为 TI-TXT 非 XML，按 spec 映射
  xml 零着色、无害，未来如要着色需 config 类高亮器，超出本轮轻量范围）。
- 评审：code-review 双轴——Standards 无硬违反（cHighlight 复用非复制、
  fx 纯函数边界、tok-* 成对主题均合规），判断项 4 记录在案（高亮/XML 扫描
  骨架同构——语法集不同提取收益低；"c"/"xml"/"plain" 字符串枚举隐式握手
  ——两函数相邻无碍；「复制」字面量两处——按钮还原文案场景不同；highlightXml
  85 行长方法——内聚单一不需拆）；Spec 缺口 2 已修（加载三态并入
  masterContentHTML、超限按字节计），交互级 CDP 冒烟属收尾工单 06 清单
  （本工单做实文件级冒烟），execCommand 回退为对 spec「回退文案」的加码
  （真实可用优先，保留）。

## 验收口径修订（2026-09-09 在途盘点）

- C 高亮命名 `highlightC` → 实际复用 `fx/code.js` 的 `cHighlight`（单源）；超限阈值 128KB → 1MB（code-page-vscode-overhaul/09 放宽）。冒烟项（key 文件高亮 + 剪贴板断言）仍未做实，故留空。

