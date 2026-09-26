# -*- coding: utf-8 -*-
"""硬件检测：库内配方机制（工单 module-hwcheck/04）。

**为什么这样测**：配方是"每一件怎么测"的数据，而检测程序的判据是
「不假装测过」——所以本文件只钉两件事：

1. **引用必须真实**：配方里出现的函数名必须在**该模块该平台的头文件**里，
   找不到 = 构建期大声失败（`HwCheckError` 中文点名），**绝不学骨架兜底把它
   改成注释**（骨架的 sanitize 是给 LLM 幻觉用的，配方是人写的库内数据，
   写错了就该当场红）。
2. **库内数据不缩水**：真实库的 pilot 清单（led / oled × 两平台）每一格都
   必须真有配方，能渲染出小节——地板断言，防"配方悄悄少了一格没人发现"。

渲染侧的判据（文本结构 / 零 LLM）在 `tests/test_hwcheck.py`（同一个域层，
同一套缝）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from contest_generator.hwcheck import HWCHECK_CHANNELS, HwCheckError
from contest_generator.hwcheck_recipe import (
    RECIPE_FILENAME,
    RecipeCatalog,
    RecipeConsole,
    RecipeProbe,
    RecipeRead,
    RecipeSection,
    c_string,
    escape_c_string,
    load_recipes,
    local_names,
    parse_recipes,
    recipe_library_path,
    render_recipe_section,
    render_recipe_summary,
    resolve_sections,
    sections_payload,
)
from contest_generator.manifest import ModuleManifest
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from tests._c_escape import decode_c_string

REAL_LIBRARY = Path(__file__).resolve().parents[1] / "library" / "modules"
REAL_MASTERS = Path(__file__).resolve().parents[1] / "library" / "masters"

# 多实例格的如实自述（工单 hwcheck-hygiene/07）——判据与数据共用的两个串。
# `_MULTI_INSTANCE_MARKER` = 学生必须看到的那一层意思（判据只认这两个字，
# **不许**把断言放松成"含『通道』就行"，那句话已经在页面上、正是误导的来源）；
# `_MULTI_INSTANCE_PHRASE` = 本单写的整句开头（用来定位"这一句"，
# 好把它与存量 354 条带 markdown 标记的 note 分开判）。
# 三者（数据 / 判据 / 报错话术）现在说的是同一件事；上一版报错里写"「首通道」也算数"
# 而判据只认"第一路"，是双轴评审抓到的一处自相矛盾。
_MULTI_INSTANCE_MARKER = "第一路"
_MULTI_INSTANCE_PHRASE = "多实例只验"

# 真实库的 pilot 清单（spec「v1 专精范围」）——地板断言的判据。
# 工单 05 起加上 ml_mpu6050 × 两个平台（**平台不对称**：stm32 只有原始六轴、
# mspm0 走官方 DMP 出角度）；工单 09 起把 v1 清单**补齐并全部钉死**（10 件 /
# 17 格）——少任何一格当场红，防"配方悄悄少了一格没人发现"。
# 单平台件（sr04 / jy61p / xunji 只有 mspm0 条目）按库内实况只列有条目那一格：
# 给它们补 stm32 格反而会被 `validate_recipes` 判红（该平台没有条目）。
PILOT = (("led", PLATFORM_STM32), ("led", PLATFORM_MSPM0),
         ("oled", PLATFORM_STM32), ("oled", PLATFORM_MSPM0),
         ("debug_uart", PLATFORM_STM32), ("debug_uart", PLATFORM_MSPM0),
         ("key", PLATFORM_STM32), ("key", PLATFORM_MSPM0),
         ("beep", PLATFORM_STM32), ("beep", PLATFORM_MSPM0),
         ("sr04", PLATFORM_MSPM0),
         ("jy61p", PLATFORM_MSPM0),
         ("xunji", PLATFORM_MSPM0),
         ("adc", PLATFORM_STM32), ("adc", PLATFORM_MSPM0),
         ("ml_mpu6050", PLATFORM_STM32), ("ml_mpu6050", PLATFORM_MSPM0))

# **专精面扩张**（spec `.scratch/hwcheck-specialize/`）：v1 清单之外**逐批**长出来的格。
# 与 `PILOT` 分工：`PILOT` 钉的是「v1 清单不许改小」（等号断言 17 格，**一个字都不许动**），
# 这一条钉的是「扩张成果不许悄悄缩水」——每落一批就在这里追加那几格，并把下面的
# `EXPANSION_CELL_COUNT` 一起改大（**条数精确**：少一格当场红，防"删一格没人发现"）。
#
# 每批落地时**只追加、不改写**已有的行（改写等于把上一批的成果从地板里抹掉）。
# 两个数各有各的用处，别混：`len(EXPANSION)` = **扩张部分自己的格数**；
# `len(PILOT) + len(EXPANSION)` = 配方文件里应有的**总覆盖格数**。
#
#   批次 A（工单 03）aht10 / sht20 / sht30 × 2 平台        → 扩张 6，总 23
#   批次 B（工单 04）bh1750 / bmp180 / ms5611 × 2 平台     → 扩张 12，总 29
#   批次 C（工单 05）hmc5883l / qmc5883l / tcs34725 × 2    → 扩张 18，总 35
#   批次 D（工单 06）mlx90614 / sgp30 / at24c02 × 2        → 扩张 24，总 41
#   批次 E（工单 07）ads1115 / pca9685 / dht11 / ds18b20   → 扩张 32，总 49
#   批次 F（工单 08）hx711 / joystick / servo / relay      → 扩张 40，总 57
EXPANSION = (("aht10", PLATFORM_STM32), ("aht10", PLATFORM_MSPM0),
             ("sht20", PLATFORM_STM32), ("sht20", PLATFORM_MSPM0),
             ("sht30", PLATFORM_STM32), ("sht30", PLATFORM_MSPM0),
             ("bh1750", PLATFORM_STM32), ("bh1750", PLATFORM_MSPM0),
             ("bmp180", PLATFORM_STM32), ("bmp180", PLATFORM_MSPM0),
             ("ms5611", PLATFORM_STM32), ("ms5611", PLATFORM_MSPM0),
             ("hmc5883l", PLATFORM_STM32), ("hmc5883l", PLATFORM_MSPM0),
             ("qmc5883l", PLATFORM_STM32), ("qmc5883l", PLATFORM_MSPM0),
             ("tcs34725", PLATFORM_STM32), ("tcs34725", PLATFORM_MSPM0),
             ("mlx90614", PLATFORM_STM32), ("mlx90614", PLATFORM_MSPM0),
             ("sgp30", PLATFORM_STM32), ("sgp30", PLATFORM_MSPM0),
             ("at24c02", PLATFORM_STM32), ("at24c02", PLATFORM_MSPM0),
             ("ads1115", PLATFORM_STM32), ("ads1115", PLATFORM_MSPM0),
             ("pca9685", PLATFORM_STM32), ("pca9685", PLATFORM_MSPM0),
             ("dht11", PLATFORM_STM32), ("dht11", PLATFORM_MSPM0),
             ("ds18b20", PLATFORM_STM32), ("ds18b20", PLATFORM_MSPM0),
             ("hx711", PLATFORM_STM32), ("hx711", PLATFORM_MSPM0),
             ("joystick", PLATFORM_STM32), ("joystick", PLATFORM_MSPM0),
             ("servo", PLATFORM_STM32), ("servo", PLATFORM_MSPM0),
             ("relay", PLATFORM_STM32), ("relay", PLATFORM_MSPM0))

# 扩张清单的**精确条数**（= `len(EXPANSION)`；每批长一次：追加了几格就改成几）。
# 判据不是"至少"，是"就是这么多"——有人悄悄删一行 `EXPANSION`，逐格断言就少跑一格、
# 静默放行。⚠ 这一条与逐格断言**都读同一个常量**：连"删一行 + 删配方那一格 + 把这里的
# 数字改小"三处一起动仍然会全绿（`PILOT` 当年正是为这个洞加了按**配方文件实数**判的
# 第三条地板）；本 spec 明说既有的文件级下限断言（`>= 17` 格 / `>= 10` 件）属 v1 那 17 格、
# **不改**，所以这条残留的洞如实记在这里，不靠措辞掩盖。
EXPANSION_CELL_COUNT = 40


def _unescape_c(code: str) -> str:
    """渲染产物 → 人能读的文本（把 ASCII 转义还原成字符）。

    渲染器把非 ASCII 转义成 UTF-8 字节（ARMCC 的本地代码页会把原样中文串的
    收尾引号吞掉），所以断言"程序里说了什么"时先把转义还原——**判据是"学生
    看到的那句话在不在"**，不是"转义写法对不对"（转义写法本身另有专门断言）。

    解码器本体单源在 `tests/_c_escape.py`（工单 05 起两个测试文件共用）。
    """
    return decode_c_string(code)


def _section(**overrides) -> dict:
    """一条合法配方的最小形态（测试里按需覆盖字段）。

    段的形状统一是对象（`{calls: [...]}` / `{expressions: [...]}` /
    `{lines: [...]}`）——显式键让"这一段的这一项叫什么"在文件里看得见。
    """
    data = {
        "locals": None,
        "prereq": {"calls": []},
        "init": {"calls": ["led_init(LED_RED)"]},
        "init_expect": "0",
        "probe": None,
        "read": {"expressions": ["LED_CHANNEL_COUNT"]},
        "console": None,
        "note": {"lines": ["测试用配方"]},
    }
    data.update(overrides)
    return data


def _document(*sections: tuple[str, str, dict]) -> dict:
    """配方文件形态：{slug: {platform: section}}。"""
    doc: dict = {}
    for slug, platform, data in sections:
        doc.setdefault(slug, {})[platform] = data
    return doc


# ---------------------------------------------------------------------------
# 落点：库根中央文件，跟随模块库根、不新增配置键
# ---------------------------------------------------------------------------


def test_recipe_file_lives_beside_the_module_library_root(tmp_path):
    """配方文件 = 模块库根的**平级兄弟**（与 topics / references 同款布局）。

    规格要求「跟随模块库根、不新增配置键」：模块库根是 `<库根>/modules`，
    配方就落在 `<库根>/hwcheck_recipes.json`——用户换库位置时它自动跟着走。
    """
    library_root = tmp_path / "library"
    modules = library_root / "modules"
    modules.mkdir(parents=True)
    assert recipe_library_path(modules) == library_root / RECIPE_FILENAME
    assert RECIPE_FILENAME == "hwcheck_recipes.json"


# ---------------------------------------------------------------------------
# 加载校验①：形状（六段 + 值类型），任一处不合法 = 中文大声失败
# ---------------------------------------------------------------------------


def test_parse_accepts_the_documented_six_segments():
    """六段齐备的一条配方解析成 RecipeSection（缺段 = 该件不支持该项）。"""
    recipes = parse_recipes(_document(("led", PLATFORM_STM32, _section())))
    section = recipes["led"][PLATFORM_STM32]
    assert isinstance(section, RecipeSection)
    assert section.slug == "led"
    assert section.platform == PLATFORM_STM32
    assert section.init == ("led_init(LED_RED)",)
    assert section.init_expect == "0"
    assert section.probe is None
    assert section.read == (RecipeRead(expression="LED_CHANNEL_COUNT"),)
    assert section.console is None
    assert section.note == ("测试用配方",)


def test_parse_reads_the_probe_and_console_segments():
    """探头段（调用 + 期望）与控制台段（命令字符 + 说明）的形状。"""
    recipes = parse_recipes(
        _document((
            "ml_mpu6050", PLATFORM_STM32,
            _section(
                init={"calls": ["mpu6050_init()"]}, init_expect="0",
                probe={"calls": ["mpu6050_read_id()"], "expect": "0x68"},
                console={"command": "m", "description": "复测 MPU6050"},
            ),
        ))
    )
    section = recipes["ml_mpu6050"][PLATFORM_STM32]
    assert section.probe is not None
    assert section.probe.calls == ("mpu6050_read_id()",)
    assert section.probe.expect == "0x68"
    assert section.console == RecipeConsole(command="m", description="复测 MPU6050")


def test_sections_payload_reports_the_assigned_console_character():
    """页面上的"敲哪个字符"必须是**分配后**的字符（工单 hwcheck-specialize/01）。

    配方里写的首选只是"想用哪个"：两件都想用 `l` 时，第二件会被分到候选字符。
    小节载荷若照抄首选，页面就会出现两件都写着"敲 l 复测"——一件真、一件假，
    而这正是"页面与板上读同一张表"要挡的错位。
    """
    from contest_generator.hwcheck_console import build_console_table

    sections = (
        RecipeSection(slug="led", platform=PLATFORM_STM32,
                      init=("led_init(LED_RED)",),
                      console=RecipeConsole("l", "复测 LED")),
        RecipeSection(slug="sht20", platform=PLATFORM_STM32,
                      init=("sht20_init()",),
                      console=RecipeConsole("l", "复测 SHT20", ("t",))),
    )
    table = build_console_table(sections)
    assigned = {entry.slug: entry.command for entry in table.entries}
    payload = {
        item["slug"]: item["console"]
        for item in sections_payload(sections, commands=assigned)
    }
    assert payload["led"]["command"] == "l"
    assert payload["sht20"]["command"] == "t", "让位后的字符才是页面上该敲的那一个"
    assert payload["sht20"]["description"] == "复测 SHT20"
    # 不给分配结果 = 照旧读配方首选（老调用方零改动，判据仍只有一处）
    assert [item["console"]["command"] for item in sections_payload(sections)] == ["l", "l"]


def test_parse_reads_the_candidate_characters_of_a_console_command():
    """`console` 段可以声明**候选字符**（工单 hwcheck-specialize/01）。

    首选（`console.command`）是"这一件最想用的字符"，候选是"首选被别的器件占了
    时按顺序让位到哪几个"——所以解析必须**保序**（让位顺序就是声明顺序），并且
    只判形状、不判"这个字符库内让不让用"（命令空间归 `hwcheck_console`，
    配方这一层不必知道库内既有命令叫什么）。
    """
    recipes = parse_recipes(_document((
        "sht20", PLATFORM_STM32,
        _section(console={"command": "t", "candidates": ["w", "z"],
                          "description": "复测 SHT20"}),
    )))
    assert recipes["sht20"][PLATFORM_STM32].console == RecipeConsole(
        command="t", description="复测 SHT20", candidates=("w", "z"))


def test_parse_keeps_old_recipes_candidate_free():
    """不带候选的老配方解析结果**逐字不变**（`candidates` 缺省 = 空元组）。

    向后兼容是这一单的硬要求：库内 17 格老配方一个字节都不用改。
    """
    recipes = parse_recipes(_document((
        "led", PLATFORM_STM32, _section(console={"command": "l", "description": "复测 LED"}),
    )))
    assert recipes["led"][PLATFORM_STM32].console == RecipeConsole(
        command="l", description="复测 LED")


@pytest.mark.parametrize(
    "candidates",
    ["wz", ["wz"], [""], [1], [None]],
)
def test_parse_rejects_a_malformed_candidate_list(candidates):
    """候选字符的形状判据与首选同款：**单个字符**，数组，不许静默丢。

    `[""]` 这类空串若被静默丢掉，"写了候选却一直不生效"就会变成一条查不出来的
    怪现象（学生只看到反复撞车）；点名字段才是能改得动的报错。
    """
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(_document((
            "sht20", PLATFORM_STM32,
            _section(console={"command": "t", "candidates": candidates,
                              "description": "复测 SHT20"}),
        )))
    assert "console.candidates" in str(exc.value)


@pytest.mark.parametrize("bad", [None, [], "not-an-object", 42])
def test_parse_rejects_a_non_object_document(bad):
    """配方文件本身必须是对象——数组 / 标量 = 库内数据坏，中文大声失败。"""
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(bad)
    assert RECIPE_FILENAME in str(exc.value)


@pytest.mark.parametrize(
    "section, bad_field",
    [
        (_section(init="led_init(LED_RED)"), "init.calls"),
        (_section(prereq="i2c_init()"), "prereq.calls"),
        (_section(read="LED_CHANNEL_COUNT"), "read.expressions"),
        (_section(read={"items": "nope"}), "read.items"),
        (_section(note="一句话"), "note.lines"),
        (_section(console={"command": "mm"}), "console.command"),
        (_section(console={"command": ""}), "console.command"),
    ],
)
def test_parse_rejects_wrongly_typed_segments(section, bad_field):
    """值类型错了要**点名到字段**（不静默强转——强转会让"命令字符写成两个
    字符"这种错一路走到板上）。"""
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(_document(("led", PLATFORM_STM32, section)))
    assert bad_field in str(exc.value)


