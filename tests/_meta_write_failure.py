"""元数据写盘的失败注入（工单 backlog-closeout/05 的三库判据共用）。

三个库（模块库 / 参考库 / 赛题库）的「更新活条目 → 元数据 JSON 落盘」判据同形状：
注入「边写边炸」（异常期恢复跑得到）与「强杀」（恢复块跑不到）两种失败，注入代码
逐字相同——提成一份，免得三处各抄一遍（照 record-write-hardening/03 评审把重复
lambda 提到域层的先例）。

注入面刻意选 `Path.write_text`（不是某个私有函数）：**两种实现都会被这一发打中**——
裸写时半截内容落在目标文件上，原子写时落在临时文件上。判据正是靠这个差别分辨
（工单 05 的反证探针把实现退回裸写，这些判据必须变红）。
"""

from __future__ import annotations

from pathlib import Path

import pytest


class Boom(OSError):
    """业务失败哨兵（断言「照抛的是原异常」——`OSError` 太宽，清理异常也满足）。"""


class Killed(BaseException):
    """强杀模拟：不是 `Exception`，所以调用方的 `except Exception:` 恢复块不会跑。

    真 SIGKILL 在本进程里模拟不了；这个模拟比真强杀**宽松**（`finally` 还会跑、
    临时文件还会被清）。判据因此只取「元数据没被截断、条目仍读得出来」——那正是
    真强杀会毁掉的东西。
    """


def break_write(monkeypatch: pytest.MonkeyPatch, filename: str, boom: BaseException) -> None:
    """让**文件名以 `filename` 打头**的那次 `write_text` 先落半截、再抛 `boom`。

    覆盖两种形态：目标文件本身（`manifest.json`）与原子写的临时文件
    （`manifest.json.tmp-…`）——所以「撤掉原子写」的实现上这些判据也会红。
    先真写半截再抛是刻意的：只抛不写的话失败路径上没有半成品，判据会空转
    （`tests/test_atomic_io.py` 的评审记过这条）。
    """
    real_write_text = Path.write_text

    def partial_then_boom(self: Path, data, *args, **kwargs):
        if self.name.startswith(filename):
            real_write_text(self, str(data)[:5], *args, **kwargs)  # 真落半截
            raise boom
        return real_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", partial_then_boom)


def files_under(root: Path) -> set[str]:
    """目录下全部文件（相对路径）——判「零杂散」用清单对比，不猜临时名形状。"""
    return {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
