# 02 — 更新器解压：唯一临时名 + 异常清残渣（+ 判据）

**要做什么：** `tools/update-app.py::extract_zip` 中断（异常 / 被杀）之后，工具根里**不再留下
`*.update-tmp`**；正常解压的行为一个字节不变。

**被谁阻塞：** 无。

**状态：** resolved

- [x] `extract_zip` 改用**唯一临时名**（`<目标>.<pid>-<进程内计数>.update-tmp`）
- [x] 写盘段落加 `finally` 清残渣；**清理失败不许掩盖原异常**（`unlink` 失败静默放过）
- [x] 保持 `update-app.py` 的独立脚本边界（**不 import `contest_generator`**）
- [x] 新判据（`tests/test_update_app.py`）：① 中途抛错 → 目标目录零 `*.update-tmp`（且目标文件保持原样）；
      ② 正常解压 → 内容正确、零残渣；③ 两个"进程"（不同 pid 替身）解同一目标 → 临时名不互抢
- [x] **反证**：把实现换回固定名 → ① 必须红
- [x] 该文件定向 pytest 全绿 + 全量 `python -m pytest -n auto -q` 零回归
- [x] 提交信息中文

## Comments

### 改了什么

`tools/update-app.py`：

- 顶部加 `import itertools` + 模块级 `_TMP_COUNTER = itertools.count(1)`（与 `pid` 一起保证
  **同进程内**两个解压者也不撞名；进程重启后计数从 1 重来没关系——pid 变了）；
- `extract_zip` 的临时名：`<目标>.update-tmp` → **`<目标>.<pid>-<计数>.update-tmp`**，
  写盘段落包进 `try/finally`：换入成功时临时文件已不在；失败时清掉它，
  **清不掉也不许盖掉原异常**（照 `atomic_io.atomic_write_via` 的同一条边界）；
- docstring 写明"为什么就地写一份而不是 import `atomic_io`"：**这个脚本跑在应用被替换之前、
  包可能还没装好**，它有"只依赖标准库"的边界——改它时别顺手把那条边界破掉。

**产品行为零变化**（正常解压的产物与顺序一个字节不变），改的只是临时名与失败路径。

### 三条新判据（`tests/test_update_app.py`）

| 用例 | 判据 |
|---|---|
| `test_extract_zip_writes_content_and_leaves_no_tmp` | 正常路径：内容落对、`*.update-tmp` 零 |
| `test_extract_zip_failure_leaves_no_tmp_and_keeps_old_content` | 把第二个目标做成**目录** → 换入必然失败：失败前已换入的那条生效、失败那条没被动过、**目录里零 `*.update-tmp`** |
| `test_extract_zip_temp_names_do_not_collide_within_one_process` | 拦 `os.replace` 记下两次替换的**源文件名** → 两次必须不同、且都以 `.update-tmp` 结尾 |

### 反证（旧形态必须红）

`.scratch/backlog-agent-sweep/probe-02-reverse.py`（真改 `tools/update-app.py` 再逐字节复原）：

| 步骤 | 读数 |
|---|---|
| 前置 | `update-app.py` sha256 `981ab01c51610623…`（LF） |
| 注入旧形态 | 固定 `<目标>.update-tmp` + 无 `finally` |
| 注入后跑三条用例 | **红 2 条**（失败留残渣 / 同进程临时名相撞）——正是这两条该红的那两条 |
| 复原复核 | sha256 **一致** ✅ |

### 读数

| 项 | 读数 |
|---|---|
| `tests/test_update_app.py` | **10 passed**（7 旧 + 3 新） |
| 全量 `python -m pytest -n auto -q` | **5659 passed + 11 skipped**（106.35s，比本轮起点 +3 条）— `pytest-sweep.txt` |
| 反证读数 | `probe-02-reverse.txt` |