def test_parse_rejects_an_unknown_platform_key():
    """平台键必须在词表内——`stm33` 这类手滑不许静默变成"这个平台没配方"。"""
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(_document(("led", "stm33", _section())))
    assert "stm33" in str(exc.value)


def test_parse_rejects_an_empty_recipe():
    """六段全空的配方 = 空壳：它不是"专精"，会让学生以为这件被测过。"""
    empty = {"prereq": {"calls": []}, "init": {"calls": []}, "init_expect": "",
             "probe": None, "read": {"expressions": []}, "console": None,
             "note": {"lines": []}}
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(_document(("led", PLATFORM_STM32, empty)))
    assert "led" in str(exc.value)


def test_parse_requires_an_expect_when_the_init_is_checked():
    """`init_expect` 有值 = 要判返回值；此时 init 不能为空（判谁？）。"""
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(_document((
            "led", PLATFORM_STM32,
            _section(init={"calls": []}, init_expect="0"))))
    assert "init" in str(exc.value)


def test_parse_accepts_a_probe_that_only_acts_without_a_verdict():
    """探头段可以**只做动作不判通断**（expect 缺省）——如实一点，不假装。

    纯输出件（OLED 屏）没有可读的状态寄存器：探头能做的是"让屏上出现一行
    字"（肉眼现象），判不出 OK/FAIL。这一形态合法，但渲染时**不打判定**
    （`hwcheck_verdict_probe_none`），期末汇总里不算通过。
    """
    recipes = parse_recipes(_document((
        "oled", PLATFORM_MSPM0,
        _section(probe={"calls": ["OLED_ShowString(0, 0, \"OLED OK\", 16)"]}))))
    probe = recipes["oled"][PLATFORM_MSPM0].probe
    assert probe is not None
    assert probe.calls == ('OLED_ShowString(0, 0, "OLED OK", 16)',)
    assert probe.expect == ""


def test_parse_rejects_a_probe_with_a_bad_expect_type():
    """写了 expect 就必须是字符串——数字会让比较式渲染成另一回事。"""
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(_document((
            "led", PLATFORM_STM32,
            _section(probe={"calls": ["led_read()"], "expect": 0x68}))))
    assert "probe.expect" in str(exc.value)


# ---------------------------------------------------------------------------
# 加载校验②：引用的函数名必须在该模块该平台的头文件里（否则构建期失败）
# ---------------------------------------------------------------------------


def _manifest(slug: str, platforms: tuple[str, ...] = (PLATFORM_STM32,)) -> ModuleManifest:
    return ModuleManifest.from_dict({
        "slug": slug,
        "description": "测试件",
        "dependencies": [],
        "platforms": {
            platform: {"files": [], "verified": True, "hardware_bound": False,
                       "notes": "", "pins": []}
            for platform in platforms
        },
    })


def _interfaces(
    slug: str, names: set[str], platform: str = PLATFORM_STM32
) -> dict[str, dict[str, frozenset[str]]]:
    """接口清单夹具（含默认配方读数列用的 LED_CHANNEL_COUNT——read 段的裸常量
    也过判据，所以夹具必须把它算进去，否则测的就不是本意的那条守卫）。

    **形状 = `{平台: {slug: 名字集}}`**（工单 05 修正）：配方文件是全平台一份，
    校验时每段按**自己的平台**取清单——早先只传一份清单，拿 mspm0 的清单去查
    stm32 的段，平台不对称一出现就误报（实测：mspm0 预览 400 说 stm32 的 `ax`
    找不到）。夹具跟着契约走，否则测的不是生产侧那条路。
    """
    return {platform: {slug: frozenset({"LED_CHANNEL_COUNT"} | set(names))}}


def _library_interfaces(modules: Path, manifests, platform: str) -> dict[str, frozenset[str]]:
    """真实库**单平台**的接口清单 = `hwcheck_recipe.interface_names`（含母版头）。

    测试直接调**生产侧那一个函数**（不另写一份）：口径若漂了，本文件的地板断言
    就失去意义——"测试侧独立复现"在这里是反模式（复现的那份一定会与生产侧漂）。
    母版头从真母版目录读（`library/masters/<platform>` 的 **/*.h）。
    """
    from contest_generator.hwcheck_recipe import interface_names

    master_dir = REAL_MASTERS / platform
    headers = [
        (path.relative_to(master_dir).as_posix(),
         path.read_text(encoding="utf-8", errors="replace"))
        for path in sorted(master_dir.rglob("*.h"))
    ] if master_dir.is_dir() else []
    return interface_names(manifests, modules, platform, headers)


def _library_interfaces_all(
    modules: Path, manifests
) -> dict[str, dict[str, frozenset[str]]]:
    """真实库**两个平台**的接口清单（`load_recipes` 吃的形状）。"""
    return {
        platform: _library_interfaces(modules, manifests, platform)
        for platform in (PLATFORM_STM32, PLATFORM_MSPM0)
    }


def test_validate_accepts_calls_that_exist_in_the_module_interface():
    recipes = parse_recipes(_document(("led", PLATFORM_STM32, _section())))
    from contest_generator.hwcheck_recipe import validate_recipes

    validate_recipes(recipes, [_manifest("led")], _interfaces("led", {"led_init"}))


def test_validate_rejects_a_function_the_module_does_not_declare():
    """**本单的核心守卫**：配方引用了不存在的函数 → 构建期大声失败 + 点名。

    这条判据存在的理由写在 spec：「绝不学骨架兜底把它改成注释——那是"看着测了
    其实没测"」。所以错一个字母就必须红，而且要说清是哪个 slug、哪一段、哪个名字。
    """
    recipes = parse_recipes(_document((
        "led", PLATFORM_STM32, _section(init={"calls": ["led_initX(LED_RED)"]}))))
    from contest_generator.hwcheck_recipe import validate_recipes

    with pytest.raises(HwCheckError) as exc:
        validate_recipes(recipes, [_manifest("led")], _interfaces("led", {"led_init"}))
    message = str(exc.value)
    assert "led_initX" in message       # 点名那个不存在的名字
    assert "led" in message             # 点名哪一件
    assert "init" in message            # 点名哪一段


def test_validate_rejects_an_unknown_module_or_platform():
    """键必须是库内真实 slug、必须存在该平台条目——两处都大声失败。"""
    from contest_generator.hwcheck_recipe import validate_recipes

    unknown = parse_recipes(_document(("nosuch", PLATFORM_STM32, _section())))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(unknown, [_manifest("led")], _interfaces("led", {"led_init"}))
    assert "nosuch" in str(exc.value)

    wrong_platform = parse_recipes(_document(("led", PLATFORM_MSPM0, _section())))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(
            wrong_platform, [_manifest("led")], _interfaces("led", {"led_init"}))
    assert PLATFORM_MSPM0 in str(exc.value)


def test_validate_checks_the_read_and_probe_segments_too():
    """三段（init / probe / read）都过判据——只查 init 会漏。

    read 段**整条表达式**都查（不只是"像调用"的部分）：裸常量同样要在接口
    清单里。本单 pilot 的 read 恰好全是裸宏，只查调用会让 `OLED_RES_128X64`
    这种"另一个平台才有的常量"漏过去、一路漏到编译期。
    """
    from contest_generator.hwcheck_recipe import validate_recipes

    bad_read = parse_recipes(_document((
        "led", PLATFORM_STM32,
        _section(read={"expressions": ["led_read_something()"]}))))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(bad_read, [_manifest("led")], _interfaces("led", {"led_init"}))
    assert "led_read_something" in str(exc.value)

    bad_probe = parse_recipes(_document((
        "led", PLATFORM_STM32,
        _section(probe={"calls": ["led_probe()"], "expect": "1"}))))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(bad_probe, [_manifest("led")], _interfaces("led", {"led_init"}))
    assert "led_probe" in str(exc.value)

    # 裸常量：清单里没有的名字要在校验期被拦下（真机判例见真库那条用例）
    bad_const = parse_recipes(_document((
        "led", PLATFORM_STM32,
        _section(read={"expressions": ["OLED_RES_128X64"]}))))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(bad_const, [_manifest("led")], _interfaces("led", {"led_init"}))
    assert "OLED_RES_128X64" in str(exc.value)

    # 裸宏名在清单里 = 合法（LED_CHANNEL_COUNT 由 _interfaces 夹具提供）
    validate_recipes(
        parse_recipes(_document(("led", PLATFORM_STM32, _section()))),
        [_manifest("led")], _interfaces("led", {"led_init"}),
    )


