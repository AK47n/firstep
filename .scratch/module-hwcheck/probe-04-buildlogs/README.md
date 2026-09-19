# 两组 buildlog 怎么读（工单 module-hwcheck/04）

`probe-04-compile-matrix.py` 每次运行都会把 UV4 的原始日志写到
`probe-04-buildlogs/`（按工程目录名命名）。这里留了两组，对应整改前后：

| 目录 | 是哪一跑 | 看什么 |
|---|---|---|
| `probe-04-buildlogs-broken/`（4 个） | **整改前**（2026-09-19 21:25 那一跑） | 专精形态的 22 个 error：中文字面量吞收尾引号（`#8`）、`void` 赋值给 `int`（`#513`）、跨平台常量未定义（`#20`）。这是本单最值钱的红证，**不删** |
| `probe-04-buildlogs/`（20 个） | 整改过程中的几跑（21:31 → 21:48），**最后一次全绿** | `error=0`；带时间戳可看出三次收敛：先治中文字面量 → 再治 `void` 初始化与跨平台常量 → 再治两条 `#177-D` 死代码（`hwcheck_verdict` / `hwcheck_report_int` 按需渲染） |

要复现自己那一次，跑：

```powershell
python .scratch/module-hwcheck/probe-04-compile-matrix.py
```

它只覆盖 **stm32 / UV4** 一路（本机没有 mspm0 那一侧的 gmake 判据，见工单
Comments 的「未修但记账」）。
