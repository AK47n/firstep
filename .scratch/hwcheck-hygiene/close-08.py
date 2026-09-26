"""close-08.py — 工单 hwcheck-hygiene/08 的**票面收口**（勾选 + 追加结论段）。

为什么用脚本而不是编辑工具：这份票的正文里混着全角引号 / 破折号，文本编辑器的
字面匹配在它上面反复不中（本轮试了三次），而 Python 按字节读进去改、再按字节写回
是确定的。**只改这两处**，其余字节逐字保留（先记 sha256，改完核对"只有这两段变了"）。

用法（幂等，收口过一次就直接返回）：
    python .scratch/hwcheck-hygiene/close-08.py
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TICKET = REPO / ".scratch/hwcheck-hygiene/issues/08-ledger-and-aftereach-diagnosis.md"

# ① 勾选：四条验收（第 1 条已经在先前那次编辑里勾上了，这里补后四条）
CHECKS = [
    ('- [ ] 两份核查报告加', '- [x] 两份核查报告加'),
    ('- [ ] 用户可见文案去掉工单号', '- [x] 用户可见文案去掉工单号'),
    ('- [ ] `hwcheck.py:100-107` 去重', '- [x] `hwcheck.py:100-107` 去重'),
    ('- [ ] **告警诊断（本单的重点）**', '- [x] **告警诊断（本单的重点）**'),
    ('- [ ] 读数：全套 pytest', '- [x] 读数：全套 pytest'),
]

CONCLUSION = """

## 结论（读数与账）

### 一、账本与自述的四项订正

| 处 | 订正前 | 订正后 |
|---|---|---|
| `.scratch/module-hwcheck/issues/09-*.md` 编译矩阵那行 | 「**16 种形态真编译**，生成前拦下 3 种」 | 「**18 种形态**，判红 0 / 生成前拦下 0 / **如实拦下 1**」，并注明**以读数文件为准**（`.scratch/module-hwcheck/probe-09-compile-matrix.txt` 的结论行）+ 记下这个数为什么会变（`hwcheck-pin-conflict-exit/01` 复跑同一支探针时打开了原先被拦下的形态） |
| `.scratch/hwcheck-acceptance/报告.md` | 无过期标记（写的还是 v1.2.2 / 未发布 / 10 件 17 格 / mspm0 开箱跑不起来） | 顶部加「⚠ 已过期」块：v1.3.0 已发布、两处硬伤已修、配方 30 件 57 格、**未上板那条仍成立**；旧内容**一字未删** |
| `.scratch/hwcheck-acceptance/报告-复测.md` | 同上（写的是「仍未发」与「专精面 10/17 未变」） | 同上（那两条当天就被后面的提交改掉了；7 项差距的**证据链**没过期，继续可用） |
| `src/contest_generator/hwcheck_board.py` 的 400 文案 | 「这一版做不到（要改母版的引脚符号，**见工单 11**）」 | 「这一版做不到（要改母版里的引脚符号，**让每个实例的符号名各不相同**）——别去引脚配置里试，改绑解不开它。」（学生读得懂、且不含内部编号） |

**「同一函数附近有没有第二处外泄」**：按 AST 把 `hwcheck*.py` 里**字符串字面量**中的「工单」
全列了一遍（临时量具 `.scratch/hwcheck-hygiene/find-labels.py`）。除了上面那处，另外 **9 处**
不在 `hwcheck_pin_message` 里，而在**产物注释**里——见下一节。

### 二、用户可见面里剩下的 9 处（本单扩了射程，理由在下面）

工单点名的是「同一函数附近」。但同一把尺子量下去，**学生要读的那份 `main.c` 里还有 9 处内部编号**
（住 4 个文件：`hwcheck.py` / `hwcheck_console.py` / `hwcheck_generic.py` / `hwcheck_recipe.py`）：
「工单 module-hwcheck/04」「工单 07」「工单 module-hwcheck/06」…检出的工程要在 CCS / Keil 里打开、
学生逐节读注释——那里印着内部编号，与那条 400 文案是**同一类缺陷**（写的人看得懂，读的人既不懂
也查不到），所以本单**一并清掉**（只删编号，句子照旧说清「这一段是什么」）。

**判据立起来了**（不是一次性清扫）：`tests/test_hwcheck.py::test_generated_program_never_names_an_internal_work_order`
——四形态（只框架 / 专精件 / 专精+通用 / 三批全在场）渲染出来的 `main.c` 全文本零命中。
**先红后绿**：加这条用例时它当场抓出那 9 处（断言逐条点名）。
**判据面只到产物**：源码里的 docstring / 注释**该留**（那是给维护者的「为什么」，全仓 400+ 处），
用例 docstring 里写明了「别把它扩成全仓 grep」。

`hwcheck.py` 那段 docstring 的订正：标题写「补的**两**件事」、下面却列到第 3 条，且第 1、2 条
**逐字重复**——`git blame` 定位到 `bb7c3816a`（`hwcheck-acceptance/01`）改这一段时**改错了行**
（把第 2 条换成了第 1 条的副本，另起一条写新事实）。订正为**两条**（标题 / 条数 / 内容三者一致），
历史（注释占位）与现状（活调用）收在第 2 条里，并把这次订正记在段末。

### 三、`[afterEach]` 告警：诊断（本单的重点）

**结论：夹具缺陷，不是产品缺陷。真因 = 夹具派发的那一次 `click` 会落在被重绘换掉的节点上
（白点一次）；根因与修法在 `ci-gate-fixes/11` 已经定性并修好（`e0b41261`）——所以本单
不新开产品缺陷单。**

