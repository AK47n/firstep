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
from contest_generator.platforms import PLATFORM_STM32
from contest_generator import reference_library
from contest_generator.reference_library import (
    ANCHOR_KIND_KIT,
    ANCHOR_KIND_NONE,
    ANCHOR_KIND_TOPIC,
    ARCHIVE_ENTRY_TYPE,
    ReferenceError,
    add_reference,
    archive_reference,
    delete_reference,
    draft_description,
    get_reference,
    list_references,
    module_kit_vocabulary,
    read_fulltext,
    search_references,
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

    listed = client.get("/api/references")
    assert [e["title"] for e in listed.json()] == ["2026C 数字钥匙例程"]
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
# 断言原样——拼装字节逐字不变）
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
