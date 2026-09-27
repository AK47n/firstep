#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/11 的读路径迁移：`tests/js/hwcheck.test.mjs` 里那 34 条读
`ui/hwcheck.js` 的源码串断言，改指**搬迁后的真实落点**（逐条按"断言的对象在哪一件"定）。

用法：

    python .scratch/hwcheck-hygiene/apply-11-tests.py            # 干跑
    python .scratch/hwcheck-hygiene/apply-11-tests.py --write    # 落盘

## 两种落点（都写进用例里的注释，供 12 号单逐条判定）

  · `layer`   —— 判"这一层有没有做某件事"（ui 走 fx 单源 / 不得手拼）：读**四件并集**。
                 钉在某一件上会变成"守卫闭眼"（读不到 → 恒假；读到空壳 → 恒真）。
  · `module`  —— 判"某个具体函数的身体"（视图刷新的并发纪律 / 删除后对齐选择集…）：
                 读它所在的那一件。

本单**只改读路径与随之失真的措辞**，断言一条不动、一条不删；"能改成行为断言的改行为"
与逐条判定、条数对账归 12 号单（票面写着）。
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEST = REPO / "tests" / "js" / "hwcheck.test.mjs"


def _split_module():
    """借 11 号单搬迁脚本里的掩码器与括号配对（**单源**：别在第二个脚本里再写一遍）。"""
    spec = importlib.util.spec_from_file_location(
        "apply_11_split", Path(__file__).resolve().parent / "apply-11-split.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SPLIT = _split_module()
MASK = _SPLIT.mask
MATCH_BRACE = _SPLIT.match_brace

# 用例标题（取唯一前缀）→ 落点。`layer` = 四件并集；其余 = 那一件的文件名。
TARGETS = {
    "产物区壳在 fx 单源": "layer",
    "纯件留在 fx": "layer",
    "ui 复用既有编译与烧录执行体": "layer",
    "ui 的清单勾选态走 fx 的键与编解码单源": "layer",
    "ui 不手拼工程面板 / 清单 / 最近的壳": "layer",
    "ui 的接线表 / 冲突 / 顺序 / chips 都走 fx 单源": "layer",
    "ui 的说明弹窗走既有委托": "layer",
    "ui 的视图刷新守并发纪律": "hwcheck-actions.js",
    "ui 的自动回读不抹掉用户刚动的选择": "hwcheck-actions.js",
    "ui 的三处清预览": "layer",
    "ui 的小节渲染走 fx 单源": "layer",
    "ui 换平台 / 换通道时清掉旧检测计划": "hwcheck-actions.js",
    "ui：器件挑选把组清单喂给单选交换": "layer",
    "结构钉：余量提示有渲染落点": "hwcheck-core.js",
    "ui 的命令台渲染走 fx 单源": "layer",
    "ui 换平台 / 换通道时清掉旧命令表": "hwcheck-actions.js",
    "ui 的建议渲染走 fx 单源": "layer",
    "ui 提交现象前先读输入框": "hwcheck-actions.js",
    "ui 生成新工程时清掉上一次的现象与建议": "hwcheck-actions.js",
    "ui 回读勾选的判据": "hwcheck-actions.js",
    "单平台件不误导：器件挑选面按": "hwcheck-core.js",
    "单平台件不误导：已选中的单平台件由服务端载荷点名": "hwcheck-core.js",
    "ui 静态 import fx/my-devices.js": "layer",
    "ui 读写端点走既有 apiGet / apiPost / apiDelete": "hwcheck-devices.js",
    "ui 删掉一件时把它从": "hwcheck-devices.js",
    "ui 的 id 建议不覆盖用户手填的 id": "hwcheck-devices.js",
    "ui 的 id 建议也只改那一个输入框": "hwcheck-devices.js",
    "「我的器件」的行随选择集重绘": "hwcheck-core.js",
    "ui 打字期间**不整块重绘表单**": "hwcheck-devices.js",
    "「我的器件」不随平台清空": "hwcheck-actions.js",
    "ui 接线：载荷 → 计划容器 + 接线区": "layer",
    "ui 的空态文案把自建件也算进": "hwcheck-core.js",
    "结构钉：表单收起 / 切换必须清掉资料与草稿": "hwcheck-devices.js",
    "结构钉：总口径那句真的被渲染出来": "layer",
    "结构钉：ui 侧走 fx": "layer",
}

README = """// 工单 hwcheck-hygiene/11：DOM 层那一个 1401 行的文件按职责拆成四件——入口
// `ui/hwcheck.js`（只剩接线 + 两个导出）／核心渲染 `ui/hwcheck-core.js`／「我的器件」
// `ui/hwcheck-devices.js`／动作与请求 `ui/hwcheck-actions.js`。
//
// 下面这些"ui 走 fx 单源 / ui 不得手拼 XX"的判据原本读那一个大文件。搬迁之后**钉死某一个
// 路径**必然变成两种"守卫闭眼"：读不到那段代码（断言恒假或直接报错），或读到空壳（恒真）。
// 所以按断言的对象分两种落点：
//   · `hwcheckUiText()`  —— 判"这一层有没有做某件事"（四件并集）；
//   · `uiModuleText(名)` —— 判"某个具体函数的身体"（读它所在的那一件）。
// 逐条判定与"能改成行为断言的改行为"归 12 号单；本单只保证断言的对象跟着代码走。
const HWCHECK_UI_DIR = new URL("../../src/contest_generator/static/js/ui/", import.meta.url);
const HWCHECK_UI_FILES = [
  "hwcheck.js", "hwcheck-core.js", "hwcheck-devices.js", "hwcheck-actions.js",
];
const hwcheckUiText = () => HWCHECK_UI_FILES
  .map((name) => readFileSync(new URL(name, HWCHECK_UI_DIR), "utf8")).join("\\n");
const uiModuleText = (name) => readFileSync(new URL(name, HWCHECK_UI_DIR), "utf8");

"""

# 用例里那一句读文件（三种换行写法都收）：
READ_RE = re.compile(
    r"const (\w+) = readFileSync\(\s*"
    r'new URL\("\.\./\.\./src/contest_generator/static/js/ui/hwcheck\.js", import\.meta\.url\),?\s*'
    r'"utf8"\);')

# 跟着落点一起失真的**锚点**（用例在源码里按某一行切片/定位；那一行也搬走了）。
# 每条 = (用例标题前缀, 旧锚点原文, 新锚点原文)：`myBox.addEventListener("blur"…)` 那条接线
# 留在入口，而它的处理分支（要切的正文）现在住器件件的 `suggestMyDeviceId` 里。
ANCHORS = [
    ("ui 的 id 建议也只改那一个输入框",
     """ui.indexOf('myBox.addEventListener("blur"')""",
     """ui.indexOf("function suggestMyDeviceId(")"""),
    ("ui 的 id 建议也只改那一个输入框",
     '"应有按名称补 id 建议的 blur 委托"',
     '"应有按名称补 id 建议的 suggestMyDeviceId"'),
]

# 落点变了会跟着失真的措辞（标题 / 断言消息里点名了某一个文件）。
MESSAGES = [
    ("纯件留在 fx：ui/hwcheck.js 不得重复定义", "纯件留在 fx：ui 这几件都不得重复定义"),
    ('"ui/hwcheck.js 不应重新定义 "', '"ui 不应重新定义 "'),
    ('`ui/hwcheck.js 应从 fx/hwcheck-${key}.js 导入纯件`', '`ui 这一层应从 fx/hwcheck-${key}.js 导入纯件`'),
    ('"ui/hwcheck.js 应静态 import fx/my-devices.js"', '"ui 应静态 import fx/my-devices.js"'),
    ('"ui/hwcheck.js 里应有 closeMyDeviceForm"', '"器件件里应有 closeMyDeviceForm"'),
    ('"ui/hwcheck.js 里应有 openMyDeviceForm"', '"器件件里应有 openMyDeviceForm"'),
]


def blocks(text: str) -> list[tuple[str, int, int]]:
    """→ [(标题, 起, 止)]，按 `test("…", …)` 的配对括号切。

    ⚠ 括号配对必须走**掩码文本**：判据的正文里满是正则字面量（`/if \\(device\\) \\{…/`），
    裸数括号会把 `\\{` 当开括号——那个用例的块尾就永远找不到，于是它**静默不进表**
    （本单第一版实测：35 条登记只迁了 34 条，漏的正是「表单收起 / 切换」那一条）。
    """
    masked = MASK(text)
    out = []
    for m in re.finditer(r'(?m)^test\("((?:[^"\\]|\\.)*)"', text):
        open_idx = masked.index("{", m.end())
        out.append((m.group(1), m.start(), MATCH_BRACE(masked, open_idx) + 1))
    return out


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    raw = TEST.read_bytes().decode("utf-8")
    assert "hwcheckUiText" not in raw, "已经迁过了（幂等：不重复落盘）"
    text = raw
    # 体检：每个 `test("` 都必须切出块来（切不出来 = 括号配对失效 → 会静默漏迁）
    titles = [m.group(1) for m in re.finditer(r'(?m)^test\("((?:[^"\\]|\\.)*)"', text)]
    assert len(blocks(text)) == len(titles), \
        f"只有 {len(blocks(text))} 个块切出来了（用例 {len(titles)} 条）——括号配对失效"
    # 从后往前替换，保持前面的下标有效
    hits = []
    for title, start, end in reversed(blocks(text)):
        chunk = text[start:end]
        m = READ_RE.search(chunk)
        if not m:
            continue
        key = next((k for k in TARGETS if title.startswith(k)), None)
        assert key, f"用例没登记落点：{title}"
        target = TARGETS[key]
        expr = "hwcheckUiText()" if target == "layer" else f'uiModuleText("{target}")'
        new = chunk[:m.start()] + f"const {m.group(1)} = {expr};" + chunk[m.end():]
        for key2, old, repl in ANCHORS:
            if key2 != key:
                continue
            assert old in new, f"{key2}：锚点不在了：{old}"
            new = new.replace(old, repl)
        text = text[:start] + new + text[end:]
        hits.append((key, target))

    missing = sorted(set(TARGETS) - {k for k, _ in hits})
    assert not missing, f"登记了却没迁的用例落点：{missing}"
    assert "static/js/ui/hwcheck.js\"" not in text.replace(
        'new URL(name, HWCHECK_UI_DIR)', ""), "还有读旧路径的写法没迁"
    for old, new in MESSAGES:
        assert old in text, f"措辞锚点不在了：{old}"
        text = text.replace(old, new)

    # 说明块插在**全部 import 之后**（第一版锚在最后一个 import 之前，等于把代码插进 import 段中间）
    anchor = ("import { moduleGridHTML } "
              "from \"../../src/contest_generator/static/js/fx/module.js\";\n")
    assert anchor in text, "找不到最后一个 import（锚点变了？）"
    text = text.replace(anchor, anchor + "\n" + README, 1)

    for title, target in sorted(hits):
        print(f"  {target:20s} ← {title}")
    print(f"共迁 {len(hits)} 条；措辞订正 {len(MESSAGES)} 处")
    if not args.write:
        print("（干跑，未落盘）")
        return 0
    TEST.write_bytes(text.encode("utf-8"))
    print(f"已写：{TEST.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
