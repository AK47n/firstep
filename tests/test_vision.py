"""视觉通道（工单 vision-eyes/01）：GLM-4V-Flash 云端识图。

假传输注入（照 llm.Transport 接缝先例）：请求体形状 / 重试 / 解析 / 缓存 /
错误登记。真实网络不在此测试（真机验收需用户配置智谱 key）。
"""

import json

import pytest

from contest_generator.errors import error_entry
from contest_generator.vision import (
    DEFAULT_DESCRIBE_PROMPT,
    DEFAULT_VISION_MODEL,
    VisionError,
    VisionNotConfiguredError,
    _IMAGE_DESCRIBE_CACHE,
    clear_describe_cache,
    describe_image,
    describe_image_cached,
    vision_configured,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-bytes-0001"
PNG_MIME = "image/png"


class FakeTransport:
    """假传输：按脚本返回（status, body）或抛错；记录最近一次请求。"""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[tuple[str, dict, dict]] = []

    def post(self, url, headers, payload, timeout):
        self.calls.append((url, headers, payload))
        step = self.script.pop(0) if self.script else (200, '{"choices":[{"message":{"content":"OK"}}]}')
        if isinstance(step, Exception):
            raise step
        status, body = step
        return status, body, {}

    @property
    def last_payload(self):
        return self.calls[-1][2]


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_describe_cache()
    yield
    clear_describe_cache()


def _ok_body(text: str = "图里有电路连接 A-B") -> tuple[int, str]:
    return 200, json.dumps(
        {"choices": [{"message": {"content": text}}]}, ensure_ascii=False
    )


# ---------------------------------------------------------------------------
# 配置判定
# ---------------------------------------------------------------------------


def test_vision_configured_requires_key():
    assert not vision_configured("")
    assert not vision_configured("   ")
    assert vision_configured("sk-test")


def test_describe_without_key_raises_not_configured():
    with pytest.raises(VisionNotConfiguredError, match="未配置"):
        describe_image(PNG_BYTES, PNG_MIME, api_key="")


def test_vision_error_registered_as_400():
    status, message = error_entry(
        VisionError("视觉服务限流（HTTP 429）")
    )
    assert status == 400
    assert "视觉" in message


# ---------------------------------------------------------------------------
# 请求体形状
# ---------------------------------------------------------------------------


def test_describe_posts_openai_compatible_payload():
    transport = FakeTransport(_ok_body())
    describe_image(
        PNG_BYTES, PNG_MIME, "自定义提示", api_key="sk-test", transport=transport
    )
    url, headers, payload = transport.calls[0]
    assert url.endswith("/chat/completions")
    assert headers["Authorization"] == "Bearer sk-test"
    assert payload["model"] == DEFAULT_VISION_MODEL
    content = payload["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "自定义提示"}
    image = content[1]["image_url"]["url"]
    assert image.startswith("data:image/png;base64,")
    # base64 解码回来 = 原字节
    import base64

    assert base64.b64decode(image.split(",", 1)[1]) == PNG_BYTES


def test_describe_default_prompt_guides_elements():
    transport = FakeTransport(_ok_body())
    describe_image(PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport)
    content = transport.last_payload["messages"][0]["content"]
    assert "示意图" in content[0]["text"]
    assert DEFAULT_DESCRIBE_PROMPT == content[0]["text"]


def test_describe_custom_base_url_and_model():
    transport = FakeTransport(_ok_body())
    describe_image(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport,
        base_url="http://localhost:9999/v1", model="other-vl",
    )
    url = transport.calls[0][0]
    assert url == "http://localhost:9999/v1/chat/completions"
    assert transport.last_payload["model"] == "other-vl"


# ---------------------------------------------------------------------------
# 响应解析
# ---------------------------------------------------------------------------


def test_describe_parses_string_content():
    transport = FakeTransport(_ok_body("尺寸 50cm"))
    assert describe_image(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
    ) == "尺寸 50cm"


def test_describe_parses_content_array():
    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "布局："},
                            {"type": "text", "text": "A 在左"},
                        ]
                    }
                }
            ]
        },
        ensure_ascii=False,
    )
    transport = FakeTransport((200, body))
    assert describe_image(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
    ) == "布局：A 在左"


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("not-json", "不是 JSON"),
        ('{"choices": []}', "缺少 choices"),
        ('{"choices": [{}]}', "缺少 choices"),
        ('{"choices": [{"message": {"content": 123}}]}', "形态非法"),
        ('{"choices": [{"message": {"content": "   "}}]}', "空描述"),
    ],
)
def test_describe_rejects_bad_responses(body, match):
    transport = FakeTransport((200, body))
    with pytest.raises(VisionError, match=match):
        describe_image(PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport)


def test_describe_rejects_http_errors():
    transport = FakeTransport((401, '{"error":"bad key"}'))
    with pytest.raises(VisionError, match="HTTP 401"):
        describe_image(PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport)


# ---------------------------------------------------------------------------
# 重试（网络类 / 5xx 重试；429 不重试）
# ---------------------------------------------------------------------------


def test_describe_retries_network_errors(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("contest_generator.vision._backoff_sleep", sleeps.append)
    transport = FakeTransport(
        VisionError("无法连接视觉服务 http://x: 网络瞬断"),
        VisionError("无法连接视觉服务 http://x: 网络瞬断"),
        _ok_body("第三次成功"),
    )
    result = describe_image(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
    )
    assert result == "第三次成功"
    assert len(transport.calls) == 3
    assert sleeps == [1, 2]


def test_describe_retries_5xx(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("contest_generator.vision._backoff_sleep", sleeps.append)
    transport = FakeTransport((500, "boom"), _ok_body("恢复"))
    result = describe_image(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
    )
    assert result == "恢复"
    assert sleeps == [1]


def test_describe_does_not_retry_429():
    transport = FakeTransport((429, "rate limited"))
    with pytest.raises(VisionError, match="限流"):
        describe_image(PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport)
    assert len(transport.calls) == 1


def test_describe_exhausts_retries():
    sleeps: list[float] = []
    transport = FakeTransport(
        VisionError("网络错 1"), VisionError("网络错 2"), VisionError("网络错 3")
    )
    import contest_generator.vision as vision

    original = vision._backoff_sleep
    vision._backoff_sleep = sleeps.append
    try:
        with pytest.raises(VisionError, match="网络错 3"):
            describe_image(
                PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
            )
    finally:
        vision._backoff_sleep = original
    assert len(transport.calls) == 3
    assert sleeps == [1, 2]  # N 次尝试 = N-1 次退避


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------


def test_describe_cached_skips_second_call():
    transport = FakeTransport(_ok_body("同图描述"))
    result1 = describe_image_cached(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
    )
    result2 = describe_image_cached(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
    )
    assert result1 == result2 == "同图描述"
    assert len(transport.calls) == 1
    # 缓存键 = 图片内容 sha256（64 位 hex），不是原字节
    assert len(_IMAGE_DESCRIBE_CACHE) == 1
    assert all(len(k) == 64 for k in _IMAGE_DESCRIBE_CACHE)


def test_describe_cached_does_not_cache_failures():
    # 3 次尝试全 500 → 失败（不缓存）；第二次调用（无脚本 → 默认成功）重新请求
    transport = FakeTransport((500, "boom"), (500, "boom"), (500, "boom"))
    with pytest.raises(VisionError):
        describe_image_cached(
            PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
        )
    assert describe_image_cached(
        PNG_BYTES, PNG_MIME, api_key="sk-test", transport=transport
    ) == "OK"
    assert len(transport.calls) == 4  # 失败不缓存，重试重新调用
