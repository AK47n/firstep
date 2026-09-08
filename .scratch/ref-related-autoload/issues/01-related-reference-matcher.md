# 01 — 相关性匹配纯函数（词表 + 计分 + related_references）

**要做什么：** 为后续工单铺路的 prefactoring：本工单让「按题面文本与所选模块自动找出相关参考例程」的能力以纯函数形式可用——输入参考库根目录、题面文本、模块 slugs、平台与条数上限，输出按相关性得分降序的参考条目；词表不命中时返回空（零增量）。本工单无用户可见行为变化，纯函数将被工单 02（推荐候选扩容）与 03（骨架自动注入）使用。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `related_references(reference_root, *, topic_text, slugs=(), platform="", limit=0)` 实现于参考库域：limit=0 返回空；得分 > 0 才入选；得分降序 → 平台精确匹配优先 → id 稳定序；limit 截断
- [x] 词表单源：PERIPHERAL_TERMS（英文外设名/缩写全小写 + 中文外设词）与 MODULE_PERIPHERAL_TERMS（模块 slug → 词表项映射）；词表项带字母数字边界规则（英文项独立出现，防 canmv 命中 can）
- [x] 条目标题 token 化：按 `[-_\s()（）]` 拆分，数字字母连体为单 token（adc12 为一个 token）；term 为 token 前缀且剩余纯数字也算命中（adc → adc12）
- [x] 平台过滤沿用既有规则（非 any 平台只收匹配/any 条目）；`platform_matches` 谓词单址化移入 reference_library（selection re-export 同名，generator 等调用方无感）
- [x] 单测全绿（参考库域 seam，11 个新用例）：命中/未命中、canmv 反例、前缀命中、中文子串命中、slugs 映射、得分降序、limit、platform 过滤、平台平局键、空输入返回空、词表单源不变量
- [x] 词表不命中场景与现状一致（零增量断言：「完全无关词汇」→ 空）

---
**验收记录：**

实现：reference_library.py「相关性匹配」section（PERIPHERAL_TERMS 词表 + MODULE_PERIPHERAL_TERMS slug 映射 + related_references + _activated_terms / _text_has_term / _entry_score / _term_matches_token 私有谓词 + _is_ascii_term 共享形态谓词）；selection.py 删除本地 _platform_matches / platform_matches 实现，改为 re-export（platform_matches 单址 = reference_library，防分叉）。

真实库冒烟（library/references 152 条）：典型控制题面（ADC/UART/定时器/按键/OLED）→ 15 条命中全为 ADC12/定时器/PWM 类例程；「时钟/中断」题面 → GPIO/NVIC 中断类例程。死库激活验证通过。

审查整改（code-review 双轴）：① 降序测试初版未真实验证降序（uart 未激活、两条目同分）——题面补 uart 后 2 分 vs 1 分真实验证；② topic_text 契约对齐为 keyword-only 必填；③ 「平台匹配优先」排序键补实（同分 exact 平台 > any）+ 平局键测试；④ _ASCII_TERM 分支两处重复抽 _is_ascii_term；⑤ 删除 _platform_matches 纯转发（Middle Man）。

回归：tests/test_reference_library.py + test_selection.py + test_generator.py + test_skeleton.py + test_llm.py = 747 passed。

**状态变更历史：**
- ready-for-agent → claimed（实现开始）
- claimed → resolved（审查整改后，747 passed）
