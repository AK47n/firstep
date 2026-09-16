"""参考文件库（工单 02）：录入 / 浏览搜索 / 归档动作与确认事务 / webapp 路由。

参考文件库：磁盘目录即数据库（一个条目一个目录：reference.json + 素材文件
本体，内容自持——归档 = 复制入库，源工程删除不丢）。录入流程复用模块库的
草稿→校验→入库模式：AI 通读素材生成简介草稿（llm.reference_summarize）→
用户补锚定（赛题编号 或 模块库已有 kit 词表内的套件型号）→ 结构校验通过
才入库、失败不留半成品。归档动作挂在提炼报告动作表上（ArchiveDecision，
只对判定范围内文件合法；残留 / main.c / 基础设施 / 二进制 / 工程配置文件
由规则确定性处置、不配归档），随确认事务一起提交：LLM 判定归档价值 + 生成
简介（全部在写盘前）→ 母版入库 → 归档条目复制入库（批回滚，失败不留半成品）。

假 LLM 用本文件自带的 ReferenceLLM（只实现工单 02 协议方法）——既有
FakeLLM（tests/fakes.py）无 reference_* 方法，既有测试也不应被本工单改动。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Sequence

import pytest
from fastapi.testclient import TestClient

from contest_generator.config import AppConfig
from contest_generator.master import (
    confirm_distillation,
    distill_master,
    scan_project,
)
from contest_generator.master_store import MasterError, list_masters
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator import reference_library
from contest_generator.reference_library import (
    ANCHOR_KIND_KIT,
    ANCHOR_KIND_NONE,
    ANCHOR_KIND_TOPIC,
    ARCHIVE_ENTRY_TYPE,
    MODULE_PERIPHERAL_TERMS,
    PERIPHERAL_SYNONYM_GROUPS,
    PERIPHERAL_TERMS,
    REFERENCE_FILE_CAP,
    ReferenceError,
    add_reference,
    archive_reference,
    build_material_manifest,
    build_topic_framework,
    delete_reference,
    draft_description,
    get_reference,
    list_entry_files,
    list_references,
    match_entry_files,
    module_kit_vocabulary,
    pdf_referenced_by,
    platform_matches,
    read_fulltext,
    related_references,
    resolve_entry_file,
    search_references,
    update_reference,
    validate_topic_anchor,
)
from contest_generator.report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    ArchiveDecision,
    DistillationReport,
    FileDecision,
    ReferenceCandidate,
    ReportError,
)
from contest_generator.webapp import AppContext, create_app
from tests.fakes import FakeLLM, make_fake_stm32_projects
from tests.generate_wiring_fakes import (
    KIT_REFERENCE_ID,
    TOPIC_REFERENCE_ID,
    make_fake_reference_library,
)

# ---------------------------------------------------------------------------
# 假件与构造助手
# ---------------------------------------------------------------------------

KIT_ALX = "ALX-AOA-FIT"
KIT_MSPM0 = "地猛星-MSPM0"


class ReferenceLLM(FakeLLM):
    """工单 02 假 LLM：固定返回参考文件简介 / 归档判定，并记录调用输入。

    继承 FakeLLM 以保持协议全量实现（其余职责用默认空行为，参考流程只用
    下面两个）。
    """

    def __init__(
        self,
        summary: str = "AI 生成的参考文件简介",
        archivable: Sequence[str] = (),
    ) -> None:
        super().__init__()
        self._summary = summary
        self._archivable = tuple(archivable)
        self.summary_calls: list[tuple[str, ...]] = []
        self.judge_calls: list[tuple[ReferenceCandidate, ...]] = []

    def reference_summarize(self, material: str) -> str:
        self.summary_calls.append((material,))
        return self._summary

    def reference_judge_archivable(
        self, candidates: Sequence[ReferenceCandidate]
    ) -> tuple[str, ...]:
        self.judge_calls.append(tuple(candidates))
        return self._archivable


def _write_module(library: Path, slug: str, kit: str) -> None:
    """在模块库写一个带 kit 的模块（身份字段必填：硬件绑定条目）。"""
    module_dir = library / slug
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "description": f"{slug} 驱动",
                "platforms": {
                    "stm32": {
                        "files": ["src.c"],
                        "verified": True,
                        "hardware_bound": True,
                        "kit": kit,
                        "source_url": "https://item.jd.com/1000123456.html",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (module_dir / "src.c").write_text(f"/* {slug} */\n", encoding="utf-8")


def _kit_library(tmp_path: Path) -> Path:
    """带 kit 词表的假模块库：ALX-AOA-FIT（双模块）+ 地猛星-MSPM0。"""
    library = tmp_path / "module_library"
    _write_module(library, "uwb", KIT_ALX)
    _write_module(library, "motor", KIT_ALX)
    _write_module(library, "ml_mpu6050", KIT_MSPM0)
    return library


EXAMPLE_C = "/* 例程 */\nvoid example(void);\n"


def _sample_files() -> dict[str, str]:
    return {"example.c": EXAMPLE_C}


def _reference_root(tmp_path: Path) -> Path:
    return tmp_path / "references"


# 母版提炼假工程（tests.fakes 构造）的判定范围与典型 AI 判定：与
# test_master.DEFAULT_DECISIONS 同形状（公共 keep × 2、独有 keep / exclude、
# 冲突 merge）。
MERGED_OLED = "/* 通用 OLED 驱动（整合版） */\nvoid oled_init(void);\n"
DEFAULT_DECISIONS = (
    FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="官方库配置头，基础必需"),
    FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="系统初始化，基础必需"),
    FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用传感器驱动，应进母版"),
    FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="上一场比赛的字体表残留"),
    FileDecision(
        "src/oled.c",
        ACTION_MERGE,
        content=MERGED_OLED,
        explanation="两版接口一致，整合去重",
        source="proj-b",
        reason="B 版本较新",
    ),
)


def _distilled_report(tmp_path: Path) -> tuple[DistillationReport, tuple[Path, Path]]:
    projects = make_fake_stm32_projects(tmp_path / "old_projects")
    report = distill_master(
        FakeLLM(distillation=DEFAULT_DECISIONS),
        PLATFORM_STM32,
        [scan_project(p) for p in projects],
    )
    return report, projects


def _confirm_payload(report: DistillationReport, projects: Sequence[Path]) -> dict:
    return {
        **report.to_dict(),
        "project_dirs": [str(p) for p in projects],
    }


def _write_config(path: Path, module_library_dir: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "api_key": "test-key",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-v4-flash",
                "module_library_dir": str(module_library_dir),
                "masters_dir": str(path.parent / "masters"),
            }
        ),
        encoding="utf-8",
    )


def _app(tmp_path: Path, llm: ReferenceLLM) -> TestClient:
    config_path = tmp_path / ".contest_generator" / "config.json"
    _write_config(config_path, _kit_library(tmp_path))
    ctx = AppContext(
        config_path=config_path,
        llm_factory=lambda cfg: llm,  # type: ignore[arg-type]
    )
    return TestClient(create_app(ctx))


# ---------------------------------------------------------------------------
# 锚定校验
# ---------------------------------------------------------------------------


def test_validate_topic_anchor_accepts_year_and_code():
    validate_topic_anchor("2026C")
    validate_topic_anchor("2021F")


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "2026",
        "C2026",
        "26C",
        "2026CDE",
        "2026-C",
        "2026c1",
        "2026 年 C 题",
        # 旧锚定正则（^\d{4}[A-Za-z]{1,2}$）会放行、赛题库永远存不了的编号：
        # 与赛题库 key 同源后必须一并拒绝（大小写 / 多字母在大小写不敏感的
        # Windows 上会与既有条目撞目录，跨平台行为不一致）
        "2026c",
        "2026a",
        "2026AB",
    ],
)
def test_validate_topic_anchor_rejects_bad_format(bad: str):
    with pytest.raises(ReferenceError, match="格式非法"):
        validate_topic_anchor(bad)


def test_validate_topic_anchor_agrees_with_topic_key_validation():
    """锚定校验与赛题库 key 校验同源（放行集合一致，契约测试）。"""
    from contest_generator.topic_library import validate_topic_key

    for sample in ["2026C", "2021F", "2026c", "2026AB", "2026", "2026CDE", "2019H"]:
        anchor_rejects = False
        try:
            validate_topic_anchor(sample)
        except ReferenceError:
            anchor_rejects = True
        assert anchor_rejects == (validate_topic_key(sample) is not None)


def test_module_kit_vocabulary_collects_deduplicates_and_preserves_order(tmp_path):
    """词表语义以 manifest.collect_kits 为准（保序去重）：顺序 = 模块按 slug
    排序 × 平台条目插入顺序 × 首次出现（工单 C3 起不再排序）。"""
    library = _kit_library(tmp_path)

    assert module_kit_vocabulary(library) == (KIT_MSPM0, KIT_ALX)


# ---------------------------------------------------------------------------
# 录入：草稿 → 校验 → 入库（磁盘目录即数据库，事务）
# ---------------------------------------------------------------------------


def test_draft_description_uses_ai_summary(tmp_path):
    llm = ReferenceLLM(summary="例程简介草稿")
    files = _sample_files()

    draft = draft_description(llm, files)

    assert draft == "例程简介草稿"
    assert len(llm.summary_calls) == 1
    # 草稿与入库校验用同一份素材拼装：文件名标注 + 全文
    assert "example.c" in llm.summary_calls[0][0]
    assert "/* 例程 */" in llm.summary_calls[0][0]


def test_add_reference_topic_anchor_roundtrip(tmp_path):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="2026C 数字钥匙例程",
        type="例程工程",
        description="开门控制逻辑示例",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )

    assert entry.id == "2026C-数字钥匙例程"
    assert (root / entry.id / "example.c").read_text(encoding="utf-8") == EXAMPLE_C
    meta = json.loads((root / entry.id / "reference.json").read_text(encoding="utf-8"))
    assert meta["title"] == "2026C 数字钥匙例程"
    assert meta["anchor_kind"] == ANCHOR_KIND_TOPIC
    assert meta["anchor_value"] == "2026C"
    assert meta["files"] == ["example.c"]
    assert get_reference(root, entry.id) == entry
    assert [e.id for e in list_references(root)] == [entry.id]
    # 体量 = 磁盘实况（元数据不含，读盘补全）：目录仅 example.c + reference.json
    # 两个文件，size 恰为两者磁盘字节和（write_text 的换行翻译以实读字节为准）
    assert entry.file_count == 2
    assert entry.size_bytes == (
        (root / entry.id / "example.c").stat().st_size
        + (root / entry.id / "reference.json").stat().st_size
    )
    data = entry.to_dict()
    assert data["file_count"] == 2
    assert data["size_bytes"] == entry.size_bytes


def test_pdf_referenced_by_matches_same_basename(tmp_path):
    """删除影响说明（工单 ux-walkthrough-02/16）：条目文件与素材 PDF 同名
    （跨目录）→ 命中并返回条目标题；无关名字 → 空列表；空路径 → 空列表。"""
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="2026C 赛题资料",
        type="说明",
        description="含传感器手册",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"规约.pdf": "pdf-bytes", "对应.pdf": "pdf-bytes"},
        kit_vocabulary=(),
    )
    assert pdf_referenced_by(root, "批一/子/规约.pdf") == ["2026C 赛题资料"]
    assert pdf_referenced_by(root, "批二/子/规约.PDF") == ["2026C 赛题资料"]  # 大小写不敏感
    assert pdf_referenced_by(root, "批一/子/无关.pdf") == []
    assert pdf_referenced_by(root, "") == []


def test_reference_mtime_roundtrip(tmp_path):
    """mtime（ux-polish-02/07）：入库/读回/更新/归档都带元数据 mtime——
    「最近更新」排序数据源；该字段只进序列化响应，不写进 reference.json。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="mtime 测试条目",
        type="说明",
        description="带 mtime",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"note.txt": "hello"},
        kit_vocabulary=(),
    )
    assert entry.mtime > 0
    assert "mtime" not in entry.to_dict()   # 磁盘/域序列化不含 mtime（写盘兼容）
    assert get_reference(root, entry.id).mtime == entry.mtime
    assert list_references(root)[0].mtime == entry.mtime
    # 元数据文件本身不含 mtime 键（写盘逐字节兼容）
    meta = json.loads((root / entry.id / "reference.json").read_text(encoding="utf-8"))
    assert "mtime" not in meta


def test_add_reference_platform_roundtrip(tmp_path):
    """平台属性（工单 01）：入库带 platform → 元数据落盘、读盘回读、序列化带出。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="巡线模板",
        type="参考例程",
        description="2024H 巡线小车配套例程",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2024H",
        platform="mspm0",
        files=_sample_files(),
        kit_vocabulary=(),
    )

    assert entry.platform == "mspm0"
    meta = json.loads((root / entry.id / "reference.json").read_text(encoding="utf-8"))
    assert meta["platform"] == "mspm0"
    assert get_reference(root, entry.id).platform == "mspm0"
    assert entry.to_dict()["platform"] == "mspm0"


def test_add_reference_platform_defaults_to_any(tmp_path):
    """缺省 = any（平台无关）：既有录入流程不带 platform 字段行为不变。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="通用开发板资料",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files=_sample_files(),
        kit_vocabulary=(),
    )

    assert entry.platform == "any"
    assert get_reference(root, entry.id).platform == "any"


def test_add_reference_rejects_invalid_platform(tmp_path):
    """词表外平台属性大声失败（与锚定词表同款严格）：esp32 不在 stm32 / mspm0 /
    any 词表内。"""
    root = _reference_root(tmp_path)
    with pytest.raises(ReferenceError, match="非法平台属性"):
        add_reference(
            root,
            title="ESP32 资料",
            type="说明书",
            description="x",
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            platform="esp32",
            files=_sample_files(),
            kit_vocabulary=(),
        )
    assert list_references(root) == []  # 失败不留半成品


