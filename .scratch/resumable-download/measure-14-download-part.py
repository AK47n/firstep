"""工单 14「先量再动」的取证脚本（只读，不改仓库）。

问的问题：`materials_task.download_part`（256 KB 分块那支，模块级**公开**函数）
今天到底还有没有活口？分五节量：

  A. **扫描面** selbst —— 扫了哪些文件、跳过什么（跳过必须写出来，否则「零调用点」不可信）；
  B. **逐处清单**：定义 / import / 调用 / 取值引用 / 只是提及，五类**分开**，
     `.py` 走 AST 判定（代码引用 vs 注释 docstring 提及不靠人眼），非 `.py` 按行模式判；
  C. **定义本体**：从 `git show <base>:<文件>` 取**改动前**那份（不读工作区现状，
     否则改完之后数字自己变了），与工作区那份并列；
  D. **对外承诺面**（工单 14 的关键一节，删之前必须查）：`__all__` / 文档点名 /
     打包白名单（`tools/pack-*.ps1`）/ 其它模块的 import / spec 里的声明；
  E. **历史**：这东西被哪些提交增删过、当没当过公开契约（`git log -S`）。

基线取法（口径与工单 10/12 一致）：
  - C 节逐字取 `git show <base>:<path>`；
  - B/D 节的「改动前」那一份用 `git grep <base>`（读的是 **git 对象**，不是工作区）——
    全仓 3500+ 文件逐个 `git show` 太慢，`git grep` 是同口径的廉价等价物，本节注明。

用法：
  python .scratch/resumable-download/measure-14-download-part.py           # 基线 = 工单 12 的收口提交
  python .scratch/resumable-download/measure-14-download-part.py <ref>
（输出打 stdout；由 `run-14-evidence.py` 取回落盘成 `verify-14-callers.txt`。）
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 工单 12 的收口提交（本单开工时的工作区基线；`4fc27282` 之后只有 CHANGELOG 自动提交）
DEFAULT_BASE = "4fc27282"

TARGET_REL = "src/contest_generator/materials_task.py"
TARGET_NAME = "download_part"

# 分区：一眼看出「活口在自研代码里还是在证据工具里」。
REGIONS = ("src", "tests", "docs", "tools", ".scratch", "static", "library", "sources", "other")

CALL_RE = re.compile(r"(?<![.\w])" + TARGET_NAME + r"\s*\(")
ATTR_RE = re.compile(r"\.\s*" + TARGET_NAME + r"\b")
BARE_RE = re.compile(r"(?<![\w.])" + TARGET_NAME + r"\b")
DEF_RE = re.compile(r"\bdef\s+" + TARGET_NAME + r"\s*\(")


def git(*args: str) -> str:
    # `--no-ext-diff --no-textconv`：本机 `diff.astextplain.textconv=astextplain` 会在
    # pickaxe（`-S`）碰到某个 `.dot` 文件时报 `E: unsupported filetype` + fatal 退出，
    # 于是「历史取证」那一节整节拿不到数据。钉住这两个开关，取证结果与机器配置无关。
    # 开关必须**跟在子命令后面**（`git log --no-ext-diff` 认，`git --no-ext-diff log` 不认）；
    # 且只有会产 diff 的子命令认它们——`git show <ref>:<path>` 取 blob 不产 diff，故不在名单里。
    switches = ["--no-ext-diff", "--no-textconv"] if args[0] in ("log", "diff") else []
    argv = ["git", args[0], *switches, *args[1:]] if switches else ["git", *args]
    out = subprocess.run(argv, cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{out.stderr.strip()}")
    return out.stdout


def region_of(rel: str) -> str:
    top = rel.split("/", 1)[0]
    if rel.startswith(".scratch/"):
        return ".scratch"
    if rel.startswith("src/contest_generator/static/"):
        return "static"
    return top if top in REGIONS else "other"


def tracked_files() -> list[str]:
    return [line for line in git("ls-files").splitlines() if line.strip()]


def scan_text(rel: str) -> str | None:
    """读工作区文本；二进制 / 读不了 → None（**跳过要计数**）。"""
    path = ROOT / rel
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def docstring_and_template_ranges(tree: ast.AST) -> tuple[list[tuple[int, int]],
                                                          list[tuple[int, int]]]:
    """（docstring 行区间, 其它字符串字面量行区间）。

    **为什么必须分开**：探针 `probe-01-negative.py` 的对照实现是**写在字符串模板里**
    再落盘执行的（`RUNNER_TEMPLATE`，里面有一句 `from contest_generator.materials_task
    import download_part as _plain`）。纯 AST 只看得见「一个字符串常量」，于是那处
    **真的会被执行的 import** 会被算成「提及」——量具自己制造的假账。
    docstring 则是纯说明，永远算提及；其余字符串里的**代码形态**行单列一类。
    """
    doc_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                first = body[0]
                doc_ranges.append((first.lineno, first.end_lineno or first.lineno))
    tmpl_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            span = (node.lineno, node.end_lineno or node.lineno)
            if not any(lo <= span[0] and span[1] <= hi for lo, hi in doc_ranges):
                tmpl_ranges.append(span)
    return doc_ranges, tmpl_ranges


def _inside(line: int, ranges: list[tuple[int, int]]) -> bool:
    return any(lo <= line <= hi for lo, hi in ranges)


def classify_python(text: str) -> dict[str, list[int]]:
    """AST 判「代码里的引用」——注释与 docstring 天然不进 AST（它们只是 提及）。"""
    found: dict[str, list[int]] = {
        "定义": [], "import": [], "调用": [], "取值引用": [], "模板代码": []}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return found
    call_nodes: set[int] = set()
    import_spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name == TARGET_NAME:
                found["调用"].append(node.lineno)
                call_nodes.add(id(func))
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            names = [alias.name for alias in node.names]
            if any(n == TARGET_NAME or n.endswith("." + TARGET_NAME) for n in names):
                # **整条 import 语句都算 import**：多行写法里裸名字在**续行**上
                # （`from … import (\n    download_part,\n)`），只记起始行会把续行
                # 漏成「提及」——量具自己制造的假账（第一版就是 23 行 import + 26 行提及）。
                import_spans.append((node.lineno, node.end_lineno or node.lineno))
                found["import"].append(node.lineno)
        elif isinstance(node, ast.FunctionDef) and node.name == TARGET_NAME:
            found["定义"].append(node.lineno)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == TARGET_NAME and id(node) not in call_nodes:
            if not _inside(node.lineno, import_spans):
                found["取值引用"].append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == TARGET_NAME and id(node) not in call_nodes:
            found["取值引用"].append(node.lineno)
    # 多行 import 的**续行**也要记成 import：裸名字那一行是 `ast.alias`（不是 `ast.Name`），
    # 上面两条循环都认领不到它——只记起始行会把它漏成「提及」（第一版就是这么漏的）。
    lines = text.splitlines()
    for lo, hi in import_spans:
        for line_no in range(lo, hi + 1):
            if 0 < line_no <= len(lines) and TARGET_NAME in lines[line_no - 1]:
                found["import"].append(line_no)
    for key in found:
        found[key] = sorted(set(found[key]))
    return found


def classify_other(rel: str, text: str) -> dict[str, list[int]]:
    """非 .py 分成两类口径，**别把文档当调用点**：

    - **纯文档/证据**（`.md` / `.txt` / `.json`）：里面写的是给人和给工具看的说明，
      没有执行语义 → 一律记「提及」；
    - **脚本类**（`.ps1` / `.js` / `.sh` …）：按行模式判（万一将来有人从脚本里调它）。
    """
    found: dict[str, list[int]] = {
        "定义": [], "import": [], "调用": [], "取值引用": [], "模板代码": []}
    if rel.endswith((".md", ".txt", ".json")):
        return found
    for idx, line in enumerate(text.splitlines(), 1):
        if TARGET_NAME not in line:
            continue
        stripped = line.lstrip()
        if DEF_RE.search(line):
            found["定义"].append(idx)
        elif re.match(r"(from|import)\s", stripped):
            found["import"].append(idx)
        elif CALL_RE.search(line):
            found["调用"].append(idx)
        elif ATTR_RE.search(line):
            found["取值引用"].append(idx)
    return found


def hit_lines(text: str) -> set[int]:
    return {idx for idx, line in enumerate(text.splitlines(), 1) if TARGET_NAME in line}


CATEGORIES = ("定义", "import", "调用", "取值引用", "模板代码", "提及")


def survey_files(files: list[str], reader) -> dict[str, dict[str, list[int]]]:
    """→ {rel: {类别: [行号]}}；只收命中 `download_part` 的文件。"""
    out: dict[str, dict[str, list[int]]] = {}
    for rel in files:
        text = reader(rel)
        if text is None or TARGET_NAME not in text:
            continue
        if rel.endswith(".py"):
            found = classify_python(text)
            doc_ranges, tmpl_ranges = docstring_and_template_ranges(ast.parse(text))
        else:
            found = classify_other(rel, text)
            doc_ranges, tmpl_ranges = [], []
        # 剩下的命中行：字符串模板里**代码形态**的算「模板代码」（会被执行），
        # docstring / 注释里的算「提及」（只是说明）。
        claimed = {ln for lines in found.values() for ln in lines}
        mentions: list[int] = []
        for line in sorted(hit_lines(text) - claimed):
            raw = text.splitlines()[line - 1]
            code_shaped = bool(CALL_RE.search(raw) or ATTR_RE.search(raw)
                               or re.match(r"\s*(from|import)\s", raw))
            if _inside(line, tmpl_ranges) and code_shaped:
                found["模板代码"].append(line)
            else:
                mentions.append(line)
        found["提及"] = mentions
        out[rel] = found
    return out


def print_survey(title: str, survey: dict[str, dict[str, list[int]]]) -> None:
    print(f"\n===== B. 逐处清单（{title}） =====")
    totals = {key: 0 for key in CATEGORIES}
    by_region: dict[str, dict[str, int]] = {}
    for rel in sorted(survey):
        found = survey[rel]
        counts = {k: len(v) for k, v in found.items()}
        for key, value in counts.items():
            totals[key] += value
            by_region.setdefault(region_of(rel), {k: 0 for k in totals})
            by_region[region_of(rel)][key] += value
        summary = "  ".join(f"{k}={v}" for k, v in counts.items() if v)
        print(f"  {rel}（{region_of(rel)}）: {summary}")
        for key in ("定义", "import", "调用", "取值引用", "模板代码"):
            if found[key]:
                print(f"      {key}：行 {found[key]}")
        if found["提及"]:
            preview = found["提及"][:6]
            more = "" if len(found["提及"]) <= 6 else f" …共 {len(found['提及'])} 行"
            print(f"      提及：行 {preview}{more}")
    print("\n  合计：" + " / ".join(f"{k} {totals[k]}" for k in CATEGORIES))
    print("  按分区：")
    for region in sorted(by_region):
        row = by_region[region]
        print(f"    {region:9s} " + " / ".join(f"{k} {row[k]}" for k in CATEGORIES))


def grep_ref(ref: str, pattern: str = TARGET_NAME) -> list[str]:
    out = subprocess.run(["git", "grep", "-n", "--full-name", "-w", pattern, ref],
                         cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode not in (0, 1):
        raise SystemExit(f"git grep {ref} 失败：{out.stderr.strip()}")
    return [line for line in (out.stdout or "").splitlines() if line.strip()]


def print_baseline_grep(ref: str) -> None:
    print(f"\n===== B′. 改动前那一份（`git grep {ref}`——读的是 git 对象，不是工作区） =====")
    hits = grep_ref(ref)
    if not hits:
        print("  （无命中）")
        return
    by_region: dict[str, int] = {}
    for line in hits:
        rel = line.split(":", 2)[1]
        by_region[region_of(rel)] = by_region.get(region_of(rel), 0) + 1
    print(f"  命中 {len(hits)} 行 / {len({l.split(':', 2)[1] for l in hits})} 个文件")
    print("  按分区：" + "，".join(f"{k} {v} 行" for k, v in sorted(by_region.items())))
    for line in hits:
        print(f"    {line}")


def function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node) or ""
            return node.lineno, node.end_lineno or node.lineno, segment
    raise SystemExit(f"源码里找不到 def {name}（扫描面变了？）")


def print_definition(base: str, worktree_source: str) -> None:
    print("\n===== C. 定义本体（改动前 / 现状） =====")
    before = git("show", f"{base}:{TARGET_REL}")
    for label, source in ((f"改动前（git {base}）", before), ("现状（工作区）", worktree_source)):
        try:
            lo, hi, segment = function_source(source, TARGET_NAME)
        except SystemExit as exc:
            print(f"  [{label}] {exc}")
            continue
        print(f"  [{label}] def 在第 {lo}-{hi} 行（共 {hi - lo + 1} 行）")
        print("  " + "\n  ".join(segment.splitlines()))
        print()


def print_affordances(worktree_source: str, survey: dict[str, dict[str, list[int]]],
                      base: str) -> None:
    print("\n===== D. 对外承诺面（删之前必须逐条查——它是模块级公开函数） =====")
    print("  *口径*：D2/D4/D5 读的是 `git grep <基线 ref>`（git 对象，不是工作区）；"
          "D6 读的是**工作区现状**（那两处事实只能在现状上问），已在该条里写明。")

    print("  D1 `__all__` / 模块级导出：")
    for label, source in (("改动前", git("show", f"{base}:{TARGET_REL}")),
                          ("现状", worktree_source)):
        hits = [ln for ln in source.splitlines() if "__all__" in ln]
        print(f"    [{label}] {'有：' + repr(hits) if hits else '模块里没有 __all__（不是显式导出面）'}")

    print(f"  D2 文档点名（docs/、CONTEXT.md、README、CHANGELOG、VERSIONS；"
          f"口径 = `git grep {base}`）：")
    doc_names = ("CONTEXT.md", "README.md", "CHANGELOG.md", "VERSIONS.md")
    doc_hits = [line for line in grep_ref(base)
                if region_of(line.split(":", 2)[1]) == "docs"
                or line.split(":", 2)[1] in doc_names]
    print("    " + ("（无）" if not doc_hits else ""))
    for line in doc_hits:
        print(f"    {line}")

    print("  D3 发布包白名单（三支打包器都要查——「活口算不算用户可见」的判据就在这儿）：")
    pack_update = (ROOT / "tools/pack-update.ps1").read_text(encoding="utf-8", errors="replace")
    array = re.search(r"\$TopLevels\s*=\s*@\(([^)]*)\)", pack_update, re.S)
    entries = re.findall(r"'([^']+)'", array.group(1)) if array else []
    print(f"    pack-update.ps1（小发版）：顶层白名单 {len(entries)} 项；"
          f"含 `src`={'src' in entries}；含 `.scratch`={'.scratch' in entries}")
    for line in pack_update.splitlines():
        if ".scratch" in line and line.lstrip().startswith("#"):
            print(f"       注释：{line.strip()}")

    full_pack_src = (ROOT / "src/contest_generator/full_pack.py").read_text(encoding="utf-8")
    top = re.search(r"TOP_LEVEL_ENTRIES[^=]*=\s*\(([^)]*)\)", full_pack_src, re.S)
    top_entries = re.findall(r'"([^"]+)"', top.group(1)) if top else []
    skip = re.search(r"SKIP_DIR_NAMES[^=]*=\s*frozenset\(\s*\{([^}]*)\}", full_pack_src, re.S)
    skip_entries = re.findall(r'"([^"]+)"', skip.group(1)) if skip else []
    print(f"    pack-full.ps1 → full_pack.py（完整包）："
          f"TOP_LEVEL_ENTRIES {len(top_entries)} 项；含 `src`={'src' in top_entries}；"
          f"SKIP_DIR_NAMES 含 `.scratch`={'.scratch' in skip_entries}")
    print("    pack-materials.ps1（资料库增量）：只打 `sources/materials`，与 `src/` 无关")

    print("  D4 其它模块的 import（src/ 分区里的 import 类命中）：")
    others = [(rel, found["import"]) for rel, found in survey.items()
              if region_of(rel) == "src" and found["import"]]
    print("    " + ("（无——除定义处外没有任何 src/ 模块 import 它）" if not others
                    else repr(others)))

    print("  D5 spec 里的声明（.scratch/resumable-download/spec.md）：")
    spec = (ROOT / ".scratch/resumable-download/spec.md").read_text(encoding="utf-8")
    for idx, line in enumerate(spec.splitlines(), 1):
        if TARGET_NAME in line:
            print(f"    spec.md:{idx}: {line.strip()}")

    print("  D6 spec 那两条理由今天还成立吗（要独立验证，不许照抄 spec）：")
    print("    *这一条读的是**工作区现状**（`download_resume` / `full_task` 当前正文）——"
          "它问的是「今天还成立吗」，基线那一份回答不了。")
    resume_src = (ROOT / "src/contest_generator/download_resume.py").read_text(encoding="utf-8")
    resume_calls = [ln for ln in resume_src.splitlines()
                    if CALL_RE.search(ln) and not ln.lstrip().startswith("#")]
    print(f"    - 「`download_resume` 内部调用它」：download_resume.py 里的**调用**行 = "
          f"{resume_calls if resume_calls else '[]（只有注释提到它——spec 这条理由已不成立）'}")
    full_task_src = (ROOT / "src/contest_generator/full_task.py").read_text(encoding="utf-8")
    print(f"    - 「既有 monkeypatch 点 `full_task.download_part` 继续有效」："
          f"full_task.py 里有 `download_part` 吗 = "
          f"{TARGET_NAME in full_task_src}")


def print_history() -> None:
    print("\n===== E. 历史：这东西被哪些提交增删过 =====")
    for label, extra in (("全仓", []),
                         ("tests/", ["--", "tests/"]),
                         ("src/", ["--", "src/"])):
        out = git("log", "--oneline", "-20", f"-S{TARGET_NAME}", *extra)
        print(f"  [{label}] `{TARGET_NAME}` 命中 {len(out.splitlines())} 次")
        for line in out.splitlines():
            print(f"      {line}")
    for label, needle in (("曾把名字 import 进 full_task", "from .materials_task import"),
                          ("曾 patch full_task.download_part", "full_task.download_part"),
                          ("定义本体", "def download_part")):
        out = git("log", "--oneline", "-20", f"-S{needle}")
        print(f"  [{label}] `{needle}` 命中 {len(out.splitlines())} 次")
        for line in out.splitlines():
            print(f"      {line}")


def main() -> int:
    # 输出**只打 stdout**，由 `run-14-evidence.py` 在内存里取回落盘（UTF-8）。
    # 本量具自己**不写文件**：让子进程自写目标文件会与落盘器抢同一个文件
    # （第一版留过一个「第二参数 = 证据文件」的分支，实际从没被走到——死代码，已删）。
    return _run()


def _run() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    files = tracked_files()
    skipped: list[str] = []

    def reader(rel: str) -> str | None:
        text = scan_text(rel)
        if text is None:
            skipped.append(rel)
        return text

    print(f"仓库根：{ROOT}")
    print(f"基线：{base}（改动前那一份从 git 对象取，不读工作区现状）")
    print("\n===== A. 扫描面 =====")
    print(f"  扫描对象 = `git ls-files` 的 tracked 文件 {len(files)} 个（含 .scratch/ 与 docs/）")
    print(f"  读不了 / 二进制（跳过）：{len(skipped)} 个"
          + (f"，例如 {skipped[:5]}" if skipped else ""))
    print("  未跟踪文件不在扫描面内（`git ls-files` 的口径）；"
          "`__pycache__` 之类的产物不在 tracked 里。")

    worktree = survey_files(files, reader)
    print_survey("现状（工作区）", worktree)
    print_baseline_grep(base)

    materials_source = (ROOT / TARGET_REL).read_text(encoding="utf-8")
    print_definition(base, materials_source)
    print_affordances(materials_source, worktree, base)
    print_history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