def test_validate_accepts_an_expect_that_names_an_interface_constant():
    """期望值可以是字面量，也可以是接口清单里的常量名（如 LED_RED）。"""
    from contest_generator.hwcheck_recipe import validate_recipes

    recipes = parse_recipes(_document((
        "led", PLATFORM_STM32,
        _section(init={"calls": ["led_init(LED_RED)"]}, init_expect="LED_RED"))))
    validate_recipes(
        recipes, [_manifest("led")], _interfaces("led", {"led_init", "LED_RED"}))


def test_validate_rejects_an_expect_that_is_neither_literal_nor_interface():
    """期望值既不是 C 字面量、也不在接口清单里 = 拼错的常量名，当场红。"""
    from contest_generator.hwcheck_recipe import validate_recipes

    recipes = parse_recipes(_document((
        "led", PLATFORM_STM32,
        _section(init={"calls": ["led_init(LED_RED)"]}, init_expect="LED_RD"))))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(
            recipes, [_manifest("led")], _interfaces("led", {"led_init", "LED_RED"}))
    assert "LED_RD" in str(exc.value)


# ---------------------------------------------------------------------------
# 加载校验③：缺文件 = 空配方库（旧库照常能生成，全走通用降级）
# ---------------------------------------------------------------------------


def test_load_returns_empty_when_the_library_has_no_recipe_file(tmp_path):
    """老库 / 自定义库里没有这个文件 = 一件都没专精（不是错误）。

    与"形状坏了大声失败"是两种事：文件不在是**能力缺失**（全走通用降级，
    检测工程照常能生成），文件坏了是**数据错误**（读下去只会默默少测几件）。
    """
    modules = tmp_path / "library" / "modules"
    (modules / "led").mkdir(parents=True)
    assert load_recipes(modules, [_manifest("led")]) == {}


def test_load_reads_and_validates_from_disk(tmp_path):
    """真读盘一遍：文件在 → 解析 → 过接口校验（缺接口清单里的名字就抛）。"""
    modules = tmp_path / "library" / "modules"
    (modules / "led").mkdir(parents=True)
    recipe_library_path(modules).write_text(
        json.dumps(_document(("led", PLATFORM_STM32, _section())), ensure_ascii=False),
        encoding="utf-8",
    )
    recipes = load_recipes(modules, [_manifest("led")],
                           _interfaces("led", {"led_init"}))
    assert recipes["led"].for_platform(PLATFORM_STM32).init == ("led_init(LED_RED)",)


def test_load_fails_loudly_on_a_broken_recipe_file(tmp_path):
    """坏 JSON = 库内数据错误 → 中文大声失败（不静默当空库）。"""
    modules = tmp_path / "library" / "modules"
    (modules / "led").mkdir(parents=True)
    recipe_library_path(modules).write_text("{ 这不是 JSON", encoding="utf-8")
    with pytest.raises(HwCheckError) as exc:
        load_recipes(modules, [_manifest("led")], _interfaces("led", {"led_init"}))
    assert RECIPE_FILENAME in str(exc.value)


# ---------------------------------------------------------------------------
# 选件 → 小节（判据单源：顺序走既有 bring-up 排序）
# ---------------------------------------------------------------------------


def _catalog(data: dict) -> dict:
    """parse_recipes 的产物 → 目录形态（resolve_sections 吃的形状）。"""
    return {
        slug: RecipeCatalog(slug=slug, sections=sections)
        for slug, sections in parse_recipes(data).items()
    }


def test_resolve_sections_picks_the_selected_devices_in_verification_order():
    """小节顺序 = 既有 bring-up 稳定分区（led 属 bring-up，排在前）。

    顺序判据**不在这里另立**：与工程 README 的「验证顺序清单」同一函数
    （readme.sort_verification_order）——检测程序里的次序与 README 里那张
    清单不一致，学生会照着一个做、被另一个打脸。
    """
    recipes = _catalog(_document(
        ("led", PLATFORM_STM32, _section()),
        ("oled", PLATFORM_STM32, _section(
            init={"calls": ["OLED_Init()"]}, init_expect="",
            read={"expressions": ["OLED_RES_128X64"]})),
    ))
    manifests = [_manifest("oled"), _manifest("led")]
    sections = resolve_sections(PLATFORM_STM32, ["oled", "led"], recipes, manifests)
    assert [s.slug for s in sections] == ["led", "oled"]


def test_resolve_sections_skips_devices_without_a_recipe():
    """没配方的器件不出小节——本单不做通用降级（归工单 07），也不静默假装
    它被测了（"未专精"标注与通用小节的落点见工单 07）。"""
    recipes = _catalog(_document(("led", PLATFORM_STM32, _section())))
    sections = resolve_sections(
        PLATFORM_STM32, ["led", "sr04"], recipes, [_manifest("led"), _manifest("sr04")])
    assert [s.slug for s in sections] == ["led"]


def test_resolve_sections_is_empty_without_recipes():
    manifests = [_manifest("led")]
    assert resolve_sections(PLATFORM_STM32, ["led"], {}, manifests) == ()


# ---------------------------------------------------------------------------
# 渲染：小节 + 结尾汇总（零 LLM 的确定性文本）
# ---------------------------------------------------------------------------


def test_render_recipe_section_marks_it_specialized_and_counts_a_verdict():
    """专精小节：标题带 [专精] 标记（与未专精件外观可区分）+ 判定记账。

    ⚠ 中文字面量按 `c_string` **转义成 ASCII 转义序列**（工单 05 起三位八进制；
    ARMCC 5.06 按本地代码页解析源文件，原样中文串会把收尾引号吞掉、整份 main.c
    编不过）——所以断言查的是转义后的写法，不是原文。这条本身就是"别改回转义"的
    守卫。
    """
    section = RecipeSection(
        slug="led", platform=PLATFORM_STM32,
        init=("led_init(LED_RED)",), init_expect="0",
        read=(RecipeRead(expression="LED_CHANNEL_COUNT", unit="通道"),),
        note=("三色通道",),
    )
    report = {}
    lines = render_recipe_section(section, report)
    code = "\n".join(lines)
    assert "[专精] led" in code
    assert "led_init(LED_RED)" in code
    assert "LED_CHANNEL_COUNT" in code
    assert c_string(" 通道") in code                # 读数单位跟着回显（转义写法）
    assert "三色通道" in code                       # 平台说明印在注释里（原样中文）
    assert "hwcheck_verdict(" in code               # 初始化判定记账
    assert report["probe"] is False                 # 无探头：不判通断
    assert report["trouble"]                        # 带排查指引的中文
    # **渲染期不写 verdict**：判定结果只有板上才算得出来，渲染期写了只会是恒定
    # 值，汇总侧照它分支就是一条永不触发的死路（评审抓到的坑）。
    assert "verdict" not in report
    # 整份小节里**没有裸的非 ASCII**（除了注释行）——编译判据的结构化表达
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("/*") or stripped.startswith("*"):
            continue
        assert all(ord(ch) < 128 for ch in line), line


# 板上行缓冲：渲染产物里的 `static char hwcheck_line[128]`——写入判据是
# `len < sizeof - 1`，所以一行的**可用字节是 127**；本守卫按 128 卡（既有那条扩张格
# 守卫也是这个口径：`size < buffer_bytes`）。
HWCHECK_LINE_BYTES = 128
# `hwcheck_report_int` 打的是 int：最坏 32 位十进制含符号 11 位，留 1 位余量。
_WORST_INT_DIGITS = 12


def _rendered_read_line_bytes(section) -> list[int]:
    """这一格**真渲染出来**的每一条读数行有多少字节（工单 hwcheck-hardening/10 补的格式钉）。

    为什么不按格式手拼一个估算：那等于把渲染格式**抄第二份**——渲染器改了顺序 / 括号 / 分隔符，
    估算会静默失守（Standards 轴评审点名的判断题 4）。这里直接读渲染产物：

    * 读数段 = 一组连续语句、以 `hwcheck_newline()` 收尾；
    * 段的开头必然是 `hwcheck_report_int(<表达式>);`——数字部分按**最坏宽度**（32 位十进制
      含符号 11 位，留 1 位余量）算；
    * 其余 `hwcheck_report("<字面量>");` 按**转义还原后的原文**数字节（中文一字 3 字节）；
    * 段里出现别的语句形态 → **当场红**：那说明渲染器变了，本守卫的假设要跟着更新
      （这就是"格式钉"本身，别让它悄悄漂过去）。
    """
    code = "\n".join(render_recipe_section(section, {}))
    sizes: list[int] = []
    current: int | None = None
    for raw in code.splitlines():
        line = raw.strip()
        if line.startswith("hwcheck_report_int("):
            assert current is None, f"读数段里出现第二条 report_int（渲染器形态变了）：{line}"
            current = _WORST_INT_DIGITS
            continue
        if current is None:
            continue
        if line.startswith("hwcheck_report("):
            literal = re.match(r'hwcheck_report\(("(?:[^"\\]|\\.)*")\);', line)
            assert literal, f"读数段里的 report 不是单字面量形态（渲染器形态变了）：{line}"
            current += len(decode_c_string(literal.group(1).strip('"')).encode("utf-8"))
            continue
        if line.startswith("hwcheck_newline()"):
            sizes.append(current)
            current = None
            continue
        raise AssertionError(f"读数段里出现没预期的语句（渲染器形态变了）：{line}")
    assert current is None, "读数段没有以 hwcheck_newline() 收尾（渲染器形态变了）"
    return sizes


