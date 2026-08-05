"""DeepSeek 生产 LLM 客户端：请求形状、结构化输出解析、错误处理。

网络调用通过注入的 FakeTransport 隔离，测试只覆盖请求/响应契约与纯解析逻辑。
"""

import json
from typing import Any

import pytest

from contest_generator.config import AppConfig
from contest_generator.llm import (
    DeepSeekLLM,
    FileVersion,
    JudgmentFile,
    LLMError,
    VersionSummary,
    build_manifest_summaries,
    parse_distillation_report,
    parse_module_selection,
    parse_summary_report,
    parse_validation_result,
)
from contest_generator.report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    FileDecision,
    ReportError,
)
from contest_generator.manifest import ModuleManifest
from tests.fakes import FakeTransport

SELECTION_JSON = json.dumps(
    {"modules": [{"slug": "dht11", "reason": "赛题要求采集温湿度"}]}
)


def _api_response(content: str) -> str:
    """模拟 DeepSeek Chat Completions 响应包络：content 在 choices[0].message.content。"""
    return json.dumps({"choices": [{"message": {"content": content}}]})


def _manifest(slug: str, description: str, deps: tuple[str, ...] = ()) -> ModuleManifest:
    return ModuleManifest(slug=slug, description=description, dependencies=deps)


def _llm(
    transport: FakeTransport,
    *,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> DeepSeekLLM:
    return DeepSeekLLM(
        AppConfig(base_url=base_url, api_key="sk-test", model=model),
        transport=transport,
    )


# ---------------------------------------------------------------------------
# manifest 摘要
# ---------------------------------------------------------------------------


def test_manifest_summaries_list_each_module_with_description_and_deps():
    manifests = [
        _manifest("dht11", "DHT11 温湿度传感器驱动", deps=("delay",)),
        _manifest("oled", "OLED 屏显驱动"),
    ]

    summaries = build_manifest_summaries(manifests)

    assert summaries == [
        "- dht11: DHT11 温湿度传感器驱动（依赖: delay）",
        "- oled: OLED 屏显驱动",
    ]


def test_manifest_summaries_empty_library_gives_empty_list():
    assert build_manifest_summaries([]) == []


# ---------------------------------------------------------------------------
# select_modules：请求形状 + 结构化输出解析
# ---------------------------------------------------------------------------


def test_select_modules_posts_chat_completion_with_expected_request():
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    problem = "设计一个环境监测仪，测量温湿度并显示"

    result = llm.select_modules(problem, ["- dht11: 温湿度传感器驱动"])

    url, headers, payload, timeout = transport.calls[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"
    assert headers["Content-Type"] == "application/json"
    assert payload["model"] == "deepseek-chat"
    assert payload["response_format"] == {"type": "json_object"}
    assert timeout == 120
    user_message = payload["messages"][1]["content"]
    assert problem in user_message
    assert "- dht11: 温湿度传感器驱动" in user_message
    assert "JSON" in user_message  # DeepSeek 的 json_object 模式要求提示词含 json

    assert result.modules == ("dht11",)
    assert result.reasons == {"dht11": "赛题要求采集温湿度"}


def test_select_modules_uses_configured_base_url_and_model():
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport, base_url="https://example.com/v1/", model="deepseek-reasoner")

    llm.select_modules("赛题", ["- dht11: 温湿度"])

    url, _, payload, _ = transport.calls[0]
    assert url == "https://example.com/v1/chat/completions"
    assert payload["model"] == "deepseek-reasoner"


def test_select_modules_empty_selection_is_valid():
    transport = FakeTransport(body=_api_response(json.dumps({"modules": []})))
    llm = _llm(transport)

    result = llm.select_modules("赛题", ["- dht11: 温湿度"])

    assert result.modules == ()
    assert result.reasons == {}


def test_select_modules_http_error_raises_with_status():
    transport = FakeTransport(status=401, body="invalid api key")
    llm = _llm(transport)

    with pytest.raises(LLMError, match="401"):
        llm.select_modules("赛题", ["- dht11: 温湿度"])


def test_select_modules_invalid_json_response_raises():
    transport = FakeTransport(body="{not json")
    llm = _llm(transport)

    with pytest.raises(LLMError, match="JSON"):
        llm.select_modules("赛题", ["- dht11: 温湿度"])


def test_select_modules_missing_content_field_raises():
    transport = FakeTransport(body=json.dumps({"choices": []}))
    llm = _llm(transport)

    with pytest.raises(LLMError, match="content"):
        llm.select_modules("赛题", ["- dht11: 温湿度"])


# ---------------------------------------------------------------------------
# 结构化输出解析（纯函数）
# ---------------------------------------------------------------------------


def test_parse_selection_accepts_multiple_modules_with_reasons():
    result = parse_module_selection(
        json.dumps(
            {
                "modules": [
                    {"slug": "dht11", "reason": "测温湿度"},
                    {"slug": "oled", "reason": "显示数据"},
                ]
            }
        ),
        known_slugs=("dht11", "oled"),
    )

    assert result.modules == ("dht11", "oled")
    assert result.reasons == {"dht11": "测温湿度", "oled": "显示数据"}


def test_parse_selection_rejects_unknown_slug():
    with pytest.raises(LLMError, match="不存在"):
        parse_module_selection(
            json.dumps({"modules": [{"slug": "wifi", "reason": "通信"}]}),
            known_slugs=("dht11",),
        )


def test_parse_selection_rejects_duplicate_slug():
    with pytest.raises(LLMError, match="重复"):
        parse_module_selection(
            json.dumps(
                {
                    "modules": [
                        {"slug": "dht11", "reason": "a"},
                        {"slug": "dht11", "reason": "b"},
                    ]
                }
            ),
            known_slugs=("dht11",),
        )


@pytest.mark.parametrize(
    "bad_json",
    [
        "{not json",
        json.dumps({"modules": "dht11"}),
        json.dumps({"modules": [{"reason": "缺 slug"}]}),
        json.dumps({"modules": [{"slug": "dht11", "reason": 42}]}),
    ],
)
def test_parse_selection_rejects_malformed_output(bad_json):
    with pytest.raises(LLMError):
        parse_module_selection(bad_json, known_slugs=("dht11",))


# ---------------------------------------------------------------------------
# 其余两个职责：骨架与简介，共用 chat 通道
# ---------------------------------------------------------------------------


def test_generate_main_skeleton_routes_problem_and_header_interfaces_to_chat():
    transport = FakeTransport(body=_api_response("int main(void) { /* TODO */ }"))
    llm = _llm(transport)
    interfaces = [
        "### 模块 dht11（inc/dht11.h）\n#pragma once\nfloat dht11_read(void);"
    ]

    skeleton = llm.generate_main_skeleton("赛题", interfaces)

    assert skeleton == "int main(void) { /* TODO */ }"
    url, headers, payload, _ = transport.calls[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"
    user_message = payload["messages"][1]["content"]
    assert "赛题" in user_message
    assert "float dht11_read(void);" in user_message
    assert "response_format" not in payload
    # 系统提示约束骨架规则：初始化序列、只调真实接口、不确定写占位、不凭空造函数
    system_message = payload["messages"][0]["content"]
    assert "初始化序列" in system_message
    assert "占位" in system_message
    assert "绝不凭空造函数" in system_message


def test_summarize_module_returns_ai_description():
    transport = FakeTransport(body=_api_response("DHT11 温湿度传感器驱动，读取单总线数据"))
    llm = _llm(transport)

    summary = llm.summarize_module("float dht11_read(void);")

    assert summary == "DHT11 温湿度传感器驱动，读取单总线数据"
    _, _, payload, _ = transport.calls[0]
    assert "float dht11_read(void);" in payload["messages"][1]["content"]


# ---------------------------------------------------------------------------
# 模块简介一致性校验：json 结构化输出
# ---------------------------------------------------------------------------


def test_validate_module_description_posts_json_request_with_description_and_code():
    transport = FakeTransport(
        body=_api_response(json.dumps({"consistent": True, "issues": ""}))
    )
    llm = _llm(transport)
    description = "DHT11 温湿度传感器驱动，单总线协议"
    code = "float dht11_read(void);"

    result = llm.validate_module_description(description, code)

    assert result.consistent is True
    assert result.issues == ""
    _, _, payload, _ = transport.calls[0]
    assert payload["response_format"] == {"type": "json_object"}
    user_message = payload["messages"][1]["content"]
    assert description in user_message
    assert code in user_message
    assert "json" in user_message  # DeepSeek 的 json_object 模式要求提示词含 json
    # 系统提示约束校验任务：判断简介与实际代码是否一致
    assert "一致" in payload["messages"][0]["content"]


def test_validate_module_description_reports_inconsistency_with_issues():
    transport = FakeTransport(
        body=_api_response(
            json.dumps(
                {
                    "consistent": False,
                    "issues": "简介声称支持 I2C，实际代码是单总线协议",
                }
            )
        )
    )
    llm = _llm(transport)

    result = llm.validate_module_description("支持 I2C", "float dht11_read(void);")

    assert result.consistent is False
    assert "单总线协议" in result.issues


@pytest.mark.parametrize(
    "bad_json",
    [
        "{not json",
        json.dumps({"consistent": True, "issues": 42}),
    ],
)
def test_parse_validation_rejects_malformed_output(bad_json):
    with pytest.raises(LLMError):
        parse_validation_result(bad_json)


def test_parse_validation_rejects_missing_consistent():
    with pytest.raises(LLMError, match="缺少"):
        parse_validation_result(json.dumps({"issues": "缺 consistent"}))


def test_parse_validation_rejects_non_bool_consistent():
    with pytest.raises(LLMError, match="布尔"):
        parse_validation_result(json.dumps({"consistent": "yes", "issues": ""}))


# ---------------------------------------------------------------------------
# 母版提炼判定：两阶段（读全文出摘要 → 基于摘要判定），json 结构化输出
# ---------------------------------------------------------------------------

DISTILL_DECISIONS_JSON = json.dumps(
    {
        "decisions": [
            {"path": "src/oled.c", "action": ACTION_MERGE,
             "content": "/* 整合产物 */\n", "explanation": "两版合并去重",
             "source": "proj-a", "reason": "A 的 include path 更全"},
            {"path": "sensors/dht11.c", "action": ACTION_KEEP, "reason": "通用驱动"},
            {"path": "ui/oled_fonts.c", "action": ACTION_EXCLUDE, "reason": "赛题残留"},
        ]
    }
)

JUDGMENT_FILES = (
    JudgmentFile(
        path="src/oled.c",
        versions=(
            FileVersion(
                content="/* 通用 OLED 驱动（A 版本） */\nvoid oled_init(void);\n",
                projects=("proj-a",),
            ),
            FileVersion(
                content="/* 通用 OLED 驱动（B 版本） */\nvoid oled_init(void);\n",
                projects=("proj-b",),
            ),
        ),
    ),
    JudgmentFile(
        path="sensors/dht11.c",
        versions=(
            FileVersion(
                content="/* 通用 DHT11 驱动 */\nfloat dht11_read(void);\n",
                projects=("proj-a",),
            ),
        ),
    ),
)

SUMMARY_REPORT_JSON = json.dumps(
    {
        "summaries": [
            {
                "path": "src/oled.c",
                "versions": [
                    {"projects": ["proj-a"], "summary": "A 版本：通用 OLED 初始化驱动"},
                    {"projects": ["proj-b"], "summary": "B 版本：OLED 驱动带滚屏功能"},
                ],
            },
            {
                "path": "sensors/dht11.c",
                "versions": [
                    {"projects": ["proj-a"], "summary": "通用 DHT11 单总线驱动"}
                ],
            },
        ]
    }
)


class SequenceTransport(FakeTransport):
    """按调用顺序返回固定响应列表的传输假件（两阶段请求形状测试）。"""

    def __init__(self, bodies: list[str]) -> None:
        super().__init__()
        self._bodies = list(bodies)

    def post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> tuple[int, str]:
        body = self._bodies.pop(0)
        self.calls.append((url, headers, payload, timeout))
        return self.status, body


def test_distill_master_two_phase_posts_summaries_then_decisions():
    transport = SequenceTransport(
        [_api_response(SUMMARY_REPORT_JSON), _api_response(DISTILL_DECISIONS_JSON)]
    )
    llm = _llm(transport)
    summary = "冲突文件（同路径、内容不同）：\n- src/oled.c（出现在：proj-a、proj-b）"

    decisions = llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, summary)

    # 两次 json_mode 调用：第一阶段读全文出摘要，第二阶段基于摘要判定
    assert len(transport.calls) == 2
    for _, _, payload, _ in transport.calls:
        assert payload["response_format"] == {"type": "json_object"}

    # 第一阶段：user 消息含平台、工程与每个版本的全文
    _, _, phase1_payload, _ = transport.calls[0]
    phase1_message = phase1_payload["messages"][1]["content"]
    assert "stm32" in phase1_message
    assert "proj-a" in phase1_message
    assert "src/oled.c" in phase1_message
    assert "通用 OLED 驱动（A 版本）" in phase1_message
    assert "通用 OLED 驱动（B 版本）" in phase1_message
    assert "json" in phase1_message  # DeepSeek 的 json_object 模式要求提示词含 json
    assert "摘要" in phase1_payload["messages"][0]["content"]

    # 第二阶段：输入包含第一阶段的摘要产物（读全文的要点）+ 结构与配置对比
    _, _, phase2_payload, _ = transport.calls[1]
    phase2_message = phase2_payload["messages"][1]["content"]
    assert "A 版本：通用 OLED 初始化驱动" in phase2_message
    assert "B 版本：OLED 驱动带滚屏功能" in phase2_message
    assert "通用 DHT11 单总线驱动" in phase2_message
    assert "src/oled.c（proj-a）" in phase2_message
    assert "冲突文件（同路径、内容不同）" in phase2_message
    assert "判定" in phase2_payload["messages"][0]["content"]
    assert "整合" in phase2_message  # merge 语义：读多份整合出通用版本

    assert len(decisions) == 3
    assert decisions[0] == FileDecision(
        "src/oled.c",
        ACTION_MERGE,
        content="/* 整合产物 */\n",
        explanation="两版合并去重",
        source="proj-a",
        reason="A 的 include path 更全",
    )


def test_distill_master_fails_loud_on_broken_summary_phase():
    """第一阶段返回非 JSON 就抛 LLMError，不进第二阶段——宁可大声失败。"""
    transport = SequenceTransport(
        [_api_response("{not json"), _api_response(DISTILL_DECISIONS_JSON)]
    )
    llm = _llm(transport)

    with pytest.raises(LLMError, match="JSON"):
        llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == 1  # 第一阶段失败即停


def test_distill_master_fails_loud_on_missing_summary():
    """缺某个文件的摘要 → 第二阶段素材残缺，拒绝进入判定。"""
    missing = json.dumps(
        {
            "summaries": [
                {
                    "path": "src/oled.c",
                    "versions": [
                        {"projects": ["proj-a"], "summary": "A 版本"},
                        {"projects": ["proj-b"], "summary": "B 版本"},
                    ],
                }
            ]
        }
    )
    transport = SequenceTransport(
        [_api_response(missing), _api_response(DISTILL_DECISIONS_JSON)]
    )
    llm = _llm(transport)

    with pytest.raises(LLMError, match="缺少文件"):
        llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == 1


def test_parse_summary_accepts_all_versions_with_holders():
    summaries = parse_summary_report(SUMMARY_REPORT_JSON, JUDGMENT_FILES)

    assert [s.path for s in summaries] == ["src/oled.c", "sensors/dht11.c"]
    assert summaries[0].versions[0] == VersionSummary(
        ("proj-a",), "A 版本：通用 OLED 初始化驱动"
    )
    assert summaries[0].versions[1].projects == ("proj-b",)
    assert summaries[1].versions[0].summary == "通用 DHT11 单总线驱动"


def test_parse_summary_accepts_identical_content_grouped_as_one_version():
    """内容一致的工程归为一个版本：proj-a / proj-c 共享同一份摘要。"""
    files = (
        JudgmentFile(
            path="src/oled.c",
            versions=(
                FileVersion(
                    content="/* A 版 */\n", projects=("proj-a", "proj-c")
                ),
                FileVersion(content="/* B 版 */\n", projects=("proj-b",)),
            ),
        ),
    )
    report = json.dumps(
        {
            "summaries": [
                {
                    "path": "src/oled.c",
                    "versions": [
                        {"projects": ["proj-c", "proj-a"], "summary": "A 版摘要"},
                        {"projects": ["proj-b"], "summary": "B 版摘要"},
                    ],
                }
            ]
        }
    )

    summaries = parse_summary_report(report, files)

    # 分组按工程名集合匹配，输出顺序无关
    by_projects = {v.projects: v.summary for v in summaries[0].versions}
    assert by_projects[("proj-c", "proj-a")] == "A 版摘要"
    assert by_projects[("proj-b",)] == "B 版摘要"


@pytest.mark.parametrize(
    "bad_json",
    [
        "{not json",
        json.dumps({"nope": []}),
        json.dumps({"summaries": "not a list"}),
        json.dumps({"summaries": [{"versions": []}]}),  # 缺 path
        json.dumps({"summaries": [{"path": "src/extra.c", "versions": []}]}),
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "src/oled.c",
                        "versions": [
                            {"projects": ["proj-a"], "summary": "A"},
                            {"projects": ["proj-b"], "summary": "B"},
                        ],
                    },
                    {"path": "src/oled.c", "versions": []},  # 重复路径
                ]
            }
        ),
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "src/oled.c",
                        "versions": [
                            {"projects": ["proj-a"], "summary": "A"},
                            {"projects": ["proj-b"], "summary": ""},  # 摘要为空
                        ],
                    }
                ]
            }
        ),
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "src/oled.c",
                        "versions": [
                            {"projects": ["proj-a"], "summary": "A"},
                            {"projects": ["proj-c"], "summary": "B"},  # 未知工程
                        ],
                    }
                ]
            }
        ),
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "src/oled.c",
                        "versions": [
                            {"projects": ["proj-a"], "summary": "A"},  # 缺 proj-b 版本
                        ],
                    }
                ]
            }
        ),
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "src/oled.c",
                        "versions": [
                            {"projects": ["proj-a"], "summary": "A"},
                            {"projects": ["proj-a"], "summary": "A 重复"},  # 版本重复
                        ],
                    }
                ]
            }
        ),
        # 独有文件（单版本）同一组工程名出两份摘要：同样按重复拒绝
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "sensors/dht11.c",
                        "versions": [
                            {"projects": ["proj-a"], "summary": "通用驱动"},
                            {"projects": ["proj-a"], "summary": "再抄一遍"},
                        ],
                    }
                ]
            }
        ),
    ],
)
def test_parse_summary_rejects_malformed_output(bad_json):
    with pytest.raises(LLMError):
        parse_summary_report(bad_json, JUDGMENT_FILES)


