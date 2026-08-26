# 03 — 预览增强：复制按钮 + 轻量语法高亮（C / XML）

**要做什么：** 母版内容箱（关键文件与树文件共用）加「复制」按钮（剪贴板
写入，成功/失败行内反馈 + toast）与轻量语法高亮——C（.c/.h）与 XML
（.syscfg/.uvprojx/.cproject）两类，先切 token 后逐段转义再拼 HTML（杜绝
注入），超大文件（>128KB）回退纯文本；纯函数可单测（fx/highlight.js +
fx/master.js 内容渲染纯件）。

**被谁阻塞：** 02（内容箱渲染在 02 已被树文件共用，本工单统一收口
masterContentHTML）

**状态：** ready-for-agent

## 验收标准

- [ ] fx/highlight.js：`languageOf(path)`（.c/.h → C；.syscfg/.uvprojx/
  .cproject/.xml → XML；其余 → plain）；`highlightC(text)` / `highlightXml(text)`
  返回转义安全 HTML（注释 / 字符串 / 预处理 / 关键字 / 数字 / 标签 / 属性 /
  引号值分类着色；文本中的 `<`、`&` 等被转义，无注入面）；超
  HIGHLIGHT_MAX_BYTES（128KB）回退 esc 纯文本
- [ ] 内容渲染统一 `masterContentHTML`（复制按钮 + 高亮内容 + 加载三态），
  关键文件与树文件共用；复制 = navigator.clipboard.writeText，失败 toast
  中文（非安全上下文 / 拒绝授权回退文案）
- [ ] 既有约定不破：content 后端契约原样（高亮纯前端展示）；pre 类样式
  兼容既有 master-file-pre（高亮为内联 span 类，新增 CSS 令牌与既有暗色
  主题和谐）
- [ ] tests/js：highlight.test.mjs（多类 token 断言 + 注入样本
  `<script>`/`&amp;` 转义 + languageOf 映射 + 超限回退）；master-ext-browser.test.mjs
  增内容渲染（复制钮存在 / 高亮类存在 / plain 无高亮）
- [ ] 冒烟：母版 key 文件（pin_config.h / mspm0.syscfg）打开 → 高亮 span
  计数 >0、复制按钮点击后剪贴板内容子串断言；全量 node --test 保持绿
- [ ] 中文提交

## 实施记录

（待实施）
