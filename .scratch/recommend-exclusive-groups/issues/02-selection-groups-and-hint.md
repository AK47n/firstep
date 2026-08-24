# 02 — 推荐链路组派生 + done 载荷 + hint 兜底

**要做什么：** AI 推荐完成后，推荐结果载荷带「功能组选择卡」数据：命中组（组内
成员被推荐）与 hint 组（赛题 manifest 声明疑似需要、AI 未命中）都出卡；AI 输出
契约不变（组为机器侧派生）。2024H topic manifest 声明 `hint_module_groups:
["attitude-hold"]`——即使 AI 漏了姿态模块，前端也能拿到「AI 未推荐，题面疑似
需要」的航向保持选择卡。

**被谁阻塞：** 01（组定义来自摘要投影）

**状态：** resolved

- [x] `build_exclusive_groups` 纯函数：`(selection_modules, group_defs, platform)` → 命中组列表（{id, label, members:[{slug, role}], recommended:[命中 slug], hint: false}）；平台成员过滤；单成员组不出卡
- [x] `run_recommendation` done 载荷增 `exclusive_groups`（仅命中组或 hint 组非空时落键；旧载荷逐字节兼容）
- [x] topic manifest 可选 `hint_module_groups`（组 id 清单）解析进 `TopicEntry`（缺省空）；done 载荷对 hint 组无条件出卡（hint: true，recommended 可空）；hint id 库内无对应组 → 静默忽略不炸推荐
- [x] 2024H topic manifest 登记 `hint_module_groups: ["attitude-hold"]`
- [x] 单测：命中派生 / 平台过滤 / 单成员组不出卡 / hint 触发 / hint 未知 id 忽略 / 无组库不落键；pytest 全绿 + mypy src 干净

**Notes:** 实现：`build_exclusive_groups`（命中卡按库登记序、hint 卡按声明序；平台投影经
`scope_group_members` 共享实现）+ 卡片构造助手 `_group_card`；run_recommendation 在
references 组装后、emit.done 前调用，非空才落键。generator.py：TopicContext 增
`exclusive_groups`（全平台视图）/`hint_module_groups`；_no_topic_context 与显式路径
对称（先全量计算再平台过滤）。topic_library.py：TopicEntry 增 `hint_module_groups`
（programs 同款严格校验）。2024H manifest 登记 `["attitude-hold"]`。

测试：+20（test_selection 11：8 纯函数 + 3 done 载荷；test_topic_library 7：解析 +
6 坏形状参数化；test_generator 2：双上下文装配）；全套 pytest 2287 passed（50s）；
mypy src 0 错误（60 文件）；真实库冒烟：full-view 两组、pid+xunji@mspm0 命中卡
recommended=[pid,xunji]、motor+hint→hint 卡 recommended=[]、stm32 视图 []、
2024H entry hint=("attitude-hold",)。

双轴审查（基线 5a67e34，双后台子代理）：Standards 轴**无硬违规**，判断项 3 条：
①平台成员过滤/单成员剔除规则与 collect_exclusive_groups 双份实现且 docstring 与
实现不同步 → 已收敛：平台投影提取为共享纯函数 `scope_group_members`（manifest.py），
collect 平台分支与 build 两侧共用；相关 docstring 同步修正（collect 的 platform
分支按 01 契约保留——库级平台视图 API + 既有测试，真机 flow 走全平台视图+build
过滤，已注明边界）。②命中/hint 卡 dict 构造逐字重复 → 提取 `_group_card`。③hint
查找 O(n) + 裸 str → 仅记录（与仓库风格一致）。Spec 轴**通过**（无实质缺陷），
附 2 澄清 + 1 补注，均已处理：role 回退——01 已强校验 role 非空，属 spec 文本遗留，
已修正 spec.md:160-162；签名追加 `hint_module_groups` kwarg——hint 兜底所需，保留；
`recommended` 为成员登记序（非 AI 推荐序）→ spec.md:103-106 已补契约注明（AI 首选
由 `data.modules` 序决定），防 04 前端误读。审查后小重构复核：受影响文件 306
passed + 全套 2287 passed + mypy 0 错误（重构后全套重跑）。
