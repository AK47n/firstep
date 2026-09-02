"""赛题库核心：长 PDF 拆条（AI）→ 用户逐条校对 → 确认入库（事务）+ 编号解析。

用假 LLM（FakeLLM 子类补 topic_* 职责，tests/fakes.py 只读）驱动，断言磁盘
库目录结构（一条目一目录：题面 topic.md + manifest.json + 原 PDF 副本）与
manifest 内容（外部行为）。确认入库是事务：任何校验失败都在落盘前，失败
不留半成品；编号解析查无此条明确报错、不猜测编造。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contest_generator.config import AppConfig
from contest_generator.llm import (
    LLMError,
    TOPIC_SPLIT_LLM_CHAR_CAP,
    parse_topic_number,
    parse_topic_split,
)
from contest_generator.manifest import MANIFEST_FILENAME
from contest_generator.extraction import locate_topic_pages_full
from contest_generator.topic_library import (
    TOPIC_CATEGORIES,
    TOPIC_MD_FILENAME,
    TopicDraft,
    TopicEntry,
    TopicError,
    TopicHealth,
    confirm_topics,
    delete_topic,
    enrich_topic_image_notes,
    list_topics,
    parse_confirm_entries,
    resolve_number,
    split_topics_document,
    topic_health,
    update_topic,
)


from contest_generator.webapp import AppContext, create_app
from tests.fakes import (
    FakeLLM,
    make_fake_module_library,
    make_sample_pdf,
)
from tests.topic_pdf_fakes import make_multi_page_pdf


@pytest.fixture(autouse=True)
def _no_render_notes(monkeypatch):
    """渲染视觉路径单测关闭（工单 topic-vision-render/02）：不真实渲染 / 调视觉。

    _figure_notes 第一级是 pdf_page_render_notes（渲染 → DeepSeek 视觉）——
    单测假 PDF 渲染失败走降级是碰运气（fitz 可用时会真发网络请求）。统一
    置空：渲染失败语义 = 降级文字标注，既有断言路径不变。渲染优先的专门
    测试自行 setattr 覆盖。
    """
    import contest_generator.topic_library as topic_library

    monkeypatch.setattr(
        topic_library, "pdf_page_render_notes", lambda *a, **k: ""
    )


class FakeTopicLLM(FakeLLM):
    """假 LLM 补赛题库两个职责（拆条 / 编号提取）；既有职责继承 FakeLLM。

    FakeLLM 在 tests/fakes.py（只读），补职责用子类不改原文件。
    """

    def __init__(
        self,
        split: tuple[TopicDraft, ...] = (),
        number: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._split = tuple(split)
        self._number = number
        self.split_calls: list[str] = []
        self.number_calls: list[str] = []

    def topic_split_topics(self, pdf_text: str) -> tuple[TopicDraft, ...]:
        self.split_calls.append(pdf_text)
        return self._split

    def topic_extract_number(self, text: str) -> str | None:
        self.number_calls.append(text)
        return self._number


DRAFTS = (
    TopicDraft(year="2026", number="C", problem_text="2026C 题面：数字钥匙锁……"),
    TopicDraft(year="2026", number="D", problem_text="2026D 题面：……"),
)

KEY_2026C = "2026C"
KEY_2026D = "2026D"


@pytest.fixture
def topic_root(tmp_path):
    """赛题库根目录（磁盘目录即数据库）。"""
    return tmp_path / "topics"


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "2026真题.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    return path


# ---------------------------------------------------------------------------
# LLM 严格解析：拆条 / 编号提取的畸形输出抛 LLMError（宁可大声失败）
# ---------------------------------------------------------------------------


def test_parse_topic_split_happy_path():
    drafts = parse_topic_split(
        json.dumps(
            {
                "topics": [
                    {"year": d.year, "number": d.number, "problem_text": d.problem_text}
                    for d in DRAFTS
                ]
            }
        )
    )

    assert drafts == DRAFTS
    assert drafts[0].key == "2026C"


def test_parse_topic_split_rejects_non_json():
    with pytest.raises(LLMError, match="不是 JSON"):
        parse_topic_split("not json")


def test_parse_topic_split_rejects_missing_topics_array():
    with pytest.raises(LLMError, match="topics"):
        parse_topic_split('{"year": "2026"}')


def test_parse_topic_split_rejects_non_dict_entry():
    with pytest.raises(LLMError, match="对象"):
        parse_topic_split('{"topics": ["2026C"]}')


def test_parse_topic_split_rejects_missing_fields():
    with pytest.raises(LLMError, match="year"):
        parse_topic_split('{"topics": [{"number": "C", "problem_text": "x"}]}')


def test_parse_topic_split_rejects_bad_key_format():
    # 年份不是 4 位数字 / 题号非单个大写字母（多字母 / 小写）→ 畸形输出
    with pytest.raises(LLMError, match="编号"):
        parse_topic_split(
            '{"topics": [{"year": "26", "number": "C", "problem_text": "x"}]}'
        )
    with pytest.raises(LLMError, match="编号"):
        parse_topic_split(
            '{"topics": [{"year": "2026", "number": "C1", "problem_text": "x"}]}'
        )
    with pytest.raises(LLMError, match="编号"):
        parse_topic_split(
            '{"topics": [{"year": "2026", "number": "CC", "problem_text": "x"}]}'
        )
    with pytest.raises(LLMError, match="编号"):
        parse_topic_split(
            '{"topics": [{"year": "2026", "number": "c", "problem_text": "x"}]}'
        )


def test_parse_topic_split_rejects_empty_topics():
    """零赛题 = 模型读错 / 素材不是真题：大声失败，不给空校对页。"""
    with pytest.raises(LLMError, match="没有拆出任何赛题"):
        parse_topic_split('{"topics": []}')


def test_parse_topic_split_rejects_empty_problem_text():
    with pytest.raises(LLMError, match="题面"):
        parse_topic_split(
            '{"topics": [{"year": "2026", "number": "C", "problem_text": "  "}]}'
        )


def test_parse_topic_split_rejects_duplicate_keys():
    with pytest.raises(LLMError, match="重复"):
        parse_topic_split(
            '{"topics": ['
            '{"year": "2026", "number": "C", "problem_text": "a"},'
            '{"year": "2026", "number": "C", "problem_text": "b"}'
            "]}"
        )


def test_parse_topic_number_happy_path():
    assert parse_topic_number('{"key": "2026C"}') == "2026C"


def test_parse_topic_number_empty_key_means_none():
    assert parse_topic_number('{"key": ""}') is None


def test_parse_topic_number_rejects_malformed_key():
    with pytest.raises(LLMError, match="编号"):
        parse_topic_number('{"key": "2026"}')  # 缺题号


def test_parse_topic_number_rejects_non_json():
    with pytest.raises(LLMError, match="不是 JSON"):
        parse_topic_number("not json")


# ---------------------------------------------------------------------------
# 确定性分块（工单 04）：多年长 PDF 按年份章节 + 题目标记切到单题，零 AI 改写
# ---------------------------------------------------------------------------

SPLIT_LINES = [
    "2017年 2018年 2025年全国大学生电子设计竞赛真题汇总",  # 封面：各年份紧邻距离小
    "2017 年全国大学生电子设计竞赛",  # 2017 章节（"2017 年"变体）
    "（A 题）2017A 题面：……正文内容……",
    "B 题难度较高，此处是正文不是标记",  # 行首 B 题后非冒号 → 不匹配
    "停止条件见评分标准",  # 正文"条件"类词 → 不匹配
    "(B 题) 2017B 题面：……正文内容……",  # 半角括号式
    "2018年全国大学生电子设计竞赛",
    "（A 题）2018A 题面：……正文……",
    "（A题）重复标记去重",  # 无空格括号式 + 同字母去重
    "C题：行首半角冒号式 2018C 题面",
    "2019年全国大学生电子设计竞赛",  # 缺题年份：有章节无题目
    "本页无赛题",
    "2020年全国大学生电子设计竞赛",
    "D题：行首全角冒号式 2020D 题面",
    "评分汇总表……2020 年得分统计与页脚说明",  # 尾部杂项 → 进最后一题
]
SPLIT_DOC = "\n".join(SPLIT_LINES)


def test_split_topics_document_cuts_single_topics_verbatim():
    drafts = split_topics_document(SPLIT_DOC)

    assert [d.key for d in drafts] == ["2017A", "2017B", "2018A", "2018C", "2020D"]
    assert drafts[0].problem_text == "\n".join(SPLIT_LINES[2:5])
    assert drafts[1].problem_text == SPLIT_LINES[5]
    assert drafts[2].problem_text == "\n".join(SPLIT_LINES[7:9])
    assert drafts[3].problem_text == SPLIT_LINES[9]
    assert drafts[4].problem_text == "\n".join(SPLIT_LINES[13:15])


def test_split_topics_document_groups_year_variants_by_number():
    """'2017年'（封面）与'2017 年'（章节）按数字归组，取'到下一年距离最大'
    的出现为章节起点——封面行（紧邻后续年份，距离小）不进任何题面。"""
    doc = "\n".join(
        [
            "2017年 2018年 2025年全国大学生电子设计竞赛真题汇总",
            "2017 年全国大学生电子设计竞赛",
            "（A 题）2017A 题面",
            "2018年全国大学生电子设计竞赛",
            "（A 题）2018A 题面",
        ]
    )

    drafts = split_topics_document(doc)

    assert [d.key for d in drafts] == ["2017A", "2018A"]
    assert drafts[0].problem_text == "（A 题）2017A 题面"  # 封面行不在题面内
    assert drafts[1].problem_text == "（A 题）2018A 题面"


def test_split_topics_document_no_year_chapter_raises():
    with pytest.raises(TopicError, match="年份"):
        split_topics_document("没有年份章节的文本（A 题）……")


def test_split_topics_document_years_without_topics_raises():
    with pytest.raises(TopicError, match="赛题"):
        split_topics_document("2025年全国大学生电子设计竞赛\n本页无赛题")


# ---------------------------------------------------------------------------
# 确认入库（事务）：一条目一目录，题面 .md + manifest + 原 PDF 副本
# ---------------------------------------------------------------------------


def test_confirm_topics_creates_entry_dirs_with_md_manifest_and_pdf(
    topic_root, pdf
):
    program = topic_root.parent / "2026C-key"
    program.mkdir()

    entries = confirm_topics(
        topic_root,
        pdf,
        DRAFTS,
        program_dirs=[program],
        pdf_filename="2026真题.pdf",
    )

    assert [e.key for e in entries] == [KEY_2026C, KEY_2026D]
    entry_dir = topic_root / KEY_2026C
    assert (entry_dir / TOPIC_MD_FILENAME).read_text(encoding="utf-8") == DRAFTS[0].problem_text
    assert (entry_dir / "2026真题.pdf").read_bytes() == b"%PDF-1.4 fake"
    manifest = json.loads((entry_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert manifest["year"] == "2026"
    assert manifest["number"] == "C"
    assert manifest["problem_md"] == TOPIC_MD_FILENAME
    assert manifest["original_pdf"] == "2026真题.pdf"
    assert manifest["programs"] == [str(program)]
    assert (topic_root / KEY_2026D / TOPIC_MD_FILENAME).exists()


def test_topic_mtime_roundtrip(topic_root, pdf):
    """mtime（ux-polish-02/07）：确认入库/读回/列表都带 manifest mtime——
    「最近更新」排序数据源；该字段只进序列化响应，不写进 manifest。"""
    entries = confirm_topics(topic_root, pdf, DRAFTS, pdf_filename="真题.pdf")
    for entry in entries:
        assert entry.mtime > 0
        assert entry.to_dict()["mtime"] == entry.mtime
    assert [e.key for e in list_topics(topic_root)] == [
        KEY_2026C, KEY_2026D,
    ]
    assert all(e.mtime > 0 for e in list_topics(topic_root))
    manifest = json.loads(
        (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert "mtime" not in manifest


def test_confirm_topics_keeps_original_pdf_inside_each_entry(topic_root, pdf):
    confirm_topics(topic_root, pdf, DRAFTS, pdf_filename="原题.pdf")

    for key in (KEY_2026C, KEY_2026D):
        assert (topic_root / key / "原题.pdf").is_file()


def test_confirm_topics_empty_entries_rejected(topic_root, pdf):
    with pytest.raises(TopicError, match="至少"):
        confirm_topics(topic_root, pdf, [])


def test_confirm_topics_duplicate_keys_rejected_before_any_write(topic_root, pdf):
    with pytest.raises(TopicError, match="重复"):
        confirm_topics(topic_root, pdf, (DRAFTS[0], DRAFTS[0]))

    assert not topic_root.exists()  # 校验失败：目录都没建


def test_confirm_topics_existing_entry_rejected(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))

    with pytest.raises(TopicError, match="已存在"):
        confirm_topics(topic_root, pdf, DRAFTS)

    # 既有条目完好，新条目不落半成品
    assert (topic_root / KEY_2026C / TOPIC_MD_FILENAME).exists()
    assert not (topic_root / KEY_2026D).exists()


@pytest.mark.parametrize(
    "draft",
    [
        TopicDraft(year="26", number="C", problem_text="x"),  # 年份非 4 位数字
        TopicDraft(year="2026", number="C1", problem_text="x"),  # 题号含非字母
        TopicDraft(year="2026", number="C", problem_text="  "),  # 题面空白
    ],
)
def test_confirm_topics_rejects_invalid_draft(topic_root, pdf, draft):
    with pytest.raises(TopicError):
        confirm_topics(topic_root, pdf, (draft,))

    assert not topic_root.exists()


def test_confirm_topics_rejects_missing_pdf(topic_root, tmp_path):
    with pytest.raises(TopicError, match="PDF"):
        confirm_topics(topic_root, tmp_path / "不存在.pdf", DRAFTS)

    assert not topic_root.exists()


def test_confirm_topics_rejects_missing_program_dir(topic_root, pdf):
    with pytest.raises(TopicError, match="程序目录"):
        confirm_topics(
            topic_root, pdf, DRAFTS, program_dirs=[str(topic_root.parent / "幽灵")]
        )

    assert not topic_root.exists()  # 校验失败：什么都没建


def test_confirm_topics_rejects_blank_program_dir(topic_root, pdf):
    """空白程序目录拒绝（Path('') 会变成 '.'，落盘后查不到真实目录）。"""
    with pytest.raises(TopicError, match="不能为空"):
        confirm_topics(topic_root, pdf, (DRAFTS[0],), program_dirs=["  "])

    assert not topic_root.exists()


def test_confirm_topics_rolls_back_created_dirs_on_midway_failure(
    topic_root, pdf, monkeypatch
):
    """事务：落盘中途失败（第二个条目复制 PDF 时模拟磁盘错误）清理全部已建条目。

    首条已完整落盘也会被清掉——任何失败都不留半成品。
    """
    real_copy2 = shutil.copy2
    calls = {"count": 0}

    def failing_copy2(src, dst, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("模拟磁盘写失败")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copy2", failing_copy2)

    with pytest.raises(OSError, match="磁盘写失败"):
        confirm_topics(topic_root, pdf, DRAFTS)

    assert not (topic_root / KEY_2026C).exists()  # 首条已建目录也被清理
    assert not (topic_root / KEY_2026D).exists()


def test_confirm_topics_rejects_pdf_name_colliding_with_topic_md(topic_root, pdf):
    with pytest.raises(TopicError, match="文件名"):
        confirm_topics(topic_root, pdf, DRAFTS, pdf_filename=TOPIC_MD_FILENAME)


def test_confirm_topics_rejects_pdf_name_colliding_with_manifest(topic_root, pdf):
    with pytest.raises(TopicError, match="文件名"):
        confirm_topics(topic_root, pdf, DRAFTS, pdf_filename=MANIFEST_FILENAME)


def test_confirm_topics_uses_basename_of_unsafe_pdf_name(topic_root, pdf):
    entries = confirm_topics(
        topic_root, pdf, (DRAFTS[0],), pdf_filename="..\\..\\evil.pdf"
    )

    assert entries[0].original_pdf == "evil.pdf"
    assert (topic_root / KEY_2026C / "evil.pdf").is_file()


# ---------------------------------------------------------------------------
# 编号解析：显式输入查库，查无此条明确报错（不猜测编造）
# ---------------------------------------------------------------------------


def test_resolve_number_returns_problem_text(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))

    entry = resolve_number(topic_root, KEY_2026C)

    assert entry.key == KEY_2026C
    assert entry.problem_text == DRAFTS[0].problem_text
    assert entry.programs == ()


def test_resolve_number_missing_raises_explicitly(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))

    with pytest.raises(TopicError, match=KEY_2026D):
        resolve_number(topic_root, KEY_2026D)


@pytest.mark.parametrize(
    "bad_key", ["../evil", "2026", "2026C1", "2026CC", "2026c", "abc", ""]
)
def test_resolve_number_rejects_bad_key_format(topic_root, bad_key):
    with pytest.raises(TopicError, match="编号"):
        resolve_number(topic_root, bad_key)


def test_resolve_number_loads_programs_and_pdf_name(topic_root, pdf, tmp_path):
    program = tmp_path / "2026C-lock"
    program.mkdir()
    confirm_topics(
        topic_root,
        pdf,
        (DRAFTS[0],),
        program_dirs=[program],
        pdf_filename="真题.pdf",
    )

    entry = resolve_number(topic_root, KEY_2026C)

    assert entry.original_pdf == "真题.pdf"
    assert entry.programs == (str(program),)


def test_resolve_number_loads_hint_module_groups(topic_root, pdf):
    """topic manifest 可选 hint_module_groups（工单 recommend-exclusive-groups/02）：
    组 id 清单解析进条目；缺省 / 空 = 空元组（旧 manifest 兼容）。"""
    confirm_topics(topic_root, pdf, (DRAFTS[0],))
    entry = resolve_number(topic_root, KEY_2026C)
    assert entry.hint_module_groups == ()

    manifest_path = topic_root / KEY_2026C / MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["hint_module_groups"] = ["attitude-hold", "gray-track"]
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    entry = resolve_number(topic_root, KEY_2026C)
    assert entry.hint_module_groups == ("attitude-hold", "gray-track")
    assert entry.to_dict()["hint_module_groups"] == ["attitude-hold", "gray-track"]


@pytest.mark.parametrize(
    "bad", ["attitude-hold", [123], [""], {"g": "attitude-hold"}, [True], None]
)
def test_resolve_number_rejects_bad_hint_module_groups(topic_root, pdf, bad):
    """hint_module_groups 类型错（非字符串列表 / 空串成员）→ TopicError 大声
    失败（与 programs 同款严格校验）。"""
    confirm_topics(topic_root, pdf, (DRAFTS[0],))
    manifest_path = topic_root / KEY_2026C / MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["hint_module_groups"] = bad
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TopicError, match="hint_module_groups"):
        resolve_number(topic_root, KEY_2026C)


# ---------------------------------------------------------------------------
# 存量条目补图注（工单 topic-vision-notes/02）：取题面自动补 + 幂等 + 降级
# ---------------------------------------------------------------------------


def _confirm_figure_topic(topic_root, pdf, problem_text="系统功能如图1所示。"):
    """入库一个题面引用图（图1）的 2026C 条目，返回该条目。"""
    return confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2026", number="C", problem_text=problem_text),),
    )[0]


def test_enrich_topic_image_notes_appends_and_is_idempotent(topic_root, pdf, monkeypatch):
    """补图注：图注段追加题面文末并写回；二次调用幂等（不再跑视觉）。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf)
    calls: list[str] = []

    def fake_notes(path, **kwargs):
        calls.append(str(path))
        return "[示意图1：这是功能示意图的完整布局]"

    monkeypatch.setattr(topic_library, "pdf_image_notes", fake_notes)

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )
    assert entry.problem_text == "系统功能如图1所示。\n\n[示意图1：这是功能示意图的完整布局]"
    # 写回磁盘
    on_disk = (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8")
    assert on_disk == "系统功能如图1所示。\n\n[示意图1：这是功能示意图的完整布局]"
    assert len(calls) == 1
    # 幂等：已含图注 → 二次调用不再跑视觉
    topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )
    assert len(calls) == 1


