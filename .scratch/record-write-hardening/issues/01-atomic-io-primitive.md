# 01 — 共享原语 `atomic_io`：唯一临时名 + 清残渣 + 按路径锁

**要做什么：** 仓库里有**一个**原子写的实现可复用——唯一临时名 → `os.replace` → `finally` 清残渣，
再加一把按记录路径的进程内锁。本单只把它立起来并自带判据，**不迁任何调用方**（零行为变化，
纯 expand 步）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09-27；读数、双轴评审处置、三段反证见文末）

**样板**（逐条搬，不重新发明）：`src/contest_generator/hwcheck_triage.py:896-919`
（唯一临时名 `f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}"` + `os.replace` + `finally` 清残渣、
清理失败不掩盖原异常）、`:387-406`（`_RECORD_LOCKS` + `_RECORD_LOCKS_GUARD` + `_record_lock`，
键 = `os.path.normcase(os.path.abspath(path))`）以及 `:387-391` 那段「表只增不减」的记账注释。

## 验收标准

- [x] 新模块 `src/contest_generator/atomic_io.py` 导出两个函数（签名与语义写进 docstring）：
      `atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None`、
      `path_lock(path: Path) -> threading.Lock`。
- [x] **唯一临时名**：临时文件名含 `os.getpid()` 与**进程内单调计数**（同进程两个写者也必须不同名——
      `codeview.py:362` 只带 pid，本单要比它更进一步，理由照 `hwcheck_triage.py:899-902`）。
- [x] **成功路径**：目标文件内容正确，目录里除目标文件外**一个文件都没有**（断言用 `iterdir`，
      不许用 `glob("*.tmp")`——`hwcheck-hygiene/03` 被评审抓过"新临时名匹配不到 = 断言空转"）。
- [x] **失败路径**：注入 `write_text` 抛错、注入 `replace` 抛错，两种都不留残渣，
      且**原异常照抛**（清理动作不许掩盖它）——评审指出第一版只钉住"抛了某个 OSError"，
      已改成哨兵异常同一性断言 + 补"清理也失败"那条（见下「评审处置」Spec ①②）。
- [x] **并发**：两个线程同时写同一路径（把本模块看到的 `os` 换成只暴露 `path`/`getpid`/`replace`
      的 `SimpleNamespace`，在 `replace` 上卡 `threading.Event`）→ 无异常、无残渣、内容是其中之一。
      **口径更正**：两次**真实** `replace` 刻意不重叠（评审 Spec ③：Windows 上并发 replace 同一目标
      会以 `WinError 5` 失败，那是"谁先落盘"的另一回事，混进来判据就测不准；那件事由各域 `update_*`
      的锁挡住）。
- [x] **锁同一性**：同一路径的两种写法（盘符大小写 / 正反斜杠）拿到**同一把**锁；
      同一目录下**不同文件名**拿到**不同**锁（这两条是 `idea_chat` 双文件不共锁的地基）。
- [x] 测试 `tests/test_atomic_io.py` 全绿（7 条）；读数落本目录（见下表）。
- [x] **不迁调用方**：改动只多出新模块 + 新测试文件（`src/` 里零调用方改动）。

## 结论（读数、评审处置、账）

**形状。** `atomic_io.py` 两个函数，逐条对照 `hwcheck_triage.py:896-919` / `:394-406` 搬：
`atomic_write_text`（唯一临时名 `…tmp-<pid>-<计数>` → `os.replace` → `finally` 清残渣，
清理失败不掩盖原异常）、`path_lock`（键 = `normcase(abspath(path))`，**含文件名** → 同目录两份记录
各拿一把锁；表只增不减的理由照 `hwcheck_triage.py:389-391` 记账）。**零调用方**（纯 expand 步），
字节格式归调用方（本原语只写字符串）。

**读数（本机实跑，全部 UTF-8 落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 定向 pytest | `python -m pytest tests/test_atomic_io.py -q` | **7 passed** | `probe-01-tests.txt` |
| mypy | `python -m mypy src/contest_generator/atomic_io.py` | **Success: no issues found** | `probe-01-mypy.txt` |
| 反证（三段） | `python .scratch/record-write-hardening/probe-01-red.py` | **PASS**：A 固定临时名 → 并发用例红；B 撤掉清残渣 → 两条残渣用例红；C 锁键不归一 → 锁同一性用例红。三段「声明 vs 实得 FAILED」逐条对账、复原 sha256 逐字节相同、复原后 7 passed | `probe-01-red.txt` |
| 全量 pytest | `python -m pytest -n auto -q` | **5611 passed + 11 skipped / 97.49s** | `probe-01-pytest.txt` |

