"""DeepSeek 生产 LLM 客户端：请求形状、结构化输出解析、错误处理。

网络调用通过注入的 FakeTransport 隔离，测试只覆盖请求/响应契约与纯解析逻辑。
"""

import json
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

import pytest

import contest_generator.llm as llm_module
from contest_generator.config import AppConfig
from contest_generator.events import (
    EVENT_BATCH_DONE,
    EVENT_BATCH_START,
    EVENT_PHASE_DONE,
    EVENT_RETRY,
    EVENT_START,
    PHASE_DECIDE,
    PHASE_SUMMARY,
    EVENT_CONVERGED,
    EVENT_ROUND,
    ProgressEvent,
)
from contest_generator.fix_errors import FixSuggestion, read_file_contexts
from contest_generator.llm import (
    CLARIFICATION_HISTORY_CAP,
    CLARIFY_SYSTEM_PROMPT,
    DEFAULT_WORDLIST,
    DISTILL_SYSTEM_PROMPT,
    DeepSeekLLM,
    EMBEDDED_CONTENT_CAP,
    ERROR_KIND_NETWORK,
    FIX_PREVIOUS_FIXES_CAP,
    FIX_SYSTEM_PROMPT,
    SELECT_SYSTEM_PROMPT,
    SKELETON_NO_UNUSED_RULE,
    SKELETON_SYSTEM_PROMPT,
    SMOKE_SYSTEM_PROMPT,
    JUDGMENT_SCOPE,
    JUDGMENT_SUMMARY_SYSTEM_PROMPT,
    LLMError,
    MAX_REQUEST_BYTES,
    MAX_SUMMARY_BATCH_CHARS,
    NETWORK_RETRY_LIMIT,
    REFERENCE_FULLTEXT_BYTES,
    SKELETON_REFERENCE_TOTAL_BYTES,
    SUMMARY_RETRY_LIMIT,
    TRUNCATION_NOTICE,
    UrllibTransport,
    VALIDATION_SYSTEM_PROMPT,
    VALIDATION_UNIVERSALITY_RULE,
    TOPIC_SPLIT_LLM_CHAR_CAP,
    _batches,
    _clarify_user_prompt,
    _distill_user_prompt,
    _file_chars,
    _fix_errors_user_prompt,
    _selection_user_prompt,
    _skeleton_user_prompt,
    _smoke_user_prompt,
    _split_versions,
    _summarize_user_prompt,
    _truncate_content,
    _validation_user_prompt,
    extract_module_selection_data,
    parse_archive_judgment,
    parse_clarify_questions,
    parse_distillation_report,
    parse_fix_suggestions,
    parse_summary_report,
    parse_validation_result,
)
from contest_generator.selection import (
    REFERENCE_SOURCE_MANUAL,
    ModuleInstance,
    ModuleSelection,
    ReferenceSuggestion,
)
from contest_generator.manifest import (
    ManifestSummary,
    MultiInstanceSpec,
    build_manifest_summaries,
)
from contest_generator.report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    FileDecision,
    FileSummary,
    FileVersion,
    JudgmentFile,
    ReferenceCandidate,
    ReportError,
    VersionSummary,
)
from contest_generator.topic_library import TopicDraft
from contest_generator.manifest import ModuleManifest, PlatformEntry
from tests.fakes import FakeLLM, FakeTransport

SELECTION_JSON = json.dumps(
    {"modules": [{"slug": "dht11", "reason": "赛题要求采集温湿度"}]}
)


def _api_response(content: str) -> str:
    """模拟 DeepSeek Chat Completions 响应包络：content 在 choices[0].message.content。"""
    return json.dumps({"choices": [{"message": {"content": content}}]})


def _manifest(
    slug: str,
    description: str,
    deps: tuple[str, ...] = (),
    kits: tuple[str, ...] = (),
    multi_instance: MultiInstanceSpec | None = None,
) -> ModuleManifest:
    """构造 manifest：kits 每个元素一个平台条目（平台名 p0/p1/…，条目的 kit 字段）。
    kit 为空串 = 存量平台条目无套件身份（摘要行不显示套件段）。"""
    platforms = {
        f"p{index}": PlatformEntry(files=("a.c",), kit=kit)
        for index, kit in enumerate(kits)
    }
    return ModuleManifest(
        slug=slug,
        description=description,
        dependencies=deps,
        platforms=platforms,
        multi_instance=multi_instance,
    )


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


