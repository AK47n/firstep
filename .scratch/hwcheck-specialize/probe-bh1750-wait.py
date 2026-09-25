# -*- coding: utf-8 -*-
"""工单 04 的**本格反证**：`bh1750` 那句等待为什么只能住 `prereq`、以及少了它会丢什么。

要证的两件事（工单 04 的判据原文是"删掉那句 `delay_ms(...)` → 产物里必须看不到等待
（或编译/行为对不上），证明这一条不是装饰"）：

  **① 形状被 schema 逼出来的**（可伪证的那一半）：把这句 `delay_ms(...)` 从 `prereq`
     搬到 `init`（同样是"这一节的初始化"这个直觉写法）→ 喂真校验器（`parse_recipes` +
     `validate_recipes`）：**mspm0 侧构建期红**（母版没有 .h，这节的判据面只认
     `bh1750.h` 里的名字），**stm32 侧照样 PASS**（`ml_delay.h` 是母版头）。
     这一条**可能失败**——如果哪天 mspm0 也有母版头了，读数就会翻过来，那正是它该说话的时候。

  **② 少了它就真的少了等待**（另一半）：只从配方文件里删掉那一句 → 渲染出的
     `hwcheck_check_bh1750()` 里等待消失，而**其余语句逐条不变**（断言，不只是打印）。
     读回来的会是上电默认值（通常 0 lx）——工单要的就是"这一句承重"。

做法：0) 前置（两平台各渲染一遍，断言等待恰好 1 条、且顺序 = init → start → 等 → 读）；
1) 形状实验（纯内存，不碰文件）；2) 删一句 → 渲染（断言等待没了、其余不变）；
3) 按原字节回滚 → 再渲染（断言与前置逐行相同）；4) 回滚保真（sha256）。

退出码 0 = 反证成立。读数先落盘 `probe-bh1750-wait.txt` 再打印。
用法：`py -3 .scratch/hwcheck-specialize/probe-bh1750-wait.py`
"""
import copy
import hashlib
import json
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.hwcheck_errors import HwCheckError  # noqa: E402
from contest_generator.hwcheck_recipe import (  # noqa: E402
    interface_names, load_recipes, parse_recipes, render_recipe_section,
    resolve_sections, validate_recipes,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.master_store import master_project_dir  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.treewalk import iter_project_files  # noqa: E402

RECIPES = REPO / "library" / "hwcheck_recipes.json"
MODULES = REPO / "library" / "modules"
SLUG = "bh1750"
WAIT_CALL = "delay_ms(BH1750_MEASURE_DELAY_MS)"
PLATFORMS = (PLATFORM_STM32, PLATFORM_MSPM0)

LINES: list[str] = ["=== 工单 04 反证：bh1750 那句等待只能住 prereq，且它是承重的 ===", ""]
FAILURES: list[str] = []

MANIFESTS = list_modules(MODULES)
INTERFACES: dict[str, dict[str, frozenset]] = {}
for _name in PLATFORMS:
    _master = master_project_dir(REPO / "library" / "masters", _name)
    _headers = [] if not _master.is_dir() else [
        (path.relative_to(_master).as_posix(),
         path.read_text(encoding="utf-8", errors="replace"))
        for path in iter_project_files(_master, pattern="*.h")
    ]
    INTERFACES[_name] = interface_names(MANIFESTS, MODULES, _name, _headers)
    LINES.append(f"   {_name} 母版 .h 个数 = {len(_headers)}；"
                 f"{SLUG} 判据面里有 delay_ms 吗 = "
                 f"{'delay_ms' in INTERFACES[_name][SLUG]}")
LINES.append("")


def _real_recipes():
    return load_recipes(MODULES, MANIFESTS, INTERFACES)


def _render_real(platform: str) -> list[str]:
    """真配方 → 这一件这一平台渲染出的 C 语句。"""
    sections = resolve_sections(platform, (SLUG,), _real_recipes(), MANIFESTS)
    target = [s for s in sections if s.slug == SLUG]
    if len(target) != 1:
        raise SystemExit(f"{SLUG} × {platform} 没渲染出唯一小节：{sections!r}")
    return render_recipe_section(target[0])


def _statements(code: list[str]) -> list[str]:
    """这一节里"真的调了什么"那几行（注释与判定记账滤掉，只看顺序）。"""
    return [
        line.strip() for line in code
        if line.strip().endswith(";") and not line.strip().startswith("/*")
        and not any(tag in line for tag in
                    ("hwcheck_report", "hwcheck_detail", "hwcheck_verdict",
                     "hwcheck_section"))
    ]


def _waits(code: list[str]) -> list[str]:
    return [line.strip() for line in code if WAIT_CALL in line]


# ---------------------------------------------------------------- 0) 前置
original = RECIPES.read_bytes()
before_digest = hashlib.sha256(original).hexdigest()
document = json.loads(original.decode("utf-8"), object_pairs_hook=OrderedDict)
if SLUG not in document:
    raise SystemExit(f"{SLUG} 不在配方文件里——这条反证的前提变了")
for platform in PLATFORMS:
    calls = document[SLUG][platform].get("prereq", {}).get("calls", [])
    if calls.count(WAIT_CALL) != 1:
        raise SystemExit(
            f"{SLUG} × {platform} 的 prereq 里那句等待不是恰好 1 条：{calls!r}——前提变了")

BEFORE: dict[str, list[str]] = {}
LINES.append(f"0) 前置：配方文件 sha256 = {before_digest[:16]}…；"
             f"{SLUG} 的 prereq（两平台）= " + " / ".join(
                 repr(document[SLUG][p]["prereq"]["calls"]) for p in PLATFORMS))
for platform in PLATFORMS:
    code = _render_real(platform)
    BEFORE[platform] = code
    statements = _statements(code)
    waits = _waits(code)
    LINES.append(f"   渲染 {SLUG} × {platform}：等待 {len(waits)} 条 → {waits}")
    LINES.append(f"   语句顺序 = {statements}")
    if len(waits) != 1:
        FAILURES.append(f"{platform} 前置不干净：渲染产物里等待 {len(waits)} 条（应为 1）")
    # 顺序判据（不只是"在不在"）：init → start → 等 → 读
    order = [i for i, s in enumerate(statements)
             if "bh1750_" in s or WAIT_CALL in s]
    want = ["bh1750_init();", "bh1750_start_measure();", WAIT_CALL + ";",
            "r = bh1750_read_lux(&lux);"]
    got = [statements[i] for i in order]
    if got != want:
        FAILURES.append(f"{platform} 前置不干净：语句顺序 = {got}，期望 = {want}")
LINES.append("")

# ------------------------------------- 1) 形状实验：同一句搬进 init（纯内存，不碰文件）
LINES.append("1) 形状实验：把同一句 `delay_ms(...)` 搬进 **init** 段（不碰文件），喂真校验器：")
for platform in PLATFORMS:
    probe_doc = copy.deepcopy(document[SLUG][platform])
    probe_doc["prereq"]["calls"] = [c for c in probe_doc["prereq"]["calls"]
                                   if c != WAIT_CALL]
    probe_doc["init"] = {"calls": ["bh1750_init()", "bh1750_start_measure()", WAIT_CALL]}
    try:
        recipes = parse_recipes({SLUG: {platform: probe_doc}})
        validate_recipes(recipes, MANIFESTS, {platform: INTERFACES[platform]})
    except HwCheckError as exc:
        LINES.append(f"   {platform}：✗ 构建期红 → {str(exc).splitlines()[0][:160]}")
        if platform != PLATFORM_MSPM0:
            FAILURES.append(f"{platform} 本该 PASS（母版有 ml_delay.h）却红了——"
                            "「只有 prereq 放行」这句话在这一侧不成立")
    else:
        LINES.append(f"   {platform}：✓ PASS（这一侧本来就放行 delay_ms）")
        if platform == PLATFORM_MSPM0:
            FAILURES.append("mspm0 侧把 delay_ms 放进 init 竟然 PASS 了——"
                            "「形状被 schema 逼出来」这句话不成立")
LINES.append("")

# --------------------------------- 2) 删掉那一句：等待必须消失、其余语句逐条不变
patched_bytes: bytes | None = None
restored = False
AFTER: dict[str, list[str]] = {}
try:
    for platform in PLATFORMS:
        document[SLUG][platform]["prereq"]["calls"] = [
            c for c in document[SLUG][platform]["prereq"]["calls"] if c != WAIT_CALL
        ]
    newline = "\r\n" if "\r\n" in original.decode("utf-8") else "\n"
    text = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline)
    patched_bytes = (text + newline).encode("utf-8")
    RECIPES.write_bytes(patched_bytes)

    LINES.append("2) 只删掉 prereq 里那一句（其余一字不动）之后：")
    for platform in PLATFORMS:
        code = _render_real(platform)
        AFTER[platform] = code
        statements = _statements(code)
        waits = _waits(code)
        LINES.append(f"   {platform}：等待 {len(waits)} 条 → {waits}")
        LINES.append(f"   语句顺序 = {statements}")
        if waits:
            FAILURES.append(f"{platform} 删掉等待后产物里**仍然**有等待——反证不成立")
        # "其余不变"是断言，不是打印：把前置里的那一行抽掉，应与现在逐条相同
        want_rest = [s for s in _statements(BEFORE[platform]) if WAIT_CALL not in s]
        if statements != want_rest:
            FAILURES.append(f"{platform} 删掉等待后其余语句也变了："
                            f"{statements} ≠ {want_rest}")