def test_parse_distillation_accepts_mixed_decisions():
    decisions = parse_distillation_report(DISTILL_DECISIONS_JSON, ("proj-a", "proj-b"))

    assert decisions[0].action == ACTION_MERGE
    assert decisions[0].content == "/* 整合产物 */\n"
    assert decisions[0].explanation == "两版合并去重"
    assert decisions[0].source == "proj-a"
    assert decisions[1].action == ACTION_KEEP
    assert decisions[2].action == ACTION_EXCLUDE


@pytest.mark.parametrize(
    "bad_json",
    [
        "{not json",
        json.dumps({"nope": []}),
        json.dumps({"decisions": "not a list"}),
        json.dumps({"decisions": [{"path": "a.c", "action": "archive"}]}),
        json.dumps({"decisions": [{"action": ACTION_KEEP}]}),  # 缺 path
        json.dumps(
            {"decisions": [{"path": "a.c", "action": ACTION_MERGE,
                            "explanation": "说明"}]}  # merge 缺 content
        ),
        json.dumps(
            {"decisions": [{"path": "a.c", "action": ACTION_MERGE,
                            "content": "产物"}]}  # merge 缺 explanation
        ),
        json.dumps(
            {"decisions": [{"path": "a.c", "action": ACTION_MERGE,
                            "content": "   ", "explanation": "说明"}]}  # 空白 content
        ),
        json.dumps({"decisions": [{"path": "a.c", "action": ACTION_KEEP, "source": "proj-a"}]}),
        json.dumps({"decisions": [{"path": "a.c", "action": ACTION_KEEP, "content": "产物"}]}),
        json.dumps(
            {
                "decisions": [
                    {"path": "a.c", "action": ACTION_KEEP},
                    {"path": "a.c", "action": ACTION_EXCLUDE},
                ]
            }
        ),
    ],
)
def test_parse_distillation_rejects_malformed_output(bad_json):
    with pytest.raises(LLMError):
        parse_distillation_report(bad_json, ("proj-a", "proj-b"))


