#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/09：把 `fx/hwcheck.js` 按职责整段搬进六个模块，旧文件转 barrel。

用法：

    python .scratch/hwcheck-hygiene/apply-09-split.py            # 干跑：核对 + 打印，不落盘
    python .scratch/hwcheck-hygiene/apply-09-split.py --write    # 落盘（含搬前快照）

## 为什么是一支脚本，而不是手工剪贴

这是"零行为变化"的机械搬迁（约 2600 行移动量），**唯一的判据就是"一个字都没变"**。
手工剪贴没法自证，这支脚本把三件事变成可复算的断言：

1. **分区完备**：原文件的每一个字节都落进"文件头 / 某个声明单元 / 某个间隙 / 桥块"之一，
   四处拼起来逐字节等于原文件（`assert_partition`）。
2. **函数体逐字**：每个声明单元（连同它**紧邻上方**的注释块）整段搬走，中间不许重排、
   不许改空白；非导出的私有件（`hwcheckSameExclusiveGroup` / `hwcheckRoleLabeler` /
   `HWCHECK_ORDER_DESC_CHARS` / `HWCHECK_VERDICT_FALLBACK`）住在"间隙"里，跟着**下一个**
   声明单元走——它们的归属由 `--write` 前打印的间隙表逐条核对。
3. **名字面**：导出名集合与 window 桥名字并集搬前搬后相等（脚本自己算一遍，
   `tests/js/hwcheck-split-integrity.test.mjs` 再按**搬前快照**独立算一遍）。

搬前快照 `fx-hwcheck-before-split.js` 与源文件逐字节相同，**只在第一次 `--write` 时落盘**，
之后不再覆盖（它要一直代表"搬之前那一份"）；完整性自检与反证探针都读它。

## 为什么 barrel 的再导出写成 `export { … } from "…"`

`export-surface-guard` 的两条判据（D 零消费者导出 / T 调用位⇒函数形态）都要能穿过 barrel：
`export { x } from "M"` 既是"从 M 取 x"的消费边（判据 D 认），又被 `exportFormOf` 沿着
再导出链递归到声明处（判据 T 认）。另一种写法（`import { x } from "M"; export { x };`）
在判据 T 眼里是"解不开"——实测见 `.scratch/hwcheck-hygiene/probe-09-barrel-forms.txt`。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FX_DIR = REPO / "src" / "contest_generator" / "static" / "js" / "fx"
SRC = FX_DIR / "hwcheck.js"
SNAP = REPO / ".scratch" / "hwcheck-hygiene" / "fx-hwcheck-before-split.js"

# ---------------------------------------------------------------------------
# 名字 → 模块（按职责；顺序 = 原文件里的声明顺序）
#
# 段边界照工单 09 的"现状"表：1–171 状态 / 172–427 工程 / 428–702 器件与接线 /
# 703–829 逐件小节 / 830–919 命令台 / 920–1069 排障 / 1070–1153 自建件 / 1154–1365 衔接。
# 工单把"命令台"与"自建件"并入逐件小节那一件（同属"这一趟测什么、怎么复测"）。
# ---------------------------------------------------------------------------