def test_every_real_read_line_fits_the_device_line_buffer():
    """**全量配方**的每条读数行都要塞得进板上那 128 字节的行缓冲（工单 hwcheck-hardening/04）。

    为什么单独立一条：既有的 `test_expansion_read_lines_fit_the_device_line_buffer` 只吃
    `EXPANSION`（扩张格），**pilot 那批刻意不吃**（`.scratch/backlog.md` §21 就是这么记的），
    而实测超限的正好**全在 pilot**：`debug_uart × stm32` 249B、`adc × mspm0` 162B、
    `beep × stm32` 156B、`adc × stm32` 149B、`adc × mspm0` 149B（比 §21 记的那 1 条多 4 条）。

    溢出保护是刻意的（宁可截一行，不让程序跑飞），但中文一字 3 字节——**截在字中间就是半个乱码**，
    学生看到的是"读数那行尾巴花了"，而不是一条能自查的报错。

    宽度**从渲染产物量**（`_rendered_read_line_bytes`），不手抄格式——渲染器改了形态当场红。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    total = 0
    too_long: list[tuple[int, str, str]] = []
    for slug, catalog in recipes.items():
        for platform, section in catalog.sections.items():
            if not section.usable:
                continue
            for size, item in zip(_rendered_read_line_bytes(section), section.read):
                total += 1
                if size >= HWCHECK_LINE_BYTES:
                    too_long.append((size, f"{slug} × {platform}", item.expression))
    # 地板 167：`section.read` 实测合计 167——其中 2 条走旧的 `expressions`（复数）形态
    # （`led × 两平台`）。解析器已经把它们并进 `section.read`，所以宽度判据本来就算到了；
    # 失真的只是这个数字与措辞（见工单 hwcheck-hardening/11）。
    assert total >= 167, f"全量读数行少于地板 167（现在 {total}）——地板要跟着扩张批上调"
    assert not too_long, (
        "这些读数行会撞上 128 字节的行缓冲（板上静默截断，中文截半就是乱码）："
        + "；".join(f"{size}B {where} [{expr}]" for size, where, expr in sorted(too_long, reverse=True))
        + "——把长说明挪进该格的平台说明（note 是页面文本、不进板上缓冲），行上只留短量纲"
    )


def test_read_line_puts_the_value_before_the_source_expression():
    """读数行**值优先**（工单 hwcheck-hardening/03）：`<值> <单位> (<表达式>)`。

    为什么改顺序：OLED 出口是单行刷新、屏宽只有 16 列，而原来那一行是
    `  <表达式> = <值> <单位>`——横幅在数值之前，实测 165 条读数里 **53% 光横幅就超 16 列**，
    数值根本进不了屏。改后数与量纲落在最前面（屏上看得见），表达式退成行尾括注
    （串口上照样读得出"这个数从哪来"）。

    表达式**不截断**：宽度交给构建期守卫（逐格量整行字节数）兜，运行期截断只会静默丢信息。
    """
    report = {}
    code = "\n".join(render_recipe_section(
        RecipeSection(
            slug="led", platform=PLATFORM_STM32,
            init=("led_init(LED_RED)",), init_expect="0",
            read=(RecipeRead(expression="LED_CHANNEL_COUNT", unit="通道"),),
        ),
        report,
    ))
    idx_value = code.index("hwcheck_report_int(LED_CHANNEL_COUNT);")
    idx_unit = code.index(c_string(" 通道"))
    idx_source = code.index(c_string(" (LED_CHANNEL_COUNT)"))
    assert idx_value < idx_unit < idx_source, (
        "读数行的顺序应当是「值 → 单位 → （表达式）」，让学生（尤其是只看 OLED 的）先看到数"
    )
    # 旧的"横幅在前"形态不许回来
    assert c_string("  LED_CHANNEL_COUNT = ") not in code
    assert "hwcheck_report_int" in code


def test_render_recipe_section_without_probe_says_it_is_not_judged():
    """**不假装测过**：没有探头的件，板上说"无法判定通断"，不许打 OK。

    spec 判据三层里第②层是"板端通信判定"，而 LED 这类纯输出件本来就没有
    可读的身份寄存器——那就如实说"这一件只看现象"，不把它算成通过。
    """
    report = {}
    code = "\n".join(render_recipe_section(
        RecipeSection(slug="led", platform=PLATFORM_STM32,
                      init=("led_init(LED_RED)",), init_expect="0",
                      read=(RecipeRead(expression="LED_CHANNEL_COUNT"),)),
        report,
    ))
    assert "通断无法判定" in _unescape_c(code)
    assert "hwcheck_verdict_probe_none(" in code
    assert "hwcheck_verdict(" in code


def test_render_recipe_section_handles_a_void_init_without_inventing_a_verdict():
    """`void` 初始化（如 led_init）**不编造比较式**：只调、如实说"不判返回值"。

    真机判例：`r = led_init(LED_RED)` 直接编译不过（`#513: a value of type
    "void" cannot be assigned to an entity of type "int"`）。配方没写
    `init_expect` 就等于"这一件判不了返回值"，渲染器不许硬编一个 `== 0`。
    """
    code = "\n".join(render_recipe_section(
        RecipeSection(slug="led", platform=PLATFORM_STM32,
                      init=("led_init(LED_RED)",)),
        {},
    ))
    assert "    led_init(LED_RED);" in code
    assert "r = led_init" not in code            # 不许把 void 调用赋给 int
    assert "int r;" not in code                  # 也不许留一个没人用的 r
    assert c_string("已调用（本件不判返回值）") in code
    assert "hwcheck_verdict_probe_none(" in code  # 判不了 = 未判定档，不算通过


def test_render_recipe_section_with_a_probe_judges_the_communication():
    """有探头：把期望值写进比较式，对得上打 OK、对不上打 FAIL + 中文排查话术。

    判定是**板端自己算**的（`== 0x68` 落在渲染出的 C 里），不是渲染期猜的——
    规格要求板上给出 OK/FAIL，而不是让学生从一个返回值里猜。
    """
    section = RecipeSection(
        slug="ml_mpu6050", platform=PLATFORM_STM32,
        prereq=("mpu_soft_i2c_init()",),
        init=("mpu6050_init()",), init_expect="0",
        probe=RecipeProbe(calls=("mpu6050_who_am_i()",), expect="0x68"),
        read=(RecipeRead(expression="mpu6050_read_accel()"),),
        note=("通信 OK 才有后面的读数",),
    )
    report = {}
    code = "\n".join(render_recipe_section(section, report))
    assert "hwcheck_verdict(1," in code
    assert "hwcheck_verdict(0," in code
    assert "== 0x68" in code                       # 探头的期望值进比较式
    assert "mpu_soft_i2c_init()" in code            # 前置调用进小节
    assert "通信 OK 才有后面的读数" in code          # 平台差异说明直接印到检测页
    assert "== 0" in code                           # 初始化的期望值进比较式
    assert "return;" in code                        # 不通就不再打无意义读数
    assert report["probe"] is True


def test_render_recipe_summary_hands_the_counting_to_the_board():
    """结尾汇总 = 板上数（`hwcheck_summary`）+ 渲染期能给的"万一失败先查哪里"。

    "几件通过 / 几件没探头"的计数在**板上**算：它取决于运行时结果（探头过没过），
    渲染期只能列出"可能失败时该看哪里"。三档分开数这件事由 C 侧
    `hwcheck_summary` 保证（判据在 `tests/test_hwcheck.py` 的结构断言里）。

    判据只吃 `trouble`、**不吃任何"结果"字段**：渲染期没有结果可吃——曾经按
    `verdict == "fail"` 过滤，而 `verdict` 在渲染期恒不为 fail，那条分支永不
    触发（评审抓到的坑，本用例钉住"不按结果过滤"）。
    """
    led = {"slug": "led", "probe": False,
           "trouble": "led：没有读取型探头，只看了现象"}
    mpu = {"slug": "ml_mpu6050", "probe": True,
           "trouble": "ml_mpu6050：通信失败（先查供电 / 上拉 / 地址 / 线序）"}
    code = "\n".join(render_recipe_summary([led, mpu]))
    assert "hwcheck_summary();" in code
    assert "先查供电 / 上拉 / 地址 / 线序" in _unescape_c(code)
    assert "只看了现象" not in _unescape_c(code)   # 没探头的件不是"失败指引"，
    #                                               不该抢在结果前面喊失败
    assert "verdict" not in code                   # 渲染期没有结果字段可用


def test_render_recipe_summary_without_specialized_sections_says_so():
    """一件专精件都没有时不渲染假汇总，如实说"只确认板子活着"。"""
    code = "\n".join(render_recipe_summary([]))
    assert "hwcheck_summary();" in code
    assert "没有专精件" in code


# ---------------------------------------------------------------------------
# 地板断言：真实库的 pilot 清单每一格都真有配方
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug,platform", PILOT)
def test_real_library_has_a_recipe_for_every_pilot_slot(slug, platform):
    """**地板断言**（照 `WIKI_COVERAGE_FLOOR` 先例）：pilot 清单不许缩水。

    配方是数据，数据丢了不会有任何用例变红——所以这里逐格直取真实库，
    少一格当场红，并说清是哪一格。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    interfaces = _library_interfaces_all(REAL_LIBRARY, manifests)
    recipes = load_recipes(REAL_LIBRARY, manifests, interfaces)
    catalog = recipes.get(slug)
    assert catalog is not None, f"真实库缺配方：{slug}"
    hit = catalog.for_platform(platform)
    assert hit is not None, f"真实库缺配方：{slug} × {platform}"
    assert hit.usable, f"{slug} × {platform} 的配方是空壳"


def test_real_library_recipes_reference_only_real_interfaces():
    """真实库整份配方都过引用校验（本单的核心守卫在真数据上跑一遍）。

    `load_recipes` 带 interfaces 就会校验——能读出来即证明每一条引用的函数名
    都在**对应模块对应平台**的头文件里。这条同时是"配方随库演进"的守卫：模块
    改名 / 删接口而配方没跟上，这里当场红。

    两个平台的清单**一起**传（工单 05 起 `interfaces` 是按平台分开的）：这样
    一段都不会因为"这次没给那个平台的清单"而被跳过——平台不对称（stm32 有
    `ax` 而没有 `DMP_Init`）正是这条要挡的东西。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    assert recipes, "真实库应当至少有 pilot 清单那几件的配方"
    for catalog in recipes.values():
        assert catalog.usable


def test_pilot_floor_covers_every_v1_slot():
    """**地板条数**断言（工单 09）：pilot 清单 = 10 件 / 17 格，逐格钉住。

    上面那条逐格断言保证"每格都有配方"，这条保证**清单本身**不被改小
    （有人删掉 PILOT 里的一行，逐格断言就少跑一格、静默放行）——两条一起
    才是地板：一格都不能少，且每一格都真的能读出来。
    """
    assert len(PILOT) == 17, f"pilot 清单格数变了：{len(PILOT)}（spec v1 清单 = 17 格）"
    assert len({slug for slug, _ in PILOT}) == 10, "pilot 清单件数应是 10 件"


@pytest.mark.parametrize("slug,platform", EXPANSION)
def test_real_library_has_a_recipe_for_every_expansion_slot(slug, platform):
    """**扩张地板**（spec `hwcheck-specialize`「覆盖记录与地板」）：逐格钉住。

    与 `PILOT` 那条同款判据、**另一条清单**：`PILOT` 管"v1 清单不许改小"，
    这条管"扩张成果不许悄悄缩水"。分开的理由写在 `EXPANSION` 上方的注释里。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    interfaces = _library_interfaces_all(REAL_LIBRARY, manifests)
    recipes = load_recipes(REAL_LIBRARY, manifests, interfaces)
    catalog = recipes.get(slug)
    assert catalog is not None, f"真实库缺配方：{slug}"
    hit = catalog.for_platform(platform)
    assert hit is not None, f"真实库缺配方：{slug} × {platform}"
    assert hit.usable, f"{slug} × {platform} 的配方是空壳"


def test_expansion_floor_keeps_its_cell_count():
    """扩张清单的**条数**精确（每批长一次）：删一行就红。

    为什么条数与逐格断言要分开：只留逐格断言时，"同步删一行 EXPANSION + 删配方文件里
    那一格"两条都静默变绿——这正是 spec 要挡的那种缩水。`PILOT` 那边同样两条并存。
    """
    assert len(EXPANSION) == EXPANSION_CELL_COUNT, (
        f"扩张清单格数变了：{len(EXPANSION)}（冻结值 {EXPANSION_CELL_COUNT}）——"
        "每落一批内容工单要同时改 EXPANSION 与 EXPANSION_CELL_COUNT，"
        "并且只追加、不改写已有的行"
    )


def test_expansion_floor_does_not_borrow_pilot_cells():
    """扩张清单与 v1 清单**不许重叠**：拿 pilot 的格冒充扩张成果 = 地板虚长。

    （两件事本来就不该互相顶替：`PILOT` 那 17 格的冻结值不变，扩张是它之外新长出来的。）
    """
    assert not (set(EXPANSION) & set(PILOT))


# 板上行缓冲：`hwcheck.py` 渲的 `static char hwcheck_line[128]`——报告文本先攒一行、
# 遇换行才整行送出，**超长静默截断**（溢出保护是刻意的：宁可截一行，也不踩内存）。
# 一条读数行 = `  <表达式> = <值> <单位>`；值的宽度取 int32 的极端写法
# `-2147483648`（11 字符）作上界——比任何真实读数都宽，所以这条判据不依赖
# "这个量大概几位数"的猜测。
_LINE_BUFFER_BYTES = 128
_INT32_MAX_CHARS = 11


