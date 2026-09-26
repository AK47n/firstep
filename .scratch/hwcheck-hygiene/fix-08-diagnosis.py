"""fix-08-diagnosis.py — 用**复核过的机制**替换工单 08 票面里的诊断段。

为什么：评审 Spec 轴抓到一段硬伤——票面写的「真因 = 派发落在被重绘换掉的节点上」当时是
**从 `ci-gate-fixes/11` 继承的**，本单的定点压测每轮只加**一件**、而那个机制要求**同时有多件**
（点第 1 件的重绘会把第 2 件的节点摘掉）⇒ 那一跑的"零命中"什么也没证明。
本单随后补了 `--chips=2 --single` 的测量，**复现率 100%**，机制这才被自己的读数钉住。
这个脚本把票面里那两处（验收段的结论、以及第三节的诊断正文）换成复核后的版本。

用法（幂等）：python .scratch/hwcheck-hygiene/fix-08-diagnosis.py
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TICKET = REPO / ".scratch/hwcheck-hygiene/issues/08-ledger-and-aftereach-diagnosis.md"

OLD_START = "### 三、`[afterEach]` 告警：诊断（本单的重点）"
OLD_END = "### 四、读数（本机实跑，落盘在本目录）"

NEW = """### 三、`[afterEach]` 告警：诊断（本单的重点）

**结论：夹具缺陷，不是产品缺陷。真因 = 夹具**一口气点掉所有 chip**，而产品的重绘会把
**第 1 件之后的 chip 节点**从文档里摘掉——它们那几次 click 白点，于是"等 10 秒仍不空"。
这个机制本单**用读数复核过**（不是从 `ci-gate-fixes/11` 继承的结论，见下面 ① 的第二版）。**

**① 复现 —— 第一版量错了形状，第二版拿到 100% 复现率**（这一段的过程比结论值钱，如实留档）：

| 回路 | 轮数 | 命中 |
|---|---|---|
| 整条 `hwcheck.spec.mjs` 连跑（`loop-08-aftereach.py`） | 18 | 0 |
| 定点压测 **每轮只加一件**（`--chips=1`，默认）+ 换前置动作 + CPU 压慢 | 24 + 40 + 60 | **0** |
| 定点压测 **每轮加两件、只派发一次**（`--chips=2 --single`，**夹具的真实形状**） | 10 + 24 | **10/10、24/24 清不掉**（每次只剩最后一件，`派发前 chips=2 / 派发后 chips=1`） |
| 同一形状走**夹具现在的重试派发**（`--chips=2`，不 `--single`） | 10 | **0**（p50 7ms） |
| 整套浏览器门禁（6 spec / 48 条） | 1 次 | 0 |

> ⚠ **第一版的漏洞**（评审 Spec 轴当场抓到，记账在此）：`--chips=1` 时"只派发一次"和
> "连派发两次"都能清掉——第 2 次落在空集上本来无害。所以那一版 124 轮零命中**既不能证实
> 也不能证伪**那个机制；而票面当时已经把它写成"真因"。第二版把形状改成 ≥2 件之后，
> **复现率从 0 变成 100%**——这才是"稳定复现"该有的样子，也才是这条判据的强度所在。

**② 真因**（读代码 + CI 日志 + 上面第二版的读数）：

* 告警那句 `[afterEach] 器件集未清干净：…` 只在 `clearDevices()` **连续 5 轮**都没等到空集时
  才打（`tests/browser/hwcheck.spec.mjs` 的 `afterEach`）——它是**判据**，不是噪声。
* 机制：chip 容器每次选择变化都 `box.innerHTML = …` **整块重绘**；而夹具那一次
  `page.evaluate` 是**一口气点掉所有 chip** 的 —— 第 1 件的 click 触发重绘，
  **其余 chip 的节点当场从文档里被摘掉**，它们那几次 click 落在游离节点上（白点）。
  两件就必现（第二版读数 10/10 + 24/24），一件时看不见——**"偶发"的表象来自夹具里
  chip 数量与重绘时机**，不是产品时快时慢。
* 产品侧**不需要改**：同一形状走重试派发（每轮重新查询、点当拍活着的那一件）10/10 收敛
  （p50 7ms）；也就是说"点一下移除一件"这条产品路径本身是确定性的。
* CI run `36218384073` 的原始报文是**单轮版**的（`page.waitForFunction: Timeout 10000ms
  exceeded`，还没有后来那句"连续 5 轮"），且它从 `afterEach` 冒到用例体内
  （`检测页 → 生成页` 那条红 12.4 秒，上跑同一条是绿的）——与"多件同时清"这个形状一致。

**③ 结论二选一**：**夹具缺陷**（修法已在 `ci-gate-fixes/11` 的 `e0b41261` 落地：
重试派发 + 真清不干净仍大声抛错，判据没被削弱；**本单不改夹具行为，只把机制与读数钉在
注释里**，并把"这行是判据"这件事写进 `afterEach` 上方那段）。**为什么不是产品问题**：
夹具用 `dispatchEvent` 模拟点击、还在一拍里点掉一整批节点，本来就该容忍"重绘换掉了后面的
节点"；换成真鼠标点（`click()`）会等元素稳定，不存在这个形状。

**没做也不该做的三件事**（票面明令）：没把 `console.log` 改成静默、没放宽等待、没 `skip`。

"""


def main() -> int:
    raw = TICKET.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    if "第一版量错了形状" in text:
        print("已替换（复核版诊断段已在）——不再重复改写")
        return 0
    if OLD_START not in text or OLD_END not in text:
        print("✗ 找不到第三节的边界锚点（标题行）——未改动任何字节", file=sys.stderr)
        return 1
    head, rest = text.split(OLD_START, 1)
    _old_body, tail = rest.split(OLD_END, 1)
    text = head + NEW + OLD_END + tail
    TICKET.write_bytes(text.encode("utf-8"))
    after = hashlib.sha256(TICKET.read_bytes()).hexdigest()
    print("已把第三节换成复核版（含第一版形状错误的记账）")
    print(f"sha256：{before} → {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
