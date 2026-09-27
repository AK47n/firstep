#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/11：把 `ui/hwcheck.js`（1401 行）按职责拆成四件。

用法：

    python .scratch/hwcheck-hygiene/apply-11-split.py            # 干跑：核对 + 打印，不落盘
    python .scratch/hwcheck-hygiene/apply-11-split.py --write    # 落盘（含搬前快照）

## 四件与归属（按职责，票面「现状」表 + 一条实测调整）

| 文件 | 职责 | 内容 |
|---|---|---|
| `ui/hwcheck-core.js` | 状态 + 各区块渲染（含面板编排） | `hwcheckUI` / 小工具 / 全部 `render*` / `renderHwcheckPanel` / `renderMyDevices` |
| `ui/hwcheck-devices.js` | 「我的器件」增删改查与草稿 | `openMyDeviceForm` … `deleteMyDevice` + 它的四个委托处理分支 |
| `ui/hwcheck-actions.js` | 动作与请求 | 预览 / 生成 / 采纳 / 恢复 / 编译 / 烧录 / 清单同步 / 排障提交 / 带入生成页 + 十个委托处理分支 |
| `ui/hwcheck.js` | 入口 | `export { renderHwcheckPanel }`（转出）＋ `initHwcheck` ＋ 9 处委托接线 |

**实测调整一条（票面「现状」表说 333–585 整段归器件件）**：`renderMyDevices`（列表 + 表单 +
资料 + 草稿四块的渲染）归**核心件**——面板编排 `renderHwcheckPanel` 要调它，而核心件不许反向
import 器件件。这样换来的是一条**零回调、零反向边**的依赖链：入口 → 器件 → 动作 → 核心。

## 这支脚本把哪几件事变成可复算的断言

1. **分区完备**：原文件每一个字节都落进「原文件头 + 59 个声明单元（含紧邻上方的注释块与
   它前面的间隙）」之一，拼回来逐字节等于原文件（`assert_partition`）。
2. **函数体逐字**：每个声明单元整段搬走，函数体与其注释一个字不改；**唯一的例外**是下面
   两张表（`EXTRACTS` 委托分支下沉、`REWRITES` 跨件写入口），每条都要求命中指定次数。
3. **名字面**：59 个声明名一个不少、不多；导出面 = "被别的件用到的那些"（判据 D 零消费者
   导出由 `tests/js/export-surface-guard.test.mjs` 守）；import 面**现算**（扫掩码正文里的
   自由标识符），不手抄——手抄的 import 表正是下一处分叉的来源。

搬前快照 `ui-hwcheck-before-split.js` 与源文件逐字节相同，**只在第一次 `--write` 时落盘**，
之后不再覆盖；`tests/js/hwcheck-split-integrity.test.mjs` 与反证探针都读它。
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UI_DIR = REPO / "src" / "contest_generator" / "static" / "js" / "ui"
SRC = UI_DIR / "hwcheck.js"
SNAP = REPO / ".scratch" / "hwcheck-hygiene" / "ui-hwcheck-before-split.js"

# 搬前快照的 sha256（落盘那一刻实测；与 `git show HEAD:…ui/hwcheck.js` 逐字节相同）。
# **刻意写死**：快照被静默替换（或误当工作副本改过）时这支脚本要当场拒绝——
# 否则它会照着错的基线重切一遍，产物还照样自洽。
SNAPSHOT_SHA256 = "65ae5e85e79ab392c2b9adc08e8262bf53963ee2162818082b22ef95fcfebb9b"

# ---------------------------------------------------------------------------
# 名字 → 模块（顺序 = 原文件里的声明顺序）
# ---------------------------------------------------------------------------

CORE = [
    "hwcheckUI",
    "hwcheckPlatforms", "hwcheckModules", "platformLabel", "readStored", "writeStored",
    "compileReady",
    "renderHwcheckPlatforms", "renderHwcheckChannelNote", "renderHwcheckUnverifiedNote",
    "renderHwcheckOutput", "renderHwcheckProject",
    "pendingFocusSelector", "selectorValue", "applyPendingFocus",
    "renderHwcheckChecklist", "renderHwcheckRecent", "renderHwcheckDevices",
    "hwcheckHandoff", "renderHwcheckHandoff", "renderMyDevices",
    "renderHwcheckWiring", "renderHwcheckSections", "renderHwcheckCustom",
    "applyDroppedDevices", "renderHwcheckDropped", "renderHwcheckConsole",
    "renderHwcheckAdvice", "renderHwcheckPanel",
]
DEVICES = [
    "myDeviceFormError", "syncMyDeviceForm", "closeMyDeviceForm", "openMyDeviceForm",
    "applyDraftResponse", "applyMyDraft", "draftMyDevice", "draftFromMyDeviceFile",
    "loadMyDevices", "saveMyDevice", "deleteMyDevice",
]
ACTIONS = [
    "handoffToGenerate",
    "adoptProject", "hwcheckViewBusy", "hwcheckViewPending", "hwcheckSelectionKey",
    "refreshHwcheckView", "previewHwcheck", "addHwcheckDevice", "generateHwcheck",
    "restoreHwcheckProject", "loadHwcheckRecent",
    "submitHwcheckTriage", "syncHwcheckChecklist",
    "setCompileStatus", "setCompileErrors", "runHwcheckCompile", "runHwcheckFlash",
    "openHwcheckFolder",
]
ENTRY = ["initHwcheck"]