def test_enrich_topic_image_notes_skips_without_figure_ref(topic_root, pdf, monkeypatch):
    """题面无图引用（无"图N"）→ 原样返回，不跑视觉不写回。"""
    from contest_generator import topic_library

    confirm_topics(topic_root, pdf, (DRAFTS[0],))  # "2026C 题面：数字钥匙锁……"
    calls: list[str] = []
    monkeypatch.setattr(
        topic_library, "pdf_image_notes", lambda *a, **k: calls.append("x") or "[示意图]"
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )
    assert entry.problem_text == DRAFTS[0].problem_text
    assert calls == []


def test_enrich_topic_image_notes_skips_when_already_annotated(topic_root, pdf, monkeypatch):
    """题面已含 [示意图 标注 → 幂等跳过（旧条目补过一次不再补）。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf, "系统功能如图1所示。\n\n[示意图1：旧图注]")
    calls: list[str] = []
    monkeypatch.setattr(
        topic_library, "pdf_image_notes", lambda *a, **k: calls.append("x") or "[示意图]"
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )
    assert entry.problem_text == "系统功能如图1所示。\n\n[示意图1：旧图注]"
    assert calls == []


def test_enrich_topic_image_notes_skips_without_pdf(topic_root, pdf, monkeypatch):
    """有图引用但原 PDF 不在条目目录 → 原样返回。"""
    from contest_generator import topic_library

    entry = _confirm_figure_topic(topic_root, pdf)
    (topic_root / KEY_2026C / entry.original_pdf).unlink()
    calls: list[str] = []
    monkeypatch.setattr(
        topic_library, "pdf_image_notes", lambda *a, **k: calls.append("x") or "[示意图]"
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )
    assert entry.problem_text == "系统功能如图1所示。"
    assert calls == []


def test_enrich_topic_image_notes_degrades_on_vision_failure(topic_root, pdf, monkeypatch):
    """视觉异常 → 原样返回不写回（视觉是增强不是阻塞）。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf)
    monkeypatch.setattr(
        topic_library,
        "pdf_image_notes",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("网络瞬断")),
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )
    assert entry.problem_text == "系统功能如图1所示。"
    on_disk = (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8")
    assert on_disk == "系统功能如图1所示。"


def test_enrich_topic_image_notes_empty_notes_returns_unchanged(topic_root, pdf, monkeypatch):
    """图注生成空串（无嵌入图）→ 原样返回不写回。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf)
    monkeypatch.setattr(topic_library, "pdf_image_notes", lambda *a, **k: "")

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )
    assert entry.problem_text == "系统功能如图1所示。"
    on_disk = (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8")
    assert on_disk == "系统功能如图1所示。"


def test_enrich_topic_annotations_prefer_text_over_vision(topic_root, pdf, monkeypatch):
    """文字标注优先（03）：pdf_figure_annotations 非空 → 写回标注段，不调视觉。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf)
    vision_calls: list[str] = []
    monkeypatch.setattr(
        topic_library,
        "pdf_figure_annotations",
        lambda *a, **k: "[图1 标注]\n-45° 门锁 60cm\n15°",
    )
    monkeypatch.setattr(
        topic_library,
        "pdf_image_notes",
        lambda *a, **k: vision_calls.append("x") or "[示意图1：视觉图注]",
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )

    assert entry.problem_text == "系统功能如图1所示。\n\n[图1 标注]\n-45° 门锁 60cm\n15°"
    assert vision_calls == []  # 文字层非空 → 视觉不被调