def test_reference_entry_platform_defaults_to_any_for_old_meta(tmp_path):
    """旧条目（reference.json 无 platform 字段）：读盘缺省 any，向后兼容。"""
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="旧条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    entry = get_reference(root, list_references(root)[0].id)
    entry_dir = root / entry.id
    data = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    data.pop("platform")
    (entry_dir / "reference.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    assert get_reference(root, entry.id).platform == "any"


def test_reference_entry_from_dict_rejects_invalid_platform(tmp_path):
    """词表外平台属性 = 元数据损坏：浏览时大声失败，不把坏数据带进列表。"""
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="正常条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    entry = get_reference(root, list_references(root)[0].id)
    entry_dir = root / entry.id
    data = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    data["platform"] = "esp32"
    (entry_dir / "reference.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ReferenceError, match="元数据不合法"):
        list_references(root)


def test_add_reference_topic_type_roundtrip(tmp_path):
    """题型标记（工单 topic-framework/01）：入库带 topic_type → 元数据落盘、
    读盘回读、序列化带出。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="巡线决策例程",
        type="例程代码",
        description="2021F 巡线送药小车决策层源码",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        topic_type="line_follow",
        files=_sample_files(),
        kit_vocabulary=(),
    )

    assert entry.topic_type == "line_follow"
    meta = json.loads((root / entry.id / "reference.json").read_text(encoding="utf-8"))
    assert meta["topic_type"] == "line_follow"
    assert get_reference(root, entry.id).topic_type == "line_follow"
    assert entry.to_dict()["topic_type"] == "line_follow"


def test_add_reference_topic_type_defaults_empty(tmp_path):
    """缺省 = 未标记（""）：既有录入流程不带 topic_type 字段行为不变。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="通用开发板资料",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files=_sample_files(),
        kit_vocabulary=(),
    )

    assert entry.topic_type == ""
    assert get_reference(root, entry.id).topic_type == ""


def test_add_reference_rejects_invalid_topic_type(tmp_path):
    """词表外题型大声失败（与平台 / 锚定词表同款严格）。"""
    root = _reference_root(tmp_path)
    with pytest.raises(ReferenceError, match="非法题型"):
        add_reference(
            root,
            title="神秘题型资料",
            type="说明书",
            description="x",
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            topic_type="mystery_type",
            files=_sample_files(),
            kit_vocabulary=(),
        )


def test_reference_entry_from_dict_defaults_topic_type_for_old_meta(tmp_path):
    """旧条目（reference.json 无 topic_type 字段）：读盘缺省 ""，向后兼容。"""
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="旧格式条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    entry = get_reference(root, list_references(root)[0].id)
    entry_dir = root / entry.id
    data = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    data.pop("topic_type")
    (entry_dir / "reference.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    assert get_reference(root, entry.id).topic_type == ""


def test_reference_entry_from_dict_rejects_invalid_topic_type(tmp_path):
    """词表外题型 = 元数据损坏：浏览时大声失败，不把坏数据带进列表。"""
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="正常条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    entry = get_reference(root, list_references(root)[0].id)
    entry_dir = root / entry.id
    data = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    data["topic_type"] = "mystery_type"
    (entry_dir / "reference.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ReferenceError, match="元数据不合法"):
        list_references(root)


def test_update_reference_topic_type_roundtrip(tmp_path):
    """编辑改题型（工单 topic-framework/01）：元数据更新落盘 + 回读。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="待编辑条目",
        type="例程代码",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    updated = update_reference(
        root,
        entry.id,
        title="待编辑条目",
        type="例程代码",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        add_files={},
        remove_files=(),
        kit_vocabulary=(),
        topic_type="line_follow",
    )

    assert updated.topic_type == "line_follow"
    assert get_reference(root, entry.id).topic_type == "line_follow"


def test_build_topic_framework_returns_none_without_topic_type(tmp_path):
    """未标记题型 → None（无框架段，向后兼容）。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="无题型条目",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    assert reference_library.build_topic_framework(root, entry) is None


def test_build_topic_framework_reads_framework_file(tmp_path):
    """正常读取：framework/main.c 全文返回（utf-8）。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="巡线决策例程",
        type="例程代码",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        topic_type="line_follow",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    framework_dir = root / entry.id / "framework"
    framework_dir.mkdir()
    framework = "/* 巡线决策框架 */\ntypedef enum { S_IDLE, S_FOLLOW } state_t;\n"
    (framework_dir / "main.c").write_text(framework, encoding="utf-8")

    assert reference_library.build_topic_framework(root, entry) == framework


def test_build_topic_framework_missing_file_returns_none(tmp_path):
    """标了题型但文件缺失 → None（降级不抛错，走全文注入现行为）。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="巡线决策例程",
        type="例程代码",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        topic_type="line_follow",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    assert reference_library.build_topic_framework(root, entry) is None


def test_read_fulltext_excludes_framework_control_file(tmp_path):
    """控制文件隔离：read_fulltext 不含 framework/main.c（与注入段不重复）。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="巡线决策例程",
        type="例程代码",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        topic_type="line_follow",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    framework_dir = root / entry.id / "framework"
    framework_dir.mkdir()
    (framework_dir / "main.c").write_text("/* 框架段 */\n", encoding="utf-8")

    fulltext = read_fulltext(root, entry)
    assert "框架段" not in fulltext
    assert "example.c" in fulltext


def test_add_reference_rejects_framework_control_file(tmp_path):
    """控制文件防双份（工单 topic-framework/02 违例）：framework/main.c 不能
    录入为素材（否则 read_fulltext 与确定性注入双份）。"""
    root = _reference_root(tmp_path)
    with pytest.raises(ReferenceError, match="控制文件"):
        add_reference(
            root,
            title="巡线决策例程",
            type="例程代码",
            description="x",
            anchor_kind=ANCHOR_KIND_TOPIC,
            anchor_value="2021F",
            files={"framework/main.c": "/* 框架段 */\n"},
            kit_vocabulary=(),
        )


def test_entry_stats_counts_framework_dir(tmp_path):
    """体量照旧磁盘实况：framework/ 控制目录也计入（与删除影响面一致）。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="巡线决策例程",
        type="例程代码",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    framework_dir = root / entry.id / "framework"
    framework_dir.mkdir()
    (framework_dir / "main.c").write_text("/* 框架段 */\n", encoding="utf-8")
    count, total = reference_library.entry_stats(root / entry.id)

    assert count == 3  # example.c + reference.json + framework/main.c
    assert total > len("/* 框架段 */\n")


def _mirror_entry(tmp_path, files=None):
    """建一个条目并按「条目标题 = 镜像目录名」在其下造 sources/materials 镜像。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="ALX 套件资料",
        type="开发板资料",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files=files or _sample_files(),
        kit_vocabulary=(),
    )
    mirror = tmp_path / "materials" / entry.title
    mirror.mkdir(parents=True, exist_ok=True)
    return root, entry, mirror


def test_entry_index_stats_counts_mirror_only_files(tmp_path):
    """索引素材口径（工单 reference-volume-dual-metric/01）：清单留痕、本体在
    sources/materials 镜像的二进制件由 entry_index_stats 单独算出——entry_stats
    的磁盘口径看不见它们，浏览层「体量」列靠这一路补全。"""
    root, entry, mirror = _mirror_entry(tmp_path)
    (mirror / "子目录").mkdir()
    (mirror / "手册.pdf").write_bytes(b"x" * 100)
    (mirror / "子目录" / "视频.mp4").write_bytes(b"y" * 250)
    (root / entry.id / "素材清单.txt").write_text(
        "素材目录（sources/materials）文件清单：\n\n"
        "手册.pdf  100 bytes\n子目录/视频.mp4  250 bytes\n",
        encoding="utf-8",
    )

    assert reference_library.entry_index_stats(root, entry.id) == (2, 350)
    # 磁盘口径不变（example.c + reference.json + 素材清单.txt），两侧互不重复
    count, _ = reference_library.entry_stats(root / entry.id)
    assert count == 3


def test_entry_index_stats_excludes_disk_backed_manifest_paths(tmp_path):
    """清单路径若已是条目目录里的实体文件，不计入索引口径——两侧相加 =
    可服务文件全集，不重复计数（文本副本与镜像摘要并存时的边界）。"""
    root, entry, mirror = _mirror_entry(tmp_path)
    (mirror / "手册.pdf").write_bytes(b"x" * 100)
    (mirror / "example.c").write_text(EXAMPLE_C, encoding="utf-8")
    (root / entry.id / "素材清单.txt").write_text(
        "素材目录（sources/materials）文件清单：\n\n"
        f"example.c  {len(EXAMPLE_C)} bytes\n手册.pdf  100 bytes\n",
        encoding="utf-8",
    )

    assert reference_library.entry_index_stats(root, entry.id) == (1, 100)


def test_entry_index_stats_no_double_count_when_mirror_and_disk_share_path(tmp_path):
    """同路径两侧都有（条目目录实体 + 镜像件）= 只算一次。

    「文本副本入库 + 完整副本走镜像」是本库的既定形态（C7 / ALX 套件条目）：
    解析优先命中条目目录，故该路径已是实体，索引口径必须排除，否则体量列
    会把同一个文件算两遍（file_count + index_count > 可服务文件数）。
    """
    root, entry, mirror = _mirror_entry(tmp_path)
    # 条目目录里新增一个文本副本，镜像里同名同路径也有（内容可不同——如实况）
    (root / entry.id / "使用说明.txt").write_text("要点", encoding="utf-8")
    (mirror / "使用说明.txt").write_text("要点与图示", encoding="utf-8")
    (mirror / "另外的手册.pdf").write_bytes(b"z" * 64)
    (root / entry.id / "素材清单.txt").write_text(
        "".join([
            "素材目录（sources/materials）文件清单：\n\n",
            "使用说明.txt  6 bytes\n",
            "另外的手册.pdf  64 bytes\n",
        ]),
        encoding="utf-8",
    )

    assert reference_library.entry_index_stats(root, entry.id) == (1, 64)
    # 不变式：素材实体（条目目录里属可服务集的那些，不含 reference.json /
    # 素材清单.txt 这类索引控制文件）+ 索引素材 = 可服务文件全集，不重不漏
    served = set(reference_library._entry_file_records(root, entry.id))
    disk_served = {rel for rel in served if (root / entry.id / rel).is_file()}
    index_count = reference_library.entry_index_stats(root, entry.id)[0]
    assert len(disk_served) + index_count == len(served) == 4
    assert "使用说明.txt" in disk_served        # 同路径以实体为准
    assert "另外的手册.pdf" not in disk_served  # 只有镜像件的那条走索引口径


def test_entry_index_stats_zero_for_pure_code_entry(tmp_path):
    """纯代码条目（无镜像件 / 无清单）= 索引口径 0，存量行为不变。"""
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="纯代码条目",
        type="例程代码",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2021F",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    assert reference_library.entry_index_stats(root, entry.id) == (0, 0)


def test_entry_index_stats_unknown_entry_raises(tmp_path):
    root = _reference_root(tmp_path)
    with pytest.raises(reference_library.ReferenceError):
        reference_library.entry_index_stats(root, "不存在的条目")


def test_references_api_reports_index_volume(tmp_path):
    """浏览端点带出索引口径：条目目录实况与索引素材分开给，前端相加即总量。"""
    root, entry, mirror = _mirror_entry(tmp_path)
    (mirror / "手册.pdf").write_bytes(b"x" * 100)
    (root / entry.id / "素材清单.txt").write_text(
        "素材目录（sources/materials）文件清单：\n\n手册.pdf  100 bytes\n",
        encoding="utf-8",
    )
    config_path = tmp_path / ".contest_generator" / "config.json"
    _write_config(config_path, _kit_library(tmp_path))
    # 端点读 reference_library_dir(module_library_dir) —— 让模块库的兄弟目录即本条目库
    client = TestClient(create_app(AppContext(config_path=config_path)))
    listed = {item["id"]: item for item in client.get("/api/references").json()}

    data = listed[entry.id]
    assert data["index_count"] == 1
    assert data["index_bytes"] == 100


def test_entry_stats_counts_whole_dir_including_unlisted_strays(tmp_path):
    """体量 = 磁盘实况（磁盘目录即数据库）：清单外的散文件也如实计入。

    删除 = 整目录移除，统计口径与删除影响面一致（比 files 字段诚实）。
    """
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="2026C 数字钥匙例程",
        type="例程工程",
        description="开门控制逻辑示例",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    stray = root / entry.id / "散文件.bin"
    stray.write_bytes(b"xyz")

    got = get_reference(root, entry.id)
    assert got.file_count == entry.file_count + 1
    assert got.size_bytes == entry.size_bytes + 3


def test_add_reference_kit_anchor_must_come_from_vocabulary(tmp_path):
    root = _reference_root(tmp_path)

    entry = add_reference(
        root,
        title="ALX 套件通信例程",
        type="例程工程",
        description="UWB 通信示例",
        anchor_kind=ANCHOR_KIND_KIT,
        anchor_value=KIT_ALX,
        files=_sample_files(),
        kit_vocabulary=(KIT_ALX, KIT_MSPM0),
    )
    assert entry.anchor_value == KIT_ALX

    with pytest.raises(ReferenceError, match="不在模块库已有 kit 词表"):
        add_reference(
            root,
            title="词表外套件",
            type="例程工程",
            description="x",
            anchor_kind=ANCHOR_KIND_KIT,
            anchor_value="某网店杂牌套件",
            files=_sample_files(),
            kit_vocabulary=(KIT_ALX, KIT_MSPM0),
        )


def test_add_reference_none_anchor_roundtrip(tmp_path):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="MSPM0 电机参考例程",
        type="参考例程",
        description="TI 官方 MSPM0 电机控制例程（不属任何已登记赛题 / 套件）",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files=_sample_files(),
        kit_vocabulary=(KIT_ALX,),
    )

    assert entry.anchor_kind == ANCHOR_KIND_NONE
    assert entry.anchor_value == ""
    meta = json.loads((root / entry.id / "reference.json").read_text(encoding="utf-8"))
    assert meta["anchor_kind"] == ANCHOR_KIND_NONE
    assert meta["anchor_value"] == ""
    assert get_reference(root, entry.id) == entry
    # 未锚定条目不参与按锚定过滤的搜索（锚定值空，子串必然不匹配）
    assert search_references(root, anchor="2026C") == []
    assert [e.id for e in search_references(root)] == [entry.id]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"anchor_kind": ANCHOR_KIND_TOPIC, "anchor_value": "26C"},
        {"anchor_kind": "series", "anchor_value": "2026C"},
        {"anchor_kind": ANCHOR_KIND_KIT, "anchor_value": ""},
        # 未锚定但塞了锚定值 = 元数据损坏，拒绝
        {"anchor_kind": ANCHOR_KIND_NONE, "anchor_value": "2026C"},
    ],
)
def test_add_reference_rejects_invalid_anchor(tmp_path, kwargs):
    with pytest.raises(ReferenceError):
        add_reference(
            _reference_root(tmp_path),
            title="坏锚定",
            type="例程工程",
            description="x",
            files=_sample_files(),
            kit_vocabulary=(KIT_ALX,),
            **kwargs,
        )


@pytest.mark.parametrize(
    "title,type_,description",
    [("", "例程工程", "x"), ("t", "", "x"), ("t", "例程工程", "  ")],
)
def test_add_reference_rejects_empty_fields(tmp_path, title, type_, description):
    with pytest.raises(ReferenceError, match="不能为空"):
        add_reference(
            _reference_root(tmp_path),
            title=title,
            type=type_,
            description=description,
            anchor_kind=ANCHOR_KIND_TOPIC,
            anchor_value="2026C",
            files=_sample_files(),
            kit_vocabulary=(),
        )


@pytest.mark.parametrize(
    "files",
    [
        {},
        {"../evil.c": "x"},  # 路径穿越
        {"a\\b.c": "x"},  # 反斜杠
        {"/abs.c": "x"},  # 绝对路径
        {"reference.json": "x"},  # 与元数据文件冲突
    ],
)
def test_add_reference_rejects_unsafe_files(tmp_path, files):
    with pytest.raises(ReferenceError):
        add_reference(
            _reference_root(tmp_path),
            title="t",
            type="例程工程",
            description="x",
            anchor_kind=ANCHOR_KIND_TOPIC,
            anchor_value="2026C",
            files=files,
            kit_vocabulary=(),
        )


def test_add_reference_transaction_leaves_nothing_on_write_failure(
    tmp_path, monkeypatch
):
    root = _reference_root(tmp_path)

    def boom(entry_dir: Path, data: Any, filename: str) -> None:
        raise OSError("磁盘写失败")

    # 事务中途失败点挂在共享原语 write_json 上（模块级替换只影响本模块引用）
    monkeypatch.setattr("contest_generator.reference_library.write_json", boom)
    with pytest.raises(OSError, match="磁盘写失败"):
        add_reference(
            root,
            title="写失败条目",
            type="例程工程",
            description="x",
            anchor_kind=ANCHOR_KIND_TOPIC,
            anchor_value="2026C",
            files=_sample_files(),
            kit_vocabulary=(),
        )
    # 入库中途失败不留半成品：条目目录不存在、元数据不存在
    assert list(root.iterdir()) == []


def test_add_reference_duplicate_title_gets_distinct_ids(tmp_path):
    root = _reference_root(tmp_path)
    first = add_reference(
        root,
        title="同名条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    second = add_reference(
        root,
        title="同名条目",
        type="例程工程",
        description="y",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )

    assert second.id == "同名条目-2"
    assert len(list_references(root)) == 2


# ---------------------------------------------------------------------------
# 浏览 / 搜索 / 删除
# ---------------------------------------------------------------------------


def test_list_references_missing_root_is_empty(tmp_path):
    assert list_references(_reference_root(tmp_path)) == []


def test_list_references_fails_loudly_on_broken_meta(tmp_path):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="正常条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    (root / entry.id / "reference.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(ReferenceError, match="不是合法 JSON"):
        list_references(root)


def test_get_reference_missing_and_unsafe_id(tmp_path):
    root = _reference_root(tmp_path)
    with pytest.raises(ReferenceError, match="不存在"):
        get_reference(root, "nope")
    with pytest.raises(ReferenceError, match="非法"):
        get_reference(root, "../escape")


def test_search_references_filters_by_title_type_anchor(tmp_path):
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="2026C 数字钥匙例程",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    add_reference(
        root,
        title="ALX 通信说明书",
        type="说明书",
        description="y",
        anchor_kind=ANCHOR_KIND_KIT,
        anchor_value=KIT_ALX,
        files=_sample_files(),
        kit_vocabulary=(KIT_ALX,),
    )

    assert len(search_references(root)) == 2
    assert [e.title for e in search_references(root, title="钥匙")] == [
        "2026C 数字钥匙例程"
    ]
    assert [e.title for e in search_references(root, type="说明")] == ["ALX 通信说明书"]
    assert [e.title for e in search_references(root, anchor="2026")] == [
        "2026C 数字钥匙例程"
    ]
    assert [e.title for e in search_references(root, title="例程", type="说明书")] == []
    assert [e.title for e in search_references(root, anchor=KIT_ALX)] == [
        "ALX 通信说明书"
    ]


def test_search_references_filters_by_filename(tmp_path):
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="塔克小车底盘资料",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files={
            "main.c": "/* 例程 */\n",
            "素材清单.txt": (
                "素材目录（Desktop/塔克）文件清单：\n"
                "\n"
                "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf  632107 bytes\n"
                "7 AT8236电机驱动资料/3.芯片手册/AT8236.pdf  1595164 bytes\n"
            ),
        },
        kit_vocabulary=(),
    )
    add_reference(
        root,
        title="无线串口模块资料",
        type="说明书",
        description="y",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"readme.md": "# 无线串口\n"},
        kit_vocabulary=(),
    )

    # 素材清单行命中（PDF 只留痕不入库，靠清单可搜）
    assert [e.title for e in search_references(root, filename="TB6612")] == [
        "塔克小车底盘资料"
    ]
    # 大小写不敏感（型号大小写混用也能命中）
    assert [e.title for e in search_references(root, filename="at8236")] == [
        "塔克小车底盘资料"
    ]
    # files 路径命中（文本文件双通道可搜）
    assert [e.title for e in search_references(root, filename="main.c")] == [
        "塔克小车底盘资料"
    ]
    assert [e.title for e in search_references(root, filename="readme")] == [
        "无线串口模块资料"
    ]
    # 不命中 / 与其他过滤可组合（AND：标题命中 + 文件名命中都要满足）
    assert search_references(root, filename="CAN") == []
    assert search_references(root, title="无线", filename="AT8236") == []
    assert search_references(root, title="塔克", filename="TB6612") != []
    # 空串 = 不过滤（向后兼容，行为与不带该参数一致）
    assert search_references(root) == search_references(root, filename="")
    assert search_references(root, title="无线") == search_references(
        root, title="无线", filename=""
    )
    # 命中文件直出：清单行优先、files 路径殿后，去重、大小写不敏感
    assert match_entry_files(root, "塔克小车底盘资料", "TB6612") == [
        "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf"
    ]
    assert match_entry_files(root, "塔克小车底盘资料", "at8236") == [
        "7 AT8236电机驱动资料/3.芯片手册/AT8236.pdf"
    ]
    assert match_entry_files(root, "塔克小车底盘资料", "main.c") == ["main.c"]
    # 空串 = 空；不命中 = 空；条目不存在抛 ReferenceError
    assert match_entry_files(root, "塔克小车底盘资料", "") == []
    assert match_entry_files(root, "塔克小车底盘资料", "CAN") == []
    try:
        match_entry_files(root, "不存在的条目", "x")
        raise AssertionError("应抛 ReferenceError")
    except Exception as exc:  # noqa: BLE001
        assert type(exc).__name__ == "ReferenceError"


def test_search_references_filename_missing_manifest_means_empty(tmp_path):
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="旧条目",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"notes.txt": "TB6612 参考\n"},  # 旧条目没有素材清单.txt
        kit_vocabulary=(),
    )
    # 无清单 = 按空处理：files 路径仍可搜，浏览不炸
    assert search_references(root, filename="TB6612") == []
    assert [e.title for e in search_references(root, filename="notes")] == ["旧条目"]


def test_search_references_filename_newline_needle_no_pseudo_hit(tmp_path):
    """含 \n 的 needle 不跨路径拼接命中（旧 join 串伪阳性回归）。"""
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="条目",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"a.txt": "x", "b.txt": "y"},
        kit_vocabulary=(),
    )
    # 逐路径判据：a.txt / b.txt 各自不包含 "a\nb"（跨路径拼接不再命中）
    assert search_references(root, filename="a\nb") == []
    assert [e.title for e in search_references(root, filename="a.txt")] == ["条目"]


def test_list_entry_files_parses_manifest_and_disk(tmp_path):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="塔克小车底盘资料",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files={
            "main.c": "/* 例程 */\n",
            "素材清单.txt": (
                "素材目录（Desktop/塔克）文件清单：\n"
                "\n"
                "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf  632107 bytes\n"
                "7 AT8236电机驱动资料/AT8236.pdf  100 bytes\n"
            ),
        },
        kit_vocabulary=(),
    )
    # 条目目录补一个实际文件：与清单同路径的"3.芯片手册"副本（同路径以磁盘
    # 实况为准）+ 清单之外的子目录散文件
    disk_dir = root / entry.id / "6 TB6612电机驱动资料" / "3.芯片手册"
    disk_dir.mkdir(parents=True)
    (disk_dir / "TB6612FNG Datasheet.pdf").write_bytes(b"pdf-bytes")
    extra = root / entry.id / "extra"
    extra.mkdir()
    (extra / "notes.c").write_text("/* 备注 */\n", encoding="utf-8")

    listing = list_entry_files(root, entry.id)
    by_path = {item["path"]: item["size_bytes"] for item in listing}

    # 素材清单记录（二进制只留痕，条目目录没有本体）+ 表头行跳过
    assert "7 AT8236电机驱动资料/AT8236.pdf" in by_path
    assert by_path["7 AT8236电机驱动资料/AT8236.pdf"] == 100
    # 同路径条目目录文件优先（真实 stat 覆盖清单记录值）
    assert "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf" in by_path
    assert (
        by_path["6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf"]
        == len(b"pdf-bytes")
    )
    # 条目目录实际文件（含子目录散文件，reference.json 排除；size = 真实 stat，
    # 与写盘内容字节数一致——Windows 文本模式会把 \n 转 \r\n，不能按原串 len 算）
    assert by_path["main.c"] == (root / entry.id / "main.c").stat().st_size
    assert by_path["extra/notes.c"] == (root / entry.id / "extra" / "notes.c").stat().st_size
    assert "reference.json" not in by_path
    assert listing == sorted(listing, key=lambda item: item["path"])


def test_list_entry_files_missing_manifest_falls_back_to_disk(tmp_path):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="旧条目",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"notes.txt": "/* 例程 */\n"},
        kit_vocabulary=(),
    )
    assert list_entry_files(root, entry.id) == [
        {"path": "notes.txt", "size_bytes": (root / entry.id / "notes.txt").stat().st_size}
    ]


def test_list_entry_files_missing_entry_raises(tmp_path):
    root = _reference_root(tmp_path)
    with pytest.raises(ReferenceError, match="不存在"):
        list_entry_files(root, "nope")


def test_build_material_manifest_lists_files_with_sizes(tmp_path):
    """行格式契约：表头 + 空行 + 每文件一行 "相对路径  大小 bytes"（目录跳过）。"""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("x" * 10, encoding="utf-8")
    (src / "子目录").mkdir()
    (src / "子目录" / "b.pdf").write_bytes(b"pdf")
    (src / "空目录").mkdir()
    lines = build_material_manifest(src).splitlines()
    assert lines[0] == "素材目录（sources/materials）文件清单："
    assert lines[1] == ""
    assert "a.txt  10 bytes" in lines
    assert "子目录/b.pdf  3 bytes" in lines
    # 目录（含空目录）不产生行
    assert len(lines) == 4


def test_build_material_manifest_stat_failure_marks_minus_one(tmp_path, monkeypatch):
    """stat 失败的文件记 size=-1（读端锚尾正则只吃数字，-1 行仅留痕不索引）。

    is_file 走 os.path.isfile（不经过 Path.stat），stat 只用于取大小——fake 对
    目标路径一律抛 OSError 即可，不影响 is_file 判定。

    **为什么写成这样**（2026-09-16 在 Windows CI 上连踩两次，都记在这）：
      · 第一版用 `if self == broken` ——路径相等比较在 runner 上误伤了**别的**路径，
        异常从用例体里冒出来（`OSError: 模拟 stat 失败`）；
      · 第二版加了 `target.exists()` ——`exists()` 内部就是调 `Path.stat`，
        被补丁拦到 → **无限递归** → pytest INTERNALERROR 把整场测试打断（`ci` 上实测）。
    所以现在：**只用 `resolve()` 做纯字符串比较**（`resolve` 不经过 `stat`），
    转发用补丁前捕获的真函数，另加一层递归护栏与命中计数——
    没命中 = 这条用例根本没验到东西（假绿），要红。
    """
    src = tmp_path / "src"
    src.mkdir()
    broken = src / "broken.bin"
    broken.write_bytes(b"data")
    target = str(broken.resolve())
    real_stat = Path.stat  # 补丁前捕获，保证转发的是真实现
    hits: list[str] = []
    calls = 0

    def fake_stat(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        # 递归护栏：补丁是全局的，任何路径兜底都直接转发，绝不无限递归
        if calls > 2000:
            return real_stat(self, *args, **kwargs)
        try:
            same = str(self.resolve()) == target
        except OSError:
            same = False
        if same:
            hits.append(str(self))
            raise OSError("模拟 stat 失败")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)
    manifest = build_material_manifest(src)
    assert hits, "补丁一次都没命中目标文件——这条用例等于没验（假绿）"
    assert calls < 2000, f"疑似无限递归（fake_stat 被调 {calls} 次）"
    assert "broken.bin  -1 bytes" in manifest.splitlines(), manifest
    # 反向判据：别的文件不受影响（fake 误伤正常路径会在这里露出来）
    (src / "ok.txt").write_text("12345", encoding="utf-8")
    assert "ok.txt  5 bytes" in build_material_manifest(src).splitlines(), "fake 误伤了正常文件"


def test_build_material_manifest_roundtrips_with_read_side(tmp_path):
    """写→读对偶：build 输出写入条目目录后，_read_manifest_records 解析一致。"""
    root = _reference_root(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("x" * 10, encoding="utf-8")
    (src / "子").mkdir()
    (src / "子" / "b.pdf").write_bytes(b"pdf")
    entry = add_reference(
        root,
        title="条目",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"素材清单.txt": build_material_manifest(src)},
        kit_vocabulary=(),
    )
    assert reference_library._read_manifest_records(root / entry.id) == [
        ("a.txt", 10),
        ("子/b.pdf", 3),
    ]


def test_resolve_entry_file_serves_entry_then_materials(tmp_path):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="塔克小车底盘资料",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files={"main.c": "/* 例程 */\n"},
        kit_vocabulary=(),
    )
    materials = tmp_path / "materials"
    pdf = (
        materials
        / entry.title
        / "6 TB6612电机驱动资料"
        / "3.芯片手册"
        / "TB6612FNG Datasheet.pdf"
    )
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 fake")

    # 条目目录命中：文本内联（media_type 留空按扩展名自动）
    path, media_type = resolve_entry_file(root, materials, entry.id, "main.c")
    assert path.read_text(encoding="utf-8") == "/* 例程 */\n"
    assert media_type is None
    # materials 镜像命中：PDF 带 application/pdf（浏览器预览）
    path, media_type = resolve_entry_file(
        root, materials, entry.id, "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf"
    )
    assert path == pdf
    assert media_type == "application/pdf"
    # materials 根不存在 / 都找不到 → ReferenceError（映射 400，与条目不存在
    # 同通道——resolve 不再返回 None，调用方无内联 404 分支）
    with pytest.raises(ReferenceError, match="中不存在文件"):
        resolve_entry_file(root, tmp_path / "no-such-materials", entry.id, "x.pdf")
    with pytest.raises(ReferenceError, match="中不存在文件"):
        resolve_entry_file(root, materials, entry.id, "nope.pdf")


@pytest.mark.parametrize("bad", ["../x", "..\\x", "/abs", "a//b", "c:/win", "a/../b"])
def test_resolve_entry_file_rejects_unsafe_paths(tmp_path, bad):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="条目",
        type="说明书",
        description="x",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"a.txt": "x"},
        kit_vocabulary=(),
    )
    with pytest.raises(ReferenceError, match="非法文件路径"):
        resolve_entry_file(root, tmp_path / "materials", entry.id, bad)


def test_delete_reference_removes_entry_and_rejects_missing(tmp_path):
    root = _reference_root(tmp_path)
    entry = add_reference(
        root,
        title="待删除条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )

    delete_reference(root, entry.id)

    assert list_references(root) == []
    with pytest.raises(ReferenceError, match="不存在"):
        delete_reference(root, entry.id)


# ---------------------------------------------------------------------------
# 归档动作（report 模型）
# ---------------------------------------------------------------------------


def test_archive_decision_roundtrip():
    decision = ArchiveDecision(path="ui/oled_fonts.c", topic="2026C", reason="旧字体表")

    assert ArchiveDecision.from_dict(decision.to_dict()) == decision


@pytest.mark.parametrize(
    "bad",
    [
        "not a dict",
        {"topic": "2026C"},  # 缺 path
        {"path": "", "topic": "2026C"},
        {"path": "a.c"},  # 缺 topic
        {"path": "a.c", "topic": "  "},
        {"path": "a.c", "topic": "2026C", "reason": 42},
    ],
)
def test_archive_decision_from_dict_rejects_malformed(bad):
    with pytest.raises(ReportError):
        ArchiveDecision.from_dict(bad)


def test_distillation_report_archive_section_roundtrip(tmp_path):
    report, _ = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=report.keep,
        merge=report.merge,
        exclude=report.exclude,
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(ArchiveDecision("ui/oled_fonts.c", topic="2026C", reason="旧字体表"),),
    )

    data = report.to_dict()
    assert data["archive"] == [
        {"path": "ui/oled_fonts.c", "topic": "2026C", "reason": "旧字体表"}
    ]
    rebuilt = DistillationReport.from_dict(
        data, main_c_preview=report.main_c_preview
    )
    assert rebuilt.archive == report.archive

    # 无归档动作的旧形状 payload 兼容（archive 缺省为空）
    legacy = {k: v for k, v in data.items() if k != "archive"}
    assert DistillationReport.from_dict(legacy, main_c_preview="x").archive == ()


# ---------------------------------------------------------------------------
# 归档落库（archive_reference：复制入库、内容自持）
# ---------------------------------------------------------------------------


def test_archive_reference_copies_file_and_anchors_topic(tmp_path):
    root = _reference_root(tmp_path)
    source = tmp_path / "proj" / "ui" / "oled_fonts.c"
    source.parent.mkdir(parents=True)
    source.write_text("/* 上届字体表 */\n", encoding="utf-8")

    entry = archive_reference(
        root,
        source=source,
        rel_path="ui/oled_fonts.c",
        title="ui/oled_fonts.c（proj）",
        description="上一场比赛的字体表",
        anchor_topic="2026C",
    )

    assert entry.type == ARCHIVE_ENTRY_TYPE
    assert entry.anchor_kind == ANCHOR_KIND_TOPIC
    assert entry.anchor_value == "2026C"
    stored = root / entry.id / "ui" / "oled_fonts.c"
    assert stored.read_text(encoding="utf-8") == "/* 上届字体表 */\n"
    # 内容自持：源文件删除不影响条目
    source.unlink()
    assert stored.is_file()
    # 体量同源补全（与录入 / 读盘同一统计）：源文件 + reference.json（落盘
    # 元数据是补全前的零值，读盘时被磁盘实况覆盖，序列化出去恒为实况）
    assert entry.file_count == 2
    assert entry.size_bytes == (
        (root / entry.id / "ui" / "oled_fonts.c").stat().st_size
        + (root / entry.id / "reference.json").stat().st_size
    )
    assert get_reference(root, entry.id) == entry


@pytest.mark.parametrize(
    "topic", ["", "26C", "2026年C"]
)
def test_archive_reference_rejects_bad_topic(tmp_path, topic):
    source = tmp_path / "a.c"
    source.write_text("x", encoding="utf-8")
    with pytest.raises(ReferenceError, match="格式非法"):
        archive_reference(
            _reference_root(tmp_path),
            source=source,
            rel_path="a.c",
            title="t",
            description="d",
            anchor_topic=topic,
        )


def test_archive_reference_transaction_leaves_nothing_on_copy_failure(tmp_path):
    root = _reference_root(tmp_path)

    with pytest.raises(OSError):
        archive_reference(
            root,
            source=tmp_path / "missing.c",  # 源不存在 → 复制失败
            rel_path="missing.c",
            title="缺失源文件",
            description="d",
            anchor_topic="2026C",
        )
    assert list(root.iterdir()) == []


def test_archive_reference_rejects_meta_filename_collision(tmp_path):
    """源工程里叫 reference.json 的文件不配归档：复制后会被元数据覆盖。"""
    source = tmp_path / "reference.json"
    source.write_text("{\"素材\": true}", encoding="utf-8")

    with pytest.raises(ReferenceError, match="冲突"):
        archive_reference(
            _reference_root(tmp_path),
            source=source,
            rel_path="reference.json",
            title="元数据撞名",
            description="d",
            anchor_topic="2026C",
        )
    assert not _reference_root(tmp_path).exists()


def test_reference_entry_from_dict_rejects_unknown_anchor_kind(tmp_path):
    """词表外锚定类型 = 元数据损坏：浏览时大声失败，不把坏数据带进列表。"""
    root = _reference_root(tmp_path)
    add_reference(
        root,
        title="正常条目",
        type="例程工程",
        description="x",
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value="2026C",
        files=_sample_files(),
        kit_vocabulary=(),
    )
    entry = get_reference(root, list_references(root)[0].id)
    entry_dir = root / entry.id
    data = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    data["anchor_kind"] = "series"
    (entry_dir / "reference.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ReferenceError, match="元数据不合法"):
        list_references(root)


# ---------------------------------------------------------------------------
# 确认事务里的归档动作（master.confirm_distillation）
# ---------------------------------------------------------------------------


class BudgetExhaustedReferenceLLM(ReferenceLLM):
    def __init__(self) -> None:
        super().__init__(archivable=["ui/oled_fonts.c"])

    def reference_summarize(self, material: str) -> str:
        from contest_generator.llm import LLMError
        raise LLMError("LLM 工作流累计尝试次数预算已耗尽")


def test_confirm_archive_budget_exhaustion_before_any_write(tmp_path, fake_masters_dir):
    """归档判定后逐文件简介耗尽预算：确认事务在母版/参考库写盘前失败。"""
    report, projects = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=report.keep,
        merge=report.merge,
        exclude=tuple(d for d in report.exclude if d.path != "ui/oled_fonts.c"),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(ArchiveDecision(path="ui/oled_fonts.c", topic="2026C"),),
    )

    from contest_generator.llm import LLMError
    with pytest.raises(LLMError, match="累计尝试次数预算已耗尽"):
        confirm_distillation(
            fake_masters_dir,
            projects,
            _confirm_payload(report, projects),
            llm_factory=BudgetExhaustedReferenceLLM,
            reference_library_dir=_reference_root(tmp_path),
        )

    assert list_masters(fake_masters_dir) == []
    assert not _reference_root(tmp_path).exists()


def test_confirm_archives_excluded_file_with_transaction(
    tmp_path, fake_masters_dir
):
    """归档动作随确认事务提交：母版不含归档文件、参考库条目复制入库锚定该题。"""
    report, projects = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=report.keep,
        merge=report.merge,
        exclude=tuple(d for d in report.exclude if d.path != "ui/oled_fonts.c"),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(
            ArchiveDecision(
                path="ui/oled_fonts.c", topic="2026C", reason="上一场比赛的字体表"
            ),
        ),
    )
    llm = ReferenceLLM(summary="旧项目字体表，可作参考", archivable=["ui/oled_fonts.c"])

    meta = confirm_distillation(
        fake_masters_dir,
        projects,
        _confirm_payload(report, projects),
        llm_factory=lambda: llm,
        reference_library_dir=_reference_root(tmp_path),
    )

    # 母版正常入库且不含归档文件
    stored = fake_masters_dir / PLATFORM_STM32
    assert not (stored / "ui" / "oled_fonts.c").exists()
    assert meta.platform == PLATFORM_STM32
    # 参考库条目：字节复制入库、锚定该题、简介 = AI 生成
    entries = list_references(_reference_root(tmp_path))
    assert len(entries) == 1
    entry = entries[0]
    assert entry.anchor_kind == ANCHOR_KIND_TOPIC
    assert entry.anchor_value == "2026C"
    assert entry.description == "旧项目字体表，可作参考"
    assert entry.type == ARCHIVE_ENTRY_TYPE
    archived = _reference_root(tmp_path) / entry.id / "ui" / "oled_fonts.c"
    assert archived.read_text(encoding="utf-8") == (
        projects[1] / "ui" / "oled_fonts.c"
    ).read_text(encoding="utf-8")
    # LLM 判定与简介都发生在写盘前：素材带剔除理由
    assert len(llm.judge_calls) == 1
    assert llm.judge_calls[0][0].reason == "上一场比赛的字体表"


def test_confirm_archive_allows_moving_kept_common_file(tmp_path, fake_masters_dir):
    """公共文件移到归档段 = 不进母版但入库参考：覆盖校验把归档段计入判定范围。"""
    report, projects = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=tuple(d for d in report.keep if d.path != "inc/stm32f10x_conf.h"),
        merge=report.merge,
        exclude=report.exclude,
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(ArchiveDecision(path="inc/stm32f10x_conf.h", topic="2026C"),),
    )
    llm = ReferenceLLM(archivable=["inc/stm32f10x_conf.h"])

    confirm_distillation(
        fake_masters_dir,
        projects,
        _confirm_payload(report, projects),
        llm_factory=lambda: llm,
        reference_library_dir=_reference_root(tmp_path),
    )

    stored = fake_masters_dir / PLATFORM_STM32
    assert not (stored / "inc" / "stm32f10x_conf.h").exists()
    assert len(list_references(_reference_root(tmp_path))) == 1


def test_confirm_archive_requires_ai_and_reference_dir(tmp_path, fake_masters_dir):
    report, projects = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=report.keep,
        merge=report.merge,
        exclude=tuple(d for d in report.exclude if d.path != "ui/oled_fonts.c"),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(ArchiveDecision(path="ui/oled_fonts.c", topic="2026C"),),
    )

    with pytest.raises(MasterError, match="归档动作需要 AI 服务与参考文件库"):
        confirm_distillation(
            fake_masters_dir,
            projects,
            _confirm_payload(report, projects),
        )
    assert list_masters(fake_masters_dir) == []
    assert not _reference_root(tmp_path).exists()


def test_confirm_archive_rejects_bad_topic_before_any_write(tmp_path, fake_masters_dir):
    report, projects = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=report.keep,
        merge=report.merge,
        exclude=tuple(d for d in report.exclude if d.path != "ui/oled_fonts.c"),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(ArchiveDecision(path="ui/oled_fonts.c", topic="26C"),),
    )

    with pytest.raises(MasterError, match="格式非法"):
        confirm_distillation(
            fake_masters_dir,
            projects,
            _confirm_payload(report, projects),
            llm_factory=lambda: ReferenceLLM(archivable=["ui/oled_fonts.c"]),
            reference_library_dir=_reference_root(tmp_path),
        )
    # 母版库与参考库都不被触碰
    assert list_masters(fake_masters_dir) == []
    assert not _reference_root(tmp_path).exists()


def test_confirm_archive_rejects_ai_unarchivable_before_any_write(
    tmp_path, fake_masters_dir
):
    report, projects = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=report.keep,
        merge=report.merge,
        exclude=tuple(d for d in report.exclude if d.path != "ui/oled_fonts.c"),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(ArchiveDecision(path="ui/oled_fonts.c", topic="2026C"),),
    )

    with pytest.raises(MasterError, match="未被 AI 判定为值得归档"):
        confirm_distillation(
            fake_masters_dir,
            projects,
            _confirm_payload(report, projects),
            llm_factory=lambda: ReferenceLLM(archivable=()),
            reference_library_dir=_reference_root(tmp_path),
        )
    assert list_masters(fake_masters_dir) == []
    assert not _reference_root(tmp_path).exists()


def test_confirm_archive_rejects_residue_and_main_c(tmp_path, fake_masters_dir):
    """构建残留 / 旧 main.c 由规则确定性处置：不配归档（与 剔除 同款强制）。"""
    report, projects = _distilled_report(tmp_path)
    for residue in ("src/oled.o", "main.c"):
        bad = DistillationReport(
            platform=report.platform,
            projects=report.projects,
            keep=report.keep,
            merge=report.merge,
            # 用户把残留 / 旧 main.c 从剔除段移到归档段（构建残留 / 模板替代
            # 文件不配归档）——规则处置校验必须拒绝；其余条目原样
            exclude=tuple(d for d in report.exclude if d.path != residue),
            main_c_preview=report.main_c_preview,
            uvprojx_preview=report.uvprojx_preview,
            archive=(ArchiveDecision(path=residue, topic="2026C"),),
        )
        with pytest.raises(MasterError, match="必须剔除"):
            confirm_distillation(
                fake_masters_dir,
                projects,
                _confirm_payload(bad, projects),
                llm_factory=lambda: ReferenceLLM(archivable=[residue]),
                reference_library_dir=_reference_root(tmp_path),
            )
        assert list_masters(fake_masters_dir) == []
        assert not _reference_root(tmp_path).exists()


def test_confirm_archive_rolls_back_entries_on_write_failure(
    tmp_path, fake_masters_dir, monkeypatch
):
    """归档批写入中途失败：已建条目全部回滚，不留半成品；母版已入库（可重试）。"""
    report, projects = _distilled_report(tmp_path)
    # 两个归档条目（一个原是剔除、一个原是保留移入归档）：第一个写成功后第二个失败
    archived_paths = ["ui/oled_fonts.c", "sensors/dht11.c"]
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=tuple(d for d in report.keep if d.path not in archived_paths),
        merge=report.merge,
        exclude=tuple(d for d in report.exclude if d.path != "ui/oled_fonts.c"),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=tuple(
            ArchiveDecision(path=p, topic="2026C") for p in archived_paths
        ),
    )
    llm = ReferenceLLM(archivable=archived_paths)
    # 只打参考库的元数据写入（shutil 是全局单例，打 copy2 会误伤 apply /
    # import 的复制）：第二个归档条目元数据写失败 → 条目 2 自清、条目 1 回滚
    # （失败点挂在共享原语 write_json 上，模块级替换只影响本模块引用）
    real_write_json = reference_library.write_json
    calls = {"n": 0}

    def flaky_write_json(entry_dir: Path, filename: str, data: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("磁盘写失败")
        return real_write_json(entry_dir, filename, data)

    monkeypatch.setattr(
        "contest_generator.reference_library.write_json", flaky_write_json
    )
    with pytest.raises(MasterError, match="归档写入失败"):
        confirm_distillation(
            fake_masters_dir,
            projects,
            _confirm_payload(report, projects),
            llm_factory=lambda: llm,
            reference_library_dir=_reference_root(tmp_path),
        )
    # 批回滚：参考库空、母版已入库（归档失败不拖母版，重试确认可恢复）
    assert list_references(_reference_root(tmp_path)) == []
    assert (fake_masters_dir / PLATFORM_STM32).is_dir()


# ---------------------------------------------------------------------------
# webapp 路由（/api/references + 确认透传）
# ---------------------------------------------------------------------------


def test_references_routes_end_to_end(tmp_path):
    client = _app(tmp_path, ReferenceLLM(summary="AI 草稿"))

    assert client.get("/api/references").json() == []

    draft = client.post(
        "/api/references/draft",
        json={"files": {"example.c": "/* 例程 */\n"}},
    )
    assert draft.status_code == 200
    assert draft.json() == {"draft": "AI 草稿"}

    added = client.post(
        "/api/references",
        json={
            "title": "2026C 数字钥匙例程",
            "type": "例程工程",
            "description": "开门控制逻辑示例",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2026C",
            "files": {"example.c": "/* 例程 */\n"},
        },
    )
    assert added.status_code == 200
    entry_id = added.json()["id"]
    assert added.json()["anchor_value"] == "2026C"
    assert added.json()["mtime"] > 0   # ux-polish-02/07：响应带 mtime（排序用）

    listed = client.get("/api/references")
    assert [e["title"] for e in listed.json()] == ["2026C 数字钥匙例程"]
    assert listed.json()[0]["mtime"] == added.json()["mtime"]
    assert [e["title"] for e in client.get("/api/references?title=钥匙").json()] == [
        "2026C 数字钥匙例程"
    ]
    assert client.get("/api/references?title=不存在").json() == []

    assert client.delete(f"/api/references/{entry_id}").json() == {"ok": True}
    assert client.get("/api/references").json() == []


def test_references_add_rejects_out_of_vocabulary_kit(tmp_path):
    client = _app(tmp_path, ReferenceLLM())
    response = client.post(
        "/api/references",
        json={
            "title": "杂牌套件说明书",
            "type": "说明书",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_KIT,
            "anchor_value": "某网店杂牌套件",
            "files": {"a.txt": "x"},
        },
    )

    assert response.status_code == 400
    assert "不在模块库已有 kit 词表" in response.json()["detail"]


def test_references_bad_payloads_are_400(tmp_path):
    client = _app(tmp_path, ReferenceLLM())

    assert client.post("/api/references/draft", json={}).status_code == 400
    assert (
        client.post(
            "/api/references",
            json={"title": "t", "type": "例程工程", "description": "x"},
        ).status_code
        == 400
    )
    # 路径穿越在路由层就被拒绝（Starlette 路径归一化）；合法格式的不存在 id → 400
    assert client.delete("/api/references/../escape").status_code == 404
    assert client.delete("/api/references/missing").status_code == 400


def test_references_add_platform_contract(tmp_path):
    """录入表单契约（工单 01 平台属性）：POST 带 platform 入库、GET 响应带
    platform；缺省 = any；词表外值 400 大声失败。"""
    client = _app(tmp_path, ReferenceLLM())
    added = client.post(
        "/api/references",
        json={
            "title": "巡线模板",
            "type": "参考例程",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2024H",
            "platform": "mspm0",
            "files": {"xunji.c": "/* 巡线 */\n"},
        },
    )
    assert added.status_code == 200
    assert added.json()["platform"] == "mspm0"

    listed = client.get("/api/references").json()
    assert [e["platform"] for e in listed] == ["mspm0"]

    # 缺省 / 空 → any（向后兼容，旧录入流程不带 platform 字段）
    legacy = client.post(
        "/api/references",
        json={
            "title": "旧式录入",
            "type": "说明书",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2024H",
            "files": {"a.txt": "x"},
        },
    )
    assert legacy.status_code == 200
    assert legacy.json()["platform"] == "any"

    # 词表外平台值 → 400（大声失败，不留半成品）
    bad = client.post(
        "/api/references",
        json={
            "title": "非法平台",
            "type": "说明书",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2024H",
            "platform": "esp32",
            "files": {"a.txt": "x"},
        },
    )
    assert bad.status_code == 400
    assert "非法平台属性" in bad.json()["detail"]
    assert [e["title"] for e in client.get("/api/references").json()] == [
        "巡线模板",
        "旧式录入",
    ]


def test_references_add_topic_type_contract(tmp_path):
    """录入表单契约（工单 topic-framework/01）：POST 带 topic_type 入库、GET
    响应带 topic_type；缺省 = ""；词表外值 400 大声失败。"""
    client = _app(tmp_path, ReferenceLLM())
    added = client.post(
        "/api/references",
        json={
            "title": "巡线决策例程",
            "type": "例程代码",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2021F",
            "topic_type": "line_follow",
            "files": {"xunji.c": "/* 巡线 */\n"},
        },
    )
    assert added.status_code == 200
    assert added.json()["topic_type"] == "line_follow"

    listed = client.get("/api/references").json()
    assert [e["topic_type"] for e in listed] == ["line_follow"]

    # 缺省 = 未标记（向后兼容）
    legacy = client.post(
        "/api/references",
        json={
            "title": "无题型资料",
            "type": "说明书",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_NONE,
            "anchor_value": "",
            "files": {"a.txt": "x"},
        },
    )
    assert legacy.status_code == 200
    assert legacy.json()["topic_type"] == ""

    # 词表外值 400
    bad = client.post(
        "/api/references",
        json={
            "title": "神秘题型资料",
            "type": "说明书",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_NONE,
            "anchor_value": "",
            "topic_type": "mystery_type",
            "files": {"a.txt": "x"},
        },
    )
    assert bad.status_code == 400
    assert "非法题型" in bad.json()["detail"]


def test_references_update_topic_type_contract(tmp_path):
    """编辑表单契约（工单 topic-framework/01）：PUT 带 topic_type 落盘回读；
    PUT 不带 = 清空（全量替换语义，与 platform 同款）。"""
    client = _app(tmp_path, ReferenceLLM())
    added = client.post(
        "/api/references",
        json={
            "title": "巡线决策例程",
            "type": "例程代码",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2021F",
            "files": {"xunji.c": "/* 巡线 */\n"},
        },
    ).json()
    # PUT 全量必填：不带 topic_type = 替换为 ""（旧前端兼容）
    resp = client.put(
        f"/api/references/{added['id']}",
        json={
            "title": "巡线决策例程",
            "type": "例程代码",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2021F",
            "platform": "stm32",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["topic_type"] == ""

    # 带 topic_type = 落盘
    resp2 = client.put(
        f"/api/references/{added['id']}",
        json={
            "title": "巡线决策例程",
            "type": "例程代码",
            "description": "x",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2021F",
            "platform": "stm32",
            "topic_type": "line_follow",
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["topic_type"] == "line_follow"
    assert client.get("/api/references").json()[0]["topic_type"] == "line_follow"


def test_references_topic_types_endpoint(tmp_path):
    """题型词表端点（工单 topic-framework/04）：GET /api/references/topic-types。"""
    client = _app(tmp_path, ReferenceLLM())
    resp = client.get("/api/references/topic-types")

    assert resp.status_code == 200
    assert set(resp.json()) == {"line_follow", "generic"}


def test_confirm_route_passes_archive_wiring(tmp_path, fake_masters_dir):
    """确认端点（归档动作）经 HTTP 全链路：报告含归档 → 参考库条目入库。"""
    report, projects = _distilled_report(tmp_path)
    report = DistillationReport(
        platform=report.platform,
        projects=report.projects,
        keep=report.keep,
        merge=report.merge,
        exclude=tuple(d for d in report.exclude if d.path != "ui/oled_fonts.c"),
        main_c_preview=report.main_c_preview,
        uvprojx_preview=report.uvprojx_preview,
        archive=(ArchiveDecision(path="ui/oled_fonts.c", topic="2026C"),),
    )
    config_path = tmp_path / ".contest_generator" / "config.json"
    _write_config(config_path, _kit_library(tmp_path))
    llm = ReferenceLLM(summary="归档简介", archivable=["ui/oled_fonts.c"])
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="test-key",
            module_library_dir=config_path.parent / "module_library",
            masters_dir=fake_masters_dir,
        ),
        llm_factory=lambda cfg: llm,  # type: ignore[arg-type]
    )
    client = TestClient(create_app(ctx))

    response = client.post("/api/masters/confirm", json=_confirm_payload(report, projects))

    assert response.status_code == 200
    entries = list_references(config_path.parent / "references")
    assert len(entries) == 1
    assert entries[0].anchor_value == "2026C"
    assert entries[0].description == "归档简介"




# ---------------------------------------------------------------------------
# 全文回读（两级注入第二级）：read_fulltext 归 store（selection 用例随迁，
# 断言原样——拼装字节逐字不变）；工单 03 起逐文件截断（超长文件截头带标注，
# 短文件仍逐字原样）
# ---------------------------------------------------------------------------


def test_read_fulltext_assembles_files_with_headers(tmp_path):
    """两级注入第二级的素材形状：带文件名标注的拼接文本。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entry = get_reference(reference_root, TOPIC_REFERENCE_ID)

    text = read_fulltext(reference_root, entry)

    assert "// ---- key_example.c ----" in text
    assert "/* 数字钥匙例程 */" in text


def test_read_fulltext_skips_binary_files_with_note(tmp_path):
    """二进制素材（说明书 PDF 等）读不了文本：跳过并标注，不让生成流程整体失败。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entry_dir = reference_root / KIT_REFERENCE_ID
    meta = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    meta["files"] = ["manual.txt", "manual.pdf"]
    (entry_dir / "manual.pdf").write_bytes(b"%PDF\x00\x01\x02binary")
    (entry_dir / "reference.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    text = read_fulltext(
        reference_root, get_reference(reference_root, KIT_REFERENCE_ID)
    )

    assert "套件接线与使用说明全文" in text
    assert "manual.pdf" in text  # 二进制素材带标注而非静默消失


def test_read_fulltext_truncates_oversized_files_independently(tmp_path):
    """逐文件截断（工单 03）：每个超长文件独立限长、截头带标注——配额不再被
    首个大文件（素材清单）吃光，每个文件的开头都进上下文（旧契约整体截 4000
    字符，尾部文件一个字符都进不了模型）；短文件完整、二进制跳过不受影响。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entry_dir = reference_root / TOPIC_REFERENCE_ID
    meta = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    meta["files"] = ["big_a.c", "big_b.h", "big_c.txt", "small.c", "manual.pdf"]

    def big(tag: str) -> str:
        return (
            f"/* {tag}_head */\n"
            + "x" * (REFERENCE_FILE_CAP + 3000)
            + f"\n/* {tag}_tail */\n"
        )

    (entry_dir / "big_a.c").write_text(big("A"), encoding="utf-8")
    (entry_dir / "big_b.h").write_text(big("B"), encoding="utf-8")
    (entry_dir / "big_c.txt").write_text(big("C"), encoding="utf-8")
    (entry_dir / "small.c").write_text(
        "/* 小文件头部 */\nint small_ok;\n/* 小文件尾部 */\n", encoding="utf-8"
    )
    (entry_dir / "manual.pdf").write_bytes(b"%PDF\x00\x01binary")
    (entry_dir / "reference.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    text = read_fulltext(
        reference_root, get_reference(reference_root, TOPIC_REFERENCE_ID)
    )

    assert text.count("内容过长，已截断") == 3  # 3 个超长文件各带一条截断标注
    for tag in ("A", "B", "C"):
        assert f"/* {tag}_head */" in text  # 每个文件的开头都在
        assert f"/* {tag}_tail */" not in text  # 截头：超出上限的尾部被剪掉
    assert len(text) > 4000  # 逐文件截断总长放宽：旧 4000 总预算必被突破
    assert "小文件尾部" in text  # 未超长文件完整保留
    assert "manual.pdf" in text  # 二进制跳过标注不受影响
    assert "按所见内容判断" in text  # 截断标注措辞（TRUNCATION_NOTICE 单源）


def test_read_fulltext_truncation_marker_matches_shared_origin(tmp_path):
    """截断文案单源：read_fulltext 的逐文件截断逐字等于 library.truncate_content
    对同一文件同一上限的输出（reference_library 不能 import llm，措辞共享层）。"""
    from contest_generator.library import truncate_content

    reference_root = make_fake_reference_library(tmp_path / "references")
    entry_dir = reference_root / TOPIC_REFERENCE_ID
    meta = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    content = "/* 头 */\n" + "y" * (REFERENCE_FILE_CAP + 500)
    meta["files"] = ["big.c"]
    (entry_dir / "big.c").write_text(content, encoding="utf-8")
    (entry_dir / "reference.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    text = read_fulltext(
        reference_root, get_reference(reference_root, TOPIC_REFERENCE_ID)
    )

    expected = "// ---- big.c ----\n" + truncate_content(content, REFERENCE_FILE_CAP)
    assert text == expected


def test_read_fulltext_missing_file_raises(tmp_path):
    """条目素材文件缺失 = 库损坏：大声失败（宁可大声失败也不带病进上下文）。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    (reference_root / TOPIC_REFERENCE_ID / "key_example.c").unlink()

    with pytest.raises(ReferenceError, match="无法读取"):
        read_fulltext(
            reference_root, get_reference(reference_root, TOPIC_REFERENCE_ID)
        )


def test_read_fulltext_rejects_unsafe_path(tmp_path):
    """坏条目（files 含 .. 越界路径）借条目 id 逃出库目录：入口拦截大声失败。"""
    reference_root = make_fake_reference_library(tmp_path / "references")
    entry_dir = reference_root / TOPIC_REFERENCE_ID
    meta = json.loads((entry_dir / "reference.json").read_text(encoding="utf-8"))
    meta["files"] = ["../evil.c"]
    (entry_dir / "reference.json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(ReferenceError, match="路径非法"):
        read_fulltext(
            reference_root, get_reference(reference_root, TOPIC_REFERENCE_ID)
        )


# ---------------------------------------------------------------------------
# 结构测试（防回退，先例 errors.py / 04 工单）：全文读取归 store 的边界 pin
# ---------------------------------------------------------------------------


def test_selection_no_read_reference_fulltext():
    """全文回读归 reference_library 后，selection 不再自持读取（防回退）。"""
    import contest_generator.selection as selection

    assert not hasattr(selection, "read_reference_fulltext")


def test_file_label_marker_single_origin():
    """标签格式单源：src 内 "// ---- " 字面量唯一出处 = library.py（file_label 定义处）。"""
    src_root = Path(reference_library.__file__).parent
    hits = [
        (path.name, line_no)
        for path in sorted(src_root.glob("*.py"))
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "// ---- " in line
    ]
    assert [name for name, _ in hits] == ["library.py"]  # file_label 的定义文件（唯一出处）


def test_reference_library_consumes_file_label():
    """消费 pin：reference_library 从 library 引入 file_label（标签单源消费方）。"""
    import contest_generator.library as library

    assert hasattr(library, "file_label")
    assert reference_library.file_label is library.file_label


# ---------------------------------------------------------------------------
# 真库数据不变量：塔克 塔克R3 条目必须不存在（工单 tark-removal/04）
# ---------------------------------------------------------------------------
# 背景：塔克（烟台塔克电子科技）版权声明要求「未经书面许可不得复制、修改、
# 传播、捆绑使用」——本工具与塔克无授权关系，故 6 条塔克R3 参考条目已全部
# 下架（工单 tark-removal/01），sources/materials 塔克目录已删（02）。
# 本段防回潮：任何塔克条目被重新录入 / 从 git 历史恢复即红。
# （原「拆分 6 条必须存在」不变量已随下架删除，历史见工单 reference-library-hygiene/01。）

REFERENCES_ROOT = Path(__file__).resolve().parents[1] / "library" / "references"

# 塔克相关标识（id 前缀 / 条目标题 / 文件名命中词；标题沿用拆分时入库存的 title）
TARKBOT_MARKERS = ("塔克", "TARKBOT", "xtark", "DB20", "塔克创新")


def test_tarkbot_entries_absent_from_reference_library():
    """参考库不得存在任何塔克相关条目（防回潮：重新入库即红）。

    tark-removal/04：塔克版权声明要求书面许可——本工具无授权，任何塔克
    条目的存在都构成「复制 + 传播 + 生成链注入」风险。list_references 全库
    解析仍应通过（坏元数据大声失败的既有行为不变）。
    """
    entries = list_references(REFERENCES_ROOT)
    hits = [
        entry.id
        for entry in entries
        if any(marker in entry.id or marker in entry.title for marker in TARKBOT_MARKERS)
    ]
    assert not hits, f"参考库不应存在塔克相关条目（版权合规下架后回潮）：{hits}"


def test_tarkbot_entries_absent_from_web_facing_search():
    """搜索接口也拦截：按塔克词搜索应零命中（防止借搜索路径间接复活）。"""
    for needle in ("塔克", "TARKBOT", "DB20"):
        hits = search_references(REFERENCES_ROOT, title=needle)
        assert hits == [], f"搜索「{needle}」应零命中（塔克已下架）：{[h.id for h in hits]}"


# ---------------------------------------------------------------------------
# 真库数据不变量：MSPM0_MOTOR 条目修复（工单 reference-library-hygiene/02）
# ---------------------------------------------------------------------------

MOTOR_OLD_ID = "MSPM0_MOTOR参考例程"
MOTOR_MATERIALS_ROOT = Path(__file__).resolve().parents[1] / "sources" / "materials" / MOTOR_OLD_ID

# 资料库目录（sources/materials，688 MB）**不进 git**（Release 分发，见 README），
# 所以 clone / CI 上没有它。凡是要拿它当夹具的用例先过这道门（与
# tests/test_full_pack.py::test_repo_materials_paths_fit_budget 同一写法）——
# 2026-09-16 CI 抓出来的：这条之前只在有资料库的本机上绿过。
needs_materials_fixture = pytest.mark.skipif(
    not MOTOR_MATERIALS_ROOT.is_dir(),
    reason="本地无资料库目录（git clone / CI）——该夹具随 Release 分发，不在仓库里",
)

# 新标题 → (type, 期望文件数)。旧条目 1630 文件修复为 13 + 6 + 1 = 20 文件
# （修复脚本 .scratch/fix_mspm0_motor.py 的前置自检同源对照，本表为防回退 pin）
MOTOR_SPLITS = {
    "MSPM0 Motor_Ctrl 电机控制例程": ("参考例程", 13),
    "MSPM0 m0imu 姿态例程": ("参考例程", 6),
    "MSPM0 MOTOR 例程移植笔记": ("移植笔记", 1),
}

# 条目 → 共享工程底板文件（两条例程都自持，移植笔记纯文本不带）
MOTOR_SHARED_FILES = ("ti_msp_dl_config.c", "ti_msp_dl_config.h", "empty.syscfg")

# 剥负载前缀 + 顶层垃圾文件（旧条目有、新条目一律不得出现；镜像 + git 历史留痕）
MOTOR_STRIPPED_PREFIXES = ("source/", "gcc/", "iar/", "keil/", "ticlang/")
MOTOR_STRIPPED_TOP_LEVEL = ("Event.dot", "README.html")

# 7 个 GBK 转码补录文件：新条目内相对路径 → 转码后必现的中文/标识正文
# （原 GBK 直读失败即漏录，转码后 UTF-8 全文回读必须可见这些正文）
MOTOR_TRANSCODED_MARKERS = {
    "MSPM0 Motor_Ctrl 电机控制例程": {
        "motor_crc.c": "auchCRCHi",
        "motor_crc.h": "用于计算 CRC",
        "motor_read_enc.c": "存储累计编码器值",
        "motor_set_speed.c": "从站地址",
        "motor_set_speed.h": "设置电机速度",
        "user.h": "微库",
    },
    "MSPM0 m0imu 姿态例程": {
        "imu.c": "Gyro_ParseFrame",
    },
}


def _motor_split_entries() -> dict[str, reference_library.ReferenceEntry]:
    """真库 3 条修复条目的 {标题: 条目}；缺失 = 修复未执行 / 被回退，直接红。"""
    by_title = {entry.title: entry for entry in list_references(REFERENCES_ROOT)}
    missing = [title for title in MOTOR_SPLITS if title not in by_title]
    assert not missing, f"MSPM0_MOTOR 修复条目缺失：{missing}"
    return {title: by_title[title] for title in MOTOR_SPLITS}


def test_motor_entries_present_and_old_absent():
    """修复后 3 条新条目存在、旧条目不存在；list_references 全库结构校验不抛。"""
    by_title = {entry.title: entry for entry in list_references(REFERENCES_ROOT)}
    assert MOTOR_OLD_ID not in by_title
    for title in MOTOR_SPLITS:
        assert title in by_title


def test_motor_entries_shape_and_stripped_load():
    """3 条新条目文件集 / 类型 / 平台 / 锚定对齐，且不含任何剥负载路径。"""
    entries = _motor_split_entries()
    for title, (type_, expect_count) in MOTOR_SPLITS.items():
        entry = entries[title]
        assert entry.type == type_
        assert entry.platform == PLATFORM_MSPM0
        assert entry.anchor_kind == ANCHOR_KIND_NONE
        assert len(entry.files) == expect_count
        # 剥负载：source/ SDK 副本树、gcc/iar/keil/ticlang 胶水、构建产物垃圾
        # 一律不得出现在任何新条目 files 里（镜像 + git 历史留痕，不丢数据）
        for rel in entry.files:
            assert not rel.startswith(MOTOR_STRIPPED_PREFIXES)
            assert rel not in MOTOR_STRIPPED_TOP_LEVEL
    motor, imu, notes = (entries[t] for t in MOTOR_SPLITS)
    assert set(motor.files) == {
        "motor_crc.c",
        "motor_crc.h",
        "motor_read_enc.c",
        "motor_read_enc.h",
        "motor_set_speed.c",
        "motor_set_speed.h",
        "user.c",
        "user.h",
        "ti_msp_dl_config.c",
        "ti_msp_dl_config.h",
        "empty.syscfg",
        "README.md",
        "素材清单.txt",
    }
    assert set(imu.files) == {
        "imu.c",
        "imu.h",
        "ti_msp_dl_config.c",
        "ti_msp_dl_config.h",
        "empty.syscfg",
        "素材清单.txt",
    }
    assert notes.files == ("移植.md",)  # 移植笔记纯文本自持，不带素材清单


def test_motor_transcoded_files_readable_utf8():
    """7 个 GBK 转码补录文件 UTF-8 全文可读且中文注释正文可见。

    转码动机：motor_crc.{c,h} / motor_read_enc.c / motor_set_speed.{c,h} /
    user.h / imu.c 原为 GBK 编码，UTF-8 直读静默跳过导致"电机控制参考例程"
    条目里没有电机控制实现代码。转码后 read_text(utf-8) 必须直接成功且正文
    标记在（若哪天被换回 GBK 或内容清空，本测试即红）。
    """
    entries = _motor_split_entries()
    for title, markers in MOTOR_TRANSCODED_MARKERS.items():
        entry = entries[title]
        for rel, marker in markers.items():
            assert rel in entry.files
            content = (REFERENCES_ROOT / entry.id / rel).read_text(encoding="utf-8")
            assert marker in content, f"{entry.id}/{rel} 全文回读不见 {marker!r}"


@needs_materials_fixture
def test_motor_manifests_match_mirror_subdirs():
    """素材清单.txt 用 build_material_manifest 对镜像子目录重新生成（写读契约 pin）。

    电机条目清单 = sources/materials 镜像 MSP_Motor_Ctrl 子目录全文件留痕、
    m0imu 条目清单 = m0imu 子目录留痕（镜像 git 追踪，重生成结果与库内清单
    逐字节一致 = 剥离负载在镜像留痕、清单不丢数据）。
    """
    entries = _motor_split_entries()
    for title, subdir in (
        ("MSPM0 Motor_Ctrl 电机控制例程", "MSP_Motor_Ctrl"),
        ("MSPM0 m0imu 姿态例程", "m0imu"),
    ):
        entry = entries[title]
        manifest = (REFERENCES_ROOT / entry.id / "素材清单.txt").read_text(encoding="utf-8")
        assert manifest == build_material_manifest(MOTOR_MATERIALS_ROOT / subdir)


def test_motor_fulltext_shows_code_bodies():
    """全文回读电机例程：motor_set_speed.c / motor_read_enc.c 正文可见。

    修复动机之一：旧条目素材清单.txt 129575 字符排 files 首位，全文回读
    4000 字符截断下模型一个代码字符都看不到。修复后 read_fulltext 必须
    带着电机控制实现代码（帧下发 + 编码器解析函数正文）。
    """
    entries = _motor_split_entries()
    fulltext = read_fulltext(REFERENCES_ROOT, entries["MSPM0 Motor_Ctrl 电机控制例程"])
    assert "Motor_Set_ClosedLoop" in fulltext
    assert "Motor_Set_Speeds" in fulltext
    assert "Modbus_ParseFrame" in fulltext
    assert "从站地址" in fulltext
    assert "存储累计编码器值" in fulltext


# ---------------------------------------------------------------------------
# 条目编辑（工单 reference-library-ui/01）：update_reference 元数据全量 +
# 文件增量，一次事务（校验全在落盘前，失败磁盘零变化）
# ---------------------------------------------------------------------------


def _edit_sample_entry(tmp_path) -> reference_library.ReferenceEntry:
    """建一条可编辑的样例题（锚定 none、单文件 example.c）。"""
    return add_reference(
        _reference_root(tmp_path),
        title="待编辑条目",
        type="例程工程",
        description="原始简介",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"example.c": EXAMPLE_C},
        kit_vocabulary=(KIT_ALX,),
    )


def test_update_reference_metadata_roundtrip(tmp_path):
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)

    updated = update_reference(
        root,
        entry.id,
        title="改过的标题",
        type="说明书",
        description="改过的简介",
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        add_files={},
        remove_files=(),
        kit_vocabulary=(),
    )

    # 标题 / 类型 / 简介 / 平台写回元数据；id 与目录名不动（编辑不重命名）
    assert updated.id == entry.id
    assert (root / entry.id).is_dir()
    assert updated.title == "改过的标题"
    assert updated.type == "说明书"
    assert updated.description == "改过的简介"
    # 文件不变：磁盘文件还在、files 清单原样
    assert updated.files == entry.files
    assert (root / entry.id / "example.c").read_text(encoding="utf-8") == EXAMPLE_C
    # 读盘回读一致
    assert get_reference(root, entry.id) == updated


def test_update_reference_platform_roundtrip(tmp_path):
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)

    updated = update_reference(
        root,
        entry.id,
        title=entry.title,
        type=entry.type,
        description=entry.description,
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        platform="mspm0",
        add_files={},
        remove_files=(),
        kit_vocabulary=(),
    )

    assert updated.platform == "mspm0"
    meta = json.loads((root / entry.id / "reference.json").read_text(encoding="utf-8"))
    assert meta["platform"] == "mspm0"


@pytest.mark.parametrize(
    "kind,value",
    [
        (ANCHOR_KIND_TOPIC, "2026C"),
        (ANCHOR_KIND_KIT, KIT_ALX),
    ],
)
def test_update_reference_anchor_kind_switches(tmp_path, kind, value):
    """锚定三态可互相切换：none → topic / kit 写回；再切回 none 清空值。"""
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    kit_vocabulary = (KIT_ALX,)

    switched = update_reference(
        root,
        entry.id,
        title=entry.title,
        type=entry.type,
        description=entry.description,
        anchor_kind=kind,
        anchor_value=value,
        add_files={},
        remove_files=(),
        kit_vocabulary=kit_vocabulary,
    )
    assert switched.anchor_kind == kind
    assert switched.anchor_value == value

    back = update_reference(
        root,
        entry.id,
        title=entry.title,
        type=entry.type,
        description=entry.description,
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        add_files={},
        remove_files=(),
        kit_vocabulary=kit_vocabulary,
    )
    assert back.anchor_kind == ANCHOR_KIND_NONE
    assert back.anchor_value == ""


def test_update_reference_add_files(tmp_path):
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)

    updated = update_reference(
        root,
        entry.id,
        title=entry.title,
        type=entry.type,
        description=entry.description,
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        add_files={"new.c": "/* 新增 */\n", "子目录/note.txt": "说明"},
        remove_files=(),
        kit_vocabulary=(),
    )

    assert (root / entry.id / "new.c").read_text(encoding="utf-8") == "/* 新增 */\n"
    assert (root / entry.id / "子目录" / "note.txt").read_text(encoding="utf-8") == "说明"
    # files 清单保序追加：原有在前、新增按序在后
    assert updated.files == ("example.c", "new.c", "子目录/note.txt")
    # 体量实况更新（新增文件计入）
    assert updated.file_count == entry.file_count + 2


def test_update_reference_remove_files(tmp_path):
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    # 清单外散文件（磁盘实况）也可删：与浏览「磁盘目录即数据库」同口径
    stray = root / entry.id / "散文件.bin"
    stray.write_bytes(b"xyz")

    updated = update_reference(
        root,
        entry.id,
        title=entry.title,
        type=entry.type,
        description=entry.description,
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        add_files={},
        remove_files=("example.c", "散文件.bin"),
        kit_vocabulary=(),
    )

    assert not (root / entry.id / "example.c").exists()
    assert not stray.exists()
    assert updated.files == ()
    meta = json.loads((root / entry.id / "reference.json").read_text(encoding="utf-8"))
    assert meta["files"] == []
    # reference.json 本身保留
    assert (root / entry.id / "reference.json").is_file()


def test_update_reference_rejects_bad_metadata_without_side_effects(tmp_path):
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    meta_before = (root / entry.id / "reference.json").read_text(encoding="utf-8")

    with pytest.raises(ReferenceError, match="不能为空"):
        update_reference(
            root,
            entry.id,
            title="",  # 空标题
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={},
            remove_files=(),
            kit_vocabulary=(),
        )
    with pytest.raises(ReferenceError, match="不能为空"):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type="",
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={},
            remove_files=(),
            kit_vocabulary=(),
        )
    with pytest.raises(ReferenceError, match="不能为空"):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description="  ",
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={},
            remove_files=(),
            kit_vocabulary=(),
        )

    # 磁盘零变化（元数据逐字节未动）
    assert (root / entry.id / "reference.json").read_text(encoding="utf-8") == meta_before


@pytest.mark.parametrize(
    "anchor_kind,anchor_value",
    [
        (ANCHOR_KIND_TOPIC, "26C"),  # 格式非法
        (ANCHOR_KIND_KIT, "某网店杂牌套件"),  # 词表外
        (ANCHOR_KIND_NONE, "2026C"),  # 未锚定却塞值
        ("series", "2026C"),  # 词表外类型
    ],
)
def test_update_reference_rejects_bad_anchor(tmp_path, anchor_kind, anchor_value):
    entry = _edit_sample_entry(tmp_path)

    with pytest.raises(ReferenceError):
        update_reference(
            _reference_root(tmp_path),
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=anchor_kind,
            anchor_value=anchor_value,
            add_files={},
            remove_files=(),
            kit_vocabulary=(KIT_ALX,),
        )


def test_update_reference_rejects_invalid_platform(tmp_path):
    entry = _edit_sample_entry(tmp_path)

    with pytest.raises(ReferenceError, match="非法平台属性"):
        update_reference(
            _reference_root(tmp_path),
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            platform="esp32",
            add_files={},
            remove_files=(),
            kit_vocabulary=(),
        )


@pytest.mark.parametrize(
    "add_files",
    [
        {"../evil.c": "x"},  # 路径穿越
        {"a\\b.c": "x"},  # 反斜杠
        {"/abs.c": "x"},  # 绝对路径
        {"reference.json": "x"},  # 与元数据文件冲突
        {},  # 空对象 = 无新增（合法，只走元数据）
    ],
)
def test_update_reference_accepts_or_rejects_add_paths(tmp_path, add_files):
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)

    if not add_files:
        updated = update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files=add_files,
            remove_files=(),
            kit_vocabulary=(),
        )
        assert updated.id == entry.id
    else:
        with pytest.raises(ReferenceError):
            update_reference(
                root,
                entry.id,
                title=entry.title,
                type=entry.type,
                description=entry.description,
                anchor_kind=ANCHOR_KIND_NONE,
                anchor_value="",
                add_files=add_files,
                remove_files=(),
                kit_vocabulary=(),
            )


def test_update_reference_overwrites_existing_add_path(tmp_path):
    """同名新增 = 覆盖内容（工单 ux-walkthrough-02/08）：一次提交替换文件内容，
    文件清单不重复、条目元数据（标题/锚定）不变——不再要求先删后加两步。"""
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    entry_dir = root / entry.id
    assert (entry_dir / "example.c").read_text(encoding="utf-8") != "/* 覆盖后的新内容 */\n"

    updated = update_reference(
        root,
        entry.id,
        title=entry.title,
        type=entry.type,
        description=entry.description,
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        add_files={"example.c": "/* 覆盖后的新内容 */\n"},
        remove_files=(),
        kit_vocabulary=(),
    )

    assert updated.files.count("example.c") == 1
    assert (entry_dir / "example.c").read_text(encoding="utf-8") == "/* 覆盖后的新内容 */\n"
    assert updated.title == entry.title  # 元数据未动
    assert updated.anchor_kind == ANCHOR_KIND_NONE


def test_update_reference_overwrite_restores_old_on_write_failure(tmp_path, monkeypatch):
    """覆盖语义的写入期失败（工单 ux-walkthrough-02/08 评审整改）：已覆盖的
    既有文件恢复旧内容、真正新建的文件清理——磁盘零变化（topic_library 同款
    恢复范式），不因回滚误删用户正在编辑的文件。"""
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    entry_dir = root / entry.id
    old = (entry_dir / "example.c").read_text(encoding="utf-8")
    real_write = Path.write_text
    calls = {"n": 0}

    def boom(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # 第一个文件（覆盖 example.c）已写，第二个（新建）写入时失败
            raise OSError("模拟写入失败")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", boom)

    with pytest.raises(OSError):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={"example.c": "/* 新内容 */\n", "second.c": "/* 新建 */\n"},
            remove_files=(),
            kit_vocabulary=(),
        )

    assert (entry_dir / "example.c").read_text(encoding="utf-8") == old  # 旧内容恢复
    assert not (entry_dir / "second.c").exists()  # 新建文件已清理


def test_update_reference_rejects_add_remove_overlap_still(tmp_path):
    """同名覆盖语义下，add 与 remove 同一文件仍拒绝（工单 ux-walkthrough-02/08：
    前端覆盖优先会从删除清单剔除，后端兜底拒绝「既添加又删除」）。"""
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)

    with pytest.raises(ReferenceError, match="既添加又删除"):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={"example.c": "x"},
            remove_files=("example.c",),
            kit_vocabulary=(),
        )


def test_update_reference_rejects_remove_missing_or_meta(tmp_path):
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    meta_before = (root / entry.id / "reference.json").read_text(encoding="utf-8")

    with pytest.raises(ReferenceError, match="不存在"):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={},
            remove_files=("不存在.c",),
            kit_vocabulary=(),
        )
    with pytest.raises(ReferenceError, match="冲突"):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={},
            remove_files=("reference.json",),
            kit_vocabulary=(),
        )
    # 校验失败磁盘零变化
    assert (root / entry.id / "reference.json").read_text(encoding="utf-8") == meta_before
    assert (root / entry.id / "example.c").is_file()


def test_update_reference_rejects_add_remove_overlap(tmp_path):
    entry = _edit_sample_entry(tmp_path)

    with pytest.raises(ReferenceError, match="既添加又删除|同一文件"):
        update_reference(
            _reference_root(tmp_path),
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={"both.c": "x"},
            remove_files=("both.c",),
            kit_vocabulary=(),
        )


def test_update_reference_validation_failure_leaves_files_untouched(tmp_path):
    """混合请求（合法 add + 非法元数据）：全部校验在落盘前，新文件不落盘。"""
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)

    with pytest.raises(ReferenceError):
        update_reference(
            root,
            entry.id,
            title="",
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={"should_not_exist.c": "/* 不应出现 */\n"},
            remove_files=(),
            kit_vocabulary=(),
        )
    assert not (root / entry.id / "should_not_exist.c").exists()


def test_update_reference_cleans_added_files_on_write_failure(tmp_path, monkeypatch):
    """写入中途失败：已写的新增文件清理、元数据保持原样（不留半成品）。"""
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    meta_before = (root / entry.id / "reference.json").read_text(encoding="utf-8")
    target = root / entry.id / "boom.c"
    real_write_text = Path.write_text

    def flaky_write_text(self, *args, **kwargs):
        if self == target:
            raise OSError("磁盘写失败")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)
    with pytest.raises(OSError, match="磁盘写失败"):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={"ok.c": "/* ok */\n", "boom.c": "/* 写失败 */\n"},
            remove_files=(),
            kit_vocabulary=(),
        )
    # 先写的 ok.c 被清理、boom.c 不落盘、元数据原样
    assert not (root / entry.id / "ok.c").exists()
    assert not target.exists()
    assert (root / entry.id / "reference.json").read_text(encoding="utf-8") == meta_before


def test_update_reference_cleans_added_files_on_meta_write_failure(
    tmp_path, monkeypatch
):
    """元数据写入失败：已写的新增文件同样清理、元数据保持原样。"""
    root = _reference_root(tmp_path)
    entry = _edit_sample_entry(tmp_path)
    meta_before = (root / entry.id / "reference.json").read_text(encoding="utf-8")
    monkeypatch.setattr(
        reference_library,
        "write_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("磁盘写失败")),
    )

    with pytest.raises(OSError, match="磁盘写失败"):
        update_reference(
            root,
            entry.id,
            title=entry.title,
            type=entry.type,
            description=entry.description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={"ok.c": "/* ok */\n"},
            remove_files=("example.c",),
            kit_vocabulary=(),
        )
    # 新增文件清理、被删文件未删（元数据写失败不丢实体）、元数据原样
    assert not (root / entry.id / "ok.c").exists()
    assert (root / entry.id / "example.c").is_file()
    assert (root / entry.id / "reference.json").read_text(encoding="utf-8") == meta_before


def test_update_reference_missing_entry(tmp_path):
    with pytest.raises(ReferenceError, match="不存在"):
        update_reference(
            _reference_root(tmp_path),
            "nope",
            title="t",
            type="例程工程",
            description="x",
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            add_files={},
            remove_files=(),
            kit_vocabulary=(),
        )


# ---------------------------------------------------------------------------
# 条目编辑：webapp 路由（PUT /api/references/{entry_id}）
# ---------------------------------------------------------------------------


def test_references_update_route_end_to_end(tmp_path):
    client = _app(tmp_path, ReferenceLLM())
    added = client.post(
        "/api/references",
        json={
            "title": "待编辑条目",
            "type": "例程工程",
            "description": "原始简介",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2026C",
            "files": {"example.c": EXAMPLE_C},
        },
    ).json()
    entry_id = added["id"]

    updated = client.put(
        f"/api/references/{entry_id}",
        json={
            "title": "改过的标题",
            "type": "说明书",
            "description": "改过的简介",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2026C",
            "platform": "mspm0",
            "add_files": {"new.c": "/* 新增 */\n"},
            "remove_files": ["example.c"],
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "改过的标题"
    assert body["platform"] == "mspm0"
    assert body["files"] == ["new.c"]

    # 列表反映变更；元数据编辑后条目 id / 目录名不变
    listed = client.get("/api/references").json()
    assert [e["id"] for e in listed] == [entry_id]
    assert [e["title"] for e in listed] == ["改过的标题"]
    # 旧文件已被删：服务 404 通道（400 中文）
    assert client.get(f"/api/references/{entry_id}/files/example.c").status_code == 400
    assert client.get(f"/api/references/{entry_id}/files/new.c").status_code == 200


def test_references_update_route_rejects_bad_payloads(tmp_path):
    client = _app(tmp_path, ReferenceLLM())
    added = client.post(
        "/api/references",
        json={
            "title": "待编辑条目",
            "type": "例程工程",
            "description": "原始简介",
            "anchor_kind": ANCHOR_KIND_TOPIC,
            "anchor_value": "2026C",
            "files": {"example.c": EXAMPLE_C},
        },
    ).json()
    entry_id = added["id"]

    base = {
        "title": "t",
        "type": "说明书",
        "description": "x",
        "anchor_kind": ANCHOR_KIND_TOPIC,
        "anchor_value": "2026C",
        "platform": "any",
    }

    # 缺必填字段（元数据全量必填：PUT 是替换语义，platform 缺省不得兜底 any）
    assert client.put(
        f"/api/references/{entry_id}", json={"title": "t"}
    ).status_code == 400
    assert (
        client.put(
            f"/api/references/{entry_id}", json={**base, "platform": None}
        ).status_code
        == 400
    )
    assert "platform" in client.put(
        f"/api/references/{entry_id}", json={k: v for k, v in base.items() if k != "platform"}
    ).json()["detail"]
    # add_files 形状错（非对象，含空数组也不放行）
    assert (
        client.put(
            f"/api/references/{entry_id}",
            json={**base, "add_files": ["not-a-dict"]},
        ).status_code
        == 400
    )
    assert (
        client.put(
            f"/api/references/{entry_id}", json={**base, "add_files": []}
        ).status_code
        == 400
    )
    # remove_files 形状错
    assert (
        client.put(
            f"/api/references/{entry_id}",
            json={**base, "remove_files": "not-a-list"},
        ).status_code
        == 400
    )
    # 删不存在的文件
    bad_remove = client.put(
        f"/api/references/{entry_id}",
        json={**base, "remove_files": ["不存在.c"]},
    )
    assert bad_remove.status_code == 400
    assert "不存在" in bad_remove.json()["detail"]
    # 条目不存在
    assert (
        client.put(
            "/api/references/missing",
            json=base,
        ).status_code
        == 400
    )
    # 显式空容器 = 合法：remove_files: [] 与 add_files: {} 都是无操作
    assert (
        client.put(
            f"/api/references/{entry_id}",
            json={**base, "add_files": {}, "remove_files": []},
        ).status_code
        == 200
    )


def test_references_anchor_value_empty_allowed_for_none(tmp_path):
    """未锚定条目：anchor_value 空串是合法值（页面「未锚定」单选提交 ""）。

    回归：路由曾用 _require_str 校验 anchor_value（拒空串），导致「未锚定」
    条目永远无法新增 / 编辑（存量 148/154 条均为早期录入）。键必须存在且为
    字符串（非字符串仍 400）；空串合法性由 _validate_anchor 域校验裁决
    （none 强制空值 / topic 格式 / kit 词表）。
    """
    client = _app(tmp_path, ReferenceLLM())
    added = client.post(
        "/api/references",
        json={
            "title": "未锚定条目",
            "type": "说明书",
            "description": "不属于任何赛题 / 套件",
            "anchor_kind": ANCHOR_KIND_NONE,
            "anchor_value": "",
            "files": {"doc.txt": "正文"},
        },
    )
    assert added.status_code == 200
    entry_id = added.json()["id"]
    assert added.json()["anchor_kind"] == ANCHOR_KIND_NONE
    assert added.json()["anchor_value"] == ""

    updated = client.put(
        f"/api/references/{entry_id}",
        json={
            "title": "未锚定条目（改）",
            "type": "说明书",
            "description": "改过",
            "anchor_kind": ANCHOR_KIND_NONE,
            "anchor_value": "",
            "platform": "any",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "未锚定条目（改）"
    assert updated.json()["anchor_value"] == ""

    # 非字符串值仍拒（400）；未锚定 + 非空锚定值仍拒（域校验）
    assert (
        client.post(
            "/api/references",
            json={
                "title": "x",
                "type": "y",
                "description": "z",
                "anchor_kind": ANCHOR_KIND_NONE,
                "anchor_value": 123,
                "files": {"a.c": "int a;"},
            },
        ).status_code
        == 400
    )
    assert (
        client.put(
            f"/api/references/{entry_id}",
            json={
                "title": "未锚定条目",
                "type": "说明书",
                "description": "改",
                "anchor_kind": ANCHOR_KIND_NONE,
                "anchor_value": "2026C",
                "platform": "any",
            },
        ).status_code
        == 400
    )


# ---------------------------------------------------------------------------
# 相关性匹配（工单 ref-related-autoload）：题面文本 / 选中模块 slug → 参考条目
# 标题 的确定性词表匹配纯函数——两级注入第一级的候选扩容（候选 = 锚定 ∪ 相关）
# ---------------------------------------------------------------------------


def _demo_reference(
    root: Path,
    *,
    title: str,
    description: str = "示例简介",
    platform: str = "any",
) -> Path:
    """相关性测试用条目：未锚定、单文件（与真实例程同形状）。"""
    return add_reference(
        root,
        title=title,
        type="例程工程",
        description=description,
        anchor_kind=ANCHOR_KIND_NONE,
        anchor_value="",
        files={"main.c": "/* demo */\n"},
        kit_vocabulary=(),
        platform=platform,
    ).id


def test_related_references_matches_peripheral_terms(tmp_path):
    """题面外设词 → 条目标题命中：UART/串口与定时器条目进候选，无关条目不进。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="UART-串口打印例程")
    _demo_reference(root, title="定时器-基本例程")
    _demo_reference(root, title="OLED 显示例程")
    hits = related_references(root, topic_text="用串口打印，定时器中断采集", limit=10)
    assert [e.id for e in hits] == ["UART-串口打印例程", "定时器-基本例程"]


def test_related_references_ascii_term_boundary_avoids_substring(tmp_path):
    """题面英文词表项必须独立出现：canmv 不激活 can（防子串伪命中）。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="CAN-总线例程")
    assert related_references(root, topic_text="使用 canmv 视觉识别", limit=5) == ()
    hits = related_references(root, topic_text="can 总线与 canmv 视觉", limit=5)
    assert [e.id for e in hits] == ["CAN-总线例程"]


def test_related_references_ascii_term_matches_token_with_digits(tmp_path):
    """英文词表项命中条目标题 token 的前缀+数字形态：adc → adc12。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="ADC12-单通道采样例程")
    hits = related_references(root, topic_text="adc 采样", limit=5)
    assert [e.id for e in hits] == ["ADC12-单通道采样例程"]


def test_related_references_chinese_term_substring(tmp_path):
    """中文词表项在标题 token 内子串命中：串口 → USART-串口打印例程。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="USART-串口打印例程")
    hits = related_references(root, topic_text="串口通信", limit=5)
    assert [e.id for e in hits] == ["USART-串口打印例程"]


def test_related_references_slug_mapping_activates_terms(tmp_path):
    """选中模块 slug 经 MODULE_PERIPHERAL_TERMS 激活词表项：adc slug → adc 例程
    （题面不含外设词也能命中——骨架阶段按选中模块自动关联的依据）。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="ADC12-单通道采样例程")
    hits = related_references(root, topic_text="采集电压并显示", slugs=("adc",), limit=5)
    assert [e.id for e in hits] == ["ADC12-单通道采样例程"]