# ---------------------------------------------------------------------------
# 新增：核心件的焦点写入口（跨件写不了 `let`——ESM 的导入绑定只读）
# ---------------------------------------------------------------------------

SET_PENDING_FOCUS = """\
// setPendingFocus(selector)：整块重绘前**登记**焦点落点（工单 hwcheck-hygiene/11）。
// 为什么是一个函数而不是导出那个 `let`：ESM 的导入绑定只读，跨件赋值写不了；状态留在
// 本件，重绘收尾由 applyPendingFocus() 统一消费（口径见上面那段）。
// 消费方 = 入口 / 器件 / 动作三件（谁触发重绘谁登记）。
export function setPendingFocus(selector) {
  pendingFocusSelector = String(selector || "");
}
"""

# ---------------------------------------------------------------------------
# 委托处理分支下沉（票面：入口只留"接线 + 两个导出"）
#
# 每条 = 从 initHwcheck 里**整段**搬走一个回调体（或那个 `const activate` 箭头），
# 在入口留下一条接线；处理分支成为目标件里的具名函数：
#   · 参数名与被搬走的正文里用到的闭包变量**同名**（`myBox` / `parentInput`），
#     于是正文一个标识符都不用改；
#   · 缩进整体左移 4 格（原来嵌在 `if (x) { … }` 里），这是唯一允许的形变。
# ---------------------------------------------------------------------------

EXTRACTS = [
    dict(
        needle='platforms.addEventListener("click", (e) => {',
        name="handlePlatformClick", params="e", home="actions",
        wiring='platforms.addEventListener("click", handlePlatformClick);',
        doc="handlePlatformClick(e)：点平台卡 → 换平台并清掉旧产物（旧产物是另一块板子的 main.c，"
            "留着会误导）；换成功再重取一次板侧视图。",
    ),
    dict(
        needle='channels.addEventListener("change", (e) => {',
        name="handleChannelChange", params="e", home="actions",
        wiring='channels.addEventListener("change", handleChannelChange);',
        doc="handleChannelChange(e)：勾 / 取消一个输出通道——通道是渲染输入，改了就把旧预览清掉，"
            "并重取板侧视图（通道模块自己也会占脚、也会撞脚）。",
    ),
    dict(
        needle="const activate = (target) => {",
        name="activateHwcheckDeviceCard", params="target", home="actions",
        wiring="",
        doc="activateHwcheckDeviceCard(target)：器件网格里「点一张卡 = 加一件」（卡片本体；"
            "详情按钮优先，见 handleDeviceGridClick）。重绘后把焦点送到**这一件的结果**上"
            "（加进之后它在 chips 里，卡片本身会从「还没选」的池子里消失）。",
    ),
    dict(
        needle='deviceGrid.addEventListener("click", (e) => {',
        name="handleDeviceGridClick", params="e", home="actions",
        wiring='deviceGrid.addEventListener("click", handleDeviceGridClick);',
        doc="handleDeviceGridClick(e)：与生成页模块网格同一套委托语义——详情按钮优先"
            "（开说明弹窗），卡片本体 = 加一件器件。平台用**本栏目自己的**"
            "（生成页的平台可能不同）。",
    ),
    dict(
        needle='deviceGrid.addEventListener("keydown", (e) => {',
        name="handleDeviceGridKeydown", params="e", home="actions",
        wiring='deviceGrid.addEventListener("keydown", handleDeviceGridKeydown);',
        doc="handleDeviceGridKeydown(e)：键盘同等可达（工单 hwcheck-hygiene/06）——卡片是"
            "role=button tabindex=0；详情按钮是真 <button>（浏览器自己把 Enter/Space"
            "变成 click），排掉免得开两次。",
    ),
    dict(
        needle='deviceChips.addEventListener("click", (e) => {',
        name="handleDeviceChipsClick", params="e", home="actions",
        wiring='deviceChips.addEventListener("click", handleDeviceChipsClick);',
        doc="handleDeviceChipsClick(e)：点 chip 上的 ✕ = 从这次检测里去掉这一件；"
            "移除之后 chip 就不在了，焦点落到网格里那张卡上。",
    ),
    dict(
        needle='deviceChips.addEventListener("keydown", (e) => {',
        name="handleDeviceChipsKeydown", params="e", home="actions",
        wiring='deviceChips.addEventListener("keydown", handleDeviceChipsKeydown);',
        doc='handleDeviceChipsKeydown(e)：chip 是 role=button tabindex=0（工单 06），'
            "Enter / Space 与点它同义（说明按钮自己会响应，排掉）。",
    ),
    dict(
        needle='parentInput.addEventListener("change", () => {',
        name="handleParentChange", params="parentInput", home="actions",
        wiring='parentInput.addEventListener("change", () => handleParentChange(parentInput));',
        doc="handleParentChange(parentInput)：输出父目录改了——记住它（本地备忘）并重载最近列表。",
    ),
    dict(
        needle='pick.addEventListener("click", async () => {',
        name="pickHwcheckParent", params="parentInput", home="actions", async_=True,
        wiring='pick.addEventListener("click", () => pickHwcheckParent(parentInput));',
        doc='pickHwcheckParent(parentInput)：「选择文件夹」（服务端原生对话框）——用户取消'
            "（没有 path）不覆盖输入框。",
    ),
    dict(
        needle='myBox.addEventListener("click", (e) => {',
        name="handleMyDeviceClick", params="e", home="devices",
        wiring='myBox.addEventListener("click", handleMyDeviceClick);',
        doc="handleMyDeviceClick(e)：「我的器件」那一块的全部点击分支（加选 / 改 / 删 / 保存 /"
            "抽草稿 / 填草稿 / 弃草稿 / 取消），全部走容器级委托（innerHTML 全量重绘后仍有效）。",
    ),
    dict(
        needle='myBox.addEventListener("input", (e) => {',
        name="handleMyDeviceInput", params="e", home="devices",
        wiring='myBox.addEventListener("input", handleMyDeviceInput);',
        doc="handleMyDeviceInput(e)：表单输入——`input` 覆盖打字（地址预览与校验理由实时跟上）；"
            "资料文本框只同步 state，**不许重绘**（正在打字，同表单纪律）。",
    ),
    dict(
        needle='myBox.addEventListener("change", (e) => {',
        name="handleMyDeviceChange", params="e", home="devices",
        wiring='myBox.addEventListener("change", handleMyDeviceChange);',
        doc="handleMyDeviceChange(e)：`change` 单独接一次是为了 `<select>`（总线下拉在部分浏览器上"
            "不触发 input）；资料文件选择走既有抽取通道。",
    ),
    dict(
        needle='myBox.addEventListener("blur", (e) => {',
        name="suggestMyDeviceId", params="myBox, e", home="devices",
        wiring='myBox.addEventListener("blur", (e) => suggestMyDeviceId(myBox, e), true);',
        doc="suggestMyDeviceId(myBox, e)：名称 → id 建议（**捕获阶段**，照原样）。只在 id 还是空 /"
            "还是上一次自动填的那值时补一下，用户手填过 id 就不动它。",
    ),
    dict(
        needle='project.addEventListener("click", (e) => {',
        name="handleProjectClick", params="e", home="actions",
        wiring='project.addEventListener("click", handleProjectClick);',
        doc="handleProjectClick(e)：工程面板上的三个动作——编译 / 烧录 / 打开工程目录"
            "（按钮由调用方传进来，不用选择器反查：Windows 路径里的 `\\U` 在 JS 字符串里是"
            "转义序列）。",
    ),
    dict(
        needle='checklist.addEventListener("change", (e) => {',
        name="handleChecklistChange", params="e", home="actions",
        wiring='checklist.addEventListener("change", handleChecklistChange);',
        doc="handleChecklistChange(e)：上板清单勾选——本地备忘写一份（离线兜底）、服务端也落一份"
            "（刷新 / 换机器回显的真源），并保持焦点在刚勾的那一项上。",
    ),
]

