# 08 — config 模块决策参数剥离（工单 06 遗留，注册表清空后的结构性尾款）

**What to build:** 工单 06 真实 AI 校验实证：config 模块代码侧带 ADR 0009 判据④ 所禁的"专用判定参数"——config.h 的 `THR_UNLOCK_ENTER/EXIT`（近区阈值 130/140cm）、`THR_WELCOME_ENTER/EXIT`（远区阈值 230/240cm）、`THR_SENSING_MAX`（430cm）、`TAGID_MASK`、`FOV_HALF_ANGLE`、`ZIGBEE_TIMEOUT_MS`、`TAG_TIMEOUT_MS` 是 2026C 门禁场景的决策参数（真实 AI issues 原文见工单 06 实施记录），按 ADR 0009 应剥离进生成骨架；模块只保留纯驱动形态的集中外设引脚配置。工单 06 已把全部代码注释中性化（近区/远区/标签，机械黑名单全库=空），本工单处理结构性尾款——config 简介过真实 AI 校验（判据④ 代码侧）。

**Status:** drafted

## 实施（细节实施会话定）

1. 界定保留/剥离：引脚映射 + 通用参数（UWB/OLED/LED/蜂鸣器/DIP 引脚宏、滤波窗口）留 config；区域判定阈值 / FOV / 超时等 2026C 决策参数剥离——目标 = 生成骨架（2026C 生成时 AI 按题面写）或母版/参考文件库。
2. 2026C 生成链路同步：真机骨架 main.c 当前引用 config.h 的 THR_* 宏（05 真机验证产物，`s_zone_state` 状态区 + 阈值注释段），剥离后生成用例需同步（红证/绿证 + UV4 复验）。
3. 剥离后 config 简介真实 AI 全流程校验通过（判据①③④），注册表已空不需动。

## 文件边界

- library/modules/config/*
- 2026C 生成链路（generate_check.py 用例、母版、参考文件库）
- **不动**：其他模块、src/* 生成机制本身

## 验收

- [ ] config 简介真实 AI 校验通过（判据④ 无题绑定在代码侧成立，update_module_description 全流程）
- [ ] 2026C 真机全管线 UV4 编译通过，产物无回归（决策参数由骨架承担）
- [ ] 工单补实施记录 + 验收勾选，Status resolved