STATE = [
    "hwcheckPlatformState", "hwcheckSelectPlatform", "HWCHECK_CHANNEL_KEYS",
    "hwcheckPickState", "hwcheckRequestPayload", "hwcheckDeviceSlugs", "hwcheckCanPreview",
    "hwcheckPlatformCardsHTML", "hwcheckHintHTML", "hwcheckErrorHTML",
    "hwcheckGenerateErrorHTML", "hwcheckDroppedNoteHTML", "hwcheckEmptyHTML",
    "hwcheckPanelHTML", "hwcheckCodeTarget", "hwcheckPreviewState", "hwcheckPlatformLabel",
]
PROJECT = [
    "hwcheckGeneratePayload", "hwcheckChecklistKey", "hwcheckCheckedIds",
    "hwcheckChecklistToggle", "hwcheckChecklistHTML", "hwcheckChecklistProgressHTML",
    "hwcheckBoardState", "hwcheckProjectState", "hwcheckChannelText",
    "hwcheckProjectInfoHTML", "hwcheckToolchainNote", "hwcheckChannelNoteHTML",
    "hwcheckUnverifiedNoteHTML", "hwcheckActionsHTML", "hwcheckProjectPanelHTML",
    "hwcheckRecentHTML", "hwcheckRecentEmptyHTML", "hwcheckProjectEmptyHTML",
    "HWCHECK_PARENT_KEY", "HWCHECK_LAST_DIR_KEY",
]
WIRING = [
    "hwcheckDevicePick", "hwcheckDeviceGroupNoticeHTML", "hwcheckDevicePool",
    "hwcheckDeviceKit", "hwcheckDeviceChipsHTML", "hwcheckDeviceEmptyHTML",
    "hwcheckMissingDevicesHTML", "hwcheckPinFixHTML", "hwcheckPinCapacityNoteHTML",
    "hwcheckWiringTableHTML", "hwcheckBoardSharesHTML", "hwcheckPinGroupsHTML",
    "hwcheckOrderDesc", "hwcheckOrderHTML",
]
PLAN = [
    "hwcheckSectionsState", "hwcheckSectionPlanText", "hwcheckSectionNoteHTML",
    "hwcheckSectionsHTML", "hwcheckUnspecializedHTML", "hwcheckSectionsEmptyHTML",
    "hwcheckConsoleState", "hwcheckConsoleNoteHTML", "hwcheckConsoleHTML",
    "hwcheckCustomState", "hwcheckCustomPlanHTML", "hwcheckCustomWiringHTML",
]
TRIAGE = [
    "hwcheckSymptomText", "hwcheckCanTriage", "hwcheckTriagePayload",
    "hwcheckChecklistPayload", "hwcheckAdviceState", "hwcheckRecordState",
    "hwcheckChecklistState", "hwcheckTriageErrorHTML", "hwcheckAdviceEmptyHTML",
    "hwcheckAdviceHTML",
]
HANDOFF = [
    "hwcheckHandoffPlan", "hwcheckHandoffMerge", "hwcheckHandoffPinNote",
    "hwcheckHandoffResultText", "hwcheckHandoffHTML",
]

MODULES = [
    {
        "file": "hwcheck-state.js",
        "names": STATE,
        "title": "状态归一 / 请求载荷 / 平台卡 / 提示与错误文案",
        "imports": ['import { esc } from "./core.js";'],
    },
    {
        "file": "hwcheck-project.js",
        "names": PROJECT,
        "title": "生成请求 / 编译降级 / 上板清单 / 最近几次检测 / 工程面板",
        "imports": [
            'import { esc } from "./core.js";',
            'import { TOOLCHAIN_NAMES } from "./env.js";',
            "// 提示壳与器件 slug 归一都在 state（生成载荷要用后者）。",
            'import { hwcheckHintHTML, hwcheckDeviceSlugs } from "./hwcheck-state.js";',
            "// 三个归一器（逐件小节 / 命令台 / 自建件计划）住在 plan：`hwcheckProjectState`",
            "// 把后端载荷一次折成 project 对象，缺谁都不完整。",
            "import {",
            "  hwcheckSectionsState, hwcheckConsoleState, hwcheckCustomState,",
            '} from "./hwcheck-plan.js";',
        ],
    },
    {
        "file": "hwcheck-wiring.js",
        "names": WIRING,
        "title": "器件选择 / 接线表 / 默认脚冲突 / 建议顺序",
        "imports": [
            'import { esc } from "./core.js";',
            "// chip 渲染取自模块库既有纯件（器件选择复用既有载荷与卡片/chip 渲染，",
            "// 不另造一套模块清单协议）。",
            'import { recommendChipHTML } from "./module.js";',
        ],
    },
    {
        "file": "hwcheck-plan.js",
        "names": PLAN,
        "title": "逐件小节 / 未专精点名 / 串口命令台 / 自建件的检测计划",
        "imports": ['import { esc } from "./core.js";'],
    },
    {
        "file": "hwcheck-triage.js",
        "names": TRIAGE,
        "title": "现象回填 / AI 排障（本栏目唯一的 LLM 入口）",
        "imports": ['import { esc } from "./core.js";'],
    },
    {
        "file": "hwcheck-handoff.js",
        "names": HANDOFF,
        "title": "检测页 → 生成页衔接（只带器件，不带引脚）",
        "imports": [
            'import { esc } from "./core.js";',
            "// 器件 slug 归一与平台展示名归 state（衔接的两条判据都要它们）。",
            'import { hwcheckDeviceSlugs, hwcheckPlatformLabel } from "./hwcheck-state.js";',
        ],
    },
]

