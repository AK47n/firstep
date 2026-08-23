"""报告草稿渲染器核心 + 生成落盘（工单 report-draft-demo/02）。

主 seam = generate_project 流程级：report_draft_text 缺省空 = 不写报告文件
（旧行为逐字节不变，回归护栏）；非空 = 落盘 设计报告草稿.md（README / 演示
脚本之后、上下文清单之前），LLM 文本注入方案论证 / 软件流程两节，空文本 =
中文占位节不阻断。渲染器纯函数直测：确定性 / 尾部换行 / 章节齐全 / LLM 文本
注入 / 占位降级 / 引脚表与 README 同源（防漂移结构测试）/ 验证顺序与 README
同源 / 板名可选。
"""

from __future__ import annotations

import pytest

from contest_generator.demo_script import DEMO_SCRIPT_FILENAME
from contest_generator.generator import generate_project
from contest_generator.manifest import ModuleManifest, PinDeclaration, PlatformEntry
from contest_generator.patchers import PLATFORM_STM32
from contest_generator.readme import README_FILENAME, PIN_TABLE_FOOTNOTE, render_readme
from contest_generator.report_draft import REPORT_DRAFT_FILENAME, render_report_draft
from tests.fakes import MAIN_SKELETON, make_fake_master_project

# 固定章节标题（spec 章节语义；标题文案为本实现定稿）
H_OVERVIEW = "## 工程概览"
H_BLOCK = "## 系统框图"
H_SELECT = "## 模块选型表"
H_PINS = "## 引脚分配表"
H_TEST = "## 测试记录模板"
H_RATIONALE = "## 系统方案论证"
H_WORKFLOW = "## 软件流程设计"
PLACEHOLDER = "本节 AI 生成失败，请手动补充"


def _entry(pins: tuple[tuple[str, str, str, str, bool], ...] = ()) -> PlatformEntry:
    """(id, type, default, label, required) 序列 → PlatformEntry（files 空，
    渲染器只读 pins 声明）。"""
    return PlatformEntry(
        files=(),
        pins=tuple(
            PinDeclaration(
                id=pid,
                type=ptype,
                default=pdefault,
                label=plabel,
                required=preq,
            )
            for (pid, ptype, pdefault, plabel, preq) in pins
        ),
    )


def _m(
    slug: str,
    description: str,
    *,
    deps: tuple[str, ...] = (),
    pins: tuple[tuple[str, str, str, str, bool], ...] = (),
) -> ModuleManifest:
    """内存直构 manifest（platform = stm32）。"""
    return ModuleManifest(
        slug=slug,
        description=description,
        dependencies=deps,
        platforms={PLATFORM_STM32: _entry(pins)},
    )


# ---------------------------------------------------------------------------
# 渲染器纯函数直测：确定性 / 章节 / LLM 注入 / 占位 / 同源防漂移
# ---------------------------------------------------------------------------


def test_render_report_draft_same_input_same_output():
    """确定性：同一输入两次调用逐字节一致（无时间戳 / 随机源）。"""
    manifests = [_m("delay", "软件延时"), _m("dht11", "DHT11 温湿度传感器驱动", deps=("delay",))]
    llm = "方案论证文本\n软件流程文本"
    assert render_report_draft("stm32", "最小系统板", manifests, llm) == (
        render_report_draft("stm32", "最小系统板", manifests, llm)
    )


def test_render_report_draft_trailing_newline():
    """尾部换行幂等：返回文本恒以单个 \\n 收尾。"""
    assert render_report_draft("stm32", None, [], "").endswith("\n")
    assert not render_report_draft("stm32", None, [], "").endswith("\n\n")


