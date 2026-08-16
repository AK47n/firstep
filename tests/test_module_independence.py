"""module-functionalize/10：模块独立性结构门禁。

把「模块尽量独立、不互相牵连」钉成机械不变量：
- 跨模块 include 必须在 manifest.dependencies 声明（隐藏耦合拦截）；
- 声明的依赖必须有实际 include（死依赖拖拽拦截）；
- 依赖图无环、依赖目标都存在（架构方向单向朝底层基础模块）。

读盘/注释剥离走 clex（与生成门禁同源）；字符串进字符串出，本测试不碰
生成器行为、不改模块代码。当前真实库审计结果：0 未声明依赖 / 0 环 /
0 死依赖（2026-08-15）。
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from contest_generator.clex import extract_quoted_includes, strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"

MANIFESTS = tuple(
    ModuleManifest.load(d) for d in sorted(MODULES.iterdir()) if d.is_dir()
)
SLUGS = tuple(m.slug for m in MANIFESTS)
DEPENDENCIES = {m.slug: set(m.dependencies) for m in MANIFESTS}


def _header_owners() -> dict[str, str]:
    """全库头文件基名 → 所属模块 slug（小写化，Windows 大小写不敏感）。"""
    owners: dict[str, set[str]] = {}
    for manifest in MANIFESTS:
        for path in (MODULES / manifest.slug).rglob("*.h"):
            if path.is_file():
                owners.setdefault(path.name.lower(), set()).add(manifest.slug)
    ambiguous = {name: slugs for name, slugs in owners.items() if len(slugs) > 1}
    assert not ambiguous, f"模块头基名跨模块重复（依赖归属歧义）：{ambiguous}"
    return {name: next(iter(slugs)) for name, slugs in owners.items()}


HEADER_OWNERS = _header_owners()


def _quoted_includes(slug: str, path: Path) -> tuple[str, ...]:
    """单文件注释剥离后的引号 include（errors=replace 与门禁同读法）。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    return tuple(
        header.lower()
        for header in extract_quoted_includes(
            strip_comments(text, keep_preprocessor=True)
        )
    )


def _module_includes(slug: str) -> set[tuple[str, str]]:
    """(被引头文件名小写, 目标模块 slug) 集合——只收跨模块引用的头。"""
    hits: set[tuple[str, str]] = set()
    for path in (MODULES / slug).rglob("*"):
        if not path.is_file() or path.suffix.lower() not in (".c", ".h"):
            continue
        for header in _quoted_includes(slug, path):
            owner = HEADER_OWNERS.get(header)
            if owner is not None and owner != slug:
                hits.add((header, owner))
    return hits


def test_cross_module_includes_are_declared_dependencies():
    """引用其他模块头 = manifest 已声明依赖：不让隐藏耦合漏过静态门禁。"""
    problems: list[str] = []
    for slug in SLUGS:
        for header, owner in sorted(_module_includes(slug)):
            if owner not in DEPENDENCIES[slug]:
                problems.append(
                    f"{slug} 引用了 {owner} 的头 {header}，但 manifest.dependencies"
                    f" 未声明 {owner}"
                )
    assert not problems, "跨模块 include 未声明依赖：\n" + "\n".join(problems)


def test_declared_dependencies_have_actual_include():
    """manifest 声明的依赖必须有实际 include：禁止死依赖拖拽无关模块。"""
    problems: list[str] = []
    for slug in SLUGS:
        owners_used = {owner for _, owner in _module_includes(slug)}
        for dep in sorted(DEPENDENCIES[slug]):
            if dep not in owners_used:
                problems.append(
                    f"{slug} 声明依赖 {dep}，但没有任何文件 include {dep} 的头"
                )
    assert not problems, "死依赖（声明但未使用）：\n" + "\n".join(problems)


def test_dependency_graph_is_acyclic_and_targets_exist():
    """依赖目标存在 + 无环：模块依赖只允许单向朝底层基础模块。"""
    unknown = {
        f"{slug} -> {dep}"
        for slug in SLUGS
        for dep in DEPENDENCIES[slug]
        if dep not in DEPENDENCIES
    }
    assert not unknown, "依赖了不存在的模块：\n" + "\n".join(sorted(unknown))

    indegree = {slug: 0 for slug in SLUGS}
    for slug in SLUGS:
        for dep in DEPENDENCIES[slug]:
            indegree[dep] += 1

    queue = deque(slug for slug in SLUGS if indegree[slug] == 0)
    ordered: list[str] = []
    while queue:
        slug = queue.popleft()
        ordered.append(slug)
        for dep in DEPENDENCIES[slug]:
            indegree[dep] -= 1
            if indegree[dep] == 0:
                queue.append(dep)
    assert len(ordered) == len(SLUGS), (
        "依赖环参与模块："
        + ", ".join(sorted(set(SLUGS) - set(ordered)))
    )