**双轴评审（2026-09-27，`code-review` 跑在首版提交 `0b0788ee` 上）与处置。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Standards ① | 工单没翻牌（`claimed` + 空勾选框却已有读数） | 属实——流程本就是"实现 → 评审 → 翻牌"，评审在前；现已 `resolved` 并补齐勾选与读数 |
| Standards ② | **读数落盘违反 `local-environment` §2**：`Tee-Object` 写 UTF-16LE、无命令/时间/退出码头 | **属实，已修**：改用 `.scratch/hwcheck-hygiene/readings.py` 落 UTF-8；顺手给它加 `--out-dir`，其他批次不必再抄一份脚本（本目录读数全部按该工具重生成） |
| Standards ③ | 测试文件自述"不断言内部实现"，却断言了锁对象；spec 与工单也打架 | **属实，已修**：口径定 **工单优先**（锁同一性是 `path_lock` 的契约本身，不是实现细节），测试 docstring 记账，spec「测试决策」补例外说明 |
| Standards ④（判断项） | Duplicated Code：与 `hwcheck_triage.py` 私有副本逐句同形，且**没有计划中的收口步**（spec 只写"另开单"无单号，工单 06 白名单还把私有副本合法化） | **属实，已修**：新开**工单 07**（私有副本迁到共享原语；纯重构，既有测试即守卫），spec「范围外」改为指向 07 |
| Standards ⑤（事实核对） | docstring「Windows 抛 PermissionError（共享冲突）」**括号写错**（实测 `WinError 5（拒绝访问）`）；"产品侧所有调用都在 `path_lock` 里"把计划写成现状 | **属实，已修**：改为 `WinError 5（拒绝访问）` + "本批的调用方都在各域的 `update_*` 里持锁（工单 02–05；本单尚无调用方）" |
| Spec ① | 工单要「注入 `write_text` 抛错」只做了一半（只测了 replace 失败） | **属实，已修**：新增 `test_atomic_write_text_write_failure_leaves_no_residue`——刻意"先真写出半截临时文件再抛"，否则 `finally` 里没东西可清 = 判据空转 |
| Spec ② | 「原异常照抛」没钉住（`pytest.raises(OSError)` 对清理异常也成立）；`except OSError: pass` 从未跑到 | **属实，已修**：新增哨兵异常 `_Sentinel` 做同一性断言 + 新增"清理也失败"用例（把 `unlink` 注入成抛错，断言抛出来的仍是哨兵） |
| Spec ③ | 反证只撤了「唯一临时名」；清残渣、锁键归一没撤过；且探针与读数在立项提交里就落了，未绑定本提交字节 | **属实，已修**：探针扩成**三段**，每段逐条声明 + 对账、复原核对 sha256、复原后回绿；读数头部打印被撤源码与判据文件的 **sha256**，把读数绑到字节 |

**本轮顺带量到的两条工具事实**（写在这里，免得下一单重踩）：

1. **工作树文件可能是 CRLF**：git 碰过之后 `atomic_io.py` 的行尾变成了 `\r\n`，探针里用 `\n`
   拼的**多行锚点会静默失配**（单行锚点不受影响）——探针已改成按文件实际行尾拼锚点，并在读数里打印行尾。
2. **子进程中文输出要显式 UTF-8**：探针往 stdout 打中文时，Windows 控制台 GBK 会把字节编成 GBK，
   读数的 UTF-8 解码就成了乱码——探针开头加 `sys.stdout.reconfigure(encoding="utf-8")`。

## 备注

- 原语**只写字符串**（不吞 `json.dumps` 参数）：`master_store._write_meta` 现在**没有尾换行**，
  三个记录文件**有**尾换行，字节格式归调用方保持。
- 不提供通用 `update_json`：四个域读侧错误语义不同（见 spec「实现决策」）。
- 锁表只增不减这件事要在代码注释里记账（照 `hwcheck_triage.py:387-391`），别留成"忘了回收"的疑问。