# 跨件写入口：`pendingFocusSelector = X` → `setPendingFocus(X)`（核心件之外的两件里各若干处）。
REWRITES = [
    ("actions", re.compile(r"pendingFocusSelector = (.+);\r\n"), "setPendingFocus(\\1);\r\n", 4),
    ("devices", re.compile(r"pendingFocusSelector = (.+);\r\n"), "setPendingFocus(\\1);\r\n", 2),
    # 那个网格助手本体下沉成具名函数（`activate` → `activateHwcheckDeviceCard`）之后，
    # **调用位**也得跟着改：两处（click / keydown 各一处）。
    # ⚠ 第一版漏了这条：`activate(e.target)` 留在两个处理分支里，而 `activate` 既不在本件声明、
    # 也不在任何 import 里、更不在 window 桥上——**门禁全绿**（前端门禁 + 除了"点卡片"那一类
    # 的真浏览器用例），因为它是运行期才炸的 `ReferenceError`。是浏览器门禁当场抓到的 9 条红。
    # 现在由搬迁完整性自检的判据 ⑥（每个调用位的自由标识符必须在场）守这一类。
    ("actions", re.compile(r"(?<![\w$.])activate\(e\.target\)"), "activateHwcheckDeviceCard(e.target)", 2),
]

# 入口**再导出**的对外契约名：它的消费边是入口那行 `export { … } from "…"`（判据 D 认），
# 入口正文里也调它（所以另有一条 import 边）。`export { x };` 那种形态不行——判据 T 不把
# 「无 from 的 export」当边（`parseModuleImports`：`export { a };` 不是边 → 解不开 → 违规）。
FORCE_EXPORTS = {"core": {"renderHwcheckPanel"}}

# ---------------------------------------------------------------------------
# 文件头（各件一份；模块约定与依赖方向的**单源**在核心件）
# ---------------------------------------------------------------------------

