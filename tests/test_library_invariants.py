"""模块库结构不变量：源码用到的引脚宏必须有主（工单 beep-pin-declaration/01）。

缺口：`beep` 的 stm32 源码直接驱动 `BUZZER_GPIO` / `BUZZER_PIN`，但清单既没
声明这两个引脚、也没声明提供宏的 `config` 依赖——引脚绑定界面看不见它、默认
布局白名单看不见它、`beep` + `jq8900` 同吃 PA15 时冲突标注静默通过。本文件把
「模块源码用到的引脚宏，必须能被该模块自身声明 ∪ 其依赖闭包内各模块声明溯源」
钉成全库不变量（扫真实 `library/modules/` 语料）——以后任何模块再偷用未声明的
引脚宏，这里立刻红。

只测外部行为：断言「用到的宏都能溯源」+ 冲突标注看得见 beep；不断言声明条目的
字段顺序、不钉具体模块清单（新模块入库不误伤）。

宏名单取源不靠手写词表：关注名单 = 全库 stm32 声明的 macros 全集（新模块自动
入名单），并用母版 `pin_config.h` 的机械抽取（名形 `_GPIO/_PORT/_PIN/_Pin/_CH`
尾 ∪ 值形 `GPIO_x` / `Pin_N`）做独立校验面——两侧对不上就红，避免词表漂移。
依赖闭包复用库内既有 `selection.resolve_dependencies`（不另写遍历）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.boards import BOARDS_DIR, load_boards
from contest_generator.manifest import ModuleManifest
from contest_generator.pin_bindings import auto_assign_bindings
from contest_generator.selection import resolve_dependencies

REPO_ROOT = Path(__file__).resolve().parents[1]
LIBRARY_MODULES = REPO_ROOT / "library" / "modules"
STM32_MASTER = REPO_ROOT / "library" / "masters" / "stm32"
PLATFORM = "stm32"

# 母版 pin_config.h 的宏行形态（与 tests/test_pins.py 同口径）：#define 名 值
_MASTER_DEFINE_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+([^/\s]+)")
# 引脚宏判据（机械，无手写名单）：名形尾 or 值形
_PIN_NAME_RE = re.compile(r"(_GPIO|_PORT|_PIN|_Pin|_CH)$")
_PORT_VALUE_RE = re.compile(r"^GPIO_[A-H]$")
_PIN_VALUE_RE = re.compile(r"^Pin_\d+$")
_IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")


def _master_defines() -> dict[str, str]:
    """母版 pin_config.h 全部 `#define`（宏名 → 值）。"""
    defines: dict[str, str] = {}
    for line in (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8").splitlines():
        m = _MASTER_DEFINE_RE.match(line)
        if m:
            defines[m.group(1)] = m.group(2).strip()
    return defines


def _load_manifests() -> dict[str, ModuleManifest]:
    return {
        m.slug: m
        for m in (
            ModuleManifest.load(module_dir)
            for module_dir in sorted(LIBRARY_MODULES.iterdir())
            if module_dir.is_dir()
        )
    }


MANIFESTS = _load_manifests()
MASTER_DEFINES = _master_defines()


def _declared_macros() -> set[str]:
    """全库 stm32 声明的 macros 全集。"""
    return {
        macro
        for manifest in MANIFESTS.values()
        for macro in _own_macros(manifest)
    }


def _master_shaped_macros() -> set[str]:
    """母版 pin_config.h 里「引脚形状」的宏：名形（`_GPIO/_PORT/_PIN/_Pin/_CH`
    尾）∪ 值形（`GPIO_x` / `Pin_N`）——机械抽取，无手写词表。"""
    shaped = {
        name
        for name, value in MASTER_DEFINES.items()
        if _PORT_VALUE_RE.match(value) or _PIN_VALUE_RE.match(value)
    }
    named = {name for name in MASTER_DEFINES if _PIN_NAME_RE.search(name)}
    return shaped | named


def _pin_macros() -> set[str]:
    """引脚宏关注名单 = 全库 stm32 声明的 macros 全集。

    取源不是手写词表：名单本身来自各模块清单的声明（新增模块自动入名单，
    新模块偷用未声明宏也逃不掉）；母版 `pin_config.h` 的机械抽取（
    `_master_shaped_macros`）作为独立校验面——见
    test_pin_macro_vocabulary_grounded_in_master。
    """
    return _declared_macros()


def _own_macros(manifest: ModuleManifest) -> set[str]:
    """模块自身（stm32 平台）声明的宏集。"""
    entry = manifest.platforms.get(PLATFORM)
    if entry is None:
        return set()
    return {macro for pin in entry.pins for macro in pin.macros}


def _closure_macros(slug: str) -> set[str]:
    """模块 + 依赖闭包内各模块声明的宏集（依赖展开复用 resolve_dependencies）。"""
    return {
        macro
        for manifest in resolve_dependencies([slug], MANIFESTS)
        for macro in _own_macros(manifest)
    }


def _used_pin_macros(manifest: ModuleManifest) -> dict[str, set[str]]:
    """模块 stm32 源码（code/*.c）用到的引脚宏：{相对路径: 宏集}。"""
    entry = manifest.platforms.get(PLATFORM)
    if entry is None:
        return {}
    pin_macros = _pin_macros()
    result: dict[str, set[str]] = {}
    for rel in entry.files:
        if not rel.endswith(".c"):
            continue
        text = strip_comments(
            (LIBRARY_MODULES / manifest.slug / rel).read_text(
                encoding="utf-8", errors="replace"
            ),
            keep_preprocessor=True,
        )
        hits = set(_IDENT_RE.findall(text)) & pin_macros
        if hits:
            result[rel] = hits
    return result


def _violations() -> list[str]:
    """全库差集：模块源码用到的引脚宏 ∉ 自身 ∪ 依赖闭包声明。"""
    problems: list[str] = []
    for slug, manifest in sorted(MANIFESTS.items()):
        traceable = _closure_macros(slug)
        for rel, used in sorted(_used_pin_macros(manifest).items()):
            missing = used - traceable
            if missing:
                problems.append(
                    f"模块 {slug} 的 {rel} 用了未声明的引脚宏："
                    f"{'、'.join(sorted(missing))}"
                )
    return problems


# ---------------------------------------------------------------------------
# 不变量：源码引脚宏必须有主
# ---------------------------------------------------------------------------


def test_module_source_pin_macros_traceable_to_declarations():
    """红证语义：源码用到的引脚宏必须能被自身或依赖闭包声明溯源；差集即失败，
    失败信息列出「模块 / 未声明宏 / 出处文件」。"""
    problems = _violations()
    assert not problems, "模块源码偷用未声明的引脚宏：\n- " + "\n- ".join(problems)


def test_pin_macro_vocabulary_grounded_in_master():
    """宏名单不漂移：关注名单 = 全库声明 macros，且每个声明宏都能在母版
    `pin_config.h` 里找到（机械抽取面）；母版的引脚形状宏也全部有主——
    任何一侧漂移（声明打错宏名 / 母版加了没人声明的引脚宏）这里红。"""
    declared = _declared_macros()
    assert declared
    assert declared <= set(MASTER_DEFINES), (
        "声明了母版 pin_config.h 里不存在的宏："
        f"{sorted(declared - set(MASTER_DEFINES))}"
    )
    assert _master_shaped_macros() <= declared, (
        "母版引脚形状宏没有模块声明："
        f"{sorted(_master_shaped_macros() - declared)}"
    )
    assert _pin_macros() == declared


def test_debug_uart_stays_green_via_dependency_closure():
    """debug_uart 也驱动 LED/BUZZER，但依赖 config——闭包溯源合法，始终绿。

    这是「依赖合法」一侧的反向守卫：若有人把 config 依赖删了或闭包不展开，
    该模块立刻进差集（本工单不修它）。"""
    manifest = MANIFESTS["debug_uart"]
    used = set().union(*_used_pin_macros(manifest).values())
    own = _own_macros(manifest)
    assert used - own, "debug_uart 应当借依赖闭包用别家的引脚宏（语料前提）"
    assert not (used - _closure_macros("debug_uart"))


def test_beep_stm32_buzzer_macros_are_declared():
    """修复本体：beep 的 stm32 条目声明 BUZZER_GPIO / BUZZER_PIN（gpio_out、
    默认 PA15）——与 code/beep_stm32.c 实际用法和母版 pin_config.h 一致。"""
    entry = MANIFESTS["beep"].platforms[PLATFORM]
    declarations = {
        macro: pin for pin in entry.pins for macro in pin.macros
    }
    used = set().union(*_used_pin_macros(MANIFESTS["beep"]).values())
    assert {"BUZZER_GPIO", "BUZZER_PIN"} <= set(declarations)
    assert used <= set(declarations)
    pin = declarations["BUZZER_GPIO"]
    assert pin is declarations["BUZZER_PIN"]  # 同一角色（一条声明带两宏）
    assert pin.type == "gpio_out"
    assert pin.default == "PA15"
    assert pin.required is True
    # mspm0 侧占位实现不引用引脚宏 → 不加声明（范围外，防回退）
    assert MANIFESTS["beep"].platforms["mspm0"].pins == ()


# ---------------------------------------------------------------------------
# 引脚冲突标注（既有能力）：beep + jq8900 同吃 PA15 必须被标成冲突
# ---------------------------------------------------------------------------


def _stm32_board():
    return next(b for b in load_boards(BOARDS_DIR) if b.platform == PLATFORM)


def test_beep_and_jq8900_share_pa15_is_reported_as_conflict():
    """beep 与 jq8900 默认同吃 PA15（提示输出互替）：冲突标注必须点名两者。

    只选 beep + jq8900（题面场景——config 的 BUZZER 角色不在场，PA15 无人认领
    时才见真章）：修复前 beep 没有引脚声明 → 冲突检查把它当空气、PA15 一条标注
    都没有（静默放行），本断言红；修复后 beep.BUZZER_OUT 进组、与
    jq8900.JQ8900_TX 分属不同外设（gpio_out × uart_tx），既有 pin-share 判据
    标 kind=conflict。"""
    manifests = [MANIFESTS[slug] for slug in ("beep", "jq8900", "delay")]
    result = auto_assign_bindings(manifests, PLATFORM, _stm32_board(), {})
    group = next((g for g in result.shared if g["pin"] == "PA15"), None)
    assert group is not None, "PA15 未被标注（beep 仍不可见？）"
    roles = set(group["roles"])
    assert {"beep.BUZZER_OUT", "jq8900.JQ8900_TX"} <= roles
    assert group["kind"] == "conflict"
    assert "外设" in str(group["reason"])


def test_beep_declaration_reaches_pin_binding_payload():
    """绑定界面数据源：声明经 manifest 序列化（/api/library 的模块载荷）到达
    前端——beep.BUZZER_OUT 在绑定载荷形状里可见、默认 PA15。"""
    entry = MANIFESTS["beep"].platforms[PLATFORM]
    payload = ModuleManifest.from_dict(MANIFESTS["beep"].to_dict())
    pins = payload.platforms[PLATFORM].pins
    assert [(p.id, p.type, p.default) for p in pins] == [
        ("BUZZER_OUT", "gpio_out", "PA15")
    ]
    assert pins == entry.pins


# ---------------------------------------------------------------------------
# 批次不变量收敛（工单 library-hookup-and-invariants/02）：21 个
# `.scratch/wiki-*/sweep_*.py` 里的批次专属快检脚本只在当批次跑过一次，
# 之后无人守。下面这些「对全库永远成立」的检查搬进 pytest，每跑一次测试就
# 检查一次；批次快照值（某批次某模块的 files/pins 期望）不进测试——历史
# 快照会随库演进失效，进测试只会变成维护负担。
# 判据同源：与只读审计脚本 `.scratch/library-audit/audit.py` 一致，脚本继续
# 作为人工复跑工具保留。
# ---------------------------------------------------------------------------


def test_module_slug_matches_directory_name():
    """slug 与目录名一致：库扫描按目录枚举、引用按 slug，两者错位会让
    「按 slug 找模块」的调用方（选择 / 绑定 / 生成）静默找不到。"""
    problems = [
        manifest.slug
        for manifest in MANIFESTS.values()
        if not (LIBRARY_MODULES / manifest.slug / "manifest.json").is_file()
    ]
    assert not problems, f"slug 与目录名不一致：{'、'.join(sorted(problems))}"


def test_declared_platform_files_exist():
    """平台条目声明的每个文件真实存在（空 files = 内嵌母版形态，跳过）：
    声明了却不在盘上 = 生成时复制失败，属硬故障。"""
    problems: list[str] = []
    for slug, manifest in sorted(MANIFESTS.items()):
        for platform, entry in sorted(manifest.platforms.items()):
            for rel in entry.files:
                if not (LIBRARY_MODULES / slug / rel).is_file():
                    problems.append(f"{slug}/{platform} 声明了不存在的文件：{rel}")
    assert not problems, "平台条目声明了不存在的文件：\n- " + "\n- ".join(problems)


def test_platform_entry_files_have_no_duplicates():
    """同一平台条目内文件不重复：重复声明会让生成时同一文件复制两次
    （覆盖无害但暴露 manifest 手改失误）。"""
    problems = [
        f"{slug}/{platform}"
        for slug, manifest in sorted(MANIFESTS.items())
        for platform, entry in sorted(manifest.platforms.items())
        if len(set(entry.files)) != len(entry.files)
    ]
    assert not problems, f"平台条目文件重复：{'、'.join(problems)}"


def test_module_dependencies_resolve_inside_library():
    """依赖不悬空：声明的依赖必须命中库内模块（拼错 slug = 生成时依赖展开
    静默少带模块，工程编不过）。"""
    problems = [
        f"{slug} → {dep}"
        for slug, manifest in sorted(MANIFESTS.items())
        for dep in manifest.dependencies
        if dep not in MANIFESTS
    ]
    assert not problems, f"依赖指向库外模块：{'、'.join(problems)}"


def test_module_dependency_graph_is_acyclic():
    """依赖图无环：环会让依赖展开（生成 / 绑定 / 门禁共用）无限递归。"""
    seen: set[str] = set()
    stack: list[str] = []
    cycles: list[str] = []

    def walk(slug: str) -> None:
        if slug in stack:
            cycles.append(" → ".join([*stack, slug]))
            return
        if slug in seen:
            return
        stack.append(slug)
        for dep in MANIFESTS[slug].dependencies:
            if dep in MANIFESTS:
                walk(dep)
        stack.pop()
        seen.add(slug)

    for slug in sorted(MANIFESTS):
        walk(slug)
    assert not cycles, f"依赖成环：{cycles}"


def test_wordlist_lib_modules_reference_existing_modules():
    """词表 `lib_modules` 引用都在库内（买件指引的「库内已有」标注与预筛
    挂接加分都按 slug 取模块，引用失效 = 标注指向空气）。"""
    wordlist = json.loads(
        (REPO_ROOT / "src" / "contest_generator" / "wordlist.json").read_text(
            encoding="utf-8"
        )
    )
    problems = [
        f"{group['category']}/{solution['name']} → {slug}"
        for group in wordlist
        for solution in group.get("solutions", [])
        for slug in solution.get("lib_modules", [])
        if slug not in MANIFESTS
    ]
    assert not problems, f"词表引用了库中不存在的模块：{'、'.join(problems)}"


def test_modules_have_descriptions():
    """模块必须有简介：摘要行（喂给 AI 的模块清单）以简介为主干，空的
    简介等于模型看不见这个模块的用途。"""
    problems = [
        slug for slug, manifest in sorted(MANIFESTS.items())
        if not manifest.description.strip()
    ]
    assert not problems, f"模块缺简介：{'、'.join(problems)}"
