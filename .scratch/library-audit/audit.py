"""模块库全链路一致性审计（只读，不改任何文件）。

覆盖 manifest → 依赖 → 平台文件 → 引脚声明 → 母版落点 → 词表 → 预算 的
每一步机械可查不变量，输出按严重度分组的发现清单。
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import boards as boards_mod  # noqa: E402
from contest_generator import budget as budget_mod  # noqa: E402
from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.library import BANNED_TOPIC_WORDS, find_topic_word_hits, list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402
from contest_generator.syscfg_instances import INSTANCES_BY_SLUG  # noqa: E402

MODULES_DIR = ROOT / "library" / "modules"
MASTERS_DIR = ROOT / "library" / "masters"

BLOCKERS: list[str] = []
RISKS: list[str] = []
NOTES: list[str] = []


def blocker(msg: str) -> None:
    BLOCKERS.append(msg)


def risk(msg: str) -> None:
    RISKS.append(msg)


def note(msg: str) -> None:
    NOTES.append(msg)


def main() -> None:
    manifests = list_modules(MODULES_DIR)
    by_slug = {m.slug: m for m in manifests}
    print(f"模块目录：{len(manifests)} 个（list_modules 全部加载成功）")

    check_dependencies(manifests, by_slug)
    check_platform_files(manifests)
    check_orphan_files(manifests)
    check_identity_fields(manifests)
    check_pins(manifests)
    check_mspm0_instances(manifests)
    check_stm32_macros(manifests)
    check_wordlist(manifests)
    check_summary_budget(manifests)
    check_descriptions(manifests)

    print_stats(manifests)


def check_dependencies(manifests, by_slug) -> None:
    for m in manifests:
        for dep in m.dependencies:
            if dep not in by_slug:
                blocker(f"[依赖] {m.slug} 依赖 {dep!r}，库内不存在")
        for spec in (m.python_artifact.templates if m.python_artifact else ()):
            for dep in spec.dependencies or ():
                if dep not in by_slug:
                    blocker(f"[依赖] {m.slug}:{spec.id} 模板依赖 {dep!r}，库内不存在")
    # 成环检测
    color: dict[str, int] = {}

    def visit(slug: str, stack: list[str]) -> None:
        color[slug] = 1
        m = by_slug.get(slug)
        if m:
            for dep in m.dependencies:
                if dep not in by_slug:
                    continue
                if color.get(dep) == 1:
                    blocker(f"[依赖] 成环：{' → '.join(stack + [slug, dep])}")
                elif color.get(dep, 0) == 0:
                    visit(dep, stack + [slug])
        color[slug] = 2

    for m in manifests:
        if color.get(m.slug, 0) == 0:
            visit(m.slug, [])
    # 被依赖次数（孤立模块提示）
    dependents = Counter()
    for m in manifests:
        for dep in m.dependencies:
            dependents[dep] += 1
    note(f"[依赖] 被依赖最多的模块：{dependents.most_common(6)}")


def check_platform_files(manifests) -> None:
    for m in manifests:
        module_dir = MODULES_DIR / m.slug
        for platform, entry in m.platforms.items():
            for rel in entry.files:
                path = module_dir / rel
                if not path.is_file():
                    blocker(f"[文件] {m.slug}/{platform} 声明的 {rel} 不存在")
            if not entry.files:
                note(f"[文件] {m.slug}/{platform} files 为空（实现内嵌母版）")
        if m.python_artifact:
            for t in m.python_artifact.templates:
                if not (module_dir / t.template).is_file():
                    blocker(f"[文件] {m.slug} 模板 {t.template} 不存在")
                for asset in t.assets:
                    if not (module_dir / asset.src).is_file():
                        blocker(f"[文件] {m.slug} 资产 {asset.src} 不存在")


def check_orphan_files(manifests) -> None:
    """模块目录下的 .c/.h 未被任何平台条目 / 模板引用 = 孤儿（漏登记或残留）。"""
    for m in manifests:
        module_dir = MODULES_DIR / m.slug
        referenced: set[str] = set()
        for entry in m.platforms.values():
            referenced.update(entry.files)
        if m.python_artifact:
            for t in m.python_artifact.templates:
                referenced.add(t.template)
                for asset in t.assets:
                    referenced.add(asset.src)
        for path in module_dir.rglob("*"):
            if path.suffix not in (".c", ".h"):
                continue
            rel = path.relative_to(module_dir).as_posix()
            if rel not in referenced:
                risk(f"[孤儿] {m.slug} 的 {rel} 未被任何平台条目引用")


def check_identity_fields(manifests) -> None:
    """硬件身份字段（kit / source_url）覆盖率——判据②。"""
    missing_kit: list[str] = []
    missing_url: list[str] = []
    bad_url: list[str] = []
    for m in manifests:
        for platform, entry in m.platforms.items():
            if not entry.kit:
                missing_kit.append(f"{m.slug}/{platform}")
            if not entry.source_url:
                missing_url.append(f"{m.slug}/{platform}")
            elif not entry.source_url.startswith("http"):
                bad_url.append(f"{m.slug}/{platform}={entry.source_url!r}")
    total = sum(len(m.platforms) for m in manifests)
    note(f"[身份] 平台条目共 {total}：缺 kit {len(missing_kit)}、缺 source_url {len(missing_url)}")
    if missing_kit:
        risk(f"[身份] 缺 kit 的平台条目：{'、'.join(sorted(missing_kit)[:40])}")
    if missing_url:
        risk(f"[身份] 缺 source_url 的平台条目：{'、'.join(sorted(missing_url)[:40])}")
    for item in bad_url:
        blocker(f"[身份] source_url 非 URL：{item}")


def check_pins(manifests) -> None:
    """引脚声明：默认脚必须在板上、且能力 token 支持该角色类型。"""
    board_cache = {p: boards_mod.board_for_platform(p) for p in KNOWN_PLATFORMS}
    overlap: dict[tuple[str, str], list[str]] = defaultdict(list)
    for m in manifests:
        for platform, entry in m.platforms.items():
            board = board_cache.get(platform)
            if board is None:
                blocker(f"[引脚] 未知平台 {platform}（{m.slug}）")
                continue
            for pin in entry.pins:
                bp = boards_mod.board_pin(board, pin.default)
                if bp is None:
                    blocker(
                        f"[引脚] {m.slug}/{platform} 角色 {pin.id} 默认脚 {pin.default}"
                        f" 不在板定义排针内"
                    )
                    continue
                # 类型级支持 = 裸 token 或 `<type>:<实例>` 任一（gpio_out/gpio_in
                # 是裸 token，实例型角色带冒号）
                if not any(
                    cap == pin.type or cap.startswith(f"{pin.type}:")
                    for cap in bp.capabilities
                ):
                    blocker(
                        f"[引脚] {m.slug}/{platform} 角色 {pin.id}({pin.type})"
                        f" 默认脚 {pin.default} 能力集不含该类型"
                        f"（{bp.capabilities}）"
                    )
                overlap[(platform, pin.default)].append(f"{m.slug}.{pin.id}")
    for (platform, pin_name), users in sorted(overlap.items()):
        if len(users) > 1:
            note(f"[引脚] {platform} {pin_name} 被 {len(users)} 个角色共用：{'、'.join(users)}")


def check_mspm0_instances(manifests) -> None:
    """mspm0 走 syscfg $assign：需要 GPIO 实例的模块必须在 INSTANCE_CONSUMERS 登记。"""
    for m in manifests:
        entry = m.platforms.get("mspm0")
        if entry is None:
            continue
        needs = any(
            p.type in ("gpio_out", "gpio_in") for p in entry.pins
        )
        if needs and m.slug not in INSTANCES_BY_SLUG:
            risk(f"[syscfg] {m.slug} mspm0 有 GPIO 角色但未登记 INSTANCE_CONSUMERS")
    known = {m.slug for m in manifests}
    for slug, instances in INSTANCES_BY_SLUG.items():
        if slug not in known:
            blocker(f"[syscfg] INSTANCE_CONSUMERS 指向不存在的模块 {slug!r}（实例 {instances}）")


def check_stm32_macros(manifests) -> None:
    """stm32 引脚角色声明的 macros 必须真的在母版 pin_config.h 里。"""
    pin_config = MASTERS_DIR / "stm32" / "pin_config.h"
    text = pin_config.read_text(encoding="utf-8", errors="replace")
    for m in manifests:
        entry = m.platforms.get("stm32")
        if entry is None:
            continue
        for pin in entry.pins:
            for macro in pin.macros:
                if macro not in text:
                    risk(f"[宏] {m.slug}/{pin.id} 声明宏 {macro} 不在母版 pin_config.h")
    # 反向：pin_config.h 里有宏但没有任何模块声明（死宏）
    declared = {
        macro
        for m in manifests
        for entry in (m.platforms.get("stm32"),)
        if entry
        for pin in entry.pins
        for macro in pin.macros
    }
    import re

    all_macros = set(re.findall(r"^#define\s+([A-Z][A-Z0-9_]+)", text, re.M))
    dead = sorted(all_macros - declared)
    if dead:
        note(f"[宏] pin_config.h 中无模块声明的宏 {len(dead)} 个：{'、'.join(dead[:30])}")


def check_wordlist(manifests) -> None:
    """词表 lib_modules 引用的 slug 必须存在；反向看哪些模块没进任何方案。"""
    slugs = {m.slug for m in manifests}
    try:
        entries = wordlist_mod.load_wordlist()
    except Exception as exc:  # noqa: BLE001
        blocker(f"[词表] 加载失败：{exc}")
        return
    referenced: set[str] = set()
    for entry in entries:
        for solution in entry.solutions:
            for slug in solution.lib_modules:
                referenced.add(slug)
                if slug not in slugs:
                    blocker(f"[词表] 方案 {solution.name!r} 引用不存在的模块 {slug!r}")
    unreferenced = sorted(slugs - referenced)
    if unreferenced:
        risk(f"[词表] 未被任何选购方案引用的模块 {len(unreferenced)} 个：{'、'.join(unreferenced)}")


def check_summary_budget(manifests) -> None:
    """模块摘要段 wire 字节 vs MODULE_SUMMARY_BYTES（预筛截断阈值）。"""
    for platform in KNOWN_PLATFORMS:
        scoped = [m for m in manifests if platform in m.platforms]
        lines = [s.to_line() for s in build_manifest_summaries(scoped)]
        wire = budget_mod.wire_size("\n".join(lines))
        pct = 100.0 * wire / budget_mod.MODULE_SUMMARY_BYTES
        msg = (
            f"[预算] {platform} 摘要 {len(scoped)} 条 wire={wire}B / "
            f"MODULE_SUMMARY_BYTES={budget_mod.MODULE_SUMMARY_BYTES}B（{pct:.0f}%）"
        )
        if wire > budget_mod.MODULE_SUMMARY_BYTES:
            risk(msg + " —— 全量摘要超段预算，AI 只能看到预筛命中的子集")
        else:
            note(msg)


def check_descriptions(manifests) -> None:
    for m in manifests:
        hits = find_topic_word_hits(m.description)
        if hits:
            blocker(f"[简介] {m.slug} 简介命中禁词 {hits}")
        if len(m.description) < 20:
            risk(f"[简介] {m.slug} 简介过短（{len(m.description)} 字）")


def print_stats(manifests) -> None:
    for platform in KNOWN_PLATFORMS:
        scoped = [m for m in manifests if platform in m.platforms]
        verified = [m for m in scoped if m.platforms[platform].verified]
        hw = [m for m in scoped if m.platforms[platform].hardware_bound]
        print(
            f"{platform}: {len(scoped)} 条（verified {len(verified)}、"
            f"hardware_bound {len(hw)}）"
        )
    multi = [m.slug for m in manifests if m.multi_instance]
    print(f"多实例模块：{multi}")
    py = [m.slug for m in manifests if m.python_artifact]
    print(f"Python 副产物模块：{py}")
    groups = Counter(
        m.exclusive_group.id for m in manifests if m.exclusive_group
    )
    print(f"功能互斥组：{dict(groups)}")


if __name__ == "__main__":
    main()
    print("\n" + "=" * 70)
    print(f"BLOCKER（必须修）{len(BLOCKERS)}")
    for msg in BLOCKERS:
        print("  [X]", msg)
    print(f"RISK（建议修）{len(RISKS)}")
    for msg in RISKS:
        print("  [!]", msg)
    print(f"NOTE（信息）{len(NOTES)}")
    for msg in NOTES:
        print("  [-]", msg)