def test_related_references_scores_desc_and_limit(tmp_path):
    """得分 = 命中的激活词表项数，降序截断：双词命中排在单词命中前。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="UART-串口例程")  # uart + 串口 = 2 分
    _demo_reference(root, title="定时器-基本例程")  # 定时器 = 1 分
    _demo_reference(root, title="OLED 显示例程")  # 0 分
    hits = related_references(root, topic_text="UART 串口中断，定时器采集", limit=1)
    assert [e.id for e in hits] == ["UART-串口例程"]


def test_related_references_platform_filter(tmp_path):
    """平台过滤沿用既有判据：非 any 平台只收匹配/any 条目。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="UART-串口例程", platform="mspm0")
    _demo_reference(root, title="串口调试助手说明", platform="any")
    hits = related_references(root, topic_text="串口", platform="stm32", limit=5)
    assert [e.id for e in hits] == ["串口调试助手说明"]


def test_related_references_tie_break_platform_exact_first(tmp_path):
    """同分平局键：平台精确匹配条目排在 any 条目前（平台非空时）；空串无差异。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="串口例程甲", platform="any")
    _demo_reference(root, title="串口例程乙", platform="mspm0")
    hits = related_references(root, topic_text="串口", platform="mspm0", limit=5)
    assert [e.id for e in hits] == ["串口例程乙", "串口例程甲"]
    hits_any = related_references(root, topic_text="串口", limit=5)
    assert [e.id for e in hits_any] == sorted(["串口例程甲", "串口例程乙"])


def test_related_references_tie_breaks_by_id(tmp_path):
    """同分稳定序 = 条目标题生成的 id 字典序（确定性，不随磁盘序漂移）。"""
    root = _reference_root(tmp_path)
    first = _demo_reference(root, title="串口例程甲")
    second = _demo_reference(root, title="串口例程乙")
    hits = related_references(root, topic_text="串口", limit=5)
    assert [e.id for e in hits] == sorted([first, second])


def test_related_references_defaults_and_edge_cases(tmp_path):
    """缺省行为与零增量边界：limit=0 缺省关闭；空题面/空 slugs 无激活；
    词表不命中 = 空；库目录不存在 = 空。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="UART-串口打印例程")
    assert related_references(root, topic_text="串口") == ()  # limit=0 缺省关闭
    assert len(related_references(root, topic_text="串口", limit=3)) == 1
    assert len(related_references(root, topic_text="", slugs=("uart",), limit=3)) == 1
    assert related_references(root, topic_text="完全无关词汇", limit=3) == ()
    assert related_references(
        root / "不存在的库", topic_text="串口", limit=3
    ) == ()
    assert len(related_references(root, topic_text="串口", limit=3, platform="mspm0")) == 1