@pytest.mark.parametrize("slug,platform", EXPANSION)
def test_expansion_read_lines_fit_the_device_line_buffer(slug, platform):
    """**扩张格**的每一条读数行都放得进板上的 128 字节行缓冲（工单 04 立的用例）。

    为什么本单要新立一条：截断发生在**字节**层面，中文一字 3 字节，截在字中间就是
    半个乱码——学生看到的是"读数那行尾巴花了"，而不是一条能自查的报错。既有的
    `test_every_reported_line_fits_the_line_buffer` 吃的是**手搓小节 + 通用件**、
    **不读真配方**，所以扩张批次的读数行宽一直靠"每批自行核对一次"（工单 03 的落地
    记录里就有这么一条），没有守卫。工单 04 落地时正是这次自查抓到 **4 行超宽**
    （最宽 171 字节：海拔那行），改完宽度再把它立成用例——反证见
    `.scratch/hwcheck-specialize/probe-line-buffer.txt`（把某一格的单位撑宽 → 本用例必红）。

    ⚠ **射程 = `EXPANSION` 这些格，不含 v1 `PILOT`**：pilot 的 `debug_uart × stm32`
    那一行**本来就超**（表达式 `gpio_get(DEBUG_UART_RX_GPIO, DEBUG_UART_RX_Pin)`
    加一段长说明 ≈ 247 字节，属既有的另一笔账）——本单只如实记账、不动它
    （见 `.scratch/backlog.md`）。新批次往 `EXPANSION` 追加即自动吃到这条守卫。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    interfaces = _library_interfaces_all(REAL_LIBRARY, manifests)
    recipes = load_recipes(REAL_LIBRARY, manifests, interfaces)
    section = recipes[slug].for_platform(platform)
    assert section is not None, f"真实库缺配方：{slug} × {platform}"
    too_wide: list[str] = []
    for item in section.read:
        line = f"  {item.expression} = " + "9" * _INT32_MAX_CHARS + f" {item.unit}"
        size = len(line.encode("utf-8"))
        if size >= _LINE_BUFFER_BYTES:
            too_wide.append(f"{size} 字节（余 {_LINE_BUFFER_BYTES - size}）：{line}")
    assert not too_wide, (
        f"{slug} × {platform} 的读数行放不下板上的行缓冲（可用 "
        f"{_LINE_BUFFER_BYTES - 1} 字节；中文一字 3 字节，截在字中间就是乱码）——"
        "把单位写短些，或把说明挪进 note：\n" + "\n".join(too_wide)
    )


def _locals_written_by(declarations, code: str) -> list[str]:
    """→ 在这段渲染产物里**从没被赋值**的局部变量名（空列表 = 都被赋过值）。

    **判据（工单 08 立的守卫）**：`locals` 的唯一用途是「把采样存下来给读数段复用」，
    所以每个声明的局部变量都必须在渲染出的 C 里**被赋值过一次**——否则读数段读到的是初值，
    现象是「探头判 OK、读数恒 0」，这是最像"测过了"的假绿。

    实现上刻意**只认 `名字 =` 这一个形态**，先把两类"也长得像赋值"的行踢掉：

    * **声明行**：渲染器把每条 `locals` 原样写成 `    <声明>;`（`类型 名字 = 初值;`）；
    * **读数标签行**：渲染器把读数的"来源表达式"写成行尾括注的 `hwcheck_report(" (raw)")`
      （工单 hwcheck-hardening/03 起值优先，标签里照样含变量名）。

    然后逐行找 `名字`，检查它后面是不是**赋值号**（`=`，且不是 `==` / `!=` / `<=` / `>=`、
    也不是语句尾 / 传参 / 括号收尾 / 引号）。步骤分开做（先剥行、再逐行扫）是为了
    **不依赖正则的变长回溯**——上一版用 lookahead 写在整段文本上扫，被 `\\s*` 的回溯
    骗成了恒真（反证时才发现），这一版把每一步都做成"看得见"的形态判断。
    """
    body = code
    for declaration in declarations:
        body = body.replace(f"    {declaration};", "")
    lines = [
        line for line in body.splitlines()
        if line.strip() and not line.strip().startswith(("/*", "//", "hwcheck_report("))
    ]
    unwritten: list[str] = []
    for name in sorted(local_names(declarations)):
        found = False
        for line in lines:
            for match in re.finditer(re.escape(name), line):
                before = line[match.start() - 1] if match.start() else ""
                if before and (before.isalnum() or before in "_.\"'\\"):
                    continue
                tail = line[match.end():]
                # 结构体成员赋值：`.c = 0`
                if re.match(r"[ \t]*\.[ \t]*\w+[ \t]*=(?!=)", tail):
                    found = True
                    break
                assignment = re.match(r"[ \t]*=(?!=)", tail)
                if assignment is None:
                    continue
                # 排除 `!=` / `<=` / `>=`：`=` 前面那个非空字符是运算符
                if tail[:assignment.end() - 1].strip(" \t").startswith(("!", "<", ">")):
                    continue
                after = tail[assignment.end():assignment.end() + 1]
                if after and after not in "=;,)\"":
                    found = True
                    break
            if found:
                break
        # 出参取地址也算"写过"：`&raw`
        if not found and re.search(rf"&[ \t]*{re.escape(name)}(?![A-Za-z0-9_])", body):
            found = True
        if not found:
            unwritten.append(name)
    return unwritten


def test_locals_guard_tells_a_write_from_a_mere_read():
    """**判据自检**：`_locals_written_by` 分得清「写」与「读 / 比较 / 声明 / 标签」。

    为什么单独立一条：这一条用例上一版的判据用 lookahead 写，被 `\\s*` 的回溯骗成恒真
    ——整条守卫绿着，而它本该抓的那个缺陷（`hx711 × stm32` 把采样存进 `r`）就在眼前。
    判据本身也要有判据，所以这里用**手写片段**把七种形态一次钉死。
    """
    def renders(declarations, *lines: str) -> str:
        """合成一段渲染产物（声明行 + 若干语句行）——形态与渲染器一致。"""
        return "\n".join([*(f"    {d};" for d in declarations), *lines])

    good = _locals_written_by(["uint32_t raw = 0"], renders(
        ["uint32_t raw = 0"], "    raw = hx711_read_raw();"))
    broken = _locals_written_by(["uint32_t raw = 0"], renders(
        ["uint32_t raw = 0"], "    r = hx711_read_raw();"))
    comma = _locals_written_by(["uint32_t raw = 0"], renders(
        ["uint32_t raw = 0"], "    r = (delay_ms(500), raw = hx711_read_raw(), 1);"))
    member = _locals_written_by(["TCS34725_RGBC rgb"], renders(
        ["TCS34725_RGBC rgb"], "    rgb.c = 0;"))
    address = _locals_written_by(["TCS34725_RGBC rgb"], renders(
        ["TCS34725_RGBC rgb"], "    tcs34725_read_rgb(&rgb);"))
    compare_only_code = renders(
        ["uint32_t raw = 0"], "    r = (raw != 0) ? 1 : 0;",
        '    hwcheck_report("  raw = ");', "    hwcheck_report_int(raw);")
    compare_only = _locals_written_by(["uint32_t raw = 0"], compare_only_code)
    other_name = _locals_written_by(["uint32_t raw = 0"], renders(
        ["uint32_t raw = 0"], "    r = hx711_read_raw();",
        "    /* note 里写着 `raw` 这个词 */"))

    assert good == [], good
    assert comma == [], comma
    assert member == [], member
    assert address == [], address
    assert broken == ["raw"], broken
    assert compare_only == ["raw"], compare_only
    assert other_name == ["raw"], other_name


@pytest.mark.parametrize("slug,platform", EXPANSION)
def test_expansion_cells_that_declare_locals_actually_write_them(slug, platform):
    """**扩张格**里声明了 `locals` 的，必须在渲染出的 C 里真被写过（工单 08 立的守卫）。

    为什么单独立一条：`locals` 的唯一用途是「把采样存下来给读数段复用」，而**判据段**的
    每条调用都会被渲染器加壳成 `r = <call>;`——写配方的人很容易在那一句里顺手把赋值目标
    写成 `r`（外层那个判定变量），于是局部变量**永远停在初值**：
    编译过、校验过、探头也判 OK，**但读数两行恒为 0 / -8388608**，学生在板上看到的是
    「探头 OK、读数是零」。工单 08 落地时正是这么写错的（`hx711 × stm32` 的探头把采样
    存进了 `r`），双轴评审用渲染产物抓出来——所以这里把它钉成判据。

    判据本体在 `_locals_written_by`（另有一条它自己的自检用例）。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    interfaces = _library_interfaces_all(REAL_LIBRARY, manifests)
    recipes = load_recipes(REAL_LIBRARY, manifests, interfaces)
    section = recipes[slug].for_platform(platform)
    assert section is not None, f"真实库缺配方：{slug} × {platform}"
    if not section.locals:
        pytest.skip(f"{slug} × {platform} 没有 locals 段（本用例对它无话可说）")
    unwritten = _locals_written_by(section.locals, "\n".join(render_recipe_section(section)))
    assert not unwritten, (
        f"{slug} × {platform} 声明了局部变量 {unwritten}，但渲染出的 C 里从没给它赋过值"
        "（读出来会恒是初值）——检查配方里那句「把采样存进 locals」是不是顺手写成了 `r = …`："
        "判据段的调用会被渲染器加壳成 `r = <call>;`，赋值目标必须是局部变量名"
    )


def test_recipe_file_itself_keeps_the_floor_cell_count():
    """**独立于 PILOT 常量**的地板（工单 09 评审整改）：直接数配方文件。

    为什么单独立一条：上面两条都以 `PILOT` 为判据，而 `PILOT` 是**测试里手写的
    常量**——有人"同步删一行 PILOT + 删配方文件里那一格"时，两条都静默变绿，
    正是 spec「防止清单缩水而无人察觉」要挡的那种改法。这条不读 PILOT，只数
    `library/hwcheck_recipes.json` 里**有实际动作的格**（prereq/init/probe/read
    至少一项）：低于冻结下限 17 或件数低于 10 就红。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    cells = [
        (slug, platform)
        for slug, catalog in recipes.items()
        for platform, section in catalog.sections.items()
        if section.usable
    ]
    slugs = {slug for slug, _ in cells}
    assert len(cells) >= 17, f"配方文件里有实际动作的格少于地板 17：{sorted(cells)}"
    assert len(slugs) >= 10, f"配方文件覆盖的件数少于地板 10：{sorted(slugs)}"


# 配方数据里**不许**再出现的措辞（工单 hwcheck-hardening/01）：这类句子会教学生去改
# 生成出来的 main.c，而那一行初始化从 hwcheck-acceptance/01 起**已经是活代码**——
# 学生照做会找不到那一行，而且它与检测页清单自相矛盾（清单里那条早已删掉）。
_FORBIDDEN_EDIT_INSTRUCTIONS = ("取消注释", "注释去掉", "注释状态")


def test_real_recipe_file_never_asks_students_to_edit_generated_code():
    """真库配方**全文**不许出现"去改生成代码"的指令（工单 hwcheck-hardening/01）。

    为什么读全文而不是逐字段：这句措辞会在 note / unit / description 之间搬家，
    按字段枚举总有漏网；它对学生的危害与它落在哪个字段无关。

    为什么单独立一条：`tests/test_hwcheck.py` 里那条同类断言只吃**页面清单**的渲染结果，
    **管不到配方数据**——2026-09-25 的复测（`.scratch/hwcheck-acceptance/报告-复测.md` 的 N1）
    正是在这个缺口上漏掉一处：清单项删了、文案改了，`key × mspm0` 那格原样留着。
    """
    text = recipe_library_path(REAL_LIBRARY).read_text(encoding="utf-8")
    hits = sorted({word for word in _FORBIDDEN_EDIT_INSTRUCTIONS if word in text})
    assert not hits, (
        f"配方文件里出现了教学生改生成代码的措辞 {hits}——那一行从 hwcheck-acceptance/01 "
        "起已经是活代码，学生照做会找不到。改写口径照 `xunji × mspm0` / `adc × mspm0`："
        "「…检测程序开头已经调了它（那一行是活代码，不需要你改 main.c）」"
    )


def test_key_recipe_note_says_the_init_line_is_already_live():
    """删掉旧指令之后，那句话要**真的换成实话**（防"删干净了但没换上"）。

    与上一条配对：上一条只管"不该在的没了"，这一条管"该在的在了"——
    只有一条时，把整段文案删空也能变绿。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    section = recipes["key"].for_platform(PLATFORM_MSPM0)
    assert section is not None, "真实库缺 `key × mspm0` 配方"
    note = "\n".join(section.note)
    assert "不需要你改 main.c" in note, f"`key × mspm0` 的平台说明没换成实话：{note}"
    assert "读数不可信" in note, (
        "原先那半句有效信息（这一行不生效 = 输入配置没配上、读数不可信）不该跟着旧指令一起删掉"
    )
    # 它真的会印到检测页：页面读的就是 `sections_payload`（hwcheck_board 的视图载荷）。
    payload = sections_payload([section])
    assert any("不需要你改 main.c" in line for line in payload[0]["note"]), (
        "这句实话没进页面载荷——学生就还是看不到它"
    )


def test_every_real_recipe_cell_discloses_its_on_board_status():
    """**57/57 格**都必须在平台说明的**最后一条**如实写「**未上板**」（工单 hwcheck-hardening/02）。

    为什么要这条：`hwcheck-specialize` 那一批把这句话写进了自己新增的格，但 **v1 pilot 那 16 格**
    （`led / oled / debug_uart / key / beep / sr04 / jy61p / adc / ml_mpu6050` × 两平台）没有——
    其中 `ml_mpu6050` 是旗舰件，说明里还写着"板上判 FAIL 就是通信真的没通"这种**从未在真板上验证过**
    的断言。学生看不到这句，就会把"配方没验过"读成"我线接错了"。

    判据取**最后一条**而不是"任意一条"：这句话是结论性自述，位置飘在中间会被后续内容盖住；
    40 格已经是这个形态，本条把它变成对**全部格**成立的不变量。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    no_note: list[str] = []
    buried: list[str] = []
    missing: list[str] = []
    total = 0
    for slug, catalog in recipes.items():
        for platform, section in catalog.sections.items():
            if not section.usable:
                continue
            total += 1
            notes = list(section.note)
            where = f"{slug} × {platform}"
            if not notes:
                no_note.append(where)
            elif "**未上板**" in notes[-1]:
                continue
            elif any("**未上板**" in note for note in notes):
                buried.append(where)
            else:
                missing.append(where)
    assert total >= 57, f"真实库的可动作配方格少于地板 57（现在 {total}）——地板要跟着扩张批上调"
    assert not no_note, f"这些格没有平台说明，学生读不到任何自述：{no_note}"
    assert not buried, f"「未上板」那句不在最后一条（会被后面的内容盖住）：{buried}"
    assert not missing, (
        f"这些格没说自己在真板上的状态：{missing}——照扩张批的措辞补一条放在最末："
        "「**未上板**：本格的结论只到「…」，真机上板验证还没做（与库内 manifest 的口径一致）。"
        "实测差异优先于本页参考值。」（本件没有可判的板端返回码时，中间那句换成如实的静态核对）"
    )


def test_every_real_recipe_note_marks_unverified_with_the_same_clause():
    """真库 57 格的末条自述必须是**同一条子句**（工单 hwcheck-hardening/09）。

    与上面那条 57/57 守卫分工：那条管"有没有这句自述、在不在最后一条"，
    这条管"**是不是同一种说法**"——`servo` 那两格原先写的是"manifest 没有上板验证记录"，
    是第二种说法；补上规范子句之后，全都含「真机上板验证还没做」。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    missing: list[str] = []
    for slug, catalog in recipes.items():
        for platform, section in catalog.sections.items():
            if not section.usable:
                continue
            notes = list(section.note)
            line = notes[-1] if notes else ""
            if "**未上板**" not in line or "真机上板验证还没做" not in line:
                missing.append(f"{slug} × {platform}")
    assert not missing, (
        f"这些格的末条自述不是同一条说法（缺「**未上板**」或「真机上板验证还没做」）：{missing}"
    )