def test_enrich_topic_annotations_falls_back_to_vision_when_text_empty(
    topic_root, pdf, monkeypatch
):
    """文字层为空（扫描件 / 无文本层）→ 视觉兜底（现状路径）。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf)
    vision_calls: list[str] = []
    monkeypatch.setattr(topic_library, "pdf_figure_annotations", lambda *a, **k: "")
    monkeypatch.setattr(
        topic_library,
        "pdf_image_notes",
        lambda *a, **k: vision_calls.append("x") or "[示意图1：扫描页的完整布局描述]",
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )

    assert entry.problem_text == "系统功能如图1所示。\n\n[示意图1：扫描页的完整布局描述]"
    assert len(vision_calls) == 1


def test_enrich_topic_annotations_idempotent_on_figure_notes(topic_root, pdf, monkeypatch):
    """题面已含 [图N 标注 → 幂等跳过（03 幂等判定更新）。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf, "系统功能如图1所示。\n\n[图1 标注]\n60cm")
    calls: list[str] = []
    monkeypatch.setattr(
        topic_library, "pdf_figure_annotations", lambda *a, **k: calls.append("x") or "[图1 标注]"
    )
    monkeypatch.setattr(
        topic_library, "pdf_image_notes", lambda *a, **k: calls.append("x") or "[示意图]"
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )

    assert entry.problem_text == "系统功能如图1所示。\n\n[图1 标注]\n60cm"
    assert calls == []
    assert entry.problem_md == TOPIC_MD_FILENAME


def test_enrich_topic_image_notes_shared_pdf_locates_pages(topic_root, pdf, monkeypatch):
    """共享 PDF（真题汇总）：定位题面页 → 只在该页范围提取图注（别的题的
    [图N 标注] 不追尾——2024H 曾污染约 280 行）；页范围传给图注提取。"""
    from contest_generator import topic_library

    confirm_topics(
        topic_root,
        pdf,
        (
            TopicDraft(year="2026", number="C", problem_text="2026C 系统功能如图1所示。"),
            TopicDraft(year="2026", number="D", problem_text="2026D 系统功能如图2所示。"),
        ),
    )
    figure_pages: list[object] = []
    vision_calls: list[str] = []
    monkeypatch.setattr(topic_library, "locate_topic_pages", lambda *a, **k: (1, 3))
    monkeypatch.setattr(
        topic_library,
        "pdf_figure_annotations",
        lambda *a, **k: figure_pages.append(k.get("pages")) or "[图1 标注]\n60cm 40cm",
    )
    monkeypatch.setattr(
        topic_library,
        "pdf_image_notes",
        lambda *a, **k: vision_calls.append("x") or "[示意图1]",
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )

    assert entry.problem_text == "2026C 系统功能如图1所示。\n\n[图1 标注]\n60cm 40cm"
    assert figure_pages == [[1, 2]]  # 页范围（开区间右端 range 展开）传给文字标注
    assert vision_calls == []  # 文字层非空 → 视觉不调


def test_enrich_topic_image_notes_shared_pdf_vision_fallback_with_pages(
    topic_root, pdf, monkeypatch
):
    """共享 PDF 文字层为空（扫描件）→ 视觉兜底也带页范围（只识别本页图）。"""
    from contest_generator import topic_library

    confirm_topics(
        topic_root,
        pdf,
        (
            TopicDraft(year="2026", number="C", problem_text="2026C 系统功能如图1所示。"),
            TopicDraft(year="2026", number="D", problem_text="2026D 系统功能如图2所示。"),
        ),
    )
    vision_pages: list[object] = []
    monkeypatch.setattr(topic_library, "locate_topic_pages", lambda *a, **k: (1, 3))
    monkeypatch.setattr(topic_library, "pdf_figure_annotations", lambda *a, **k: "")
    monkeypatch.setattr(
        topic_library,
        "pdf_image_notes",
        lambda *a, **k: vision_pages.append(k.get("pages")) or "[示意图1：本页图的完整布局描述]",
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )

    assert entry.problem_text == "2026C 系统功能如图1所示。\n\n[示意图1：本页图的完整布局描述]"
    assert vision_pages == [[1, 2]]  # 视觉兜底同样限定页范围（range 展开）


def test_enrich_topic_image_notes_shared_pdf_skips_when_locate_fails(
    topic_root, pdf, monkeypatch
):
    """共享 PDF 定位失败（扫描件无文本层 / 题面不匹配）→ 原样返回，不跑
    图注提取——宁可没有图注，也不冒险全文档扫描。"""
    from contest_generator import topic_library

    confirm_topics(
        topic_root,
        pdf,
        (
            TopicDraft(year="2026", number="C", problem_text="2026C 系统功能如图1所示。"),
            TopicDraft(year="2026", number="D", problem_text="2026D 系统功能如图2所示。"),
        ),
    )
    calls: list[str] = []
    monkeypatch.setattr(topic_library, "locate_topic_pages", lambda *a, **k: None)
    monkeypatch.setattr(
        topic_library,
        "pdf_figure_annotations",
        lambda *a, **k: calls.append("x") or "[图1 标注]\n其它题的标注",
    )
    monkeypatch.setattr(
        topic_library,
        "pdf_image_notes",
        lambda *a, **k: calls.append("x") or "[示意图1]",
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )

    assert entry.problem_text == "2026C 系统功能如图1所示。"  # 原样，没追尾
    assert calls == []  # 一次图注提取都没跑


def test_enrich_topic_image_notes_skips_meaningless_vision_text(
    topic_root, pdf, monkeypatch
):
    """视觉兜底返回无实质内容（如「无实质内容」/ 过短描述）→ 视为失败，
    原样返回不写回——装饰图 / 空图的识别结果不入库。"""
    from contest_generator import topic_library

    _confirm_figure_topic(topic_root, pdf)
    monkeypatch.setattr(topic_library, "pdf_figure_annotations", lambda *a, **k: "")
    monkeypatch.setattr(
        topic_library, "pdf_image_notes", lambda *a, **k: "[示意图1：无实质内容]"
    )

    entry = topic_library.enrich_topic_image_notes(
        topic_root, KEY_2026C, vision_base_url="", vision_api_key="sk-v", vision_model=""
    )

    assert entry.problem_text == "系统功能如图1所示。"  # 原样，垃圾不入库


def test_resolve_number_corrupt_manifest_raises(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))
    (topic_root / KEY_2026C / MANIFEST_FILENAME).write_text(
        "{not json", encoding="utf-8"
    )

    with pytest.raises(TopicError, match="manifest"):
        resolve_number(topic_root, KEY_2026C)


def test_resolve_number_missing_problem_md_raises(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))
    (topic_root / KEY_2026C / TOPIC_MD_FILENAME).unlink()

    with pytest.raises(TopicError, match=TOPIC_MD_FILENAME):
        resolve_number(topic_root, KEY_2026C)


# ---------------------------------------------------------------------------
# 数据健康（工单 topic-library-ui/01）：附带程序悬空 + 原 PDF 缺失服务端实况
# ---------------------------------------------------------------------------


def test_topic_health_all_ok(topic_root, pdf, tmp_path):
    program = tmp_path / "2026C-src"
    program.mkdir()
    confirm_topics(
        topic_root, pdf, (DRAFTS[0],), program_dirs=[program], pdf_filename="真题.pdf"
    )

    health = topic_health(topic_root, resolve_number(topic_root, KEY_2026C))

    assert health.original_pdf_missing is False
    assert health.programs_missing == ()
    assert health.original_pdf_size == pdf.stat().st_size  # 体量随列表带出