def test_related_references_vocabulary_single_source(tmp_path):
    """词表单源：PERIPHERAL_TERMS 覆盖库内例程关键外设词（英文边界项 + 中文子串项），
    MODULE_PERIPHERAL_TERMS 的 slug 映射值都在词表内；同义词组内词同样在词表内。"""
    for term in ("adc", "uart", "spi", "i2c", "can", "gpio", "dma", "flash", "rtc",
                 "nvic", "systick", "timer", "pwm", "串口", "定时器", "比较器",
                 "运放", "低功耗", "循迹", "巡线", "摄像头", "视觉"):
        assert term in PERIPHERAL_TERMS
    for terms in MODULE_PERIPHERAL_TERMS.values():
        assert all(term in PERIPHERAL_TERMS for term in terms)
    assert MODULE_PERIPHERAL_TERMS["adc"] == ("adc",)
    assert "uart" not in MODULE_PERIPHERAL_TERMS["adc"]
    for group in PERIPHERAL_SYNONYM_GROUPS:
        assert all(term in PERIPHERAL_TERMS for term in group)


def test_related_references_synonym_group_bridges_problem_and_title(tmp_path):
    """同义词组桥接（工单 02 巡检补）：题面命中「循迹」→ 条目标题「巡线」也
    命中（组内任一词命中 token 计 1 分，同义词不重复计分——标题同时含两词
    仍 1 分）；反向（题面「巡线」→ 条目「循迹」）同样桥接。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="20XX-巡线送药决策例程")
    _demo_reference(root, title="循迹模板-基础版")
    _demo_reference(root, title="UART-串口打印例程")

    hits = related_references(root, topic_text="循迹小车", limit=5)
    assert [e.title for e in hits] == [
        "20XX-巡线送药决策例程",  # 题面「循迹」→ 标题「巡线」（同义桥接）
        "循迹模板-基础版",
    ]
    hits = related_references(root, topic_text="巡线小车", limit=5)
    assert [e.title for e in hits] == [
        "20XX-巡线送药决策例程",
        "循迹模板-基础版",  # 反向桥接
    ]
    # 同义词不重复计分：标题「循迹-巡线双词例程」在题面「循迹」下仍 1 分
    # （若按词计分会得 2 分排首位；按组计分与其它 1 分条目同组、id 序第 2）
    _demo_reference(root, title="循迹-巡线双词例程")
    hits = related_references(root, topic_text="循迹", limit=5)
    dual = next(e for e in hits if e.title == "循迹-巡线双词例程")
    assert hits.index(dual) == 1


def test_related_references_ascii_term_with_cjk_tail_in_title(tmp_path):
    """英文词项粘连中文尾巴（工单 02 巡检补）：标题「ESP32-CAM开发板资料」
    （token 拆分后 cam 后是「开」——非纯数字尾巴）题面含摄像头 → cam 以
    字母数字边界独立出现命中（跨语言同义组）；canmv 内 can 仍不命中
    （can 后是字母 m，粘连规则不误报）。"""
    root = _reference_root(tmp_path)
    _demo_reference(root, title="C7-3-4L ESP32-CAM开发板资料")
    _demo_reference(root, title="canmv-k230 开发板资料")

    hits = related_references(root, topic_text="摄像头视觉识别", limit=5)
    assert [e.title for e in hits] == ["C7-3-4L ESP32-CAM开发板资料"]
    # canmv 条目在「can（CAN 总线）」题面下也不因 canmv 中缀 miss 边界——不命中
    hits = related_references(root, topic_text="CAN 总线通信", limit=5)
    assert "canmv-k230 开发板资料" not in [e.title for e in hits]
