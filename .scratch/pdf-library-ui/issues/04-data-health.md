# 04 — 数据健康警示：重复 / 损坏

**要做什么：** 素材库健康问题从「不为人知」变成「一眼可见」：0 字节损坏
PDF 与同名同大小疑似重复（>0 字节）的判定纯函数 + 行内 ⚠ 徽章 + 统计条
红色计数段（点击只看该类，再点取消，与关键字 / 批次 chips 正交过滤）。
**提示语义，只警示不删**——素材根是 git 版本化的原始素材区，不提供删除
动作；判定为纯客户端（不读内容 hash），冒烟对真实素材断言「4 组重复 /
现状 0 损坏」锁定判据与实况一致（数字按 ≥ 下限设计）。

**被谁阻塞：** 02（挂进行渲染与统计条）

**状态：** resolved

**评审（双轴）：**
- **Standards 硬违反 1：** `.badge.pdf-dup` 硬编码 rgba(255,189,92,.18)/#d9822b
  → 改 `var(--warn-dim)`/`var(--warn)`（badge.unverified 同族，随主题切换）。
- **值得修（已修）：** ① renderPdfStats 与 renderPdfs 健康谓词漂移（统计条
  「共 N 份」不随 health 过滤收缩，违反 ref 系列「行渲染与统计渲染共用同
  一定义」契约）→ 抽 `pdfHealthPredicates(pdfs)` 双方共用，冒烟补「统计条
  随过滤收缩」断言；② `.lib-stats-red` 与 `.ref-dangling-count` 重复定义
  → CSS 选择器组合并一条规则（ref 旧名保留，HTML 不动）；③ 徽章 HTML 两处
  重复 → 抽 `pdfBadgeTags(broken, dup)`（行/详情共用 + 单测）；④ `pdfBroken`
  严格 ===0 与兄弟函数防护不一致 → 显式接受字符串 "0"（null/undefined 不判）。
- **可保留判断句：** 纯函数 purity / 幂等边界 / 防 detached 点击陷阱 /
  extract 增强无误配平 / 测试子串断言范式均达标；pdfHealth 每轮重复算 O(n)
  微优化；红段 .on 态属合理增强。
- **Spec：无硬偏离**（3 轻微：pdfStats 与 pdfHealth 职责分界——验收已指派
  pdfHealth 故可接受；「对偶参考库 dangling 注释」类比不精确（ref 随过滤
  收缩、pdf 有意全量）——注释已修正措辞；冒烟 `rows === 2*dupN` 假设每组
  恰 2 成员——有 ≥8 前置守卫，固定真实数据可接受）。「同名」语义核对：
  spec 的 name 含扩展名，实现用 p.name 一致，无偏离。spec 测试决策
  「健康状态正交」由既有 pdfFilterEntries 健康测试满足。

- [x] 纯函数：`pdfBroken`（size_bytes === 0）、`pdfDupGroups`（同名，大小写
      不敏感，且同大小，且大小 > 0；组内 ≥ 2 成员——0 字节归损坏不参与
      重复；同名不同大小 = 不同版本不判重复）、`pdfHealth`（全量派生：
      {dupGroups, dupPaths, broken}——对偶 refDanglingAnchors，红段/行内
      徽章全量口径真值）
- [x] 行内标注：损坏「⚠ 损坏」徽章（红，.badge.pdf-broken）+ 疑似重复
      「⚠ 疑似重复」徽章（橙，.badge.pdf-dup = warn 令牌族）——pdfRowHTML
      挂接（谓词恒注入，filter 仅 health 置位时消费）；详情弹窗同步标注
      （flags 第三参，缺省不标注兼容 03 调用）；徽章 HTML = pdfBadgeTags 单源
- [x] 统计条红段：`疑似重复 N 组` + `损坏 N 份`（全量口径），点击 = 只看该类
      （再点取消，on 态下划线），与关键字 / 批次 chips 正交组合（pdfUI.health
      维度 + pdfFilterEntries 谓词 + pdfHealthPredicates 单源装配）
- [x] tests/js：判据边界（0 字节不参与重复、同名不同大小不判、大小写不敏感、
      组计数与输入序、字符串 "0" 判损坏/null 不判）、pdfHealth 派生、
      pdfBadgeTags 开关、行渲染 ⚠ 子串断言、详情 flags 断言
- [x] 冒烟：真实素材断言（重复红段 ≥4 组 + 行内徽章 ≥8；现状无损坏 = 红段
      不显示 + 临时 0 字节注入 → 损坏 1 份 / 徽章 1 个 / 点击只显示损坏 →
      清理后消失）；红段点击/再点取消过滤 + 统计条随过滤收缩（37 项 PASS）
- [x] 全量 tests/js 362 绿（355 + 7）+ pytest 2402 绿（无后端改动）

**实施期核查：**
- 素材库重扫（重复判据 = 同名大小写不敏感 + 同大小 + >0 字节）：66 份，
  重复 **4 组**（000_2017-2025 全国大学生电子设计竞赛真题汇总.pdf
  34996432B：2026_04/2026_07 两批各一；TB6612FNG 364305B、RT8289GSP
  283267B、RT9013-33GB 287134B：塔克R3 两驱小车底盘资料 6/7 批各一）；
  0 字节损坏 **0 份**；同名不同大小版本差异 0 组。与 spec 原数字一致
  （损坏基线已按「现状修订」段走双态验证）。
- extract 工具增强：跳过参数区（默认值花括号如 `flags = {}` 会提前截断
  函数体）——pdf-library / reference-library 两测试文件同步。此改动是
  04 的 `pdfDetailHTML(pdf, pages, flags = {})` 暴露的既有限制。
