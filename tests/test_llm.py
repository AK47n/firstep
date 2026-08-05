"""DeepSeek 生产 LLM 客户端：请求形状、结构化输出解析、错误处理。

网络调用通过注入的 FakeTransport 隔离，测试只覆盖请求/响应契约与纯解析逻辑。
"""

import json

import pytest

from contest_generator.config import LLMConfig
from contest_generator.llm import (
    DeepSeekLLM,
    LLMError,
    build_manifest_summaries,
    parse_module_selection,
    parse_validation_result,
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
        LLMConfig(base_url=base_url, api_key="sk-test", model=model),
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