finally:
    current = RECIPES.read_bytes()
    if patched_bytes is not None and current == patched_bytes:
        RECIPES.write_bytes(original)
        restored = hashlib.sha256(RECIPES.read_bytes()).hexdigest() == before_digest
    else:
        FAILURES.append("配方文件在反证窗口期内被外力改动，未回滚（不覆盖别人的改动）")
    LINES.append("")
    LINES.append(f"3) 回滚：{'✓ 按原字节写回，sha256 与前置一致' if restored else '✗ 未回滚'}"
                 f"（{hashlib.sha256(RECIPES.read_bytes()).hexdigest()[:16]}…）")

if restored:
    LINES.append("4) 拿回来之后：")
    for platform in PLATFORMS:
        code = _render_real(platform)
        waits = _waits(code)
        LINES.append(f"   {platform}：等待 {len(waits)} 条 → {waits}")
        if len(waits) != 1:
            FAILURES.append(f"{platform} 还原后等待没回来——配方文件没回到原状")
        if code != BEFORE[platform]:
            FAILURES.append(f"{platform} 还原后渲染产物与前置不逐行相同")

verdict = not FAILURES
LINES.append("")
LINES.append("结论：" + (
    "✓ 反证成立——① 同一句搬进 init 时 mspm0 构建期红、stm32 照样过（形状确实被 schema 逼到 "
    "prereq）；② 删掉它，渲染产物里的等待消失而其余语句逐条不变；③ 按原字节还原、产物逐行复原"
    if verdict else "✗ 反证不成立：" + "；".join(FAILURES)))

out_text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-bh1750-wait.txt").write_text(
    out_text, encoding="utf-8")
print(out_text)
raise SystemExit(0 if verdict else 1)