def test_parse_distillation_rejects_unknown_source_project():
    with pytest.raises(LLMError, match="来源工程"):
        parse_distillation_report(
            json.dumps(
                {
                    "decisions": [
                        {
                            "path": "a.c",
                            "action": ACTION_MERGE,
                            "content": "产物",
                            "explanation": "说明",
                            "source": "proj-c",
                        }
                    ]
                }
            ),
            ("proj-a", "proj-b"),
        )


# ---------------------------------------------------------------------------
# FileDecision 序列化：确认请求按 to_dict 的同一形状回传
# ---------------------------------------------------------------------------


def test_file_decision_round_trips_through_json():
    decision = FileDecision(
        "src/oled.c",
        ACTION_MERGE,
        content="/* 整合产物 */\n",
        explanation="两版合并去重",
        source="proj-a",
        reason="include path 更全",
    )

    rebuilt = FileDecision.from_dict(decision.to_dict())

    assert rebuilt == decision
    assert rebuilt.to_dict() == {
        "path": "src/oled.c",
        "action": ACTION_MERGE,
        "content": "/* 整合产物 */\n",
        "explanation": "两版合并去重",
        "source": "proj-a",
        "reason": "include path 更全",
    }


def test_file_decision_from_dict_accepts_keep_without_source():
    decision = FileDecision.from_dict(
        {"path": "main.c", "action": ACTION_KEEP, "reason": "公共骨架"}
    )

    assert decision == FileDecision("main.c", ACTION_KEEP, reason="公共骨架")


@pytest.mark.parametrize(
    "bad",
    [
        "not a dict",
        {"action": ACTION_KEEP},  # 缺 path
        {"path": "", "action": ACTION_KEEP},
        {"path": "a.c", "action": "archive"},  # action 非法
        {"path": "a.c", "action": ACTION_MERGE, "explanation": "说明"},  # merge 缺 content
        {"path": "a.c", "action": ACTION_MERGE, "content": "产物"},  # merge 缺 explanation
        {"path": "a.c", "action": ACTION_MERGE, "content": "   ", "explanation": "说明"},  # 空白 content
        {"path": "a.c", "action": ACTION_KEEP, "source": "proj-a"},  # 非 merge 带来源
        {"path": "a.c", "action": ACTION_KEEP, "content": "产物"},  # 非 merge 带 content
        {"path": "a.c", "action": ACTION_KEEP, "reason": 42},
    ],
)
def test_file_decision_from_dict_rejects_malformed(bad):
    with pytest.raises(ReportError):
        FileDecision.from_dict(bad)