BARREL_HEAD = """\
// fx/hwcheck.js — **过渡态 barrel**（工单 hwcheck-hygiene/09）：本文件只剩再导出，
// 由 10 号单删除（届时消费者改指下面这六个模块）。
//
// 为什么让它活一笔提交：1380 行按职责拆成六件是"零行为变化"的机械搬迁，却有 2600 行移动量。
// 这一步让**搬迁**与**迁移消费者**分成两笔 diff：消费者里的 import **一个字没动**
//（`ui/hwcheck.js` 与用例仍指 `/js/fx/hwcheck.js`）；跟着搬的只有两处**读源码文件**的断言
//（`tests/js/hwcheck.test.mjs` 的「fx 不得 import ui / 碰 DOM / 发请求」改成对六件逐个断言、
// `tests/test_hwcheck.py` 两处读路径改指新家）——钉在旧路径上它们要么恒真、要么红。
// 搬漏了什么由 tests/js/hwcheck-split-integrity.test.mjs
// 按搬前快照（.scratch/hwcheck-hygiene/fx-hwcheck-before-split.js）逐名逐字对账。
//
// 六件（按职责；它们之间的单向依赖写在 `hwcheck-state.js` 头部——那份是单源）：
//   hwcheck-state.js    状态归一 / 载荷 / 平台卡 / 提示与错误文案
//   hwcheck-project.js  生成请求 / 编译降级 / 上板清单 / 最近几次检测 / 工程面板
//   hwcheck-wiring.js   器件选择 / 接线表 / 默认脚冲突 / 建议顺序
//   hwcheck-plan.js     逐件小节 / 未专精点名 / 命令台 / 自建件计划
//   hwcheck-triage.js   现象回填 / AI 排障
//   hwcheck-handoff.js  检测页 → 生成页衔接
//
// ⚠ barrel **不再**发布 window 桥条目（桥由六件各自发布自己那一段，并集与搬前逐名相同）：
// 旧文件底部那一块 `Object.assign(window, …)` 已按声明的归属拆到六件里。
"""

# 模块头里的"模块约定"块**只写一份**（写在 state 那件），其余五件转引它——
# 抄六遍就是六份会各自漂移的散文，而判据钉的只是函数体（Standards 轴评审指出的）。
SHARED_HEAD = """\
// 模块约定（**单源**；改这里就够，其余五件只转引本段）：
// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**——函数体与注释
// 逐字保留，唯一的增量是文件头说明与 import 段。分工照旧（仓库既有约定）：只出字符串与
// 状态对象，**不碰 DOM、不发请求**；DOM 胶水全在 ui/hwcheck.js；加载顺序无关——六件只声明、
// 不在求值期做任何事。依赖方向（单向，无环）：state / plan / wiring / triage 是叶子；
// project → state + plan；handoff → state。window 桥条目由各件发布自己那一段（并集与搬前
// 逐名相同，由 tests/js/hwcheck-split-integrity.test.mjs 钉住）。
"""

# 搬前快照的 sha256（落盘那一刻实测；与 `git show HEAD:…fx/hwcheck.js` 逐字节相同）。
# **刻意写死**：快照必须永远是"搬之前那一份"，被静默替换（或误当工作副本改过）时这支脚本
# 要当场拒绝，而不是照着错的基线重切一遍、产物还照样自洽。
SNAPSHOT_SHA256 = "6f2591afbd696563d728067d4a02a7514fc4a0f7b17fa0328424403fcf72d6e7"


def mask(text: str) -> str:
    """注释 / 字符串 / 模板串的内容变空格（保留换行与长度）——括号配对只在掩码文本上数。

    本文件没有正则字面量（脚本 `assert_no_regex_literals` 兜底），所以不必判除号。
    """
    out = list(text)

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, len(out))):
            if out[k] != "\n":
                out[k] = " "

    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = i
            while j < n and text[j] != "\n":
                j += 1
            blank(i, j)
            i = j
            continue
        if c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
            continue
        if c in "\"'`":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == c:
                    j += 1
                    break
                if c != "`" and text[j] == "\n":
                    break
                j += 1
            blank(i + 1, j - 1)
            i = j
            continue
        i += 1
    return "".join(out)


