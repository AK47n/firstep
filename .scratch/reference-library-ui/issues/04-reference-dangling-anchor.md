# 04 — 悬空锚定警示：跨库判定 + 行内标注 + 统计红段

**要做什么：** 让「永远不会被自动关联注入」的条目显形——锚定值不命中任何
库内赛题 / 套件的条目：行内 ⚠ 标注 + 统计条红色计数段，点击红段只显示悬空
条目；警示为提示语义，不拦截编辑。空库降级不误报（赛题库 / 模块库 kit 词表
为空时跳过对应检查）。

**被谁阻塞：** 工单 02（行渲染与统计条集成点）；与工单 03 互不依赖。

**状态：** resolved

- [x] 数据源就绪：tab 打开时拉取 GET /api/topics（key 清单，失败降级 = 空数组
      不阻塞渲染）；kit 词表沿用 loadKitVocabulary（/api/modules 派生）；空集
      降级跳过对应方向检查（refDanglingAnchors 内预过滤空 key/空词表项，
      无有效项 = 不判定）
- [x] 判定纯函数 refDanglingAnchors：topic 方向 = 不存在任何库内赛题 key 是
      锚定值子串；kit 方向 = 词表内不存在任何值是锚定值子串（与生成侧
      search_references 统一子串方向一致，评审修订——原成员判定会误标
      「词表值+前后缀」条目）；只对 topic / kit 锚定条目生效（none 无此概念）
- [x] 表格行内：悬空条目锚定徽章后显示 ⚠ 警示标（.ref-dangling-tag，title
      「锚定值不命中任何库内赛题 / 套件，生成时不会自动关联（点「编辑」改正
      锚定）」；无词表上下文降级不渲染）
- [x] 统计条：红色悬空计数段（.ref-dangling-count，0 时不渲染红色形态），
      点击 = 过滤只显示悬空条目（refUI.dangling 正交维度），再点取消；与既有
      过滤 / 排序正交可组合
- [x] 编辑弹窗不改动条目数据（警示语义），悬空条目「编辑」入口可直接改正锚定
      （冒烟联调闭环：临时 topic 悬空条目 → ⚠ 出现 → 编辑改未锚定 → 保存后
      ⚠ 消失，finally 前缀清理零残留）
- [x] 空库降级用例：赛题库空 / kit 词表空时对应方向零误报（单测锁定：
      空 key 忽略、词表空降级、缺 ctx 零误报）
- [x] tests/js 新增单测全绿（两方向判定、子串方向、降级、refStats ctx 悬空
      契约、行渲染 ⚠）；页面冒烟验证真实库 2 条悬空（topics=8/kits=2 数据源
      非空断言 + ⚠ 数 = 纯函数期望 + 红段点击过滤往返 + 编辑闭环）

**实现备注（评审双轴修订后）：**

- Spec 轴 C1（最关键，语义修订）：kit 方向原按 spec 字面「锚定值不在 kit
  词表」实现为成员判定——但生成侧 `associated_references` 对 topic 与 kit
  统一走 `search_references` 子串（`needle_anchor in anchor_value.lower()`），
  「锚定值包含词表值但不等」（如 ALX-套件-v2）的条目仍会被自动关联 → 成员判定
  假阳性。修订：kit 方向与 topic 同构为子串（词表内不存在任何值是锚定值子串），
  并同步修订 spec.md L102 定义（注明评审修订因）；单测新增「带前后缀不悬空」。
- Spec 轴 A1：spec 要求 refStats 输出含悬空数 → 实现（初版）由 DOM 层另算。
  修订：`refStats(entries, ctx?)` 增可选 ctx（{topicKeys, kitVocab}），内部按
  refDanglingAnchors 补 dangling 计数（缺 ctx / 词表空 = 0 不误报）；渲染层只
  做红段 span 包装；单测覆盖 ctx 契约（含 ctx=2 / 无 ctx=0 / 空词表=0）。
- Spec 轴 A2：冒烟「数据源就绪」断言 topics>=0 恒真 → 修订为 `topics > 0 &&
  kits > 0`（真实库两数据源非空；数据源失败时不再静默 PASS）。
- Spec 轴 C3：refRowHTML 的「无词表上下文」守卫 `(f.topicKeys || f.kitVocab)`
  因 refFilterContext 恒传数组而实际不短路（死代码误导）→ 删除：降级语义集中
  refDanglingAnchors 内部（f 缺词表 → undefined → 内部降级不渲染 ⚠）。
- Standards 轴（判断级全部采纳）：①命名空间——统计红段 lib-dangling-count →
  ref-dangling-count、行内 dangling-tag → ref-dangling-tag（参考库 ref-* 前缀
  先例；CSS 选择器组 `.dangling-tag, .ref-dangling-tag` 共享样式）；②重复组装
  过滤上下文 → 提取 `refFilterContext()`（refUI + 词表）两处渲染共用；
  ③loadKitVocabulary 的 `typeof renderReferences === "function"` 守卫 → 删除
  （同脚本函数声明恒在，防御性噪声）；④tests 双 extract（refFilterEntries 无
  注入 + refFilterEntriesD 带注入）→ 合并单一 extract（旧 extract 的
  refDanglingAnchors 自由变量是潜在 ReferenceError 地雷）。
- 判断级不修：refStats 悬空计数「二次调用 refDanglingAnchors 谓词」——语义
  各自成立（视图内悬空数），非重复逻辑；Data Clumps（两词表恒成对传参）——
  签名与 spec 契约一致；冒烟 t04b 同源自比（DOM↔纯函数一致性）——独立性由
  编辑闭环段提供（行为端到端 + 服务器直查）。
- 既有缺陷修复（顺带）：冒烟首屏「固定等待」竞态（reload 后就绪条件提前满足、
  loadReferences 未完成 → 偶发假 FAIL）→ 改轮询 refEntryCache 非空（≤10s×250ms），
  连续两轮全 PASS 验证稳定。
- 验证：tests/js 336 绿（+6）、冒烟 43 项 PASS（工单 04 段 8 项：数据源非空 /
  行内 ⚠ 数 / 红段存在性 / 点击过滤 / 再点取消 / 临时条目 ⚠ / 编辑改正 ⚠ 消失 /
  清理零残留）、pytest 全量绿；截图证据 04-dangling-full.png（全量态 ⚠×2 + 红段）
  / 04-dangling-filtered.png（点击红段后仅 2 悬空行 + 统计联动「共 2 条」）。