def test_topic_health_missing_original_pdf(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],), pdf_filename="真题.pdf")
    (topic_root / KEY_2026C / "真题.pdf").unlink()

    health = topic_health(topic_root, resolve_number(topic_root, KEY_2026C))

    assert health.original_pdf_missing is True
    assert health.programs_missing == ()
    assert health.original_pdf_size == 0  # 缺失 = 0（详情弹窗显示「无法读取」）


def test_topic_health_missing_program_dirs(topic_root, pdf, tmp_path):
    """附带程序清单里的悬空引用（入库后目录被删）逐个列出；存在的目录不算。"""
    ghost = tmp_path / "幽灵程序"
    alive = tmp_path / "还在的程序"
    ghost.mkdir()
    alive.mkdir()
    confirm_topics(
        topic_root, pdf, (DRAFTS[0],), program_dirs=[ghost, alive]
    )
    shutil.rmtree(ghost)  # 模拟运行期腐坏：用户删了源目录

    health = topic_health(topic_root, resolve_number(topic_root, KEY_2026C))

    assert health.programs_missing == (str(ghost),)


def test_topic_health_mixed_programs_lists_only_dangling(topic_root, pdf, tmp_path):
    """多条程序引用：存在 / 悬空夹杂 → 只列悬空的（按 manifest 声明序）。"""
    a = tmp_path / "a_exists"
    b = tmp_path / "b_ghost"
    c = tmp_path / "c_ghost"
    for p in (a, b, c):
        p.mkdir()
    confirm_topics(topic_root, pdf, (DRAFTS[0],), program_dirs=[a, b, c])
    shutil.rmtree(b)
    shutil.rmtree(c)

    health = topic_health(topic_root, resolve_number(topic_root, KEY_2026C))

    assert health.programs_missing == (str(b), str(c))


def test_topic_health_no_original_pdf_declared_not_missing(topic_root):
    """原 PDF 字段为空（无声明）→ 不算缺失（没有就不查）。"""
    entry = TopicEntry(year="2026", number="C", problem_text="题面", original_pdf="")

    assert topic_health(topic_root, entry).original_pdf_missing is False


def test_topic_health_dangling_program_is_a_file_not_missing(topic_root, pdf, tmp_path):
    """声明路径存在但指向文件（非目录）→ 悬空（与确认入库 is_dir 判据一致）。"""
    program_path = tmp_path / "程序目录"
    program_path.mkdir()
    confirm_topics(topic_root, pdf, (DRAFTS[0],), program_dirs=[program_path])
    program_path.rmdir()
    program_path.write_text("x", encoding="utf-8")  # 同名文件顶替

    health = topic_health(topic_root, resolve_number(topic_root, KEY_2026C))

    assert health.programs_missing == (str(program_path),)


# ---------------------------------------------------------------------------
# 浏览列表 / 删除（工单 05）：list_topics 按编号排序、损坏 manifest 大声失败；
# delete_topic 条目目录移除、删除后编号解析报错
# ---------------------------------------------------------------------------


def test_list_topics_sorts_by_key(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))  # 2026C
    older = TopicDraft(year="2018", number="A", problem_text="2018A 题面")
    confirm_topics(topic_root, pdf, (older,))  # 乱序入库，列表按编号排

    entries = list_topics(topic_root)

    assert [e.key for e in entries] == ["2018A", KEY_2026C]
    assert entries[0].problem_text == older.problem_text


def test_list_topics_missing_root_returns_empty(topic_root):
    assert list_topics(topic_root) == []


def test_list_topics_ignores_stray_files(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))
    (topic_root / "notes.txt").write_text("随手笔记", encoding="utf-8")

    assert [e.key for e in list_topics(topic_root)] == [KEY_2026C]


def test_list_topics_corrupt_manifest_raises(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))
    (topic_root / KEY_2026C / MANIFEST_FILENAME).write_text(
        "{not json", encoding="utf-8"
    )

    # 损坏 manifest 大声失败，与模块库 / 参考库浏览同哲学，不静默跳过
    with pytest.raises(TopicError, match="manifest"):
        list_topics(topic_root)


def test_delete_topic_removes_entry_and_resolve_raises(topic_root, pdf):
    confirm_topics(topic_root, pdf, (DRAFTS[0],))

    delete_topic(topic_root, KEY_2026C)

    assert not (topic_root / KEY_2026C).exists()
    with pytest.raises(TopicError, match=KEY_2026C):
        resolve_number(topic_root, KEY_2026C)


def test_delete_topic_missing_raises(topic_root):
    with pytest.raises(TopicError, match=KEY_2026C):
        delete_topic(topic_root, KEY_2026C)


@pytest.mark.parametrize(
    "bad_key", ["../evil", "2026", "2026C1", "2026CC", "2026c", ""]
)
def test_delete_topic_rejects_bad_key(topic_root, bad_key):
    with pytest.raises(TopicError, match="编号"):
        delete_topic(topic_root, bad_key)


# ---------------------------------------------------------------------------
# 编辑（工单 topic-library-ui/02）：题面全文 / 附带程序 / 功能组一次事务修改，
# 身份字段（year/number/original_pdf/problem_md）不可改，校验全在落盘前
# ---------------------------------------------------------------------------


def _confirm_editable(topic_root, pdf, tmp_path):
    """入库一个带程序目录 + hint 组的 2026C（编辑测试母本）。"""
    program = tmp_path / "2026C-lock"
    program.mkdir()
    confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2026", number="C", problem_text="2026C 原题面"),),
        program_dirs=[program],
        pdf_filename="真题.pdf",
    )
    manifest_path = topic_root / KEY_2026C / MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["hint_module_groups"] = ["attitude-hold"]
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return program


