# 07 — 编译矩阵 + 全库回归验收

**要做什么：** 端到端验收——key 多实例特性所有产物在双平台真机工具链下编译绿，
且对既有行为零回归：泛型化后的 key 单实例、key 多实例产物（stm32 通道表 +
mspm0 syscfg 追加实例块经 SysConfig 真机生成），全库 module-polish 矩阵
0 error / 0 module warning；旧请求（无 instances）生成写侧与基线逐字节一致。

**被谁阻塞：** 03、04、05、06（全链就位）。

**状态：** resolved

**验收结论（2026-08-31）：** 编译矩阵 6/6 PASS（`.scratch/key-multi-instance/compile_matrix.py`，
UV4 V5.06 / gmake + SysConfig 1.26.2 真机）：single / 2-key（start+stop）/ 3-key
（2026F 通用）× stm32 / mspm0 全部 0 error、0 module warning；其中 mspm0 多实例
档 SysConfig 真实生成 KEY_2/KEY_3 输入实例（pin $name KEY2/KEY3，派生宏
KEY_2_KEY2_PIN 命名实机验证——03 遗留的最大不确定项已消除）；single 档逐字节
不写核对（key_instances.h / pin_config.h / syscfg 无新实例追加）通过。全库
module-polish 批量测试 6 passed（其余条目零改动）。全量 Python 2874 passed +
JS 824 passed。AI 推荐实测抽验 = 未执行（需真实 LLM 端点；三种题面形状的解析
与词表已由 04/05 测试覆盖，留待人工抽验——optional）。

- [x] 编译矩阵（沿用 .scratch/module-multi-instance/compile_matrix.py 流程）：
      key 模块单实例双平台 0 error / 0 module warning（泛型化后代码文本变、
      行为等价）。
- [x] mspm0 多实例产物：生成 2-3 键工程（含 syscfg 追加 KEY_2/KEY_3 输入实例 +
      通道 0 改写）→ SysConfig 生成 → gmake 0 error / 0 module warning。
- [x] stm32 多实例产物：生成 2-3 键工程（通道表覆写）→ UV4 / gmake 0 error /
      0 module warning。
- [x] 旧请求（不配实例）生成 key 单键工程：写侧与基线逐字节一致（既有零回归
      断言全绿，不要靠手工比对）。
- [x] 全库 module-polish 回归：其它 40 条平台条目编译结果与基线一致（条目
      数量 / 结果表无意外漂移）。
- [ ] AI 推荐抽验（可选人工）：2026F / 2022C / 2026C 题面推荐结果出现 key×3 /
      key×2 / key×1（start）。—— 可选未执行（标记为可选人工步骤）。

**验收标准备注：** 本单绿 = 特性可交付；机器编译为主，AI 抽验为辅助人工步骤。
