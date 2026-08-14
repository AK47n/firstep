"""生成器核心：唯一的测试接缝。

输入（平台、已选 manifest 集、母版目录、输出目录、main.c 内容）
→ 输出完整工程目录。断言输出目录的结构与文件内容。
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.generator import (
    FencedMainCError,
    GENERATION_GATES,
    GateContext,
    GeneratorError,
    GenerationGate,
    MacroRedefinitionError,
    MasterNotFoundError,
    MissingModuleFilesError,
    ModuleCorpus,
    ModuleFile,
    ModuleSelfIncludeError,
    OutputDirNotEmptyError,
    UndefinedCallsError,
    UnresolvedIncludeError,
    _LIBC_HEADERS,
    _check_main_calls,
    _check_macro_conflicts,
    _check_module_files,
    _check_module_self_include,
    _check_unresolved_includes,
    _search_dir_header_names,
    build_module_corpus,
    build_output_tree_corpus,
    generate,
    generate_project,
    resolve_topic_context,
    run_generation_gates,
)
from contest_generator.ccs import INCLUDE_OPTION_SUPERCLASSES, _SETTINGS_MODULE_ID
from contest_generator.library import list_modules
from contest_generator.llm import LLMError
from contest_generator.manifest import ModuleManifest, PlatformEntry
from contest_generator.master_store import MasterError
from contest_generator.patchers import (
    PLATFORM_MSPM0,
    PLATFORM_STM32,
    PatcherRegistry,
    UnknownPlatformError,
    external_headers,
    include_search_dirs,
)
from contest_generator.reference_library import ReferenceError
from contest_generator.selection import (
    ManualReferenceError,
    REFERENCE_SOURCE_MANUAL,
)
from contest_generator.topic_library import TopicError
from contest_generator.treewalk import iter_project_files
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
    make_fake_motor_pid_library,
    make_fake_stm32_ml_master,
)
from tests.generate_wiring_fakes import (
    KIT_REFERENCE_ID,
    OTHER_REFERENCE_ID,
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


def test_generate_embedded_in_master_entry_copies_nothing(
    make_project, tmp_path
):
    """空 files 平台条目（实现内嵌母版）：不复制模块文件、不加 include 目录、
    输出无 modules/ 子树（实现随母版进工程）。"""
    embedded = ModuleManifest(
        slug="oled",
        description="OLED（stm32 实现内嵌母版）",
        platforms={PLATFORM_STM32: PlatformEntry(files=(), verified=True)},
    )
    registry = PatcherRegistry()
    spy = RecordingPatcher()
    registry.register(PLATFORM_STM32, spy)

    result = make_project(
        manifests=[embedded],
        output_dir=tmp_path / "out",
        main_c_content="int main(void) { while (1); }\n",
        registry=registry,
    )

    assert not (result / "modules").exists()
    project_dir, module_files, include_dirs = spy.calls[0]
    assert module_files == ()  # 无模块文件复制
    assert include_dirs == ()  # 不加 include 目录


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
# 语料门禁（工单 02）：纯内存构造 ModuleCorpus 直喂门禁，无盘上夹具。
# 门禁不再读盘——文件文本与搜索目录头名单全部来自语料（构建时一次扫盘，
# 工单 gate-corpus-closure/01，见 test_unresolved_include_is_pure_predicate_zero_disk_access）。
# ---------------------------------------------------------------------------


def _memory_corpus(
    tmp_path,
    *,
    main_c: str = "int main(void) { while (1); }\n",
    module_texts: list[tuple[str, str, str]] | None = None,
    missing_files: list[tuple[str, str]] | None = None,
    missing_platforms: list[str] | None = None,
    master_headers: list[tuple[str, str]] | None = None,
    search_dir_headers: tuple[tuple[Path, frozenset[str]], ...] = (),
) -> ModuleCorpus:
    """内存语料：module_texts = (slug, rel, text)，master_headers / 搜索目录
    头名单可传（默认空）。"""
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
        master_headers=tuple(master_headers or ()),
        master_search_dirs=(),
        search_dir_headers=search_dir_headers,
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


def test_corpus_main_calls_accept_master_header_functions(tmp_path):
    """母版内嵌实现（空 files 平台条目）的函数声明在母版头——接口集并入
    母版头后，main.c 调母版 API（OLED_* 等）不再误报未定义。"""
    corpus = _memory_corpus(
        tmp_path,
        main_c='int main(void) { OLED_ShowString(1, 2, "hi"); while (1); }\n',
        master_headers=[
            ("ml_oled.h", "#pragma once\nvoid OLED_ShowString(uint8_t line, uint8_t col, char *s);\n"),
        ],
    )

    _check_main_calls(corpus)  # 母版头里的函数 → 通过


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
        search_dir_headers=(),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    with pytest.raises(MacroRedefinitionError, match="LED_GPIO.*ml_led.h") as excinfo:
        _check_macro_conflicts(corpus)

    assert "重定义了母版接口宏" in str(excinfo.value)


def test_unresolved_include_checks_master_search_dirs(tmp_path):
    """include 解析按 Keil 语义查搜索目录：搜索目录头名单在语料构建时一次
    glob 进 search_dir_headers（模拟母版头在搜索目录，门禁纯集合判定）。

    include 写法混合大小写 → 名集合小写化对齐后照常放行（Windows is_file
    大小写不敏感语义，门禁不再碰盘）。
    """
    master = tmp_path / "master"
    master.mkdir()
    (master / "headfile.h").write_text("", encoding="utf-8")
    corpus = ModuleCorpus(
        platform=PLATFORM_STM32,
        modules=(("mod", (ModuleFile(rel="mod.c", kind="c", text='#include "HeadFile.H"\n', own_dir=tmp_path),)),),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(master,),
        search_dir_headers=_search_dir_header_names((master,)),
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


def test_unresolved_include_is_pure_predicate_zero_disk_access(tmp_path, monkeypatch):
    """第六道门禁零盘访问（契约：门禁只吃语料）——is_file 被调即红。

    include 解析唯一碰盘点（搜索目录 stat）收进语料构建后，门禁退化为纯
    集合成员判定（工单 gate-corpus-closure/01，旧实现 generator.py 对每个
    include 候选 stat 活盘，本测试 monkeypatch 证明修复后零盘访问）。
    """
    master = tmp_path / "master"
    master.mkdir()
    (master / "headfile.h").write_text("", encoding="utf-8")
    corpus = ModuleCorpus(
        platform=PLATFORM_STM32,
        modules=(
            (
                "mod",
                (
                    ModuleFile(
                        rel="mod.c",
                        kind="c",
                        text='#include "headfile.h"\n',
                        own_dir=tmp_path,
                    ),
                ),
            ),
        ),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(master,),
        search_dir_headers=((master, frozenset({"headfile.h"})),),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    def _boom(*args, **kwargs):
        raise AssertionError("include 解析门碰盘：Path.is_file 被调用")

    monkeypatch.setattr(Path, "is_file", _boom)
    try:
        _check_unresolved_includes(corpus)  # 纯语料放行，is_file 被调即红
    finally:
        monkeypatch.undo()  # 先撤 patch 再让 tmp_path 清理（清理代码用 is_file）


def test_unresolved_include_resolves_search_dir_from_corpus_only(tmp_path):
    """内存直构语料：搜索目录在盘上不存在，语料 search_dir_headers 照常放行
    （纯语料判定——旧实现 stat 活盘必挂，产物体外验收无需真实工具链目录）。"""
    ghost = tmp_path / "no_such_search_dir"  # 盘上不存在
    corpus = _memory_corpus(
        tmp_path,
        module_texts=[("mod", "mod.c", '#include "headfile.h"\n')],
        search_dir_headers=((ghost, frozenset({"headfile.h"})),),
    )

    _check_unresolved_includes(corpus)  # 纯语料判定，不碰盘


def test_build_module_corpus_scans_search_dir_headers(tmp_path):
    """语料构建一次扫盘：每个母版 IncludePath 目录的 *.h 基名集合（小写化）
    进 search_dir_headers；目录不存在 = 空集（与旧 is_file 判 False 同义）。"""
    master = make_fake_master_project(tmp_path / "master")  # IncludePath = .\inc;.\src
    corpus = build_module_corpus(
        [], PLATFORM_STM32, tmp_path / "lib", master, "int main(void) { while (1); }\n"
    )

    by_dir = dict(corpus.search_dir_headers)
    assert by_dir[master / "inc"] == frozenset({"stm32f10x_conf.h"})
    assert by_dir[master / "src"] == frozenset()  # 无 .h → 空集
    assert corpus.master_search_dirs == tuple(
        include_search_dirs(PLATFORM_STM32, master)
    )


def test_search_dir_header_names_missing_dir_is_empty(tmp_path):
    """搜索目录在盘上不存在 → 空集合（语义与旧 is_file 判 False 一致）。"""
    ghost = tmp_path / "no_such_dir"
    assert _search_dir_header_names((ghost,)) == ((ghost, frozenset()),)


# ---------------------------------------------------------------------------
# 产物树语料重建（工单 generate-check-parity/01）：build_output_tree_corpus
# 从生成产物树重建语料——真机验收脚本（generate_check）不再抄门禁逻辑，
# 镜像删除后验收测的就是 run_generation_gates 本身（门禁一改脚本不再静默
# 漂移）。tmp_path 直构产物树可测。
# ---------------------------------------------------------------------------


def _write_output_tree(
    root: Path,
    *,
    main_c: str = "int main(void) { while (1); }\n",
    modules: dict[str, dict[str, str]] | None = None,
    master_headers: dict[str, str] | None = None,
) -> None:
    """tmp_path 直构产物树：modules = {slug: {rel: text}}，母版头相对根。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / "main.c").write_text(main_c, encoding="utf-8")
    for slug, files in (modules or {}).items():
        for rel, text in files.items():
            p = root / "modules" / slug / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    for rel, text in (master_headers or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_build_output_tree_corpus_rebuilds_modules_and_master(tmp_path):
    root = tmp_path / "out"
    _write_output_tree(
        root,
        main_c='#include "headfile.h"\nint main(void) { while (1); }\n',
        modules={
            "pid": {
                "code/pid.c": '#include "pid.h"\n',
                "code/pid.h": "#pragma once\n",
            },
            "led": {"led.c": '#include "led.h"\n', "led.h": "#pragma once\n"},
        },
        master_headers={
            "headfile.h": "#pragma once\n",
            "ml_led.h": "#define LED_GPIO 1\n",
        },
    )

    corpus = build_output_tree_corpus(root, PLATFORM_STM32, [root / "user"])

    assert corpus.platform == PLATFORM_STM32
    assert corpus.master_project_dir == root
    assert corpus.missing_platforms == () and corpus.missing_files == ()
    assert corpus.main_c.startswith('#include "headfile.h"')
    # modules 按 slug 排序；文件 rel 相对模块目录，kind 判定与 build_module_corpus 同规
    assert [slug for slug, _ in corpus.modules] == ["led", "pid"]
    pid_files = {f.rel: f for f in dict(corpus.modules)["pid"]}
    assert set(pid_files) == {"code/pid.c", "code/pid.h"}
    assert pid_files["code/pid.c"].kind == "c"
    assert pid_files["code/pid.h"].kind == "h"
    assert pid_files["code/pid.c"].own_dir == root / "modules" / "pid" / "code"
    assert pid_files["code/pid.c"].text == '#include "pid.h"\n'
    # master_headers 收母版树 *.h，排除 modules/ 子树（模块头在 modules 语料里）
    assert {rel for rel, _ in corpus.master_headers} == {"headfile.h", "ml_led.h"}
    # master_search_dirs = 调用方传入（generate_check 读补丁后工程文件的 IncludePath）
    assert corpus.master_search_dirs == (root / "user",)
    # search_dir_headers 与生成侧同构（工单 gate-corpus-closure/01）：字段形状
    # (Path, frozenset 小写基名)，搜索目录不存在 = 空集
    assert corpus.search_dir_headers == ((root / "user", frozenset()),)


def test_build_output_tree_corpus_scans_search_dir_headers(tmp_path):
    """产物树侧重建语料与生成侧同规：搜索目录的 *.h 基名集合一次 glob 进
    search_dir_headers（真机验收与门禁同源，字段形状同构）。"""
    root = tmp_path / "out"
    _write_output_tree(root)
    (root / "user").mkdir()
    (root / "user" / "headfile.h").write_text("#pragma once\n", encoding="utf-8")

    corpus = build_output_tree_corpus(root, PLATFORM_STM32, [root / "user"])

    assert corpus.search_dir_headers == (
        (root / "user", frozenset({"headfile.h"})),
    )


def test_build_output_tree_corpus_no_modules_dir_is_empty(tmp_path):
    root = tmp_path / "out"
    _write_output_tree(root, master_headers={"headfile.h": "#pragma once\n"})

    corpus = build_output_tree_corpus(root, PLATFORM_STM32, [])

    assert corpus.modules == ()
    assert corpus.master_headers == (("headfile.h", "#pragma once\n"),)
    assert corpus.main_c == "int main(void) { while (1); }\n"


def test_output_tree_unresolved_include_hits_real_gate(tmp_path):
    """门禁对偶：产物树含未解析 include → 重建语料跑真门禁抛
    UnresolvedIncludeError（镜像删净后验收测的就是生产谓词本身）。"""
    root = tmp_path / "out"
    _write_output_tree(
        root,
        modules={"mod": {"code/mod.c": '#include "ghost.h"\n'}},
        master_headers={"headfile.h": "#pragma once\n"},
    )

    corpus = build_output_tree_corpus(root, PLATFORM_STM32, [])
    with pytest.raises(UnresolvedIncludeError, match="ghost.h"):
        run_generation_gates(corpus, [], PLATFORM_STM32)


def test_output_tree_macro_conflict_hits_real_gate(tmp_path):
    """门禁对偶：产物树模块头重定义母版接口宏 → 真门禁抛
    MacroRedefinitionError（宏冲突判例：config.h LED_GPIO 撞 ml_led.h）。"""
    root = tmp_path / "out"
    _write_output_tree(
        root,
        modules={"mod": {"config.h": "#define LED_GPIO 1\n"}},
        master_headers={"ml_led.h": "#define LED_GPIO 2\n"},
    )

    corpus = build_output_tree_corpus(root, PLATFORM_STM32, [])
    with pytest.raises(MacroRedefinitionError, match="LED_GPIO.*ml_led.h"):
        run_generation_gates(corpus, [], PLATFORM_STM32)


def test_output_tree_clean_tree_passes_all_gates(tmp_path):
    """门禁对偶：产物树干净（include 可解析 + 模块自包含 + 无宏冲突）→ 六道全过。"""
    root = tmp_path / "out"
    _write_output_tree(
        root,
        main_c='#include "headfile.h"\nint main(void) { mod_init(); while (1); }\n',
        modules={
            "mod": {
                "code/mod.c": '#include "mod.h"\nvoid mod_init(void) {}\n',
                "code/mod.h": "#pragma once\nvoid mod_init(void);\n",
            },
        },
        master_headers={"headfile.h": "#pragma once\n"},
    )

    corpus = build_output_tree_corpus(root, PLATFORM_STM32, [])
    run_generation_gates(corpus, [], PLATFORM_STM32)  # 不抛 = 六道全过


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
    search_dirs = tuple(include_search_dirs(PLATFORM_MSPM0, master))
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
        master_search_dirs=search_dirs,
        search_dir_headers=_search_dir_header_names(search_dirs),
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
    search_dirs = tuple(include_search_dirs(PLATFORM_MSPM0, master))
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
        master_search_dirs=search_dirs,
        search_dir_headers=_search_dir_header_names(search_dirs),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    with pytest.raises(UnresolvedIncludeError, match="ghost_sdk.h") as excinfo:
        _check_unresolved_includes(corpus)

    assert "引用了最终工程中不存在的头文件" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 外部头豁免（工单 03）：C 标准库头归门禁（_LIBC_HEADERS，平台无关），工具链
# 头各平台各自声明（keil/ccs EXTERNAL_HEADERS）、patchers.external_headers
# 分派——跨平台工具链头不互相泄漏，静默放行改拒绝（修门禁洞）
# ---------------------------------------------------------------------------


def test_external_header_exemptions_are_platform_specific():
    """豁免并集 = C 标准库头（两平台共用）+ 本平台工具链头，互不泄漏。"""
    stm32_union = _LIBC_HEADERS | external_headers(PLATFORM_STM32)
    mspm0_union = _LIBC_HEADERS | external_headers(PLATFORM_MSPM0)

    assert external_headers(PLATFORM_STM32) == frozenset({"stm32f10x_conf.h"})
    assert external_headers(PLATFORM_MSPM0) == frozenset({"ti_msp_dl_config.h"})
    assert _LIBC_HEADERS.isdisjoint(external_headers(PLATFORM_STM32))
    assert _LIBC_HEADERS.isdisjoint(external_headers(PLATFORM_MSPM0))
    assert _LIBC_HEADERS <= stm32_union and _LIBC_HEADERS <= mspm0_union
    assert "stm32f10x_conf.h" in stm32_union
    assert "ti_msp_dl_config.h" in mspm0_union
    assert "ti_msp_dl_config.h" not in stm32_union  # 跨平台工具链头不混入
    assert "stm32f10x_conf.h" not in mspm0_union


def test_external_headers_unknown_platform_raises():
    with pytest.raises(UnknownPlatformError, match="未知平台.*esp32"):
        external_headers("esp32")


def test_unresolved_include_accepts_own_platform_toolchain_header_on_stm32(tmp_path):
    """stm32 + conf.h（STM32F1xx DFP 提供）→ 豁免通过。"""
    corpus = _memory_corpus(
        tmp_path,
        module_texts=[("mod", "mod.c", '#include "stm32f10x_conf.h"\n')],
    )

    _check_unresolved_includes(corpus)


def test_unresolved_include_accepts_own_platform_toolchain_header_on_mspm0(tmp_path):
    """mspm0 + SysConfig 头（构建时生成，工程树里没有）→ 豁免通过。"""
    corpus = ModuleCorpus(
        platform=PLATFORM_MSPM0,
        modules=(
            (
                "mod",
                (
                    ModuleFile(
                        rel="mod.c",
                        kind="c",
                        text='#include "ti_msp_dl_config.h"\n',
                        own_dir=tmp_path,
                    ),
                ),
            ),
        ),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(),
        search_dir_headers=(),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    _check_unresolved_includes(corpus)


def test_unresolved_include_rejects_cross_platform_toolchain_header_on_stm32(tmp_path):
    """跨平台工具链头不泄漏（刻意，修门禁洞）：stm32 工程 include SysConfig 头 → 拒绝。

    今天它静默过门禁、Keil 编译必失败——门禁存在的意义就是抓这个。
    """
    corpus = _memory_corpus(
        tmp_path,
        module_texts=[("mod", "mod.c", '#include "ti_msp_dl_config.h"\n')],
    )

    with pytest.raises(UnresolvedIncludeError, match="ti_msp_dl_config.h") as excinfo:
        _check_unresolved_includes(corpus)

    assert "引用了最终工程中不存在的头文件" in str(excinfo.value)


def test_unresolved_include_rejects_cross_platform_toolchain_header_on_mspm0(tmp_path):
    """跨平台工具链头不泄漏（刻意）：mspm0 工程 include DFP 配置头 → 拒绝。"""
    corpus = ModuleCorpus(
        platform=PLATFORM_MSPM0,
        modules=(
            (
                "mod",
                (
                    ModuleFile(
                        rel="mod.c",
                        kind="c",
                        text='#include "stm32f10x_conf.h"\n',
                        own_dir=tmp_path,
                    ),
                ),
            ),
        ),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(),
        search_dir_headers=(),
        master_project_dir=tmp_path,
        main_c="int main(void) { while (1); }\n",
    )

    with pytest.raises(UnresolvedIncludeError, match="stm32f10x_conf.h") as excinfo:
        _check_unresolved_includes(corpus)

    assert "引用了最终工程中不存在的头文件" in str(excinfo.value)


def test_generation_gate_table_complete_and_ordered():
    """门禁装配表钉死：9 键有序完整（顺序有语义——file_path_conflicts 依赖
    module_files 先报缺平台条目；timer_instance_conflicts 依赖 pin_bindings
    先校验载荷），增删 / 换序即红。"""
    assert [g.key for g in GENERATION_GATES] == [
        "module_files",
        "file_path_conflicts",
        "main_calls",
        "module_self_include",
        "unresolved_includes",
        "macro_conflicts",
        "pin_bindings",
        "timer_instance_conflicts",
        "no_pin_literals_in_main",
    ]


def test_run_generation_gates_invokes_all_in_order_and_stops_on_failure(
    monkeypatch,
):
    """runner 按表序全调、同一 (corpus, manifests, platform) 透传、首个失败即抛。

    表 = 装配唯一出处：generate 不再自写门禁循环，runner 是唯一执行方。
    """
    calls: list[tuple[str, object]] = []

    def record(label: str):
        def check(corpus, manifests, platform, context):
            calls.append((label, (corpus, manifests, platform, context)))

        return check

    def boom(corpus, manifests, platform, context):
        calls.append(("boom", None))
        raise GeneratorError("装配表门禁炸了")

    corpus, manifests, platform = object(), object(), "stm32"
    fake_gates = (
        GenerationGate("first", record("first")),
        GenerationGate("boom", boom),
        GenerationGate("never", record("never")),  # 首个失败即停，不应被调
    )
    monkeypatch.setattr("contest_generator.generator.GENERATION_GATES", fake_gates)
    context = GateContext()

    with pytest.raises(GeneratorError, match="装配表门禁炸了"):
        run_generation_gates(corpus, manifests, platform, context)

    assert [label for label, _ in calls] == ["first", "boom"]
    assert calls[0][1] == (corpus, manifests, platform, context)  # 参数原样透传


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


# ---------------------------------------------------------------------------
# mspm0 构建脚本（工单 mspm0-build-makefiles/01）：产物完整后写 CCS 标准
# Debug/makefile 集（模块条目 = 选中集推导，manifest 单源）；未探测到 CCS
# 工具链 → 跳过 + build_hint 提示，不阻断生成（决策记录 3）；stm32 零改动。
# ---------------------------------------------------------------------------


def test_generate_mspm0_writes_makefile_set_for_selected_modules(tmp_path):
    """mspm0 + ccs_tools 命中：Debug/makefile 集落盘，模块条目 = 选中集
    （dht11 + delay，delay 平铺 subdir 空），未选模块（oled）不出现；纯 .h
    目录（dht11/inc）不产生编译条目。"""
    from contest_generator.compile_runner import CcsTools

    library = make_fake_module_library(tmp_path / "modules")
    master = make_fake_ccs_theia_master_project(tmp_path / "master")
    manifests = [ModuleManifest.load(library / slug) for slug in ("dht11", "delay")]
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    compiler = tmp_path / "compiler"
    compiler.mkdir()
    cli = tmp_path / "cli.bat"
    cli.write_text("", encoding="utf-8")

    out_dir, _, build_hint = generate(
        platform=PLATFORM_MSPM0,
        manifests=manifests,
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content=MAIN_SKELETON,
        ccs_tools=CcsTools(sdk_dir=sdk, compiler_dir=compiler, sysconfig_cli=cli),
    )

    assert build_hint == ""
    makefile = (out_dir / "Debug" / "makefile").read_text(encoding="utf-8")
    assert "-include modules/dht11/mspm0/src/subdir_vars.mk" in makefile
    assert "-include modules/delay/subdir_vars.mk" in makefile  # 平铺（subdir 空）
    assert "oled" not in makefile  # 未选模块不出现（决策记录 2）
    assert "modules/dht11/inc" not in makefile  # 纯 .h 目录无编译条目
    assert (
        out_dir / "Debug" / "modules" / "dht11" / "mspm0" / "src" / "subdir_vars.mk"
    ).is_file()
    assert (out_dir / "Debug" / "modules" / "delay" / "subdir_vars.mk").is_file()
    # 结构摘要跳过 Debug/（treewalk 顶层构建产物目录），摘要不含构建脚本
    structure = tuple(
        p.relative_to(out_dir).as_posix() for p in iter_project_files(out_dir)
    )
    assert not any(rel.startswith("Debug") for rel in structure)


def test_generate_mspm0_without_ccs_tools_skips_and_hints(tmp_path):
    """mspm0 + ccs_tools None（未探测到）：生成照常、无 Debug/、build_hint
    非空（命令行构建不可用提示，不阻断——决策记录 3）。"""
    from contest_generator.compile_runner import CCS_NOT_FOUND_HINT

    library = make_fake_module_library(tmp_path / "modules")
    master = make_fake_ccs_theia_master_project(tmp_path / "master")
    out_dir, _, build_hint = generate(
        platform=PLATFORM_MSPM0,
        manifests=[ModuleManifest.load(library / "dht11")],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content=MAIN_SKELETON,
    )

    assert build_hint == CCS_NOT_FOUND_HINT
    assert (out_dir / "main.c").is_file()
    assert not (out_dir / "Debug").exists()


def test_generate_stm32_never_writes_makefile_set(tmp_path):
    """stm32 零改动（决策记录 5）：不写 Debug/makefile 集、hint 恒空。"""
    library = make_fake_module_library(tmp_path / "modules")
    master = make_fake_master_project(tmp_path / "master")
    out_dir, _, build_hint = generate(
        platform=PLATFORM_STM32,
        manifests=[ModuleManifest.load(library / "dht11")],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content=MAIN_SKELETON,
    )

    assert build_hint == ""
    assert not (out_dir / "Debug").exists()


def test_generate_project_mspm0_summary_carries_build_hint(
    fake_module_library, tmp_path
):
    """流程接缝（generate_project）：mspm0 摘要透传 build_hint——未探测到 →
    提示 + 无 Debug/；命中 → 空串 + makefile 集落盘。"""
    from contest_generator.compile_runner import CCS_NOT_FOUND_HINT, CcsTools

    masters_dir = tmp_path / "masters"
    make_fake_ccs_theia_master_project(masters_dir / "mspm0")

    summary = generate_project(
        platform=PLATFORM_MSPM0,
        slugs=["dht11", "delay"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out1",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )
    assert summary.build_hint == CCS_NOT_FOUND_HINT
    assert not (summary.output_dir / "Debug").exists()

    sdk = tmp_path / "sdk"
    sdk.mkdir()
    compiler = tmp_path / "compiler"
    compiler.mkdir()
    cli = tmp_path / "cli.bat"
    cli.write_text("", encoding="utf-8")
    with_tools = generate_project(
        platform=PLATFORM_MSPM0,
        slugs=["dht11", "delay"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out2",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        ccs_tools=CcsTools(sdk_dir=sdk, compiler_dir=compiler, sysconfig_cli=cli),
    )
    assert with_tools.build_hint == ""
    assert (with_tools.output_dir / "Debug" / "makefile").is_file()
    assert "Debug/makefile" not in with_tools.structure  # 摘要跳过构建产物


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
    """生成接线的素材区：赛题库 + 参考文件库 + 带套件 kit 的候选模块（各自
    独立临时目录，互不污染）。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_topic_specific_module(library)
    make_kit_candidate_module(library)
    topics = make_fake_topic_library(tmp_path / "topics")
    references = make_fake_reference_library(tmp_path / "references")
    return library, topics, references


def test_resolve_topic_context_explicit_key_materializes_entry(tmp_path):
    """显式编号：题面全文（长 PDF 题面全文只在选了该赛题时进上下文）+ 关联素材
    （锚定该题或候选模块套件的参考文件）。"""
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
    assert [e.id for e in ctx.references] == [
        TOPIC_REFERENCE_ID,
        KIT_REFERENCE_ID,
        UWB_REFERENCE_ID,
    ]


def test_resolve_topic_context_without_specific_modules_still_carries_kit_refs(
    tmp_path,
):
    """候选模块的 kit 词表锚定的参考文件仍经套件进清单（评审 c2：关联面
    不依赖任何"题专用模块"存在）。"""
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
    assert UWB_REFERENCE_ID in [e.id for e in ctx.references]


def test_resolve_topic_context_filters_candidates_by_platform(tmp_path):
    """推荐层平台过滤（工单 ref-platform-filter 模块侧对偶）：platform 给定
    时模块候选只含本平台有实现的条目——摘要行（模型可见）同源同滤
    （stm32-only 的 lock_control 不进 mspm0 候选）；stm32 全量库不受影响
    （stm32 有全部模块）。"""
    library, topics, references = _wired_dirs(tmp_path)

    mspm0 = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
        platform="mspm0",
    )
    assert mspm0 is not None
    assert {s.slug for s in mspm0.manifest_summaries} == {"dht11", "delay"}

    stm32 = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
        platform="stm32",
    )
    assert stm32 is not None
    assert {s.slug for s in stm32.manifest_summaries} == {
        "dht11",
        "delay",
        "oled",
        "broken",
        "lock_control",
        "uwb",
    }


def test_no_topic_context_filters_candidates_by_platform(tmp_path):
    """no-topic 形（粘贴题面未识别到历史赛题）同样按平台过滤候选（2026H 真机
    场景：粘贴题面 + mspm0，模型不该看到 stm32-only 模块）。"""
    library = make_fake_module_library(tmp_path / "modules")

    class NoNumberLLM:
        def topic_extract_number(self, text: str) -> None:
            return None

    ctx = resolve_topic_context(
        llm=NoNumberLLM(),
        topic_key="",
        problem_text="普通粘贴题面",
        module_library_dir=library,
        topic_library_dir=make_fake_topic_library(tmp_path / "topics"),
        reference_library_dir=tmp_path / "references",
        platform="mspm0",
    )
    assert ctx.key == ""
    assert {s.slug for s in ctx.manifest_summaries} == {"dht11", "delay"}


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
# import 面清零 + include 读侧对偶定义单址（工单 07）+ 模块源读路径单源（工单 01）
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


def test_generator_source_has_no_toolchain_header_literals():
    """结构自证：工具链头字面量只许在平台模块声明，生成核心源码零字面量。"""
    import contest_generator.generator as generator
    from pathlib import Path

    text = (Path(generator.__file__).parent / "generator.py").read_text(
        encoding="utf-8"
    )
    assert "stm32f10x_conf" not in text
    assert "ti_msp_dl_config" not in text


def test_external_header_declaration_origins():
    """结构自证：工具链外部头恰在 keil.py / ccs.py 声明（分派在 patchers.py）。"""
    import contest_generator.generator as generator
    from pathlib import Path

    src_root = Path(generator.__file__).parent
    keil_text = (src_root / "keil.py").read_text(encoding="utf-8")
    ccs_text = (src_root / "ccs.py").read_text(encoding="utf-8")
    patchers_text = (src_root / "patchers.py").read_text(encoding="utf-8")
    assert "EXTERNAL_HEADERS" in keil_text
    assert "EXTERNAL_HEADERS" in ccs_text
    assert "def external_headers" in patchers_text


def test_source_read_primitives_single_origin():
    """is_header_path / read_module_sources 定义单址 = skeleton.py。"""
    import contest_generator.skeleton as skeleton
    from pathlib import Path

    src_root = Path(skeleton.__file__).parent
    for primitive in ("is_header_path", "read_module_sources"):
        hits = [
            path.name
            for path in sorted(src_root.glob("*.py"))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(f"def {primitive}")
        ]
        assert hits == ["skeleton.py"], f"{primitive} 应单址 skeleton.py"


def test_skeleton_source_has_no_raw_read_text():
    """结构自证：skeleton.py 的 read_text 恰两处——模块源读盘唯一读点在原语
    read_module_sources 体内，母版头读盘在 build_master_interface_blocks（工单
    02，母版头段允许裸读，与 generator 的语料母版头段同规；新增模块源裸读即红）。"""
    import contest_generator.skeleton as skeleton
    from pathlib import Path

    text = (Path(skeleton.__file__).parent / "skeleton.py").read_text(
        encoding="utf-8"
    )
    assert text.count("read_text") == 2


def test_generator_module_file_segment_has_no_raw_read_text():
    """结构自证：build_module_corpus 模块文件段（manifests 循环到母版头之间）
    无裸 read_text——读盘全走 read_module_sources 原语（母版头段允许，原语范围外）。"""
    import contest_generator.generator as generator
    from pathlib import Path

    text = (Path(generator.__file__).parent / "generator.py").read_text(
        encoding="utf-8"
    )
    def_start = text.index("def build_module_corpus(")
    loop_start = text.index("    for manifest in manifests:", def_start)
    master_start = text.index("    master_headers:", loop_start)
    segment = text[loop_start:master_start]
    assert "read_text" not in segment


# ---------------------------------------------------------------------------
# 工单 01：手动选参考资料（追加准入 = 锚定 ∪ 手动，全文直读；no-topic 唯一准入）
# ---------------------------------------------------------------------------


def test_resolve_topic_context_manual_ids_added_as_admission(tmp_path):
    """手动准入（追加语义）：reference_ids → 手动条目进清单（来源标注 manual）+
    全文直读（manual_fulltexts）；锚定命中照旧自动进（并集，锚定两级不动）。"""
    library, topics, references = _wired_dirs(tmp_path)

    ctx = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="粘贴",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
        reference_ids=[OTHER_REFERENCE_ID],
    )

    # 锚定照旧自动进（追加语义）
    assert TOPIC_REFERENCE_ID in [s.id for s in ctx.suggestions]
    # 手动条目进清单（来源标注 manual）+ 全文直读
    manual = [s for s in ctx.suggestions if s.source == REFERENCE_SOURCE_MANUAL]
    assert [s.id for s in manual] == [OTHER_REFERENCE_ID]
    assert [e.id for e in ctx.manual_references] == [OTHER_REFERENCE_ID]
    assert "别的套件" in ctx.manual_fulltexts[OTHER_REFERENCE_ID]


def test_resolve_topic_context_manual_overlapping_anchor_deduped(tmp_path):
    """并集去重：同一条目既锚定命中又被手动选，清单只出现一次（保留锚定位置、
    标注手动）；全文仍直读（手动 = 全文直读强制）。"""
    library, topics, references = _wired_dirs(tmp_path)

    ctx = resolve_topic_context(
        llm=None,
        topic_key="2026C",
        problem_text="粘贴",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
        reference_ids=[TOPIC_REFERENCE_ID],
    )

    ids = [s.id for s in ctx.suggestions]
    assert ids.count(TOPIC_REFERENCE_ID) == 1
    topic = next(s for s in ctx.suggestions if s.id == TOPIC_REFERENCE_ID)
    assert topic.source == REFERENCE_SOURCE_MANUAL  # 手动优先标注（用户显式选择）
    assert TOPIC_REFERENCE_ID in ctx.manual_fulltexts  # 全文仍直读


def test_resolve_topic_context_no_topic_manual_is_only_admission(tmp_path):
    """no-topic + 手动选：手动条目是唯一准入（清单非空 + 全文直读 + 回读器可读
    手动条目）；未选 = 现行为（零参考）。"""
    library, topics, references = _wired_dirs(tmp_path)

    ctx = resolve_topic_context(
        llm=None,
        topic_key="",
        problem_text="粘贴题面",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
        reference_ids=[OTHER_REFERENCE_ID],
    )

    assert ctx.key == ""
    assert ctx.references == ()  # 锚定零命中
    assert [s.id for s in ctx.suggestions] == [OTHER_REFERENCE_ID]
    assert ctx.suggestions[0].source == REFERENCE_SOURCE_MANUAL
    assert "别的套件" in ctx.manual_fulltexts[OTHER_REFERENCE_ID]
    assert "别的套件" in ctx.read_fulltext(OTHER_REFERENCE_ID)  # 回读器可读手动条目

    bare = resolve_topic_context(
        llm=None,
        topic_key="",
        problem_text="粘贴题面",
        module_library_dir=library,
        topic_library_dir=topics,
        reference_library_dir=references,
    )
    assert bare.suggestions == () and bare.manual_fulltexts is None  # 未选 = 现行为


def test_resolve_topic_context_manual_unknown_id_raises(tmp_path):
    """手动幻觉 id：大声失败（不猜测、不静默忽略）。"""
    library, topics, references = _wired_dirs(tmp_path)

    with pytest.raises(ManualReferenceError, match="不存在"):
        resolve_topic_context(
            llm=None,
            topic_key="2026C",
            problem_text="粘贴",
            module_library_dir=library,
            topic_library_dir=topics,
            reference_library_dir=references,
            reference_ids=["幻觉 id"],
        )


# ---------------------------------------------------------------------------
# 工单 02：stm32 电机链路（motor/pid 补录 + pin_config.h + 母版头并入门禁）
# ---------------------------------------------------------------------------


def test_generate_stm32_motor_registers_module_and_pin_config(tmp_path):
    """选 motor 不选 pid stm32 生成：uvprojx 注册 motor_stm32.c、pin_config.h
    随母版进工程、EXTI2/4 计数中断随模块。"""
    library = make_fake_motor_pid_library(tmp_path / "modules")
    master = make_fake_stm32_ml_master(tmp_path / "master")
    manifests = [ModuleManifest.load(library / "motor")]
    out = generate(
        platform=PLATFORM_STM32,
        manifests=manifests,
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content="int main(void) { motor_init(); encoder_init(); while (1); }\n",
    )[0]

    # pin_config.h 随母版进工程根（IncludePath 补工程根后模块 include 可解析）
    assert (out / "pin_config.h").is_file()
    module_c = (out / "modules" / "motor" / "code" / "motor_stm32.c").read_text(
        encoding="utf-8"
    )
    assert "EXTI2_IRQHandler" in module_c
    assert "EXTI4_IRQHandler" in module_c
    assert "MOTOR_A_PWM_CH" in module_c  # 只引用宏，无硬编码引脚

    uvprojx = (out / "user" / "Project.uvprojx").read_text(encoding="utf-8")
    assert "modules\motor\code\motor_stm32.c" in uvprojx


def test_generate_stm32_motor_plus_pid_registers_isr_and_closes_loop(tmp_path):
    """选 motor+pid stm32 生成：uvprojx 注册 pid_isr.c、TIM3→pid_control 闭环在。"""
    library = make_fake_motor_pid_library(tmp_path / "modules")
    master = make_fake_stm32_ml_master(tmp_path / "master")
    manifests = [
        ModuleManifest.load(library / slug) for slug in ("motor", "pid")
    ]
    out = generate(
        platform=PLATFORM_STM32,
        manifests=manifests,
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content=(
            "int main(void) { motor_init(); encoder_init(); "
            "pid_init(&motorA, 0, 1, 0, 0); pid_init(&motorB, 0, 1, 0, 0); "
            "while (1); }\n"
        ),
    )[0]

    isr = (out / "modules" / "pid" / "code" / "pid_isr.c").read_text(encoding="utf-8")
    assert "TIM3_IRQHandler" in isr
    assert "Encoder_count1" in isr and "Encoder_count2" in isr
    assert "motorA.now" in isr and "motorB.now" in isr
    assert "pid_control();" in isr

    uvprojx = (out / "user" / "Project.uvprojx").read_text(encoding="utf-8")
    assert "modules\pid\code\pid_isr.c" in uvprojx


def test_generate_stm32_empty_selection_accepts_master_header_calls(tmp_path):
    """母版空生成（不选任何模块）：main.c 调母版 ml_* API 过门禁、能落盘。"""
    master = make_fake_stm32_ml_master(tmp_path / "master")

    out = generate(
        platform=PLATFORM_STM32,
        manifests=[],
        module_library_dir=make_fake_motor_pid_library(tmp_path / "modules"),
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content=(
            "int main(void) { pwm_init(TIM_2, TIM2_CH1, 1000); while (1); }\n"
        ),
    )[0]

    assert (out / "main.c").is_file()
    assert (out / "pin_config.h").is_file()


def test_check_main_calls_accepts_master_header_functions(tmp_path):
    """门禁接口集并入母版头：main.c 调母版头声明的函数不报未定义（mspm0
    母版无 .h 时并入为空，见 test_corpus_main_calls_fence_and_undefined_from_memory）。"""
    corpus = ModuleCorpus(
        platform=PLATFORM_STM32,
        modules=(),
        missing_platforms=(),
        missing_files=(),
        master_headers=(("ml_pwm.h", "void pwm_init(void);\n"),),
        master_search_dirs=(),
        search_dir_headers=(),
        master_project_dir=tmp_path,
        main_c="int main(void) { pwm_init(); while (1); }\n",
    )

    _check_main_calls(corpus)  # 不抛 UndefinedCallsError


def test_check_main_calls_still_rejects_unknown_calls_with_master_headers(tmp_path):
    """并入母版头不放松门禁：模块头与母版头都没有的函数仍明确报错。"""
    corpus = ModuleCorpus(
        platform=PLATFORM_STM32,
        modules=(),
        missing_platforms=(),
        missing_files=(),
        master_headers=(("ml_pwm.h", "void pwm_init(void);\n"),),
        master_search_dirs=(),
        search_dir_headers=(),
        master_project_dir=tmp_path,
        main_c="int main(void) { ghost(); while (1); }\n",
    )

    with pytest.raises(UndefinedCallsError, match="ghost"):
        _check_main_calls(corpus)
