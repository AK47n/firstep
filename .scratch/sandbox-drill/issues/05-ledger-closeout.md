# B5 — 收口：账本与挂账单当场更新

**要做什么：** 本轮演练产生的事实（沙箱版本、落差、极端场景结论、编码钉实证）**当场**写回该记的地方，不留"下次就没人记得"的尾巴。

**被谁阻塞：** B1、B2、B3、B4。

**状态：** resolved（2026-09-18）

- [x] `docs/agents/local-environment.md`：**新增 1.5 节**（B1–B5 结论表 + 复跑命令）；第 1 节沙箱状态（升到 v1.2.1 / 基线仍 v1.1.0 / 痕迹清单 / **更正「盘上钉在 1.1.0」那条——实测是 1.1.1，且现在已升到 1.2.1，这台沙箱不能再重演「从旧版升上来」**）；第 2 节端口现状（8000/8020/8021）；第 2.5 节全局 editable 安装归零（更新器 `pip install -e .` 的连带 + 收尾卸载）
- [x] `.scratch/real-acceptance/issues/01` 的 **G1 后三步勾选**（含四分支实测、判红一条与撤回一条、两条真机才看得见的口径）
- [x] `E2E-8020.md` 追加 **L3 记录**（命令 / 预期 / 实测 / 原始输出路径 + 卡点清单 K7–K11）
- [x] 发现的缺陷按 `docs/agents/issue-tracker.md` 开工单并登记进 `.scratch/backlog.md` 第 8 节：
  `update-restart-stale-service/01`（🔴 用户可见）、`update-orphan-files/01`（🟠 卫生）、
  `update-verify-failure-leftovers/01`（🟡 卫生/可自愈）、`update-content-mismatch-retry-cap/01`（🟡 决策单）
- [x] 全仓测试跑一次（本轮的仓库改动只落在 `docs/` 与 `.scratch/`，但按纪律照跑；结果见下）
- [x] 提交（中文提交信息 + CHANGELOG 自动补录）

## 本轮改了什么（不含产品代码）

| 类别 | 文件 |
|---|---|
| 演练脚本与证据 | `.scratch/verify-gate-drills/`（4 支 drill + 1 支本地服务器 + 1 支更正脚本 + `verify-*.txt/.json` + `artifacts-b3/`） |
| 工单收口 | `.scratch/sandbox-drill/issues/01–05`（五张全 resolved） |
| 新开缺陷单 | `.scratch/update-restart-stale-service/`、`.scratch/update-orphan-files/`、`.scratch/update-verify-failure-leftovers/`、`.scratch/update-content-mismatch-retry-cap/` |
| 账本 | `docs/agents/local-environment.md`、`.scratch/real-acceptance/issues/01`、`.scratch/newuser-download/E2E-8020.md`、`.scratch/backlog.md` |

**产品代码零改动**（spec 实现决策：发现缺陷按 issue-tracker 开单，不在演练脚本里就地改产品）。

## 两处工单口径的更正（都写在对应工单里）

1. **spec 与工单编号不一致**：spec「实现决策」写 `drill-04-encoding-pin.py`，而工单 B3 写
   `drill-03-encoding-pin.py`、B4 写 `drill-04-full-pack.py`。**按工单**落地（03 = 编码钉、04 = 完整包），
   两个脚本名与证据文件名都以工单为准；spec 那处笔误留在原处未改（改 spec 会让已 resolved 的工单对不上）。
2. **B2「校验失败」预期与 spec 冲突**：工单原文预期「终态失败」，但 spec 第 122 行对「内容与清单不符」
   明文规定「退避重试直到对上或用户取消」。真机两支分别跑了（不可重试 / 可重试），**以 spec 为准**记账。

## 全仓测试

```
python -m pytest -n auto -q
→ 4536 passed, 1 skipped, 32 warnings in 89.84s (0:01:29)
```

（本轮仓库改动只有 `docs/` 与 `.scratch/`，`src/` 与 `tests/` 零改动；绿灯数与本轮开始前一致。）
