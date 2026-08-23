"""演示脚本渲染器核心 + 生成落盘（工单 report-draft-demo/01）。

主 seam = generate_project 流程级：生成工程根多出 演示脚本.md，断言评分点分区
组织（操作 / 预期现象 / 对应需求与模块）、桥接正确（sentence_refs ↔
requirement.sentence 同编号体系）、降级链（无评分点 = 功能需求驱动；皆无 =
模块清单验证）、尾部「请按实物调整」注明、幂等（两次生成逐字节一致）。渲染器
纯函数直测：确定性 / 尾部换行 / 评分点小节格式 / 未关联需求独立成条不丢弃 /
需求驱动 / 模块兜底 / refs 空不桥接 / 畸形需求防御。
"""

from __future__ import annotations

from typing import Any

from contest_generator.demo_script import (
    DEMO_SCRIPT_FILENAME,
    render_demo_script,
)
from contest_generator.generator import generate_project
from contest_generator.manifest import ModuleManifest, PlatformEntry
from contest_generator.patchers import PLATFORM_STM32
from contest_generator.selection import ScorePoint
from tests.fakes import MAIN_SKELETON, make_fake_master_project

# 固定章节标题 / 话术（spec 逐字规定）
HEADING_PREPARE = "## 演示前准备"
HEADING_SCORE = "## 评分点演示"
HEADING_EXTRA = "## 补充功能需求演示"
HEADING_REQ = "## 功能需求演示"
HEADING_MANIFEST = "## 模块验证演示"
ADJUST_NOTE = "请按实物调整"

# 需求 dict 形状 = generate() requirements 参数直传形状（webapp 载荷原样：
# 键 requirement / sentence / modules / suggestions）
REQ_MEASURE = {
    "requirement": "测量距离",
    "sentence": 2,
    "modules": ["dht11"],
    "suggestions": [],
}
REQ_KEY = {
    "requirement": "启动控制",
    "sentence": 3,
    "modules": ["key", "delay"],
    "suggestions": [],
}
REQ_STORE = {
    "requirement": "存储记录",
    "sentence": 4,
    "modules": [],
    "suggestions": [{"name": "eeprom", "reason": "库外"}],
}


def _m(slug: str, description: str) -> ModuleManifest:
    """内存直构 manifest（platform = stm32，渲染器只读 slug/description）。"""
    return ModuleManifest(
        slug=slug,
        description=description,
        dependencies=(),
        platforms={PLATFORM_STM32: PlatformEntry(files=(), pins=())},
    )


# ---------------------------------------------------------------------------
# 渲染器纯函数直测：确定性 / 尾部换行 / 三模式 / 桥接 / 降级 / 防御
# ---------------------------------------------------------------------------


def test_render_demo_script_same_input_same_output():
    """确定性：同一输入两次调用逐字节一致（无时间戳 / 随机源）。"""
    points = (ScorePoint("B1", "basic", "完成测距", 10.0, (2, 3)),)
    reqs = [REQ_MEASURE]
    manifests = [_m("dht11", "DHT11 温湿度传感器驱动")]
    assert render_demo_script(points, reqs, manifests) == render_demo_script(
        points, reqs, manifests
    )


def test_render_demo_script_trailing_newline():
    """尾部换行幂等：返回文本恒以单个 \\n 收尾。"""
    assert render_demo_script((), [], []).endswith("\n")
    assert not render_demo_script((), [], []).endswith("\n\n")


def test_render_demo_script_score_point_section():
    """评分点分区组织：每评分点小节 = 标题（编号 描述 分区 分值）+ 操作 /
    预期现象 / 对应功能需求（sentence_refs 桥接）/ 对应模块；头段与尾部
    「请按实物调整」注明恒在。"""
    points = (
        ScorePoint("B1", "basic", "完成测距", 10.0, (2, 3)),
        ScorePoint("D1", "development", "提高精度", None, ()),
    )
    text = render_demo_script(points, [REQ_MEASURE, REQ_KEY], [_m("dht11", "DHT11 温湿度传感器驱动")])

    assert text.startswith("# 演示脚本\n")
    assert HEADING_PREPARE in text
    assert HEADING_SCORE in text
    assert ADJUST_NOTE in text

    # B1：标题 + 操作/预期现象 + 桥接到句子 2、3 的需求（REQ_MEASURE 挂句子 2
    # → 关联；REQ_KEY 挂句子 3 → 也关联）；对应模块行带 manifest 描述（能力
    # 方向，库外 slug 只显 slug）
    assert "### B1 完成测距（基础 · 10 分）" in text
    assert "- 操作：演示「完成测距」，对应句子 2、3" in text
    assert "- 预期现象：「完成测距」按题面要求呈现" in text
    assert "- 对应功能需求：测量距离（句子 2）；启动控制（句子 3）" in text
    assert "- 对应模块：dht11（DHT11 温湿度传感器驱动）、key、delay" in text

    # D1：refs 空 = 操作行不带句子引用；未关联需求 = 明确标注，不编造
    assert "### D1 提高精度（发挥 · 未标分）" in text
    assert "- 操作：演示「提高精度」" in text
    assert "- 预期现象：「提高精度」按题面要求呈现" in text
    assert "- 对应功能需求：未关联到具体需求" in text
    assert "- 对应模块：未命中库内模块" in text