HEAD_CORE = """\
// ui/hwcheck-core.js — 硬件检测栏目的**核心渲染件**（工单 hwcheck-hygiene/11）：
// 栏目状态 + 各区块渲染 + 面板编排。正文由 `ui/hwcheck.js`（1401 行）整段搬来，
// **函数体与注释逐字保留**——唯一的增量是文件头、import 段与一个写入口
// `setPendingFocus`（跨件写不了 `let`，见它自己的注释）。
//
// ## 四件与单向依赖（**单源**；改这里就够，另三件只转引本段）
//
//   ui/hwcheck.js          入口：**对外**（`boot.js` 与用例）只有两个导出
//                          （renderHwcheckPanel / initHwcheck）＋ 全部事件委托接线
//                          （处理分支下沉到下面两件）。其余三件的导出是**件间**接口，
//                          不是对外契约。
//   ui/hwcheck-devices.js  「我的器件」（库外件）的增删改查与草稿
//   ui/hwcheck-actions.js  动作与请求（预览 / 生成 / 采纳 / 恢复 / 编译 / 烧录 /
//                          清单同步 / 排障提交 / 带入生成页）
//   ui/hwcheck-core.js     本件：状态 + 各区块渲染（含面板编排 renderHwcheckPanel）
//
// 依赖方向（**单向、无环**；由 tests/js/ui-cycle.test.mjs 与静态对账守卫守）。真实边是
// 四组并列，**不是**一条链——按本段读，别按"入口 → 器件 → 动作 → 核心"那样读成一条链：
//
//     入口 → 器件 / 动作 / 核心      三件并列，入口可以用其中任何一件
//     器件 → 动作 / 核心             删掉一件后要重取板侧视图，所以够得着动作
//     动作 → 核心
//     核心 → 谁都不 import           只 import fx / app
//
// 面板编排（renderHwcheckPanel）住在本件、它要调的那块「我的器件」列表渲染
// （renderMyDevices）也一并留在这里——否则就是"核心 → 器件"的反向边。反过来的
// 代价是「我的器件」那一块**渲染在核心件、增删改查在器件件**：分成两件的依据是
// "谁调得到谁"，不是"看上去像不像一类东西"。
//
// 为什么这条方向要写死：入口一度是 1401 行里八类职责混住，每次改动都要重新建立上下文。
// 反向边一旦出现，那个大文件会以另一种形状长回来，而 `ui-cycle` 只拦得住成环的那一种。
// **不许用 window 桥绕过**（工单 hwcheck-hygiene/01 已把"模块正文靠全局桥解析"判死）。
"""

HEAD_DEVICES = """\
// ui/hwcheck-devices.js — 「我的器件」（库外件）的增删改查与草稿（工单 hwcheck-hygiene/11）。
//
// 正文由 `ui/hwcheck.js` 整段搬来（函数体与注释逐字保留），另加四个委托处理分支
// （原 initHwcheck 里那几个匿名回调整段搬来，正文一个字没改）。
//
// 分工：**渲染在核心件**（renderMyDevices / renderHwcheckDevices），本件管"点了之后
// 做什么"——表单状态机、请求、校验理由。件与平台无关（切平台不清这些键）。
//
// 依赖方向（单源 = ui/hwcheck-core.js 头部）：本件 → 动作件（删一件后要重取板侧视图）、
// 核心件。**不 import 入口**——那会成环。
"""

HEAD_ACTIONS = """\
// ui/hwcheck-actions.js — 硬件检测栏目的**动作与请求**（工单 hwcheck-hygiene/11）：
// 预览 / 生成 / 采纳 / 恢复 / 最近 / 编译 / 烧录 / 打开目录 / 清单同步 / 排障提交 /
// 带入生成页，加上它们在入口里那十处委托的处理分支。
//
// 正文由 `ui/hwcheck.js` 整段搬来（函数体与注释逐字保留；下沉进来的处理分支只左移了缩进）。
// 判据全在服务端与 fx 纯件里，本件只做"读状态 / 发请求 / 调渲染"三件事。
//
// 依赖方向（单源 = ui/hwcheck-core.js 头部）：本件 → 核心件。**不 import 入口、也不
// import 器件件**。复用既有执行体的三条边（编译 / 烧录 / 切页签）照旧。
"""

HEAD_ENTRY = """\
// ui/hwcheck.js — 硬件检测栏目的**入口**（工单 module-hwcheck/01 + 02；
// 工单 hwcheck-hygiene/11 起只剩"接线 + 两个导出"）。
//
// 对外契约（`boot.js` 的装载清单与既有用例指着的是**这两个名字**，一个字不许改）：
//   renderHwcheckPanel()  面板整体重绘（本件只转出，定义在 ui/hwcheck-core.js）
//   initHwcheck()         接线 + 首次渲染
//
// 四件的**依赖方向**见 ui/hwcheck-core.js 头部（单源，改那里就够）：不是一条链，而是
// 「入口 → 器件 / 动作 / 核心（三件并列）＋ 器件 → 动作 / 核心 ＋ 动作 → 核心 ＋ 核心 →
// 谁都不 import」。本件只留**接线的形状**（谁在什么事件上挂哪个处理函数）；处理分支住在
// 它们操作的那一件里——这样"点了会怎样"的代码与它改的状态在同一屏，入口不必再读懂全部业务。
//
// ⚠ 这一栏的接线有三条老规矩（下面各自带注释）：一律**容器级委托**（`innerHTML` 全量重绘
// 后仍有效）；重绘前用 `setPendingFocus` 登记焦点落点（工单 hwcheck-hygiene/06）；
// 说明按钮走既有捕获阶段委托（冒泡阶段拦不住"点说明 = 把器件去掉"）。
"""

