"""add-08-b2.py — 把 B2 那条**判据抢跑**的诊断与修复记进工单 08 的票面。

为什么用脚本：票面正文混着全角标点，编辑工具在这份文件上反复不中（本轮已踩三次）；
Python 按字节改、按字节写回是确定的，且改完记 sha256。
本脚本在「### 四、读数」之前插入一节，并在读数表里补两行。

用法（幂等）：python .scratch/hwcheck-hygiene/add-08-b2.py
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TICKET = REPO / ".scratch/hwcheck-hygiene/issues/08-ledger-and-aftereach-diagnosis.md"

ANCHOR = "### 四、读数（本机实跑，落盘在本目录）"

SECTION = """### 三之二、顺带抓到并修掉的第二条：`launcher-reload` 的 B2 **判据抢跑**

修完上面那条之后，整套浏览器门禁在本机**红了**——红的不是检测栏目，是 `B2：登记那一发被丢一次
（坏连接）——重试救回，服务活着`，报文是「新文档那一发登记被丢掉之后只有 1 发请求——重试没发生」。
按同一套纪律（先复现、再定性、再改）走完：

**① 复现率 5/8 → 定性**（连跑 8 轮、每轮打印"reload 后到断言那一刻"的实测毫秒）：

| 实测 | 结果 |
|---|---|
| 断言在 reload 后 **322–339ms** 返回 | **红 5 轮**（只数到 1 发） |
| 断言在 reload 后 **362–372ms** 返回 | **绿 3 轮**（数到 2 发） |

**② 真因**：产品的登记重试写在 `index.html` 的 `setTimeout(…, **300**)` 里（`ci-gate-fixes/05`
立的，预算是 300ms），而这条用例的等待链 `waitNewDocument + waitReady` 实测 **322–372ms**
就返回了——**恰好落在 300ms 这个阈值两侧**。也就是说：**判据读的是一个"还没发生的事"**，
同一份产品代码一半轮次红、一半绿。CI 上不红只是因为那边每次都慢过 300ms；本机（以及任何
热起来的机器）一快就露出来。

> ⚠ 这条与第三节那条**是两回事**，别混：第三节是**夹具**在一拍里点掉一批 chip 导致派发丢失
> （产品没毛病）；这条是**用例**断言抢在产品重试之前（产品也没毛病）。两条都是判据侧的缺陷。

**③ 改法**（`tests/browser/launcher-reload.spec.mjs`）：断言之前**轮询等那个可观测事实**——
"浏览器又发了一发 `POST /api/tabs/register`"（`attempts - attemptsBefore >= 2`，
每 50ms 查一次、上限 5 秒），而不是"页面就绪了就断言"。**等的是事实，不是"再睡一会儿"**：
注入态下它照样要等满 5 秒然后红。

**④ 判据强度（`probe-08-red-b2.py` / `probe-08-red-b2.txt`）**：注入 = 把产品那一发登记的
重试关掉（`setTimeout` → 空操作，正是 `ci-gate-fixes/05` 修掉的那个形态）——
**注入态 3/3 红且都红在"重试没发生"那句；复原态 3/3 绿；`index.html` sha256 逐字节复原**
（`4b7b201d…38fc241`）。

**⑤ 读数**：修前连跑 8 轮 **红 5 / 绿 3**；修后连跑 8 轮 **绿 8/8**；
整套浏览器门禁 6 spec / 48 条 **48 / 0**。

**这笔账记在 08 而不是另开单**：它挡住的是本单的验收线（"浏览器门禁零告警"要求门禁先绿），
改动是判据侧三行 + 一段注释；**性质与本单第三节同类**（都是"判据读错了东西"），
放在一起读比拆成两张单清楚。**它不是本批 01–07 引入的**（那三行改动之前就在），
是这条门禁第一次在本机跑得够快才露出来。

"""

TABLE_ADD = """
| B2 判据抢跑（本节三之二） | 修前 8 轮红 5 → 修后 8 轮绿 8；反证注入 3/3 红 / 复原 3/3 绿 | `probe-08-red-b2.txt` |
| 门禁全跑（含 B2 修好之后） | **48 / 0**，零 `[afterEach]` 告警 | `probe-08-browser.txt` |
"""


def main() -> int:
    raw = TICKET.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    if "三之二" in text:
        print("已记录（B2 那一节已在）——不再重复插入")
        return 0
    if ANCHOR not in text:
        print("✗ 找不到读数节锚点——未改动任何字节", file=sys.stderr)
        return 1
    text = text.replace(ANCHOR, SECTION + ANCHOR, 1)
    text = text.rstrip("\n") + "\n" + TABLE_ADD
    TICKET.write_bytes(text.encode("utf-8"))
    after = hashlib.sha256(TICKET.read_bytes()).hexdigest()
    print("已插入「三之二」一节并在读数表补两行")
    print(f"sha256：{before} → {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