DECL_RE = re.compile(r"(?m)^export (function|const) ([A-Za-z_$][\w$]*)")
BRIDGE_RE = re.compile(r"Object\.assign\(\s*window\s*,\s*\{")


def declarations(text: str, masked: str):
    """→ [{kind, name, start, end}]（start = `export` 那个字符，end = 声明收尾之后）。"""
    out = []
    for m in DECL_RE.finditer(masked):
        kind, name = m.group(1), m.group(2)
        if kind == "function":
            # 函数体的 `{` = **圆括号深度 0** 处的第一个 `{`：缺省参数里的对象字面量
            # （`opts = {}`）不是函数体（第一版就栽在这里，报"最后一个声明后还有内容"）。
            depth = 0
            open_at = None
            for i in range(m.end(), len(masked)):
                if masked[i] == "(":
                    depth += 1
                elif masked[i] == ")":
                    depth -= 1
                elif masked[i] == "{" and depth == 0:
                    open_at = i
                    break
            assert open_at is not None, f"{name} 找不到函数体"
            depth = 0
            end = None
            for i in range(open_at, len(masked)):
                if masked[i] == "{":
                    depth += 1
                elif masked[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            assert end is not None, f"{name} 的函数体括号没配平"
        else:
            end = masked.index(";", m.end()) + 1
        out.append({"kind": kind, "name": name, "start": m.start(), "end": end})
    return out


def unit_start(text: str, decl_start: int) -> int:
    """声明**紧邻上方**的连续 `//` 注释块起点（中间隔空行的不算——那属于"间隙"）。"""
    lines = text[:decl_start].split("\n")
    assert lines[-1] == "", "声明不在行首？"
    idx = len(lines) - 2                      # 声明所在行的上一行
    while idx >= 0 and lines[idx].lstrip().startswith("//"):
        idx -= 1
    start_line = idx + 1                      # 注释块的第一行
    return sum(len(line) + 1 for line in lines[:start_line])


def bridge_names(text: str, masked: str):
    """原文件底部 `Object.assign(window, { … })` 发布的名字（保序）。"""
    m = BRIDGE_RE.search(masked)
    if not m:
        return []
    depth = 0
    body_start = m.end()
    for i in range(m.end() - 1, len(masked)):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1
            if depth == 0:
                body = masked[body_start:i]
                break
    else:
        raise AssertionError("桥块括号没配平")
    names = []
    for part in body.split(","):
        clean = part.strip()
        if clean:
            names.append(clean)
    return names


def assert_no_regex_literals(text: str) -> None:
    """本文件的掩码器不判除号 —— 一旦出现正则字面量就当场喊，别让掩码悄悄错位。"""
    bad = re.findall(r"(?:=|\(|,|:)\s*/[^/*\s]", text)
    assert not bad, f"出现疑似正则字面量：{bad[:3]}（掩码器要跟着升级）"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build():
    # 取数面 = **搬前快照**（它一旦落盘就是"搬之前那一份"的权威副本）——于是这支脚本
    # 可以反复跑（改格式、重来一次），不会因为源文件已经变成 barrel 而失去输入。
    src = SNAP if SNAP.exists() else SRC
    raw = src.read_bytes()
    if src is SNAP:
        # 快照是**输入**，不是工作副本：被替换过就当场拒绝（否则会照着错的基线重切一遍，
        # 而产物照样"自洽"）。指纹是落盘那一刻实测的。
        got = hashlib.sha256(raw).hexdigest()
        assert got == SNAPSHOT_SHA256, (
            f"搬前快照的 sha256 变了：\n  期望 {SNAPSHOT_SHA256}\n  实得 {got}\n"
            "——它是'搬之前那一份'，不该被改。真要重来请连这份指纹一起更新，并说明为什么。")
    text = raw.decode("utf-8")
    assert_no_regex_literals(text)
    masked = mask(text)

    decls = declarations(text, masked)
    by_name = {d["name"]: d for d in decls}
    assert len(by_name) == len(decls), "导出名有重复"

    # 名字 → 模块（每个名字必须恰好登记一次）
    owner = {}
    for mod in MODULES:
        for name in mod["names"]:
            assert name not in owner, f"{name} 被登记了两次"
            owner[name] = mod["file"]
    missing = [n for n in by_name if n not in owner]
    extra = [n for n in owner if n not in by_name]
    assert not missing, f"这些导出没分到模块：{missing}"
    assert not extra, f"登记了但文件里没有这些导出：{extra}"

    bridge = bridge_names(text, masked)
    assert bridge, "没找到 window 桥块"
    for name in bridge:
        assert name in by_name or name == "HWCHECK_VERDICT_FALLBACK", f"桥上的 {name} 在文件里找不到声明"

    # 声明单元（含紧邻上方的注释块）→ 每件按原顺序取自己的
    units = []
    for d in decls:
        start = unit_start(text, d["start"])
        units.append({"name": d["name"], "start": start, "end": d["end"], "owner": owner[d["name"]]})
    for a, b in zip(units, units[1:]):
        assert a["end"] <= b["start"], f"声明区间重叠：{a['name']} / {b['name']}"

    bridge_match = BRIDGE_RE.search(masked)
    bridge_at = masked.rindex("if (typeof window", 0, bridge_match.start())
    assert masked.rfind("\n", 0, bridge_at) == bridge_at - 1, "桥块的 if 不在行首"
    # 桥块之前那一行若是空行，桥块不算进任何单元
    trailing = text[units[-1]["end"]:bridge_at]
    assert trailing.strip() == "", f"最后一个声明与桥块之间有非空内容：{trailing!r}"
    head = text[: units[0]["start"]]
    assert "export function" not in mask(head) and "export const" not in mask(head), "文件头里有导出"
    assert "function " not in mask(head).replace("//", ""), "文件头里有函数定义"

    chunks = {}
    for mod in MODULES:
        chunks[mod["file"]] = []
    flat = []                                  # 按**原文件顺序**的 (owner, 文本) —— 分区检查用它
    prev_end = units[0]["start"]
    for u in units:
        piece = text[prev_end:u["start"]] + text[u["start"]:u["end"]]
        chunks[u["owner"]].append(piece)
        flat.append(piece)
        prev_end = u["end"]
    tail = text[units[-1]["end"]:bridge_at]     # 最后一个声明之后到桥块之前（只有换行）

    # —— 分区完备：文件头 ＋ 按原顺序的全部单元 ＋ 尾 ＋ 桥块，必须逐字节等于原文件 ——
    rebuilt = head + "".join(flat) + tail + text[bridge_at:]
    assert rebuilt == text, "分区不完备：拼回来与原文件不是同一份"

    files = {}
    claimed = []                               # [(件名, 它认领的桥条目)] —— 落盘前逐名对账
    for mod in MODULES:
        header = [
            f"// fx/{mod['file']} — 硬件检测栏目的纯函数：**{mod['title']}**。",
            "//",
        ]
        if mod["file"] == "hwcheck-state.js":
            header += SHARED_HEAD.rstrip("\n").split("\n")   # 约定块的单源
        else:
            header += [
                "// 由 `fx/hwcheck.js` 按职责整段搬来（工单 hwcheck-hygiene/09），**只搬不改**。",
                "// 模块约定与六件的依赖方向见 `fx/hwcheck-state.js` 头部——那份是**单源**，",
                "// 别在这里再抄一遍（抄六遍就是六份会各自漂移的散文）。",
            ]
        header.append("")
        body = "".join(chunks[mod["file"]]).strip("\n")
        # 桥条目按**声明的归属**认领：导出名只是"声明名"的一个子集，还有私有件
        # （`HWCHECK_VERDICT_FALLBACK` 就没导出、但挂在桥上）——第一版只按导出名认领，
        # 于是它掉出了桥，被 `tests/js/hwcheck-split-integrity.test.mjs` 的 ③ 当场抓住。
        declared = set(re.findall(
            r"(?m)^[ \t]*(?:export\s+)?(?:async\s+)?(?:function|const|let|var|class)\s+"
            r"([A-Za-z_$][\w$]*)", mask(body)))
        mine = [n for n in bridge if n in declared]
        claimed.append((mod["file"], mine))
        lines = ['if (typeof window !== "undefined") {', "  Object.assign(window, {"]
        row = []
        for name in mine:
            row.append(name + ",")
            if len(row) == 3:
                lines.append("    " + " ".join(row))
                row = []
        if row:
            lines.append("    " + " ".join(row))
        lines += ["  });", "}"]
        blocks = [*header, *mod["imports"], "", body, ""]
        if mine:
            blocks += ["// —— 探针桥（CDP / devtools 与页面内联脚本的既有出口）——", *lines, ""]
        files[mod["file"]] = "\n".join(blocks)

    # 桥的并集必须逐名等于搬前：每一条都要有且只有一个家（漏一条 = 页面内联脚本/探针
    # 取不到那个全局名；重复认领 = 同一名字发两遍）
    seen_claim = {}
    for filename, names in claimed:
        for name in names:
            assert name not in seen_claim, f"桥条目 {name} 被 {seen_claim[name]} 与 {filename} 同时认领"
            seen_claim[name] = filename
    homeless = [n for n in bridge if n not in seen_claim]
    assert not homeless, f"这些桥条目没分到任何一件：{homeless}"

    barrel_lines = []
    for mod in MODULES:
        rows = [mod["names"][i:i + 3] for i in range(0, len(mod["names"]), 3)]
        barrel_lines.append("export {")
        for r in rows:
            barrel_lines.append("  " + ", ".join(r) + ",")
        barrel_lines.append(f'}} from "./{mod["file"]}";')
        barrel_lines.append("")
    files["hwcheck.js"] = BARREL_HEAD + "\n" + "\n".join(barrel_lines).rstrip("\n") + "\n"

    return {
        "text": text, "masked": masked, "units": units, "bridge": bridge,
        "files": files, "chunks": chunks, "head": head, "bridge_at": bridge_at,
    }


def write(built) -> None:
    """先落搬前快照（只在它不存在时），再落六个模块与 barrel。"""
    if not SNAP.exists():
        snapshot = SRC.read_bytes()
        assert snapshot.decode("utf-8") == built["text"], "源文件在本次运行里被改过？"
        SNAP.write_bytes(snapshot)
        print(f"[快照] {SNAP.relative_to(REPO)}  {len(snapshot)} B  "
              f"sha256={sha(snapshot.decode('utf-8'))[:16]}")
    else:
        print(f"[快照] 已在（不覆盖）：{SNAP.relative_to(REPO)}")
    for name, content in built["files"].items():
        (FX_DIR / name).write_bytes(content.encode("utf-8"))
        print(f"[落盘] fx/{name}  {len(content.encode('utf-8'))} B  sha256={sha(content)[:16]}")


def main() -> int:
    # 输出一律 UTF-8：本机控制台是 GBK，中文/符号混排会撞 UnicodeEncodeError
    #（读数经 .scratch/hwcheck-hygiene/readings.py 落盘，它按 UTF-8 解码）。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="hwcheck-hygiene/09：拆 fx/hwcheck.js")
    ap.add_argument("--write", action="store_true", help="落盘（默认只干跑核对）")
    args = ap.parse_args()

    built = build()
    print(f"源文件 {'（快照）' if SNAP.exists() else ''}{SRC.relative_to(REPO)}："
          f"{len(built['text'].encode('utf-8'))} B / "
          f"{len(built['units'])} 个导出声明 / 桥 {len(built['bridge'])} 个名字")
    print(f"分区完备：文件头 {len(built['head'])} B ＋ {len(built['units'])} 个声明单元 "
          f"＋ 桥块 {len(built['text']) - built['bridge_at']} B = 原文（逐字节相等 OK）")
    print("\n间隙表（非导出私有件住在这里，跟着**下一个**声明单元走）：")
    prev = built["units"][0]["start"]
    for u in built["units"]:
        gap = built["text"][prev:u["start"]]
        code = [ln.strip() for ln in gap.split("\n")
                if ln.strip() and not ln.lstrip().startswith("//")]
        if code:
            print(f"  {u['owner']:22s} ← {u['name']:34s} 间隙里的代码：{code}")
        prev = u["end"]
    print("\n各件：")
    for mod in MODULES:
        print(f"  fx/{mod['file']:22s} {len(mod['names']):2d} 个导出  "
              f"{len(built['files'][mod['file']].encode('utf-8')):6d} B  —— {mod['title']}")
    print(f"  fx/hwcheck.js（barrel）    {sum(len(m['names']) for m in MODULES):2d} 条再导出  "
          f"{len(built['files']['hwcheck.js'].encode('utf-8'))} B")

    if args.write:
        write(built)
    else:
        print("\n（干跑：没写盘。加 --write 落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