# ---------------------------------------------------------------------------
# 掩码 / 解析
# ---------------------------------------------------------------------------

# 正则字面量之前的词（`return /x/` 这类形态）——判 `/` 是正则还是除号要用上下文。
REGEX_KEYWORDS = {
    "return", "typeof", "case", "in", "of", "new", "delete", "void", "instanceof",
    "do", "else", "yield", "await",
}
# 正则可以开始的"上一个有意义字符"（除号前面只可能是值：标识符 / 数字 / `)` / `]` / 引号）。
REGEX_PREV = set("(,=:[!&|?{};+-*%~^<>")


def _scan(text: str, out: list[str], i: int, terminator: str | None) -> int:
    """从 i 扫到 terminator（`}` 或 None = 文件尾）；注释 / 字符串 / 正则的内容变空格。

    保留换行与长度（下标与原文一一对应）。**模板串 `${…}` 里的表达式段当代码扫**——
    里面出现的函数调用（如 `` `${selectorValue(x)}` ``）必须看得见，否则现算 import 会漏。
    """
    n = len(text)
    prev = ""
    word = ""
    while i < n:
        c = text[i]
        if terminator and c == terminator:
            return i
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            word = text[i:j]
            prev = text[j - 1]
            i = j
            continue
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            out[i] = out[i + 1] = " "
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            if i < n:
                out[i] = out[i + 1] = " "
                i += 2
            continue
        if c == "/" and (prev == "" or prev in REGEX_PREV or word in REGEX_KEYWORDS):
            out[i] = " "
            i += 1
            in_class = False
            while i < n:
                ch = text[i]
                if ch == "\\":
                    out[i] = " "
                    if i + 1 < n and text[i + 1] != "\n":
                        out[i + 1] = " "
                    i += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    out[i] = " "
                    i += 1
                    break
                if ch != "\n":
                    out[i] = " "
                i += 1
            while i < n and text[i].isalpha():      # 标志位 gimsuy
                out[i] = " "
                i += 1
            prev, word = "/", ""
            continue
        if c == '"' or c == "'":
            quote = c
            out[i] = " "
            i += 1
            while i < n:
                if text[i] == "\\":
                    out[i] = " "
                    if i + 1 < n and text[i + 1] != "\n":
                        out[i + 1] = " "
                    i += 2
                    continue
                if text[i] == quote:
                    out[i] = " "
                    i += 1
                    break
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            prev, word = quote, ""
            continue
        if c == "`":
            out[i] = " "
            i += 1
            while i < n:
                if text[i] == "\\":
                    out[i] = " "
                    if i + 1 < n and text[i + 1] != "\n":
                        out[i + 1] = " "
                    i += 2
                    continue
                if text[i] == "$" and i + 1 < n and text[i + 1] == "{":
                    i = _scan(text, out, i + 2, "}") + 1
                    continue
                if text[i] == "`":
                    out[i] = " "
                    i += 1
                    break
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            prev, word = "`", ""
            continue
        prev, word = c, ""
        i += 1
    return i


def mask(text: str) -> str:
    """注释 / 字符串 / 模板串 / 正则的内容变空格（保留换行与长度）——括号配对与"用了哪些
    自由标识符"都只在掩码文本上算。"""
    out = list(text)
    _scan(text, out, 0, None)
    return "".join(out)


DECL_RE = re.compile(r"^(?:export )?(?:async )?(function|const|let|var|class) ([A-Za-z_$][\w$]*)",
                     re.M)


def match_brace(masked: str, open_idx: int) -> int:
    """掩码文本上从 `{` 配对到它的 `}`，返回 `}` 的下标。"""
    depth = 0
    for i in range(open_idx, len(masked)):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise AssertionError("括号配不上")


def decl_end(masked: str, text: str, kind: str, start: int) -> int:
    """一个顶层声明的收尾下标（`}` 或 `;` 之后）。"""
    if kind == "function":
        depth = 0
        open_idx = -1
        for i in range(start, len(masked)):
            if masked[i] == "(":
                depth += 1
            elif masked[i] == ")":
                depth -= 1
            elif masked[i] == "{" and depth == 0:
                open_idx = i
                break
        assert open_idx > 0, "找不到函数体"
        return match_brace(masked, open_idx) + 1
    open_idx = masked.find("{", start)
    semi = masked.find(";", start)
    if open_idx != -1 and (semi == -1 or open_idx < semi):
        close = match_brace(masked, open_idx)
        semi = masked.find(";", close)
        assert semi > 0, "声明没有收尾分号"
        return semi + 1
    assert semi > 0, "声明没有收尾分号"
    return semi + 1


def comment_block_start(lines: list[str], decl_line: int) -> int:
    """紧邻上方的连续 `//` 注释块（中间隔空行的不算——那是段落表头）。返回 0 基行号。"""
    i = decl_line - 1
    while i >= 0 and lines[i].strip().startswith("//"):
        i -= 1
    return i + 1