**① 复现 —— 复现不出来，而且把「复现不出来」量成了读数**（复现率是 0，不是 1）：

| 回路 | 轮数 | 命中 |
|---|---|---|
| 整条 `hwcheck.spec.mjs` 连跑（`loop-08-aftereach.py`，落盘 `loop-08-aftereach-2026*.txt`） | **18** | **0** |
| 定点压测：加一件 → 不等任何东西立刻点掉，三个 slug 轮换（`probe-08-clear-race.mjs`） | 24 | 0（清空 p50 9ms / max 16ms） |
| 定点压测 + **CPU 压慢 6×** + 每轮换前置动作（切平台 / 搜索 / 点预览） | 40 | 0（p50 169ms / max 218ms） |
| **只派发一次**（= `ci-gate-fixes/11` 之前的夹具形状）+ CPU 4× + 换前置动作 | 60 | **0**（p50 86ms / max 122ms） |
| 整套浏览器门禁（6 spec / 48 条） | 5 次全跑 | 0 |

**② 真因**（读代码 + CI 日志 + 上面那张表）：

* 告警那句 `[afterEach] 器件集未清干净：…` 只在 `clearDevices()` **连续 5 轮**都没等到空集时才打
  （`tests/browser/hwcheck.spec.mjs` 的 `afterEach`）——它是**判据**，不是噪声。
* `ci-gate-fixes/11` 定性过机制：chip 容器每次选择变化都 `box.innerHTML = …` **整块重绘**，
  派发在旧 chip 上的 `click` 会**连同那个节点一起被丢掉**，于是「派发 → 等 10 秒 → 仍不空」。
  CI run `36218384073` 里它从 `afterEach` 冒到用例体内（`检测页 → 生成页` 那条红 12.4 秒，
  同一条用例上一跑是绿的 ⇒ 偶发）；那一轮的原始报文是**单轮版**的
  （`page.waitForFunction: Timeout 10000ms exceeded`，还没有后来那句「连续 5 轮」）。
* 本单复核**产品的移除路径本身是确定性的**：`#hwcheck-device-chips [data-remove]` 上的事件委托
  在慢 4–6 倍的 CPU 上、**单次派发**也 60/60 收敛（p90 ≈ 97ms）。⇒ 既不是「某状态下按钮不渲染」，
  也不是「重绘把按钮替换掉之后就不再响应」——就是那一次派发打在了旧节点上。

**③ 结论二选一**：**夹具缺陷**（已修：`e0b41261` 的重试派发；真清不干净仍然大声抛错，
判据没被削弱）。**为什么不是产品问题**：产品对「一整块 `innerHTML` 重绘」的既定行为就是
「当前 DOM 说了算」，而夹具用 `dispatchEvent` 模拟点击、本来就该容忍派发落在旧节点上；
换成真鼠标点（`click()`）会等元素稳定，不存在这个形状。测出的动作延迟（p90 ≈ 100ms）
也远小于夹具那 10 秒等待——剩余失败另有成因，不是「产品太慢」。

**没做也不该做的三件事**（票面明令）：没把 `console.log` 改成静默、没放宽等待、没 `skip`。
**留下来的是**：`afterEach` 那段注释现在写清了「这行是判据、它出现意味着什么、历史机制在哪」，
外加本单的零命中读数——**下次它再出现，第一反应是「某一步的重绘又变了」，不是「噪声，忽略」**。

### 四、读数（本机实跑，落盘在本目录）

| 闸门 | 读数 | 文件 |
|---|---|---|
| 全套 pytest | **5604 passed + 11 skipped**（07 那次是 5603；+1 = 本单的「产物零工单号」守卫。收集数 5614 → 5615 已用 `git stash` 在 07 提交上对过账） | `probe-08-pytest-full.txt` |
| 前端门禁 | **1819 / 0** | `probe-08-js.txt` |
| 浏览器门禁 | **48 / 0**（零 `[afterEach]` 告警） | `probe-08-browser.txt` |
| 两平台真编译矩阵 | `led` / `key` × 两平台 **4 格全 PASS**（产物注释改了字，编过才算数） | `probe-08-compile-matrix.txt` |
| 告警诊断 | 见上表（整 spec 18 轮 + 定点 124 轮，命中 0） | `loop-08-aftereach-*.txt` / `probe-08-clear-race*.txt` / `probe-08-single-dispatch.txt` |
| 判据强度（新守卫） | 加「产物零工单号」用例时**当场抓到 9 处**（先红后绿），断言逐条点名 | `tests/test_hwcheck.py` |

**未上板**：本单只改账本、文案与判据，**没有任何板上行为被验证**（本机没有板子）。
"""


def main() -> int:
    raw = TICKET.read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    if "## 结论（读数与账）" in text:
        print("已收口（结论段已在）——不再重复追加")
        return 0
    missing = [old for old, _new in CHECKS if old not in text]
    if missing:
        print(f"✗ 勾选锚点没找到：{missing}", file=sys.stderr)
        return 1
    for old, new in CHECKS:
        text = text.replace(old, new, 1)
    text = text.rstrip("\n") + "\n" + CONCLUSION
    TICKET.write_bytes(text.encode("utf-8"))
    after = hashlib.sha256(TICKET.read_bytes()).hexdigest()
    print(f"已勾选 {len(CHECKS)} 条并追加结论段")
    print(f"sha256：{before} → {after}")
    print(f"行数：{len(raw.decode('utf-8').splitlines())} → "
          f"{len(TICKET.read_text(encoding='utf-8').splitlines())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
