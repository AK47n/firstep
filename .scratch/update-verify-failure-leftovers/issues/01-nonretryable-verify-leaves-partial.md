# 01 — 不可重试的校验失败：清掉整卷半成品与边车（不留孤儿）

**要做什么：** 任务层拿到下载域异常时，先问一次既有分类——`error_kind == "verify"` 且
**不可重试** → 这份重下也不会有变化 → 清掉半成品与边车；其余（网络、取消、可重试的内容不符）
一律维持「留着当断点」。用户可观察的结果：撞上「发布物与清单不一致」而失败之后，
`updates/full/` 是空的，不再白占一整卷（线上完整包 ~765 MB）。

**被谁阻塞：** 无——spec 已拍板（`.scratch/update-verify-failure-leftovers/spec.md`）。

**状态：** resolved（2026-09-19）

**完成记录。** 修法按 spec 落地在**任务层共享原语**（`src/contest_generator/task_download.py`，
两条链路共用，故只改一处）：

- 新增纯谓词 `is_terminal_verify(exc)` = `error_kind(exc) == "verify" and not is_retryable(exc)`
  ——**不列举异常类型**（那等于在任务层再抄一份成员表），只消费下载域既有两个单源判据，
  于是后续新增的终态 verify 错误（见 `update-content-mismatch-retry-cap/02`）自动落进来；
- 异常路径改成：终态 verify → `clear_partial(dest)`（半成品 + 边车）；其余 → 写边车（断点）；
  取消路径与「长度到点 → 本地哈希不符」那条既有清理路径**一个字没动**；
- 顺带把 `download_and_verify` 的规则清单 docstring 补上这条例外（免得下一个读码的人
  以为「一律留断点」是全部）。

**判据强度探针 3/3 转红**（`.scratch/update-verify-failure-leftovers/verify-01-guard-strength.{txt,json}`）：

| 注入 | 结果 |
|---|---|
| ① 一律不清（回到改动前） | 转红 ✓（3 failed） |
| ② 一律清（连网络失败的断点也删） | 转红 ✓（2 failed） |
| ③ 判据换成「只看 error_kind」（可重试的内容不符也判终态） | 转红 ✓（1 failed） |

复原复核：`task_download.py` sha256 未变。聚焦测试：`test_task_download.py` /
`test_download_sequence_home.py` / `test_download_status_surface.py` 共 **59 passed**。

真机复跑单独一张单（`02-real-machine-and-ledger.md`，需要先把修好的源码放进沙箱）。

## 背景（真机原始证据）

演练 B2 场景三（`drill-02-degraded.py --only verify-size`，fixture 把卷声明成 1 MiB、
服务器照真载荷 3,961,701 B 发）：终态 `failed`、不重试、中文话术与 `error_kind=verify` 都对，
`updating.lock` / `pending-update.json` 都没留下，旧版本照常可用——**只有盘面不对**：
`updates/full/` 里留着整卷 3,961,701 字节 + 边车 73 字节，与
`.scratch/resumable-download/spec.md` 第 147 行「成功 / 校验失败时一并删除边车与半成品」不符。

## 验收标准

- [x] 任务层共享原语（`.scratch/resumable-download` 那支 `download_and_verify`）的异常路径：
      非取消异常下先判 `error_kind(exc) == "verify" and not is_retryable(exc)` →
      `clear_partial(dest)`（半成品 + 边车一起），否则写边车；判据只用下载域既有两个纯函数，
      **不新增第三张表**、不解析文案（谓词 `is_terminal_verify`）
- [x] 取消路径**不动**（半成品保留、不写额外边车）；「长度到点 → 本地算出的哈希不符」那条
      既有清理路径不动
- [x] 单测（`tests/test_task_download.py` 同族加格，注入假下载器）四格：
      不可重试 verify → **文件没了、边车没了**；可重试 verify（内容不符）→ 保持现状；
      截断（网络）→ **文件在、边车在**；取消 → 文件在、边车在
- [x] 反向注入探针（`.scratch/update-verify-failure-leftovers/probe-guard-strength.py`）：
      「一律不清」（回到改动前）与「一律清」（连断点也删）两处注入**都必须转红**；
      跑完复原并复核 sha256，探针输出落 `.txt`/`.json`（实测 3/3 转红、复原未变）
- [ ] 真机复跑：`run-real-machine.py`（drill-02 零改动；把修好的源码放进沙箱＝用户机上那代代码，
      这一步在证据里显式记账）→ `--only verify-size` 该格 `checks` 全为真、判红 0、
      `updates/full/` 为空；`--only cut-retry` 的「失败态留边车 / 成功后边车已清」仍成立
      → **移交工单 02**（真机是沙箱面的事，与本单的代码修复分开记账）
- [x] 既有守卫全绿：`tests/test_download_status_surface.py`（12 键契约与 `error_kind` 单源）、
      `tests/test_download_sequence_home.py`、`tests/test_full_task.py`、`tests/test_materials_task.py`
      → 聚焦四文件实测 59 passed；全套在工单 04 收口时跑一次