def parse(text: str):
    """→ (header, [(name, unit_text)])；header + 各单元拼回来逐字节等于原文。"""
    masked = mask(text)
    lines = text.split("\n")
    line_of = [0]
    for line in lines[:-1]:
        line_of.append(line_of[-1] + len(line) + 1)

    decls = []
    for m in DECL_RE.finditer(masked):
        if m.start() != 0 and masked[m.start() - 1] != "\n":
            continue
        line = masked.count("\n", 0, m.start())
        start = decls[-1][2] if decls else 0
        cb = comment_block_start(lines, line)
        decls.append((m.group(2), line, start, decl_end(masked, text, m.group(1), m.end())))

    units = []
    prev = line_of[comment_block_start(lines, decls[0][1])]
    header = text[:prev]
    for i, (name, line, _start, end) in enumerate(decls):
        nxt = (line_of[comment_block_start(lines, decls[i + 1][1])]
               if i + 1 < len(decls) else len(text))
        units.append((name, text[prev:nxt]))
        prev = nxt
    return header, units


# ---------------------------------------------------------------------------
# 搬移
# ---------------------------------------------------------------------------

def deindent(body: str) -> str:
    """回调体缩进整体左移 4 格（原来嵌在 `if (x) { … }` 里）——唯一允许的形变。"""
    out = []
    for line in body.split("\r\n"):
        if line.startswith("    "):
            out.append(line[4:])
        else:
            out.append(line)
    return "\r\n".join(out)


def wrap_doc(doc: str, width: int = 76) -> str:
    """把一条处理分支的说明折成 `// ` 注释块（中文按两列宽算——本仓注释都折在 ~80 列内）。"""
    def cols(s: str) -> int:
        return sum(2 if ord(ch) > 0x2000 else 1 for ch in s)

    lines, cur = [], ""
    for ch in doc:
        cur += ch
        if cols(cur) >= width and ch in "、，。；：）」/ ":
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\r\n".join("// " + line for line in lines) + "\r\n"


def apply_extracts(entry_text: str) -> tuple[str, dict[str, str]]:
    """入口正文里把 15 个回调整段换成一条接线；→ (新正文, {件: 处理分支正文})。"""
    handlers: dict[str, list[str]] = {"actions": [], "devices": []}
    for spec in EXTRACTS:
        needle = spec["needle"]
        assert entry_text.count(needle) == 1, f"锚点不唯一：{needle}"
        idx = entry_text.index(needle)
        brace = idx + len(needle) - 1
        assert entry_text[brace] == "{", f"锚点结尾不是 {{：{needle}"
        close = match_brace(mask(entry_text), brace)
        semi = entry_text.index(";", close)
        start = entry_text.rindex("\n", 0, idx) + 1
        indent = entry_text[start:idx]
        assert indent == "    ", f"{spec['name']}：缩进不是 4 格（{indent!r}）"
        body = entry_text[brace + 1:close]
        assert body.split("\r\n")[1].startswith("      "), \
            f"{spec['name']}：正文首行缩进不是 6 格"
        # async 是回调形态的一部分：`await` 出现在正文里就必须带上 `async`（否则整份解析失败）
        assert ("await " in body) == bool(spec.get("async_")), \
            f"{spec['name']}：async 标记与正文里的 await 不符"
        prefix = "async " if spec.get("async_") else ""
        fn = (wrap_doc(spec["doc"])
              + f"{prefix}function {spec['name']}({spec['params']}) {{{deindent(body)}}}\r\n")
        handlers[spec["home"]].append(fn)
        if spec["wiring"]:
            entry_text = entry_text[:start] + indent + spec["wiring"] + entry_text[semi + 1:]
        else:
            end = semi + 1
            if entry_text[end:end + 2] == "\r\n":
                end += 2
            entry_text = entry_text[:start] + entry_text[end:]
    return entry_text, {k: "\r\n".join(v) for k, v in handlers.items()}


def build_imports(module_key: str, text: str, owner: dict[str, str], files: dict[str, str],
                  spec_of: dict[str, str]) -> list[str]:
    """现算 import 面：正文里用到的自由标识符 ∩（别的件声明的 ∪ 原 import 表的）。

    判据是**掩码正文**上的标识符（前面不许是 `.`/`$`/词字符）——手抄 import 表正是
    下一处分叉的来源，这里一个名字都不手抄。
    """
    masked = mask(text)
    groups: dict[str, list[str]] = {}
    for name in sorted({*owner, *spec_of}):
        if name == "default":
            continue
        if owner.get(name) == module_key:          # 本件自己的声明（含本件新加的）
            continue
        if not re.search(r"(?<![\w$.])" + re.escape(name) + r"(?![\w$])", masked):
            continue
        spec = (f"/js/ui/{files[owner[name]]}" if name in owner else spec_of.get(name))
        assert spec, f"{module_key}：{name} 没有出处（既不在四件里，也不在原 import 表里）"
        groups.setdefault(spec, []).append(name)
    out = []
    for spec in sorted(groups):
        names = groups[spec]
        if len(names) <= 3:
            out.append(f'import {{ {", ".join(names)} }} from "{spec}";')
        else:
            out.append("import {\r\n" + "".join(f"  {n},\r\n" for n in names) + f'}} from "{spec}";')
    return out


