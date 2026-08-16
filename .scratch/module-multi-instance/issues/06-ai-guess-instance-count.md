# 06 — AI 自动猜实例数量 / 名称 + 收敛

**What to build:** 题面写「4 个指示灯」时，推荐链路 LLM 输出 led×4（红/黄/绿/状态灯），
`build_module_selection` 解析为实例清单（`instances`）；用户确认后仍可增删改。收敛循环
对多实例推荐同样收敛（连续两轮一致）。

**Blocked by:** 02（展开/命名契约冻结后）

**Status:** resolved

- [x] 推荐协议增实例清单输出：LLM 按题面猜实例数量与名称（led = 颜色），模型输出经
      `build_module_selection` 机械校验（数量 ≤ max、颜色词表、名称非空），非法大声失败
- [x] 「4 个指示灯」→ led×4（红/黄/绿/状态灯）有收敛测试
- [x] 用户确认后实例清单可增删改，再进生成（与 04 装配同源）
- [x] 旧推荐（无实例清单）= 单实例，现行为不变
- [x] pytest 全绿 + mypy src 干净

**Notes:** 1704 passed（基线 1684 + 20 新测试）+ mypy 44 文件干净 + node --check /
node --test 9 通过。

实现（文件边界外一处必要支撑改动——**manifest.py**：ManifestSummary 增
multi_instance 字段 + to_line「多实例」标注段；能力清单要随摘要同源走
（prompt 标注与解析校验单源），否则 build_module_selection 拿不到能力证据）：
- **llm.py**：模块清单行带「多实例」标注（上限+变体名，旧 manifest 行逐字节不变）；
  输出契约 modules 条目加 instances 形状 + 用户消息多实例猜测规则段（两条都**条件化**：
  库内有多实例模块才出，旧库提示词逐字节等价 = 验收②——契约无条件宣传 instances 会让
  旧库模型输出该字段被能力校验硬失败）；内置色 token 词表单源 = selection.LED_COLOR_MACROS
  （提示词 f-string join，改词表只改那一处）；parse 闭包传 multi_instance_slugs。
- **selection.py**：_parse_model_instances（name 非空 / variant 字符串 null 归一空串 /
  slug 在 known；非多实例模块带 instances = SelectionError，null = 无声明不拦——DeepSeek
  常补显式 null，空数组照拦）；_record_instances 跨需求聚合（同 slug 清单不一致 = 拒收，
  相同幂等接受）；build_module_selection 聚合进 ModuleSelection.instances（数量不设硬上限，
  上限守卫是 expand_instances 的活）；_functional_layer_key 纳入实例清单（ModuleInstance
  冻结结构相等，led×4 vs led×3 不误收敛）；run_recommendation done 载荷带 instances
  （无实例不落键 = 旧载荷逐字节不变）。
- **index.html**：renderRecommendResult 回填 instances 进 04 实例卡（pin 恒空 = 自动分配；
  载荷未猜的模块保留用户已配清单；前端不截断上限）。
- **CONTEXT.md**：「多实例」「模块摘要」两行更新。

验收④口径判例（刻意取舍，code-review 双轴确认）：**推荐链路**的模型输出错误沿用既有
SelectionError→LLMError 翻译（llm 拆层契约，与未知 slug 同口径：重试后 502 + 中文
message 经 SSE error 事件达用户）；**400 中文**由请求层 parse_instances（04）兑现——
AI 猜的实例回填前端后经 /api/generate 实例载荷走的就是这条 400 路。改翻译口径 = 动拆层
契约，超出本票边界。

留痕偏差（review 发现、已修）：契约段条件化（原无条件改契约违背验收②）；前端
slice(max) 静默截断删除（上限守卫归 expand_instances，且首推时 expanded 为空守卫
不生效 = 死代码）；_FunctionalKey 由 (name, variant) 嵌套元组改为直接嵌 ModuleInstance；
_parse_ai_instances 改名 _parse_model_instances。已知退化（无实际影响，docstring 留痕）：
旧契约（无需求层）路径 requirements 恒空 → 收敛键恒空、实例不参与收敛——生产提示词
恒走新契约。
