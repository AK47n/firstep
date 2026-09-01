# 2023/2025 控制题拆条 + 题库控制题分类（topics-control-2023-2025）

> spec 状态：待实施（用户已拍板：只拆控制题、本次不扩题型框架、加控制题分类标记）
> 关联：用户 2026-09-01 澄清「选题范围只做控制题（小车体或很简单其他题）」；README.md 已声明「当前版本定位：控制题专项」。

## 一、背景与动机

- 题库现状 15 条（2018C/2019A/2020C/2021F/2022C/2022H/2024H/2026A-H），**缺 2023/2025**——新题入口不完整。
- 素材本地现成：`library/topics/*/000_2017-2025_全国大学生电子设计竞赛真题汇编.pdf`（34MB，261 页，含 2017-2025 全部真题；**2023 = p171-205 共 11 题，2025 = p235-260 共 8 题**），无需联网或用户提供。
- 用户圈定 5 道控制题（全部经确认）：
  - 2023E 运动目标控制与自动追踪系统（p183，云台+相机追踪）
  - 2023G 空地协同智能消防系统（p189，无人机+小车协同）
  - 2023I 气垫悬浮车（p197，悬浮车姿态/位置控制）
  - 2025E 简易自行瞄准装置（p249，舵机云台自动瞄准）
  - 2025H 野生动物巡查系统（p258，自动行驶+识别巡视）
- 「控制题专项」定位需要在题库可见、可筛选 → 加分类标记机制（用户已拍板）。
- 现库 15 条几乎全为控制题（2018C 无线充电电动小车/2019A 电动小车无线充电/2020C 坡道行驶电动小车/2021F 智能送药小车/2022C+H 小车跟随行驶/2024H 自动行驶小车/2026D 陆空协同无人机/2026E 拼图/2026H 车载平衡滚球；2026A/B/C/F/G 为其他）——补标主要以「题名/任务性质」为准。

## 二、范围

1. 题库分类标记机制：后端词表 + manifest 字段 + 列表/详情透出 + 前端筛选与标签。
2. 全库补标：现有 15 条 + 新增 5 条全部标注（control / other）。
3. 5 道控制题拆条入库（topic.md + 小题 PDF + manifest.json）。

## 三、方案

### A. 分类标记机制（照参考库 topic_type 先例）

- `topic_library.py`：`TopicEntry` 加 `category: str = ""`；词表常量 `TOPIC_CATEGORIES = ("control", "other")`（空串 = 未标记，向后兼容）；新增 `validate_topic_category()`（照 `validate_topic_type`：词表外值报中文 `ValueError`）。
- manifest.json 增加 `category` 字段：`_build_manifest` 写入；load 校验（词表外 → `TopicLibraryError` 中文报错）；**身份键不变**（year/number/original_pdf/problem_md 不可改，沿用现有编辑接口只收三个可编辑字段的约定——category 为新增可编辑字段）。
- 列表/详情接口透出 `category`（`TopicSummary`/详情 dict 加字段）；`original_pdf_size` 等既有字段不动。
- 前端题库 tab：筛选下拉（全部 / 控制题 / 其他，选项单源 = 后端词表端点或常量）+ 条目 chips 显示（「控制题」「其他」徽标，照参考库 topic_type chip 先例 `js/fx/reference.js`）；新建/编辑表单加分类下拉（词表选项 LOADED from GET /api/topics/categories 或等价端点）。

### B. 全库补标（15 条 + 5 条）

| 条目 | 题名（判定依据） | category |
|---|---|---|
| 2018C | 无线充电电动小车 | control |
| 2019A | 电动小车动态无线充电系统 | control |
| 2020C | 坡道行驶电动小车 | control |
| 2021F | 智能送药小车 | control |
| 2022C | 小车跟随行驶系统 | control |
| 2022H | 小车跟随行驶系统（高职/赛区版） | control |
| 2024H | 自动行驶小车（巡线） | control |
| 2026A | AC-AC 变换电路 | other |
| 2026B | '无源'交流电流表及无线读表器 | other |
| 2026C | 基于无线通信的数字钥匙实验系统 | other |
| 2026D | 陆空协同无人机系统 | control |
| 2026E | 拼图装置 | control |
| 2026F | 李萨如图形显示控制装置 | other |
| 2026G | 周期信号测量分析装置 | other |
| 2026H | 车载平衡滚球运动控制系统 | control |
| 2023E/G/I、2025E/H（新增） | 见范围 | control |

> 注：2018C/2022C/2022H/2024H 等以各条目 topic.md 正文（任务描述）复核为准，如与题名有出入以拆条工单内核实结果修正本表。

### C. 拆条流程（每题，**复用既有机制**，零 LLM 改写）

> 核实结论：`topic_library.py` 已具备两套成熟机制——①`split_topics_document`（L567，多年长 PDF 确定性分块：YEAR_RE 年份章节 + TITLE_RE 题目标记（X 题）/行首 X 题：，已真机验证 163K 字符 69/69 全对，零 AI 改写）；②`enrich_topic_image_notes`（L230，存量条目补图注：渲染视觉 `pdf_page_render_notes` → 文字标注 `pdf_figure_annotations` → 内嵌图视觉 `pdf_image_notes` 三级降级链；共享 PDF 用 `locate_topic_pages` 限定页范围防跨题污染；幂等；失败静默）。**拆条不手写图注、不手工排版 topic.md**。

