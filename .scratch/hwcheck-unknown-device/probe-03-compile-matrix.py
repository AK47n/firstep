# -*- coding: utf-8 -*-
"""hwcheck-unknown-device/03+04 真编译矩阵：**自建件探测小节** × 两平台。

证的是什么（03 的验收线，04 扩到第二个平台）：检测页为一件库外件渲染出的探测
小节（自建件 ＋ `i2c_probe` 支点 ＋ 通道模块）在**两平台**都能过一次真编译，
且 **0 error / 0 warning** —— "能生成"与"能编译"不是两件事（spec 判据）。

跟 `compile_matrix.py`（工单 01）的分工：那支只证"支点模块本身能编译"，本支证
**产品渲染出的 main.c**（经 `hwcheck_view` + `render_main_c` 这条真路径）在真
母版工程里能编译。所以这里不手写 main.c —— 用手写的那份就绕过了要验的东西。

矩阵两轴：

* **平台**：`mspm0`（CCS SysConfig CLI + gmake）/ `stm32`（UV4）——工单 04 把
  mspm0 那一轴并进来（原 `probe-03-compile-stm32.py`）。
* **形态**（票面点名的四类，见 `CASES` 的 `kind`）：一件都不选 / 只有自建件 /
  自建件 + 库内器件 / 全选……外加 03 留下的"三种定义形态"（只有地址 / 有寄存器
  无期望值 / 有寄存器 + 期望值 / 无输出通道）与几格**反向**形态（用户自己把
  `i2c_probe` 选上、自建件不是 I2C 件）：按需渲染那条验收线的交点正在这些格上。

mspm0 侧多证两件事（否则 `i2c_probe.c` 直接编不过，是 01 反证项证过的那条链）：
`I2C_0` 实例在裁剪后仍然活着（`I2C_0_INST` 存在），且探测代码里的 `DL_*` 一个
都不在 `main.c`（全在模块 `.c` 里——母版没有 `.h`，写进 main.c 实测被生成门禁
判未定义）。

**已知受限的两格**（矩阵如实记，但不为它们变红——都是**独立于本单**的既有限制，
各有自己的单）：
* `all-library` 在 mspm0 上让位到"装得下的最大子集"：一是板载 31 脚放不下十件
  （产品正确行为，页面会点名），二是**母版引脚符号重名**（`SCL`/`SDA` 一组 17 件）
  ——后者是工单 `11-mspm0-pin-name-collision`，最小复现里连自建件都不需要；
* 选了用堆的模块（`ml_mpu6050` 一族）时 TI 链接器给一条 `.sysmem` 提示，
  与本仓库代码无关（见 `_KNOWN_TOOLCHAIN_WARNINGS`），单独计数。

用法：`python .scratch/hwcheck-unknown-device/probe-03-compile-matrix.py [--out FILE] [--only NAME]`
**先落盘再打印**（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
产物落 `.scratch/hwcheck-unknown-device/matrix/`（gitignore），日志落 `matrix-logs/`。

跑一格的顺序（**错一步读数就假**）：

1. `hwcheck_view` 装配（引脚消解 / 自建件小节都在这一处）；
2. `generate_project(slugs=view.generation_slugs, bindings=view.pin_bindings)`——
   **产品端点调的就是这个函数**。探针早先自己 `resolve_dependencies` + `generate()`，
   漏掉引脚消解那一份增量，产物带着母版原脚去撞 PA22（本单实测 400）；
3. 编译（UV4 / gmake）；
4. **编译之后**才判 `Debug/ti_msp_dl_config.h` 与 `I2C_0_INST`——那个文件是
   SysConfig CLI 在编译那一步生成的，生成端点只摆 makefile。

告警分两栏：**我们代码的**（验收线 0 条）与**已知工具链的**（`.sysmem` 一次分配
提示，选了用堆的模块就有，与本仓库代码无关，见 `_KNOWN_TOOLCHAIN_WARNINGS`）——
混在一起会让验收线永远红在一个改不动的点上。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Sequence

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log,
    compile_passed,
    find_ccs_tools,
    find_make,
    find_uv4,
)
from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.generator import generate_project  # noqa: E402
from contest_generator.hwcheck import (  # noqa: E402
    HwCheckConfig,
    hwcheck_modules,
    render_main_c,
)
from contest_generator.hwcheck_board import hwcheck_view  # noqa: E402
from contest_generator.my_devices import (  # noqa: E402
    CustomDevice,
    my_devices_dir,
    save_device,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402

MODULES = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
MATRIX_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "matrix"
LOG_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "matrix-logs"
WORK_DIR = REPO / ".scratch" / "hwcheck-unknown-device" / "probe-03-data"
GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"

# 两个平台（一次跑完；`--only` 可按格名挑一格排查）
PLATFORMS = (PLATFORM_MSPM0, PLATFORM_STM32)

# 全选那一格用的库内器件（**按平台**，两边都是"检测页能选、这一平台真有实现"的
# 那一批）：
#
# * stm32 侧少了 sr04 / jy61p / xunji——它们**只有 mspm0 实现**，选进 stm32 会在
#   生成门禁那里大声失败（`MissingModuleFilesError`：「模块 sr04 没有平台 stm32 的
#   版本条目」）。那是产品正确行为（页面会点名哪几件本平台没有），不是这一格要
#   证的"能生成能编译"——探针的第一版把这三种混进 stm32，读数就成了假红。
# * mspm0 侧十件全上，再按同一份判据（`hwcheck_pin_plan`）逐件让位到装得下。
ALL_LIBRARY: dict[str, tuple[str, ...]] = {
    PLATFORM_MSPM0: (
        "led", "beep", "key", "adc", "ml_mpu6050", "oled", "debug_uart",
        "sr04", "jy61p", "xunji",
    ),
    PLATFORM_STM32: (
        "led", "beep", "key", "adc", "ml_mpu6050", "oled", "debug_uart",
    ),
}

# **已知工具链事实**（不是本仓库代码的告警，别把它读成缺陷）：
# `ml_mpu6050` 那一族用堆（`malloc`），TI 链接器于是开一个默认 0x800 的 .sysmem
# 段并提示 `#10210-D ... use the -heap option`。实测：同一份配置**去掉
# ml_mpu6050 就一条都没有**（`.scratch/hwcheck-unknown-device/tmp-diag-warn.py`），
# 与"有没有自建件"无关——所以它既不是这一单一句话能改的，也不该混进"我们代码的
# 告警数"里（改了 mspm0 母版的链接选项 = 跨平台共享面，另议）。
_KNOWN_TOOLCHAIN_WARNINGS = ("#10210-D",)


def _case(
    kind: str,
    *,
    devices: tuple[str, ...] = (),
    custom: tuple[CustomDevice, ...] = (),
    channel: bool = True,
):
    """一格的形态 → 一个**按平台取形态**的工厂。

    自建件是数据、不是模块（与平台无关），所以两平台的定义本来就是同一份——
    但接口留成工厂：将来某一格真要按平台分野（如"mspm0 上装不下"），改格子的
    地方只有一处，`CASES[name][platform]` 这个读取面不用动。
    """
    shape = {"kind": kind, "devices": devices, "custom": custom, "channel": channel}
    return {platform: dict(shape) for platform in PLATFORMS}


def _dev(device_id: str, name: str, address=None, register=None, expect=None, bus="i2c"):
    return CustomDevice(
        id=device_id, name=name, bus=bus, address=address,
        register=register, expect=expect, notes="编译探针用的一件",
    )


def _save_with_retry(root: Path, device: CustomDevice, attempts: int = 5):
    """`save_device` 整调用重试：矩阵在几分钟里连发几十次落盘，Windows 的
    实时扫描 / 索引器偶尔会把刚写完的暂存目录句柄占住一拍，原子改名撞
    `PermissionError [WinError 5]`（本机实测，两次矩阵各废在**不同格**上）。
    每次重试都是**完整的产品调用**（不是绕过校验的分步操作），失败仍如实抛。"""
    import time

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return save_device(root, device)
        except PermissionError as exc:
            last = exc
            time.sleep(0.5 * (attempt + 1))
    assert last is not None
    raise last


# 工单 12 的边界格用：**旧文法下建的**带连字符 id（建件端点已进不去，
# 只会以"盘上旧条目"的形态存在）
HYPHEN_ID = "mine_gyro-2"

# 边界格的 kind：生成/装载期被产品拦下是**正确行为**，读数如实记、不计入验收线
BOUNDARY_KINDS = frozenset({"all-recipes", "hyphen-id-refused"})


# 矩阵的格子（键 = 格名，值 = {平台: 形态}）。**格名出现在日志文件名与读数里**，
# 改名前先想清楚 03 已经发布过的那几个读数还认不认得出来。
CASES: dict[str, dict[str, dict]] = {
    # ---- 票面点名的四类形态 ----
    "empty": _case("empty"),                                    # 一件都不选
    "custom-only": _case("custom-only", custom=(                  # 只有自建件
        _dev("mine_judge", "有寄存器有期望值的库外件", 0x6A, 0x75, 0x68),
    )),
    # 自建件 + 库内器件（三个按需渲染开关 needs_hex / needs_verdict /
    # needs_probe_none 的交点正在这一格上：只跑"自建件单独"证不到）
    "custom+library": _case(
        "custom+library",
        devices=("led", "beep", "key", "ml_mpu6050"),
        custom=(_dev("mine_mixed", "与库内件同趟的库外件", 0x6B, 0x75, 0x68),),
    ),
    "all-library": _case("all-library", devices=ALL_LIBRARY[PLATFORM_MSPM0]),
    # 票面说的"全选"到底有多大：**检测页给得出的全部器件**（= 库内有本平台配方的
    # 那一批，不是手挑的十件）。这一格不设"装得下"的让位——它就是要在真实规模上
    # 量一次选中集的边界（读数如实记：装不下 / 母版重名各拦掉哪些）。
    "all-recipes": _case("all-recipes"),

    # ---- 03 留下的定义形态（三档文案各一格 + 无通道）----
    "shape1-ping-only": _case("shape", custom=(
        _dev("mine_ping", "只有地址的库外件", 0x68),
    )),
    "shape2-echo": _case("shape", custom=(
        _dev("mine_echo", "有寄存器无期望值的库外件", 0x69, 0x75),
    )),
    "shape3-judge": _case("shape", custom=(
        _dev("mine_judge", "有寄存器有期望值的库外件", 0x6A, 0x75, 0x68),
    )),
    "no-channel": _case("shape", channel=False, custom=(
        _dev("mine_nochan", "无输出通道形态的库外件", 0x6C, 0x75, 0x68),
    )),

    # ---- 反向形态（按需渲染 / 幂等那几条判据的交点）----
    # 用户自己把支点模块选上：产物里 `i2c_probe` 的头**只许印一遍**
    # （03 评审实测复现过的重复 include）
    "probe-already-selected": _case("reverse",
        devices=("i2c_probe",),
        custom=(_dev("mine_dedup", "支点模块也被选中的库外件", 0x6D, 0x75, 0x68),),
    ),
    # 非 I2C 自建件：**不生成探测程序**（清单与排障是后续工单的事），
    # 但它仍不是模块——补进模块集就会在生成链上游被拒
    "custom-not-i2c": _case("reverse", custom=(
        _dev("mine_spi", "SPI 的库外件（不该出探测小节）", None, None, None, bus="spi"),
    )),

    # ---- 工单 12 的边界格：id 文法收紧后的**盘上旧条目** ----
    # 带连字符的 id 在建件端点已进不去（工单 12 收紧文法），但**收紧之前**建的
    # 条目可能还躺在数据目录里。这一格把那样的条目**手工**写进数据目录（绕过
    # `save_device` 的校验，模拟"它是在旧文法下建的"），预期两平台的装载阶段
    # 都大声拦下（`MyDeviceError` 点名条目 + 指路）——到不了生成、更到不了编译。
    # 它与 `all-recipes` 同属**边界读数**（`BOUNDARY_KINDS`），不计入 0e/0w 验收线。
    "hyphen-id-refused": _case("hyphen-id-refused", devices=(HYPHEN_ID,)),
}


def _write_stale_hyphen_entry(root: Path) -> None:
    """把一件**旧文法下建的**带连字符条目手工写进数据目录（绕过 `save_device`）。

    `save_device` 会按现行文法校验（工单 12 起连字符直接 400），而这一格要模拟的
    恰恰是"它是在收紧之前建的"——所以按目录即数据库的落盘形状直接写文件。
    先清后写：两平台先后跑同一格，上一格留下的条目不能让下一格撞 `FileExistsError`
    （第一版就是这么把 stm32 那格的读数从 `MyDeviceError` 污染成探针自己的异常的）。
    """
    entry = root / HYPHEN_ID
    if entry.exists():
        shutil.rmtree(entry)
    (entry / "materials").mkdir(parents=True)
    (entry / "device.json").write_text(
        json.dumps(
            {"id": HYPHEN_ID, "name": "旧文法下建的库外件", "bus": "i2c", "address": 0x68}
        ),
        encoding="utf-8",
    )


def build_case(name: str, platform: str) -> tuple[Path, str, tuple[str, ...], list[str]]:
    """按真路径生成一个检测工程（返回目录、main.c、生成用的 slug 集、收敛说明）。

    ⚠ `all-recipes` 那一格**预期**在生成期就被产品拦下（下面 `main` 里按 `kind`
    认它）：它不是验收格，是"全选到底有多大、产品怎么答"的边界读数。
    """
    case = CASES[name][platform]
    # 起手先清上一格可能留下的坏条目：`hyphen-id-refused` 把带连字符的旧条目
    # 手工写进数据目录，而 `hwcheck_view` 装载时 `list_devices` **全量**读目录——
    # 条目若还在，后面任何一格都会在装载期假红（评审 🟡 抓到的位置隐式依赖，
    # 修成与格顺序无关）
    stale = my_devices_dir(WORK_DIR) / HYPHEN_ID
    if stale.exists():
        shutil.rmtree(stale)
    devices = tuple(case["devices"])
    notes: list[str] = []
    if case["kind"] == "all-library":
        devices, notes = _largest_that_fits(platform, ALL_LIBRARY[platform])
    elif case["kind"] == "all-recipes":
        devices = _recipe_devices(platform)
        notes.append(
            f"全选规模：{len(devices)} 件（检测页给得出的全部——库内有 {platform} "
            "配方的那些，不设让位）"
        )
    devices = devices + tuple(d.id for d in case["custom"])
    if case["kind"] == "hyphen-id-refused":
        _write_stale_hyphen_entry(my_devices_dir(WORK_DIR))
        notes.append(
            f"盘上旧条目（旧文法下建的 id）{HYPHEN_ID!r} 已手工落进数据目录"
            "——预期装载期大声拦下"
        )
    config = HwCheckConfig(
        platform=platform,
        debug_uart=case["channel"],
        oled=case["channel"],
        devices=devices,
    )
    # 自建件先落进（临时的）数据目录——判据只读那里的数据，不玩内存特例。
    # 落点是 `my_devices_dir(data_dir)`（`<数据目录>/hwcheck_devices/`），与
    # `hwcheck_view(data_dir=…)` 读的那个目录**同一个推导**（写这儿读那儿）。
    for device in case["custom"]:
        _save_with_retry(my_devices_dir(WORK_DIR), device)
    view = hwcheck_view(
        config,
        module_library_dir=MODULES,
        masters_dir=MASTERS,
        data_dir=WORK_DIR,
    )
    main_c = render_main_c(config, view.sections, view.generic, view.custom)
    out = MATRIX_DIR / f"custom-{name}-{platform}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    # **走产品那一条路**：`hwcheck_generate` 端点在 webapp 里调的就是
    # `generate_project(slugs=…, bindings=…)`。探针早先自己 `resolve_dependencies`
    # 展开再调 `generate()`，于是漏掉了 `view.pin_bindings`（检测页在生成前自动
    # 移开的那几根线）——产物带着母版原脚去撞 PA22，400。手推一遍就是第二个
    # 真相源：slugs / 引脚消解 / 上下文清单三件事产品都替我们算好了。
    generate_project(
        platform=platform,
        slugs=view.generation_slugs,
        main_c_content=main_c,
        output_dir=out,
        module_library_dir=MODULES,
        masters_dir=MASTERS,
        ccs_tools=find_ccs_tools() if platform == PLATFORM_MSPM0 else None,
        bindings=view.pin_bindings or None,
        devices=devices,
    )
    return out, main_c, tuple(view.generation_slugs), notes


def _largest_that_fits(platform: str, candidates: Sequence[str]) -> tuple[tuple[str, ...], list[str]]:
    """「全选」格：候选集里**装得下的最大子集**（逐个让位，如实记账）。

    两条让位判据，顺序固定：

    1. **引脚符号重名的组**（mspm0 独有）：同一批里出现 `SCL`/`SDA` 这类同名引脚
       符号，SysConfig 直接 `Duplicate name` 报错。这条**独立于本单**，已由工单 11
       修成"生成前拦下"（`.scratch/hwcheck-unknown-device/issues/
       11-mspm0-pin-name-collision.md`）。这一格不为它变红（那会把 04 的验收线绑在
       别处的判据上），但也不假装没这回事：让位清单里点名，读数里可见；
    2. **装不下**（板载脚不够 / 改绑解不开）：走产品同一条判据
       （`hwcheck_pin_plan`，页面上那条 400 的判据），逐件让位到 `plan.ok`。

    为什么不做成"把这十件全塞进去"：地猛星上物理装不下（13 个模块 36 个落点 >
    板载 31 脚，实测 5 组冲突改绑解不开）——那是**产品正确行为**（页面上会点名
    该去掉哪几件），不是这一格要证的"能生成能编译"。

    顺序敏感（先来的先留）是刻意的：这让人一眼看出"最坏的那一版"长什么样，而
    探针要的是一个**稳定可复现**的形态，不是"最优选择"。
    """
    from contest_generator.boards import board_for_platform
    from contest_generator.hwcheck_board import hwcheck_pin_plan, read_master_syscfg
    from contest_generator.library import list_modules
    from contest_generator.selection import resolve_dependencies

    board = board_for_platform(platform)
    master_syscfg = read_master_syscfg(MASTERS, platform)
    by_slug = {m.slug: m for m in list_modules(MODULES)}
    notes: list[str] = []
    kept = list(candidates)

    collisions = _pin_symbol_collisions(master_syscfg)
    if collisions:
        # 组内只留第一件（其余让位）：让位清单连同"因为哪一条"一起记账
        dropped_pairs: list[str] = []
        for group in collisions:
            present = [slug for slug in kept if slug in group]
            for slug in present[1:]:
                kept.remove(slug)
                dropped_pairs.append(f"{slug}（与 {present[0]} 同名）")
        if dropped_pairs:
            notes.append(
                "引脚符号重名让位（工单 11；该单已把这类组合改成生成前拦下，"
                "矩阵仍按最小子集取材）："
                + "、".join(dropped_pairs)
            )

    dropped: list[str] = []
    while kept:
        manifests = resolve_dependencies(kept, by_slug)
        plan = hwcheck_pin_plan(platform, manifests, board, master_syscfg)
        if plan.ok:
            break
        dropped.append(kept.pop())       # 让位：从最后一件开始（顺序敏感，见 docstring）
    if dropped:
        notes.append(
            f"装不下让位：{'、'.join(dropped)}（原候选 {len(candidates)} 件，"
            f"留下这一格自己选的 {len(kept)} 件）"
        )
    return tuple(kept), notes


def _recipe_devices(platform: str) -> tuple[str, ...]:
    """**检测页给得出的全部器件** = 库内有本平台配方的那些（判据单源：配方文件）。

    为什么用它当"全选"的口径：检测页的器件池就是这么来的（`/api/hwcheck/preview`
    的 `devices` 面 = 有配方的 slug），不是"整库 87 件"，也不是手挑的十件。
    """
    import json

    recipes = json.loads(
        (REPO / "library" / "hwcheck_recipes.json").read_text(encoding="utf-8")
    )
    return tuple(
        slug for slug, entry in recipes.items()
        if not slug.startswith("_") and isinstance(entry, dict) and platform in entry
    )


def _pin_symbol_collisions(master_syscfg: str | None) -> list[frozenset[str]]:
    """母版 syscfg 里**同名引脚符号**的**实例组**（判据 = `associatedPins[n].$name`）。

    为什么单独判：`syscfg_pin_conflict_report` 判的是"同一个脚被两个实例占用"
    （`$assign` 的 pin 值重复），**不判引脚符号重名**——SysConfig 对 `$name` 另有
    一条全局唯一约束，撞上直接 `Duplicate name: 'SCL'`。两者是不同轴，工单 11 管
    前者没覆盖到的那一半。

    返回的是**实例名组**（`SR04` / `OLED_SPI` 这类），由 `.associatedPins[n]` 的
    路径前缀得到；实例名 → 模块 slug 的映射交给 `INSTANCE_CONSUMERS`（本仓库那
    份单源），本函数只做文本解析、不猜哪件是哪个模块。
    """
    if not master_syscfg:
        return []
    from contest_generator.syscfg_instances import INSTANCE_CONSUMERS

    slug_of: dict[str, str] = {}
    for instance, slugs in INSTANCE_CONSUMERS.items():
        for slug in slugs:
            slug_of.setdefault(instance, slug)
    names: dict[str, set[str]] = {}
    for line in master_syscfg.splitlines():
        text = line.strip()
        if not text.endswith(";") or ".$name" not in text or "=" not in text:
            continue
        path, value = text[:-1].split("=", 1)
        if ".associatedPins[" not in path:
            continue
        instance = slug_of.get(path.split(".associatedPins")[0])
        if instance:
            names.setdefault(value.strip().strip('"'), set()).add(instance)
    return [frozenset(instances) for instances in names.values() if len(instances) > 1]


def split_warnings(output: str) -> tuple[list[str], list[str]]:
    """告警行 →（我们代码的, 已知工具链的）。

    **排除工具汇总行**：`0 Error(s), 0 Warning(s).` 自己就含 `warning` 子串
    （本单第一版就是这么把 0 告警读成 1 条的）。
    **已知工具链那一条另算**（见 `_KNOWN_TOOLCHAIN_WARNINGS`）：它由 TI 链接器
    在"选了用堆的模块"时发出、与本仓库代码无关——混在一起会让"0 warning"这条
    验收线永远红在一个改不动的点上，而分开记既保住了验收线，又没把它藏起来。
    """
    ours: list[str] = []
    known: list[str] = []
    for line in output.splitlines():
        low = line.lower()
        if "warning" not in low or "warning(s)" in low:
            continue
        target = known if any(code in line for code in _KNOWN_TOOLCHAIN_WARNINGS) else ours
        target.append(line)
    return ours, known


def check_shape(name: str, case: dict, main_c: str, slugs: tuple[str, ...]) -> list[str]:
    """产物形态判据（**与编译无关**的那几条，编译前先判一次）。

    这些都是"编译绿 ≠ 做对了"的那一类：无通道形态不该有自建件字样、非 I2C 件
    不该出小节、产物不许出现引脚 / 实例字面量（`mspm0` 上连 `I2C_0_INST` 都不许
    出现在 main.c —— 那是模块 `.c` 的事）。

    ⚠ 判据用 `clex.strip_comments` 剥掉注释与字符串（生成门禁同款口径）：注释里
    提一句脚名**不是**缺陷，生成门禁也正是这么判的。探针第一版按裸文本扫，把
    `I2C_PROBE_SCL PA6` 这种"宏名 + 人读标签"误报成引脚字面量——量具比产品严，
    读数就没人信了。
    """
    problems: list[str] = []
    has_custom = bool(case["custom"])
    code = strip_comments(main_c)
    if not case["channel"]:
        if "hwcheck_custom_" in code:
            problems.append("无输出通道形态不该有自建件小节")
        if "i2c_probe" in code:
            problems.append("无输出通道形态不该带支点模块")
    if case["kind"] == "reverse" and not case["devices"] and has_custom:
        if "hwcheck_custom_" in code:
            problems.append("非 I2C 自建件不该出探测小节")
    for literal in ("PA0", "PA1", "PA6", "PA7", "Pin_", "I2C_0_INST", "GPIOA"):
        if literal in code:
            problems.append(f"代码里出现了引脚 / 实例字面量 {literal}")
    if not has_custom and "hwcheck_custom_" in code:
        problems.append("这一格没有自建件，产物里却有小节")
    expected = "i2c_probe" in slugs
    if expected != ("i2c_probe" in code):
        problems.append(
            "生成 slug 集与产物不一致："
            f"slug 里有 i2c_probe={expected}，产物里={('i2c_probe' in code)}"
        )
    return problems


def check_mspm0(out: Path, main_c: str, slugs: tuple[str, ...]) -> list[str]:
    """mspm0 特有的三条（工单 04 验收项 1 与 2）。

    1. **`main.c` 一个字都不直接调 SDK**：母版没有 `.h`，`DL_*` 写进 main.c 会
       被生成门禁判未定义（本机实测），所以这一条是"04 的分工"那条验收项的判据。
       注释里提到 `SYSCFG_DL_init()` 不算（那是平台说明，不是调用）——故先剥注释；
    2. **选中 `i2c_probe` 时 `I2C_0` 实例必须活着**：判据在
       `Debug/ti_msp_dl_config.h`（SysConfig 的真产物）里有 `I2C_0_INST`
       ——裁剪判据是"消费者 ∩ 选中集"，本件被裁掉时这里就没有它，
       `i2c_probe.c` 直接编不过；
    3. **没选中它时反过来**：`I2C_0` 该被裁掉（不然"实例随选中集走"这条不变量
       就没在验——两侧都判才叫判据）。

    ⚠ 本函数必须在**编译之后**调：`Debug/ti_msp_dl_config.h` 是 SysConfig CLI
    在编译那一步生成的（`Debug/makefile` 的第一条规则），生成端点只摆好 makefile。
    """
    problems: list[str] = []
    for bad in ("DL_I2C", "DL_GPIO", "DL_Timer", "SYSCFG_DL_init"):
        if bad in strip_comments(main_c):
            problems.append(f"main.c 里出现了 SDK 调用 {bad}（该封在模块 .c 里）")
    config_h = out / "Debug" / "ti_msp_dl_config.h"
    if not config_h.is_file():
        problems.append("没生成 Debug/ti_msp_dl_config.h（SysConfig 那一步没跑？）")
        return problems
    # `I2C_0` 的存活判据 = **它的消费者 ∩ 选中集**（不是"选了 i2c_probe 吗"：
    # ml_mpu6050 也是它的消费者，那条路早就在跑）。两侧都判——选了却不在 = 支点
    # 被裁掉；没选却还在 = 裁剪没随选中集走。
    from contest_generator.syscfg_instances import INSTANCE_CONSUMERS

    consumers = set(INSTANCE_CONSUMERS.get("I2C_0", ()))
    expected = bool(consumers & set(slugs))
    present = "I2C_0_INST" in config_h.read_text(encoding="utf-8", errors="replace")
    who = "、".join(sorted(consumers & set(slugs))) or "（无）"
    if expected and not present:
        problems.append(f"选中了 I2C_0 的消费者（{who}）却 I2C_0_INST 不在配置头里")
    if not expected and present:
        problems.append("没选中任何 I2C_0 消费者却 I2C_0_INST 还在（实例没随选中集裁掉）")
    return problems


def run_case(name: str, platform: str) -> tuple[bool, list[str]]:
    """跑一格：生成 → 形态判据 → 真编译 → **编译后**的产物判据 → 读数行。

    ⚠ 顺序有讲究：`check_mspm0` 读的 `Debug/ti_msp_dl_config.h` 是 **SysConfig
    在编译那一步**生成的（`Debug/makefile` 里 SysConfig CLI 是第一条规则），
    生成端点只摆好 makefile。把它放在编译前判，永远读到"文件不在"——第一版
    就是这么假红的。
    """
    case = CASES[name][platform]
    lines: list[str] = []
    out, main_c, slugs, notes = build_case(name, platform)
    problems = check_shape(name, case, main_c, slugs)
    log = collect_build_log(
        platform, out,
        uv4=find_uv4() if platform == PLATFORM_STM32 else None,
        make=find_make(GMAKE) if platform == PLATFORM_MSPM0 else None,
        timeout=600,
    )
    ok = compile_passed(platform, log.run.exit_code)
    warnings, known_warnings = split_warnings(log.run.output)
    if platform == PLATFORM_MSPM0:
        problems.extend(check_mspm0(out, main_c, slugs))
    (LOG_DIR / f"custom-{name}-{platform}.log").write_text(
        f"exit_code={log.run.exit_code}\ncompile_passed={ok}\n"
        f"device_slugs={list(slugs)}\nnotes={notes}\n"
        f"warnings_ours={len(warnings)}\n"
        f"warnings_known_toolchain={len(known_warnings)}\n\n{log.run.output}",
        encoding="utf-8",
    )
    lines.append(
        f"[custom/{platform}/{name}] exit={log.run.exit_code} passed={ok} "
        f"warnings={len(warnings)} devices={len(slugs)}"
        + (f"（另有已知工具链 {len(known_warnings)} 条）" if known_warnings else "")
    )
    for note in notes:
        lines.append("    · " + note)
    for warning in known_warnings[:2]:
        lines.append("    (已知工具链) " + warning.strip()[:150])
    for warning in warnings[:8]:
        lines.append("    " + warning.strip()[:160])
    for problem in problems:
        lines.append("    ✗ 形态：" + problem)
    return (ok and not warnings and not problems), lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8，先落盘再打印）")
    parser.add_argument("--only", default="", help="只跑某一格（格名子串，排查用）")
    args = parser.parse_args()

    names = [n for n in CASES if not args.only or args.only in n]
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    ok_all = True

    for name in names:
        for platform in PLATFORMS:
            try:
                ok, block = run_case(name, platform)
            except Exception as exc:  # 生成期失败也算不通过，如实记录
                # **边界格**（`BOUNDARY_KINDS`，不是验收格）：生成 / 装载期被产品
                # 拦下是**正确行为**——`all-recipes` 是引脚装不下 → 400 点名哪几件，
                # `hyphen-id-refused` 是盘上旧坏条目 → 装载期点名（工单 12）。这里
                # 如实记读数、不计入验收线。判据仍是"产品有没有拦"——异常被换成
                # 一个"生成了但编不过"的产物才是缺陷。
                boundary = CASES[name][platform]["kind"] in BOUNDARY_KINDS
                ok = boundary
                detail = str(exc).splitlines()
                block = [
                    f"[custom/{platform}/{name}] "
                    + ("产品按预期在生成前拦下（边界读数，不计入验收线）"
                       if boundary else "生成期异常")
                    + f"：{type(exc).__name__}"
                ] + [f"    {line.strip()[:160]}" for line in detail[:6]]
            lines.extend(block)
            ok_all = ok_all and ok

    lines.append("")
    lines.append(
        f"=== 结果：{'全部 PASS（0 error / 0 warning）' if ok_all else '有 FAIL'} "
        f"===（{len(names)} 格 × {len(PLATFORMS)} 平台）"
    )
    report = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")   # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
