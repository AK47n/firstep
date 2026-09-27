"""原子写 + 按路径进程内锁（工单 record-write-hardening/01）。

这一族的样板先例是 `hwcheck-hygiene/03`（`hwcheck_triage.py:896-919` 的唯一临时名与
`finally` 清残渣、`:394-406` 的按路径锁）——本模块把那两段**逐条搬**出来，
供想法商量 / 想法草稿 / 参数表 / 母版元数据四处复用，避免各写一份。

边界（照 spec「范围外」，别当成缺陷）：
- **本函数不内置锁**：调用方自己持 `path_lock(path)`——三个记录域走各域的 `update_*`
  （工单 02–04），母版元数据走 `_write_meta`（工单 05，整份重写、不读旧文件，所以那条路
  没有"读-改-写"可言），锁的粒度与顺序因此看得见。实测记一笔：两个线程对**同一目标**并发
  `os.replace` 时，Windows 上会以 `WinError 5（拒绝访问）` 失败——所以"先读后写"的调用方
  必须自己串行化，别指望原子写顺手把这个也解决了。
- **锁是进程内的**：本应用是单进程 `uvicorn.run`，跨进程并发不在射程，也不假装安全。
- **只清本进程本次写失败留下的临时文件**：进程被强杀留下的残渣不扫。
- **字节格式归调用方**：本模块只写字符串（缩进 / `ensure_ascii` / 尾换行都是调用方的事——
  实测这一批：母版元数据、两份聊天记录**没有**尾换行；`.contest_ideas.json`、
  `.contest_params.json`、`.hwcheck_record.json` **有**）。
"""

from __future__ import annotations

import itertools
import os
import threading
from pathlib import Path
from typing import Callable

__all__ = ["atomic_write_text", "atomic_write_via", "path_lock"]

_TMP_COUNTER = itertools.count(1)

_PATH_LOCKS: dict[str, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()
# 记账：这张表**只增不减**（每个见过的路径一把锁；照 hwcheck_triage.py:389-391 的理由）。
# 本地工具一次会话见过的记录数量有限（几十到几百），每把锁几十字节；弱引用反而会把
# "锁还被某个写者持有时被回收、下一个写者拿到另一把锁"变成真竞态——比这点常驻内存坏得多。


def path_lock(path: Path) -> threading.Lock:
    """取这条路径对应的锁（同一路径恒同一把；首用才建）。

    键按 `normcase(abspath(...))` 归一：Windows 上盘符大小写 / 正反斜杠的两种写法指的是
    同一个文件，用原样字符串当键会给它们各发一把锁 = 等于没锁。
    键**含文件名**，所以同一目录下的两份记录（`.contest_idea_chat.json` 与
    `.contest_params_chat.json`）天然各拿一把锁，互不阻塞。
    """
    key = os.path.normcase(os.path.abspath(path))
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[key] = lock
        return lock


def atomic_write_via(path: Path, write: Callable[[Path], None]) -> None:
    """原子写「你自己写临时文件」：`write(tmp)` 把内容写进临时路径，本函数负责换入。

    这是本模块**唯一的实现**（`atomic_write_text` 是它的薄壳，工单 backlog-closeout/03 收的）：
    临时名带 **pid + 进程内单调计数**（照 `hwcheck_triage.py:896-919`，比 `codeview.py:362`
    的只带 pid 更进一步）——固定名 `.tmp` 在两个写者并发时会互抢：一个刚写完、另一个把
    同一文件截断，`replace` 落盘的可能就是半成品，或者后一个 `replace` 直接失败。
    同进程内两个写者也必须不同名，所以加计数。

    `write` 拿到的是**临时路径**（此刻目标文件还没出现）——大文件（资料库解包）靠它
    **流式**写，别改成"先读进内存再传字节"。异常路径清残渣，且**清理动作不许掩盖原异常**
    （`unlink` 失败静默放过）。
    """
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{next(_TMP_COUNTER)}")
    try:
        write(tmp)
        os.replace(tmp, path)
    finally:
        # `replace` 成功时 tmp 已经不在了；失败时它还在，清掉它
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:  # pragma: no cover —— 清不掉也不该把原异常盖掉
                pass


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """原子写文本：唯一临时名 → `os.replace`；坏写不落半成品也不留残渣。

    实现走 `atomic_write_via`（临时名 / 换入 / 清残渣只有那一份），这里只交代"怎么写"。
    """

    def write(tmp: Path) -> None:
        tmp.write_text(text, encoding=encoding)

    atomic_write_via(path, write)