def test_render_report_draft_all_sections():
    """七章齐全：概览 / 框图（依赖树 + 引脚连接）/ 选型表 / 引脚表 / 测试记录
    模板 / 方案论证 / 软件流程。"""
    manifests = [
        _m("delay", "软件延时"),
        _m("key", "独立按键输入", deps=("delay",)),
    ]
    text = render_report_draft("stm32", "蓝药丸", manifests, "论证\n\n流程")

    assert text.startswith("# 设计报告草稿\n")
    for heading in (H_OVERVIEW, H_BLOCK, H_SELECT, H_PINS, H_TEST, H_RATIONALE, H_WORKFLOW):
        assert heading in text
    assert "- 平台：STM32F103C8T6 / Keil5" in text
    assert "- 开发板：蓝药丸" in text


def test_render_report_draft_block_diagram_dependency_tree():
    """框图 = 依赖树（文本层次图：缩进 = 依赖层级，依赖先于使用者）+ 引脚
    连接表。"""
    manifests = [
        _m("delay", "软件延时"),
        _m("key", "独立按键输入", deps=("delay",)),
    ]
    text = render_report_draft("stm32", None, manifests, "x\n\nx")
    block = text.split(H_BLOCK)[1].split(H_SELECT)[0]

    assert "- delay：软件延时" in block
    assert "  - key：独立按键输入（依赖：delay）" in block
    assert block.index("- delay") < block.index("- key")


def test_render_report_draft_dependency_tree_deep_nesting():
    """多级依赖链缩进递增（a→b→c：c 缩进 0、b 缩进 1、a 缩进 2）。"""
    manifests = [
        _m("c", "底层模块"),
        _m("b", "中层模块", deps=("c",)),
        _m("a", "顶层模块", deps=("b",)),
    ]
    text = render_report_draft("stm32", None, manifests, "x\n\nx")
    block = text.split(H_BLOCK)[1].split(H_SELECT)[0]

    assert "- c：底层模块" in block
    assert "  - b：中层模块（依赖：c）" in block
    assert "    - a：顶层模块（依赖：b）" in block


def test_render_report_draft_pin_table_same_source_as_readme():
    """引脚表与 README 同源：报告「引脚分配表」行与 README「引脚接线表」行
    完全一致（防漂移结构测试）；尾注同源。"""
    manifests = [
        _m(
            "key",
            "独立按键输入",
            pins=(("KEY_START", "gpio_in", "PB3", "启动按键", True),),
        ),
    ]
    report = render_report_draft("stm32", None, manifests, "x\n\nx")
    readme = render_readme("stm32", None, manifests)

    report_rows = _pin_data_rows(report.split(H_PINS)[1])
    readme_rows = _pin_data_rows(readme.split("## 引脚接线表")[1])
    assert report_rows == readme_rows == ["| key | KEY_START（启动按键） | PB3 | gpio_in（必接） |"]
    assert PIN_TABLE_FOOTNOTE in report


def test_render_report_draft_verification_same_source_as_readme():
    """测试记录模板验证顺序与 README 验证顺序清单同源（bring-up 前置）。"""
    manifests = [
        _m("dht11", "DHT11 温湿度传感器驱动"),
        _m("delay", "软件延时"),
        _m("led", "状态指示灯"),
    ]
    report = render_report_draft("stm32", None, manifests, "x\n\nx")
    readme = render_readme("stm32", None, manifests)

    report_items = _checklist_items(report.split(H_TEST)[1])
    readme_items = _checklist_items(readme.split("## 验证顺序清单")[1])
    assert report_items == readme_items == [
        "delay — 软件延时",
        "led — 状态指示灯",
        "dht11 — DHT11 温湿度传感器驱动",
    ]


def test_render_report_draft_llm_text_injected():
    """LLM 文本注入：方案论证 / 软件流程两节 = 入参文本原样（段落间保留空行）。"""
    llm = "论证段落一\n\n论证段落二\n\n流程段落"
    text = render_report_draft("stm32", None, [], llm)

    rationale = text.split(H_RATIONALE)[1].split(H_WORKFLOW)[0].strip()
    workflow = text.split(H_WORKFLOW)[1].strip()
    assert rationale == "论证段落一\n\n论证段落二"
    assert workflow == "流程段落"


