"""任务层共享的「一次分卷下载」（工单 resumable-download/10）。

**为什么有这个模块**：完整包（`full_task`）与资料库（`materials_task`）两条链路的
`_download_one` 里，除了两处不同，其余是**同一段动作序列**——判「长度到点 → 不发请求」、
判半成品可不可续、清来路不明的半成品、装配进下载缝、调下载器、失败时写边车、
复用下载器算好的哈希、校验失败清掉重下。这套序列承载的规则也逐条相同。

**量出来的事实**（`measure-10-duplication.py`，工单 10 的「先量再动」；
改动前那份从 `git show` 取，所以重排之后**仍然可复现**）：

| | 改动前（工单 09 收口时） | 改动后 |
|---|---|---|
| `full_task._download_one` | 55 行 | **16 行** |
| `materials_task._download_one` | 47 行 | **18 行** |
| 两处**完全相同**的代码行（去噪后） | **37 行** | 7 行（只剩调用与说明） |
| 真正的差异 | 3 处 | 2 处 |

三处差异是：**落盘路径**（`full/` vs `materials/`）、**整文件哈希的取法**、
**跟批次有关的记账**（`_current_part_name` / 换卷复位 / 快照写在哪一层）。
哈希那处顺手收到下载域单源（`download_resume.file_sha256`，原本有三个住处），
于是缝划在剩下两处：`download_and_verify(part, dest, *, retry, lock, cancel, resolve)`
收掉共同的，**不引入一组回调参数**。

**代价已经付过的证据**（「两边各改一次、漏一边就出 bug」）：

| 提交 | 工单 | 改动 |
|---|---|---|
| `22d0f643` | 03 | 「长度到点 → 不发请求」这条分支两边各加**一遍完全相同的代码**（评审发现：判据把**完整卷**删掉重下） |
| `2cad192c` | 07 | 边车口径改「开跑就写」，两文件的说明文字各同步一次 |
| `daf0319d` | 08 | 同一段序列里三处「清了却没重下」——下载域侧改好了，但任务层仍在**各自维护**这套序列（下一次同样的问题还是两边各改一次） |

**为什么不塞进 `download_resume`**：下载域**不许知道任务层的记账**——`part.ok` /
重试摘要 / 快照怎么写，都是任务层的策略。`tests/test_download_status_surface.py::
test_download_resume_module_has_no_status_knowledge` 钉着这个方向（工单 04 立的）。
依赖方向：本模块 → `download_resume`（策略函数）与 `task_retry`（观测），反向不许。

**半成品「保留还是删除」的分界仍是任务层策略**（工单 03 立的）：下载域只给
`is_resumable_partial` 这条判据，删不删由这里（代表任务层）决定。

**本模块还持另外两件「两条链路各写一遍就得同步」的事**（工单 11）：

- `resolve_task_download`——**注入缝的解析**（实例属性 → 类属性 → 缺省实现）。
  两处原本是 7 行**逐字相同**的代码（`22d0f643` 同一提交各抄一遍）；
- `restore_snapshot_parts`——**卷级断点的逐卷恢复**（认下「标了 ok + 文件在 + 内容哈希
  与清单一致」的卷）。两处原本有 16 行相同，差异只在「怎么遍历自己的卷」，
  故这里吃一个 `iter_parts` 而不是把两种遍历都塞进来。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol

from . import download_resume
from .download_resume import (
    DownloadCancelledError,
    DownloadResult,
    DownloadVerifyError,
    resumable_download,
)
from .task_retry import TaskRetryState, part_progress_callbacks

# 「本次不下载、直接进校验」的记号。
# 为什么要一个记号而不是空串：**空串本来就是合法的信号**——注入的下载器可能返回空 sha
# （假件 / 凑合的实现），那种情况要读盘自己算（重排前的 `if not digest` 就是这个意思）。
# 拿空串同时表示「没下载」和「下载器给了空 sha」，两件事就分不开了。
_NOT_DOWNLOADED = "\0"


class PartLike(Protocol):
    """分卷状态对象的**最小契约**（只声明本模块真的碰的字段）。

    两条链路的 `_PartState` 本来就地同形（`name` / `url` / `size` / `sha256` / `dest` /
    `ok` / `downloaded_bytes`），所以这里不需要一个共同基类，也不需要 duck-typing 的
    `# type: ignore` 撒一地：`part` 始终是**同一个对象**，只是它的类型由调用方声明。
    """

    name: str
    url: str
    size: int
    sha256: str
    dest: str
    ok: bool
    downloaded_bytes: int


def download_and_verify(
    part: PartLike,
    dest: Path,
    *,
    retry: TaskRetryState,
    lock: threading.Lock,
    cancel: threading.Event,
    resolve: Callable[[], tuple[Any, bool]],
) -> None:
    """一卷：下载（能续就续）→ 校验 → 记账。成功返回，失败**如实往上抛**。

    调用方负责的只剩两件（就是上面表里那三处差异去掉「哈希取法」之后剩下的）：
    **dest 怎么算**、**成功之后的卷级记账与快照**（`_current_part_name`、`_write_snapshot`）。

    `resolve` 是**注入缝的解析器**（→ `(下载函数, 是不是缺省的可续下载)`），由调用方给
    （就是各链路的 `_resolve_download` 壳，规则在 `resolve_task_download`）：
    解析顺序（实例属性 → 类属性 → 缺省）是任务对象自己的事，
    **而且只在真的要下载时才调用**——「长度到点」那条短路上不解析（与重排前一致：
    那条路走的是 `if/else` 的另一支）。

    四条规则（与重排前逐字等价）：

    - **已下字节 == 卷大小 → 不发请求**，直接进校验。少了这条，「盘上已经是一整卷」
      会被当「来路不明的文件」删掉重下，白下几百 MB（快照没记 ok 的卷就是这个下场）；
    - 有可续的半成品（边车对得上）→ 不重下，接着下（用户视角：上次断在这儿），
      摘要如实写「从多少接着下」；
    - **下载异常 → 半成品留着**（它就是断点），并把边车写出来——好让**换一次进程**
      也知道这份还能不能接着用；取消不算失败，不写边车；
    - **校验失败 → 清掉半成品与边车**（重下也不会有变化），抛下载域的
      `DownloadVerifyError`，好让 `error_kind` 仍是**单源**。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part.dest = str(dest)
    part.downloaded_bytes = 0
    have = dest.stat().st_size if dest.is_file() else 0
    digest = _NOT_DOWNLOADED
    if part.size > 0 and have == part.size:
        # 长度已到点：不再发请求，直接进下面那条校验。
        part.downloaded_bytes = have
    else:
        if download_resume.is_resumable_partial(dest, part.url, part.size):
            # 接着下：进度基准 = 盘上现有的，摘要把这事说清楚
            retry.message = download_resume.resume_message(have, part.size)
            part.downloaded_bytes = have
        else:
            download_resume.clear_partial(dest)   # 来路不明的不完整文件：不留
        download, is_default_now = resolve()
        on_progress, on_start = part_progress_callbacks(part, lock=lock)
        call = download_resume.as_task_downloader(
            download, cancel=cancel, on_start=on_start,
            default=is_default_now,
            # 两个重试观测回调（`before_retry` / `before_attempt`）由观测对象自己装配
            **retry.callbacks(part),
        )
        try:
            actual = call(part.url, dest, on_progress,
                          expected_size=part.size,
                          expected_sha256=part.sha256)
        except Exception as exc:
            if not isinstance(exc, DownloadCancelledError):
                # 失败：半成品是断点，留着；边车（谁留下的、期望多大）一并写出。
                download_resume.write_partial_marker(dest, part.url, part.size)
            raise
        # 缺省下载器已经把整卷算过哈希了（`DownloadResult.sha256`），不必再读一遍盘；
        # 注入的下载器返回裸 sha 字符串（甚至什么都不返回）→ 读盘自己算，
        # 与重排前的 `if not digest` 逐字等价。
        digest = (actual.sha256 if isinstance(actual, DownloadResult)
                  else str(actual or ""))
    if digest is _NOT_DOWNLOADED or not digest:
        # 没下载（长度到点）或下载器没给出哈希 → 读盘自己算
        digest = download_resume.file_sha256(dest)
    if str(digest).lower() != part.sha256.lower():
        # 校验失败 = 重下也是坏的：整份清掉（半成品 + 边车），不留孤儿。
        # 异常用下载域那一支（`DownloadVerifyError`），好让 `error_kind` 仍是单源。
        download_resume.clear_partial(dest)
        raise DownloadVerifyError(f"卷 {part.name} 校验失败（SHA256 不匹配）")
    part.ok = True
    part.downloaded_bytes = part.size
    retry.clear_message()


