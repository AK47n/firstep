# 01 — 并发记录写用例：给两次真实 `os.replace` 排序（根治已知假红）

**要做什么：** `tests/test_hwcheck_triage.py::test_concurrent_record_writes_share_no_tmp_file` 在机器忙时
会以 `PermissionError(13, 拒绝访问)` 红——**同样能抓真缺陷，但不再受平台竞态影响**。

**被谁阻塞：** 无。

**状态：** resolved

- [x] 给两次真实替换**定序**：第二个写者**整条走完**（含它自己那发真实 `replace`）→ 再放行第一个
- [x] 判据三条**一个不动**（无异常 / 零残留 / 读回的是其中一个写者的内容）
- [x] 用例注释写清"为什么排序"（平台行为 vs 被测缺陷），并注明它仍能抓到"临时名互抢"
- [x] **反向验证**：把被测实现临时换回固定临时名（内存里 monkeypatch）→ 该用例必须红；复原
- [x] 连跑该用例 20 轮全绿（本机）
- [x] 提交信息中文

## Comments

### 改了什么（只动编排，不动判据）

`tests/test_hwcheck_triage.py::test_concurrent_record_writes_share_no_tmp_file`：
在 `second.start()` 之后加 **`second.join(timeout=30)` + 一条"它真的走完了"的断言**，
**再** `release.set()` 放行第一个。理由（写进用例注释了）：两次真实 `os.replace` 一旦重叠，
Windows 会对**同一目标**回 `PermissionError(13)` / `WinError 5`——那是**平台行为**，
`record-write-hardening/07` 的对照读数（固定名 25/400、唯一临时名 30/400，无统计差别）就是这么来的。
docstring 补了一句"第二个整条结算完才放行第一个"。

### 反证（判据强度没被削弱）

`.scratch/backlog-agent-sweep/probe-01-reverse.py`（真改 `atomic_io.py` 再逐字节复原）：

| 步骤 | 读数 |
|---|---|
| 前置 | `atomic_io.py` sha256 `097628cee1d8f83a…`（LF 检出） |
| 注入旧形态 | `tmp = path.with_name(f"{path.name}.tmp")`（固定临时名） |
| 注入后跑该用例 | **红**，且红在机制上：`Left contains one more item: FileNotFoundError(2, '系统找不到指定的文件。')`——第一个写者的源临时文件被第二个吃掉，它的 `replace` 落空 |
| 复原复核 | sha256 **一致** ✅ |

⚠ 探针第一版把替换串也带了缩进（锚点是行内子串、不带缩进）→ 注入出来是 `IndentationError`，
**红是红了但红在语法上**；探针自己的"失败要指向被测机制"那条判据当场把它拦下来了
（这正是不满足于"看它红没红"的价值）。

### 读数

| 项 | 读数 |
|---|---|
| 该用例连跑 20 轮（本机） | **绿 20 / 红 0** |
| 定向复跑（该用例 + 解压三条） | **4 passed** — `targeted-sweep.txt` |
| 全量 `python -m pytest -n auto -q` | **5659 passed + 11 skipped**（106.35s）— `pytest-sweep.txt`（本条 +0 条用例） |
| 反证读数 | `probe-01-reverse.txt` |