def _multi_instance_overclaims(text: str) -> list[str]:
    """一段**页面文本**里把"只验第一路"说成"全验了"的肯定式命中（判据本体）。

    单独立函数是为了能**单独自证**（`test_multi_instance_overclaim_predicate_*`）：
    这条判据有两处容易写歪的地方，都拿合成文本钉住——

    * 半截词整串匹配会把**否定式**判成违规：本轮那两句实话正是
      "通道数不是「每一路都验过」的意思"（产品文案必须能这么写）；
    * 只列完整断言又会让"每一路都测过了"这种说法漏网（它不是"验过"）。

    ⚠ **它是一条绊线，不是语义判据**：只认这几个词组、只在**断言前那一段**（到上一个小句
    边界为止，封顶 `_NEGATION_WINDOW` 字）里找否定词，换个说法（"四路都验过了"）照样能溜
    过去。真要"任何措辞都抓得住"得判语义，那不是测试该干的事——所以另一条腿是**正向**的
    （必须出现自述），这条只负责拦住最像的几种反话。
    """
    claims = ("已验全部", "全部通道", "每一路都验过", "每一路都测过")
    hits: list[str] = []
    for claim in claims:
        start = text.find(claim)
        while start != -1:
            # 否定词的判据窗口 = 断言**往前一整句**（到上一个小句边界为止，再用
            # _NEGATION_WINDOW 封顶）：只看"紧挨着的 6 个字"会在「并不能说明每一路都验过」
            # 这种写法上漏判——而那正是这条判据存在的理由（评审实测）。
            head = text[max(0, start - _NEGATION_WINDOW):start]
            if not any(neg in head for neg in _NEGATIONS):
                hits.append(f"…{text[max(0, start - 8):start]}{claim}…")
            start = text.find(claim, start + 1)
    return hits


# 否定词的判据窗口（断言前多少字之内找否定词）。单列成常量是为了让"我放宽到多少"这件事
# 在文件里看得见（原先写死 `start - 6`，评审判为无出处的魔数）：**12 字**刚好覆盖本轮那两种
# 写法（"不是「" / "并不能说明"），再放宽就会把"这不是第一路的问题，四路都验过了"这种
# **同句反话**也豁免掉——绊线宜紧不宜松，宁可偶发误报（报错了改文案）也不漏报。
_NEGATION_WINDOW = 12
_NEGATIONS = ("不是", "并非", "不等于", "非", "不", "没", "未")


def test_multi_instance_overclaim_predicate_accepts_the_honest_negation():
    """判据自证①：**否定式**（"通道数不是「每一路都验过」的意思"）不算违规。

    为什么值得单独钉：这条判据整串匹配"每一路都验过"时，本轮那两句实话会被自己
    判红——判据写歪了却表现得像数据有问题，最费时间的一种红。
    """
    assert _multi_instance_overclaims(
        "多实例只验第一路：回显的通道数不是「每一路都验过」的意思。") == []
    assert _multi_instance_overclaims(
        "多实例只验第一路：通道数并非每一路都验过。") == []
    # 否定词与断言之间夹着别的字（评审实测的那一处写法）也要认出来
    assert _multi_instance_overclaims(
        "多实例只验第一路：通道数并不能说明每一路都验过。") == []
    assert _multi_instance_overclaims(
        "多实例只验第一路：这四个字不等于每一路都验过。") == []


def test_multi_instance_overclaim_predicate_rejects_the_positive_claim():
    """判据自证②：**肯定式**必须报出来（含"测过"这一支，别只认"验过"）。"""
    assert _multi_instance_overclaims("本件已验全部通道，放心用。")
    assert _multi_instance_overclaims("多实例每一路都验过了。")
    assert _multi_instance_overclaims("多实例每一路都测过了。")
    assert _multi_instance_overclaims("全部通道都测了。")
    assert _multi_instance_overclaims("只验第一路，别的都好好的。") == []


def test_every_multi_instance_recipe_cell_discloses_it_only_tests_the_first_channel():
    """凡声明多实例（`multi_instance.max > 1`）的格，**页面拿到的文本**必须如实说"只验第一路"
    （工单 hwcheck-hygiene/07）。

    为什么要这条：`led` / `key` 的 manifest 声明了 `max = 8`（生成页能给 8 路实例），
    而检测配方只有"通道"这一维——`led_init(LED_RED)` / `get_key_state(KEY_START)`
    **只驱动第一路**，另外几路这一趟一个动作都没有。页面上却照旧回显 `LED_CHANNEL_COUNT` /
    `KEY_CHANNEL_COUNT`（"本工程有 4 路"）——学生装了 4 个 LED，只看见 1 个被验过，
    而回显的通道数让他以为 4 个都验了。这不是配方写漏，是**能力缺口**（按实例展开要动
    配方 schema，见 spec「范围外」），所以本轮只把这句缺口如实写出来。

    判据取**渲染产物**而不是 JSON 字段（照 `test_every_real_recipe_cell_discloses_its_on_board_status`
    的先例）：`sections_payload` 是页面读的那一份，`render_recipe_section` 是检测程序那一份——
    note 里写了、却没进这两个出口，学生照样看不到。（载荷 → DOM 那最后一跳由前端门禁
    `tests/js/hwcheck.test.mjs::hwcheckSectionNoteHTML…多实例` 作证，那支才跑得动 `ui` 件。）

    与「未上板」那条**不许互相顶替**：那条说"没上过板"，这条说"只验了第一路"，
    两件事各自说自己那件；把「未上板」那句抄过来当自述不算数，页顶那条总口径
    （`fx/hwcheck.js` 的 `hwcheckUnverifiedNoteHTML`）同理——它一个字都不含 `_MULTI_INSTANCE_MARKER`。

    ⚠ 判据面是**声明了多实例、且这一格可用**的格（与「未上板」那条同款 `usable` 门）。
    不可用 = 配方残缺（`validate_recipes` 在加载期就红了），不是本条的判据面。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    multi = [m for m in manifests if m.multi_instance and m.multi_instance.max > 1]
    assert multi, "库内一件多实例模块都没有——本条前提变了（判据要跟着改，不是删掉）"

    missing: list[str] = []
    overstated: list[str] = []
    marked_up: list[str] = []
    covered: list[str] = []
    for manifest in multi:
        catalog = recipes.get(manifest.slug)
        assert catalog is not None, (
            f"{manifest.slug} 声明了多实例（max = {manifest.multi_instance.max}）"
            "却没有配方——页面连「这一件测不测得了」都说不出")
        for platform, section in catalog.sections.items():
            if not section.usable:
                continue
            where = f"{manifest.slug} × {platform}"
            # 两个出口都要：`sections_payload` = 页面读的那一份（前端逐条印成 `.hwcheck-hint`），
            # `render_recipe_section` = 检测程序那一份（注释块）。
            notes = [line for row in sections_payload([section]) for line in row["note"]]
            page = "\n".join(notes)
            program = "\n".join(render_recipe_section(section))
            covered.append(where)
            if _MULTI_INSTANCE_MARKER not in page or _MULTI_INSTANCE_MARKER not in program:
                missing.append(where)
            # 本单新写的那一句不许带 markdown 标记：前端 `esc()` 之后就是两个字面星号
            # （工单 02 的口径）。存量 354 条 note 都带标记，那是**另一张单**的账——
            # 这里只钉自己新写的（自述起点之后的那一句），别把整条 note 判成违规。
            honest = [line for line in notes if _MULTI_INSTANCE_PHRASE in line]
            assert honest, f"{where}：自述不在任何一条 note 里（下面的 missing 会说）"
            marked_up += [where] if any(
                "**" in line[line.index(_MULTI_INSTANCE_PHRASE):] for line in honest) else []
            overstated += [f"{where}：{hit}" for hit in _multi_instance_overclaims(page)]
    assert set(covered) == {"led × stm32", "led × mspm0", "key × stm32", "key × mspm0"}, (
        f"多实例格的清单变了（现在 {sorted(covered)}）——判据要按实况核一遍，"
        "不是把断言删掉")
    assert not marked_up, (
        "本单新写的那句带了 markdown 标记（页面上就是两个字面星号）：" + str(marked_up))
    assert not missing, (
        "这些格声明了多实例，页面上却没说「" + _MULTI_INSTANCE_MARKER + "」：" + str(missing)
        + "——补一条放在平台说明里（页面与检测程序都会印出来），整句要含"
          "「只验第一路」这一层意思，别只写「通道数」（那正是让人误读成"
          "「每一路都验过」的半句）"
    )
    assert not overstated, (
        "这些格把「只验一路」说成了「全验了」：" + str(overstated))


@pytest.mark.parametrize("slug", ["sr04", "jy61p", "xunji"])
def test_single_platform_pilot_modules_have_no_other_platform_recipe(slug):
    """单平台件（工单 09 的验收项之一）：**只有 mspm0 条目**的件不许出现 stm32 格。

    为什么单独立一条：给它们补一格 stm32 配方，`validate_recipes` 会判红
    （"该模块没有 stm32 平台条目"）——但那条红只在"有人写了"时才出现；这条
    反过来钉住"现在没有、也不该有"，同时把"检测页在 stm32 上选到它 = 如实
    报无本平台版本"这个事实写进测试（页面不产生"另一平台也能测"的误导）。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    by_slug = {m.slug: m for m in manifests}
    entry = by_slug[slug].platforms
    assert PLATFORM_STM32 not in entry, f"{slug} 居然有了 stm32 条目——本条前提变了"
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    catalog = recipes.get(slug)
    assert catalog is not None and PLATFORM_MSPM0 in catalog.sections
    assert PLATFORM_STM32 not in catalog.sections


def test_enum_constants_and_typedefs_are_real_interface_names():
    """**枚举常量与 typedef 名进白名单**（工单 09 修的一处真缺口）。

    判据面原本只收函数声明 / `#define` / extern 全局量——`typedef enum {
    ADC_Channel_0, … } ADCINx_enum;` 里的名字一个都不认。后果不是"少个名字"，
    而是配方被逼绕道：stm32 的 adc 读数只能写"整型变量 + 强转"，编译出 4 个
    `#188-D: enumerated type mixed with another type`（检测程序的验收线是
    0 error / **0 warning**），而直接写 `adc_get(ADC_1, ADC_Channel_0)` 反而
    过不了校验。这条钉住修好后的行为，并**同时**钉住"没变松"。
    """
    from contest_generator.hwcheck_recipe import interface_names

    headers = [(
        "ml_adc.h",
        "typedef enum\n{\n\tADC_1,\n\tADC_2,\n}ADCx_enum;\n\n"
        "typedef enum\n{\n\tADC_Channel_0,  //PA0\n\tADC_Channel_1,  //PA1\n}ADCINx_enum;\n\n"
        "uint16_t adc_get(ADCx_enum adc, ADCINx_enum adc_channel);\n",
    )]
    manifests = [_manifest("adc")]
    names = interface_names(manifests, REAL_LIBRARY, PLATFORM_STM32, headers)["adc"]
    for name in ("ADC_1", "ADC_Channel_0", "ADC_Channel_1", "ADCx_enum", "ADCINx_enum"):
        assert name in names, f"真实存在的枚举常量 / typedef 名被漏掉：{name}"
    # 注释里的词**不**该被当成接口（枚举体先剥注释再取名字）
    assert "PA0" not in names, "枚举体里的行尾注释被当成了接口名"
    # 没变松：编造的名字照旧不在
    assert "ADC_Channel_99" not in names
    assert "adc_read_magic" not in names