# ---------------------------------------------------------------------------
# 任务层的另外两件共享事（工单 resumable-download/11）
#
# 它们与上面的「一次分卷下载」是**两件事**，但同属「两条链路各写一遍就一定要同步」的那类，
# 所以家也在这里（工单 11 的「先量再动」量出来的账：解析逻辑两处 7 行逐字相同、
# 恢复逻辑两处 16 行相同）。
# ---------------------------------------------------------------------------


def resolve_task_download(task: Any) -> tuple[Callable[..., Any], bool]:
    """→（这次要用的下载函数, 是不是**缺省的可续下载**）——注入缝的解析**单源**。

    解析顺序：**实例属性**（构造注入 / 判据直接赋值）→ **类属性**
    （`monkeypatch.setattr(<Task>, "_download", …)` 这个既有注入点）→ 缺省的可续下载。
    实例属性仍等于缺省实现 = 没人注入过 → 让类属性优先
    （这就是既有 monkeypatch 判据继续有效的原因：`__init__` 总会把实例属性写成
    `download or resumable_download`，若不这样判，类属性注入会被那份缺省实现挡掉）。

    第二个返回值交给 `as_task_downloader`：缺省实现无条件吃
    `expected_size` / `expected_sha256` / `cancel` / `before_retry`；注入的下载器
    仍按既有的三参形态调用（除非它自己声明要吃那几个关键字参数）——
    「`(url, dest, on_progress)` 签名不变」这条契约因此零改动。

    **为什么收在这里而不是收成基类方法**：两条链路的类上各留一个一行壳即可，
    类层次零改动——壳之所以要留，是因为调用点（`download_and_verify(resolve=…)`）
    与**既有判据**都按方法取用：`tests/test_full_task.py` 与
    `tests/test_materials_task.py::test_task_download_defaults_to_resumable`
    各有一条 `task._resolve_download()[0] is resumable_download`。
    **壳不是「同形重复」**（它只剩一句转发，没有规则），规则（解析顺序与
    `is_default` 的语义）从今天起只有本函数这一份。
    """
    instance = task.__dict__.get("_download")
    if instance is None or instance is resumable_download:
        chosen = getattr(type(task), "_download", None) or resumable_download
        return chosen, chosen is resumable_download
    return instance, False


