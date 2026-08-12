# 04 — ball_detect 伪题专用清理

**What to build:** ball_detect 已是驱动形态（K230 视觉串口帧解析 → BallResult 结构），题绑定主要在描述（"2026H 滚球题"）与命名语感。清理为四要素达标：manifest 描述重写（能力方向 = K230 视觉帧解析 / 球体检测，去题号年份绑定）；检查代码内题绑定（题号/年份注释、专用常量、启停/门限等逻辑——若有则按 ADR 0009 移出）；命名评估（slug 保留 = 能力方向词；BallResult 等符号名评估是否通用化——**若改名必须同步 pid 模块 deps 引用，与工单 03 协调，避免两边各改一半**）。**先决依赖：工单 01 已闭环（结构测试 + EXCEPTION_REGISTRY 例外注册表已立）——本工单清理 ball_detect 后必须删除注册表对应条目（不删 = 存量校验红）。**

**Status:** drafted

## 实施（细节实施会话定）

1. 代码检查：头注释/常量/逻辑层是否有 2026H 滚球题绑定；若只有帧解析 + 结构体 = 驱动达标，仅清理描述。
2. manifest.json：description 四要素（能力方向 = K230 视觉帧解析/球体检测），去题号年份。
3. 命名：默认不改（slug/符号名已是能力方向词）；若改 → 与 03 工单协调同批落地。
4. 结构测试 EXCEPTION_REGISTRY（tests/test_module_universality.py）删除 ball_detect 条目——不删 = 存量校验红。

## 文件边界

- library/modules/ball_detect/code/ball_detect.c、ball_detect.h、ball_detect_stm32.c/.h
- library/modules/ball_detect/manifest.json
- 交叉：pid manifest deps 引用 ball_detect（改名才动）
- **不动**：生成链路

## 验收

- [ ] 双平台编译 0 错（stm32 + mspm0 各一产物线）。
- [ ] 结构测试绿（ball_detect 不再命中黑名单）。
- [ ] manifest 四要素齐（无题号/年份/题名）。
- [ ] 命名决定有记录（不改 / 改 + 与 03 同步记录）。
- [ ] EXCEPTION_REGISTRY 已删 ball_detect 条目，删后全库测试仍绿。
- [ ] 工单补实施记录 + 验收勾选，Status resolved。
