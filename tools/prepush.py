#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""推之前跑什么：按本次要推的改动选测试子集（工单 commit-gate/01-02）。

**为什么存在**：2026-09-15 那次误删让母版同步守卫在 main 上**红了整整一天**
（`docs/agents/local-environment.md` 7.1，根因写着「因为没人跑全套」）。全套实测
58 秒（`-n auto`）——闸门成本早就够低了，缺的只是「推之前自动跑一次」。

**判据只按路径机械映射，不做任何聪明事**（宁可多跑）：

| 改动落在 | 跑什么 |
|---|---|
| `tests/test_X.py` | 该文件（改测试就是改它自己） |
| `src/contest_generator/X.py` | `tests/test_X.py`（**存在**才用）；**没有同名测试 → 全套** |
| 被 ≥ `WIDE_IMPORT_THRESHOLD` 个测试文件 import 的模块（实测推导，非手写名单） | 全套（改它等于动半仓测试的公共面） |
| **前端（`static/`，含 index.html / js/）+ `tests/js/`（工单 module-hwcheck/01）** | **前端门禁（`node --test "tests/js/*.test.mjs"`）+ 全套 pytest** |
| **浏览器门禁落点（`tests/browser/`、`static/js/ui/`、`static/index.html`、`static/js/app.js`，工单 ui-dom-contract-gate/03）** | **浏览器门禁（`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`，真浏览器 + 真后端）+ 上面那支前端门禁 + 全套 pytest** |
| `library/`（库内容） | 库与母版守卫族（见 `LIBRARY_FAMILY`） |
| 纯文档（README / VERSIONS / CHANGELOG / docs/ / .scratch/） | 文档守卫族（见 `DOCUMENT_FAMILY`） |
| **认不出来的任何路径** | 全套（倒向更严） |

**前端门禁为什么单列一支**（工单 module-hwcheck/01）：pytest 面**完全看不见**
`tests/js/`——那 1500 多条前端用例此前没有任何自动触发点，全靠人记得手敲。
于是"改了导航忘了同步守卫"这类错误只能等真机上发现（2026-09-12 那次
「一打开就卡死」就是同一个盲区）。现在改前端文件时**两边都跑**：pytest 认不出
前端落点（倒向更严，仍整套），前端门禁补上 `node --test`。node 不在 PATH 时
按「闸门自身故障」政策打印原因并跳过——**但 node 跑了且用例红了，必须拒推**。

**浏览器门禁为什么又是一支**（工单 ui-dom-contract-gate/03）：`tests/browser/*.spec.mjs`
是 21 条**真浏览器 + 真后端**的验收用例，它不满足前端门禁那支的前提（"只吃 `node:`
内置模块、零 npm 依赖、几秒跑完"）——它要 playwright 与它下载的 chromium，本机实测
三个 spec 串行约 35–45 秒。所以两支并列、各自独立开关：改动落在哪一支就付哪一支
的成本，**不把浏览器用例混进 `tests/js/` 的 glob**（那会让每次改前端都多一个浏览器前提）。
它的失败语义与前端门禁同在一条政策上（详见 `run_browser_tests` 的 docstring）：
node/用例清单/playwright 缺失 → 打印原因放行；用例真红 → 拒推。

**绝不卡人的边界**：闸门自身故障（python 没装 / git 读不到改动 / 选择器抛错 /
node 缺失）一律**打印原因并放行**（exit 0）——闸门坏了不该把维护者堵在门外；
但**测试真红了必须拒推**（pytest 或前端门禁任一红）。

用法：

    python tools/prepush.py                    # 从 git 读本次推送的改动（pre-push 钩子走这条）
    python tools/prepush.py --changed src/contest_generator/manifest.py
    python tools/prepush.py --full             # 强制全套（pytest + 前端门禁）
    python tools/prepush.py --dry-run          # 只说要跑什么，不执行
    python tools/prepush.py --explain          # 打印每条改动的命中理由
    python tools/prepush.py --no-js            # 已知不需要前端门禁时关掉这一支
    FIRSTEP_PREPUSH=full python tools/prepush.py    # 环境变量强制全套
    FIRSTEP_PREPUSH=select-only python tools/prepush.py   # 只选择、绝不执行（看会跑什么）
    FIRSTEP_PREPUSH=off  python tools/prepush.py    # 跳过（明写警告）