def restore_snapshot_parts(
    snapshot_path: Path,
    iter_parts: Callable[[Mapping[str, Any]], Iterator[tuple[PartLike, Any]]],
) -> None:
    """读上次快照，把**已经在盘上且内容对得上**的卷标记为跳过（卷级断点）——逐卷原语**单源**。

    调用方只负责**怎么遍历自己的卷**（`iter_parts(快照 JSON) → (part, 存档项) 迭代器`）：
    完整包是扁平分卷表、资料库是「批次 → 卷」两层，这一层形状差异留在各自的调用点，
    本原语**不碰**（工单 11 的缝就划在这里：抽掉的只有两处逐字相同的那 16 行）。

    三条规则（与两处旧正文逐字等价）：

    - 快照缺失 / 读不出来（坏 JSON）/ 存档项形状不对 → 当作**没有断点**，静默返回。
      快照是节流写盘的，断电、硬杀进程留下的半截文件很常见，任务对象在 `__init__`
      里就要能带着它起来（大不了重下一卷）；把启动流程炸掉才是真 bug。
      *存档项的形状判定是 `Mapping` + `.get(...)`（**不是**重建 `_PartState`）*：
      两条链路的 `_PartState` 都只有一个 `to_dict`、没有 `from_dict`（工单 12：
      那个 `from_dict` 全仓零调用点，已删），读侧一律把 JSON 存档项当 dict 用。
    - 只有**标了 ok、且盘上文件在、且内容哈希 == 清单 sha** 的卷才认。
      哈希那一格是安全线：没有它，一个被改坏 / 被别的程序覆盖的同名文件会被当
      「已下好」交给应用器。清单 sha 大小写不统一也要认（比对前 `.lower()`）。
    - 认下来就**三个字段一起**恢复：`ok` / `dest` / `downloaded_bytes`。
      少恢复 `downloaded_bytes` 会让进度从 0 起（用户以为白下了）；
      少恢复 `dest` 会让 `part_paths()` 交不出应用器的输入。
    """
    if not snapshot_path.is_file():
        return
    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        return
    for part, saved in iter_parts(data):
        if not isinstance(saved, Mapping) or not saved.get("ok"):
            continue
        dest = Path(str(saved.get("dest") or ""))
        if not dest.is_file():
            continue
        if download_resume.file_sha256(dest) == str(part.sha256 or "").lower():
            part.ok = True
            part.dest = str(dest)
            part.downloaded_bytes = part.size