def test_render_report_draft_empty_llm_placeholder():
    """LLM 文本为空：两节仍渲染，中文占位提示（报告不阻断、不缺失章节）。"""
    text = render_report_draft("stm32", None, [], "")

    assert H_RATIONALE in text
    assert H_WORKFLOW in text
    assert PLACEHOLDER in text


def test_render_report_draft_single_paragraph_workflow_placeholder():
    """契约外输入（单段，无 \\n\\n 分隔）：整段作方案论证，软件流程节占位
    （该节缺内容 → 占位降级，不把契约问题伪装成成功）。"""
    text = render_report_draft("stm32", None, [], "只有一段论证")

    rationale = text.split(H_RATIONALE)[1].split(H_WORKFLOW)[0].strip()
    workflow = text.split(H_WORKFLOW)[1].strip()
    assert rationale == "只有一段论证"
    assert workflow == PLACEHOLDER


def test_render_report_draft_board_name_optional():
    """板名取不到（None）= 概览章不显示板名行。"""
    assert "- 开发板" not in render_report_draft("stm32", None, [], "x\n\nx")


# ---------------------------------------------------------------------------
# 流程级 seam：generate_project 落盘 设计报告草稿.md
# ---------------------------------------------------------------------------


def test_generate_project_no_report_draft_text_no_file(fake_module_library, tmp_path):
    """report_draft_text 缺省（空串）= 不写报告文件（旧行为逐字节不变）；演示
    脚本照常落盘（两产物互不依赖）。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )

    assert not (summary.output_dir / REPORT_DRAFT_FILENAME).exists()
    assert (summary.output_dir / DEMO_SCRIPT_FILENAME).is_file()


def test_generate_project_report_draft_written(fake_module_library, tmp_path):
    """report_draft_text 非空：落盘 设计报告草稿.md（README / 演示脚本之后），
    内容 = 确定性章节 + LLM 文本注入；写盘不触碰既有文件。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        report_draft_text="论证：采用 DHT11 直接测温。\n\n流程：初始化串口后轮询。",
    )
    report = (summary.output_dir / REPORT_DRAFT_FILENAME).read_text(encoding="utf-8")

    assert (summary.output_dir / REPORT_DRAFT_FILENAME).is_file()
    for heading in (H_OVERVIEW, H_BLOCK, H_SELECT, H_PINS, H_TEST, H_RATIONALE, H_WORKFLOW):
        assert heading in report
    assert "论证：采用 DHT11 直接测温。" in report
    assert "流程：初始化串口后轮询。" in report
    assert "- dht11：DHT11 温湿度传感器驱动" in report
    assert (summary.output_dir / README_FILENAME).is_file()
    assert (summary.output_dir / DEMO_SCRIPT_FILENAME).is_file()


def test_generate_project_report_draft_byte_deterministic(fake_module_library, tmp_path):
    """同一输入两次生成 → 设计报告草稿.md 逐字节一致。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    def _run(out) -> bytes:
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=out,
            module_library_dir=fake_module_library,
            masters_dir=masters_dir,
            report_draft_text="论证\n\n流程",
        )
        return (out / REPORT_DRAFT_FILENAME).read_bytes()

    assert _run(tmp_path / "out1") == _run(tmp_path / "out2")


def _pin_data_rows(text: str) -> list[str]:
    """引脚表数据行（剔除表头 `| 模块 |` 与分隔行 `|---|`）。"""
    return [
        ln
        for ln in text.splitlines()
        if ln.startswith("| ") and not ln.startswith("| 模块") and not ln.startswith("|---")
    ]


def _checklist_items(text: str) -> list[str]:
    """checkbox 行内容（slug — description）。"""
    return [
        ln.removeprefix("- [ ] ")
        for ln in text.splitlines()
        if ln.startswith("- [ ] ")
    ]
