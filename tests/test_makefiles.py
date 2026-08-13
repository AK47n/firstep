"""CCS Debug/makefile 集模板测试（工单 mspm0-build-makefiles/01 验收项）。

覆盖：渲染确定性（同参必同文）、模块过滤（未选模块不出现）、三件套路径
参数化（SDK / 编译器 / SysConfig CLI 各入各文件、零硬编码）、落盘完整性
（全文件集 + 返回清单与渲染一致）、空模块集 / 平铺模块（subdir 空串）形态、
recipe 行 tab 契约（gmake 语法硬要求）。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.makefiles import render_makefile_set, write_makefile_set

SDK = "C:/ti/ccs2051/mspm0_sdk_2_10_00_04"
COMPILER = "C:/ti/ccs2050/ccs/tools/compiler/ti-cgt-armllvm_4.0.4.LTS"
SYSCFG = "C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat"
PROJ = Path("C:/work/out_2024H_mspm0")

# 模块源形状（生成侧从 manifest 推导）：(slug, 子目录, (源文件名, ...))——
# ml_mpu6050 的 ml_libs 子目录形态天然覆盖
SOURCES = (
    ("dht11", "code", ("dht11.c",)),
    ("delay", "code", ("delay.c",)),
    (
        "ml_mpu6050",
        "ml_libs",
        ("inv_mpu.c", "inv_mpu_dmp_motion_driver.c", "mpu_port.c"),
    ),
)


def _render(**overrides):
    args = dict(
        module_sources=SOURCES,
        proj_dir=PROJ,
        sdk_dir=SDK,
        compiler_dir=COMPILER,
        sysconfig_cli=SYSCFG,
    )
    args.update(overrides)
    return render_makefile_set(**args)


# ---------------------------------------------------------------------------
# 渲染确定性 + 文件集形状
# ---------------------------------------------------------------------------


def test_render_is_deterministic():
    """同参必同文（模板确定性钉死）：两次渲染逐字节一致 + 文件集形状完整。"""
    first = _render()
    second = _render()
    assert first == second
    assert set(first) == {
        "sources.mk",
        "objects.mk",
        "subdir_vars.mk",
        "subdir_rules.mk",
        "modules/dht11/code/subdir_vars.mk",
        "modules/dht11/code/subdir_rules.mk",
        "modules/delay/code/subdir_vars.mk",
        "modules/delay/code/subdir_rules.mk",
        "modules/ml_mpu6050/ml_libs/subdir_vars.mk",
        "modules/ml_mpu6050/ml_libs/subdir_rules.mk",
        "makefile",
    }


def test_module_filtering_only_selected_modules_appear():
    """模块条目 = 选中集（决策记录 2）：只给 dht11 → delay / ml_mpu6050 的
    条目与目录文件都不出现。"""
    one = _render(module_sources=(("dht11", "code", ("dht11.c",)),))
    assert "modules/dht11/code/subdir_vars.mk" in one
    assert "modules/delay" not in one["makefile"]
    assert "ml_mpu6050" not in one["makefile"]
    assert "modules/delay/code/subdir_vars.mk" not in one
    # 全量渲染则三者俱在（对照，防过滤写反）
    full = _render()
    assert "modules/delay/code/subdir_vars.mk" in full
    assert "modules/ml_mpu6050/ml_libs/subdir_vars.mk" in full


# ---------------------------------------------------------------------------
# 三件套路径参数化（零硬编码）
# ---------------------------------------------------------------------------


def test_toolchain_paths_parameterized():
    """SDK / 编译器 / SysConfig CLI 各入各文件；换参数 → 输出跟随。"""
    rendered = _render()
    assert SDK in rendered["subdir_vars.mk"]  # startup 路径（C_SRCS）
    assert SDK in rendered["subdir_rules.mk"]  # product.json + 编译 INC
    assert SYSCFG in rendered["subdir_rules.mk"]  # SysConfig CLI 调用
    assert COMPILER in rendered["subdir_rules.mk"]  # tiarmclang 编译行
    assert f"CG_TOOL_ROOT := {COMPILER}" in rendered["makefile"]
    assert f'-Wl,-i"{SDK}/source"' in rendered["makefile"]  # 链接搜索路径
    assert f'-Wl,-i"{COMPILER}/lib"' in rendered["makefile"]

    alt = _render(
        sdk_dir="X:/sdk_alt",
        compiler_dir="Y:/cc_alt",
        sysconfig_cli="Z:/sc_alt.bat",
    )
    assert "X:/sdk_alt" in alt["subdir_vars.mk"]
    assert SDK not in alt["subdir_vars.mk"]
    assert "Z:/sc_alt.bat" in alt["subdir_rules.mk"]
    assert "CG_TOOL_ROOT := Y:/cc_alt" in alt["makefile"]
    assert "X:/sdk_alt" not in alt["objects.mk"]  # 静态文件无路径


def test_project_dir_parameterized():
    """工程根路径入参（INC / SysConfig --script / 链接 -i）：换工程根输出跟随。"""
    other_dir = Path("D:/another/out")
    other = _render(proj_dir=other_dir)
    text = "\n".join(other.values())
    assert str(PROJ) not in text
    assert str(other_dir) in text  # Windows 下 str(Path) 是反斜杠形态


# ---------------------------------------------------------------------------
# 落盘完整性
# ---------------------------------------------------------------------------


def test_write_makefile_set_writes_full_file_set(tmp_path):
    out = tmp_path / "proj"
    out.mkdir()
    written = write_makefile_set(out, SOURCES, SDK, COMPILER, SYSCFG)
    rendered = render_makefile_set(SOURCES, out.resolve(), SDK, COMPILER, SYSCFG)
    assert set(written) == set(rendered)  # 返回清单 = 渲染清单
    for rel, text in rendered.items():
        assert (out / "Debug" / rel).read_text(encoding="utf-8") == text


def test_empty_module_sources_still_writes_makefile(tmp_path):
    """空模块集（slugs=() 最小工程）：makefile 照写，仅根三源进编译。"""
    out = tmp_path / "proj"
    out.mkdir()
    write_makefile_set(out, (), SDK, COMPILER, SYSCFG)
    makefile = (out / "Debug" / "makefile").read_text(encoding="utf-8")
    assert "modules/" not in makefile
    assert "./ti_msp_dl_config.o \\" in makefile
    assert "./startup_mspm0g350x_ticlang.o \\" in makefile
    assert "./main.o \\" in makefile


def test_flat_module_without_subdir(tmp_path):
    """平铺模块（subdir 空串，库内 delay.c 直放模块根形态）：目录文件落在
    Debug/modules/<slug>/，无空目录段（modules// 双斜杠）。"""
    out = tmp_path / "proj"
    out.mkdir()
    written = write_makefile_set(
        out, (("delay", "", ("delay.c",)),), SDK, COMPILER, SYSCFG
    )
    assert "modules/delay/subdir_vars.mk" in written
    makefile = (out / "Debug" / "makefile").read_text(encoding="utf-8")
    assert "-include modules/delay/subdir_vars.mk" in makefile
    assert "./modules/delay/delay.o \\" in makefile
    assert "modules//" not in makefile
    vars_text = (
        out / "Debug" / "modules" / "delay" / "subdir_vars.mk"
    ).read_text(encoding="utf-8")
    assert "C_SRCS += \\\n../modules/delay/delay.c" in vars_text


