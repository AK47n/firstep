# Spec — 推荐缓存加模块库指纹（recommend-cache-fingerprint）

## 问题陈述

`validate_recommend` 只校验题面 / 平台 / 赛题键 / Q&A 指纹——**不查模块库内容**。库变了（模块增删 / 简介 / 能力 / 多实例标注变化）缓存照旧命中，直出旧推荐结果。实测：2026C 缓存是旧模块库时代生成的（OLED/LED 被归库外建议），库切换后缓存仍直出，用户看到"库内明明有 oled 却提示需自备"。CONTEXT 声称"库内命中每次现算，库会变"，但实现是整体直出。

## 方案

推荐缓存加**模块库指纹**（library_sha256）：指纹 = 装配点产出的全部 ManifestSummary 摘要行（to_line，prompt 可见契约）**排序后 hash**——模型看到什么就指纹什么（模块增删 / 简介 / 能力 / 多实例标注变化自动覆盖，顺序无关）。写缓存存指纹；校验时比对，库变 → 失效走真实推荐。

## 用户故事

1. 作为用户，我在库新增/修改模块后重推同题——不命中旧缓存，基于新库重新收敛。
2. 作为用户，旧格式缓存（无 library 字段）**保守失效**（无法证明匹配当前库，重推一次成本 < 用错结果成本）。
3. 作为用户，库没变时缓存照常命中（省钱不变）。
4. 作为用户，模块库指纹与 Q&A/平台/题面指纹是**与**关系（任一不符即失效）。

## 实现决策

- `recommend_cache.library_fingerprint(summaries) -> str`：`sorted(s.to_line())` 序列化 hash（顺序无关；to_line 是模型可见的唯一行渲染，字段变化自动覆盖）；空摘要 = 空库指纹（正常 hash，不特判）。
- `cache_recommend` 加 `library_fingerprint: str` 字段（payload 存 library_sha256）。
- `validate_recommend` 加 `library_fingerprint: str = ""` 参数（缺省空 = 不校验，兼容既有调用/测试）：
  - 缓存有 library_sha256 且 ≠ 传入 → 失效（"模块库与缓存时不同"）；
  - **缓存无 library_sha256（旧格式）→ 失效**（保守：无法证明匹配当前库，与 Q&A 先例不同——库永远存在，缺指纹 = 无法验证）；
  - 传入空 = 跳过（兼容）。
- webapp recommend 路由：装配点已有 `topic.manifest_summaries` → 路由计算指纹（写缓存与校验同源，一次计算两用）。
- CLI generate_check 的缓存格式兼容：加字段不影响 CLI 读取（它只取 done 等字段）；CLI 自带"缺失即报错"语义不动。
- 范围外：参考文件库 / 题库变化不进本指纹（references 已有 reference_ids 指纹与手动准入机制；锚定命中变化由用户重选触发）。

## 测试决策

- recommend_cache 单测：指纹对摘要内容敏感（改 description / 增删模块 → 变）、顺序无关、空库稳定；validate 库指纹匹配 / 不匹配 / 旧缓存无字段失效 / 空参数跳过；cache_recommend 落字段。
- webapp 集成：第一次推荐写缓存 → 改库（模块 description）→ 第二次推荐**不命中缓存**（真实收敛，FakeLLM 调用次数证明）；库不变 → 命中（done 直出）。
- 既有 validate 测试（不传指纹）原样绿（空 = 跳过）。

## 范围外

- 不重推既有缓存文件（用户现有缓存遇下次推荐自然失效重写）。
- 不动 CLI 语义。
