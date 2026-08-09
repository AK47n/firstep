"""生成器核心：唯一的测试接缝。

输入（平台、已选 manifest 集、母版目录、输出目录、main.c 内容）
→ 输出完整工程目录。断言输出目录的结构与文件内容。
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.generator import (
    FencedMainCError,
    GeneratorError,
    MacroRedefinitionError,
    MasterNotFoundError,
    MissingModuleFilesError,
    ModuleCorpus,
    ModuleFile,
    ModuleSelfIncludeError,
    OutputDirNotEmptyError,
    UndefinedCallsError,
    UnresolvedIncludeError,
    _check_main_calls,
    _check_macro_conflicts,
    _check_module_files,
    _check_module_self_include,
    _check_unresolved_includes,
    build_module_corpus,
    generate_project,
    resolve_topic_context,
)
from contest_generator.ccs import INCLUDE_OPTION_SUPERCLASSES, _SETTINGS_MODULE_ID
from contest_generator.library import list_modules
from contest_generator.llm import LLMError
from contest_generator.manifest import ModuleManifest
from contest_generator.master_store import MasterError
from contest_generator.patchers import (
    PLATFORM_MSPM0,
    PLATFORM_STM32,
    PatcherRegistry,
    include_search_dirs,
)
from contest_generator.reference_library import ReferenceError
from contest_generator.topic_library import TopicError
from tests.fakes import (
    DHT11_H,
    DHT11_MSPM0_C,
    DHT11_STM32_C,
    MAIN_SKELETON,
    OLED_H,
    OLED_STM32_C,
    RecordingPatcher,
    _add_module,
    make_fake_ccs_theia_master_project,
    make_fake_master_project,
    make_fake_module_library,
)
from tests.generate_wiring_fakes import (
    KIT_REFERENCE_ID,
    TOPIC_PROBLEM_TEXT,
    TOPIC_REFERENCE_ID,
    UWB_REFERENCE_ID,
    make_fake_reference_library,
    make_fake_topic_library,
    make_kit_candidate_module,
    make_topic_specific_module,
)


def test_generate_project_full_flow_returns_summary(fake_module_library, tmp_path):
    """完整流程接缝：选模块 → 定位母版 → 生成 → 摘要，一步返回只读摘要。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    output_dir = tmp_path / "out"

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=output_dir,
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )

    # 依赖 delay 被自动展开（resolve_selection），落盘与摘要一次给齐
    assert (output_dir / "main.c").is_file()
    assert (output_dir / "modules" / "delay" / "delay.c").is_file()
    assert "modules/dht11/stm32/src" in summary.include_dirs
    assert any(slug == "delay" for slug, _ in summary.modules)


def test_generate_project_master_missing_fails(fake_module_library, tmp_path):
    """母版库里没有该平台母版——流程入口就报错，不产出残缺工程。"""
    with pytest.raises(MasterNotFoundError, match="母版"):
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=tmp_path / "out",
            module_library_dir=fake_module_library,
            masters_dir=tmp_path / "masters",
        )

    assert not (tmp_path / "out").exists()