# ---------------------------------------------------------------------------
# makefile 本体契约
# ---------------------------------------------------------------------------


def test_recipe_lines_use_tabs():
    """recipe 行必须以 tab 开头（gmake 语法硬要求，空格即 "missing separator"）。"""
    rules = _render()["subdir_rules.mk"]
    for line in rules.splitlines():
        if "@echo" in line or "tiarmclang.exe" in line:
            assert line.startswith("\t"), f"recipe 行未用 tab：{line!r}"


def test_makefile_ordered_objs_root_first_then_modules():
    """链接顺序：根三源在前、模块对象随后（IDE 同款 ORDERED_OBJS）。"""
    text = _render()["makefile"]
    assert text.index("./ti_msp_dl_config.o") < text.index("./startup_mspm0g350x_ticlang.o")
    assert text.index("./startup_mspm0g350x_ticlang.o") < text.index("./main.o")
    assert text.index("./main.o") < text.index("./modules/dht11/code/dht11.o")
    assert "./modules/delay/code/delay.o \\" in text
    assert "./modules/ml_mpu6050/ml_libs/inv_mpu.o \\" in text


def test_makefile_has_clean_and_include_init_targets():
    """IDE 同款骨架：makefile.init / makefile.defs / makefile.targets 三个
    外部 include + clean 目标（反斜杠路径 cmd DEL 语义）。"""
    text = _render()["makefile"]
    assert "-include ../makefile.init" in text
    assert "-include ../makefile.defs" in text
    assert "-include ../makefile.targets" in text
    assert "clean:" in text
    assert 'modules\\dht11\\code\\dht11.o' in text  # clean 清单反斜杠形态
    assert 'modules\\dht11\\code\\dht11.d' in text