def export_names(names: list[str], module_key: str, texts: dict[str, str]) -> set[str]:
    """被**别的件**用到的名字才 export（判据 D：零消费者导出由守卫守）。

    例外只有一条：`renderHwcheckPanel` 由入口的**再导出边**消费（入口正文里也调它，
    所以它同时有一条 import 边）——两条边都算消费，见 tests/js/export-surface-guard。
    """
    out = set(FORCE_EXPORTS.get(module_key, ()))
    for name in names:
        for other, text in texts.items():
            if other == module_key:
                continue
            if re.search(r"(?<![\w$.])" + re.escape(name) + r"(?![\w$])", mask(text)):
                out.add(name)
                break
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

MODULES = [
    ("core", "hwcheck-core.js", HEAD_CORE, CORE),
    ("devices", "hwcheck-devices.js", HEAD_DEVICES, DEVICES),
    ("actions", "hwcheck-actions.js", HEAD_ACTIONS, ACTIONS),
    ("entry", "hwcheck.js", HEAD_ENTRY, ENTRY),
]


def crlf(text: str) -> str:
    """整份统一成 CRLF。

    为什么必须做：四件的**正文**来自快照（工作树上逐字节是 CRLF），而文件头是这支脚本里的
    三引号字符串（脚本文件自身是 LF）——不归一的话每个新文件都是"头 LF + 正文 CRLF"的混装
    （双轴评审实测：入口 14 行 / 器件 9 行 / 核心 36 行纯 LF）。工作树约定是
    `core.autocrlf=true`（blob 里 LF、盘上 CRLF），所以盘上这一份应当是纯 CRLF、与它替代的
    那个旧文件逐字节同规。
    """
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def build(text: str) -> tuple[dict[str, str], list[str]]:
    header, units = parse(text)
    # 分区完备：原文件头 + 全部声明单元拼回来逐字节等于原文件
    assert header + "".join(u for _n, u in units) == text, "分区不完备（拼不回原文）"
    by_name = dict(units)
    kinds = [n for n, _u in units]
    want = [n for _k, _f, _h, names in MODULES for n in names]
    assert sorted(kinds) == sorted(want), (
        "声明清单与归属表对不上：\n  只原文有 %s\n  只表里有 %s"
        % (sorted(set(kinds) - set(want)), sorted(set(want) - set(kinds))))
    assert len(kinds) == len(set(kinds)) == len(want), "声明名有重复"
    # 每件内部必须**按原文顺序**（搬迁不许重排）
    order = {n: i for i, n in enumerate(kinds)}
    for _k, fname, _h, names in MODULES:
        idx = [order[n] for n in names]
        assert idx == sorted(idx), f"{fname}：归属表里的名字不是原文顺序"

    # 入口：委托分支下沉 + 接线替换
    entry_text, handlers = apply_extracts(by_name["initHwcheck"])
    by_name["initHwcheck"] = entry_text

    body: dict[str, str] = {}
    for key, _f, _h, names in MODULES:
        body[key] = "".join(by_name[n] for n in names)

    # 核心件：补 setPendingFocus（放在 applyPendingFocus 之后）
    anchor = "export function applyPendingFocus() {"
    if anchor not in body["core"]:
        # 未导出形态（首轮：核心件的 export 还没加）
        anchor = "function applyPendingFocus() {"
    assert anchor in body["core"], "找不到 applyPendingFocus 的落脚点"
    insert_at = body["core"].index(anchor)
    body["core"] = body["core"][:insert_at] + SET_PENDING_FOCUS + "\r\n" + body["core"][insert_at:]

    # 器件 / 动作：下沉进来的处理分支接在末尾
    for key in ("devices", "actions"):
        if handlers[key]:
            banner = ("\r\n// —— 事件委托的处理分支（工单 hwcheck-hygiene/11）——\r\n"
                      "// 由入口 `ui/hwcheck.js` 的接线调用：这里只放「点了之后做什么」，"
                      "选择器的归属\r\n// 仍在入口的接线行上（一处只写一遍）。\r\n\r\n")
            body[key] = body[key].rstrip("\r\n") + "\r\n" + banner + handlers[key]

    # 跨件写入口（`pendingFocusSelector = …` → `setPendingFocus(…)`）
    for key, pattern, repl, count in REWRITES:
        body[key], n = pattern.subn(repl, body[key])
        assert n == count, f"{key}：pendingFocusSelector 改写命中 {n} 处（应 {count}）"

    owner = {n: key for key, _f, _h, names in MODULES for n in names}
    files = {key: fname for key, fname, _h, _n in MODULES}
    # 新加的名字（下沉进来的处理分支 + 核心件的焦点写入口）也在归属表里——
    # 漏掉它们 = 入口 import 不到处理分支（ReferenceError），而"整页还能起来"的验证照样绿。
    for spec in EXTRACTS:
        assert spec["name"] not in owner, f"{spec['name']} 与既有声明重名"
        owner[spec["name"]] = spec["home"]
    owner["setPendingFocus"] = "core"
    new_names = {key: [] for key, _f, _h, _n in MODULES}
    for spec in EXTRACTS:
        new_names[spec["home"]].append(spec["name"])
    new_names["core"].append("setPendingFocus")

    spec_of = {}
    for m in re.finditer(r'import\s*\{([^}]*)\}\s*from\s*"([^"]+)"', header):
        for part in m.group(1).split(","):
            clean = part.strip()
            if clean:
                spec_of[clean] = m.group(2)
    assert len(spec_of) >= 50, f"原 import 表只解出 {len(spec_of)} 个名字"

    # 先算"谁用到谁"（需要 body 的最终形态），再算 exports 与 imports 段
    texts = {key: body[key] for key, _f, _h, _n in MODULES}
    exports = {key: export_names(names + new_names[key], key, texts)
               for key, _f, _h, names in MODULES}

    out: dict[str, str] = {}
    for key, fname, head, names in MODULES:
        # 把 export 关键字加到声明本体上（幂等：本来没写）
        text = body[key]
        for name in names + new_names[key]:
            if name not in exports[key]:
                continue
            pattern = re.compile(
                r"(?m)^(?:export )?((?:async )?(?:function|const|let|var) "
                + re.escape(name) + r")(?![\w$])")
            text, n = pattern.subn(lambda m: "export " + m.group(1), text, count=1)
            assert n == 1, f"{fname}：{name} 没找到声明行"
            assert re.search(r"(?m)^export [^\n]*\b" + re.escape(name) + r"\b", text), \
                f"{fname}：{name} 的 export 没落上"
        imports = build_imports(key, text, owner, files, spec_of)
        head_text = head
        tail_text = ""
        if key == "entry":
            # 再导出**排在 import 段之后**（形态 A：`export { x } from "M"`）——判据 T 要
            # 沿这条边递归到核心件才算得出"函数形态"；`import` ＋ 裸 `export { x };` 那形态
            # 在 parseModuleImports 眼里不是边（`export { a };` → 解不开 → 违规）。
            tail_text = ('\r\n// 面板重绘的定义在核心件——这里**转出**：入口正文也要调它（下面那句\r\n'
                         '// `renderHwcheckPanel()`），所以同时有一条 import 边与这条再导出边。\r\n'
                         'export { renderHwcheckPanel } from "/js/ui/hwcheck-core.js";\r\n\r\n')
        out[fname] = crlf(head_text + "\r\n" + "\r\n".join(imports) + "\r\n" + tail_text + text)
    for fname, content in out.items():
        assert "\n" not in content.replace("\r\n", ""), f"{fname}：还有纯 LF 行（换行混装）"
    return out, [f"{key}: {len(exports[key])} 个导出" for key, _f, _h, _n in MODULES]


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--preview", metavar="DIR", help="干跑并把四件写到 DIR（不碰仓库）")
    args = ap.parse_args(argv)

    # 源 = **搬前快照**（第一次 --write 落盘之后，源文件就已经是新形态了：再按它重切一遍
    # 会切出垃圾。快照才是这次搬迁的真源，指纹写死在上面）。
    raw = SNAP.read_bytes() if SNAP.exists() else SRC.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    print(f"搬前快照/源文件：{len(raw)} B / sha256 {digest}")
    assert digest == SNAPSHOT_SHA256, (
        "读到的不是写死指纹那一份——先确认工作树干净（git status）、快照没被人动过")
    text = raw.decode("utf-8")

    out, notes = build(text)
    print("四件：")
    for fname, content in out.items():
        print(f"  {fname}: {len(content.encode('utf-8'))} B / "
              f"{content.count(chr(13) + chr(10))} 行")
    for note in notes:
        print("  " + note)

    header, units = parse(text)
    print(f"分区完备：原文件头 {len(header)} B + {len(units)} 个声明单元 = 原文逐字节相同 ✓")
    for spec in EXTRACTS:
        assert spec["needle"] not in out["hwcheck.js"], f"入口里还留着 {spec['needle']}"
    entry_wires = out["hwcheck.js"].count("addEventListener(")
    assert entry_wires == 23, f"入口的接线处数变了：{entry_wires}（搬前 23）"
    print(f"委托下沉：{len(EXTRACTS)} 段处理分支搬进两件；入口接线 {entry_wires} 处"
          f"（与搬前同数，其中 {len(EXTRACTS)} 处只留一行「挂哪个函数」）")

    if args.preview:
        out_dir = Path(args.preview)
        out_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in out.items():
            (out_dir / fname).write_bytes(content.encode("utf-8"))
        print(f"\n预览已写到 {out_dir}（仓库未动）")
        return 0
    if not args.write:
        print("\n（干跑，未落盘；加 --write 落盘）")
        return 0
    if not SNAP.exists():
        SNAP.write_bytes(raw)
        print(f"搬前快照已落盘：{SNAP.relative_to(REPO).as_posix()}")
    for fname, content in out.items():
        (UI_DIR / fname).write_bytes(content.encode("utf-8"))
        print(f"已写：{(UI_DIR / fname).relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