退出码：0 = 通过或按规则放行；1 = 测试红（应当拒推）；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"

# 前端守卫的落点与跑法（工单 module-hwcheck/01）：pytest 面看不见 tests/js/，
# 这条支线把"改了前端就必须跑前端用例"接进闸门。
#
# **为什么把文件清单在 Python 侧展开、而不是把 glob 交给 node**：`node --test`
# 的位置参数只有在 **Node ≥21** 才支持 glob（Node 20 会把 `tests/js/*.test.mjs`
# 当成一个字面文件名，报 MODULE_NOT_FOUND）；而 windows-latest 预装的 node 版本
# 会变。清单在 Python 侧展开后传给 node 的是一串**真实文件路径**，任何版本都认，
# 也不依赖 shell 展开（跨平台一致）。JS_TESTS_GLOB 仍是对外契约文本（CI / 文档 /
# 人工命令都用它，并有用例钉住两处一致）。
JS_TESTS_GLOB = "tests/js/*.test.mjs"
JS_TESTS_DIR = "tests/js/"

# 浏览器门禁（工单 ui-dom-contract-gate/03）：**与上面那条并列、相互独立**的一支。
#
# 它跑的是 `tests/browser/*.spec.mjs`——真浏览器（playwright chromium）+ 真后端
# （夹具自己起服务、自己挑空闲端口）。这些东西**不属于**上面那条门禁的前提：
# 那条的前提是"只吃 node: 内置模块、零 npm 依赖、几秒跑完"，浏览器用例三条都不满足。
# 所以两支并列、各自独立开关，改动落在哪一支就付哪一支的成本。
BROWSER_TESTS_GLOB = "tests/browser/*.spec.mjs"
BROWSER_TESTS_DIR = "tests/browser/"

# 浏览器用例覆盖的是 ui 的交互，所以"改了 ui 就得跑它"：
#   · tests/browser/                       = 用例与夹具自身
#   · static/js/ui/                        = ui 层（用例断的就是它的 DOM 契约）
#   · static/index.html                    = 标记（用例驱动真页面：555 个 id 都在这里）
#   · static/js/boot.js                    = **装载根**（模块清单 + 接线 + 启动；工单
#                                            frontend-boot-module/02 从 index.html 搬来的
#                                            —— 落点跟着搬家，否则"改了装载清单不跑真浏览器"）
#   · static/js/app.js                     = $ / apiGet / state 这些胶水的出处
# fx/ 不列：浏览器用例不直接断言 fx（那是 tests/js 纯函数面的事，已在另一支里）。
BROWSER_PREFIXES = (
    BROWSER_TESTS_DIR,
    "src/contest_generator/static/js/ui/",
    "src/contest_generator/static/index.html",
    "src/contest_generator/static/js/boot.js",
    "src/contest_generator/static/js/app.js",
)

# 前端改动落点（仓库根相对前缀）：改这些必须跑前端门禁。
#   · src/contest_generator/static/  = 整个前端资产（index.html / js/fx / js/ui / js/app.js）
#   · tests/js/                      = 前端用例自身
FRONTEND_PREFIXES = ("src/contest_generator/static/", JS_TESTS_DIR)


# 一个模块被这么多「测试文件」import 就算公共面：改它等于动半仓测试的地基，
# 只跑同名测试等于自欺。阈值取自实测分布（2026-09-16：86 个模块里 ≥10 的有 13 个，
# 恰好是 manifest / generator / selection / platforms / clex / webapp / boards /
# pin_bindings / errors / llm / patchers / pinwriter 这一层）。
WIDE_IMPORT_THRESHOLD = 10