1. 定位页：fitz 文本定位 2023 章节（p171-205）与 2025 章节（p235-260）内各题起始页（2023E p183 / 2023G p189 / 2023I p197 / 2025E p249 / 2025H p258），用题目标记（X 题）核实精确边界。
2. 小题 PDF：fitz 提取该题页 → `.scratch/topics-control-2023-2025/pdf/<编号>.pdf`（几百 KB；**不放 34MB 汇编副本**——现 7 份副本均独立 inode 共 ~238MB，新条目不再复制，与 2026 条目「当年小题 PDF」先例一致）。
3. 确定性拆条：提取小题文本 → 调 `split_topics_document(text)` 得 TopicDraft（year/number/problem_text）；输出条数 ≠ 1 时用「章节切片」兜底（标题行起点到文档末尾的原文段落，照 split_topics_document 内部逻辑）。
4. 结构补全：年份标题 / `## 参赛注意事项` 等章节级头（若拆出草稿不含）由脚本从全文章节文本确定性拼接（照 2026H 结构：# 年份标题 → ## 参赛注意事项 → # 题名（X 题）→ 一任务/二要求/三说明/四评分标准）；不 AI 生成。
5. 视觉核对：渲染各题页面 PNG（`.scratch/topics-control-2023-2025/pages/`）+ read_image 检查文本层是否完整（图/表是否被漏）、评分标准表是否齐全。
6. 入库：`confirm_topics`（直接调用或走 /api/topics/confirm，pdf=小题 PDF，entries=[{year, number, problem_text, category}], program_dirs=[]）→ 一条目一目录（`2023E` 等）+ topic.md + manifest（category=control → 01 完成后字段落盘；original_pdf=小题 PDF 文件名）。
7. 图注：入库后 GET /api/topics/{key}（webapp L4783 触发 `enrich_topic_image_notes`）自动补 `[图N 标注：…]` 段；视觉不可用/失败静默降级——图注是增强不是阻塞，不阻塞拆条验收。

## 四、用户故事

1. 作为学生，在题库页选「控制题」筛选 → 看到全部控制题（含新增 2023E/G/I、2025E/H），边缘其他题被过滤。
2. 作为学生，打开 2023E 条目 → 看到完整题面（任务/要求/说明/评分标准）+ 图注 + 原小题 PDF。
3. 作为库管理方，编辑条目分类 → 词表外值被拒并中文报错（非法结构不落盘）。

## 五、实现决策

1. 分类词表英文值 `control/other` + 前端中文显示映射（照 topic_type 词表先例）。
2. 小题 PDF 替代 34MB 副本（省空间，与 2026 先例一致）。
3. 图注复用 `enrich_topic_image_notes` 三级降级机制（渲染视觉 → 文字标注 → 内嵌图视觉；幂等；失败静默），**不人工编写**；拆条视觉核对只用于验证文本层完整性（不用于生成图注）。
4. `programs` 初始空 `[]`（本机无对应参考工程目录；后续工单可关联）。
5. 老条目补标只改 manifest 的 category 字段，**不动 topic.md/PDF**。

## 六、测试决策

- pytest（`tests/test_topic_library.py` 扩展）：category 词表校验（合法/空/非法）；manifest 读写含 category；列表/详情透出；编辑接口 category 可改、身份键不可改。
- js 测试：筛选下拉选项单源 + 条目标签渲染 + 编辑表单分类下拉（照 reference.js 题型 chip 测试先例）。
- 拆条完整性（每道新题）：topic.md 含「一、任务」与「四、评分标准」段；小题 PDF 存在且页数 = 该题页数；manifest 字段齐全、category=control。
- 全库校验：所有条目 category ∈ 词表且补标完成态（无空串）。

## 七、范围外（明确不做）

1. 题型框架素材扩充（本次不扩；等真实例程素材——2026_04 地猛星配套含「云台（步进电机/SPI 屏/激光笔）例程」，可作 2023E 后续框架素材候选）。
2. 非控制题拆条（2022/2024/其他年份非控制题）。
3. 2022 广西/2024 赛区赛补充条目。
4. 参考素材与题库条目关联（如 2023E ↔ 2026_04 云台例程）。
5. programs 目录关联。
6. 题库 34MB 汇编副本去重（现有 7 份独立拷贝的处理另议，避免动老条目）。
7. 拆条后的 LLM 润色/题名补全等非确定性处理（保持零改写）。

## 八、工单（纵向切片）

1. `01-mechanism-category` — 后端词表/字段/接口透出 + 前端筛选与标签（含测试）。
2. `02-backfill-labels` — 15 条老条目补标 + 全库校验。
3. `03-split-2023` — 2023E/G/I 拆条（PDF 提取 → txt → topic.md + 图注 → 小题 PDF → manifest）。
4. `04-split-2025` — 2025E/H 拆条（同流程）。
5. `05-verify` — 全库验收（拆条完整性断言 + 前端 CDP 冒烟：筛选/标签/打开 2023E）。
