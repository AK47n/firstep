"""赛题库核心：长 PDF 拆条（AI）→ 用户逐条校对 → 确认入库（事务）+ 编号解析。

用假 LLM（FakeLLM 子类补 topic_* 职责，tests/fakes.py 只读）驱动，断言磁盘
库目录结构（一条目一目录：题面 topic.md + manifest.json + 原 PDF 副本）与
manifest 内容（外部行为）。确认入库是事务：任何校验失败都在落盘前，失败
不留半成品；编号解析查无此条明确报错、不猜测编造。
"""

from __future__ import annotations

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from contest_generator.config import AppConfig
from contest_generator.library import LibraryError, add_module
from contest_generator.llm import (
    LLMError,
    TOPIC_SPLIT_LLM_CHAR_CAP,
    parse_topic_number,
    parse_topic_split,
)
from contest_generator.manifest import MANIFEST_FILENAME
from contest_generator.topic_library import (
    TOPIC_MD_FILENAME,
    TopicDraft,
    TopicError,
    confirm_topics,
    delete_topic,
    discover_related_modules,
    list_topics,
    parse_confirm_entries,
    resolve_number,
    split_topics_document,
)
from contest_generator.webapp import AppContext, create_app
from tests.fakes import (
    FakeLLM,
    _add_module,
    make_fake_module_library,
    make_sample_pdf,
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
    assert entry.problem_md == TOPIC_MD_FILENAME


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
# 关联模块：复用模块简介"XX 题专用"标注自动发现，不新造链接字段
#
# 注意（工单 module-universalization/01 起）：补录/编辑简介已被判据④机械拦截
# （题号/年份/题名禁止入简介），发现机制只对直写 manifest 的存量/手改条目
# 生效——测试用 _add_module 直写 manifest 构造素材（绕过补录门禁，专测发现
# 机制本身）。
# ---------------------------------------------------------------------------


def test_discover_related_modules_finds_specific_modules(tmp_path):
    library = make_fake_module_library(tmp_path / "module_library")
    # 假库已有 dht11 / oled / delay / broken；再直写两道带题号的模块
    _add_module(
        library,
        {
            "slug": "lock_control",
            "description": "2026C 数字钥匙题专用锁控制逻辑",
            "dependencies": [],
            "platforms": {
                "stm32": {"files": ["lock_control.c"], "verified": False}
            },
        },
        {"lock_control.c": "int lock_open(void);\n"},
    )
    _add_module(
        library,
        {
            "slug": "zone",
            "description": "2026C 数字钥匙题专用区域判定",
            "dependencies": [],
            "platforms": {
                "stm32": {"files": ["zone.c"], "verified": False}
            },
        },
        {"zone.c": "int zone_determine(void);\n"},
    )

    related = discover_related_modules(library, KEY_2026C)

    assert related == ("lock_control", "zone")
    assert "dht11" not in related


def test_discover_related_modules_excludes_other_topics_and_generic(tmp_path):
    library = make_fake_module_library(tmp_path / "module_library")
    add_module(
        FakeLLM(),
        library,
        slug="pid",
        platform="stm32",
        description="巡线题专用 PID 控制",
        files={"pid.c": "int pid_calc(void);\n"},
    )

    assert discover_related_modules(library, KEY_2026C) == ()
    assert discover_related_modules(library, "2025A") == ()


def test_discover_related_modules_missing_library_returns_empty(tmp_path):
    assert discover_related_modules(tmp_path / "不存在", KEY_2026C) == ()


def test_discover_related_modules_corrupt_manifest_raises(tmp_path):
    library = make_fake_module_library(tmp_path / "module_library")
    (library / "broken" / MANIFEST_FILENAME).write_text("{bad", encoding="utf-8")

    # 模块清单走 library.list_modules（唯一浏览入口）：损坏 manifest 大声失败，
    # 与模块库浏览同哲学，不静默跳过
    with pytest.raises(LibraryError, match="manifest"):
        discover_related_modules(library, KEY_2026C)


# ---------------------------------------------------------------------------
# HTTP 层：拆条上传 / 确认入库（multipart）/ 编号解析
# ---------------------------------------------------------------------------


@pytest.fixture
def topic_context(tmp_path):
    """已配置的假上下文：假模块库（关联模块发现用）+ 赛题库根（模块库同级
    topics/）+ 假 LLM，配置文件路径在 tmp 下。"""
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
    assert body["related_modules"] == []  # 假库无"XX 题专用"模块
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
# 浏览列表 / 删除路由（工单 05）：GET /api/topics（每条带关联模块，一次性
# 算好不 N 次前端调用）、DELETE /api/topics/{key}（查无此条明确报错）
# ---------------------------------------------------------------------------


def _confirm_draft(ctx, topics_dir, tmp_path, draft) -> None:
    pdf_path = tmp_path / "真题.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    confirm_topics(topics_dir, pdf_path, (draft,))


def test_topics_list_endpoint_sorted_with_related_modules(topic_context, tmp_path):
    ctx, _, topics_dir = topic_context
    older = TopicDraft(year="2018", number="A", problem_text="2018A 题面")
    _confirm_draft(ctx, topics_dir, tmp_path, older)
    _confirm_draft(ctx, topics_dir, tmp_path, DRAFTS[0])  # 2026C
    # 判据④ 起补录拒题绑定，直写 manifest 构造带题号模块（专测发现机制）
    _add_module(
        ctx.config.module_library_dir,
        {
            "slug": "lock_control",
            "description": "2026C 数字钥匙题专用锁控制逻辑",
            "dependencies": [],
            "platforms": {
                "stm32": {"files": ["lock_control.c"], "verified": False}
            },
        },
        {"lock_control.c": "int lock_open(void);\n"},
    )

    with _client(ctx) as client:
        response = client.get("/api/topics")

    assert response.status_code == 200
    body = response.json()
    assert [t["key"] for t in body] == ["2018A", KEY_2026C]
    by_key = {t["key"]: t for t in body}
    assert by_key[KEY_2026C]["related_modules"] == ["lock_control"]
    assert by_key["2018A"]["related_modules"] == []
    assert by_key[KEY_2026C]["problem_text"] == DRAFTS[0].problem_text


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
