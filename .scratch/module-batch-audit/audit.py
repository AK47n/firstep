# -*- coding: utf-8 -*-
"""批量模块入库审计（地阔星 dkx 线 + 地猛星 dmx 线，免真机）：
扫描 library/modules 全部 manifest / 代码 / wordlist / 测试 / 文档，输出
结构化问题清单。只读，不改任何文件。

检查面：
A  目录与 manifest 完整性（slug==目录名、JSON 可解析、平台条目字段齐全、
   files 存在、pins 合法、deps 有落点）
B  平台条目不变量（verified / hardware_bound / kit / source_url / 来源 URL 归线）
C  词表挂接（wordlist lib_modules 覆盖）
D  测试覆盖（wiki 线 slug 是否有 test_module_<slug>.py）
E  stm32 默认引脚跨模块重叠 vs test_default_layout.WHITELIST（漂移检测）
F  mspm0 默认引脚跨模块重叠 + 证据标注核查（notes 是否提及对方 slug/重叠词）
G  双平台 API 对偶（头文件导出函数集合差异，仅信息面）
H  文档数字核对（README 派生模块数 vs 实况；CONTEXT 批次提及）
I  必需角色（required=true）同默认脚碰撞（最高风险项）
"""
import ast
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "library" / "modules"
TESTS = REPO / "tests"
PINCFG = (REPO / "library" / "masters" / "stm32" / "pin_config.h").read_text(
    encoding="utf-8", errors="replace"
)
WL = json.load(open(REPO / "src" / "contest_generator" / "wordlist.json", encoding="utf-8"))
LIBMODS: set[str] = set()
for g in WL:
    for s in g.get("solutions", []):
        LIBMODS.update(s.get("lib_modules", []))

# mspm0 线（batch1-13）slug 集 = 自 sweep_52_modules.py 的 batch_slugs
sweep_src = (REPO / ".scratch" / "wiki-modules-batch13" / "sweep_52_modules.py").read_text(
    encoding="utf-8", errors="replace"
)
tree = ast.parse(sweep_src)
DMX_SLUGS: set[str] = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "batch_slugs":
        DMX_SLUGS = {x.value for x in node.value.elts if isinstance(x, ast.Constant)}
# dkx（stm32 线）slug 集 = dkx-map.tsv 的 lib_slug 列
import csv as _csv

DKX_MAP_ROWS = list(
    _csv.DictReader(
        open(REPO / ".scratch" / "materials-wiki" / "dkx-map.tsv",
             encoding="utf-8", newline=""),
        delimiter="\t",
    )
)
assert len(DKX_MAP_ROWS) == 77, f"dkx-map.tsv 行数 {len(DKX_MAP_ROWS)} ≠ 77"
DKX_SLUGS: set[str] = set()
for _row in DKX_MAP_ROWS:
    _slug = (_row["lib_slug"] or "").strip()
    if _slug.startswith("（新）"):
        _slug = _slug[3:].strip()
    if _slug:
        DKX_SLUGS.add(_slug)

problems: list[str] = []
info: list[str] = []


def manifest(slug: str):
    p = MOD / slug / "manifest.json"
    return json.load(open(p, encoding="utf-8")) if p.is_file() else None


def find_funcs(text: str) -> set[str]:
    """头文件导出函数名粗提取（去注释）。"""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    names = set()
    for m in re.finditer(r"(?:^|\n)\s*(?:[A-Za-z_][\w\s\*]*?)\b(\w+)\s*\([^;{}]*\)\s*;",
                         text, flags=re.S):
        names.add(m.group(1))
    return names