def test_update_topic_edits_all_three_fields(topic_root, pdf, tmp_path):
    program = _confirm_editable(topic_root, pdf, tmp_path)
    new_program = tmp_path / "2026C-key-new"
    new_program.mkdir()

    entry = update_topic(
        topic_root,
        KEY_2026C,
        problem_text="2026C 新题面：数字钥匙……\n\n[图1 标注]\n60cm",
        programs=[str(new_program)],
        hint_module_groups=["gray-track", "attitude-hold"],
    )

    assert entry.key == KEY_2026C
    assert entry.problem_text == "2026C 新题面：数字钥匙……\n\n[图1 标注]\n60cm"
    assert entry.programs == (str(new_program),)
    assert entry.hint_module_groups == ("gray-track", "attitude-hold")
    # 磁盘实况：题面文件与 manifest 都更新
    assert (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(
        encoding="utf-8"
    ) == "2026C 新题面：数字钥匙……\n\n[图1 标注]\n60cm"
    manifest = json.loads(
        (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["programs"] == [str(new_program)]
    assert manifest["hint_module_groups"] == ["gray-track", "attitude-hold"]


def test_update_topic_keeps_identity_fields(topic_root, pdf, tmp_path):
    """身份不变量：year / number / original_pdf / problem_md 编辑后原样。"""
    _confirm_editable(topic_root, pdf, tmp_path)

    update_topic(
        topic_root, KEY_2026C, problem_text="新题面", programs=[], hint_module_groups=[]
    )

    manifest = json.loads(
        (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["year"] == "2026"
    assert manifest["number"] == "C"
    assert manifest["original_pdf"] == "真题.pdf"
    assert manifest["problem_md"] == TOPIC_MD_FILENAME


def test_update_topic_rejects_empty_problem_text_zero_write(topic_root, pdf, tmp_path):
    _confirm_editable(topic_root, pdf, tmp_path)
    before_text = (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8")
    before_manifest = (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")

    with pytest.raises(TopicError, match="题面不能为空"):
        update_topic(
            topic_root, KEY_2026C, problem_text="   ", programs=[], hint_module_groups=[]
        )

    # 校验失败：磁盘零变化
    assert (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8") == before_text
    assert (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8") == before_manifest


def test_update_topic_rejects_missing_program_dir_zero_write(topic_root, pdf, tmp_path):
    _confirm_editable(topic_root, pdf, tmp_path)
    before_manifest = (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")

    with pytest.raises(TopicError, match="程序目录不存在"):
        update_topic(
            topic_root,
            KEY_2026C,
            problem_text="新题面",
            programs=[str(tmp_path / "幽灵")],
            hint_module_groups=[],
        )

    assert (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8") == before_manifest
    assert (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8") == "2026C 原题面"


def test_update_topic_rejects_blank_program_dir(topic_root, pdf, tmp_path):
    _confirm_editable(topic_root, pdf, tmp_path)

    with pytest.raises(TopicError, match="不能为空"):
        update_topic(
            topic_root, KEY_2026C, problem_text="新题面", programs=["  "], hint_module_groups=[]
        )


def test_update_topic_rejects_blank_hint_group(topic_root, pdf, tmp_path):
    _confirm_editable(topic_root, pdf, tmp_path)

    with pytest.raises(TopicError, match="hint_module_groups"):
        update_topic(
            topic_root, KEY_2026C, problem_text="新题面", programs=[], hint_module_groups=["", "gray-track"]
        )


@pytest.mark.parametrize(
    "programs, hint, fragment",
    [
        ([123], [], "programs"),
        ([], [1], "hint_module_groups"),
    ],
)
def test_update_topic_rejects_non_string_elements(
    topic_root, pdf, tmp_path, programs, hint, fragment
):
    """非字符串元素 → TopicError（禁止静默强转——错误类型复用 TopicError，
    直调域层与 HTTP 断言语义一致）；磁盘零变化。"""
    _confirm_editable(topic_root, pdf, tmp_path)
    before_manifest = (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")

    with pytest.raises(TopicError, match=fragment):
        update_topic(
            topic_root, KEY_2026C, problem_text="新题面", programs=programs, hint_module_groups=hint
        )

    assert (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8") == before_manifest
    assert (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8") == "2026C 原题面"


def test_update_topic_restores_problem_text_on_write_failure(
    topic_root, pdf, tmp_path, monkeypatch
):
    """写盘中途失败（manifest 写失败）→ 题面恢复旧值、manifest 原值保留
    （对偶 update_reference 写入期清理契约）。"""
    import contest_generator.topic_library as topic_library

    _confirm_editable(topic_root, pdf, tmp_path)
    before_manifest = (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")
    monkeypatch.setattr(
        topic_library, "write_json", lambda *a, **k: (_ for _ in ()).throw(OSError("磁盘满"))
    )

    with pytest.raises(OSError, match="磁盘满"):
        update_topic(
            topic_root, KEY_2026C, problem_text="新题面", programs=[], hint_module_groups=[]
        )

    assert (topic_root / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8") == "2026C 原题面"
    assert (topic_root / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8") == before_manifest


def test_update_topic_missing_entry_raises(topic_root):
    with pytest.raises(TopicError, match=KEY_2026C):
        update_topic(
            topic_root, KEY_2026C, problem_text="新题面", programs=[], hint_module_groups=[]
        )


@pytest.mark.parametrize("bad_key", ["../evil", "2026", "2026C1", "2026c"])
def test_update_topic_rejects_bad_key(topic_root, bad_key):
    with pytest.raises(TopicError, match="编号"):
        update_topic(
            topic_root, bad_key, problem_text="新题面", programs=[], hint_module_groups=[]
        )


def test_update_topic_commits_autocommit(topic_root, pdf, tmp_path, monkeypatch):
    """写库成功后自动 git 提交（提交信息含条目编号）。"""
    import contest_generator.topic_library as topic_library

    _confirm_editable(topic_root, pdf, tmp_path)
    messages: list[str] = []
    monkeypatch.setattr(topic_library, "commit_after_write", lambda root, msg: messages.append(msg))

    update_topic(
        topic_root, KEY_2026C, problem_text="新题面", programs=[], hint_module_groups=[]
    )

    assert messages == [f"lib: update topic {KEY_2026C}"]


def test_update_topic_can_remove_all_programs(topic_root, pdf, tmp_path):
    """附带程序清单可清空（悬空引用 / 录错 → 编辑弹窗移除）。"""
    _confirm_editable(topic_root, pdf, tmp_path)

    entry = update_topic(
        topic_root, KEY_2026C, problem_text="新题面", programs=[], hint_module_groups=[]
    )

    assert entry.programs == ()
    assert entry.hint_module_groups == ()


# ---------------------------------------------------------------------------
# HTTP 层：拆条上传 / 确认入库（multipart）/ 编号解析
# ---------------------------------------------------------------------------


@pytest.fixture
def topic_context(tmp_path):
    """已配置的假上下文：假模块库 + 赛题库根（模块库同级 topics/）+ 假 LLM，
    配置文件路径在 tmp 下。"""
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    holder = {"llm": FakeTopicLLM(split=DRAFTS)}
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=lambda config: holder["llm"],
    )
    return ctx, holder, tmp_path / "topics"


def _client(context):
    return TestClient(create_app(context))


def _confirm_payload(**overrides):
    payload = {
        "entries": [
            {"year": d.year, "number": d.number, "problem_text": d.problem_text}
            for d in DRAFTS
        ],
        "program_dirs": [],
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_topics_split_endpoint_returns_drafts(topic_context, tmp_path):
    ctx, holder, _ = topic_context
    holder["llm"] = FakeTopicLLM(split=DRAFTS)
    pdf_path = make_sample_pdf(tmp_path / "真题.pdf", "2026 contest topics A B C")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/split",
                files={"upload": ("2026真题.pdf", file, "application/pdf")},
            )

    assert response.status_code == 200
    assert [t["key"] for t in response.json()["topics"]] == [KEY_2026C, KEY_2026D]
    assert response.json()["topics"][0]["problem_text"] == DRAFTS[0].problem_text
    # 新建默认 control（工单 topics-control-2023-2025/01：控制题专项定位，
    # 校对表单默认选中；confirm 提交值以用户改动为准）
    assert response.json()["topics"][0]["category"] == "control"
    assert holder["llm"].split_calls  # 拆条确实调了 LLM


def test_topics_split_endpoint_llm_failure_returns_502(topic_context, tmp_path):
    ctx, holder, _ = topic_context
    holder["llm"] = FakeTopicLLM()

    def _raise(text: str) -> tuple[TopicDraft, ...]:
        raise LLMError("服务不可用")

    holder["llm"].topic_split_topics = _raise
    pdf_path = make_sample_pdf(tmp_path / "真题.pdf", "2026 contest topics")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/split",
                files={"upload": ("真题.pdf", file, "application/pdf")},
            )

    assert response.status_code == 502


def _long_topics_text() -> str:
    """超长假真题全文（> 20K 路由阈值）：单年份两题，题面填充长正文。"""
    return (
        "2025年全国大学生电子设计竞赛\n"
        "（A 题）2025A 题面\n"
        + "……正文填充……" * 3000
        + "\nB题：2025B 题面\n"
        + "……正文填充……" * 3000
        + "\n"
    )


def test_topics_split_endpoint_long_text_uses_deterministic_split(
    topic_context, tmp_path
):
    ctx, holder, _ = topic_context
    text = _long_topics_text()
    assert len(text) > TOPIC_SPLIT_LLM_CHAR_CAP  # 超长判定阈值：超过即走确定性分块
    pdf_path = tmp_path / "真题.txt"
    pdf_path.write_text(text, encoding="utf-8")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/split",
                files={"upload": ("真题.txt", file, "text/plain")},
            )

    assert response.status_code == 200
    topics = response.json()["topics"]
    assert [t["key"] for t in topics] == ["2025A", "2025B"]
    assert topics[0]["problem_text"].startswith("（A 题）")
    assert not holder["llm"].split_calls  # 超长走确定性分块，不调 LLM


@pytest.mark.parametrize(
    "n_chars", [TOPIC_SPLIT_LLM_CHAR_CAP, TOPIC_SPLIT_LLM_CHAR_CAP + 1]
)
def test_topics_split_endpoint_routes_at_char_cap(topic_context, tmp_path, n_chars):
    """路由阈值（TOPIC_SPLIT_LLM_CHAR_CAP）：≤ 阈值单次调 LLM（全量直传），
    超过走确定性分块（格式不匹配大声失败）。"""
    ctx, holder, _ = topic_context
    text = "x" * n_chars
    pdf_path = tmp_path / "真题.txt"
    pdf_path.write_text(text, encoding="utf-8")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/split",
                files={"upload": ("真题.txt", file, "text/plain")},
            )

    if n_chars == TOPIC_SPLIT_LLM_CHAR_CAP:
        assert response.status_code == 200
        assert holder["llm"].split_calls == [text]
    else:
        assert response.status_code == 400  # 无年份章节 → 确定性分块大声失败
        assert not holder["llm"].split_calls


def test_topics_confirm_endpoint_creates_entries_and_resolves(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    pdf_path = tmp_path / "真题.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/confirm",
                files={"pdf": ("2026真题.pdf", file, "application/pdf")},
                data={"payload": _confirm_payload()},
            )
        assert response.status_code == 200
        assert [t["key"] for t in response.json()["topics"]] == [
            KEY_2026C,
            KEY_2026D,
        ]

        entry = client.get(f"/api/topics/{KEY_2026C}")

    assert entry.status_code == 200
    body = entry.json()
    assert body["problem_text"] == DRAFTS[0].problem_text
    assert body["original_pdf"] == "2026真题.pdf"
    assert (topics_dir / KEY_2026C / "2026真题.pdf").is_file()


def test_topics_confirm_endpoint_rejects_existing_entry(topic_context, tmp_path):
    ctx, _, _ = topic_context
    pdf_path = tmp_path / "真题.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            assert client.post(
                "/api/topics/confirm",
                files={"pdf": ("真题.pdf", file, "application/pdf")},
                data={"payload": _confirm_payload()},
            ).status_code == 200
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/confirm",
                files={"pdf": ("真题.pdf", file, "application/pdf")},
                data={"payload": _confirm_payload()},
            )

    assert response.status_code == 400
    assert KEY_2026C in response.json()["detail"]


def test_parse_confirm_entries_rejects_invalid_key_format_inline():
    """用户提交的畸形编号在解析层就地拦截（不再等 confirm_topics 第二跳）。"""
    with pytest.raises(TopicError, match="格式非法"):
        parse_confirm_entries(
            {
                "entries": [
                    {"year": "2026", "number": "c", "problem_text": "题面"}
                ]
            }
        )
    with pytest.raises(TopicError, match="格式非法"):
        parse_confirm_entries(
            {
                "entries": [
                    {"year": "2026", "number": "AB", "problem_text": "题面"}
                ]
            }
        )


def test_parse_confirm_entries_rejects_duplicate_keys_inline():
    """同批重复编号在解析层就地拦截（与拆条解析同标准）。"""
    with pytest.raises(TopicError, match="重复"):
        parse_confirm_entries(
            {
                "entries": [
                    {"year": "2026", "number": "C", "problem_text": "题面一"},
                    {"year": "2026", "number": "C", "problem_text": "题面二"},
                ]
            }
        )


def test_topics_confirm_endpoint_rejects_bad_payload(topic_context, tmp_path):
    ctx, _, _ = topic_context
    pdf_path = tmp_path / "真题.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/confirm",
                files={"pdf": ("真题.pdf", file, "application/pdf")},
                data={"payload": json.dumps({"entries": "not-a-list"})},
            )

    assert response.status_code == 400
    assert "entries" in response.json()["detail"]


def test_topic_get_missing_returns_400(topic_context):
    ctx, _, _ = topic_context
    with _client(ctx) as client:
        response = client.get(f"/api/topics/{KEY_2026C}")

    assert response.status_code == 400
    assert KEY_2026C in response.json()["detail"]


def test_topic_get_rejects_bad_key_400(topic_context):
    ctx, _, _ = topic_context
    with _client(ctx) as client:
        response = client.get("/api/topics/2026")  # 缺题号

    assert response.status_code == 400
    assert "编号" in response.json()["detail"]


def test_topics_extract_number_endpoint(topic_context):
    ctx, holder, _ = topic_context
    holder["llm"] = FakeTopicLLM(number="2026C")
    with _client(ctx) as client:
        response = client.post(
            "/api/topics/extract-number", json={"text": "粘贴的 2026C 题面……"}
        )

    assert response.status_code == 200
    assert response.json()["key"] == "2026C"


# ---------------------------------------------------------------------------
# 浏览列表 / 删除路由（工单 05）：GET /api/topics（浏览列表，一次性算好不
# N 次前端调用）、DELETE /api/topics/{key}（查无此条明确报错）
# ---------------------------------------------------------------------------


def _confirm_draft(ctx, topics_dir, tmp_path, draft) -> None:
    pdf_path = tmp_path / "真题.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    confirm_topics(topics_dir, pdf_path, (draft,))


def test_topics_list_endpoint_sorted(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    older = TopicDraft(year="2018", number="A", problem_text="2018A 题面")
    _confirm_draft(ctx, topics_dir, tmp_path, older)
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])  # 2026C

    with _client(ctx) as client:
        response = client.get("/api/topics")

    assert response.status_code == 200
    body = response.json()
    assert [t["key"] for t in body] == ["2018A", KEY_2026C]
    by_key = {t["key"]: t for t in body}
    assert by_key[KEY_2026C]["problem_text"] == DRAFTS[0].problem_text


def test_topics_list_endpoint_includes_health(topic_context, tmp_path):
    """浏览列表每条带 health 实况（工单 topic-library-ui/01）：原 PDF 缺失 /
    程序目录悬空在列表端点一次算好，前端不按条回查。"""
    ctx, _, topics_dir = topic_context
    ghost = tmp_path / "幽灵"
    ghost.mkdir()
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])  # 2026C 无程序
    draft_with_program = TopicDraft(
        year="2026", number="D", problem_text="2026D 题面"
    )
    confirm_topics(topics_dir, tmp_path / "真题.pdf", (draft_with_program,),
                   program_dirs=[ghost])
    shutil.rmtree(ghost)  # 运行期腐坏：程序目录被删

    with _client(ctx) as client:
        response = client.get("/api/topics")

    assert response.status_code == 200
    by_key = {t["key"]: t for t in response.json()}
    assert by_key[KEY_2026C]["health"] == {
        "original_pdf_missing": False,
        "programs_missing": [],
        "original_pdf_size": (tmp_path / "真题.pdf").stat().st_size,
    }
    assert by_key["2026D"]["health"] == {
        "original_pdf_missing": False,
        "programs_missing": [str(ghost)],
        "original_pdf_size": (tmp_path / "真题.pdf").stat().st_size,
    }


def test_topic_get_endpoint_has_no_health(topic_context, tmp_path):
    """单条取题面（生成入口素材）不带 health——字段现状保持，不扩大形状。"""
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])

    with _client(ctx) as client:
        response = client.get(f"/api/topics/{KEY_2026C}")

    assert response.status_code == 200
    assert "health" not in response.json()


def test_topics_list_endpoint_corrupt_manifest_returns_400(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])
    (topics_dir / KEY_2026C / MANIFEST_FILENAME).write_text(
        "{bad", encoding="utf-8"
    )

    with _client(ctx) as client:
        response = client.get("/api/topics")

    assert response.status_code == 400
    assert "manifest" in response.json()["detail"]


def test_topics_delete_endpoint_removes_entry(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])

    with _client(ctx) as client:
        response = client.delete(f"/api/topics/{KEY_2026C}")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert not (topics_dir / KEY_2026C).exists()  # 条目目录整体移除
    with _client(ctx) as client:
        missing = client.get(f"/api/topics/{KEY_2026C}")
    assert missing.status_code == 400  # 删除后编号解析明确报错
    assert KEY_2026C in missing.json()["detail"]


def test_topics_delete_missing_returns_400(topic_context):
    ctx, _, _ = topic_context
    with _client(ctx) as client:
        response = client.delete(f"/api/topics/{KEY_2026C}")

    assert response.status_code == 400
    assert KEY_2026C in response.json()["detail"]


def test_topics_delete_bad_key_returns_400(topic_context):
    ctx, _, _ = topic_context
    with _client(ctx) as client:
        response = client.delete("/api/topics/2026")  # 缺题号

    assert response.status_code == 400
    assert "编号" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 编辑路由（工单 topic-library-ui/02）：PUT /api/topics/{key} 三字段全量替换
# ---------------------------------------------------------------------------


def test_topics_put_endpoint_updates_entry(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])
    program = tmp_path / "锁程序"
    program.mkdir()

    with _client(ctx) as client:
        response = client.put(
            f"/api/topics/{KEY_2026C}",
            json={
                "problem_text": "2026C 编辑后题面",
                "programs": [str(program)],
                "hint_module_groups": ["gray-track"],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["key"] == KEY_2026C
    assert body["problem_text"] == "2026C 编辑后题面"
    assert body["programs"] == [str(program)]
    assert body["hint_module_groups"] == ["gray-track"]
    # 落盘实况
    assert (topics_dir / KEY_2026C / TOPIC_MD_FILENAME).read_text(encoding="utf-8") == "2026C 编辑后题面"
    manifest = json.loads(
        (topics_dir / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["programs"] == [str(program)]
    assert manifest["hint_module_groups"] == ["gray-track"]


def test_topics_put_endpoint_ignores_identity_keys(topic_context, tmp_path):
    """body 里的身份键（year / number / original_pdf）一概忽略——不可改。"""
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])

    with _client(ctx) as client:
        response = client.put(
            f"/api/topics/{KEY_2026C}",
            json={
                "problem_text": "新题面",
                "programs": [],
                "hint_module_groups": [],
                "year": "1999",
                "number": "Z",
                "original_pdf": "偷换.pdf",
            },
        )

    assert response.status_code == 200
    assert response.json()["year"] == "2026"
    assert response.json()["number"] == "C"
    assert response.json()["original_pdf"] == "topic.pdf"
    assert not (topics_dir / KEY_2026C / "偷换.pdf").exists()


@pytest.mark.parametrize(
    "body, detail_fragment",
    [
        ({"programs": [], "hint_module_groups": []}, "problem_text"),
        ({"problem_text": "题面", "hint_module_groups": []}, "programs"),
        ({"problem_text": "题面", "programs": []}, "hint_module_groups"),
        ({"problem_text": "题面", "programs": "not-a-list", "hint_module_groups": []}, "programs"),
        ({"problem_text": "题面", "programs": [], "hint_module_groups": [1]}, "hint_module_groups"),
    ],
)
def test_topics_put_endpoint_rejects_bad_shapes(topic_context, tmp_path, body, detail_fragment):
    """形状校验（薄壳层）：缺字段 / 非字符串列表 → 400 中文。"""
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])

    with _client(ctx) as client:
        response = client.put(f"/api/topics/{KEY_2026C}", json=body)

    assert response.status_code == 400
    assert detail_fragment in response.json()["detail"]


def test_topics_put_endpoint_rejects_missing_program_dir(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])

    with _client(ctx) as client:
        response = client.put(
            f"/api/topics/{KEY_2026C}",
            json={
                "problem_text": "新题面",
                "programs": [str(tmp_path / "幽灵")],
                "hint_module_groups": [],
            },
        )

    assert response.status_code == 400
    assert "程序目录不存在" in response.json()["detail"]


def test_topics_put_endpoint_missing_entry_returns_400(topic_context):
    ctx, _, _ = topic_context
    with _client(ctx) as client:
        response = client.put(
            f"/api/topics/{KEY_2026C}",
            json={"problem_text": "题面", "programs": [], "hint_module_groups": []},
        )

    assert response.status_code == 400
    assert KEY_2026C in response.json()["detail"]


# ---------------------------------------------------------------------------
# 取题面页图（工单 topic-pdf-viewer/01）：原题 PDF 题面页渲染展示
# ---------------------------------------------------------------------------


def _confirm_pdf_topic(topics_dir, tmp_path, *, problem_text, pdf_text):
    """建条目：可渲染单页 PDF（ASCII 文本层）+ 题面文本与 PDF 文本层匹配。

    make_sample_pdf 只支持 ASCII 文本层，故题面文本用 ASCII——页定位按
    「去空白前 20 字符」匹配文本层，与中文题面行为一致。
    """
    pdf_path = make_sample_pdf(tmp_path / "真题.pdf", pdf_text)
    confirm_topics(
        topics_dir,
        pdf_path,
        (
            TopicDraft(
                year="2026", number="C", problem_text=problem_text
            ),
        ),
    )


def test_topics_pages_endpoint_renders_topic_pages(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    _confirm_pdf_topic(
        topics_dir,
        tmp_path,
        problem_text="2026C design task: delivery car",
        pdf_text="2026C design task: delivery car in hospital",
    )

    with _client(ctx) as client:
        response = client.get(f"/api/topics/{KEY_2026C}/pages")

    assert response.status_code == 200
    body = response.json()
    assert body["key"] == KEY_2026C
    assert len(body["pages"]) == 1  # 单页 PDF：命中页 1，范围右端页 2 不存在被跳过
    page = body["pages"][0]
    assert page["page_no"] == 1
    assert page["data_url"].startswith("data:image/png;base64,")
    import base64

    png = base64.b64decode(page["data_url"].split(",", 1)[1])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG 魔数（真实渲染产物）


def test_topics_pages_endpoint_locate_failure_returns_400(topic_context, tmp_path):
    """题面文本在 PDF 文本层找不到（扫描件 / 不匹配）→ 400 明确报错。"""
    ctx, _, topics_dir = topic_context
    _confirm_pdf_topic(
        topics_dir,
        tmp_path,
        problem_text="2026C 题面：数字钥匙锁",
        pdf_text="something else entirely",
    )

    with _client(ctx) as client:
        response = client.get(f"/api/topics/{KEY_2026C}/pages")

    assert response.status_code == 400
    assert "定位" in response.json()["detail"]


def test_topics_pages_endpoint_missing_pdf_returns_400(topic_context, tmp_path):
    """条目 manifest 记了原 PDF 但文件缺失 → 400 明确报错。"""
    ctx, _, topics_dir = topic_context
    _confirm_pdf_topic(
        topics_dir,
        tmp_path,
        problem_text="2026C design task",
        pdf_text="2026C design task",
    )
    (topics_dir / KEY_2026C / "topic.pdf").unlink()

    with _client(ctx) as client:
        response = client.get(f"/api/topics/{KEY_2026C}/pages")

    assert response.status_code == 400
    assert "不存在" in response.json()["detail"]


def test_topics_pages_endpoint_render_failure_returns_400(
    topic_context, tmp_path, monkeypatch
):
    """渲染全失败（缺 PyMuPDF / PDF 损坏）→ 400 明确报错，不返回空列表。"""
    ctx, _, topics_dir = topic_context
    _confirm_pdf_topic(
        topics_dir,
        tmp_path,
        problem_text="2026C design task",
        pdf_text="2026C design task",
    )
    import contest_generator.webapp as webapp

    monkeypatch.setattr(webapp, "render_page_png", lambda *a, **k: None)

    with _client(ctx) as client:
        response = client.get(f"/api/topics/{KEY_2026C}/pages")

    assert response.status_code == 400
    assert "渲染" in response.json()["detail"]


def test_topics_pages_endpoint_unknown_key_returns_400(topic_context):
    """查无此条：与取题面同一编号解析契约（明确报错、不猜测编造）。"""
    ctx, _, _ = topic_context
    with _client(ctx) as client:
        response = client.get(f"/api/topics/{KEY_2026C}/pages")

    assert response.status_code == 400
    assert KEY_2026C in response.json()["detail"]


# ---------------------------------------------------------------------------
# 取题面页图（工单 topic-pdf-viewer/02）：多页题面完整页范围（页脚总页数扩展）
# ---------------------------------------------------------------------------


def test_locate_topic_pages_full_extends_by_footer_total(tmp_path):
    """页脚总页数扩展：真题汇总 PDF 页脚「F - 1 / 4」→ 题面共 4 页，范围
    精确覆盖，不含下一页 G 题。"""
    pdf = make_multi_page_pdf(
        tmp_path / "真题.pdf",
        [
            ("F - 1 / 4", "2021F design task page one"),
            ("F - 2 / 4", "figure page"),
            ("F - 3 / 4", "requirements page three"),
            ("F - 4 / 4", "scoring page four"),
            ("G - 1 / 4", "next topic G page one"),
        ],
    )

    located = locate_topic_pages_full(pdf, "2021F design task page one")

    assert located == (1, 5)


def test_locate_topic_pages_full_normalizes_from_non_first_page(tmp_path):
    """k 归一：定位命中题面非首页（页脚 k=2）→ 反推回题面首页，范围不含
    下一题（评审提示：忽略 k 会把下一题卷进范围）。"""
    pdf = make_multi_page_pdf(
        tmp_path / "真题.pdf",
        [
            ("F - 1 / 4", "intro page"),
            ("F - 2 / 4", "layout figure"),
            ("F - 3 / 4", "requirements page three"),
            ("F - 4 / 4", "scoring page four"),
            ("G - 1 / 4", "next topic G page one"),
        ],
    )

    # 题面独特文本只出现在第 2 页 → 定位落在 (2, 4)，k=2 反推回 (1, 5)
    located = locate_topic_pages_full(pdf, "layout figure")

    assert located == (1, 5)


def test_locate_topic_pages_full_falls_back_without_footer(tmp_path):
    """无页脚（单题 PDF / 测试假件）→ 回退既有 span（命中页起 2 页）。"""
    pdf = make_multi_page_pdf(
        tmp_path / "真题.pdf",
        [
            ("", "2026C design task page one"),
            ("", "2026C design task page two"),
        ],
    )

    located = locate_topic_pages_full(pdf, "2026C design task page one")

    assert located == (1, 3)


def test_topics_pages_endpoint_renders_all_topic_pages(topic_context, tmp_path):
    """端点：多页题面（页脚总页数扩展）→ 全部页图，页码 1-4 完整。"""
    ctx, _, topics_dir = topic_context
    pdf = make_multi_page_pdf(
        tmp_path / "真题.pdf",
        [
            ("F - 1 / 4", "2021F design task page one"),
            ("F - 2 / 4", "figure page"),
            ("F - 3 / 4", "requirements page three"),
            ("F - 4 / 4", "scoring page four"),
        ],
    )
    confirm_topics(
        topics_dir,
        pdf,
        (TopicDraft(year="2021", number="F", problem_text="2021F design task page one"),),
    )

    with _client(ctx) as client:
        response = client.get("/api/topics/2021F/pages")

    assert response.status_code == 200
    body = response.json()
    assert [p["page_no"] for p in body["pages"]] == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# 真库不变量：赛题题面无跨题污染（修订前置排查修复，防拆条串页回退）
# ---------------------------------------------------------------------------

TOPICS_ROOT = Path(__file__).resolve().parents[1] / "library" / "topics"

# 跨题污染黑名单：2017-2025 真题汇总 PDF 拆条串页时混入的其它题目特征词。
# 本库 7 个赛题（2018C/2019A/2020C/2021F/2022C/2022H/2024H/2026C）无一
# 涉及这些词，命中即红；新增赛题入库若真用到（如将来收录声源定位题），
# 需人工更新词表。2023-09-01 人工更新：删除「激光笔」——2023E（运动目标
# 控制与自动追踪系统）/ 2023G（空地协同智能消防系统）题面合法大量使用
# 红色/绿色激光笔，黑名单与合法题面冲突。2026-09-02 人工更新：删除
# 「野生动物」——2025H（野生动物巡查系统）题名与题面正词，黑名单与合法
# 题面冲突。
FOREIGN_TOPIC_MARKERS = (
    "播撒作业",
    "用电器分析",
    "线路故障",
    "声源定位跟踪",
    "总谐波失真",
    "目标板和背景板",
    "飞行器起降点",
)

# 乱码签名（2024H 编码事故防回退）：GBK 误读 UTF-8 的高频产物——"锛"（（）、
# "銆"（。）、"鐨"（的）、"鏄"（是）、"鑷"（自）等。正常中文题面不会出现
# 这些生僻字；出现即文件被双重编码（UTF-8 字节按 GBK 误解码后重编码）。
MOJIBAKE_SIGNATURES = ("锛", "銆", "鐨", "鏄", "鑷", "閬", "涓€")


def test_real_topic_files_free_of_cross_topic_pollution():
    """真库不变量：每份 topic.md 不得含其它题目的特征词（拆条串页防回退），
    也不得含乱码签名（编码事故防回退）。

    历史：2024H（78 行真题面后混入约 280 行声源定位/无人机播撒/用电器分析
    等串页内容）、2021F（420 行中约 300 行垃圾）、2022C、2022H 均被同一本
    真题汇总 PDF 串页污染——推荐 AI 读到的题面混入大量无关题目要求，推荐
    质量失真（2024H 需要直线行驶却未推荐陀螺仪即典型受害场景）。已人工
    清洗，本测试锁定防回退。清洗过程曾发生编码事故（PowerShell 按 GBK
    读 UTF-8 再写回 = 双重编码乱码），签名词同时防该类回退。
    """
    assert TOPICS_ROOT.is_dir(), f"真库缺失：{TOPICS_ROOT}"
    topics = [
        p for p in TOPICS_ROOT.iterdir() if (p / TOPIC_MD_FILENAME).is_file()
    ]
    assert topics, "真库没有任何赛题条目"
    foreign: list[str] = []
    for topic in topics:
        text = (topic / TOPIC_MD_FILENAME).read_text(encoding="utf-8")
        for marker in FOREIGN_TOPIC_MARKERS:
            if marker in text:
                foreign.append(f"{topic.name}: 跨题污染 {marker}")
        for sig in MOJIBAKE_SIGNATURES:
            if sig in text:
                foreign.append(f"{topic.name}: 疑似乱码 {sig}")
    assert not foreign, "赛题题面异常：\n" + "\n".join(foreign)


def test_real_topic_library_all_entries_have_category():
    """真库不变量：全部赛题条目 category 非空且 ∈ 词表（补标后锁定防回退，
    工单 topics-control-2023-2025/02）。

    历史：15 条老条目分类补标（2018C-2024H 控制题 + 2026D/E/H 控制题、
    2026A/B/C/F/G 其他题）；拆条新建默认 control。任何条目 category 空串
    = 新题入库漏标 / 补标回退；词表外 = 元数据损坏（_load_entry 已拒，兜底）。
    """
    assert TOPICS_ROOT.is_dir(), f"真库缺失：{TOPICS_ROOT}"
    entries = list_topics(TOPICS_ROOT)
    assert entries, "真库没有任何赛题条目"
    unmarked = [entry.key for entry in entries if not entry.category]
    assert not unmarked, (
        f"存在未标记 category 的条目（{len(unmarked)} 条）：{unmarked}"
    )
    invalid = [
        entry.key
        for entry in entries
        if entry.category and entry.category not in TOPIC_CATEGORIES
    ]
    assert not invalid, f"category 词表外的条目：{invalid}"


# ---------------------------------------------------------------------------
# 渲染视觉优先（工单 topic-vision-render/02）：三级降级链
# ---------------------------------------------------------------------------


def test_enrich_prefers_render_vision_over_text_annotations(
    topic_root, pdf, monkeypatch
):
    """渲染视觉优先：pdf_page_render_notes 非空 → 写回，不调文字标注 / 内嵌图视觉。"""
    import contest_generator.topic_library as topic_library

    _confirm_figure_topic(topic_root, pdf)
    calls: list[str] = []
    monkeypatch.setattr(
        topic_library,
        "pdf_page_render_notes",
        lambda *a, **k: calls.append("render") or "[图1 标注：走廊 60cm 红实线走向]",
    )
    monkeypatch.setattr(
        topic_library,
        "pdf_figure_annotations",
        lambda *a, **k: calls.append("annotations") or "[图1 标注]\n60cm",
    )
    monkeypatch.setattr(
        topic_library, "pdf_image_notes", lambda *a, **k: calls.append("vision") or "[示意图]"
    )
    monkeypatch.setattr(topic_library, "commit_after_write", lambda *a, **k: None)

    entry = topic_library.enrich_topic_image_notes(
        topic_root,
        KEY_2026C,
        vision_base_url="",
        vision_api_key="sk",
        vision_model="m",
    )
    assert calls == ["render"]  # 只走第一级
    assert "[图1 标注：走廊 60cm 红实线走向]" in entry.problem_text
    assert "[图1 标注]\n60cm" not in entry.problem_text  # 文字标注未参与


def test_enrich_falls_back_to_text_annotations_when_render_empty(
    topic_root, pdf, monkeypatch
):
    """渲染空（未配置 / 渲染不可用）→ 文字标注兜底（既有路径语义不变）。"""
    import contest_generator.topic_library as topic_library

    _confirm_figure_topic(topic_root, pdf)
    calls: list[str] = []
    monkeypatch.setattr(topic_library, "pdf_page_render_notes", lambda *a, **k: "")
    monkeypatch.setattr(
        topic_library,
        "pdf_figure_annotations",
        lambda *a, **k: calls.append("annotations") or "[图1 标注]\n60cm",
    )
    monkeypatch.setattr(
        topic_library, "pdf_image_notes", lambda *a, **k: calls.append("vision") or "[示意图]"
    )
    monkeypatch.setattr(topic_library, "commit_after_write", lambda *a, **k: None)

    entry = topic_library.enrich_topic_image_notes(
        topic_root,
        KEY_2026C,
        vision_base_url="",
        vision_api_key="sk",
        vision_model="m",
    )
    assert calls == ["annotations"]
    assert "[图1 标注]\n60cm" in entry.problem_text


def test_enrich_all_three_levels_empty_returns_unchanged(topic_root, pdf, monkeypatch):
    """三级全空 → 原样返回，绝不写回。"""
    import contest_generator.topic_library as topic_library

    _confirm_figure_topic(topic_root, pdf)
    monkeypatch.setattr(topic_library, "pdf_page_render_notes", lambda *a, **k: "")
    monkeypatch.setattr(topic_library, "pdf_figure_annotations", lambda *a, **k: "")
    monkeypatch.setattr(topic_library, "pdf_image_notes", lambda *a, **k: "")

    entry = topic_library.enrich_topic_image_notes(
        topic_root,
        KEY_2026C,
        vision_base_url="",
        vision_api_key="",
        vision_model="",
    )
    assert "[图" not in entry.problem_text
    assert "[示意图" not in entry.problem_text


def test_enrich_skips_meaningless_render_vision_text(topic_root, pdf, monkeypatch):
    """渲染视觉段无实质内容（[图N 标注：无实质内容]）→ 不写回（工单 02 守卫）。"""
    import contest_generator.topic_library as topic_library

    _confirm_figure_topic(topic_root, pdf)
    monkeypatch.setattr(
        topic_library,
        "pdf_page_render_notes",
        lambda *a, **k: "[图1 标注：无实质内容]",
    )
    entry = topic_library.enrich_topic_image_notes(
        topic_root,
        KEY_2026C,
        vision_base_url="",
        vision_api_key="sk",
        vision_model="m",
    )
    assert "[图" not in entry.problem_text  # 无实质 → 原样返回
    assert entry.problem_text == "系统功能如图1所示。"


# ---------------------------------------------------------------------------
# 分类标记（工单 topics-control-2023-2025/01）：词表 / 校验 / manifest 读写 /
# update / confirm / webapp PUT+confirm+词表端点
# ---------------------------------------------------------------------------


def test_validate_topic_category_accepts_vocab_and_empty():
    """词表三态：control / other / 空串（未标记）全部合法。"""
    from contest_generator.topic_library import (
        validate_topic_category,
    )

    validate_topic_category("control")
    validate_topic_category("other")
    validate_topic_category("")


def test_validate_topic_category_rejects_unknown():
    """词表外分类大声失败（照 validate_topic_type 同款严格）。"""
    from contest_generator.topic_library import (
        TOPIC_CATEGORIES,
        TopicError,
        validate_topic_category,
    )

    assert TOPIC_CATEGORIES == ("control", "other")
    with pytest.raises(TopicError, match="非法分类"):
        validate_topic_category("mystery")
    with pytest.raises(TopicError, match="control、other"):
        validate_topic_category("mystery")


def test_confirm_topics_writes_category_to_manifest(topic_root, pdf):
    """confirm_topics 带 category → manifest 落盘「category」字段 + 回读。"""
    (entry,) = confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2023", number="E", problem_text="2023E 题面", category="control"),),
    )
    assert entry.category == "control"
    manifest = json.loads(
        (topic_root / "2023E" / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["category"] == "control"
    assert resolve_number(topic_root, "2023E").category == "control"


def test_confirm_topics_category_defaults_empty(topic_root, pdf):
    """不带 category = 未标记（""）——既有确认流程行为不变。"""
    confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2023", number="E", problem_text="2023E 题面"),),
    )
    manifest = json.loads(
        (topic_root / "2023E" / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["category"] == ""
    assert resolve_number(topic_root, "2023E").category == ""


def test_parse_confirm_entries_reads_category():
    """确认解析（工单 topics-control-2023-2025/01）：category 缺省 ""、合法值透传。"""
    (draft,) = parse_confirm_entries(
        {
            "entries": [
                {"year": "2026", "number": "C", "problem_text": "题面", "category": "other"}
            ]
        }
    )
    assert draft.category == "other"
    (draft2,) = parse_confirm_entries(
        {
            "entries": [
                {"year": "2026", "number": "C", "problem_text": "题面"}
            ]
        }
    )
    assert draft2.category == ""


def test_parse_confirm_entries_rejects_bad_category():
    """词表外分类 = 用户提交值非法，解析层就地拒绝（与编号格式同款）。"""
    with pytest.raises(TopicError, match="非法分类"):
        parse_confirm_entries(
            {
                "entries": [
                    {"year": "2026", "number": "C", "problem_text": "题面", "category": "mystery"}
                ]
            }
        )


def test_load_entry_category_defaults_empty_for_old_manifest(topic_root, pdf):
    """旧条目（manifest 无 category）：读盘缺省 ""，向后兼容。"""
    confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2023", number="E", problem_text="2023E 题面"),),
    )
    manifest_path = topic_root / "2023E" / MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data.pop("category")
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert resolve_number(topic_root, "2023E").category == ""


def test_load_entry_rejects_out_of_vocab_category(topic_root, pdf):
    """词表外 category = 元数据损坏：浏览时大声失败，不把坏数据带进列表。"""
    confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2023", number="E", problem_text="2023E 题面"),),
    )
    manifest_path = topic_root / "2023E" / MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["category"] = "mystery"
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(TopicError, match="非法分类"):
        resolve_number(topic_root, "2023E")
    with pytest.raises(TopicError, match="非法分类"):
        list_topics(topic_root)


def test_topic_entry_to_dict_contains_category():
    """to_dict 带出 category（浏览列表 / 单条取题面经它自动透出）。"""
    entry = TopicEntry(year="2023", number="E", problem_text="题面", category="control")
    assert entry.to_dict()["category"] == "control"
    assert TopicEntry(year="2023", number="E", problem_text="题面").to_dict()["category"] == ""


def test_update_topic_edits_category(topic_root, pdf, tmp_path):
    """edit 分类（工单 topics-control-2023-2025/01）：category 是第四可编辑字段。"""
    confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2026", number="C", problem_text="2026C 题面"),),
    )
    updated = update_topic(
        topic_root,
        "2026C",
        problem_text="2026C 题面",
        programs=(),
        hint_module_groups=(),
        category="control",
    )
    assert updated.category == "control"
    manifest = json.loads(
        (topic_root / "2026C" / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["category"] == "control"
    assert resolve_number(topic_root, "2026C").category == "control"


def test_update_topic_category_defaults_empty(topic_root, pdf):
    """update 不带 category = 未标记（""）——既有调用（测试 / 前端旧表单）兼容。"""
    confirm_topics(
        topic_root,
        pdf,
        (TopicDraft(year="2026", number="C", problem_text="2026C 题面", category="other"),),
    )
    updated = update_topic(
        topic_root,
        "2026C",
        problem_text="2026C 题面",
        programs=(),
        hint_module_groups=(),
    )
    assert updated.category == ""
    manifest = json.loads(
        (topic_root / "2026C" / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["category"] == ""


def test_topics_categories_endpoint(topic_context):
    """词表端点（工单 topics-control-2023-2025/01）：GET /api/topics/categories——
    路由必须注册在 GET /api/topics/{key} 之前，否则 categories 被当 key 解析。"""
    ctx, _, _ = topic_context
    with _client(ctx) as client:
        response = client.get("/api/topics/categories")

    assert response.status_code == 200
    assert response.json() == {"categories": ["control", "other"]}


def test_topics_confirm_endpoint_accepts_category(topic_context, tmp_path):
    """confirm 路由：entries 项带 category 落盘；缺省 = ""。"""
    ctx, _, topics_dir = topic_context
    pdf_path = tmp_path / "真题.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    with _client(ctx) as client:
        with pdf_path.open("rb") as file:
            response = client.post(
                "/api/topics/confirm",
                files={"pdf": ("真题.pdf", file, "application/pdf")},
                data={
                    "payload": json.dumps(
                        {
                            "entries": [
                                {
                                    "year": "2023",
                                    "number": "E",
                                    "problem_text": "2023E 题面",
                                    "category": "control",
                                }
                            ],
                            "program_dirs": [],
                        }
                    )
                },
            )
    assert response.status_code == 200
    assert response.json()["topics"][0]["category"] == "control"
    manifest = json.loads(
        (topics_dir / "2023E" / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["category"] == "control"


def test_topics_get_and_list_endpoints_expose_category(topic_context, tmp_path):
    """透出契约（review 整改）：GET /api/topics/{key} 与 GET /api/topics
    都经 to_dict 带出 category（浏览列表 + 生成入口素材两路都可见）。"""
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])  # 无 category → ""
    manifest_path = topics_dir / KEY_2026C / MANIFEST_FILENAME
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["category"] = "control"
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with _client(ctx) as client:
        single = client.get(f"/api/topics/{KEY_2026C}")
        listed = client.get("/api/topics")

    assert single.status_code == 200
    assert single.json()["category"] == "control"
    assert listed.status_code == 200
    assert {t["key"]: t["category"] for t in listed.json()}[KEY_2026C] == "control"


def test_topics_put_endpoint_category_contract(topic_context, tmp_path):
    """PUT 编辑路由：body 带 category 落盘回读；词表外 400 中文。"""
    ctx, _, topics_dir = topic_context
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])

    with _client(ctx) as client:
        response = client.put(
            f"/api/topics/{KEY_2026C}",
            json={
                "problem_text": "2026C 编辑后题面",
                "programs": [],
                "hint_module_groups": [],
                "category": "control",
            },
        )
    assert response.status_code == 200
    assert response.json()["category"] == "control"
    manifest = json.loads(
        (topics_dir / KEY_2026C / MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert manifest["category"] == "control"

    with _client(ctx) as client:
        bad = client.put(
            f"/api/topics/{KEY_2026C}",
            json={
                "problem_text": "2026C 编辑后题面",
                "programs": [],
                "hint_module_groups": [],
                "category": "mystery",
            },
        )
    assert bad.status_code == 400
    assert "非法分类" in bad.json()["detail"]
