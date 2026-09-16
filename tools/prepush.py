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
| `library/`（库内容） | 库与母版守卫族（见 `LIBRARY_FAMILY`） |
| 纯文档（README / VERSIONS / CHANGELOG / docs/ / .scratch/） | 文档守卫族（见 `DOCUMENT_FAMILY`） |
| **认不出来的任何路径** | 全套（倒向更严） |

**绝不卡人的边界**：闸门自身故障（python 没装 / git 读不到改动 / 选择器抛错）
一律**打印原因并放行**（exit 0）——闸门坏了不该把维护者堵在门外；但**测试真红了必须拒推**。

用法：

    python tools/prepush.py                    # 从 git 读本次推送的改动（pre-push 钩子走这条）
    python tools/prepush.py --changed src/contest_generator/manifest.py
    python tools/prepush.py --full             # 强制全套
    python tools/prepush.py --dry-run          # 只说要跑什么，不执行
    python tools/prepush.py --explain          # 打印每条改动的命中理由
    FIRSTEP_PREPUSH=full python tools/prepush.py    # 环境变量强制全套
    FIRSTEP_PREPUSH=off  python tools/prepush.py    # 跳过（明写警告）

退出码：0 = 通过或按规则放行；1 = 测试红（应当拒推）；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"

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
    """选择结果：要跑的文件（仓库根相对）、是否必须整套、逐条理由。"""

    paths: tuple[str, ...]
    full: bool
    reasons: dict[str, str] = field(default_factory=dict)

    def describe(self) -> str:
        if self.full:
            head = "整套 pytest"
        elif not self.paths:
            head = "不跑测试"
        else:
            head = f"{len(self.paths)} 个测试文件"
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


def classify(path: str, *, tests: frozenset[str], wide: frozenset[str]) -> tuple[str, str, str]:
    """单条改动的归类 → (类, 要跑的测试或空串, 理由)。

    类 ∈ {FULL, TESTS, LIBRARY, DOCS, NONE}；FULL 表示「认不出/公共面 → 整套」。
    """
    rel = normalize(path)
    if not rel:
        return NONE, "", "空路径（跳过）"

    # 测试文件自身
    if rel.startswith("tests/"):
        if rel in tests:
            return TESTS, rel, f"测试文件自身（{rel}）"
        return FULL, "", f"{rel} 在 tests/ 下但认不出（不是 test_*.py，倒向更严）"

    # 纯文档
    if rel in DOC_FILES or rel.startswith(DOC_PREFIXES):
        return DOCS, "", f"{rel} 是文档（只跑文档守卫族）"

    # 产品源码
    if rel.startswith("src/contest_generator/"):
        rest = rel[len("src/contest_generator/"):]
        if "/" in rest:
            top = rest.split("/", 1)[0]
            where = "前端/模板资产" if top in ("static", "templates") else f"{top}/ 子目录"
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
    """纯函数：一串改动路径 → 要跑的测试（含「必须整套」一支）。"""
    tests = known_test_files() if tests is None else tests
    wide = wide_modules() if wide is None else wide

    if not changed:
        return Selection(paths=(), full=False, reasons={})

    picked: set[str] = set()
    reasons: dict[str, str] = {}
    for raw in changed:
        rel = normalize(raw)
        kind, target, why = classify(rel, tests=tests, wide=wide)
        reasons[rel or raw] = why
        if kind == FULL:
            return Selection(paths=(), full=True, reasons=reasons)
        if kind == DOCS:
            picked.update(p for p in DOCUMENT_FAMILY if p in tests)
        elif kind == LIBRARY:
            picked.update(p for p in LIBRARY_FAMILY if p in tests)
        elif kind == TESTS and target:
            picked.add(target)

    return Selection(paths=tuple(sorted(picked)), full=False, reasons=reasons)


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


def changed_from_refs(stdin_text: str) -> tuple[list[str], bool]:
    """按 pre-push 协议的 stdin 算改动 → (路径, 是否含 tag 推送)。

    git 给钩子的每行 = `<local ref> <local sha> <remote ref> <remote sha>`。
    推 tag = 发版动作 → 调用方应当整套跑（这里只如实报出来）。
    """
    changed: set[str] = set()
    has_tag = False
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
        if set(remote_sha) == {"0"}:
            # 远端还没这条分支：与默认分支的合并基点比
            try:
                base = _git(["merge-base", local_sha, "origin/main"]).strip()
            except RuntimeError:
                base = ""
            spec = f"{base}..{local_sha}" if base else local_sha
        else:
            spec = f"{remote_sha}..{local_sha}"
        try:
            out = _git(["diff", "--name-only", "--diff-filter=ACMR", spec])
        except RuntimeError:
            # 远端那个 sha 本地没有（别人 force push 过之类）：认不出 → 整套
            return [], True
        changed.update(normalize(line) for line in out.splitlines() if line.strip())
    return sorted(changed), has_tag


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


HINT = (
    "\n[prepush] 闸门拦下这次推送：上面的用例红了。\n"
    "  · 复跑：python tools/prepush.py --changed <你改的文件>\n"
    "  · 强制整套：python tools/prepush.py --full\n"
    "  · 确知要绕过：FIRSTEP_PREPUSH=off git push（不鼓励）"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="推之前按改动选测试子集")
    parser.add_argument("--full", action="store_true", help="强制整套")
    parser.add_argument("--changed", nargs="*", default=None,
                        help="显式给改动路径（不给则从 git 读）")
    parser.add_argument("--dry-run", action="store_true", help="只说要跑什么，不执行")
    parser.add_argument("--explain", action="store_true", help="打印每条改动的理由")
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
                print("[prepush] 本次要推 tag（发版动作）→ 整套跑", flush=True)
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
        selection = Selection(paths=(), full=True, reasons=selection.reasons)

    print(f"[prepush] 改动 {len(changed)} 个文件 → {selection.describe()}", flush=True)
    if args.explain or not selection.full:
        for rel, why in sorted(selection.reasons.items()):
            print(f"    - {rel}：{why}", flush=True)

    if args.dry_run:
        for path in selection.paths:
            print(f"    · {path}", flush=True)
        return 0

    if not selection.full and not selection.paths:
        print("[prepush] 没有需要跑的守卫，放行", flush=True)
        return 0

    code = run_pytest(selection.paths, full=selection.full)
    if code != 0:
        print(HINT, flush=True)
    return code


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