def test_generate_project_rejects_platform_path_traversal(fake_module_library, tmp_path):
    """借平台名逃出母版库在入口处被拦：平台先过母版库的平台名校验。"""
    with pytest.raises(MasterError, match="非法平台名"):
        generate_project(
            platform="../evil",
            slugs=["dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=tmp_path / "out",
            module_library_dir=fake_module_library,
            masters_dir=tmp_path / "masters",
        )


def test_generate_stm32_outputs_complete_project(make_project, tmp_path):
    result = make_project(output_dir=tmp_path / "out")

    assert result == tmp_path / "out"
    # 母版文件就位
    assert (result / "project.uvprojx").exists()
    assert (result / "inc/stm32f10x_conf.h").exists()
    assert (result / "src/system_stm32f10x.c").exists()
    assert not (result / ".git").exists()
    # .uvprojx：模块源文件注册进工程树，include path 已填好，设备型号保留
    root = ET.parse(result / "project.uvprojx").getroot()
    assert (
        root.findtext("Targets/Target/TargetOption/TargetCommonOption/Device")
        == "STM32F103C8"
    )
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    assert [f.findtext("FilePath") for f in modules.findall("Files/File")] == [
        ".\\modules\\dht11\\stm32\\src\\dht11.c",
        ".\\modules\\oled\\stm32\\src\\oled.c",
    ]
    include_path = root.findtext(
        "Targets/Target/TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
    )
    assert include_path == (
        ".\\inc;.\\src"
        ";.\\modules\\dht11\\stm32\\src;.\\modules\\dht11\\inc"
        ";.\\modules\\oled\\stm32\\src;.\\modules\\oled\\inc"
    )
    # main.c 落位，替换母版旧 main
    assert (result / "main.c").read_text(encoding="utf-8") == (
        "int main(void) { float t = dht11_read(); while (1); }\n"
    )
    # 模块文件按平台版本复制，内容原样
    assert (
        result / "modules/dht11/stm32/src/dht11.c"
    ).read_text(encoding="utf-8") == DHT11_STM32_C
    assert (result / "modules/dht11/inc/dht11.h").read_text(encoding="utf-8") == DHT11_H
    assert (
        result / "modules/oled/stm32/src/oled.c"
    ).read_text(encoding="utf-8") == OLED_STM32_C
    assert (result / "modules/oled/inc/oled.h").read_text(encoding="utf-8") == OLED_H


def test_generate_mspm0_outputs_complete_project(make_ccs_project, tmp_path):
    result = make_ccs_project(output_dir=tmp_path / "out")

    assert result == tmp_path / "out"
    # 母版文件就位（.project 是 CCS 打开工程的必需文件）
    assert (result / ".project").exists()
    assert (result / "project.cproject").exists()
    assert (result / "inc/mspm0g3507.h").exists()
    assert (result / "mspm0g3507.cmd").exists()
    assert not (result / ".git").exists()
    # .cproject：include path 已填好，模块目录有 sourceEntry 覆盖
    root = ET.parse(result / "project.cproject").getroot()
    assert _ccs_include_values(root, "Debug") == [
        "${PROJECT_LOC}/inc",
        "${PROJECT_LOC}/driverlib",
        "${PROJECT_LOC}/modules/dht11/mspm0/src",
        "${PROJECT_LOC}/modules/dht11/inc",
        "${PROJECT_LOC}/modules/delay",
    ]
    assert _ccs_include_values(root, "Release") == [
        "${PROJECT_LOC}/inc",
        "${PROJECT_LOC}/modules/dht11/mspm0/src",
        "${PROJECT_LOC}/modules/dht11/inc",
        "${PROJECT_LOC}/modules/delay",
    ]
    assert _ccs_source_entry_names(root, "Debug") == [""]  # 根条目覆盖 modules/
    # main.c 落位，替换母版旧 main
    assert (result / "main.c").read_text(encoding="utf-8") == (
        "int main(void) { float t = dht11_read(); while (1); }\n"
    )
    # 模块文件按平台版本复制，内容原样
    assert (
        result / "modules/dht11/mspm0/src/dht11.c"
    ).read_text(encoding="utf-8") == DHT11_MSPM0_C
    assert (result / "modules/dht11/inc/dht11.h").read_text(encoding="utf-8") == DHT11_H
    assert (result / "modules/delay/delay.c").read_text(encoding="utf-8") == (
        "#include \"delay.h\"\n/* delay */\nvoid delay_ms(int ms);\n"
    )
    assert (result / "modules/delay/delay.h").read_text(encoding="utf-8") == (
        "#pragma once\nvoid delay_ms(int ms);\n"
    )


def _ccs_build_configuration(root: ET.Element, name: str) -> ET.Element:
    """与生产同款的双格式走查（classic settings 内 cdtBuildSystem 元素 / Theia
    独立 cdtBuildSystem storageModule），按配置名取 configuration。"""
    from contest_generator.ccs import _BUILD_SYSTEM_MODULE_ID

    for storage in root.findall("storageModule"):
        if storage.get("moduleId") != _SETTINGS_MODULE_ID:
            continue
        for cconfig in storage.findall("cconfiguration"):
            for inner in cconfig.findall("storageModule"):
                build_system = inner.find("cdtBuildSystem")
                if build_system is None:
                    if inner.get("moduleId") != _BUILD_SYSTEM_MODULE_ID:
                        continue
                    build_system = inner
                for configuration in build_system.findall("configuration"):
                    if configuration.get("name") == name:
                        return configuration
    raise AssertionError(f"没有名为 {name} 的 build configuration")


def _ccs_include_option(configuration: ET.Element) -> ET.Element:
    """与生产同款双位置：classic 直接子元素 / Theia 在 <tool> 元素内。"""
    for option in configuration.findall("folderInfo/toolChain/option"):
        if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
            return option
    for tool in configuration.findall("folderInfo/toolChain/tool"):
        for option in tool.findall("option"):
            if option.get("superClass") in INCLUDE_OPTION_SUPERCLASSES:
                return option
    raise AssertionError("没有 include 选项")


def _ccs_include_values(root: ET.Element, config_name: str) -> list[str]:
    configuration = _ccs_build_configuration(root, config_name)
    option = _ccs_include_option(configuration)
    values = [v.get("value") for v in option.findall("listOptionValue")]
    return [v for v in values if v is not None]


def _ccs_source_entry_names(root: ET.Element, config_name: str) -> list[str]:
    configuration = _ccs_build_configuration(root, config_name)
    names = [e.get("name") for e in configuration.findall("sourceEntries/entry")]
    return [n for n in names if n is not None]


def test_generate_copies_platform_specific_version(
    make_ccs_project, mspm0_selection, tmp_path
):
    dht11 = [m for m in mspm0_selection if m.slug == "dht11"]  # dht11 双平台都有版本
    result = make_ccs_project(manifests=dht11, output_dir=tmp_path / "out")

    assert (
        result / "modules/dht11/mspm0/src/dht11.c"
    ).read_text(encoding="utf-8") == DHT11_MSPM0_C
    # 另一个平台的版本不进来
    assert not (result / "modules/dht11/stm32").exists()


def test_generate_unknown_platform_fails_before_touching_output(make_project, tmp_path):
    from contest_generator.patchers import UnknownPlatformError

    output_dir = tmp_path / "out"

    with pytest.raises(UnknownPlatformError, match="esp32"):
        make_project(platform="esp32", output_dir=output_dir)

    assert not output_dir.exists()


def test_generate_rejects_main_c_calling_undefined_functions(make_project, tmp_path):
    """生成器落盘前的静态自检兜底：不存在调用明确报错，不产出残缺工程。"""
    output_dir = tmp_path / "out"

    with pytest.raises(UndefinedCallsError, match="dht11_init") as excinfo:
        make_project(
            main_c_content="int main(void) { dht11_init(); while (1); }\n",
            output_dir=output_dir,
        )

    assert "头文件" in str(excinfo.value)
    assert not output_dir.exists()


def test_generate_missing_module_file_fails_with_clear_message(
    fake_module_library, make_project, tmp_path
):
    broken = ModuleManifest.load(fake_module_library / "broken")
    output_dir = tmp_path / "out"

    with pytest.raises(MissingModuleFilesError, match="broken") as excinfo:
        make_project(manifests=[broken], output_dir=output_dir)

    assert "stm32/src/broken.c" in str(excinfo.value)
    # 不产出残缺工程：输出目录不被创建
    assert not output_dir.exists()


# ---------------------------------------------------------------------------
# 语料门禁（工单 02）：纯内存构造 ModuleCorpus 直喂五道门，无盘上夹具。
# 门禁不再读盘——文件文本全部来自语料，唯一例外是 include 解析要查盘上
# 搜索目录（模拟 Keil 搜索，见 test_unresolved_include_checks_master_search_dirs）。
# ---------------------------------------------------------------------------


def _memory_corpus(
    tmp_path,
    *,
    main_c: str = "int main(void) { while (1); }\n",
    module_texts: list[tuple[str, str, str]] | None = None,
    missing_files: list[tuple[str, str]] | None = None,
    missing_platforms: list[str] | None = None,
) -> ModuleCorpus:
    """内存语料：module_texts = (slug, rel, text)，master_headers 留空。"""
    files: list[tuple[str, tuple[ModuleFile, ...]]] = []
    seen_slugs: set[str] = set()
    for slug, rel, text in module_texts or []:
        if slug not in seen_slugs:
            seen_slugs.add(slug)
            files.append((slug, ()))
        kind = "c" if rel.endswith(".c") else "h" if rel.endswith(".h") else "other"
        file = ModuleFile(rel=rel, kind=kind, text=text, own_dir=tmp_path / slug)
        for i, (s, _files) in enumerate(files):
            if s == slug:
                files[i] = (s, (*_files, file))
    return ModuleCorpus(
        platform=PLATFORM_STM32,
        modules=tuple(files),
        missing_platforms=tuple(missing_platforms or ()),
        missing_files=tuple(missing_files or ()),
        master_headers=(),
        master_search_dirs=(),
        master_project_dir=tmp_path,
        main_c=main_c,
    )


def test_corpus_missing_platform_and_files_reported_in_order(tmp_path):
    corpus = _memory_corpus(
        tmp_path,
        missing_platforms=["noplat"],
        missing_files=[("mod", "missing.c")],
    )

    with pytest.raises(MissingModuleFilesError) as excinfo:
        _check_module_files(corpus)

    assert "模块 noplat 没有平台 stm32 的版本条目" in str(excinfo.value)
    assert "模块 mod 缺文件：missing.c" in str(excinfo.value)


def test_corpus_main_calls_fence_and_undefined_from_memory(tmp_path):
    corpus = _memory_corpus(
        tmp_path,
        main_c="```c\nint main(void) { ghost(); while (1); }\n```\n",
        module_texts=[("mod", "mod.h", "#pragma once\nfloat real(void);\n")],
    )

    with pytest.raises(FencedMainCError, match="第 1 行"):
        _check_main_calls(corpus)


def test_corpus_self_include_checks_own_headers_from_memory(tmp_path):
    corpus = _memory_corpus(
        tmp_path,
        module_texts=[
            ("mod", "mod.h", "#pragma once\nvoid mod_init(void);\n"),
            ("mod", "mod.c", '#include "other.h"\nvoid mod_init(void) {}\n'),
        ],
    )

    with pytest.raises(ModuleSelfIncludeError, match="mod.c.*mod.h") as excinfo:
        _check_module_self_include(corpus)

    assert "没有 include 本模块自己的头" in str(excinfo.value)


def test_corpus_macro_conflict_reported_from_memory(tmp_path):
    corpus = ModuleCorpus(
        platform=PLATFORM_STM32,
        modules=(("mod", (ModuleFile(rel="mod.h", kind="h", text="#define LED_GPIO 1\n", own_dir=tmp_path),)),),
        missing_platforms=(),
        missing_files=(),
        master_headers=(("ml_led.h", "#define LED_GPIO 2\n"),),
        master_search_dirs=(),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    with pytest.raises(MacroRedefinitionError, match="LED_GPIO.*ml_led.h") as excinfo:
        _check_macro_conflicts(corpus)

    assert "重定义了母版接口宏" in str(excinfo.value)


def test_unresolved_include_checks_master_search_dirs(tmp_path):
    """唯一碰盘的检查：include 解析按 Keil 语义查搜索目录（模拟母版头在位）。"""
    master = tmp_path / "master"
    master.mkdir()
    (master / "headfile.h").write_text("", encoding="utf-8")
    corpus = ModuleCorpus(
        platform=PLATFORM_STM32,
        modules=(("mod", (ModuleFile(rel="mod.c", kind="c", text='#include "headfile.h"\n', own_dir=tmp_path),)),),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(master,),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    _check_unresolved_includes(corpus)  # 母版搜索目录里有 headfile.h → 通过


def test_unresolved_include_missing_header_rejected_from_memory(tmp_path):
    corpus = _memory_corpus(
        tmp_path,
        module_texts=[("mod", "mod.c", '#include "ghost.h"\n')],
    )

    with pytest.raises(UnresolvedIncludeError, match="ghost.h") as excinfo:
        _check_unresolved_includes(corpus)

    assert "引用了最终工程中不存在的头文件" in str(excinfo.value)


def _mspm0_master_with_sdk_include(master_dir: Path, sdk_dir: Path) -> Path:
    """合成 mspm0 母版：.cproject buildIncludePath 指向含 SDK 头的目录（门禁全链 fixture）。"""
    master_dir.mkdir()
    (master_dir / "project.cproject").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<cproject>\n'
        '  <storageModule moduleId="org.eclipse.cdt.core.settings">\n'
        '    <cconfiguration id="c1">\n'
        '      <storageModule moduleId="org.eclipse.cdt.core.settings">\n'
        '        <cdtBuildSystem>\n'
        '          <configuration name="Debug">\n'
        '            <folderInfo name="/">\n'
        '              <toolChain name="TI Code Generation Tools">\n'
        f'                <option name="Include Options" '
        f'superClass="ti.ccs.misc.options.buildIncludePath" valueType="includePath">\n'
        f'                  <listOptionValue builtIn="false" value="{sdk_dir}"/>\n'
        '                </option>\n'
        '              </toolChain>\n'
        '            </folderInfo>\n'
        '          </configuration>\n'
        '        </cdtBuildSystem>\n'
        '      </storageModule>\n'
        '    </cconfiguration>\n'
        '  </storageModule>\n'
        '</cproject>\n',
        encoding="utf-8",
    )
    return master_dir


def test_unresolved_include_checks_mspm0_sdk_headers_from_cproject(tmp_path):
    """mspm0 门禁全链：母版 .cproject buildIncludePath 指到 SDK 头目录 → include 可解析。

    master_search_dirs 走 patchers 分派（ccs 语义），与 Keil 版同款只查搜索目录。
    """
    sdk = tmp_path / "sdk_headers"
    sdk.mkdir()
    (sdk / "ti_mspm0_config.h").write_text("#pragma once\n", encoding="utf-8")
    master = _mspm0_master_with_sdk_include(tmp_path / "mspm0_master", sdk)
    corpus = ModuleCorpus(
        platform=PLATFORM_MSPM0,
        modules=(
            (
                "mod",
                (
                    ModuleFile(
                        rel="mod.c",
                        kind="c",
                        text='#include "ti_mspm0_config.h"\n',
                        own_dir=tmp_path,
                    ),
                ),
            ),
        ),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=tuple(include_search_dirs(PLATFORM_MSPM0, master)),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    _check_unresolved_includes(corpus)  # 母版 buildIncludePath 里有 SDK 头 → 通过


def test_unresolved_include_rejects_mspm0_missing_sdk_header(tmp_path):
    """mspm0 门禁：SDK 目录里没有的头 → 拒绝（UnresolvedIncludeError，文案同 Keil 版）。"""
    sdk = tmp_path / "sdk_headers"
    sdk.mkdir()
    (sdk / "ti_mspm0_config.h").write_text("#pragma once\n", encoding="utf-8")
    master = _mspm0_master_with_sdk_include(tmp_path / "mspm0_master", sdk)
    corpus = ModuleCorpus(
        platform=PLATFORM_MSPM0,
        modules=(
            (
                "mod",
                (
                    ModuleFile(
                        rel="mod.c",
                        kind="c",
                        text='#include "ghost_sdk.h"\n',
                        own_dir=tmp_path,
                    ),
                ),
            ),
        ),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=tuple(include_search_dirs(PLATFORM_MSPM0, master)),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    with pytest.raises(UnresolvedIncludeError, match="ghost_sdk.h") as excinfo:
        _check_unresolved_includes(corpus)

    assert "引用了最终工程中不存在的头文件" in str(excinfo.value)


def test_generate_module_without_platform_version_fails(
    stm32_selection, make_project, tmp_path
):
    oled = [m for m in stm32_selection if m.slug == "oled"]  # oled 没有 mspm0 版本
    output_dir = tmp_path / "out"

    with pytest.raises(MissingModuleFilesError, match=PLATFORM_MSPM0) as excinfo:
        make_project(platform=PLATFORM_MSPM0, manifests=oled, output_dir=output_dir)

    assert "oled" in str(excinfo.value)
    assert not output_dir.exists()


def test_generate_missing_master_dir_fails(make_project, tmp_path):
    output_dir = tmp_path / "out"

    with pytest.raises(MasterNotFoundError, match="master"):
        make_project(
            master_project_dir=tmp_path / "no_such_master", output_dir=output_dir
        )

    assert not output_dir.exists()


def test_generate_rejects_nonempty_output_dir(make_project, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "leftover.txt").write_text("x", encoding="utf-8")

    with pytest.raises(OutputDirNotEmptyError, match="out"):
        make_project(output_dir=output_dir)


def test_generate_accepts_existing_empty_output_dir(make_project, tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    result = make_project(output_dir=output_dir)

    assert (result / "main.c").exists()


def test_generate_twice_produces_identical_project_config(make_project, tmp_path):
    first = make_project(output_dir=tmp_path / "out1")
    second = make_project(output_dir=tmp_path / "out2")

    assert (first / "project.uvprojx").read_bytes() == (
        second / "project.uvprojx"
    ).read_bytes()


def test_generate_mspm0_twice_produces_identical_project_config(
    make_ccs_project, tmp_path
):
    first = make_ccs_project(output_dir=tmp_path / "out1")
    second = make_ccs_project(output_dir=tmp_path / "out2")

    assert (first / "project.cproject").read_bytes() == (
        second / "project.cproject"
    ).read_bytes()


# ---------------------------------------------------------------------------
# Theia 20.5 母版端到端（工单 08）：合成整理后形态 → 生成最小工程
# ---------------------------------------------------------------------------


def _theia_masters_dir(tmp_path) -> Path:
    masters_dir = tmp_path / "masters"
    make_fake_ccs_theia_master_project(masters_dir / "mspm0")
    return masters_dir


def test_generate_mspm0_theia_minimal_project_succeeds(fake_module_library, tmp_path):
    """端到端（slugs=() 最小工程）：Theia 母版全程走通，无 CcsProjectError；
    输出树 = main.c 骨架 + 母版文件，无 empty.c / .clangd / Debug / README。"""
    main_c = "int main(void) { while (1); }\n"
    summary = generate_project(
        platform=PLATFORM_MSPM0,
        slugs=(),
        main_c_content=main_c,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=_theia_masters_dir(tmp_path),
    )

    out = summary.output_dir
    assert (out / "main.c").read_text(encoding="utf-8") == main_c
    assert (out / "project.cproject").exists()
    assert (out / ".project").exists()
    assert (out / "mspm0.syscfg").exists()
    assert not (out / "empty.c").exists()  # 母版已整理（empty.c → main.c）
    assert not (out / ".clangd").exists()
    assert not (out / "Debug").exists()
    assert not (out / "README.html").exists()
    assert not (out / "README.md").exists()


def test_generate_mspm0_theia_appends_module_includes_and_root_source_entry(
    fake_module_library, tmp_path
):
    """端到端带模块：.cproject 追加 ${PROJECT_LOC}/modules include + 补根
    sourceEntry（Theia 母版无 sourceEntries，main.c 与模块都进编译）。"""
    summary = generate_project(
        platform=PLATFORM_MSPM0,
        slugs=["dht11", "delay"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=_theia_masters_dir(tmp_path),
    )

    root = ET.parse(summary.output_dir / "project.cproject").getroot()
    values = _ccs_include_values(root, "Debug")
    assert values[-3:] == [
        "${PROJECT_LOC}/modules/delay",  # 依赖展开后 delay 在前（resolve_selection 顺序）
        "${PROJECT_LOC}/modules/dht11/mspm0/src",
        "${PROJECT_LOC}/modules/dht11/inc",
    ]
    entry_names = _ccs_source_entry_names(root, "Debug")
    assert entry_names == [""]  # 根条目覆盖 modules/（main.c 一并编译）


def test_patcher_invoked_via_registry_with_files_and_include_dirs(make_project, tmp_path):
    registry = PatcherRegistry()
    spy = RecordingPatcher()
    registry.register(PLATFORM_STM32, spy)
    output_dir = tmp_path / "out"

    make_project(output_dir=output_dir, registry=registry)

    assert len(spy.calls) == 1
    project_dir, module_files, include_dirs = spy.calls[0]
    assert project_dir == output_dir
    assert module_files == (
        Path("modules/dht11/stm32/src/dht11.c"),
        Path("modules/dht11/inc/dht11.h"),
        Path("modules/oled/stm32/src/oled.c"),
        Path("modules/oled/inc/oled.h"),
    )
    assert include_dirs == (
        Path("modules/dht11/stm32/src"),
        Path("modules/dht11/inc"),
        Path("modules/oled/stm32/src"),
        Path("modules/oled/inc"),
    )


# ---------------------------------------------------------------------------
# 工单 03：生成入口支持历史赛题编号（题面全文 + 关联素材 + 该题专用模块）
# ---------------------------------------------------------------------------


def _wired_dirs(tmp_path):
    """生成接线的素材区：赛题库 + 参考文件库 + 该题专用模块与普通候选模块
    （各自独立临时目录，互不污染）。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_topic_specific_module(library)
    make_kit_candidate_module(library)
    topics = make_fake_topic_library(tmp_path / "topics")
    references = make_fake_reference_library(tmp_path / "references")
    return library, topics, references


def test_resolve_topic_context_explicit_key_materializes_entry(tmp_path):
    """显式编号：题面全文（长 PDF 题面全文只在选了该赛题时进上下文）+ 关联素材
    （锚定该题或候选模块套件的参考文件）+ 该题专用模块（XX 题专用标注自动发现）。"""
    library, topics, references = _wired_dirs(tmp_path)

    ctx = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="用户粘贴的题面片段",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
    )

    assert ctx is not None
    assert ctx.key == "2026C"
    assert ctx.problem_text == TOPIC_PROBLEM_TEXT
    assert ctx.related_modules == ("lock_control",)
    assert [e.id for e in ctx.references] == [
        TOPIC_REFERENCE_ID,
        KIT_REFERENCE_ID,
        UWB_REFERENCE_ID,
    ]


def test_resolve_topic_context_without_specific_modules_still_carries_kit_refs(
    tmp_path,
):
    """该题没有专用模块（库中无"XX 题专用"标注）时，套件锚定的参考文件仍经
    候选模块的 kit 进清单（评审 c2：关联面不得依赖专用模块是否入库）。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_kit_candidate_module(library)
    topics = make_fake_topic_library(tmp_path / "topics")
    references = make_fake_reference_library(tmp_path / "references")

    ctx = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="粘贴",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
    )

    assert ctx is not None
    assert ctx.related_modules == ()
    assert UWB_REFERENCE_ID in [e.id for e in ctx.references]


def test_resolve_topic_context_recognizes_number_in_pasted_text(tmp_path):
    """粘贴题面中出现编号同样可认：AI 提取编号 → 查库得题面全文 + 关联素材。"""
    library, topics, references = _wired_dirs(tmp_path)

    class ExtractingLLM:
        def topic_extract_number(self, text: str) -> str:
            return "2026C"

    ctx = resolve_topic_context(
        llm=ExtractingLLM(),
        topic_key="",
        problem_text="……2026C 数字钥匙题……",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
    )

    assert ctx is not None
    assert ctx.key == "2026C"
    assert ctx.problem_text == TOPIC_PROBLEM_TEXT


def test_resolve_topic_context_auto_recognition_is_best_effort(tmp_path):
    """自动识别尽力而为：提取失败（LLMError）/ 查无此条 / 没提取到 → no-topic
    上下文（key="" 哨兵），不阻断纯粘贴题面流程（与显式编号的查无此条大声
    报错相对）。"""
    library, topics, references = _wired_dirs(tmp_path)

    class NoNumberLLM:
        def topic_extract_number(self, text: str) -> None:
            return None

    _assert_no_topic_context(
        resolve_topic_context(
            llm=NoNumberLLM(),
            topic_key="",
            problem_text="普通粘贴题面",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        ),
        library,
        "普通粘贴题面",
    )

    class RaisingExtractLLM:
        def topic_extract_number(self, text: str) -> str:
            raise LLMError("服务不可用")

    _assert_no_topic_context(
        resolve_topic_context(
            llm=RaisingExtractLLM(),
            topic_key="",
            problem_text="粘贴题面",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        ),
        library,
        "粘贴题面",
    )

    class UnknownKeyLLM:
        def topic_extract_number(self, text: str) -> str:
            return "2021F"  # 库中没有的编号

    _assert_no_topic_context(
        resolve_topic_context(
            llm=UnknownKeyLLM(),
            topic_key="",
            problem_text="粘贴题面",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        ),
        library,
        "粘贴题面",
    )


def _assert_no_topic_context(ctx, library, problem_text):
    """no-topic 形上下文：key="" 哨兵（key 非空 = 识别到历史赛题）+ 题面原样
    + 空关联 / 建议 + 全模块摘要 + 空集回读器（任何 id 抛 ReferenceError——
    suggestions 恒空所以永不被调，诚实 no-op）。"""
    assert ctx.key == ""
    assert ctx.problem_text == problem_text
    assert ctx.references == ()
    assert ctx.related_modules == ()
    assert ctx.suggestions == ()
    assert {s.slug for s in ctx.manifest_summaries} == {
        m.slug for m in list_modules(library)
    }
    with pytest.raises(ReferenceError, match="不存在"):
        ctx.read_fulltext(TOPIC_REFERENCE_ID)


def test_resolve_topic_context_explicit_unknown_key_raises(tmp_path):
    """显式编号查无此条：明确报错（不猜测编造），不是静默降级。"""
    library, topics, references = _wired_dirs(tmp_path)

    with pytest.raises(TopicError, match="没有"):
        resolve_topic_context(
            llm=None,
            topic_key="2021F",
            problem_text="粘贴",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
        )


def test_generate_project_with_related_modules_auto_includes_them(
    fake_module_library, tmp_path
):
    """生成入口带该题专用模块（webapp 装配点 resolve_topic_context 的结果透传）：
    自动并入最终模块集（生成物与用户手选等价）——接缝只消费不重扫库。"""
    make_topic_specific_module(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        related_modules=("lock_control",),
    )

    assert (tmp_path / "out" / "modules" / "lock_control" / "lock_control.c").is_file()
    assert any(slug == "lock_control" for slug, _ in summary.modules)


# ---------------------------------------------------------------------------
# include 解析门禁（判例：库模块引用了从未入库的头，Keil cannot open）
# ---------------------------------------------------------------------------


def test_generate_rejects_module_with_unresolved_include(
    fake_module_library, make_project, tmp_path
):
    """模块源码引用了最终工程里不存在的头 → 拒绝生成并点名头文件。"""
    _add_module(
        fake_module_library,
        {
            "slug": "badmod",
            "description": "引用不存在头的坏模块",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/bad.c"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        # 悬空 include 放第 2 行——复刻真实判例（pid.c 第 1 行 headfile.h 第 2 行
        # digit_uart.h）：第 1 行的 # 行判断能过、第 2 行起不能，曾漏检
        {"code/bad.c": '#include "headfile.h"\n#include "digit_uart.h"\nvoid bad_fn(void) {}\n'},
    )
    badmod = ModuleManifest.load(fake_module_library / "badmod")
    output_dir = tmp_path / "out"

    with pytest.raises(UnresolvedIncludeError, match="digit_uart.h") as excinfo:
        make_project(
            manifests=[badmod],
            main_c_content="int main(void) { while (1); }\n",
            output_dir=output_dir,
        )

    assert "bad.c" in str(excinfo.value)
    assert not output_dir.exists()  # 校验在创建输出目录之前


def test_generate_rejects_module_without_self_include(
    fake_module_library, make_project, tmp_path
):
    """模块 .c 不 include 自己的头（符号声明依赖原始工程聚合头，真机编译
    pid_t/yaw_gyro/D1..D8 全未声明判例）→ 拒绝生成并点名模块与头文件。"""
    _add_module(
        fake_module_library,
        {
            "slug": "noself",
            "description": "不自含的坏模块",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/noself.c", "code/noself.h"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        {
            # 只 include 母版聚合头，不 include 自己的头 —— 复刻真实判例
            "code/noself.c": '#include "headfile.h"\nvoid noself_fn(void) { pid_t p; }\n',
            "code/noself.h": "typedef int pid_t;\nvoid noself_fn(void);\n",
        },
    )
    mod = ModuleManifest.load(fake_module_library / "noself")
    output_dir = tmp_path / "out"

    with pytest.raises(ModuleSelfIncludeError, match="noself.h") as excinfo:
        make_project(
            manifests=[mod],
            main_c_content="int main(void) { while (1); }\n",
            output_dir=output_dir,
        )

    assert "noself.c" in str(excinfo.value)
    assert not output_dir.exists()  # 校验在创建输出目录之前


def test_generate_rejects_main_c_with_code_fences(make_project, tmp_path):
    """main.c 带 Markdown 围栏（LLM 围栏输出未剥离）→ 拒绝生成。"""
    output_dir = tmp_path / "out"

    with pytest.raises(FencedMainCError, match="第 1 行") as excinfo:
        make_project(
            main_c_content="```c\nint main(void) { while (1); }\n```\n",
            output_dir=output_dir,
        )

    assert "围栏" in str(excinfo.value)
    assert not output_dir.exists()


def test_generate_accepts_module_include_resolving_via_other_module_dir(
    fake_module_library, make_project, tmp_path
):
    """模块间 include（A 引 B 的头，B 目录进 IncludePath）→ 正常生成。"""
    _add_module(
        fake_module_library,
        {
            "slug": "mod_b",
            "description": "提供 b.h",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/b.h"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        {"code/b.h": "#pragma once\nint b_val;\n"},
    )
    _add_module(
        fake_module_library,
        {
            "slug": "mod_a",
            "description": "引用 mod_b 的头",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/a.c"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        {"code/a.c": '#include "b.h"\nvoid a_fn(void) { (void)b_val; }\n'},
    )
    mod_a = ModuleManifest.load(fake_module_library / "mod_a")
    mod_b = ModuleManifest.load(fake_module_library / "mod_b")

    out = make_project(
        manifests=[mod_a, mod_b],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
    )

    assert (out / "modules/mod_a/code/a.c").is_file()


def test_generate_accepts_stdlib_header_in_quotes(
    fake_module_library, make_project, tmp_path
):
    """引号形式的标准库头（math.h）Keil 在工程外能解析 → 不误报。"""
    _add_module(
        fake_module_library,
        {
            "slug": "mathmod",
            "description": "用引号引用标准库头",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/m.c"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        {"code/m.c": '#include "math.h"\ndouble m_fn(double x) { return x; }\n'},
    )
    mathmod = ModuleManifest.load(fake_module_library / "mathmod")

    out = make_project(
        manifests=[mathmod],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
    )

    assert (out / "modules/mathmod/code/m.c").is_file()


# ---------------------------------------------------------------------------
# 宏重定义门禁（判例：config.h 的 LED_GPIO 撞母版 ml_led.h，Keil #47-D）
# ---------------------------------------------------------------------------


def test_generate_rejects_module_redefining_master_macro(
    fake_master_project, fake_module_library, make_project, tmp_path
):
    """模块头重定义母版接口宏（同名不同值）→ 拒绝生成并点名三方。"""
    (fake_master_project / "inc/ml_led.h").write_text(
        "#define LED_GPIO GPIO_A\n", encoding="utf-8"
    )
    _add_module(
        fake_module_library,
        {
            "slug": "clash",
            "description": "重定义库宏的坏模块",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/clash.h"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        {"code/clash.h": "#define LED_GPIO GPIO_C\n"},
    )
    clash = ModuleManifest.load(fake_module_library / "clash")
    output_dir = tmp_path / "out"

    with pytest.raises(MacroRedefinitionError) as excinfo:
        make_project(
            manifests=[clash],
            main_c_content="int main(void) { while (1); }\n",
            output_dir=output_dir,
        )

    message = str(excinfo.value)
    assert "LED_GPIO" in message
    assert "clash.h" in message
    assert "ml_led.h" in message
    assert not output_dir.exists()  # 校验在创建输出目录之前


def test_generate_allows_same_value_macro(
    fake_master_project, fake_module_library, make_project, tmp_path
):
    """同名同值宏 = Keil benign redefinition → 放行。"""
    (fake_master_project / "inc/ml_led.h").write_text(
        "#define LED_GPIO GPIO_A\n", encoding="utf-8"
    )
    _add_module(
        fake_module_library,
        {
            "slug": "sameval",
            "description": "同值重定义模块",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/sameval.h"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        {"code/sameval.h": "#define LED_GPIO GPIO_A\n"},
    )
    sameval = ModuleManifest.load(fake_module_library / "sameval")

    out = make_project(
        manifests=[sameval],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
    )

    assert (out / "modules/sameval/code/sameval.h").is_file()


def test_generate_ignores_include_guard_and_undef(
    fake_master_project, fake_module_library, make_project, tmp_path
):
    """include guard 定义（#ifndef 块内）与 #undef 后重定义 → 均不误报。"""
    (fake_master_project / "inc/ml_led.h").write_text(
        "#ifndef _ml_led_h_\n#define _ml_led_h_\n#define LED_GPIO GPIO_A\n#endif\n",
        encoding="utf-8",
    )
    _add_module(
        fake_module_library,
        {
            "slug": "guarded",
            "description": "guard 与 undef 模式模块",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/guarded.h"],
                    "verified": False,
                    "hardware_bound": False,
                    "notes": "",
                    "kit": "",
                    "source_url": "",
                }
            },
        },
        {
            # 模块头带 guard（同名 guard 宏不冲突）+ #undef 后合法重定义
            "code/guarded.h": (
                "#ifndef _guarded_h_\n#define _guarded_h_\n"
                "#undef LED_GPIO\n#define LED_GPIO GPIO_C\n"
                "#define LED_RED_Pin Pin_13\n#endif\n"
            )
        },
    )
    guarded = ModuleManifest.load(fake_module_library / "guarded")

    out = make_project(
        manifests=[guarded],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
    )

    assert (out / "modules/guarded/code/guarded.h").is_file()


def test_generate_rejects_main_c_redefining_master_macro(
    fake_master_project, make_project, tmp_path
):
    """main.c 重定义母版接口宏同样拒绝。"""
    (fake_master_project / "inc/ml_led.h").write_text(
        "#define LED_GPIO GPIO_A\n", encoding="utf-8"
    )
    output_dir = tmp_path / "out"

    with pytest.raises(MacroRedefinitionError, match="LED_GPIO"):
        make_project(
            main_c_content="#define LED_GPIO GPIO_C\nint main(void) { while (1); }\n",
            output_dir=output_dir,
        )

    assert not output_dir.exists()


def test_generate_writes_main_c_with_trailing_newline(make_project, tmp_path):
    """main.c 落盘幂等补尾部换行（Keil #1-D last line without newline 判例）。"""
    out = make_project(
        main_c_content="int main(void) { while (1); }",  # 无尾部换行
        output_dir=tmp_path / "out",
    )

    content = (out / "main.c").read_text(encoding="utf-8")
    assert content.endswith("\n")


# ---------------------------------------------------------------------------
# 结构测试（防回退，先例 03 工单 hasattr / 06 工单 grep）：generator 对平台模块
# import 面清零 + include 读侧对偶定义单址（工单 07）
# ---------------------------------------------------------------------------


def test_generator_has_no_platform_module_imports():
    """generator 对平台模块（keil/ccs）运行时 import 面清零：搜索目录经 patchers 分派。"""
    import contest_generator.generator as generator

    assert "keil" not in generator.__dict__
    assert "ccs" not in generator.__dict__


def test_include_search_dirs_definition_origins():
    """读侧对偶单址：include_search_dirs 格式定义恰在 keil.py + ccs.py（分派在 patchers.py）。"""
    import contest_generator.generator as generator
    from pathlib import Path

    src_root = Path(generator.__file__).parent
    hits = [
        path.name
        for path in sorted(src_root.glob("*.py"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("def include_search_dirs")
    ]
    assert hits == ["ccs.py", "keil.py", "patchers.py"]
