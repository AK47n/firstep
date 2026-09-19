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
from pathlib import Path

import pytest

from contest_generator.hwcheck import HwCheckError
from contest_generator.hwcheck_recipe import (
    RECIPE_FILENAME,
    RecipeCatalog,
    RecipeConsole,
    RecipeProbe,
    RecipeRead,
    RecipeSection,
    c_string,
    load_recipes,
    parse_recipes,
    recipe_library_path,
    render_recipe_section,
    render_recipe_summary,
    resolve_sections,
)
from contest_generator.manifest import ModuleManifest
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

REAL_LIBRARY = Path(__file__).resolve().parents[1] / "library" / "modules"
REAL_MASTERS = Path(__file__).resolve().parents[1] / "library" / "masters"

# 真实库的 pilot 清单（spec「v1 专精范围」的本单两件）——地板断言的判据。
PILOT = (("led", PLATFORM_STM32), ("led", PLATFORM_MSPM0),
         ("oled", PLATFORM_STM32), ("oled", PLATFORM_MSPM0))


def _unescape_c(code: str) -> str:
    """渲染产物 → 人能读的文本：把 `\\xNN` 字节转义还原成字符。

    渲染器把非 ASCII 转义成 UTF-8 字节（ARMCC 的本地代码页会把原样中文串的
    收尾引号吞掉），所以断言"程序里说了什么"时先把转义还原——**判据是"学生
    看到的那句话在不在"**，不是"转义写法对不对"（转义写法本身另有专门断言）。
    """
    out = bytearray()
    index = 0
    while index < len(code):
        chunk = code[index:index + 4]
        if chunk.startswith("\\x") and len(chunk) == 4:
            try:
                out.append(int(chunk[2:], 16))
                index += 4
                continue
            except ValueError:
                pass
        out.extend(code[index].encode("utf-8"))
        index += 1
    return out.decode("utf-8", errors="replace")


def _section(**overrides) -> dict:
    """一条合法配方的最小形态（测试里按需覆盖字段）。

    段的形状统一是对象（`{calls: [...]}` / `{expressions: [...]}` /
    `{lines: [...]}`）——显式键让"这一段的这一项叫什么"在文件里看得见。
    """
    data = {
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


def _interfaces(slug: str, names: set[str]) -> dict[str, frozenset[str]]:
    """接口清单夹具（含默认配方读数列用的 LED_CHANNEL_COUNT——read 段的裸常量
    也过判据，所以夹具必须把它算进去，否则测的就不是本意的那条守卫）。"""
    return {slug: frozenset({"LED_CHANNEL_COUNT"} | set(names))}


def _library_interfaces(modules: Path, manifests, platform: str) -> dict[str, frozenset[str]]:
    """真实库的接口清单 = `hwcheck_recipe.interface_names`（含母版头）。

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

    ⚠ 中文字面量按 `c_string` **转义成 `\\xNN`**（ARMCC 5.06 按本地代码页解析
    源文件，原样中文串会把收尾引号吞掉、整份 main.c 编不过）——所以断言查的是
    转义后的写法，不是原文。这条本身就是"别改回转义"的守卫。
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
    interfaces = _library_interfaces(REAL_LIBRARY, manifests, platform)
    recipes = load_recipes(REAL_LIBRARY, manifests, interfaces)
    catalog = recipes.get(slug)
    assert catalog is not None, f"真实库缺配方：{slug}"
    hit = catalog.for_platform(platform)
    assert hit is not None, f"真实库缺配方：{slug} × {platform}"
    assert hit.usable, f"{slug} × {platform} 的配方是空壳"


def test_real_library_recipes_reference_only_real_interfaces():
    """真实库整份配方都过引用校验（本单的核心守卫在真数据上跑一遍）。

    `load_recipes` 带 interfaces 就会校验——能读出来即证明每一条引用的函数名
    都在对应模块对应平台的头文件里。这条同时是"配方随库演进"的守卫：模块
    改名 / 删接口而配方没跟上，这里当场红。
    """
    from contest_generator.library import list_modules

    manifests = list_modules(REAL_LIBRARY)
    for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
        interfaces = _library_interfaces(REAL_LIBRARY, manifests, platform)
        recipes = load_recipes(REAL_LIBRARY, manifests, interfaces)
        assert recipes, "真实库应当至少有 pilot 清单那两件的配方"
        for catalog in recipes.values():
            assert catalog.usable


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
        REAL_LIBRARY, manifests,
        _library_interfaces(REAL_LIBRARY, manifests, PLATFORM_MSPM0))
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
