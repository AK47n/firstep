# 01 — 共享原语 `atomic_io`：唯一临时名 + 清残渣 + 按路径锁

**要做什么：** 仓库里有**一个**原子写的实现可复用——唯一临时名 → `os.replace` → `finally` 清残渣，
再加一把按记录路径的进程内锁。本单只把它立起来并自带判据，**不迁任何调用方**（零行为变化，
纯 expand 步）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed（2026-09-27 开工）

**样板**（逐条搬，不重新发明）：`src/contest_generator/hwcheck_triage.py:896-919`
（唯一临时名 `f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}"` + `os.replace` + `finally` 清残渣、
清理失败不掩盖原异常）、`:387-406`（`_RECORD_LOCKS` + `_RECORD_LOCKS_GUARD` + `_record_lock`，
键 = `os.path.normcase(os.path.abspath(path))`）以及 `:387-391` 那段「表只增不减」的记账注释。

## 验收标准

- [ ] 新模块 `src/contest_generator/atomic_io.py` 导出两个函数（签名与语义写进 docstring）：
      `atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None`、
      `path_lock(path: Path) -> threading.Lock`。
- [ ] **唯一临时名**：临时文件名含 `os.getpid()` 与**进程内单调计数**（同进程两个写者也必须不同名——
      `codeview.py:362` 只带 pid，本单要比它更进一步，理由照 `hwcheck_triage.py:899-902`）。
- [ ] **成功路径**：目标文件内容正确，目录里除目标文件外**一个文件都没有**（断言用 `iterdir`，
     不许用 `glob("*.tmp")`——`hwcheck-hygiene/03` 被评审抓过"新临时名匹配不到 = 断言空转"）。
- [ ] **失败路径**：注入 `write_text` 抛错、注入 `replace` 抛错，两种都不留残渣，
      且**原异常照抛**（清理动作不许掩盖它）。
- [ ] **并发**：两个线程同时写同一路径（把本模块看到的 `os` 换成只暴露 `path`/`getpid`/`replace`
      的 `SimpleNamespace`，在 `replace` 上卡 `threading.Event` 制造重叠）→ 无异常、无残渣、
      内容是其中之一。
- [ ] **锁同一性**：同一路径的两种写法（盘符大小写 / 正反斜杠）拿到**同一把**锁；
      同一目录下**不同文件名**拿到**不同**锁（这两条是 `idea_chat` 双文件不共锁的地基）。
- [ ] 测试 `tests/test_atomic_io.py` 全绿；读数落 `.scratch/record-write-hardening/probe-01-pytest.txt`。
- [ ] **不迁调用方**：`git diff` 只多出新模块 + 新测试文件（这条要肉眼核，别顺手改别的）。

## 备注

- 原语**只写字符串**（不吞 `json.dumps` 参数）：`master_store._write_meta` 现在**没有尾换行**，
  三个记录文件**有**尾换行，字节格式归调用方保持。
- 不提供通用 `update_json`：四个域读侧错误语义不同（见 spec「实现决策」）。
- 锁表只增不减这件事要在代码注释里记账（照 `hwcheck_triage.py:387-391`），别留成"忘了回收"的疑问。
