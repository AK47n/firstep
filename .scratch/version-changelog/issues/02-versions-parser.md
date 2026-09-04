# 02 — VERSIONS.md 解析器（parse_versions / load_versions）

**要做什么：** `changelog.py` 新增两个纯函数并可被测试独立验证：
`parse_versions(text)` 把 VERSIONS.md 文本解析成
`[{version, date, summary, items: [{kind, text}]}]`（文件顺序）；
`load_versions(path)` 读文件并解析，缺失 / 读取 / 解析异常 → `[]`（展示数据不抛）。
解析契约：`## vX.Y.Z (YYYY-MM-DD)` 开新版本区块（ASCII 括号 + 严格日期）；
组内 `- 标签：文本`（标签 ∈ 新增/改进/修复/性能，`- 主题：文本` 归 summary
不占条目）；无标签行整体保留、kind 为「其他」；非版本 `##` 小节与 HTML 注释跳过。

**被谁阻塞：** 01（VERSIONS.md 格式约定先立，契约有物可依）。

**状态：** resolved

**审查结论（code-review 双轴）与整改：**
- 规格轴：多行 HTML 注释内的格式示例会击穿注释态解析出幽灵版本块（真实
  VERSIONS.md 实况命中）——已修（注释状态追踪，含同行闭合注释），并补
  单测（多行注释含 `## v`/`- ` 行、同行 `<!-- … -->`、真实文件契约守卫）。
- 规格轴：版本号段数放宽 1~3 段与契约「主.次.补丁」不符——收紧为严格三段
  （`v1.1` / `v1.1.0.1` 均整块丢弃），测试同步。
- 标准轴：load_versions 与 load_changelog 重复——仓库明规则「参数化劣于
  清晰重复」（CONTEXT.md 条目库原语）豁免，保留；`kind="其他"` 提为常量
  `_VERSION_KIND_OTHER`；其余气味均为判断项，不整改。

- [ ] parse_versions 正常样例：版本 + 日期 + 主题 + 多条带标签条目
- [ ] 无标签行 → kind=「其他」且整行文本保留
- [ ] 非版本 `## ` 小节、HTML 注释、说明段不产生条目
- [ ] 损坏 / 异常输入 → []（不抛）；load_versions 缺文件 → []
- [ ] tests/test_changelog.py 全套绿