# 库内容的守卫族：库（模块库 / 母版库 / 赛题库 / 参考库）变了，这些判据都可能翻。
LIBRARY_FAMILY = (
    "tests/test_library_invariants.py",
    "tests/test_library.py",
    "tests/test_wordlist.py",
    "tests/test_manifest.py",
    "tests/test_master.py",
    "tests/test_master_store.py",
    "tests/test_master_template_config.py",
    "tests/test_master_embedded.py",
    "tests/test_readme.py",
    "tests/test_skeleton_mapping_coverage.py",
    "tests/test_reference_library.py",
    "tests/test_topic_library.py",
    "tests/test_lckfb_attribution.py",
)

# 纯文档改动的守卫族：只写文档时不值得跑半仓，但这几条正是「文档与事实分叉」的闸门。
DOCUMENT_FAMILY = (
    "tests/test_readme.py",
    "tests/test_changelog.py",
    "tests/test_repo_language.py",
    "tests/test_onboarding_docs.py",
    "tests/test_ps1_encoding.py",
)

# 纯文档落点：改这些目录/文件不需要跑产品测试（仅文档守卫族）。
DOC_PREFIXES = ("docs/", ".scratch/", "assets/")
DOC_FILES = ("README.md", "VERSIONS.md", "CHANGELOG.md", "CONTEXT.md", "CLAUDE.md")

FULL = "FULL"
TESTS = "TESTS"
LIBRARY = "LIBRARY"
DOCS = "DOCS"
NONE = "NONE"


@dataclass(frozen=True)
class Selection:
    """选择结果：要跑的测试（仓库根相对）、是否必须整套、是否跑前端门禁、是否跑浏览器门禁、逐条理由。"""

    paths: tuple[str, ...]
    full: bool
    reasons: dict[str, str] = field(default_factory=dict)
    js: bool = False
    browser: bool = False

    def describe(self) -> str:
        if self.full:
            head = "整套 pytest"
        elif not self.paths:
            head = "不跑测试"
        else:
            head = f"{len(self.paths)} 个测试文件"
        if self.js:
            head += " + 前端门禁（" + JS_TESTS_GLOB + "）"
        if self.browser:
            head += " + 浏览器门禁（" + BROWSER_TESTS_GLOB + "）"
        why = "；".join(dict.fromkeys(self.reasons.values()))
        return f"{head}（{why or '无理由记录'}）"