# ---------- A 目录与 manifest 完整性 ----------
# 基建/系统件按设计无 pins 声明（config/delay/filter/uart 等；k230 副控板；
# multi_instance led…走 led_instances.h 通道宏，不占引脚角色）
INFRA_NO_PINS = {
    "beep", "config", "delay", "filter", "k230", "led", "led_beep",
    "ntb_time", "uart",
}
all_slugs = sorted(d.name for d in MOD.iterdir() if d.is_dir())
for slug in all_slugs:
    p = MOD / slug / "manifest.json"
    if not p.is_file():
        problems.append(f"[A] {slug}: 缺 manifest.json")
        continue
    try:
        m = json.load(open(p, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        problems.append(f"[A] {slug}: manifest.json 无法解析 {e}")
        continue
    if m.get("slug") != slug:
        problems.append(f"[A] {slug}: manifest.slug={m.get('slug')!r} ≠ 目录名")
    if "description" not in m or not m.get("description", "").strip():
        problems.append(f"[A] {slug}: 缺 description")
    if "dependencies" not in m or not isinstance(m.get("dependencies"), list):
        problems.append(f"[A] {slug}: dependencies 不是列表")
    else:
        for dep in m["dependencies"]:
            if not (MOD / dep).is_dir():
                problems.append(f"[A] {slug}: 依赖 {dep} 无落点")
    plats = m.get("platforms", {})
    if not plats:
        problems.append(f"[A] {slug}: platforms 为空")
    for plat in plats:
        if plat not in ("mspm0", "stm32"):
            problems.append(f"[A] {slug}: 未知平台键 {plat}")
        e = plats[plat]
        for key in ("files", "verified", "hardware_bound", "notes", "pins"):
            if key not in e and not (key == "pins" and slug in INFRA_NO_PINS):
                problems.append(f"[A] {slug}.{plat}: 缺字段 {key}")
        for f in e.get("files", []):
            if not (MOD / slug / f).is_file():
                problems.append(f"[A] {slug}.{plat}: files 缺失 {f}")
        pins = e.get("pins", [])
        if not pins:
            if slug not in INFRA_NO_PINS:
                problems.append(f"[A] {slug}.{plat}: pins 为空")
        else:
            seen_ids: set[str] = set()
            for pin in pins:
                if pin.get("id") in seen_ids:
                    problems.append(f"[A] {slug}.{plat}: 角色 id 重复 {pin.get('id')}")
                seen_ids.add(pin.get("id"))
                if not pin.get("default"):
                    problems.append(f"[A] {slug}.{plat}: {pin.get('id')} 默认脚为空")
                if pin.get("type") not in (
                        "gpio_out", "gpio_in", "uart_tx", "uart_rx", "pwm", "enc",
                        "adc", "i2c_scl", "i2c_sda", "spi_mosi", "spi_miso",
                        "spi_sck", "spi_cs", "exti"):
                    problems.append(f"[A] {slug}.{plat}: {pin.get('id')} 类型词表外 {pin.get('type')!r}")
                for macro in pin.get("macros", []):
                    if not re.search(r"#define\s+" + re.escape(macro) + r"\s+", PINCFG):
                        problems.append(f"[A] {slug}.stm32: pin_config.h 未定义 {macro}")

# ---------- B 平台条目不变量（仅对 wiki 线 slug 检查 kit/source_url） ----------
WIKI_LINE = DMX_SLUGS | DKX_SLUGS
VERIFIED_EXCEPT = {"k230", "zigbee_link"}   # 既有设计：verified=false
HW_EXCEPT = {"coord_detect", "k230", "beep", "led_beep", "ml_mpu6050",
             "huidu", "xunji"}              # 既有设计：hardware_bound=true（板载/官方库）
# kit/source_url 缺口（批次前状态；**补录实证不可行**——代码源为 21F/car 工程，
# 挂 wiki URL 会触发 test_lckfb_attribution「wiki 派生模块源码头带原页 URL」断言，
# 属虚来源宣称；维持缺口直至来源字段重构（区分代码来源与硬件身份））
KIT_SRC_GAP = {"huidu", "xunji", "motor", "servo", "oled"}
for slug in all_slugs:
    m = manifest(slug)
    if m is None:
        continue
    for plat in ("mspm0", "stm32"):
        e = m.get("platforms", {}).get(plat)
        if e is None:
            continue
        if e.get("verified") is not True and slug not in VERIFIED_EXCEPT:
            problems.append(f"[B] {slug}.{plat}: verified != True")
        if e.get("hardware_bound") is not False and slug not in HW_EXCEPT:
            problems.append(f"[B] {slug}.{plat}: hardware_bound != False")
        if slug not in WIKI_LINE or slug in KIT_SRC_GAP:
            continue  # 基建/母版内嵌件与既有缺口件：维持批次前状态（见 KIT_SRC_GAP 注释）
        if not e.get("kit") or not str(e.get("kit", "")).strip():
            problems.append(f"[B] {slug}.{plat}: 缺 kit")
        if not e.get("source_url"):
            problems.append(f"[B] {slug}.{plat}: 缺 source_url")

# 来源 URL 归线与计数
dmx_url = re.compile(r"^https://wiki\.lckfb\.com/zh-hans/dmx/")
dkx_url = re.compile(r"^https://wiki\.lckfb\.com/zh-hans/dkx-stm32f103c8t6/")
dmx_mods: set[str] = set()
dkx_mods: set[str] = set()
for slug in all_slugs:
    m = manifest(slug)
    if m is None:
        continue
    for plat, e in m.get("platforms", {}).items():
        u = str(e.get("source_url") or "")
        if dmx_url.match(u):
            dmx_mods.add(slug)
        if dkx_url.match(u):
            dkx_mods.add(slug)
info.append(f"[B] dmx（地猛星）来源模块数={len(dmx_mods)}；dkx（地阔星）来源模块数={len(dkx_mods)}")
info.append(f"[B] sweep52 声明的 dmx slug={len(DMX_SLUGS)}，dkx-map slug={len(DKX_SLUGS)}")
missing_dmx_sweep = DMX_SLUGS - dmx_mods
missing_dkx_map = DKX_SLUGS - dkx_mods
if missing_dmx_sweep:
    info.append(f"[B] dmx slug 在 sweep 但无 dmx 来源 URL: {sorted(missing_dmx_sweep)}")
if missing_dkx_map:
    info.append(f"[B] dkx slug 在 map 但无 dkx 来源 URL: {sorted(missing_dkx_map)}")

# ---------- C 词表挂接 ----------
no_wl = [s for s in all_slugs if s not in LIBMODS]
info.append(f"[C] wordlist lib_modules 未挂接的模块（含基建件可能属编缉例外）: {no_wl}")
wl_slugs = {s for s in LIBMODS if (MOD / s).is_dir()}
ghost = sorted(s for s in LIBMODS if not (MOD / s).is_dir())
if ghost:
    problems.append(f"[C] wordlist 引用了不存在的模块目录: {ghost}")

# ---------- D 测试覆盖（wiki 线；既有件有结构性覆盖，记入豁免） ----------
D_TEST_EXCEPT = {
    "huidu": "test_module_dep_cleanup/test_module_universality 覆盖",
    "xunji": "test_module_dep_cleanup/test_module_universality 覆盖",
    "ml_mpu6050": "test_module_universality/test_module_jy61p 分工断言覆盖",
    "motor": "test_module_motor_parity 覆盖",
    "oled": "test_module_oled_extra/test_module_oled_spi 覆盖",
}
for slug in sorted(DMX_SLUGS | DKX_SLUGS):
    if slug in D_TEST_EXCEPT:
        continue
    if not (TESTS / f"test_module_{slug}.py").is_file():
        problems.append(f"[D] wiki 线模块 {slug} 无 test_module_{slug}.py")

# ---------- E stm32 默认脚重叠 vs WHITELIST ----------
try:
    dl_src = (TESTS / "test_default_layout.py").read_text(encoding="utf-8")
    dl_tree = ast.parse(dl_src)
    whitelist: dict[str, set[str]] = {}
    for node in ast.walk(dl_tree):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "WHITELIST":
            whitelist = {k.value: {x.value for x in v.elts} for k, v in
                         zip(node.value.keys, node.value.values)}
    overlap_st: list[tuple[str, str, set[str]]] = []
    grouped: dict[str, set[str]] = {}
    for slug in all_slugs:
        m = manifest(slug)
        if m is None:
            continue
        e = m.get("platforms", {}).get("stm32")
        if e is None:
            continue
        for pin in e.get("pins", []):
            grouped.setdefault(pin["default"], set()).add(f"{slug}.{pin['id']}")
    for pin, roles in sorted(grouped.items()):
        if len(roles) > 1:
            wl_roles = whitelist.get(pin, set())
            drift = roles - wl_roles
            overlap_st.append((pin, ",".join(sorted(roles)), sorted(drift)))
    for pin, roles, drift in overlap_st:
        if drift:
            problems.append(f"[E] stm32 默认脚 {pin} 共享但不在白名单: {sorted(drift)}"
                            f"（白名单={sorted(whitelist.get(pin, set()))}）")
    info.append(f"[E] stm32 默认脚重叠组数={len(overlap_st)}（均有白名单）= "
                f"{len([x for x in overlap_st if not x[2]])}")
except Exception as e:  # noqa: BLE001
    info.append(f"[E] WHITELIST 解析跳过: {e}")

# ---------- F mspm0 默认脚重叠 + 证据标注核查 ----------
msp_grouped: dict[str, set[str]] = {}
for slug in all_slugs:
    m = manifest(slug)
    if m is None:
        continue
    e = m.get("platforms", {}).get("mspm0")
    if e is None:
        continue
    for pin in e.get("pins", []):
        msp_grouped.setdefault(pin["default"], set()).add(f"{slug}.{pin['id']}")
undoc: list[str] = []
doc_ok = 0
overlap_pairs = 0
HINT = ("重叠|互替|共享|同脚|同槽|同框|同读|叠|共用|占位|共读|消解")
for pin, roles in sorted(msp_grouped.items()):
    if len(roles) < 2:
        continue
    pairset = []
    for a in sorted(roles):
        for b in sorted(roles):
            if a >= b:
                continue
            overlap_pairs += 1
            sa, ra = a.split(".", 1)
            sb, rb = b.split(".", 1)
            ma, mb = manifest(sa), manifest(sb)
            na = (ma.get("platforms", {}).get("mspm0", {}).get("notes") or "") if ma else ""
            nb = (mb.get("platforms", {}).get("mspm0", {}).get("notes") or "") if mb else ""
            ev = f"{sb}|{rb}" in na or f"{sa}|{ra}" in nb
            ev = ev or (sb in na and re.search(HINT, na))
            ev = ev or (sa in nb and re.search(HINT, nb))
            ev = ev or (pin in na and re.search(HINT, na))
            ev = ev or (pin in nb and re.search(HINT, nb))
            if ev:
                doc_ok += 1
            else:
                undoc.append(f"{pin}: {a} × {b}")
info.append(f"[F] mspm0 默认脚重叠对={overlap_pairs}，notes 有证据={doc_ok}，"
            f"无直接证据={len(undoc)}")
for u in undoc[:40]:
    info.append(f"[F]   无标注证据重叠: {u}")

# ---------- G 双平台 API 对偶 ----------
for slug in all_slugs:
    m = manifest(slug)
    if m is None:
        continue
    e_m = m.get("platforms", {}).get("mspm0")
    e_s = m.get("platforms", {}).get("stm32")
    if not e_m or not e_s:
        continue
    hdr_m = [f for f in e_m["files"] if f.endswith(".h")]
    hdr_s = [f for f in e_s["files"] if f.endswith(".h")]
    if not hdr_m or not hdr_s:
        continue
    fm = set()
    for f in hdr_m:
        fm |= find_funcs((MOD / slug / f).read_text(encoding="utf-8", errors="replace"))
    fs = set()
    for f in hdr_s:
        fs |= find_funcs((MOD / slug / f).read_text(encoding="utf-8", errors="replace"))
    only_m = sorted(fm - fs)
    only_s = sorted(fs - fm)
    if only_m or only_s:
        info.append(f"[G] {slug}: mspm0-only={only_m} stm32-only={only_s}")

# ---------- H 文档数字核对 ----------
readme = (REPO / "README.md").read_text(encoding="utf-8", errors="replace")
m56 = re.search(r"(\d+)\s*个派生模块", readme)
if m56:
    claimed = int(m56.group(1))
    if claimed != len(dmx_mods):
        problems.append(f"[H] README 称 {claimed} 个派生模块（dmx），实况={len(dmx_mods)}")
context = (REPO / "CONTEXT.md").read_text(encoding="utf-8", errors="replace")
for n in range(1, 14):
    if f"wiki-modules-batch{n}" not in context and f"batch{n}/" not in context:
        problems.append(f"[H] CONTEXT.md 未提及 wiki-modules-batch{n}")
for n in range(1, 12):
    if f"wiki-stm32-batch{n}" not in context and f"batch{n}/" not in context:
        problems.append(f"[H] CONTEXT.md 未提及 wiki-stm32-batch{n}")

# ---------- I 必需角色同默认脚（双平台，按角色类型家族分类） ----------
I2C_FAM = {"i2c_scl", "i2c_sda"}
UART_FAM = {"uart_tx", "uart_rx"}
for plat in ("mspm0", "stm32"):
    req_groups: dict[str, list[tuple[str, str]]] = {}
    for slug in all_slugs:
        m = manifest(slug)
        if m is None:
            continue
        e = m.get("platforms", {}).get(plat)
        if e is None:
            continue
        for pin in e.get("pins", []):
            if pin.get("required"):
                req_groups.setdefault(pin["default"], []).append(
                    (f"{slug}.{pin['id']}", pin.get("type", "")))
    cross_bus: list[str] = []
    same_bus: int = 0
    for pin, roles in sorted(req_groups.items()):
        if len(roles) < 2:
            continue
        types = {t for _, t in roles}
        if types <= I2C_FAM or types <= UART_FAM:
            same_bus += 1
            continue
        cross_bus.append(f"{pin}: {sorted(r for r, _ in roles)}")
    info.append(f"[I] {plat} 必需角色同默认脚：同家族（I2C/UART 总线共享合法）"
                f"={same_bus}，跨家族={len(cross_bus)}")
    for c in cross_bus:
        info.append(f"[I]   {plat} 跨家族必需同脚（同选需绑定消解）: {c}")

# ---------- J dkx 映射 slug 的 stm32 条目来源 URL 归线 ----------
st_offline: list[str] = []
for slug in sorted(DKX_SLUGS):
    m = manifest(slug)
    if m is None:
        problems.append(f"[J] dkx-map 映射 {slug} 无 manifest")
        continue
    e = m.get("platforms", {}).get("stm32")
    if e is None:
        continue  # A 类 mspm0-only 例外（huidu/xunji/sr04）
    u = str(e.get("source_url") or "")
    if not dkx_url.match(u):
        st_offline.append(f"{slug}: {u[:100]}")
info.append(f"[J] dkx 映射且 stm32 条目来源非 dkx-stm32f103c8t6 前缀: {len(st_offline)}")
for s in st_offline:
    info.append(f"[J]   {s}")

# ---------- K mspm0 线批次溯源 ----------
no_batch = [s for s in sorted(DMX_SLUGS) if "batch" not in
            json.dumps(manifest(s) or {}, ensure_ascii=False)]
if no_batch:
    info.append(f"[K] dmx 线 slug 的 manifest 无批次溯源: {no_batch}")


# ---------- 汇总 ----------
print("== 模块总数:", len(all_slugs))
print("== mspm0 条目数:", sum(1 for s in all_slugs if manifest(s) and manifest(s).get("platforms", {}).get("mspm0")))
print("== stm32 条目数:", sum(1 for s in all_slugs if manifest(s) and manifest(s).get("platforms", {}).get("stm32")))
for line in info:
    print(line)
print("==")
if problems:
    print(f"=== 问题 {len(problems)} 条 ===")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("=== 审计通过（无 A/B/C/D/E/F/H/I 问题） ===")