def _decode_like_c(escaped: str) -> bytes:
    """按 **C 的转义规则**解码一段字面量内容 → 字节（判"编译器会读出什么"）。

    这正是判据该用的量具：`\\x` 贪婪吃**所有**后续十六进制数字，八进制最多吃
    **三位**。于是"转义写法能不能被后面的字符吃掉"这件事，由"C 读出来的字节等不
    等于原字节"直接作证，不必去猜正则怎么写（本用例第一版就写歪过：拿
    `\\\\[0-7]{4,}` 去judge，把合法的 `\\2612g` 判成了违规）。
    """
    out = bytearray()
    index = 0
    while index < len(escaped):
        char = escaped[index]
        if char != "\\":
            out.extend(char.encode("utf-8"))
            index += 1
            continue
        nxt = escaped[index + 1] if index + 1 < len(escaped) else ""
        if nxt == "x":                       # 十六进制：贪婪吃光所有十六进制数字
            end = index + 2
            while end < len(escaped) and escaped[end] in "0123456789abcdefABCDEF":
                end += 1
            out.append(int(escaped[index + 2:end], 16) & 0xFF)
            index = end
            continue
        if nxt in "01234567":                # 八进制：最多三位
            end = index + 1
            while (end < len(escaped) and end < index + 4
                   and escaped[end] in "01234567"):
                end += 1
            out.append(int(escaped[index + 1:end], 8) & 0xFF)
            index = end
            continue
        if nxt == "n":
            out.append(0x0A)
        elif nxt == "r":
            out.append(0x0D)
        elif nxt == "t":
            out.append(0x09)
        elif nxt in ('"', "'", "\\"):
            out.append(ord(nxt))
        elif nxt:
            out.append(ord(nxt))
        index += 2
    return bytes(out)


def test_escape_c_string_is_byte_exact_and_never_greedy():
    """转义必须**逐字节还原**，而且不能被后面的字符吃掉（工单 05 的真机判例）。

    `\\x` 转义贪婪地吃十六进制数字：`±2g` 的字节是 `C2 B1 32 67`，写成
    `\\xc2\\xb12g` 就被编译器读成 `\\xb12`（一个越界转义）——ARMCC 报
    `#27-D: character value is out of range`，学生看到的字节也不对了。所以转义
    改用**三位八进制**（最多三位数字，天然自终止）。

    判据 = 按 **C 的规则**解码转义串，结果必须与原字符串的 UTF-8 字节**逐字节
    相等**（`_decode_like_c` 就是"编译器会读出什么"的量具）。
    """
    for text in ("±2g", "角度：3 轴", "通过：", "°1", "a±b", "", "量程 ±2000dps"):
        escaped = escape_c_string(text)
        assert all(ord(ch) < 128 for ch in escaped), escaped
        assert _decode_like_c(escaped) == text.encode("utf-8"), (text, escaped)
        # 贪婪判据：`\x` 后面出现第三个十六进制数字 = 会被连读（旧写法中招的形态）
        assert not re.search(r"\\x[0-9a-fA-F]*[0-9a-fA-F]{2}[0-9a-fA-F]",
                             escaped), escaped


def test_parse_and_reject_the_include_segment():
    """`include` 段：`{headers: [...]}`——只收**头文件名**（不带目录、.h 结尾）。

    为什么要这个段（本单真机判例）：检测程序直接调模块函数，而框架那套固定
    include 只覆盖通道与心跳——不声明器件模块的头，`main.c` 会报一串
    `#223-D function declared implicitly` 与 `#20 identifier undefined`（实测
    7 个 error）。
    """
    section = parse_recipes(_document((
        "ml_mpu6050", PLATFORM_STM32,
        _section(include={"headers": ["ml_mpu6050.h", "ml_i2c.h"]}))))[
        "ml_mpu6050"][PLATFORM_STM32]
    assert section.include == ("ml_mpu6050.h", "ml_i2c.h")
    for bad in ("ml_libs/ml_mpu6050.h", "ml_mpu6050.hpp", "ml_mpu6050"):
        with pytest.raises(HwCheckError) as exc:
            parse_recipes(_document((
                "ml_mpu6050", PLATFORM_STM32,
                _section(include={"headers": [bad]}))))
        assert "include.headers" in str(exc.value)


def test_validate_rejects_an_include_that_is_not_in_the_library():
    """头名写错 → 配方校验当场红；写对 → 过（判据面 = 库内 / 母版的头名清单）。

    判据面刻意**不读盘**（`platform_header_names` 只吃 manifest 声明的文件名与
    母版头路径）：真实可解析性由生成门禁的 include 解析门兜底，两处都在。
    """
    from contest_generator.hwcheck_recipe import (
        platform_header_names,
        validate_recipes,
    )

    with_header = ModuleManifest.from_dict({
        "slug": "ml_mpu6050", "description": "测试件", "dependencies": [],
        "platforms": {PLATFORM_STM32: {
            "files": ["ml_libs/ml_mpu6050.h"], "verified": True,
            "hardware_bound": False, "notes": "", "pins": []}},
    })
    interfaces = _interfaces("ml_mpu6050", {"MPU6050_Init"})
    headers = {
        PLATFORM_STM32: platform_header_names(
            [with_header], PLATFORM_STM32, [("ml_libs/ml_i2c.h", "")])
    }
    assert {"ml_mpu6050.h", "ml_i2c.h"} <= headers[PLATFORM_STM32]

    def _recipe(header: str):
        return parse_recipes(_document((
            "ml_mpu6050", PLATFORM_STM32,
            _section(include={"headers": [header]},
                     init={"calls": ["MPU6050_Init()"]}, init_expect=""))))

    validate_recipes(
        _recipe("ml_mpu6050.h"), [with_header], interfaces, headers)
    validate_recipes(
        _recipe("ml_i2c.h"), [with_header], interfaces, headers)
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(
            _recipe("ml_mpu0650.h"), [with_header], interfaces, headers)
    assert "ml_mpu0650.h" in str(exc.value)
    # 母版不可用（这次没给头名清单）= 判不了就不判，不冤枉好配方
    validate_recipes(_recipe("ml_mpu0650.h"), [with_header], interfaces, {})


def test_real_library_mpu6050_declares_the_headers_its_calls_need():
    """真库那一份必须声明器件头与跨模块前置头（否则产物编不过）。

    判据落在数据上：stm32 侧要 `ml_mpu6050.h`（驱动 API + extern 全局量）与
    `ml_i2c.h`（前置 `I2C_Init` 的声明——`ml_mpu6050.h` 自己 include 了它，
    但检测程序直接调，写出来才不依赖传递包含）；mspm0 侧要 `mpu_port.h`
    （`DMP_Init` / `DMP_Read_Data` 的声明）。
    """
    catalog = _real_mpu()
    stm32 = catalog.for_platform(PLATFORM_STM32)
    mspm0 = catalog.for_platform(PLATFORM_MSPM0)
    assert set(stm32.include) == {"ml_mpu6050.h", "ml_i2c.h"}, stm32.include
    assert set(mspm0.include) == {"mpu_port.h"}, mspm0.include


def test_real_library_channel_module_recipes_declare_their_headers():
    """通道模块的配方必须**自己**声明头（工单 hwcheck-pin-conflict-exit/01 实测）。

    为什么：框架那几行 include 只覆盖"勾了那个通道"的形态（`oled.h` 只在
    OLED 通道打开时进 main.c）。而器件挑选里也能把 oled 当**器件**选——那时通道
    可能没勾，配方小节照样渲染，头却没人 include → tiarmclang 一串
    `call to undeclared function`（实测 mspm0 选 oled 当器件 + 只勾串口 = 4 warning，
    验收线是 0 warning）。debug_uart 的配方早就自己声明了，oled 靠通道 include
    蒙混过关——本单把那条路打通之后才暴露。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    for slug in HWCHECK_CHANNELS:
        catalog = recipes.get(slug)
        assert catalog is not None, f"{slug} 是通道模块，却没有配方"
        for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
            section = catalog.for_platform(platform)
            if section is None:
                continue
            assert section.include, (
                f"{slug}:{platform} 的配方没声明 include——通道没勾时它的调用"
                f"就是隐式声明（0 warning 验收线直接破）"
            )


def test_real_library_led_recipe_clamps_to_channel_zero_on_mspm0():
    """led 专精的平台差异（票面明写）：stm32 走三色通道宏、mspm0 只走通道 0。

    判据不是"配方里写了什么字"而是**真库数据**：地猛星驱动会把越界通道静默
    钳回通道 0（led_instances.h 的注释），所以 mspm0 的**调用面**（init /
    prereq / read）不得出现 `LED_YELLOW` / `LED_GREEN`——那会让学生以为三路
    都测了。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    mspm0 = recipes["led"].for_platform(PLATFORM_MSPM0)
    assert mspm0 is not None
    calls = " ".join(
        (*mspm0.init, *mspm0.prereq, *(item.expression for item in mspm0.read)))
    assert "LED_YELLOW" not in calls
    assert "LED_GREEN" not in calls
    assert any("LED_RED" in call for call in mspm0.init), (
        "mspm0 的 led 配方应当只测通道 0（LED_RED）")
    # 平台差异（越界通道被钳回 0）必须写进 note——它直接印到检测页。
    # ⚠ 这里刻意**只查 note**、不查整份小节：note 本来就该提到"别写
    # LED_YELLOW / LED_GREEN"，对整份配方做子串否定会把正确的说明判成违规。
    notes = " ".join(mspm0.note)
    assert "钳" in notes or "通道 0" in notes, notes


# ---------------------------------------------------------------------------
# 工单 module-hwcheck/05：局部变量声明 + extern 全局量（平台不对称的地基）
# ---------------------------------------------------------------------------


def test_parse_and_render_local_declarations_before_every_action():
    """`locals` 段：声明的变量排在**所有动作之前**（探头要用它们装角度）。

    为什么必须是小节级而不是塞进 `read`：mspm0 的探头本身就是
    `DMP_Read_Data(&pitch, &roll, &yaw)`——**探头那一步就要把角度搬进变量**，
    声明晚于它就编不过（`pitch` 未声明）。
    """
    section = parse_recipes(_document((
        "ml_mpu6050", PLATFORM_MSPM0,
        _section(
            locals={"declarations": ["float pitch = 0", "float roll = 0"]},
            prereq={"calls": ["some_prereq()"]},
            init={"calls": ["DMP_Init()"]}, init_expect="0",
            probe={"calls": ["DMP_Read_Data(&pitch, &roll)"], "expect": "0"},
            read={"items": [{"expression": "(int)pitch", "unit": "度"}]},
        ))))[
        "ml_mpu6050"][PLATFORM_MSPM0]
    assert section.locals == ("float pitch = 0", "float roll = 0")
    code = "\n".join(render_recipe_section(section))
    assert "    float pitch = 0;" in code
    assert code.index("float pitch = 0;") < code.index("some_prereq();")
    assert code.index("float pitch = 0;") < code.index("DMP_Init();")
    assert code.index("float pitch = 0;") < code.index("DMP_Read_Data(&pitch, &roll);")


@pytest.mark.parametrize(
    "declaration",
    [
        "float a = 0, b = 0",        # 一次声明两个：名字看不全
        "float a = some_macro()",    # 初值不是数字字面量
        "char buf[16]",              # 数组
        "void (*cb)(void)",          # 函数指针
        "int",                       # 只有类型
    ],
)
def test_parse_rejects_a_local_declaration_it_cannot_read_statically(declaration):
    """`locals` 只收 `类型 名字 [= 数字]`：**名字必须能静态看出来**。

    这一条不是洁癖：声明的名字要进引用校验的白名单（读数表达式里写 `pitch` 是
    在读自己声明的变量），名字藏进 `float a = f()` 这类写法里，白名单就失灵了
    ——要么漏判、要么把整串都放行。
    """
    with pytest.raises(HwCheckError) as exc:
        parse_recipes(_document((
            "led", PLATFORM_MSPM0,
            _section(locals={"declarations": [declaration]}))))
    assert "locals.declarations" in str(exc.value)


def test_parse_rejects_a_duplicate_or_keyword_local_name():
    """同名声明两次 / 拿 C 关键字当变量名 → 当场红（编译期才发现就太晚了）。"""
    for declarations in (["float pitch = 0", "float pitch = 0"], ["int int = 0"]):
        with pytest.raises(HwCheckError) as exc:
            parse_recipes(_document((
                "led", PLATFORM_MSPM0,
                _section(locals={"declarations": declarations}))))
        assert "locals.declarations" in str(exc.value)