_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+contest_generator\.([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE
)

_WIDE_CACHE: frozenset[str] | None = None


def wide_modules() -> frozenset[str]:
    """被 ≥ WIDE_IMPORT_THRESHOLD 个测试文件 import 的模块名（进程内缓存一次）。

    读的是测试文件里真实的 import 行——不手写名单，库/测试长大时判据自己跟上。
    """
    global _WIDE_CACHE
    if _WIDE_CACHE is not None:
        return _WIDE_CACHE
    counts: dict[str, int] = {}
    if TESTS_DIR.is_dir():
        for test_file in sorted(TESTS_DIR.glob("test_*.py")):
            try:
                text = test_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name in sorted(set(_IMPORT_RE.findall(text))):
                counts[name] = counts.get(name, 0) + 1
    _WIDE_CACHE = frozenset(n for n, c in counts.items() if c >= WIDE_IMPORT_THRESHOLD)
    return _WIDE_CACHE


def reset_cache() -> None:
    """测试用：丢掉 wide_modules 的进程内缓存。"""
    global _WIDE_CACHE
    _WIDE_CACHE = None


def known_test_files() -> frozenset[str]:
    """仓库里真实存在的测试文件（仓库根相对，正斜杠）。"""
    if not TESTS_DIR.is_dir():
        return frozenset()
    return frozenset(f"tests/{p.name}" for p in sorted(TESTS_DIR.glob("test_*.py")))


def normalize(path: str) -> str:
    """统一成仓库根相对的正斜杠路径（git 输出与本机路径都吃）。"""
    text = path.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def is_frontend_path(rel: str) -> bool:
    """前端落点判定（工单 module-hwcheck/01）：static/ 资产或 tests/js/ 用例。"""
    path = normalize(rel)
    return any(path.startswith(prefix) for prefix in FRONTEND_PREFIXES)


def is_browser_path(rel: str) -> bool:
    """浏览器门禁落点判定（工单 ui-dom-contract-gate/03）：ui / 装载清单 / 用例夹具。"""
    path = normalize(rel)
    return any(path.startswith(prefix) for prefix in BROWSER_PREFIXES)


def classify(path: str, *, tests: frozenset[str], wide: frozenset[str]) -> tuple[str, str, str]:
    """单条改动的归类 → (类, 要跑的测试或空串, 理由)。

    类 ∈ {FULL, TESTS, LIBRARY, DOCS, NONE}；FULL 表示「认不出/公共面 → 整套」。
    前端落点（static/ 与 tests/js/）**仍归 FULL**（pytest 面认不出对应关系，
    倒向更严），另由 select_tests 统一置 Selection.js——两支是叠加不是互斥。
    """
    rel = normalize(path)
    if not rel:
        return NONE, "", "空路径（跳过）"

    # 测试文件自身
    if rel.startswith("tests/"):
        if rel in tests:
            return TESTS, rel, f"测试文件自身（{rel}）"
        if rel.startswith(JS_TESTS_DIR):
            return FULL, "", (
                f"{rel} 是前端用例（node --test {JS_TESTS_GLOB} 跑，"
                "pytest 面照旧整套——倒向更严）"
            )
        return FULL, "", f"{rel} 在 tests/ 下但认不出（不是 test_*.py，倒向更严）"

    # 纯文档
    if rel in DOC_FILES or rel.startswith(DOC_PREFIXES):
        return DOCS, "", f"{rel} 是文档（只跑文档守卫族）"

    # 产品源码
    if rel.startswith("src/contest_generator/"):
        rest = rel[len("src/contest_generator/"):]
        if is_frontend_path(rel):
            return FULL, "", (
                f"{rel} 是前端资产（pytest 面认不出对应关系，倒向更严：整套跑，"
                f"另跑前端门禁 {JS_TESTS_GLOB}）"
            )
        if "/" in rest:
            top = rest.split("/", 1)[0]
            where = f"{top}/ 子目录"
            return FULL, "", f"{rel} 是{where}（pytest 面认不出对应关系，倒向更严）"
        if not rest.endswith(".py"):
            return FULL, "", f"{rel} 不是 .py（认不出，倒向更严）"
        module = rest[:-3]
        if module == "__init__":
            return FULL, "", "改包入口 __init__.py（版本号/导出面，整套跑）"
        if module in wide:
            return FULL, "", (
                f"{module} 被 ≥{WIDE_IMPORT_THRESHOLD} 个测试文件 import（公共面，整套跑）"
            )
        candidate = f"tests/test_{module}.py"
        if candidate in tests:
            return TESTS, candidate, f"命中同名测试 {candidate}"
        return FULL, "", f"{module} 没有同名测试（认不出影响面，倒向更严）"

    # 库内容
    if rel.startswith("library/"):
        return LIBRARY, "", f"{rel} 是库内容（跑库与母版守卫族）"

    # 仓库工具 / 闸门 / 投影 / 其余
    if rel.startswith(("tools/", ".githooks/", ".github/")):
        return FULL, "", f"{rel} 属仓库工具/闸门（认不出影响面，整套跑）"
    if rel in ("pyproject.toml", "pytest.ini", "setup.cfg", ".gitattributes", ".gitignore"):
        return FULL, "", f"{rel} 是投影/配置（会改测试行为，整套跑）"
    if rel.endswith((".ps1", ".js", ".mjs", ".html", ".css", ".md")):
        return FULL, "", f"{rel} 是脚本/前端/文档外落点（认不出影响面，整套跑）"
    return FULL, "", f"{rel} 认不出来（倒向更严：整套跑）"


def select_tests(changed: list[str], *, tests: frozenset[str] | None = None,
                 wide: frozenset[str] | None = None) -> Selection:
    """纯函数：一串改动路径 → 要跑的测试（含「必须整套」与「前端门禁」两支）。

    前端门禁（Selection.js）与 pytest 选择**相互独立**：前端落点让 pytest
    倒向整套（认不出对应关系），同时置 js=True——两支都跑，宁可贵一次。
    """
    tests = known_test_files() if tests is None else tests
    wide = wide_modules() if wide is None else wide

    if not changed:
        return Selection(paths=(), full=False, reasons={})

    # 两支前端门禁都先整体判一次（**不能**在循环里"遇到才置位"）：下面碰到
    # FULL 会提前 return，若标志还在循环里累加，改动顺序一旦是「先公共面/
    # 认不出的落点、后前端文件」，那次提前 return 就把门禁整个吞掉——
    # 改了前端却一条前端用例都不跑，且不报错（"少跑"长得像"全绿"）。
    js = any(is_frontend_path(raw) for raw in changed)
    browser = any(is_browser_path(raw) for raw in changed)

    picked: set[str] = set()
    reasons: dict[str, str] = {}
    full = False
    for raw in changed:
        rel = normalize(raw)
        kind, target, why = classify(rel, tests=tests, wide=wide)
        reasons[rel or raw] = why
        if kind == FULL:
            # **不在这里 return**：提前返回会把后面那些改动的理由丢掉
            # （--explain 只显示一部分，维护者据此判断"会跑什么"会被误导）。
            # 整套是一票否决，但理由要收全。
            full = True
            continue
        if kind == DOCS:
            picked.update(p for p in DOCUMENT_FAMILY if p in tests)
        elif kind == LIBRARY:
            picked.update(p for p in LIBRARY_FAMILY if p in tests)
        elif kind == TESTS and target:
            picked.add(target)

    if full:
        return Selection(paths=(), full=True, reasons=reasons, js=js, browser=browser)
    return Selection(paths=tuple(sorted(picked)), full=False, reasons=reasons, js=js, browser=browser)


# ---------------------------------------------------------------------------
# git 侧：本次要推的改动
# ---------------------------------------------------------------------------


def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败：{(result.stderr or '').strip()[:200]}")
    return result.stdout


def base_ref() -> str:
    """认「本地这个分支是从哪儿分出来的」用的引用（只读，不猜）。

    顺序：远端的默认分支（`origin/HEAD`）→ `origin/main` → `main` → `master`。
    一个都没有 → 空串（调用方据此倒向整套）。
    """
    try:
        name = _git(["rev-parse", "--abbrev-ref", "origin/HEAD"]).strip()
        if name:
            return name
    except RuntimeError:
        pass
    for candidate in ("origin/main", "main", "master"):
        try:
            _git(["rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"])
            return candidate
        except RuntimeError:
            continue
    return ""


def changed_from_refs(stdin_text: str) -> tuple[list[str], bool]:
    """按 pre-push 协议的 stdin 算改动 → (路径, 是否含 tag 推送)。

    git 给钩子的每行 = `<local ref> <local sha> <remote ref> <remote sha>`。

    三种情形分开处理（2026-09-16 两个真缺陷都在这里）：

    * **远端已有这条分支**（remote_sha 非零）：`remote_sha..local_sha` 就是本次要推的改动；
    * **推新分支 / 远端没有**（remote_sha 全零）：与「本分支分出来的那个点」比。
      这里**不能用 `origin/main`**——若本地 main 已经跟到远端默认分支的最新，那个基点
      就是 HEAD 自己，diff 恒空，闸门会静默判「没有守卫要跑」（实测踩到：一笔删掉
      母版守卫的提交就这么被放过去了）。改用 `HEAD~1`（新分支通常只有一个新提交）
      作基点；
    * **认不出远端状态**（远端 sha 本地没有）：倒向整套。

    另加一条**退化判据**：认得出 refs、却算出「零改动」时也倒向整套——宁可贵一次，
    不可静默放行。
    """
    changed: set[str] = set()
    has_tag = False
    saw_ref = False
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        local_ref, local_sha, _remote_ref, remote_sha = parts
        if local_ref.startswith("refs/tags/"):
            has_tag = True
            continue
        local_sha = local_sha.strip()
        remote_sha = remote_sha.strip()
        if not local_sha or set(local_sha) == {"0"}:
            continue
        saw_ref = True
        if set(remote_sha) == {"0"}:
            # 推新分支：优先用「分出来的那个点」（远端默认分支），它才是这批提交的完整范围；
            # 拿不到基点（没有默认分支引用 / 本地 HEAD 已跟到远端默认分支）时退到 HEAD~1。
            # 见 docstring 里的踩坑记录：**不能直接用 origin/main**——HEAD 跟到远端默认分支时
            # 那个基点就是 HEAD 自己，diff 恒空，闸门会静默放行。
            base = base_ref()
            spec = ""
            if base:
                try:
                    _git(["merge-base", "--is-ancestor", base, local_sha])
                    spec = f"{base}..{local_sha}"
                except RuntimeError:
                    spec = ""
            if not spec:
                spec = f"{local_sha}~1..{local_sha}"
        else:
            spec = f"{remote_sha}..{local_sha}"
        try:
            out = _git(["diff", "--name-only", "--diff-filter=ACMR", spec])
        except RuntimeError:
            # 基点不存在（远端那个 sha 本地没有 / 新分支只有一个提交）→ 整套
            return [], True
        changed.update(normalize(line) for line in out.splitlines() if line.strip())
    # 退化：认得出 refs、却算出「零改动」——不轻信，交给整套（由 main 转成 full）
    return sorted(changed), (has_tag or (saw_ref and not changed))


def changed_from_worktree() -> list[str]:
    """手动跑（没有 stdin refs）：拿「工作树 + 已暂存」相对 HEAD 的改动当输入。"""
    out = _git(["diff", "--name-only", "--diff-filter=ACMR", "HEAD"])
    return sorted({normalize(line) for line in out.splitlines() if line.strip()})


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------


def run_pytest(paths: tuple[str, ...], *, full: bool) -> int:
    """跑选中的测试（pytest 退出码原样返回；`-p no:cacheprovider` 不污染工作树）。"""
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if full:
        cmd.extend(["-n", "auto"])
    else:
        cmd.extend(paths)
    print(f"[prepush] 执行：{' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def js_test_files() -> tuple[str, ...]:
    """前端用例清单（仓库根相对 POSIX 路径，排序）——JS_TESTS_GLOB 展开的唯一实现。

    找不到任何用例 = 闸门判据失效（目录改名 / 清单过期）→ 返回空元组，调用方
    大声报错而不是"跑 0 个用例"（静默的 0 用例正是这道门禁最坏的失效方式）。
    """
    if not (REPO_ROOT / JS_TESTS_DIR).is_dir():
        return ()
    return tuple(
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted((REPO_ROOT / "tests" / "js").glob("*.test.mjs"))
    )


def run_js_tests() -> int:
    """跑前端门禁：`node --test <tests/js 下的每个 *.test.mjs>`（工单 module-hwcheck/01）。

    失败语义分三层，**别混**：

    * node 不在 PATH → 打印原因并返回 0（闸门自身能力缺失，不该把维护者堵在
      门外——与 "python 没装" 同政策）；
    * node 在、清单为空（目录改名等）→ 打印原因并返回 0（同上：判据失效不是
      代码红，且**不许**静默跑 0 个用例装作通过）；
    * node 在、用例跑了但红了 → 返回非 0（**这是真红，必须拒推**）。

    命令里传的是**展开后的真实文件路径**（见 JS_TESTS_GLOB 上方注释：交 glob
    给 node 要 ≥21，Node 20 会把它当字面文件名）。
    """
    exe = shutil.which("node")
    if exe is None:
        print(
            f"[prepush] 跳过前端门禁：PATH 里找不到 node（无法跑 {JS_TESTS_GLOB}）"
            "——装了 Node.js 后这条会自动生效",
            flush=True,
        )
        return 0
    files = js_test_files()
    if not files:
        print(
            f"[prepush] 跳过前端门禁：{JS_TESTS_DIR} 下没有 *.test.mjs（目录改名 / 清单过期？）",
            flush=True,
        )
        return 0
    cmd = [exe, "--test", *files]
    print(f"[prepush] 执行：{' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


def browser_test_files() -> tuple[str, ...]:
    """浏览器用例清单（仓库根相对 POSIX 路径，排序）——BROWSER_TESTS_GLOB 展开的唯一实现。"""
    if not (REPO_ROOT / BROWSER_TESTS_DIR).is_dir():
        return ()
    return tuple(
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted((REPO_ROOT / "tests" / "browser").glob("*.spec.mjs"))
    )


def run_browser_tests() -> int:
    """跑浏览器门禁：真浏览器（playwright chromium）+ 真后端（工单 ui-dom-contract-gate/03）。

    与 `run_js_tests` 的失败语义**同在一条政策上**（闸门自身能力缺失 → 打印原因放行；
    用例真红 → 拒推），只是"能力"这一项多了一层：这条门禁还要 playwright 与它下载的
    chromium。三道前置各查一次、各自说清缺什么：

    * node 不在 PATH → 放行（同上）；
    * 用例清单为空 → 放行（打印原因，不静默跑 0 个）；
    * playwright 装不上 / 浏览器二进制缺失（`require("playwright")` 或 `chromium.executablePath()`
      抛错）→ **放行并打印怎么装**（新 clone / CI 上这是"环境没准备好"，不是代码红）；
    * 用例跑了但红了 → 返回非 0。

    **`--test-concurrency=1` 是刻意的**：每个 spec 各起一个真后端 + 一个真 Chromium，
    跑在同一份工作树与同一个库目录上；端口已经各用各的了（夹具向内核要空闲端口），
    串行是为了失败可归因，也不再让三个 spec 抢同一份资源。
    """
    exe = shutil.which("node")
    if exe is None:
        print(
            f"[prepush] 跳过浏览器门禁：PATH 里找不到 node（无法跑 {BROWSER_TESTS_GLOB}）",
            flush=True,
        )
        return 0
    files = browser_test_files()
    if not files:
        print(
            f"[prepush] 跳过浏览器门禁：{BROWSER_TESTS_DIR} 下没有 *.spec.mjs（目录改名 / 清单过期？）",
            flush=True,
        )
        return 0
    probe = subprocess.run(
        [exe, "-e", "const {chromium}=require('playwright');console.log(chromium.executablePath())"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if probe.returncode != 0:
        print(
            "[prepush] 跳过浏览器门禁：playwright / chromium 不可用"
            "（新 clone 或 CI 上先跑 `npm install` + `npx playwright install chromium`）"
            f"\n    探测输出：{(probe.stderr or probe.stdout or '').strip()[:300]}",
            flush=True,
        )
        return 0
    cmd = [exe, "--test", "--test-concurrency=1", *files]
    print(f"[prepush] 执行：{' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(REPO_ROOT)).returncode


HINT = (
    "\n[prepush] 闸门拦下这次推送：上面的用例红了。\n"
    "  · 复跑：python tools/prepush.py --changed <你改的文件>\n"
    "  · 只跑前端：node --test " + JS_TESTS_GLOB + "\n"
    "  · 只跑浏览器验收：node --test --test-concurrency=1 " + BROWSER_TESTS_GLOB + "\n"
    "  · 强制整套：python tools/prepush.py --full\n"
    "  · 确知要绕过：FIRSTEP_PREPUSH=off git push（不鼓励）"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="推之前按改动选测试子集")
    parser.add_argument("--full", action="store_true", help="强制整套（pytest + 前端门禁）")
    parser.add_argument("--changed", nargs="*", default=None,
                        help="显式给改动路径（不给则从 git 读）")
    parser.add_argument("--dry-run", action="store_true", help="只说要跑什么，不执行")
    parser.add_argument("--select-only", action="store_true",
                        help="只做选择、绝不执行任何测试（钩子契约测试用；同 --dry-run）")
    parser.add_argument("--explain", action="store_true", help="打印每条改动的理由")
    parser.add_argument("--no-js", action="store_true",
                        help="跳过前端门禁（已知这次改动不需要跑 tests/js 时用）")
    parser.add_argument("--stdin-refs", action="store_true",
                        help="从 stdin 读 pre-push 协议的 refs（钩子用）")
    args = parser.parse_args(argv)

    mode = os.environ.get("FIRSTEP_PREPUSH", "").strip().lower()
    if mode == "off":
        print("[prepush] FIRSTEP_PREPUSH=off：跳过闸门（仅限你确知自己在做什么时）", flush=True)
        return 0

    full = bool(args.full) or mode == "full"

    if args.changed is None:
        stdin_text = ""
        try:
            if args.stdin_refs or not sys.stdin.isatty():
                stdin_text = sys.stdin.read()
        except Exception:  # noqa: BLE001 —— 读不到 stdin 就当没有 refs
            stdin_text = ""
        if stdin_text.strip():
            changed, tag_push = changed_from_refs(stdin_text)
            if tag_push:
                full = True
                if changed:
                    print("[prepush] 本次要推 tag（发版动作）→ 整套跑", flush=True)
                else:
                    print("[prepush] 认得出 refs 却算不出改动（新分支 / 基点认不出）→ 整套跑",
                          flush=True)
        else:
            try:
                changed = changed_from_worktree()
            except RuntimeError as exc:
                print(f"[prepush] 读不到 git 改动，放行：{exc}", flush=True)
                return 0
    else:
        changed = [normalize(p) for p in args.changed]

    selection = select_tests(changed)
    if full:
        # 「整套」= pytest 全套 + 前端门禁 + 浏览器门禁（发版 / 推 tag 的口径）：
        # 后两支平时由"改动落在对应落点"带起，而整套跑时改动可能一件前端文件都没有
        # （例如只改了 Python），照样要跑——不然"整套"名不副实。
        # **浏览器门禁也进整套**：它是"改动落在 ui 才跑"的那一支，整套的意义就是
        # 不看改动、全都跑一遍；不带上它，发版前反而漏掉真浏览器那一层。
        selection = Selection(paths=(), full=True, reasons=selection.reasons,
                              js=True, browser=True)
    if args.no_js:
        selection = Selection(paths=selection.paths, full=selection.full,
                              reasons=selection.reasons, js=False, browser=False)

    print(f"[prepush] 改动 {len(changed)} 个文件 → {selection.describe()}", flush=True)
    if args.explain or not selection.full:
        for rel, why in sorted(selection.reasons.items()):
            print(f"    - {rel}：{why}", flush=True)

    if args.dry_run or args.select_only or mode == "select-only":
        if selection.full:
            print("    · （整套）", flush=True)
        for path in selection.paths:
            print(f"    · {path}", flush=True)
        if selection.js:
            print(f"    · 前端门禁：node --test {JS_TESTS_GLOB}", flush=True)
        if selection.browser:
            print(f"    · 浏览器门禁：node --test --test-concurrency=1 {BROWSER_TESTS_GLOB}",
                  flush=True)
        return 0

    if not selection.full and not selection.paths and not selection.js and not selection.browser:
        print("[prepush] 没有需要跑的守卫，放行", flush=True)
        return 0

    # 前端门禁先跑（几秒钟）：它红了就没必要再等整套 pytest——但**每一支都要
    # 如实报到**，不能因为前者红就吞掉后面的（`&` 语义：跑完全部再定论）。
    # 浏览器门禁放在前端门禁之后、pytest 之前：它是三支里最贵的（真浏览器 + 真后端），
    # 前端那支红了就已经该拒推了，没必要再付这份成本；要是它自己红，pytest 也照跑。
    js_code = run_js_tests() if selection.js else 0
    browser_code = 0
    if selection.browser and js_code == 0:
        browser_code = run_browser_tests()
    elif selection.browser:
        print("[prepush] 跳过浏览器门禁：前端门禁已经红了（先修它再复跑）", flush=True)
    code = 0
    if selection.full or selection.paths:
        code = run_pytest(selection.paths, full=selection.full)
    if js_code != 0 or browser_code != 0 or code != 0:
        print(HINT, flush=True)
        return 1
    return 0


def safe_main(argv: list[str] | None = None) -> int:
    """闸门入口：自身出任何故障都放行（打印原因），只有测试红才拒推。"""
    try:
        return main(argv)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 —— 闸门坏了不该堵住维护者
        print(f"[prepush] 闸门自身故障（{type(exc).__name__}: {exc}）→ 放行本次推送", flush=True)
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(safe_main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