def test_render_demo_script_unlinked_requirement_kept():
    """桥接不上的需求（句子不在任何评分点 refs）独立成条进补充节，不丢弃。"""
    points = (ScorePoint("B1", "basic", "完成测距", 10.0, (2,)),)
    text = render_demo_script(points, [REQ_STORE], [_m("dht11", "DHT11 温湿度传感器驱动")])

    assert HEADING_EXTRA in text
    assert "### 存储记录（句子 4）" in text
    assert "- 对应模块：未命中库内模块" in text
    assert "- 操作：演示「存储记录」" in text
    assert "- 预期现象：「存储记录」相关现象正常呈现" in text
    # 评分点小节内不出现该需求
    assert "对应功能需求：存储记录" not in text


def test_render_demo_script_no_score_points_requirement_driven():
    """无评分点：功能需求驱动——每需求独立小节（操作 / 预期现象 / 对应模块）。"""
    text = render_demo_script((), [REQ_MEASURE], [_m("dht11", "DHT11 温湿度传感器驱动")])

    assert HEADING_SCORE not in text
    assert HEADING_REQ in text
    assert "### 测量距离（句子 2）" in text
    assert "- 对应模块：dht11（DHT11 温湿度传感器驱动）" in text
    assert "- 操作：演示「测量距离」" in text
    assert "- 预期现象：「测量距离」相关现象正常呈现" in text
    assert ADJUST_NOTE in text


def test_render_demo_script_empty_falls_back_to_manifests():
    """评分点与需求皆无：模块清单验证演示项，不崩、不空文件。"""
    text = render_demo_script(
        (), [], [_m("delay", "软件延时"), _m("dht11", "DHT11 温湿度传感器驱动")]
    )

    assert HEADING_MANIFEST in text
    assert "- delay：软件延时" in text
    assert "- dht11：DHT11 温湿度传感器驱动" in text
    assert ADJUST_NOTE in text


def test_render_demo_script_malformed_requirement_skipped():
    """畸形需求（缺 requirement / sentence 非整数（含 bool，int 子类）/
    编号非 1 起）防御性跳过，不崩；缺 modules 键按未命中处理（有效需求 →
    需求驱动模式）。"""
    malformed: list[dict[str, Any]] = [
        {"sentence": 2, "modules": ["dht11"], "suggestions": []},  # 缺 requirement
        {"requirement": "脑补需求", "sentence": "三", "modules": [], "suggestions": []},  # sentence 非整数
        {"requirement": "布尔句子", "sentence": True, "modules": [], "suggestions": []},  # bool 是 int 子类
        {"requirement": "零号句子", "sentence": 0, "modules": [], "suggestions": []},  # 编号非 1 起
        {"requirement": "无模块键", "sentence": 5, "suggestions": []},
    ]
    text = render_demo_script((), malformed, [_m("delay", "软件延时")])

    assert "脑补需求" not in text
    assert "布尔句子" not in text
    assert "零号句子" not in text
    assert "无模块键" in text
    assert "- 对应模块：未命中库内模块" in text
    assert HEADING_REQ in text


# ---------------------------------------------------------------------------
# 流程级 seam：generate_project 落盘 演示脚本.md
# ---------------------------------------------------------------------------


def test_generate_project_writes_demo_script(fake_module_library, tmp_path):
    """生成工程根多出 演示脚本.md：评分点 + 需求 + 模块全部进入；桥接正确；
    尾部注明恒在。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        score_points=(
            ScorePoint("B1", "basic", "完成测距", 10.0, (2,)),
            ScorePoint("D1", "development", "提高精度", None, ()),
        ),
        requirements=[REQ_MEASURE, REQ_STORE],
    )

    demo = (summary.output_dir / DEMO_SCRIPT_FILENAME).read_text(encoding="utf-8")
    assert (summary.output_dir / DEMO_SCRIPT_FILENAME).is_file()
    assert HEADING_SCORE in demo
    assert "### B1 完成测距（基础 · 10 分）" in demo
    assert "- 操作：演示「完成测距」，对应句子 2" in demo
    assert "- 对应功能需求：测量距离（句子 2）" in demo
    assert "- 对应模块：dht11（DHT11 温湿度传感器驱动）" in demo
    assert "### D1 提高精度（发挥 · 未标分）" in demo
    # 未关联需求（存储记录，句子 4）独立成条
    assert HEADING_EXTRA in demo
    assert "### 存储记录（句子 4）" in demo
    assert ADJUST_NOTE in demo


def test_generate_project_demo_script_byte_deterministic(fake_module_library, tmp_path):
    """同一输入两次生成 → 演示脚本.md 逐字节一致（不含时间戳，可测试）。"""
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
            score_points=(ScorePoint("B1", "basic", "完成测距", 10.0, (2,)),),
            requirements=[REQ_MEASURE],
        )
        return (out / DEMO_SCRIPT_FILENAME).read_bytes()

    assert _run(tmp_path / "out1") == _run(tmp_path / "out2")


def test_generate_project_demo_script_defaults_self_contained(
    fake_module_library, tmp_path
):
    """缺省数据（无评分点 / 无需求）：演示脚本仍落盘，内容 = 模块清单验证
    演示（自洽，不空文件）；README 先例的其它文件不受影响。"""
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
    demo = (summary.output_dir / DEMO_SCRIPT_FILENAME).read_text(encoding="utf-8")

    assert HEADING_SCORE not in demo
    assert HEADING_REQ not in demo
    assert HEADING_MANIFEST in demo
    assert "- dht11：DHT11 温湿度传感器驱动" in demo
    assert ADJUST_NOTE in demo