def test_validate_accepts_a_read_that_uses_a_declared_local():
    """自己声明的变量可以在读数表达式里用；**拼错的类型名仍要红**。"""
    from contest_generator.hwcheck_recipe import validate_recipes

    good = parse_recipes(_document((
        "ml_mpu6050", PLATFORM_MSPM0,
        _section(
            locals={"declarations": ["float pitch = 0"]},
            init={"calls": ["DMP_Init()"]}, init_expect="0",
            probe={"calls": ["DMP_Read_Data(&pitch)"], "expect": "0"},
            read={"items": [{"expression": "(int)pitch", "unit": "度"}]},
        ))))
    validate_recipes(
        good, [_manifest("ml_mpu6050", (PLATFORM_MSPM0,))],
        _interfaces("ml_mpu6050", {"DMP_Init", "DMP_Read_Data"}, PLATFORM_MSPM0))

    bad_type = parse_recipes(_document((
        "ml_mpu6050", PLATFORM_MSPM0,
        _section(locals={"declarations": ["folat pitch = 0"]}))))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(
            bad_type, [_manifest("ml_mpu6050", (PLATFORM_MSPM0,))],
            _interfaces("ml_mpu6050", {"DMP_Init"}, PLATFORM_MSPM0))
    assert "folat" in str(exc.value)


def test_validate_judges_each_platform_with_its_own_interface_list():
    """**按平台分开判**（工单 05 修的一处真缺陷）：stm32 的段只按 stm32 的清单查。

    复现的现场：配方一份覆盖两个平台，而两个平台的接口互不相认（stm32 有
    `MPU6050_Read` / `ax`，mspm0 有 `DMP_Init` / `DMP_Read_Data`）。早先只传一份
    清单 → 拿 mspm0 的清单去查 stm32 的段 → 误报"找不到 ax"，mspm0 预览直接 400。
    """
    from contest_generator.hwcheck_recipe import validate_recipes

    recipes = parse_recipes(_document(
        ("ml_mpu6050", PLATFORM_STM32,
         _section(init={"calls": ["MPU6050_Init()"]}, init_expect="",
                  probe={"calls": ["MPU6050_Read(WHO_AM_I)"], "expect": "0x68"},
                  read={"items": [{"expression": "ax", "unit": "LSB"}]})),
        ("ml_mpu6050", PLATFORM_MSPM0,
         _section(locals={"declarations": ["float pitch = 0"]},
                  init={"calls": ["DMP_Init()"]}, init_expect="0",
                  probe={"calls": ["DMP_Read_Data(&pitch)"], "expect": "0"},
                  read={"items": [{"expression": "(int)pitch", "unit": "度"}]})),
    ))
    manifests = [_manifest("ml_mpu6050", (PLATFORM_STM32, PLATFORM_MSPM0))]
    validate_recipes(recipes, manifests, {
        PLATFORM_STM32: {"ml_mpu6050": frozenset(
            {"MPU6050_Init", "MPU6050_Read", "WHO_AM_I", "ax", "LED_CHANNEL_COUNT"})},
        PLATFORM_MSPM0: {"ml_mpu6050": frozenset(
            {"DMP_Init", "DMP_Read_Data", "LED_CHANNEL_COUNT"})},
    })
    # 反向：把 stm32 的段错写成 mspm0 的接口 → 仍然当场红
    wrong = parse_recipes(_document((
        "ml_mpu6050", PLATFORM_STM32,
        _section(init={"calls": ["DMP_Init()"]}, init_expect="0"))))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(wrong, manifests, {
            PLATFORM_STM32: {"ml_mpu6050": frozenset({"MPU6050_Init"})},
            PLATFORM_MSPM0: {"ml_mpu6050": frozenset({"DMP_Init"})},
        })
    assert "DMP_Init" in str(exc.value)


def test_interface_names_includes_extern_globals_from_module_headers(tmp_path):
    """**模块的公开数据接口也是接口**：`extern int16_t ax, az;` 里的名字要认。

    真机判例（本单）：stm32 的 `ml_mpu6050.h` 用 `extern` 暴露六轴原始值，而
    生成门禁那套提取只收函数与宏——不补这一条，"配方读了模块头里真实存在的
    全局量"会被判成拼错（`ax` 找不到），读数就写不出来。
    """
    from contest_generator.hwcheck_recipe import interface_names

    modules = tmp_path / "library" / "modules"
    slug_dir = modules / "ml_mpu6050"
    (slug_dir / "ml_libs").mkdir(parents=True)
    (slug_dir / "ml_libs" / "ml_mpu6050.h").write_text(
        "#ifndef _mpu6050_h\n#define _mpu6050_h\n"
        "struct int_param_s { int pin; };\n"
        "extern int16_t ax, ay, az, gx, gy, gz;\n"
        "extern const char *label;\n"
        "extern struct int_param_s param;\n"
        "void MPU6050_Init(void);\n"
        "#endif\n",
        encoding="utf-8",
    )
    manifest = ModuleManifest.from_dict({
        "slug": "ml_mpu6050",
        "description": "测试件",
        "dependencies": [],
        "platforms": {
            PLATFORM_STM32: {
                "files": ["ml_libs/ml_mpu6050.h"], "verified": True,
                "hardware_bound": False, "notes": "", "pins": [],
            },
        },
    })
    names = interface_names([manifest], modules, PLATFORM_STM32)
    assert {"ax", "ay", "az", "gx", "gy", "gz"} <= names["ml_mpu6050"]
    assert "label" in names["ml_mpu6050"]
    # 结构体标签名不是变量名（`extern struct int_param_s param;` 里 `param` 才是）
    assert "int_param_s" not in names["ml_mpu6050"]
    assert "param" in names["ml_mpu6050"]
    assert "MPU6050_Init" in names["ml_mpu6050"]


def test_validate_covers_the_prereq_segment_across_modules():
    """前置调用（工单 05 起纳入判据）：**可以来自别的模块 / 母版**，但必须真存在。

    stm32 侧的现场：`ml_mpu6050` 要先调母版的 `I2C_Init()` 初始化软 I2C 总线
    （它自己不初始化），而 `I2C_Init` 是 ml_i2c 的接口、不在本模块的头里——
    所以判据面取"该平台库内任何模块 ∪ 母版"的并集。
    """
    from contest_generator.hwcheck_recipe import validate_recipes

    recipes = parse_recipes(_document((
        "ml_mpu6050", PLATFORM_STM32,
        _section(prereq={"calls": ["I2C_Init()"]},
                 init={"calls": ["MPU6050_Init()"]}, init_expect=""))))
    manifests = [_manifest("ml_mpu6050"), _manifest("other")]
    validate_recipes(recipes, manifests, {
        PLATFORM_STM32: {
            "ml_mpu6050": frozenset({"MPU6050_Init", "LED_CHANNEL_COUNT"}),
            "other": frozenset({"I2C_Init"}),      # 别的模块提供的
        },
    })
    typos = parse_recipes(_document((
        "ml_mpu6050", PLATFORM_STM32,
        _section(prereq={"calls": ["I2C_Initt()"]},
                 init={"calls": ["MPU6050_Init()"]}, init_expect=""))))
    with pytest.raises(HwCheckError) as exc:
        validate_recipes(typos, manifests, {
            PLATFORM_STM32: {
                "ml_mpu6050": frozenset({"MPU6050_Init", "LED_CHANNEL_COUNT"}),
                "other": frozenset({"I2C_Init"}),
            },
        })
    assert "I2C_Initt" in str(exc.value)


# ---------------------------------------------------------------------------
# 工单 05：真实库的 MPU6050 配方把平台不对称如实讲清楚
# ---------------------------------------------------------------------------


def _real_mpu():
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    recipes = load_recipes(
        REAL_LIBRARY, manifests, _library_interfaces_all(REAL_LIBRARY, manifests))
    return recipes["ml_mpu6050"]


def test_real_library_mpu6050_recipes_pass_the_reference_guard():
    """真库那一份能读出来 = 每条引用的名字都在**对应平台**的头文件里。

    这条是本单的核心守卫在真数据上的落点：stm32 侧写 `ax` / `WHO_AM_I`，mspm0
    侧写 `DMP_Init` / `DMP_Read_Data`——任何一处拼错，`load_recipes` 当场红。
    """
    catalog = _real_mpu()
    assert catalog.for_platform(PLATFORM_STM32) is not None
    assert catalog.for_platform(PLATFORM_MSPM0) is not None


def test_real_library_mpu6050_stm32_judges_comm_and_shows_raw_axes_only():
    """stm32：**自己带探头**判通信 + 只显示原始六轴（**不给角度**）。

    票面两条硬要求：① 探头自证（不信驱动的初始化返回值——库里这份 stm32 驱动
    不做身份校验、通信失败也照样往下写寄存器）：读 WHO_AM_I 比对 0x68；
    ② 前端与产出的注释都要写明"本平台没有姿态解算"，避免学生把"显示不了角度"
    误判成"我接错了"。
    """
    stm32 = _real_mpu().for_platform(PLATFORM_STM32)
    assert stm32 is not None
    # ① 前置调用：既有驱动不初始化总线，检测程序必须先起软 I2C
    assert any("I2C_Init" in call for call in stm32.prereq), stm32.prereq
    # ② 探头：寄存器读身份，比对期望值（期望值落在渲染出的比较式里）
    assert stm32.probe is not None
    assert stm32.probe.expect == "0x68"
    assert any("WHO_AM_I" in call for call in stm32.probe.calls), stm32.probe.calls
    # ③ 读数 = 原始六轴（驱动的 extern 全局量），**没有**角度
    read = [item.expression for item in stm32.read]
    assert read == ["ax", "ay", "az", "gx", "gy", "gz"], read
    assert stm32.init_expect == "", "MPU6050_Init() 是 void，不许编一个期望值"
    notes = " ".join(stm32.note)
    assert "没有姿态解算" in notes
    assert "jy61p" in notes or "imu_uart" in notes, "要给出改姿态模块的出路"


def test_real_library_mpu6050_mspm0_shows_dmp_angles_split_into_integers():
    """mspm0：官方 DMP 出 pitch / roll / yaw，且**没浮点显示接口**→ 拆整数 / 小数。

    判据落在数据上：`locals` 声明三个 float（探头要把角度搬进去）、探头就是
    `DMP_Read_Data(&pitch, &roll, &yaw)`（既证通信通、又取到数据）、每条读数
    都是**整数表达式**（渲染走 `hwcheck_report_int`）。
    """
    mspm0 = _real_mpu().for_platform(PLATFORM_MSPM0)
    assert mspm0 is not None
    assert mspm0.locals == ("float pitch = 0", "float roll = 0", "float yaw = 0")
    assert mspm0.init_expect == "0"          # DMP_Init 的返回值是板上判定入口之一
    assert mspm0.probe is not None
    assert mspm0.probe.expect == "0"         # 探头：真的从 FIFO 读回一帧
    assert any("DMP_Read_Data" in call for call in mspm0.probe.calls)
    read = [item.expression for item in mspm0.read]
    # 三个角度 × （整数部分 + 小数第一位）
    assert len(read) == 6, read
    for angle in ("pitch", "roll", "yaw"):
        assert f"(int){angle}" in read, (angle, read)
        assert f"(int)(({angle} - (int){angle}) * 10)" in read, (angle, read)
    notes = " ".join(mspm0.note)
    assert "没有浮点显示接口" in notes
    assert "拼起来" in notes or "拼起来看" in notes, "拆开显示必须说清怎么读"
    assert "SysTick" in notes, "DMP 端口自开 SysTick 中断这件事要如实写在页面上"
    # 第③层「只回显 + 给正常范围参考」（spec 判据三层）也要落在这一侧：
    # 没给参考的话，"角度显示得对不对"学生无从判断（stm32 侧给了 LSB 换算）。
    assert "静止" in notes and "≈ 0" in notes, "要给「静止时角度应≈0」的参考"
    assert "漂移" in notes, "yaw 漂移是这套 DMP 的物理事实，要说清不是坏了"


def test_real_library_platform_asymmetry_is_visible_on_both_sides():
    """**平台不对称如实呈现**（spec）：两边都要说清"这一侧有什么、没有什么"。

    mspm0 侧要说"与 stm32 不同（那边只有原始六轴）"；stm32 侧要说"没有姿态
    解算、要角度去 mspm0 或用串口姿态模块"。只在一侧写，另一侧的用户就会把
    "能力缺失"读成"自己接错了"。
    """
    catalog = _real_mpu()
    stm32_notes = " ".join(catalog.for_platform(PLATFORM_STM32).note)
    mspm0_notes = " ".join(catalog.for_platform(PLATFORM_MSPM0).note)
    assert "没有姿态解算" in stm32_notes
    assert "原始六轴" in stm32_notes
    assert "DMP" in mspm0_notes
    assert "原始六轴" in mspm0_notes, "mspm0 侧也要点明与 stm32 的差别"