def _judgment_batches(
    files: Sequence[JudgmentFile],
) -> tuple[tuple[JudgmentFile, ...], ...]:
    """摘要阶段分批（镜像生产 _summarize_judgment_files 的调用参数）。"""
    return _batches(
        files,
        max_chars=MAX_SUMMARY_BATCH_CHARS,
        size_of=_file_chars,
        split_oversized=_split_versions,
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

    assert [s.to_line() for s in summaries] == [
        "- dht11: DHT11 温湿度传感器驱动（依赖: delay）",
        "- oled: OLED 屏显驱动",
    ]
    assert [s.slug for s in summaries] == ["dht11", "oled"]  # known_slugs 同源


def test_manifest_summaries_include_kit_segment_when_present():
    manifests = [
        _manifest("uwb", "UWB 测距模块驱动", deps=("delay",), kits=("地猛星 UWB 套件",)),
        _manifest("oled", "OLED 屏显驱动", kits=("OLED 套件",)),
    ]

    summaries = build_manifest_summaries(manifests)

    assert [s.to_line() for s in summaries] == [
        "- uwb: UWB 测距模块驱动（套件: 地猛星 UWB 套件; 依赖: delay）",
        "- oled: OLED 屏显驱动（套件: OLED 套件）",
    ]


def test_manifest_summaries_no_kit_segment_when_kit_missing():
    """存量平台条目无套件身份（kit 为空串）→ 套件段不显示，依赖段照旧。"""
    manifests = [
        _manifest("uwb", "UWB 测距模块驱动", deps=("delay",), kits=("",)),
        _manifest("motor", "电机驱动"),
    ]

    summaries = build_manifest_summaries(manifests)

    assert [s.to_line() for s in summaries] == [
        "- uwb: UWB 测距模块驱动（依赖: delay）",
        "- motor: 电机驱动",
    ]


def test_manifest_summaries_aggregate_distinct_kits_across_platforms():
    """多平台条目的 kit 聚合去重（保序）：AI 读到模块的全部套件身份，不重复。"""
    manifest = _manifest(
        "dht11",
        "DHT11 温湿度传感器驱动",
        deps=("delay",),
        kits=("STM32F103C8T6 最小系统板", "地猛星 MSPM0G3507 开发板", "STM32F103C8T6 最小系统板"),
    )

    summaries = build_manifest_summaries([manifest])

    assert [s.to_line() for s in summaries] == [
        "- dht11: DHT11 温湿度传感器驱动（套件: STM32F103C8T6 最小系统板、地猛星 MSPM0G3507 开发板; 依赖: delay）",
    ]
    assert summaries[0].kits == ("STM32F103C8T6 最小系统板", "地猛星 MSPM0G3507 开发板")


def test_manifest_summaries_empty_library_gives_empty_list():
    assert build_manifest_summaries([]) == []
    assert [s.slug for s in build_manifest_summaries([])] == []


def test_manifest_summaries_include_multi_instance_marker():
    """多实例能力进摘要行（工单 module-multi-instance/06）：带 multi_instance
    的 manifest 摘要行带「多实例」标注（上限 + 变体名）——AI 据此知道哪些
    模块可多实例、上限多少；不带该块的旧 manifest 行逐字节不变。"""
    summaries = build_manifest_summaries(
        [
            _manifest(
                "led", "LED 指示灯驱动",
                multi_instance=MultiInstanceSpec(max=8, variant="color"),
            ),
            _manifest("dht11", "温湿度"),
        ]
    )

    assert [s.to_line() for s in summaries] == [
        "- led: LED 指示灯驱动（多实例：上限 8，变体 = color）",
        "- dht11: 温湿度",
    ]
    assert summaries[0].multi_instance == MultiInstanceSpec(max=8, variant="color")
    assert summaries[1].multi_instance is None


def test_select_modules_receives_kit_in_summary_lines():
    """选模块请求的清单文本带套件信息；模型按新格式回 slug 能被正常解析
    （known_slugs 取 ManifestSummary.slug，与行渲染同源）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    summaries = build_manifest_summaries(
        [
            _manifest(
                "dht11",
                "DHT11 温湿度传感器驱动",
                deps=("delay",),
                kits=("地猛星 MSPM0G3507 开发板",),
            )
        ]
    )

    result = llm.select_modules("设计一个环境监测仪，测量温湿度", summaries)

    _, _, payload, _ = transport.calls[0]
    user_message = payload["messages"][1]["content"]
    assert (
        "- dht11: DHT11 温湿度传感器驱动"
        "（套件: 地猛星 MSPM0G3507 开发板; 依赖: delay）" in user_message
    )
    assert result.modules == ("dht11",)


def test_fake_llm_receives_manifest_summaries_with_kit():
    """FakeLLM 断言：喂给选模块 AI 的清单文本包含套件信息——记录型假 LLM
    （LLM 协议边界的系统边界假件）收到的清单行带套件段，AI 能据此分辨
    "哪个套件的 UWB"、看懂简介里的赛题专用性。"""
    class RecordingLLM:
        def __init__(self) -> None:
            self.received: list[tuple[str, ...]] = []

        def select_modules(
            self,
            problem_text: str,
            manifest_summaries: Sequence[ManifestSummary],
        ) -> ModuleSelection:
            self.received.append(tuple(s.to_line() for s in manifest_summaries))
            return ModuleSelection(modules=(), reasons={})

    fake = RecordingLLM()
    summaries = build_manifest_summaries(
        [
            _manifest("uwb", "UWB 测距模块驱动", kits=("地猛星 UWB 套件",)),
            _manifest("oled", "OLED 屏显驱动"),
        ]
    )

    fake.select_modules("赛题", summaries)

    assert "套件: 地猛星 UWB 套件" in fake.received[0][0]
    assert "套件" not in fake.received[0][1]  # 无 kit 的模块不显示套件段


# ---------------------------------------------------------------------------
# select_modules：请求形状 + 结构化输出解析
# ---------------------------------------------------------------------------


def test_select_modules_posts_chat_completion_with_expected_request():
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    problem = "设计一个环境监测仪，测量温湿度并显示"

    result = llm.select_modules(problem, [ManifestSummary("dht11", "温湿度传感器驱动")])

    url, headers, payload, timeout = transport.calls[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"
    assert headers["Content-Type"] == "application/json"
    assert payload["model"] == "deepseek-chat"
    assert payload["response_format"] == {"type": "json_object"}
    assert timeout == 300  # 判例 08：大批量判定 JSON 生成超 120 秒，超时放宽
    user_message = payload["messages"][1]["content"]
    assert problem in user_message
    assert "- dht11: 温湿度传感器驱动" in user_message
    assert "JSON" in user_message  # DeepSeek 的 json_object 模式要求提示词含 json

    assert result.modules == ("dht11",)
    assert result.reasons == {"dht11": "赛题要求采集温湿度"}


def test_select_modules_uses_configured_base_url_and_model():
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport, base_url="https://example.com/v1/", model="deepseek-reasoner")

    llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    url, _, payload, _ = transport.calls[0]
    assert url == "https://example.com/v1/chat/completions"
    assert payload["model"] == "deepseek-reasoner"


def test_select_modules_empty_selection_is_valid():
    transport = FakeTransport(body=_api_response(json.dumps({"modules": []})))
    llm = _llm(transport)

    result = llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert result.modules == ()
    assert result.reasons == {}


def test_select_modules_http_error_raises_with_status():
    transport = FakeTransport(status=401, body="invalid api key")
    llm = _llm(transport)

    with pytest.raises(LLMError, match="401"):
        llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])


def test_select_modules_invalid_json_response_raises():
    transport = FakeTransport(body="{not json")
    llm = _llm(transport)

    with pytest.raises(LLMError, match="JSON"):
        llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])


def test_select_modules_missing_content_field_raises():
    transport = FakeTransport(body=json.dumps({"choices": []}))
    llm = _llm(transport)

    with pytest.raises(LLMError, match="content"):
        llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])


# select_modules 整次重试兜底（工单 recommend-call-retry/01）：DeepSeek 偶发
# 空内容（真机 2026C 实测）→ 自动重问，不再一枪毙命


def test_select_modules_retries_on_empty_content_then_succeeds():
    """瞬时空内容响应 → 整次重问（最多 SUMMARY_RETRY_LIMIT 轮）→ 成功。"""
    transport = SequenceTransport(
        [_api_response(""), _api_response(""), _api_response(SELECTION_JSON)]
    )
    llm = _llm(transport)

    result = llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert result.modules == ("dht11",)
    assert len(transport.calls) == 3  # 空内容 2 次 + 成功 1 次


def test_select_modules_exhausts_retries_on_empty_content():
    """全部空内容 → 大声失败（错误文案含"连续"，语义保留在末次失败里）。"""
    transport = SequenceTransport([_api_response("")] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)

    with pytest.raises(LLMError, match=f"模块选择连续 {SUMMARY_RETRY_LIMIT} 次调用失败"):
        llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])
    assert len(transport.calls) == SUMMARY_RETRY_LIMIT


def test_select_modules_retries_on_malformed_json_then_succeeds():
    """畸形输出（非 JSON）同样整次重问，直到解析通过。"""
    transport = SequenceTransport([_api_response("{not json"), _api_response(SELECTION_JSON)])
    llm = _llm(transport)

    result = llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert result.modules == ("dht11",)
    assert len(transport.calls) == 2


def test_select_modules_retries_when_selection_rejected():
    """SelectionError 路径在重试覆盖内：域判决拒绝（未知 slug）→ 翻译成
    LLMError → 整次重问 → 成功。"""
    transport = SequenceTransport(
        [
            _api_response(json.dumps({"modules": [{"slug": "ghost", "reason": "x"}]})),
            _api_response(SELECTION_JSON),
        ]
    )
    llm = _llm(transport)

    result = llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert result.modules == ("dht11",)
    assert len(transport.calls) == 2


# ---------------------------------------------------------------------------
# 网络类退避重试（工单 deepseek-retry-hardening/01）：LLMError 分网络 /
# 解析两类——网络瞬断（连接重置 / URLError / 网关 5xx）5 次指数退避
# （1/2/4/8s），解析类（空内容 / 畸形 JSON）保持 3 次快重试。
# 红证先行：改前形态（无类别标记）下网络类 3 次即抛、零 sleep。
# ---------------------------------------------------------------------------


def _record_backoff_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """monkeypatch llm._backoff_sleep 记录退避序列（测试不可真睡 1+2+4+8s）。"""
    sleeps: list[float] = []
    monkeypatch.setattr(llm_module, "_backoff_sleep", sleeps.append)
    return sleeps


class _NetworkFailureTransport(FakeTransport):
    """每次调用都抛网络类 LLMError（模拟 UrllibTransport 的转换产物：连接
    重置 / URLError / OSError → LLMError(kind=network)）。"""

    def post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> tuple[int, str]:
        self.calls.append((url, headers, payload, timeout))
        raise LLMError("无法连接 LLM 服务：连接重置", kind=ERROR_KIND_NETWORK)


class _FlakyNetworkTransport(FakeTransport):
    """前 n 次调用抛网络类 LLMError，之后正常（测退避后成功）。"""

    def __init__(self, body: str, failures: int) -> None:
        super().__init__(body=body)
        self._failures = failures

    def post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> tuple[int, str]:
        self.calls.append((url, headers, payload, timeout))
        if len(self.calls) <= self._failures:
            raise LLMError("无法连接 LLM 服务：连接重置", kind=ERROR_KIND_NETWORK)
        return self.status, self.body


def test_llm_error_kind_defaults_to_parse():
    """kind 缺省 parse（向后兼容：存量单参构造的 LLMError 全部按解析类处理）。"""
    assert LLMError("boom").kind == "parse"
    assert LLMError("boom", kind="network").kind == "network"


def test_select_modules_network_failure_exhausts_with_backoff(monkeypatch):
    """网络类失败 → NETWORK_RETRY_LIMIT 次尝试 + 指数退避（1/2/4/8s），
    失败文案随实际次数变化（连续 5 次）。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = _NetworkFailureTransport()
    llm = _llm(transport)

    with pytest.raises(LLMError, match="模块选择连续 5 次调用失败"):
        llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert len(transport.calls) == NETWORK_RETRY_LIMIT  # 5
    assert sleeps == [1.0, 2.0, 4.0, 8.0]  # 退避序列钉死


def test_select_modules_http_5xx_uses_network_backoff(monkeypatch):
    """网关 5xx 与连接失败同策略：5 次退避重试（4xx 不在此列，见 401 用例）。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = _FlakyTransport(body=_api_response(SELECTION_JSON), failures=9)
    llm = _llm(transport)

    with pytest.raises(LLMError, match="模块选择连续 5 次调用失败"):
        llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert len(transport.calls) == NETWORK_RETRY_LIMIT
    assert sleeps == [1.0, 2.0, 4.0, 8.0]


def test_select_modules_network_failures_then_success(monkeypatch):
    """混合：前 2 次网络失败后退避 → 第 3 次成功（退避后正常返回）。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = _FlakyNetworkTransport(body=_api_response(SELECTION_JSON), failures=2)
    llm = _llm(transport)

    result = llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert result.modules == ("dht11",)
    assert len(transport.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_select_modules_parse_failures_stay_fast_retries(monkeypatch):
    """解析类（空内容）保持 SUMMARY_RETRY_LIMIT 次快重试：零 sleep（策略分派不误伤解析类）。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = SequenceTransport([_api_response("")] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)

    with pytest.raises(LLMError, match=f"模块选择连续 {SUMMARY_RETRY_LIMIT} 次调用失败"):
        llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    assert len(transport.calls) == SUMMARY_RETRY_LIMIT
    assert sleeps == []


def test_urllib_transport_marks_network_errors(monkeypatch):
    """传输层网络异常（URLError / OSError）→ LLMError(kind=network)——
    转换点是 _retry_parse 分策略的依据（红证：旧实现无类别标记）。"""
    transport = UrllibTransport()
    for exc in (
        urllib.error.URLError("timeout"),
        ConnectionResetError(10054, "连接被重置"),
    ):
        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda *args, **kwargs: (_ for _ in ()).throw(exc),
        )
        with pytest.raises(LLMError) as caught:
            transport.post("https://api.deepseek.com/chat/completions", {}, {"m": []}, 300)
        assert caught.value.kind == ERROR_KIND_NETWORK


# ---------------------------------------------------------------------------
# 澄清阶段（工单 01 推荐先澄清后收敛）：只看题面 + 问答历史，输出仍存疑问
# ---------------------------------------------------------------------------


def test_clarify_posts_chat_completion_with_history():
    """请求形状：CLARIFY_SYSTEM_PROMPT + 题面与逐条 Q/A 历史的用户消息
    （json_mode）；返回解析后的疑问列表。"""
    transport = FakeTransport(
        body=_api_response(json.dumps({"questions": ["识别方式？"]}))
    )
    llm = _llm(transport)
    problem = "设计一个识别数字的送药小车"

    result = llm.clarify(problem, [("识别方式？", "摄像头")])

    url, headers, payload, timeout = transport.calls[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert headers["Authorization"] == "Bearer sk-test"
    assert payload["model"] == "deepseek-chat"
    assert payload["response_format"] == {"type": "json_object"}
    assert timeout == 300
    assert payload["messages"][0]["content"] == CLARIFY_SYSTEM_PROMPT
    user_message = payload["messages"][1]["content"]
    assert problem in user_message
    assert "Q: 识别方式？" in user_message
    assert "A: 摄像头" in user_message
    assert "JSON" in user_message  # DeepSeek 的 json_object 模式要求提示词含 json

    assert result == ("识别方式？",)


def test_clarify_empty_questions_means_done():
    """空 questions 数组 / 缺省 questions → 空元组（澄清完成，进收敛）。"""
    for body in (json.dumps({"questions": []}), json.dumps({})):
        transport = FakeTransport(body=_api_response(body))
        assert _llm(transport).clarify("赛题", []) == ()


@pytest.mark.parametrize(
    "bad_content",
    [
        json.dumps({"questions": "识别方式？"}),
        json.dumps({"questions": [123]}),
        json.dumps({"questions": [""]}),
        "{not json",
        json.dumps([1, 2]),
    ],
)
def test_clarify_rejects_malformed_output(bad_content):
    """畸形输出（非 JSON / 顶层非对象 / questions 非字符串数组）→ LLMError——
    宁可大声失败也不带病进收敛循环（与其它 AI 契约同哲学）。"""
    transport = FakeTransport(body=_api_response(bad_content))
    with pytest.raises(LLMError):
        _llm(transport).clarify("赛题", [])


# clarify 整次重试兜底（工单 recommend-call-retry/01）：与 select_modules 同款
# _retry_parse，空内容 / 畸形输出自动重问，不再一枪毙命


def test_clarify_retries_on_empty_content_then_succeeds():
    """瞬时空内容响应 → 整次重问 → 成功解析疑问。"""
    transport = SequenceTransport(
        [
            _api_response(""),
            _api_response(""),
            _api_response(json.dumps({"questions": ["识别方式？"]})),
        ]
    )
    llm = _llm(transport)

    result = llm.clarify("赛题", [("识别方式？", "摄像头")])

    assert result == ("识别方式？",)
    assert len(transport.calls) == 3  # 空内容 2 次 + 成功 1 次


def test_clarify_exhausts_retries_on_empty_content():
    """全部空内容 → 大声失败（错误文案含"连续"）。"""
    transport = SequenceTransport([_api_response("")] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)

    with pytest.raises(LLMError, match=f"澄清连续 {SUMMARY_RETRY_LIMIT} 次调用失败"):
        llm.clarify("赛题", [])
    assert len(transport.calls) == SUMMARY_RETRY_LIMIT


def test_clarify_prompt_contract():
    """澄清系统提示词契约：逐句核对题面、证据不足才补问、不重复已答问题、
    无疑问输出空 questions 数组（机械提取层把行为要点写死在提示词）。"""
    assert "逐句核对" in CLARIFY_SYSTEM_PROMPT
    assert "证据不足" in CLARIFY_SYSTEM_PROMPT
    assert "不要重复问" in CLARIFY_SYSTEM_PROMPT
    assert "空 questions 数组" in CLARIFY_SYSTEM_PROMPT
    assert TRUNCATION_NOTICE in CLARIFY_SYSTEM_PROMPT


def test_clarify_truncates_oversized_problem():
    """超大赛题文本同样截断（带标注）：澄清调用也不会让请求体超限。"""
    transport = FakeTransport(
        body=_api_response(json.dumps({"questions": []}))
    )
    llm = _llm(transport)

    llm.clarify("赛题" * (EMBEDDED_CONTENT_CAP + 100), [])

    _, _, payload, _ = transport.calls[0]
    message = payload["messages"][1]["content"]
    assert len(message) < EMBEDDED_CONTENT_CAP + 1000
    assert "截断" in message
    assert TRUNCATION_NOTICE in message


def test_parse_clarify_questions_pure_parse():
    """解析函数直测：空数组 → 空元组；缺省 → 空元组；字符串数组原样返回。"""
    assert parse_clarify_questions('{"questions": []}') == ()
    assert parse_clarify_questions("{}") == ()
    assert parse_clarify_questions('{"questions": ["a", "b"]}') == ("a", "b")


# ---------------------------------------------------------------------------
# 编译错误修复（工单 compile-error-fix/01）：提示词契约 + 严格解析
# ---------------------------------------------------------------------------


def test_fix_system_prompt_contract():
    """契约测试：修复提示词带截断标注（与所有嵌内容调用同款，双端断言）。"""
    assert TRUNCATION_NOTICE in FIX_SYSTEM_PROMPT
    # 替换协议的关键约束（决策记录 4）在系统提示词里有唯一表述：精确匹配、
    # 唯一匹配、file 限清单内
    assert "逐字一致" in FIX_SYSTEM_PROMPT
    assert "唯一匹配" in FIX_SYSTEM_PROMPT
    assert "文件清单" in FIX_SYSTEM_PROMPT
    # 回喂约束（工单 fix-loop-progress/01 决策记录 2，约束 6）：看到上一轮
    # 未应用原因时对齐重试或放弃，不重复输出相同建议
    assert "上一轮修复应用结果" in FIX_SYSTEM_PROMPT
    assert "不要重复输出与上一轮一模一样的" in FIX_SYSTEM_PROMPT


def test_fix_system_prompt_warning_guidance():
    """告警修复指引（工单 fix-loop-warnings/01，约束 7）：编译输出中的 Warning
    条目同样逐条修复——未使用变量 / 函数删声明或补引用、告警指出实质问题的
    照修；第三方库 / 模块自带警告不瞎改。红证：现行提示词无 warning 指引
    （0 错 N 警即停，警告永不进修复轮）。"""
    assert "Warning" in FIX_SYSTEM_PROMPT
    assert "未使用变量" in FIX_SYSTEM_PROMPT
    assert "不瞎改" in FIX_SYSTEM_PROMPT


def test_fix_errors_user_prompt_embeds_contexts():
    prompt = _fix_errors_user_prompt(
        error_text="main.c(1): error #20: boom",
        file_contexts={"main.c": "int x = 1;\n"},
        problem_text="赛题：做个小车",
        platform="stm32",
        module_slugs=("dht11", "oled"),
        main_c="int main(void) { return 0; }",
    )
    assert "main.c(1): error #20: boom" in prompt
    assert "=== main.c ===" in prompt
    assert "int x = 1;" in prompt
    assert "赛题：做个小车" in prompt and "stm32" in prompt
    assert "dht11、oled" in prompt
    assert "int main(void)" in prompt


def test_fix_errors_user_prompt_degraded_mode_notes_no_files():
    prompt = _fix_errors_user_prompt(error_text="error #20: boom", file_contexts={})
    assert "未定位到可读取的源码文件" in prompt
    assert "精确匹配" in prompt  # 降级模式仍要求精确 old_snippet


def test_fix_errors_user_prompt_previous_fixes_section():
    """回喂段（工单 fix-loop-progress/01）：独立段标题固定，逐条 file:line +
    status + reason 在场；位置在文件上下文之后、工程上下文之前。"""
    prompt = _fix_errors_user_prompt(
        error_text="main.c(1): error #20: boom",
        file_contexts={"main.c": "int x = 1;\n"},
        previous_fixes=(
            {
                "file": "main.c",
                "line": 1,
                "status": "skipped",
                "reason": "未应用：文件内未找到 old_snippet（精确匹配失败，可能缩进 / 内容不一致）",
            },
            {
                "file": "code/mod.c",
                "line": 45,
                "status": "applied",
                "reason": "按行首前缀归一化匹配应用",
            },
        ),
    )
    assert "【上一轮修复应用结果】" in prompt
    assert "main.c:1 skipped：未应用：文件内未找到 old_snippet（精确匹配失败，可能缩进 / 内容不一致）" in prompt
    assert "code/mod.c:45 applied：按行首前缀归一化匹配应用" in prompt
    # 段位置：文件上下文之后、约束（工程上下文）之前（实施注固定，测试断言）
    assert prompt.index("=== main.c ===") < prompt.index("【上一轮修复应用结果】")
    assert prompt.index("【上一轮修复应用结果】") < prompt.index("【工程上下文】")


def test_fix_errors_user_prompt_empty_previous_zero_regression():
    """空列表 = 无回喂段（零回归）：全参提示词与旧行为逐字节一致（验收：空
    列表提示词零回归）。"""
    prompt = _fix_errors_user_prompt(
        error_text="main.c(1): error #20: boom",
        file_contexts={"main.c": "int x = 1;\n"},
        problem_text="赛题：做个小车",
        platform="stm32",
        module_slugs=("dht11", "oled"),
        main_c="int main(void) { return 0; }",
        previous_fixes=(),
    )
    assert "【上一轮修复应用结果】" not in prompt
    expected = "\n\n".join(
        [
            "【编译报错全文】",
            "main.c(1): error #20: boom",
            "【输出目录内文件内容】",
            "=== main.c ===\nint x = 1;\n",
            "【工程上下文】",
            "赛题原文：\n赛题：做个小车",
            "目标平台：stm32",
            "选中模块：dht11、oled",
            "main.c：\nint main(void) { return 0; }",
        ]
    )
    assert prompt == expected


def test_fix_errors_user_prompt_previous_fixes_capped():
    """回喂段级截断（工单 fix-request-budget/01）：海量 previous_fixes → 段级
    合计截头带标注（truncate_content 单源，与澄清历史同哲学），不再 N×~150
    字符无界增长；标题与首条保留（首条 = 最近的上一轮结果），尾部条目裁掉。
    条目数在限内时不截断（零回归由既有逐字节测试钉死）。"""
    entries = tuple(
        {
            "file": f"code/mod_{i}.c",
            "line": 10 + i,
            "status": "skipped",
            "reason": "未" * 200,
        }
        for i in range(60)
    )
    prompt = _fix_errors_user_prompt(
        error_text="main.c(1): error #20: boom",
        file_contexts={"main.c": "int x = 1;\n"},
        previous_fixes=entries,
    )
    assert "【上一轮修复应用结果】" in prompt  # 标题保留（截断只裁段体）
    assert "code/mod_0.c:10 skipped：未未未" in prompt  # 截头：首条仍在
    assert "code/mod_59.c" not in prompt  # 尾部条目被裁掉
    assert "内容过长，已截断" in prompt  # 截断标注（truncate_content 单源措辞）
    assert f"仅展示前 {FIX_PREVIOUS_FIXES_CAP} 字符" in prompt
    # 段体长度 ≤ cap + 标注（结构保证链上的确定性上界）
    segment = prompt.split("【上一轮修复应用结果】")[1].split("【工程上下文】")[0]
    assert len(segment) <= FIX_PREVIOUS_FIXES_CAP + 80


def test_fix_prompt_worst_case_fits_request_budget(tmp_path):
    """结构测试（工单 fix-request-budget/01 唯一硬保证，红证先行）：最坏形态
    修复请求——文件上下文（全中文巨型文件，真实走 read_file_contexts 预算
    截断）+ 报错全文 4000 + 赛题 4000 + main.c 4000 + previous_fixes 海量条
    + dropped 清单 + 模块清单——完整 payload 按 json.dumps 序列化（对齐
    llm._chat 预检口径：中文 \\uXXXX 转义 6 字节/字符，不继承 select 测试的
    prompt.encode 3 字节口径）≤ MAX_REQUEST_BYTES，余量 ≥ 10KB；文件上下文
    预算改大即红（红证：现行 49152 字符口径最坏 ≈373KB 单段超总量 2×+）。
    """
    # 文件上下文最坏形态：全中文文件（每行 50 中文 × 3000 行）——单文件 500
    # 行截断后仍远超总量预算，必须真实走 read_file_contexts 的预算截断路径
    (tmp_path / "big.c").write_text(
        "\n".join("中" * 50 for _ in range(3000)), encoding="utf-8"
    )
    contexts, dropped = read_file_contexts(tmp_path, ("big.c",))

    prompt = _fix_errors_user_prompt(
        error_text="错" * 5000,  # 超 4000 截断（带标注）的最坏形态
        file_contexts=dict(contexts),
        # dropped 清单最坏形态（数百条，工单定夺不强加上限）：报错路径派生，
        # 实测 KB 级，结构测试按数百条覆盖
        dropped_files=tuple(f"code/mod_{i}_driver.c" for i in range(200)),
        problem_text="设" * 4000,  # 赛题截断上限（2026C 实测 2626 / 2021F 2796 都在此上限内）
        platform="stm32",
        module_slugs=tuple(f"mod_{i}_driver" for i in range(40)),
        main_c="主" * 5000,  # 超 4000 截断（带标注）的最坏形态
        previous_fixes=tuple(
            {
                "file": f"code/mod_{i}.c",
                "line": 10 + i,
                "status": "skipped",
                "reason": "未" * 200,
            }
            for i in range(60)
        ),
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": FIX_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    total = len(json.dumps(payload).encode("utf-8"))
    assert total <= MAX_REQUEST_BYTES - 10 * 1024
    assert "上下文预算限制" in prompt  # 文件上下文真实走了总量预算截断
    assert f"仅展示前 {FIX_PREVIOUS_FIXES_CAP} 字符" in prompt  # 回喂段合计截断带标注


def test_parse_fix_suggestions_pure_parse():
    content = json.dumps(
        {
            "fixes": [
                {
                    "file": "main.c",
                    "line": 1,
                    "old_snippet": "int x = 1;",
                    "new_snippet": "int x = 2;",
                    "reason": "变量初始化改值",
                },
                {
                    "file": "code/mod.c",
                    "line": 45,
                    "old_snippet": "bad_line();",
                    "new_snippet": "",
                    "reason": "删除整行",
                },
            ]
        }
    )
    fixes = parse_fix_suggestions(content, ("main.c", "code/mod.c"))
    assert fixes == (
        FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;", new_snippet="int x = 2;", reason="变量初始化改值"),
        FixSuggestion(file="code/mod.c", line=45, old_snippet="bad_line();", new_snippet="", reason="删除整行"),
    )


def test_parse_fix_suggestions_empty_is_valid():
    """空 fixes / 缺 fixes = 无修复（合法终态，不重问）。"""
    assert parse_fix_suggestions('{"fixes": []}', ("main.c",)) == ()
    assert parse_fix_suggestions("{}", ("main.c",)) == ()


@pytest.mark.parametrize(
    "bad_content",
    [
        "{not json",
        json.dumps([1, 2]),  # 非对象
        json.dumps({"fixes": "x"}),  # fixes 非数组
        json.dumps({"fixes": [{"file": "other.c", "line": 1, "old_snippet": "a", "new_snippet": "b", "reason": ""}]}),  # file 不在清单
        json.dumps({"fixes": [{"file": "../evil.c", "line": 1, "old_snippet": "a", "new_snippet": "b", "reason": ""}]}),  # 越界路径也拒（清单外）
        json.dumps({"fixes": [{"file": "main.c", "line": "x", "old_snippet": "a", "new_snippet": "b", "reason": ""}]}),  # line 非数字
        json.dumps({"fixes": [{"file": "main.c", "line": 1, "old_snippet": "", "new_snippet": "b", "reason": ""}]}),  # old_snippet 空
        json.dumps({"fixes": [{"file": "main.c", "line": 1, "old_snippet": "a", "new_snippet": "b"}]}),  # 缺 reason
    ],
)
def test_parse_fix_suggestions_rejects_malformed(bad_content):
    """畸形输出抛 LLMError（模型输出不可信，宁可大声失败也不带病进写回流程）。"""
    with pytest.raises(LLMError):
        parse_fix_suggestions(bad_content, ("main.c",))


# ---------------------------------------------------------------------------
# 结构化输出解析（纯函数）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_content",
    [
        "{not json",
        json.dumps([1, 2]),
        json.dumps("字符串"),
    ],
)
def test_extract_module_selection_data_rejects_non_json_or_non_object(bad_content):
    """机械形状提取（工单 06）：非 JSON / 顶层非对象 → LLMError（只这两处；
    语义校验——缺模块数组 / 缺 slug / 字段类型——在 selection 侧）。"""
    with pytest.raises(LLMError):
        extract_module_selection_data(bad_content)


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


def test_skeleton_prompt_carries_no_unused_var_rule():
    """契约测试：骨架「不声明未使用变量」约束双端同源（SKELETON_NO_UNUSED_RULE 唯一出处）。

    ticket 06 的双端漂移教训：判定范围曾只改系统提示词、漏改用户提示词——模型按
    用户消息行事当场失败。骨架同款风险：用户消息尾句「保证可编译」是模型最直接
    读到的指令，未用变量规则只写系统提示词会被尾句盖过（真机 2026C 曾出 UV4
    4 警：s_lock_state / s_welcome_state / s_zone_state / s_expect_id 占位声明未用，
    #177-D / #550-D，违背 0 错 0 警验收）。改规则只动常量（契约测试双端断言）。
    """
    user_prompt = _skeleton_user_prompt("赛题", ("x.h",))

    assert SKELETON_NO_UNUSED_RULE in SKELETON_SYSTEM_PROMPT
    assert SKELETON_NO_UNUSED_RULE in user_prompt
    assert "未使用的变量" in SKELETON_NO_UNUSED_RULE
    assert "占位声明" in SKELETON_NO_UNUSED_RULE
    assert "不要带 code/、modules/ 等目录前缀" in user_prompt


def test_generate_main_skeleton_forwards_reference_fulltexts():
    """DeepSeekLLM.generate_main_skeleton 把参考全文透传进 user 消息。"""
    transport = FakeTransport(body=_api_response("int main(void) { /* TODO */ }"))
    llm = _llm(transport)

    llm.generate_main_skeleton("赛题", ["x.h"], {"r1": "巡线决策源码"})

    _, _, payload, _ = transport.calls[0]
    user_message = payload["messages"][1]["content"]
    assert "### 参考资料 r1" in user_message
    assert "巡线决策源码" in user_message


def test_skeleton_prompt_with_references_adds_section_and_rewrite_rule():
    """参考实现进骨架：非空 reference_fulltexts → 参考段 + 改写约束；空/None = 零回归。"""
    base = _skeleton_user_prompt("赛题", ("x.h",))
    with_refs = _skeleton_user_prompt("赛题", ("x.h",), {"ref-1": "巡线决策源码"})

    assert "赛题" in with_refs and "x.h" in with_refs
    assert with_refs.index("### 参考资料") > with_refs.index("x.h")
    assert "### 参考资料 ref-1" in with_refs
    assert "巡线决策源码" in with_refs
    assert "适配当前所选模块接口" in with_refs
    assert "保持 TODO" in with_refs
    assert _skeleton_user_prompt("赛题", ("x.h",), None) == base
    assert _skeleton_user_prompt("赛题", ("x.h",), {}) == base


def test_generate_smoke_main_routes_to_smoke_prompts():
    """自检冒烟职责走独立系统/用户提示词，不经骨架提示词。"""
    transport = FakeTransport(body=_api_response("int main(void) { /* smoke */ }"))
    llm = _llm(transport)
    interfaces = ["### 模块 oled（inc/oled.h）\n#pragma once\nvoid oled_init(void);"]

    smoke = llm.generate_smoke_main("赛题", interfaces)

    assert smoke == "int main(void) { /* smoke */ }"
    _, _, payload, _ = transport.calls[0]
    system_message = payload["messages"][0]["content"]
    user_message = payload["messages"][1]["content"]
    assert "自检" in system_message
    assert "初始化" in system_message
    assert "赛题" in user_message
    assert "void oled_init(void);" in user_message
    assert "为赛题生成 main.c 骨架" not in system_message  # 冒烟不写赛题逻辑，与骨架提示词分家


def test_smoke_prompt_carries_channel_and_per_module_rules():
    """契约测试：冒烟用户提示词含 OLED 为主 / 串口为辅 + 逐模块自检 + 无平台版本留注释。"""
    user_prompt = _smoke_user_prompt("赛题", ("x.h",))

    assert "OLED" in user_prompt
    assert "debug_uart" in user_prompt
    assert "逐段显示" in user_prompt or "OLED 上" in user_prompt
    assert "串口" in user_prompt
    assert "不要用 printf/sprintf/snprintf" in user_prompt
    assert "debug_uart_send" in user_prompt
    assert "每个所选模块" in user_prompt
    assert "无平台 XX 版本" in user_prompt
    assert "照接口块里的平台名写" in user_prompt
    assert "不要带 code/、modules/ 等目录前缀" in user_prompt
    assert SKELETON_NO_UNUSED_RULE in SMOKE_SYSTEM_PROMPT
    assert SKELETON_NO_UNUSED_RULE in user_prompt

def test_generate_main_skeleton_retries_empty_content_then_succeeds():
    """骨架出稿也走 _retry_parse：空内容自动重问，成功后返回正文。"""
    transport = SequenceTransport(
        [_api_response(""), _api_response(""), _api_response("int main(void) {}")]
    )
    llm = _llm(transport)

    result = llm.generate_main_skeleton("赛题", ["x.h"])

    assert result == "int main(void) {}"
    assert len(transport.calls) == 3  # 空内容 2 次 + 成功 1 次


def test_generate_main_skeleton_exhausts_retries_on_empty_content():
    """骨架出稿连续空内容 → 按 SUMMARY_RETRY_LIMIT 大声失败。"""
    transport = SequenceTransport(
        [_api_response("")] * SUMMARY_RETRY_LIMIT
    )
    llm = _llm(transport)

    with pytest.raises(
        LLMError, match=f"骨架 main.c 生成连续 {SUMMARY_RETRY_LIMIT} 次调用失败"
    ):
        llm.generate_main_skeleton("赛题", ["x.h"])
    assert len(transport.calls) == SUMMARY_RETRY_LIMIT


def test_generate_smoke_main_retries_empty_content_then_succeeds():
    """冒烟出稿同款兜底：空内容自动重问。"""
    transport = SequenceTransport(
        [_api_response(""), _api_response("int main(void) { /* smoke */ }")]
    )
    llm = _llm(transport)

    result = llm.generate_smoke_main("赛题", ["x.h"])

    assert result == "int main(void) { /* smoke */ }"
    assert len(transport.calls) == 2  # 空内容 1 次 + 成功 1 次


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


def test_validation_prompts_share_universality_rule():
    """契约测试：判据③④双端同源（VALIDATION_UNIVERSALITY_RULE 唯一出处）。

    ticket 06 的双端漂移教训：判定范围曾只改系统提示词、漏改用户提示词——校验
    提示词的判据③④（能力方向 / 无题绑定，ADR 0009）同理：只改一侧会让模型在
    另一侧消息里漏掉这项检查，简介的普适性失去可信度。改判据只动常量（契约
    测试双端断言）。
    """
    user_prompt = _validation_user_prompt("2026C 题专用锁逻辑", "int lock(void);")

    assert VALIDATION_UNIVERSALITY_RULE in VALIDATION_SYSTEM_PROMPT
    assert VALIDATION_UNIVERSALITY_RULE in user_prompt
    assert "能力方向" in VALIDATION_UNIVERSALITY_RULE
    assert "无题绑定" in VALIDATION_UNIVERSALITY_RULE


def test_validate_module_description_posts_universality_rule():
    """实际发出的校验请求（系统 + 用户消息）都带判据③④要求。"""
    transport = FakeTransport(
        body=_api_response(json.dumps({"consistent": True, "issues": ""}))
    )
    llm = _llm(transport)

    llm.validate_module_description("2026C 题专用锁逻辑", "int lock(void);")

    _, _, payload, _ = transport.calls[0]
    user_message = payload["messages"][1]["content"]
    assert VALIDATION_UNIVERSALITY_RULE in user_message
    system_message = payload["messages"][0]["content"]
    assert VALIDATION_UNIVERSALITY_RULE in system_message


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

    # 素材范围外的判定（ui/oled_fonts.c 不在 JUDGMENT_FILES）被过滤丢弃
    assert len(decisions) == 2
    assert {d.path for d in decisions} == {"src/oled.c", "sensors/dht11.c"}
    assert decisions[0] == FileDecision(
        "src/oled.c",
        ACTION_MERGE,
        content="/* 整合产物 */\n",
        explanation="两版合并去重",
        source="proj-a",
        reason="A 的 include path 更全",
    )


def test_distill_prompts_share_judgment_scope():
    """契约测试：系统提示词与用户提示词对判定范围说同一件事。

    ticket 06 曾只改系统提示词、漏改用户提示词——模型按用户消息跳过公共文件，
    多工程提炼当场失败（"提炼报告缺少判定"）。判定范围表述必须来自同一常量
    （JUDGMENT_SCOPE），且旧判据 / 旧判定范围的表述不得重新出现：出现即说明
    有人改了单点、漏了另一处。
    """
    user_prompt = _distill_user_prompt(
        "stm32", ("proj-a",), (), "结构与配置对比"
    )

    assert JUDGMENT_SCOPE in DISTILL_SYSTEM_PROMPT
    assert JUDGMENT_SCOPE in user_prompt
    for stale in ("公共文件已确定保留", "只判定冲突与独有文件", "是否通用（不依赖具体赛题）"):
        assert stale not in DISTILL_SYSTEM_PROMPT
        assert stale not in user_prompt
    # 第一阶段摘要的素材范围描述同样覆盖公共文件（判定范围 = 公共 + 冲突 + 独有）
    assert "公共" in JUDGMENT_SUMMARY_SYSTEM_PROMPT


def test_summarize_prompt_caps_oversized_content():
    """巨型判定素材（判例 08：stm32f10x.h ~800KB 标准库头）第一阶段提示词只嵌入
    文件头截断、不全文搬运——截断标记注明原文长度，模型不会误判文件规模；截断
    只影响提示词，keep 落盘仍复制工程原文全文。"""
    transport = SequenceTransport(
        [
            _api_response(
                json.dumps(
                    {
                        "summaries": [
                            {
                                "path": "sys/stm32f10x.h",
                                "versions": [
                                    {
                                        "projects": ["proj-a"],
                                        "summary": "STM32 标准外设库头文件",
                                    }
                                ],
                            }
                        ]
                    }
                )
            ),
            _api_response(
                json.dumps(
                    {
                        "decisions": [
                            {
                                "path": "sys/stm32f10x.h",
                                "action": ACTION_KEEP,
                                "reason": "STM32 标准外设库头文件，基础必需",
                            }
                        ]
                    }
                )
            ),
        ]
    )
    llm = _llm(transport)
    big_content = "/* stm32f10x.h */\n" + "x" * 20_000
    files = (JudgmentFile("sys/stm32f10x.h", (FileVersion(big_content, ("proj-a",)),)),)

    llm.distill_master("stm32", ("proj-a",), files, "对比摘要")

    _, _, payload, _ = transport.calls[0]
    message = payload["messages"][1]["content"]
    assert "sys/stm32f10x.h" in message
    assert "x" * 20_000 not in message  # 全文不搬运
    assert "内容过长，已截断" in message
    assert "20" in message  # 截断标记注明原文长度


# ---------------------------------------------------------------------------
# 请求体大小控制：截断 + 分批 + 体积断言（413 修复）
# ---------------------------------------------------------------------------


def test_truncate_content_caps_oversized_with_marker():
    """超长内容截断到预算并带标注（AI 知道读到的是截断内容）；未超长原样返回。"""
    content = "x" * (EMBEDDED_CONTENT_CAP + 1000)

    truncated = _truncate_content(content)

    assert truncated.startswith(content[:EMBEDDED_CONTENT_CAP])
    assert "截断" in truncated
    assert "不要脑补" in truncated
    assert len(truncated) < EMBEDDED_CONTENT_CAP + 200
    assert _truncate_content("short") == "short"


def test_judgment_batches_splits_by_budget():
    """分批按内容字符预算：批内合计不超预算，顺序保持输入顺序。

    文件都在截断上限之下（3900 < 4000），预算约束单独生效：6 份合计 23400
    恰在预算内，第 7 份会超——拆成 6+1 两批。
    """
    files = tuple(
        JudgmentFile(f"{index}.c", (FileVersion("x" * 3900, ("p1",)),))
        for index in range(7)
    )

    batches = _judgment_batches(files)

    assert batches == ((files[0], files[1], files[2], files[3], files[4], files[5]), (files[6],))
    assert _judgment_batches(()) == ()


def test_judgment_batches_respects_file_count_cap(monkeypatch):
    """文件数上限（JUDGMENT_BATCH_SIZE）与预算双约束：小文件时按文件数拆批。

    判例 08 的文件数上限是模型可靠性约束（一次问太多文件系统性漏判小配置
    文件），413 的预算约束是请求体上限——两者同时成立。
    """
    import contest_generator.llm as llm_module

    monkeypatch.setattr(llm_module, "JUDGMENT_BATCH_SIZE", 2)
    files = tuple(
        JudgmentFile(f"{index}.c", (FileVersion("/* x */", ("p1",)),))
        for index in range(5)
    )

    batches = _judgment_batches(files)

    assert all(len(batch) <= 2 for batch in batches)
    assert tuple(len(batch) for batch in batches) == (2, 2, 1)
    assert [f.path for batch in batches for f in batch] == [f"{i}.c" for i in range(5)]


def test_judgment_batches_splits_multi_version_file():
    """单文件多版本合计超预算时按版本拆批：批预算不变量仍成立。

    8 个工程同路径内容不同（如各自不同的 main.c）→ 同一路径 8 个内容版本，
    截断后合计远超预算——必须拆批且批内路径不重复（parse_summary_report 按
    路径校验批次覆盖），版本不丢、顺序保持输入顺序。
    """
    file = JudgmentFile(
        "main.c",
        tuple(
            FileVersion(f"/* v{index} */\n" + "x" * 8000, (f"p{index}",))
            for index in range(8)
        ),
    )

    batches = _judgment_batches((file,))

    assert len(batches) > 1
    for batch in batches:
        batch_size = sum(
            len(_truncate_content(version.content))
            for batch_file in batch
            for version in batch_file.versions
        )
        assert batch_size <= MAX_SUMMARY_BATCH_CHARS  # 不变量：每批不超预算
        paths = [batch_file.path for batch_file in batch]
        assert len(paths) == len(set(paths))  # 批内路径唯一
    assert sum(len(batch_file.versions) for b in batches for batch_file in b) == 8
    order = [
        version.projects[0]
        for b in batches
        for batch_file in b
        for version in batch_file.versions
    ]
    assert order == [f"p{index}" for index in range(8)]  # 版本不丢、顺序保持


def test_prompts_share_truncation_notice():
    """契约测试：截断标注措辞双端同源（TRUNCATION_NOTICE 唯一出处）。

    系统提示词与用户提示词都必须让模型知道"读到的是截断内容"——只改一处
    会让模型在另一侧消息里以为内容完整（ticket 06 的双端漂移教训）。所有
    嵌内容调用（赛题 / 接口块 / 文件全文）的系统提示词同样声明。
    """
    user_prompt = _summarize_user_prompt("stm32", ("proj-a",), JUDGMENT_FILES)

    assert TRUNCATION_NOTICE in JUDGMENT_SUMMARY_SYSTEM_PROMPT
    assert TRUNCATION_NOTICE in user_prompt
    assert TRUNCATION_NOTICE in SELECT_SYSTEM_PROMPT
    assert TRUNCATION_NOTICE in SKELETON_SYSTEM_PROMPT
    assert TRUNCATION_NOTICE in CLARIFY_SYSTEM_PROMPT


def test_select_modules_truncates_oversized_problem():
    """超大赛题文本同样截断：模块选择请求体也不会超限（未兜底输入闭环）。

    提示词开销 = 固定常数段（词表科普段 / 输出契约，工单 10 起新增），余量
    放宽到 +1000：断言的重点是"赛题内容被截断到预算内"，开销段不随内容增长。
    """
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules("赛题" * (EMBEDDED_CONTENT_CAP + 100), [ManifestSummary("dht11", "温湿度")])

    _, _, payload, _ = transport.calls[0]
    message = payload["messages"][1]["content"]
    assert len(message) < EMBEDDED_CONTENT_CAP + 1000
    assert "截断" in message
    assert TRUNCATION_NOTICE in message


def test_summarize_module_truncates_oversized_code():
    """单文件超长同样截断：简介草稿 / 校验的请求体也不会超限（413 兜底）。"""
    transport = FakeTransport(body=_api_response("摘要"))
    llm = _llm(transport)

    llm.summarize_module("x" * (EMBEDDED_CONTENT_CAP + 1000))

    _, _, payload, _ = transport.calls[0]
    message = payload["messages"][1]["content"]
    assert len(message) < EMBEDDED_CONTENT_CAP + 500
    assert "截断" in message


def test_http_413_raises_with_actionable_message():
    """网关 413（请求体过大）给出可操作提示，而不是裸 HTML。"""
    transport = FakeTransport(status=413, body="<html>Request Entity Too Large</html>")
    llm = _llm(transport)

    with pytest.raises(LLMError, match="413.*请求体过大"):
        llm._chat([{"role": "user", "content": "hi"}])


def test_chat_rejects_oversized_payload_before_send():
    """发送前体积断言兜底：未截断的超长输入在请求发出前大声失败（而不是 413）。"""
    transport = FakeTransport(body=_api_response("x"))
    llm = _llm(transport)

    with pytest.raises(LLMError, match="请求体过大"):
        llm._chat([{"role": "user", "content": "x" * (MAX_REQUEST_BYTES + 1024)}])

    assert transport.calls == []  # 断言在传输之前，网络调用未发生


def test_distill_master_batches_summary_phase():
    """大批文件按预算分批摘要：多次第一阶段调用，摘要合并后进第二阶段。"""
    files = tuple(
        JudgmentFile(
            f"{index}.c", (FileVersion(f"/* {index} */\n" + "x" * 50000, ("p1",)),)
        )
        for index in range(8)
    )  # 每文件超长截断到 4K；8 份截断内容超过单批预算 → 拆成多批
    batches = _judgment_batches(files)
    assert len(batches) > 1

    def summary_body(paths: tuple[str, ...]) -> str:
        return _api_response(
            json.dumps(
                {
                    "summaries": [
                        {
                            "path": path,
                            "versions": [
                                {"projects": ["p1"], "summary": f"{path} 摘要"}
                            ],
                        }
                        for path in paths
                    ]
                }
            )
        )

    bodies = [summary_body(tuple(f.path for f in batch)) for batch in batches]
    bodies.append(
        _api_response(
            json.dumps(
                {
                    "decisions": [
                        {"path": f"{index}.c", "action": ACTION_KEEP, "reason": "通用"}
                        for index in range(8)
                    ]
                }
            )
        )
    )
    transport = SequenceTransport(bodies)
    llm = _llm(transport)

    decisions = llm.distill_master("stm32", ("p1",), files, "对比")

    # 每批一次第一阶段调用 + 一次第二阶段调用；批内内容不超预算且带截断标注
    assert len(transport.calls) == len(batches) + 1
    for _, _, payload, _ in transport.calls[: len(batches)]:
        message = payload["messages"][1]["content"]
        assert len(message) <= MAX_SUMMARY_BATCH_CHARS + 2000  # 提示词开销留余量
        assert "截断" in message
    # 全部批的摘要合并进第二阶段（缺任何一批都会缺摘要）
    phase2 = transport.calls[len(batches)][2]["messages"][1]["content"]
    for path in (f"{index}.c" for index in range(8)):
        assert f"{path} 摘要" in phase2
    assert len(decisions) == 8


# 只含 src/oled.c 摘要的响应（缺 sensors/dht11.c——判例 08 的模型漏条目病）
SUMMARY_WITHOUT_DHT11 = json.dumps(
    {
        "summaries": [
            {
                "path": "src/oled.c",
                "versions": [
                    {"projects": ["proj-a"], "summary": "A 版本：通用 OLED 初始化驱动"},
                    {"projects": ["proj-b"], "summary": "B 版本：OLED 驱动带滚屏功能"},
                ],
            },
        ]
    }
)


def test_summarize_phase_retries_missing_files_only():
    """第一阶段漏条目（判例 08：真实工程 115 个文件一次返回漏了 1 个）→
    挖出已覆盖的合法摘要、只对缺失文件补问，不整批重来。"""
    only_dht11 = json.dumps(
        {
            "summaries": [
                {
                    "path": "sensors/dht11.c",
                    "versions": [
                        {"projects": ["proj-a"], "summary": "通用 DHT11 单总线驱动"}
                    ],
                },
            ]
        }
    )
    transport = SequenceTransport(
        [
            _api_response(SUMMARY_WITHOUT_DHT11),
            _api_response(only_dht11),
            _api_response(DISTILL_DECISIONS_JSON),
        ]
    )
    llm = _llm(transport)

    decisions = llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == 3
    # 补问轮只含缺失的 dht11.c，不再搬运已覆盖的 oled.c
    _, _, phase1_retry, _ = transport.calls[1]
    message = phase1_retry["messages"][1]["content"]
    assert "sensors/dht11.c" in message
    assert "src/oled.c" not in message
    # 补问后两阶段产物完整，判定覆盖全部待判文件（素材外的 oled_fonts 被过滤）
    assert {d.path for d in decisions} == {"src/oled.c", "sensors/dht11.c"}


def test_summarize_phase_batches_large_material(monkeypatch):
    """大批量素材按 JUDGMENT_BATCH_SIZE 分批问（判例 08：一次问 115 个文件，
    模型系统性漏判小配置文件、补问不收敛——分批把漏判降为偶发，交补问兜底）。"""
    import contest_generator.llm as llm_module

    monkeypatch.setattr(llm_module, "JUDGMENT_BATCH_SIZE", 2)
    files = (
        JudgmentFile(
            "src/oled.c",
            (
                FileVersion("/* A */", ("proj-a",)),
                FileVersion("/* B */", ("proj-b",)),
            ),
        ),
        JudgmentFile("sensors/dht11.c", (FileVersion("/* D */", ("proj-a",)),)),
        JudgmentFile("ui/led.c", (FileVersion("/* L */", ("proj-a",)),)),
    )
    batch1_summaries = json.dumps(
        {
            "summaries": [
                {
                    "path": "src/oled.c",
                    "versions": [
                        {"projects": ["proj-a"], "summary": "A"},
                        {"projects": ["proj-b"], "summary": "B"},
                    ],
                },
                {"path": "sensors/dht11.c", "versions": [{"projects": ["proj-a"], "summary": "D"}]},
            ]
        }
    )
    batch2_summaries = json.dumps(
        {
            "summaries": [
                {"path": "ui/led.c", "versions": [{"projects": ["proj-a"], "summary": "L"}]}
            ]
        }
    )
    decisions_batch1 = json.dumps(
        {
            "decisions": [
                {"path": "src/oled.c", "action": ACTION_MERGE,
                 "content": "/* M */\n", "explanation": "合并", "reason": "去重"},
                {"path": "sensors/dht11.c", "action": ACTION_KEEP, "reason": "通用"},
            ]
        }
    )
    decisions_batch2 = json.dumps(
        {
            "decisions": [
                {"path": "ui/led.c", "action": ACTION_EXCLUDE, "reason": "业务"}
            ]
        }
    )
    transport = SequenceTransport(
        [
            _api_response(batch1_summaries),
            _api_response(batch2_summaries),
            _api_response(decisions_batch1),
            _api_response(decisions_batch2),
        ]
    )
    llm = _llm(transport)

    result = llm.distill_master("stm32", ("proj-a", "proj-b"), files, "对比摘要")

    assert len(transport.calls) == 4
    # 每批各自一问：批 1 含 oled/dht11，批 2 只含 led（两阶段同款分批）
    _, _, phase1_batch1, _ = transport.calls[0]
    msg1 = phase1_batch1["messages"][1]["content"]
    assert "src/oled.c" in msg1 and "sensors/dht11.c" in msg1
    assert "ui/led.c" not in msg1
    _, _, phase1_batch2, _ = transport.calls[1]
    msg2 = phase1_batch2["messages"][1]["content"]
    assert "ui/led.c" in msg2
    assert "src/oled.c" not in msg2
    assert {d.path for d in result} == {"src/oled.c", "sensors/dht11.c", "ui/led.c"}


def test_decide_phase_retries_missing_decisions():
    """第二阶段漏条目 → 只补问缺失路径，判定最终完整覆盖。"""
    decisions_without_dht11 = json.dumps(
        {
            "decisions": [
                {
                    "path": "src/oled.c",
                    "action": ACTION_MERGE,
                    "content": "/* 整合产物 */\n",
                    "explanation": "两版合并去重",
                    "source": "proj-a",
                    "reason": "A 的 include path 更全",
                },
                {"path": "ui/oled_fonts.c", "action": ACTION_EXCLUDE, "reason": "赛题残留"},
            ]
        }
    )
    only_dht11 = json.dumps(
        {
            "decisions": [
                {"path": "sensors/dht11.c", "action": ACTION_KEEP, "reason": "通用驱动"}
            ]
        }
    )
    transport = SequenceTransport(
        [
            _api_response(SUMMARY_REPORT_JSON),
            _api_response(decisions_without_dht11),
            _api_response(only_dht11),
        ]
    )
    llm = _llm(transport)

    decisions = llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == 3
    # 补问轮只含缺失的 dht11.c
    _, _, phase2_retry, _ = transport.calls[2]
    message = phase2_retry["messages"][1]["content"]
    assert "sensors/dht11.c" in message
    assert "src/oled.c" not in message
    # 素材范围外的判定（ui/oled_fonts.c 不在 JUDGMENT_FILES）被过滤丢弃
    assert {d.path for d in decisions} == {"src/oled.c", "sensors/dht11.c"}


def test_summarize_phase_fails_loud_after_retries():
    """补问 SUMMARY_RETRY_LIMIT 轮仍缺失 → LLMError（宁可大声失败也不带病进第二阶段）。"""
    transport = SequenceTransport([_api_response(SUMMARY_WITHOUT_DHT11)] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)

    with pytest.raises(LLMError, match="多次补问后仍缺失"):
        llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")


def test_summarize_phase_bad_entry_retries_only_that_file():
    """批内一个文件输出不可修复的畸形（版本合并且 projects 与发送词表并集不
    匹配，拆分兜底拒绝）→ 只补问它自己，同批合法摘要不连坐（判例 08：
    deploy_config.json 版本合并曾让整批 15 个文件 3 轮全废）。"""
    deploy = JudgmentFile(
        path="ml/deploy.json",
        versions=(
            FileVersion(content="/* 部署配置 A */\n", projects=("proj-a",)),
            FileVersion(content="/* 部署配置 B */\n", projects=("proj-b",)),
        ),
    )
    merged_versions = json.dumps(
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
                {
                    # 模型合并且多报工程名——projects 与并集不匹配，拆分兜底拒绝
                    "path": "ml/deploy.json",
                    "versions": [
                        {"projects": ["proj-a", "proj-b", "proj-c"], "summary": "合并版"}
                    ],
                },
            ]
        }
    )
    correct_versions = json.dumps(
        {
            "summaries": [
                {
                    "path": "ml/deploy.json",
                    "versions": [
                        {"projects": ["proj-a"], "summary": "A 版部署配置"},
                        {"projects": ["proj-b"], "summary": "B 版部署配置"},
                    ],
                }
            ]
        }
    )
    decisions = json.dumps(
        {
            "decisions": [
                {"path": "src/oled.c", "action": ACTION_MERGE,
                 "content": "/* M */\n", "explanation": "合并", "source": "proj-a",
                 "reason": "去重"},
                {"path": "sensors/dht11.c", "action": ACTION_KEEP, "reason": "通用驱动"},
                {"path": "ml/deploy.json", "action": ACTION_EXCLUDE,
                 "reason": "特定模型部署配置"},
            ]
        }
    )
    transport = SequenceTransport(
        [_api_response(merged_versions), _api_response(correct_versions),
         _api_response(decisions)]
    )
    llm = _llm(transport)

    result = llm.distill_master(
        "stm32", ("proj-a", "proj-b"), JUDGMENT_FILES + (deploy,), "对比摘要"
    )

    assert len(transport.calls) == 3
    # 补问轮只问坏文件（deploy.json），已覆盖的 oled.c 不重问；补问轮 prompt
    # 对多版本文件带"版本 N"标记
    _, _, retry_payload, _ = transport.calls[1]
    retry_message = retry_payload["messages"][1]["content"]
    assert "ml/deploy.json" in retry_message
    assert "版本 1（proj-a）" in retry_message
    assert "版本 2（proj-b）" in retry_message
    assert "src/oled.c" not in retry_message
    assert {d.path for d in result} == {"src/oled.c", "sensors/dht11.c", "ml/deploy.json"}


def test_summarize_phase_merged_versions_split_into_versions():
    """模型把多内容版本合并成一条且 projects = 各版本工程名并集（判例 08：
    deploy_config.json 内容过于相似、屡次合并）→ 确定性拆回逐版本条目（摘要
    复制），一次通过、不进补问轮。"""
    deploy = JudgmentFile(
        path="ml/deploy.json",
        versions=(
            FileVersion(content="/* A */\n", projects=("proj-a",)),
            FileVersion(content="/* B */\n", projects=("proj-b",)),
        ),
    )
    merged = _api_response(
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "ml/deploy.json",
                        "versions": [
                            {
                                "projects": ["proj-a", "proj-b"],
                                "summary": "合并版部署配置",
                            }
                        ],
                    }
                ]
            }
        )
    )
    decisions = _api_response(
        json.dumps(
            {
                "decisions": [
                    {"path": "ml/deploy.json", "action": ACTION_EXCLUDE,
                     "reason": "特定模型部署配置"}
                ]
            }
        )
    )
    transport = SequenceTransport([merged, decisions])
    llm = _llm(transport)

    result = llm.distill_master("stm32", ("proj-a", "proj-b"), (deploy,), "对比摘要")

    # 拆分兜底一轮通过：无需补问（阶段 1 摘要 + 阶段 2 判定各一次）
    assert len(transport.calls) == 2
    assert [d.path for d in result] == ["ml/deploy.json"]


def test_summarize_phase_merged_versions_not_split_when_projects_mismatch():
    """合并条目的 projects 不等于发送版本组并集（多报工程名）→ 不拆，补问
    3 轮仍合并 → 大声失败。"""
    deploy = JudgmentFile(
        path="ml/deploy.json",
        versions=(
            FileVersion(content="/* A */\n", projects=("proj-a",)),
            FileVersion(content="/* B */\n", projects=("proj-b",)),
        ),
    )
    mismatched = _api_response(
        json.dumps(
            {
                "summaries": [
                    {
                        "path": "ml/deploy.json",
                        "versions": [
                            {
                                "projects": ["proj-a", "proj-b", "proj-c"],
                                "summary": "合并版",
                            }
                        ],
                    }
                ]
            }
        )
    )
    transport = SequenceTransport([mismatched] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)

    with pytest.raises(LLMError, match="ml/deploy.json"):
        llm.distill_master("stm32", ("proj-a", "proj-b"), (deploy,), "对比摘要")


def test_decide_phase_bad_entry_retries_only_that_file():
    """第二阶段一个条目畸形（merge 缺整合产物全文）→ 好条目不连坐，只补问
    坏文件。"""
    bad_entry = json.dumps(
        {
            "decisions": [
                {
                    "path": "src/oled.c",
                    "action": ACTION_MERGE,
                    "content": "/* 整合产物 */\n",
                    "explanation": "两版合并去重",
                    "source": "proj-a",
                    "reason": "A 的 include path 更全",
                },
                {
                    # merge 缺 content——条目形状错，严格解析拒绝
                    "path": "sensors/dht11.c",
                    "action": ACTION_MERGE,
                    "explanation": "合并",
                    "source": "proj-a",
                    "reason": "去重",
                },
            ]
        }
    )
    only_dht11 = json.dumps(
        {
            "decisions": [
                {"path": "sensors/dht11.c", "action": ACTION_KEEP, "reason": "通用驱动"}
            ]
        }
    )
    transport = SequenceTransport(
        [_api_response(SUMMARY_REPORT_JSON), _api_response(bad_entry),
         _api_response(only_dht11)]
    )
    llm = _llm(transport)

    decisions = llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == 3
    # 补问轮只问坏文件 dht11.c，已判定的 oled.c 不重问
    _, _, phase2_retry, _ = transport.calls[2]
    retry_message = phase2_retry["messages"][1]["content"]
    assert "sensors/dht11.c" in retry_message
    assert "src/oled.c" not in retry_message
    assert {d.path for d in decisions} == {"src/oled.c", "sensors/dht11.c"}


def test_decide_phase_cross_batch_repeats_filtered():
    """模型在批 N 幻觉复述其他批已判的路径（判例 08：提示词带完整结构对比
    清单，模型把 ml_adc.c 判了两次）→ 跨批复述被按批过滤丢弃，不产生重复
    判定。"""
    import contest_generator.llm as llm_module

    monkeypatch_batch = 2
    old = llm_module.JUDGMENT_BATCH_SIZE
    llm_module.JUDGMENT_BATCH_SIZE = monkeypatch_batch
    try:
        files = (
            JudgmentFile(
                "src/oled.c",
                (
                    FileVersion("/* A */", ("proj-a",)),
                    FileVersion("/* B */", ("proj-b",)),
                ),
            ),
            JudgmentFile("sensors/dht11.c", (FileVersion("/* D */", ("proj-a",)),)),
            JudgmentFile("ui/led.c", (FileVersion("/* L */", ("proj-a",)),)),
        )
        batch1_decisions = json.dumps(
            {
                "decisions": [
                    {"path": "src/oled.c", "action": ACTION_MERGE,
                     "content": "/* M */\n", "explanation": "合并", "source": "proj-a",
                     "reason": "去重"},
                    {"path": "sensors/dht11.c", "action": ACTION_KEEP,
                     "reason": "通用"},
                ]
            }
        )
        batch2_decisions = json.dumps(
            {
                "decisions": [
                    # 幻觉复述批 1 已判的 oled.c——应按批过滤丢弃
                    {"path": "src/oled.c", "action": ACTION_KEEP, "reason": "复述"},
                    {"path": "ui/led.c", "action": ACTION_EXCLUDE, "reason": "业务"},
                ]
            }
        )
        transport = SequenceTransport(
            [
                _api_response(
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
                                {
                                    "path": "sensors/dht11.c",
                                    "versions": [
                                        {"projects": ["proj-a"], "summary": "D"}
                                    ],
                                },
                            ]
                        }
                    )
                ),
                _api_response(
                    json.dumps(
                        {
                            "summaries": [
                                {
                                    "path": "ui/led.c",
                                    "versions": [
                                        {"projects": ["proj-a"], "summary": "L"}
                                    ],
                                }
                            ]
                        }
                    )
                ),
                _api_response(batch1_decisions),
                _api_response(batch2_decisions),
            ]
        )
        llm = _llm(transport)

        result = llm.distill_master("stm32", ("proj-a", "proj-b"), files, "对比摘要")

        paths = [d.path for d in result]
        assert len(paths) == len(set(paths))  # 无重复路径
        assert set(paths) == {"src/oled.c", "sensors/dht11.c", "ui/led.c"}
        # 复述的 oled.c（ACTION_KEEP）被丢弃，保留的是批 1 的 merge 判定
        oled = next(d for d in result if d.path == "src/oled.c")
        assert oled.action == ACTION_MERGE
    finally:
        llm_module.JUDGMENT_BATCH_SIZE = old


def test_decide_phase_out_of_scope_paths_filtered():
    """模型编造素材范围外的路径（判例 08：code/pid_debug.h 不在判定范围、
    属模型幻觉）→ 判定被过滤丢弃，不会触发 master 的"对比范围外路径"校验。"""
    hallucinated = json.dumps(
        {
            "decisions": [
                {"path": "src/oled.c", "action": ACTION_MERGE,
                 "content": "/* M */\n", "explanation": "合并", "source": "proj-a",
                 "reason": "去重"},
                {"path": "sensors/dht11.c", "action": ACTION_KEEP, "reason": "通用"},
                {"path": "code/pid_debug.h", "action": ACTION_EXCLUDE,
                 "reason": "幻觉路径"},
            ]
        }
    )
    transport = SequenceTransport(
        [_api_response(SUMMARY_REPORT_JSON), _api_response(hallucinated)]
    )
    llm = _llm(transport)

    decisions = llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == 2
    assert {d.path for d in decisions} == {"src/oled.c", "sensors/dht11.c"}


def test_decide_phase_early_output_from_later_batch_filtered():
    """模型在批 N 提前输出批 N+1 的路径判定（判例 08：提示词带完整结构对比
    清单，模型"预判"未读摘要路径）→ 提前判定不可信、被丢弃，该批正规判定
    保留。"""
    import contest_generator.llm as llm_module

    old = llm_module.JUDGMENT_BATCH_SIZE
    llm_module.JUDGMENT_BATCH_SIZE = 2
    try:
        files = (
            JudgmentFile(
                "src/oled.c",
                (
                    FileVersion("/* A */", ("proj-a",)),
                    FileVersion("/* B */", ("proj-b",)),
                ),
            ),
            JudgmentFile("sensors/dht11.c", (FileVersion("/* D */", ("proj-a",)),)),
            JudgmentFile("ui/led.c", (FileVersion("/* L */", ("proj-a",)),)),
        )
        batch1_decisions = json.dumps(
            {
                "decisions": [
                    {"path": "src/oled.c", "action": ACTION_MERGE,
                     "content": "/* M */\n", "explanation": "合并", "source": "proj-a",
                     "reason": "去重"},
                    {"path": "sensors/dht11.c", "action": ACTION_KEEP,
                     "reason": "通用"},
                    # 提前输出批 2 的 led.c（没读过它的摘要）——应被丢弃
                    {"path": "ui/led.c", "action": ACTION_KEEP, "reason": "预判"},
                ]
            }
        )
        batch2_decisions = json.dumps(
            {
                "decisions": [
                    {"path": "ui/led.c", "action": ACTION_EXCLUDE, "reason": "业务"}
                ]
            }
        )
        transport = SequenceTransport(
            [
                _api_response(
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
                                {
                                    "path": "sensors/dht11.c",
                                    "versions": [
                                        {"projects": ["proj-a"], "summary": "D"}
                                    ],
                                },
                            ]
                        }
                    )
                ),
                _api_response(
                    json.dumps(
                        {
                            "summaries": [
                                {
                                    "path": "ui/led.c",
                                    "versions": [
                                        {"projects": ["proj-a"], "summary": "L"}
                                    ],
                                }
                            ]
                        }
                    )
                ),
                _api_response(batch1_decisions),
                _api_response(batch2_decisions),
            ]
        )
        llm = _llm(transport)

        result = llm.distill_master("stm32", ("proj-a", "proj-b"), files, "对比摘要")

        assert len(transport.calls) == 4
        # led 的判定必须是批 2 的正规判定（exclude），批 1 的预判 keep 被丢弃
        led = next(d for d in result if d.path == "ui/led.c")
        assert led.action == ACTION_EXCLUDE
        assert {d.path for d in result} == {"src/oled.c", "sensors/dht11.c", "ui/led.c"}
    finally:
        llm_module.JUDGMENT_BATCH_SIZE = old


def test_summarize_prompt_labels_versions_for_conflicts():
    """第一阶段提示词：多内容版本文件带"版本 N（工程）"标记与禁止合并说明，
    单版本文件不带版本号。"""
    prompt = _summarize_user_prompt("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES)

    assert "版本 1（proj-a）" in prompt
    assert "版本 2（proj-b）" in prompt
    assert "把不同内容的版本合并成一条是错误" in prompt
    # 单版本文件只带工程名、不带"版本 N"标记
    single_line = next(
        line for line in prompt.splitlines()
        if line.startswith("- sensors/dht11.c")
    )
    assert "版本 1" not in single_line
    assert "sensors/dht11.c （proj-a）：" in single_line


def test_distill_master_fails_loud_on_broken_summary_phase():
    """第一阶段连续返回非 JSON（补问 SUMMARY_RETRY_LIMIT 轮仍不可用）→ LLMError，不进第二阶段——
    宁可大声失败。"""
    transport = SequenceTransport([_api_response("{not json")] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)

    with pytest.raises(LLMError, match="多次补问后仍缺失"):
        llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == SUMMARY_RETRY_LIMIT  # 补问轮用尽后才放弃


def test_distill_master_fails_loud_on_missing_summary():
    """缺某个文件的摘要（补问 SUMMARY_RETRY_LIMIT 轮仍缺）→ 第二阶段素材残缺，拒绝进入判定。"""
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
    transport = SequenceTransport([_api_response(missing)] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)

    with pytest.raises(LLMError, match="多次补问后仍缺失"):
        llm.distill_master("stm32", ("proj-a", "proj-b"), JUDGMENT_FILES, "对比摘要")

    assert len(transport.calls) == SUMMARY_RETRY_LIMIT


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


# ---------------------------------------------------------------------------
# 提炼进度事件契约（工单 01）：发射 seam + 事件序列（spec「事件契约」）
# ---------------------------------------------------------------------------


def test_distill_master_emits_progress_events_normal_path():
    """正常路径事件契约：start → 每批 batch_start/batch_done → 阶段 phase_done。

    事件契约唯一出处（spec「事件契约」+ ADR 0004），契约测试断言字段形状与
    事件顺序：本路径单批各阶段，事件序列即契约的基准形态。start 由入口发射
    且总量先算定（阶段 1 批数 = _judgment_batches、阶段 2 批数 = ⌈待判文件数 /
    批大小⌉）；阶段 1 批文件清单 = 待判文件路径、阶段 2 = 摘要路径。
    """
    transport = SequenceTransport(
        [_api_response(SUMMARY_REPORT_JSON), _api_response(DISTILL_DECISIONS_JSON)]
    )
    llm = _llm(transport)
    events: list[ProgressEvent] = []

    decisions = llm.distill_master(
        "stm32",
        ("proj-a", "proj-b"),
        JUDGMENT_FILES,
        "对比摘要",
        progress_emitter=events.append,
    )

    assert [e.type for e in events] == [
        EVENT_START,
        EVENT_BATCH_START,
        EVENT_BATCH_DONE,
        EVENT_PHASE_DONE,  # 阶段 1：摘要
        EVENT_BATCH_START,
        EVENT_BATCH_DONE,
        EVENT_PHASE_DONE,  # 阶段 2：判定
    ]
    assert events[0] == ProgressEvent(
        type=EVENT_START,
        judgment_count=2,
        summary_batch_count=1,
        decide_batch_count=1,
    )
    assert events[1] == ProgressEvent(
        type=EVENT_BATCH_START,
        phase=PHASE_SUMMARY,
        batch_index=1,
        batch_count=1,
        paths=("src/oled.c", "sensors/dht11.c"),
    )
    assert events[2] == ProgressEvent(
        type=EVENT_BATCH_DONE, phase=PHASE_SUMMARY, batch_index=1, processed_count=2
    )
    assert events[3] == ProgressEvent(
        type=EVENT_PHASE_DONE, phase=PHASE_SUMMARY, file_count=2
    )
    assert events[4] == ProgressEvent(
        type=EVENT_BATCH_START,
        phase=PHASE_DECIDE,
        batch_index=1,
        batch_count=1,
        paths=("src/oled.c", "sensors/dht11.c"),
    )
    assert events[5] == ProgressEvent(
        type=EVENT_BATCH_DONE, phase=PHASE_DECIDE, batch_index=1, processed_count=2
    )
    assert events[6] == ProgressEvent(
        type=EVENT_PHASE_DONE, phase=PHASE_DECIDE, file_count=2
    )
    assert len(decisions) == 2  # 发射器是旁路，不改变主流程产物


def test_distill_master_zero_batches_emits_no_batch_events():
    """零批次（无待判文件）契约：start 总量为 0，不发射任何批事件，两阶段直接完成。

    spec Further Notes：批数为 0（全部文件都是规则处理的残留 / 二进制等）时
    不发射任何批事件，阶段直接完成——done 由 webapp 层（工单 02）接。
    """
    transport = FakeTransport()
    llm = _llm(transport)
    events: list[ProgressEvent] = []

    decisions = llm.distill_master(
        "stm32", ("proj-a",), (), "对比", progress_emitter=events.append
    )

    assert [e.type for e in events] == [EVENT_START, EVENT_PHASE_DONE, EVENT_PHASE_DONE]
    assert events[0] == ProgressEvent(
        type=EVENT_START, judgment_count=0, summary_batch_count=0, decide_batch_count=0
    )
    assert events[1] == ProgressEvent(
        type=EVENT_PHASE_DONE, phase=PHASE_SUMMARY, file_count=0
    )
    assert events[2] == ProgressEvent(
        type=EVENT_PHASE_DONE, phase=PHASE_DECIDE, file_count=0
    )
    assert decisions == ()
    assert transport.calls == []  # 无文件 → 无 LLM 调用


def test_distill_master_emitter_failure_does_not_break_distillation():
    """发射器抛异常（旁路）→ 提炼主流程不受影响：判定照常返回。

    spec「发射 seam」决策点：发射是旁路，不因 UI 消费失败中断提炼——进度只是
    观察通道，主产物是完整报告（10-15 分钟 API 调用），UI 消费失败最多丢进度。
    """
    transport = SequenceTransport(
        [_api_response(SUMMARY_REPORT_JSON), _api_response(DISTILL_DECISIONS_JSON)]
    )
    llm = _llm(transport)

    def exploding(_event: ProgressEvent) -> None:
        raise RuntimeError("UI 消费失败")

    decisions = llm.distill_master(
        "stm32",
        ("proj-a", "proj-b"),
        JUDGMENT_FILES,
        "对比摘要",
        progress_emitter=exploding,
    )

    assert {d.path for d in decisions} == {"src/oled.c", "sensors/dht11.c"}
    assert len(transport.calls) == 2  # 两阶段各一次调用，未中断


def test_distill_master_start_totals_match_emitted_batch_sequence(monkeypatch):
    """start 总量契约：阶段 1 批数 = _judgment_batches 先算定、阶段 2 批数 =
    ⌈待判文件数 / 批大小⌉——与实际发射的批序列严格一致（批号 1 起、批总数一致、
    batch_done 携带本阶段累计已处理文件数，前端可直接显示"已读 X/115"）。"""
    import contest_generator.llm as llm_module

    monkeypatch.setattr(llm_module, "JUDGMENT_BATCH_SIZE", 2)
    files = tuple(
        JudgmentFile(f"{index}.c", (FileVersion("/* x */", ("p1",)),))
        for index in range(5)
    )

    def summaries_body(paths: tuple[str, ...]) -> str:
        return _api_response(
            json.dumps(
                {
                    "summaries": [
                        {
                            "path": path,
                            "versions": [
                                {"projects": ["p1"], "summary": f"{path} 摘要"}
                            ],
                        }
                        for path in paths
                    ]
                }
            )
        )

    def decisions_body(paths: tuple[str, ...]) -> str:
        return _api_response(
            json.dumps(
                {
                    "decisions": [
                        {"path": path, "action": ACTION_KEEP, "reason": "通用"}
                        for path in paths
                    ]
                }
            )
        )

    batches = (("0.c", "1.c"), ("2.c", "3.c"), ("4.c",))
    transport = SequenceTransport(
        [summaries_body(b) for b in batches]
        + [decisions_body(b) for b in batches]
    )
    llm = _llm(transport)
    events: list[ProgressEvent] = []

    llm.distill_master(
        "stm32", ("p1",), files, "对比", progress_emitter=events.append
    )

    assert events[0] == ProgressEvent(
        type=EVENT_START, judgment_count=5, summary_batch_count=3, decide_batch_count=3
    )
    summary_starts = [
        e for e in events if e.type == EVENT_BATCH_START and e.phase == PHASE_SUMMARY
    ]
    assert [(e.batch_index, e.batch_count, e.paths) for e in summary_starts] == [
        (1, 3, ("0.c", "1.c")),
        (2, 3, ("2.c", "3.c")),
        (3, 3, ("4.c",)),
    ]
    summary_dones = [
        e for e in events if e.type == EVENT_BATCH_DONE and e.phase == PHASE_SUMMARY
    ]
    assert [e.processed_count for e in summary_dones] == [2, 4, 5]  # 累计
    decide_starts = [
        e for e in events if e.type == EVENT_BATCH_START and e.phase == PHASE_DECIDE
    ]
    assert [(e.batch_index, e.batch_count) for e in decide_starts] == [
        (1, 3),
        (2, 3),
        (3, 3),
    ]
    decide_dones = [
        e for e in events if e.type == EVENT_BATCH_DONE and e.phase == PHASE_DECIDE
    ]
    assert [e.processed_count for e in decide_dones] == [2, 4, 5]
    assert events[-1] == ProgressEvent(
        type=EVENT_PHASE_DONE, phase=PHASE_DECIDE, file_count=5
    )


def test_distill_start_decide_count_single_sourced_across_version_split(monkeypatch):
    """start 的判定批数单源化（工单 B）：单文件多版本合计超预算拆批后，摘要
    条目数 > 待判文件数——start 的 decide_batch_count 必须从实际摘要条目数推导
    （旧公式按 judgment_files 数算会少报，start 总量 ≠ 实发批序）。"""
    import contest_generator.llm as llm_module

    monkeypatch.setattr(llm_module, "JUDGMENT_BATCH_SIZE", 2)
    monkeypatch.setattr(llm_module, "MAX_SUMMARY_BATCH_CHARS", 3)
    files = (
        JudgmentFile(
            "A.c",
            (FileVersion("AAAA", ("p1",)), FileVersion("BBBB", ("p2",))),
        ),
        JudgmentFile("B.c", (FileVersion("CC", ("p1",)),)),
    )

    def summaries_body(entries: tuple[tuple[str, str], ...]) -> str:
        """每批的摘要响应：版本工程名必须与发送词表一致（parse 校验版本组
        不重不漏恰好覆盖）。"""
        return _api_response(
            json.dumps(
                {
                    "summaries": [
                        {
                            "path": path,
                            "versions": [
                                {
                                    "projects": [project],
                                    "summary": f"{path} {project} 摘要",
                                }
                            ],
                        }
                        for path, project in entries
                    ]
                }
            )
        )

    def decisions_body(paths: tuple[str, ...]) -> str:
        return _api_response(
            json.dumps(
                {
                    "decisions": [
                        {"path": path, "action": ACTION_KEEP, "reason": "通用"}
                        for path in paths
                    ]
                }
            )
        )

    # A 拆成两条目（p1/p2 各一版）→ 摘要批 3（每条目一批）、摘要条目 3 →
    # 判定批 ⌈3/2⌉=2；旧公式按 judgment_files 数算 ⌈2/2⌉=1，与实际批序分叉。
    transport = SequenceTransport(
        [
            summaries_body((("A.c", "p1"),)),
            summaries_body((("A.c", "p2"),)),
            summaries_body((("B.c", "p1"),)),
            decisions_body(("A.c",)),
            decisions_body(("B.c",)),
        ]
    )
    llm = _llm(transport)
    events: list[ProgressEvent] = []

    decisions = llm.distill_master(
        "stm32", ("p1",), files, "对比", progress_emitter=events.append
    )

    assert events[0] == ProgressEvent(
        type=EVENT_START, judgment_count=2, summary_batch_count=3, decide_batch_count=2
    )
    decide_starts = [
        e for e in events if e.type == EVENT_BATCH_START and e.phase == PHASE_DECIDE
    ]
    assert [(e.batch_index, e.batch_count) for e in decide_starts] == [(1, 2), (2, 2)]
    assert {d.path for d in decisions} == {"A.c", "B.c"}


def test_distill_master_emits_retry_events_on_missing():
    """补问路径：两阶段各自漏条目 → 每轮补问开始发 retry（轮次 1 起、缺失数 =
    该轮要补问的文件数），补全后照常 batch_done / phase_done——事件序列完整。"""
    only_dht11_summary = json.dumps(
        {
            "summaries": [
                {
                    "path": "sensors/dht11.c",
                    "versions": [
                        {"projects": ["proj-a"], "summary": "通用 DHT11 单总线驱动"}
                    ],
                }
            ]
        }
    )
    decisions_without_dht11 = json.dumps(
        {
            "decisions": [
                {
                    "path": "src/oled.c",
                    "action": ACTION_MERGE,
                    "content": "/* 整合产物 */\n",
                    "explanation": "两版合并去重",
                    "source": "proj-a",
                    "reason": "A 的 include path 更全",
                },
                {"path": "ui/oled_fonts.c", "action": ACTION_EXCLUDE, "reason": "赛题残留"},
            ]
        }
    )
    only_dht11_decisions = json.dumps(
        {
            "decisions": [
                {"path": "sensors/dht11.c", "action": ACTION_KEEP, "reason": "通用驱动"}
            ]
        }
    )
    transport = SequenceTransport(
        [
            _api_response(SUMMARY_WITHOUT_DHT11),
            _api_response(only_dht11_summary),
            _api_response(decisions_without_dht11),
            _api_response(only_dht11_decisions),
        ]
    )
    llm = _llm(transport)
    events: list[ProgressEvent] = []

    decisions = llm.distill_master(
        "stm32",
        ("proj-a", "proj-b"),
        JUDGMENT_FILES,
        "对比摘要",
        progress_emitter=events.append,
    )

    assert [e for e in events if e.type == EVENT_RETRY] == [
        ProgressEvent(
            type=EVENT_RETRY,
            phase=PHASE_SUMMARY,
            batch_index=1,
            retry_round=1,
            missing_count=1,
        ),
        ProgressEvent(
            type=EVENT_RETRY,
            phase=PHASE_DECIDE,
            batch_index=1,
            retry_round=1,
            missing_count=1,
        ),
    ]
    # 补问后事件序列照常收尾：batch_done → phase_done
    assert [e.type for e in events] == [
        EVENT_START,
        EVENT_BATCH_START,
        EVENT_RETRY,
        EVENT_BATCH_DONE,
        EVENT_PHASE_DONE,
        EVENT_BATCH_START,
        EVENT_RETRY,
        EVENT_BATCH_DONE,
        EVENT_PHASE_DONE,
    ]
    assert {d.path for d in decisions} == {"src/oled.c", "sensors/dht11.c"}


def test_distill_master_failure_path_emits_retries_then_raises():
    """失败路径：补问轮次全部用尽仍缺 → 每轮补问开始发 retry（轮次 1..4、缺失数），
    然后大声失败——失败的批不发射 batch_done / phase_done（事件只描述已发生的
    事实，不虚构完成）。"""
    transport = SequenceTransport([_api_response(SUMMARY_WITHOUT_DHT11)] * SUMMARY_RETRY_LIMIT)
    llm = _llm(transport)
    events: list[ProgressEvent] = []

    with pytest.raises(LLMError, match="多次补问后仍缺失"):
        llm.distill_master(
            "stm32",
            ("proj-a", "proj-b"),
            JUDGMENT_FILES,
            "对比摘要",
            progress_emitter=events.append,
        )

    assert [e.type for e in events] == [
        EVENT_START,
        EVENT_BATCH_START,
        EVENT_RETRY,
        EVENT_RETRY,
        EVENT_RETRY,
        EVENT_RETRY,  # SUMMARY_RETRY_LIMIT 次调用 = 首次 + 补问 4 轮
    ]
    retries = [e for e in events if e.type == EVENT_RETRY]
    assert [(e.retry_round, e.missing_count) for e in retries] == [(1, 1), (2, 1), (3, 1), (4, 1)]
    assert all(e.phase == PHASE_SUMMARY and e.batch_index == 1 for e in retries)


# ---------------------------------------------------------------------------
# 工单 03：选模块 prompt 扩展——参考文件两级注入协议
# ---------------------------------------------------------------------------


def _suggestion(
    entry_id: str,
    title: str = "参考标题",
    description: str = "一句话简介",
    source: str = "auto",
) -> ReferenceSuggestion:
    return ReferenceSuggestion(
        id=entry_id, title=title, description=description, source=source
    )


def test_select_prompt_includes_reference_list_when_given():
    """两级注入第一级：参考文件清单（标题 + 一句话简介）进选模块用户提示词。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules(
        "2026C 数字钥匙题",
        [ManifestSummary("dht11", "温湿度传感器驱动")],
        references=[_suggestion("key-example", "2026C 数字钥匙参考例程", "2026C 钥匙题配套例程")],
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "关联参考文件" in user_message
    assert "- key-example: 2026C 数字钥匙参考例程 —— 2026C 钥匙题配套例程" in user_message
    assert '"references"' in user_message  # 输出契约带 references 数组


def test_select_prompt_embeds_requested_fulltexts():
    """两级注入第二级：模型要求阅读全文的参考文件以全文形态嵌入——总预算
    放宽为 REFERENCE_FULLTEXT_BYTES wire 字节（工单 03 放宽旧 4000 总截断吞
    掉尾部文件；budget-wire-unification/01 弃字符 cap 改 wire 记账），预算内
    全文原样直传（逐文件截断已由 read_fulltext 完成）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    long_text = "长全文" * 2500  # 7500 字符 = 45000 wire 字节：超旧 4000 上限、在 wire 预算内

    llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[_suggestion("key-example")],
        reference_fulltexts={"key-example": long_text},
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "以下是你要求阅读全文的参考文件" in user_message
    assert long_text in user_message  # 超 4000 字符仍全文在（旧实现必截断）
    assert TRUNCATION_NOTICE not in user_message  # 总上限内不截断（截断标注归 read_fulltext）


def test_select_prompt_embeds_fulltext_with_every_file_head():
    """工单 03 回归：注入块含每个文件开头——read_fulltext 逐文件截断后的多文件
    全文在总预算内逐字嵌入（旧 4000 总截断下首个大文件吃光配额、尾部文件不可见）。
    全文总量保持在 REFERENCE_FULLTEXT_BYTES wire 字节预算内（budget-wire-
    unification/01 定 67000，3 × 11K 字节 ≈ 33KB < 预算）——超预算的截断断言由
    test_select_prompt_truncates_fulltext_at_relaxed_total_cap 钉死。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    fulltext = "\n".join(
        f"// ---- f{i}.c ----\n/* f{i}_head */\n" + "c" * 11000 for i in range(3)
    )

    llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[_suggestion("key-example")],
        reference_fulltexts={"key-example": fulltext},
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    for i in range(3):
        assert f"// ---- f{i}.c ----" in user_message  # 每个文件的标注都在
        assert f"/* f{i}_head */" in user_message  # 每个文件的开头都在（含尾部文件）
    assert TRUNCATION_NOTICE not in user_message  # 总上限内不截断


def test_select_prompt_truncates_fulltext_at_relaxed_total_cap():
    """工单 03 回归 + budget-wire-unification/01：总预算放宽不是去掉——超过
    REFERENCE_FULLTEXT_BYTES wire 字节预算的全文仍截头带标注（兜底超大条目
    请求体，防 MAX_REQUEST_BYTES 网关预算爆掉；wire 记账口径）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    long_text = "x" * (REFERENCE_FULLTEXT_BYTES + 5000)

    llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[_suggestion("key-example")],
        reference_fulltexts={"key-example": long_text},
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "内容过长，已截断" in user_message
    assert f"仅展示前 {REFERENCE_FULLTEXT_BYTES} wire 字节" in user_message
    assert TRUNCATION_NOTICE in user_message


def test_select_prompt_embeds_empty_fulltext_without_dropping():
    """空文件全文也嵌入（带标注的空白块）——静默丢弃会让模型以为点名的文件没给。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[_suggestion("key-example")],
        reference_fulltexts={"key-example": ""},
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "key-example: 参考标题：" in user_message


def test_select_prompt_without_references_keeps_old_shape():
    """不传参考文件时提示词与既有形态一致（无参考段、输出契约不含 references）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "参考文件" not in user_message
    assert '"references"' not in user_message


def test_select_modules_with_references_parses_reference_ids():
    transport = FakeTransport(
        body=_api_response(json.dumps({"modules": [], "references": ["key-example"]}))
    )
    llm = _llm(transport)

    result = llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[_suggestion("key-example")],
    )

    assert result.reference_ids == ("key-example",)


# ---------------------------------------------------------------------------
# 拆条（工单 04）：短全文全量直传不截断；超长全文 = 调用方路由错误，大声失败
# ---------------------------------------------------------------------------


def test_topic_split_topics_sends_full_text_without_truncation():
    """短全文（≤ TOPIC_SPLIT_LLM_CHAR_CAP）全量直传：旧路径截断到 4000 字符
    （EMBEDDED_CONTENT_CAP）是 flash 模型静默漏题的根因之一，拆条不再截断。"""
    text = "2026 年赛题正文……" * 500
    assert len(text) > EMBEDDED_CONTENT_CAP  # 超过旧截断上限，必须全量直传
    transport = FakeTransport(
        body=_api_response(
            json.dumps(
                {
                    "topics": [
                        {"year": "2026", "number": "C", "problem_text": "题面全文"}
                    ]
                }
            )
        )
    )
    llm = _llm(transport)

    drafts = llm.topic_split_topics(text)

    _, _, payload, _ = transport.calls[0]
    assert text in payload["messages"][1]["content"]
    assert drafts == (TopicDraft(year="2026", number="C", problem_text="题面全文"),)


def test_topic_split_topics_rejects_overlong_fulltext():
    """超长全文 = 调用方未走确定性分块路由：请求发出前大声失败（与
    MAX_REQUEST_BYTES 兜底同哲学），不把塞给 flash 模型后静默漏题。"""
    transport = FakeTransport()
    llm = _llm(transport)

    with pytest.raises(LLMError, match="拆条"):
        llm.topic_split_topics("x" * (TOPIC_SPLIT_LLM_CHAR_CAP + 1))

    assert transport.calls == []  # 请求未发出


# ---------------------------------------------------------------------------
# 归档判定 / 参考文件简介（工单 02，重试兜底工单 C5）
# ---------------------------------------------------------------------------


def _candidate(path: str = "src/motor.c") -> ReferenceCandidate:
    return ReferenceCandidate(path=path, content="int main(void) { }", reason="剔除")


def test_parse_archive_judgment_rejects_non_json():
    with pytest.raises(LLMError, match="不是 JSON"):
        parse_archive_judgment("{not json", ["src/motor.c"])


def test_parse_archive_judgment_rejects_missing_archive_array():
    with pytest.raises(LLMError, match="缺少 archive 数组"):
        parse_archive_judgment("{}", ["src/motor.c"])


def test_parse_archive_judgment_rejects_non_string_item():
    with pytest.raises(LLMError, match="必须是字符串"):
        parse_archive_judgment('{"archive": [1]}', ["src/motor.c"])


def test_parse_archive_judgment_rejects_unknown_path():
    """词表外路径拒绝：模型判定了素材外的路径 = 输出不可信，大声失败。"""
    with pytest.raises(LLMError, match="素材外的路径"):
        parse_archive_judgment('{"archive": ["src/other.c"]}', ["src/motor.c"])


def test_parse_archive_judgment_rejects_duplicate_path():
    with pytest.raises(LLMError, match="重复判定归档"):
        parse_archive_judgment(
            '{"archive": ["src/motor.c", "src/motor.c"]}', ["src/motor.c"]
        )


def test_parse_archive_judgment_accepts_empty_and_subset():
    """空列表合法（没有文件值得归档，由调用方呈现）；子集按序返回。"""
    assert parse_archive_judgment('{"archive": []}', ["src/motor.c"]) == ()
    assert parse_archive_judgment(
        '{"archive": ["src/motor.c"]}', ["src/motor.c", "src/pid.c"]
    ) == ("src/motor.c",)


class _FlakyTransport(FakeTransport):
    """前 n 次调用返回 502，之后正常（测整次调用级重试，工单 C5）。

    502 是 5xx = 网络类（工单 deepseek-retry-hardening/01）→ 走指数退避；
    触发重试的用例必须 monkeypatch _backoff_sleep（测试不可真睡）。
    """

    def __init__(self, body: str, failures: int) -> None:
        super().__init__(body=body)
        self._failures = failures

    def post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> tuple[int, str]:
        self.calls.append((url, headers, payload, timeout))
        if len(self.calls) <= self._failures:
            return 502, "transient failure"
        return self.status, self.body


def test_reference_judge_archivable_retries_transient_failure(monkeypatch):
    """单次瞬时失败（网关 502，网络类）整次重问：退避 1s 后成功
    （与提炼批处理同哲学：宁可多花一次调用）。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = _FlakyTransport(
        body=_api_response('{"archive": ["src/motor.c"]}'), failures=1
    )
    llm = _llm(transport)

    result = llm.reference_judge_archivable([_candidate()])

    assert result == ("src/motor.c",)
    assert len(transport.calls) == 2
    assert sleeps == [1.0]


def test_reference_judge_archivable_exhausts_retries_then_loud_failure(monkeypatch):
    """超过重试上限仍失败 = 大声抛错（不静默吞成假结果）——网络类 5 次退避。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = _FlakyTransport(body=_api_response('{"archive": []}'), failures=9)
    llm = _llm(transport)

    with pytest.raises(LLMError, match="归档判定连续 5 次调用失败"):
        llm.reference_judge_archivable([_candidate()])

    assert len(transport.calls) == NETWORK_RETRY_LIMIT
    assert sleeps == [1.0, 2.0, 4.0, 8.0]


def test_reference_summarize_retries_transient_failure(monkeypatch):
    """逐文件简介同样有重试兜底（多文件归档不再单次失败即整体放弃）。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = _FlakyTransport(body=_api_response("UWB 例程"), failures=2)
    llm = _llm(transport)

    assert llm.reference_summarize("材料全文") == "UWB 例程"
    assert len(transport.calls) == 3
    assert sleeps == [1.0, 2.0]


# ---------------------------------------------------------------------------
# 赛题简介生成（wait-what 步骤）：文本模式单调用契约
# ---------------------------------------------------------------------------


def test_summarize_topic_posts_plain_text_prompt():
    """赛题简介：文本模式（非 json_mode），一句话总览 + 功能要点的提示词。"""
    transport = FakeTransport(
        body=_api_response("做一个温湿度采集系统\n- 采集温湿度\n- 显示结果")
    )
    llm = _llm(transport)

    summary = llm.summarize_topic("温湿度采集并显示")

    assert summary == "做一个温湿度采集系统\n- 采集温湿度\n- 显示结果"
    _, _, payload, _ = transport.calls[0]
    messages = payload["messages"]
    assert "一句话总览" in messages[0]["content"]
    assert TRUNCATION_NOTICE in messages[0]["content"]
    assert "温湿度采集并显示" in messages[1]["content"]
    assert "response_format" not in payload  # 文本模式


def test_summarize_topic_truncates_oversized_problem():
    """超长赛题截断带标注（与所有嵌内容调用同款预算）。"""
    transport = FakeTransport(body=_api_response("概述"))
    llm = _llm(transport)
    long_problem = "题" * (EMBEDDED_CONTENT_CAP + 100)

    llm.summarize_topic(long_problem)

    _, _, payload, _ = transport.calls[0]
    user = payload["messages"][1]["content"]
    assert len(user) < len(long_problem)
    assert TRUNCATION_NOTICE in user


def test_summarize_topic_retries_transient_failure(monkeypatch):
    """瞬时失败（网关 502，网络类）整次重问：退避 1/2s 后成功
    （与参考文件简介同款兜底）。"""
    sleeps = _record_backoff_sleeps(monkeypatch)
    transport = _FlakyTransport(body=_api_response("概述"), failures=2)
    llm = _llm(transport)

    assert llm.summarize_topic("题面") == "概述"
    assert len(transport.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_reference_judge_archivable_retries_on_malformed_json_output():
    """输出畸形（非 JSON）也整次重问，直到严格解析通过。"""
    transport = FakeTransport(body=_api_response("{broken"))
    llm = _llm(transport)

    # 固定响应始终畸形：SUMMARY_RETRY_LIMIT 次尝试后大声失败（与输出可用性策略一致）
    with pytest.raises(LLMError, match=f"归档判定连续 {SUMMARY_RETRY_LIMIT} 次调用失败"):
        llm.reference_judge_archivable([_candidate()])
    assert len(transport.calls) == SUMMARY_RETRY_LIMIT


# 工单 10：功能需求层端到端（提示词契约 + 默认词表校验；域判决用例随
# build_module_selection 迁 test_selection.py，工单 06）

REQUIREMENTS_JSON = json.dumps(
    {
        "requirements": [
            {
                "requirement": "识别数字",
                "sentence": 3,
                "modules": [
                    {"slug": "dht11", "reason": "测温湿度"},
                    {"slug": "oled", "reason": "显示结果"},
                ],
                "suggestions": [{"name": "视觉模块", "examples": ["K230", "OpenMV"]}],
            },
            {
                "requirement": "声光提示",
                "sentence": 5,
                "modules": [],
                "suggestions": [{"name": "蜂鸣器", "examples": []}],
            },
        ]
    }
)


def test_select_modules_prompt_includes_wordlist_and_new_contract():
    """提示词契约：硬件词表科普段 + 新输出契约（requirements / suggestions /
    questions）都进用户消息——模型按新契约输出，解析器才有得校验。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules("设计一个识别数字的送药小车", [ManifestSummary("dht11", "温湿度")])

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "硬件词表" in user_message
    assert "- 视觉模块：K230、OpenMV" in user_message  # 词表科普段
    assert '"requirements"' in user_message
    assert '"suggestions"' in user_message
    assert '"questions"' in user_message
    assert '"references"' not in user_message  # 无参考文件清单时旧形态保持


def test_select_modules_deepseek_parses_new_contract_with_default_wordlist():
    """生产 LLM 端到端：新契约 JSON → 功能需求层 + 库外建议（默认词表校验）。"""
    transport = FakeTransport(body=_api_response(REQUIREMENTS_JSON))
    llm = _llm(transport)

    result = llm.select_modules("设计一个送药小车", [ManifestSummary("dht11", "温湿度"), ManifestSummary("oled", "显示")])

    assert result.modules == ("dht11", "oled")
    assert result.requirements[0].requirement == "识别数字"
    assert result.requirements[0].suggestions[0].name == "视觉模块"


REQUIREMENTS_INSTANCES_JSON = json.dumps(
    {
        "requirements": [
            {
                "requirement": "声光提示",
                "sentence": 4,
                "modules": [
                    {
                        "slug": "led",
                        "reason": "4 个指示灯",
                        "instances": [
                            {"name": "红", "variant": "red"},
                            {"name": "黄", "variant": "yellow"},
                            {"name": "绿", "variant": "green"},
                            {"name": "状态灯", "variant": ""},
                        ],
                    }
                ],
            }
        ]
    }
)


def test_select_modules_parses_instances_for_multi_instance_manifest():
    """生产 LLM 端到端（工单 module-multi-instance/06）：清单里的 led 带
    multi_instance 能力 → 模型输出的 instances 被解析进
    ModuleSelection.instances（能力清单从 ManifestSummary 同源取）。"""
    transport = FakeTransport(body=_api_response(REQUIREMENTS_INSTANCES_JSON))
    llm = _llm(transport)
    summary = ManifestSummary(
        "led", "指示灯", multi_instance=MultiInstanceSpec(max=8, variant="color")
    )

    result = llm.select_modules("作品需要 4 个指示灯", [summary])

    assert result.instances == {
        "led": (
            ModuleInstance(name="红", variant="red"),
            ModuleInstance(name="黄", variant="yellow"),
            ModuleInstance(name="绿", variant="green"),
            ModuleInstance(name="状态灯", variant=""),
        )
    }


def test_select_modules_rejects_instances_without_multi_instance_capability():
    """能力校验宁严勿假绿：清单模块未声明 multi_instance 时模型带 instances
    → LLMError（重试后大声失败），不带病进选择结果。"""
    transport = FakeTransport(body=_api_response(REQUIREMENTS_INSTANCES_JSON))
    llm = _llm(transport)

    with pytest.raises(LLMError, match="不支持多实例"):
        llm.select_modules("赛题", [ManifestSummary("led", "指示灯")])


def test_select_prompt_marks_multi_instance_and_contract_includes_instances():
    """提示词契约（工单 module-multi-instance/06）：模块清单行带「多实例」
    标注（AI 知道谁能多实例 + 上限），输出契约的 modules 条目含 instances
    形状，用户消息有条件规则段（题面数量为证据 / 不猜引脚 / 非多实例模块
    不输出——库内有多实例模块才出段）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    led_summary = ManifestSummary(
        "led", "指示灯", multi_instance=MultiInstanceSpec(max=8, variant="color")
    )

    llm.select_modules(
        "作品需要 4 个指示灯", [led_summary, ManifestSummary("dht11", "温湿度")]
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "- led: 指示灯（多实例：上限 8，变体 = color）" in user_message
    assert "- dht11: 温湿度（多实例" not in user_message  # 无能力块不标注
    assert '"instances"' in user_message  # 输出契约带 instances 形状
    assert "不为非多实例模块输出 instances" in user_message
    assert "不输出 pin" in user_message


def test_select_prompt_without_multi_instance_module_keeps_old_shape():
    """库内没有多实例模块（旧库形状）：提示词与既有形态一致——无多实例规则
    段、输出契约也不含 instances 形状（验收②：旧推荐无 instances 现行为不变，
    旧库提示词逐字节等价——契约若无条件宣传 instances，旧库模型输出该字段会
    被能力校验硬失败）。（最坏情形请求预算零成本。）"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules("赛题", [ManifestSummary("dht11", "温湿度")])

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "不为非多实例模块输出 instances" not in user_message
    assert '"instances"' not in user_message  # 契约保持旧形状（逐字节等价）



def test_select_prompt_embeds_manual_fulltexts_with_label():
    """手动选参考资料（工单 01）：全文直读段（read_fulltext 的 file_label 文件名
    标注 + 逐文件截断标注原样保留；注入处总预算放宽为 REFERENCE_FULLTEXT_BYTES
    wire 字节——预算内原样直传）；清单段手动条目带来源标注（无需点名）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)
    # 1500 份 ≈ 9000 字符：超旧 4000 上限（注入处不再截断）、又低于
    # REFERENCE_FULLTEXT_BYTES 预算（中文 json.dumps 6 字节/字符 ≈ 54KB）
    manual_text = "// ---- visual.txt ----\n" + "视觉资料正文" * 1500

    llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[
            _suggestion("visual-ref", "视觉参考", "视觉资料", source=REFERENCE_SOURCE_MANUAL)
        ],
        manual_fulltexts={"visual-ref": manual_text},
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "以下为你手动指定的参考文件全文" in user_message
    assert manual_text in user_message  # 超 4000 字符仍全文在（旧实现必截断）
    assert "// ---- visual.txt ----" in user_message  # read_fulltext 的 file_label 标注保留
    assert TRUNCATION_NOTICE not in user_message  # 总上限内不截断（截断标注归 read_fulltext）
    assert "（用户手动指定，全文已直接给出，无需点名）" in user_message  # 清单行来源标注


def test_select_prompt_without_manual_keeps_old_shape():
    """不传 manual_fulltexts：提示词与既有形态一致（无手动段、清单行无来源标注）——
    缺省 = 现状逐字节等价（回归钉死）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[_suggestion("key-example", "2026C 参考", "配套例程")],
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "手动" not in user_message
    assert "无需点名" not in user_message
    assert "- key-example: 2026C 参考 —— 配套例程" in user_message  # 清单行形状不变


def test_select_prompt_embeds_clarifications_as_independent_section():
    """选择阶段 prompt 契约（工单 clarify-history-in-convergence）：题面 / 参考段
    之后的"用户已澄清的问题"独立段——Q/A 逐条、按历史顺序；不带编号、不并入
    题面（题面逐句编号跨轮稳定，收敛判定的对照句编号依赖它）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules(
        "送药小车。识别数字。",
        [ManifestSummary("dht11", "温湿度")],
        clarifications=(
            ("识别方式？", "摄像头"),
            ("屏幕尺寸？", "1.3 寸"),
        ),
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    history_section = user_message.split("用户已澄清的问题")[1]
    assert "Q: 识别方式？\nA: 摄像头" in history_section  # 逐条 Q/A、保序
    assert "Q: 屏幕尺寸？\nA: 1.3 寸" in history_section
    assert history_section.index("识别方式") < history_section.index("屏幕尺寸")
    # 与题面分离：题面原样在前（不并入题面，题面编号稳定性不受影响），
    # 历史段独立成段、不带编号、无题面内容混入
    topic_section = user_message.split("用户已澄清的问题")[0]
    assert "送药小车。识别数字。" in topic_section
    assert (
        user_message.index("送药小车。识别数字。")
        < user_message.index("用户已澄清的问题")
    )
    assert "Q: " not in topic_section  # 无问答混入题面段
    assert "1. Q" not in history_section  # 历史段未被编号（独立段不带编号）


def test_select_prompt_without_clarifications_keeps_old_shape():
    """缺省空 clarifications：提示词与既有形态一致（无历史段）——回归钉死
    （向后兼容：缺省空 = 旧行为）。"""
    transport = FakeTransport(body=_api_response(SELECTION_JSON))
    llm = _llm(transport)

    llm.select_modules(
        "赛题",
        [ManifestSummary("dht11", "温湿度")],
        references=[_suggestion("key-example", "2026C 参考", "配套例程")],
    )

    user_message = transport.calls[0][2]["messages"][1]["content"]
    assert "用户已澄清的问题" not in user_message
    assert "- key-example: 2026C 参考 —— 配套例程" in user_message  # 参考段形状不变


def test_selection_prompt_worst_case_fits_request_budget():
    """结构测试（工单 budget-wire-unification/01 唯一硬保证，红证先行）：最坏
    情况 select 请求——REFERENCE_FULLTEXT_BYTES 上限全文（全中文，wire 口径
    6 字节/字符）+ 20 条长问答历史（截断后形态）+ 词表 + 摘要 + 题面 4000
    （推导最坏形态）——完整 payload 按 json.dumps 序列化（对齐 llm._chat 预检
    口径，不继承旧 select 测试的 prompt.encode 3 字节假口径：红证实测同一
    载荷旧实现真实线 256001 字节 > 120832）≤ MAX_REQUEST_BYTES，余量 ≥ 10KB；
    REFERENCE_FULLTEXT_BYTES 改大即红（实测 +4096 → 124582 > 120832 红）。"""
    problem = "设" * EMBEDDED_CONTENT_CAP  # 题面截断上限（推导最坏形态 4000 中文）
    summaries = [
        ManifestSummary(f"mod{i}", "温湿度传感器采集与显示" * 8)
        for i in range(14)  # stm32 线 14 条摘要
    ]
    clarifications = tuple(
        (f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20)
    )

    prompt = _selection_user_prompt(
        problem,
        summaries,
        references=[_suggestion("big-ref", "大参考文件", "巨型参考")],
        reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_BYTES},
        clarifications=clarifications,
        hardware_words=DEFAULT_WORDLIST,
    )

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SELECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    total = len(json.dumps(payload).encode("utf-8"))
    assert total <= MAX_REQUEST_BYTES - 10 * 1024
    assert "内容过长，已截断" in prompt  # 历史段合计截断带标注
    assert f"仅展示前 {CLARIFICATION_HISTORY_CAP} 字符" in prompt
    assert f"仅展示前 {REFERENCE_FULLTEXT_BYTES} wire 字节" in prompt  # 全文 wire 预算截断带标注


def test_skeleton_prompt_worst_case_with_references_fits_request_budget():
    """结构测试（skeleton-smoke-refs/02 真机验收补）：锚定 ∪ 手动多篇全文按
    SKELETON_REFERENCE_TOTAL_BYTES 均分截断——完整 payload json.dumps 序列化
    ≤ MAX_REQUEST_BYTES 且余量 ≥ 10KB（真机 2021F 两篇曾 195232 字节 502）。"""
    problem = "设" * EMBEDDED_CONTENT_CAP
    interfaces = ["### 模块 m（h）\nvoid init(void);"] * 3
    refs = {
        f"ref-{i}": "中" * REFERENCE_FULLTEXT_BYTES for i in range(3)
    }

    prompt = _skeleton_user_prompt(problem, interfaces, refs)

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SKELETON_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    total = len(json.dumps(payload).encode("utf-8"))
    assert total <= MAX_REQUEST_BYTES - 10 * 1024
    per_ref = SKELETON_REFERENCE_TOTAL_BYTES // 3
    assert f"仅展示前 {per_ref} wire 字节" in prompt
    assert "内容过长，已截断" in prompt


def test_clarify_prompt_worst_case_fits_request_budget():
    """结构测试（工单 recommend-speedup/01 D + budget-wire-unification/01 换
    json.dumps 口径）：20 条长问答历史（截断后形态）+ 上限题面完整 payload
    json.dumps 序列化 ≤ MAX_REQUEST_BYTES；合计截断带标注。"""
    clarifications = tuple(
        (f"问题{i}：" + "疑" * 200, "答" * 5000) for i in range(20)
    )

    prompt = _clarify_user_prompt("设" * EMBEDDED_CONTENT_CAP, clarifications)

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": CLARIFY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    total = len(json.dumps(payload).encode("utf-8"))
    assert total <= MAX_REQUEST_BYTES - 10 * 1024
    assert "内容过长，已截断" in prompt  # 历史段合计截断带标注
    assert f"仅展示前 {CLARIFICATION_HISTORY_CAP} 字符" in prompt


def test_select_system_prompt_carries_no_reask_rule():
    """系统提示词补"已答不重问"：SELECT_SYSTEM_PROMPT 与 CLARIFY_SYSTEM_PROMPT
    同款措辞（两阶段语义一致——收敛阶段同样不换措辞反复补问）。"""
    assert "用户已回答过的问题不要重复问" in SELECT_SYSTEM_PROMPT
    assert "用户已回答过的问题不要重复问" in CLARIFY_SYSTEM_PROMPT  # 同款措辞在场


def test_prompts_carry_one_shot_question_rule():
    """两阶段提示词补"一轮问全"（工单 recommend-speedup/01）：有疑问时一次性
    把所有疑问全部列出（宁全勿漏、每条具体可答、最多 10 条），用户一轮全部
    答完，不要分批渐进追问——2021F 补问 4 轮 10 条的历史教训：渐进式追问
    是问答轮数多的根因。两阶段同款措辞。"""
    assert "一次性把所有疑问全部列出" in SELECT_SYSTEM_PROMPT
    assert "一次性把所有疑问全部列出" in CLARIFY_SYSTEM_PROMPT  # 同款措辞在场
    assert "不要分批渐进追问" in SELECT_SYSTEM_PROMPT
    assert "不要分批渐进追问" in CLARIFY_SYSTEM_PROMPT
    assert "最多 10 条" in SELECT_SYSTEM_PROMPT  # 上限防问题轰炸
    assert "最多 10 条" in CLARIFY_SYSTEM_PROMPT
