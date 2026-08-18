"""FastAPI 薄壳：端到端装配测试（工单 09）。

用 TestClient + 假上下文（tmp 配置 / 假模块库 / 假母版 / 假 LLM）驱动，
断言全部端点与验收项：生成流程完整可走通、AI 推荐展示理由、平台警告
明确呈现、生成结果就位（结构 / include path / main.c）、未落地平台显示
"暂不可用"、设置保存后即时生效。网络与 LLM 调用不进测试。
"""

from __future__ import annotations

import ast
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from contest_generator.config import (
    AppConfig,
    reference_library_dir,
    topic_library_dir,
)
from contest_generator.events import (
    EVENT_APPLY_RESULT,
    EVENT_BATCH_DONE,
    EVENT_BATCH_START,
    EVENT_COMPILE_START,
    EVENT_CONVERGED,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_FIX_START,
    EVENT_LLM_TELEMETRY,
    EVENT_PARSE_DONE,
    EVENT_PHASE_DONE,
    EVENT_QUESTION,
    EVENT_RETRY,
    EVENT_ROUND,
    EVENT_START,
    PHASE_DECIDE,
    PHASE_SUMMARY,
    ProgressEmitter,
    ProgressEvent,
)
from contest_generator.boards import board_for_platform
from contest_generator.fix_errors import FixSuggestion
from contest_generator.llm import (
    LLMObservationCollector,
    LOCAL_LLM_UNAVAILABLE_MESSAGE,
    LLMError,
    RoutingLLM,
    build_llm,
)
from contest_generator.pin_bindings import PinBindingError, resolve_bindings
from contest_generator.library import ValidationResult
from contest_generator.manifest import ManifestSummary
from contest_generator.selection import (
    FunctionRequirement,
    ModuleSelection,
    OutOfLibrarySuggestion,
    ReferenceSuggestion,
    resolve_selection,
)
from contest_generator.reference_library import add_reference
from contest_generator.report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    FileDecision,
    JudgmentFile,
    ReferenceCandidate,
)
from contest_generator.topic_library import TopicDraft
from contest_generator.master import distill_master, main_c_template, scan_project
from contest_generator.master_store import import_master
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.webapp import (
    AppContext,
    create_app,
)
from tests.fakes import (
    FAKE_DISTILL_UVPROJX_A,
    FakeLLM,
    FakeTransport,
    RecordingLLM,
    make_fake_ccs_master_project,
    make_fake_master_project,
    make_fake_module_library,
    make_fake_stm32_projects,
    make_sample_docx,
)
from tests.generate_wiring_fakes import (
    KIT_REFERENCE_ID,
    OTHER_REFERENCE_ID,
    TOPIC_PROBLEM_TEXT,
    TOPIC_REFERENCE_ID,
    UWB_REFERENCE_ID,
    make_fake_reference_library,
    make_fake_topic_library,
    make_kit_candidate_module,
    make_topic_specific_module,
)

SELECTION = ModuleSelection(
    modules=("dht11", "oled"),
    reasons={"dht11": "赛题要求采集温湿度", "oled": "需要显示测量结果"},
)


class RaisingLLM:
    """AI 服务失败用的假 LLM：任何职责都抛 LLMError（对应 502）。

    实现协议全部方法（编号提取的 LLMError 会被生成器按"自动识别尽力而为"
    接住降级，与协议契约一致——不再依赖调用方 getattr 探测）。
    """

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
    ) -> ModuleSelection:
        raise LLMError("服务不可用")

    def clarify(
        self, problem_text: str, clarifications: Sequence[tuple[str, str]]
    ) -> tuple[str, ...]:
        raise LLMError("服务不可用")

    def summarize_topic(self, problem_text: str) -> str:
        raise LLMError("服务不可用")

    def generate_main_skeleton(
        self,
        problem_text: str,
        module_interfaces: Sequence[str],
        reference_fulltexts: Mapping[str, str] | None = None,
    ) -> str:
        raise LLMError("服务不可用")

    def generate_smoke_main(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        raise LLMError("服务不可用")

    def summarize_module(self, code: str) -> str:
        raise LLMError("服务不可用")

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        raise LLMError("服务不可用")

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]:
        raise LLMError("服务不可用")

    def reference_summarize(self, material: str) -> str:
        raise LLMError("服务不可用")

    def reference_judge_archivable(
        self, candidates: Sequence[ReferenceCandidate]
    ) -> tuple[str, ...]:
        raise LLMError("服务不可用")

    def topic_split_topics(self, pdf_text: str) -> tuple[TopicDraft, ...]:
        raise LLMError("服务不可用")

    def topic_extract_number(self, text: str) -> str | None:
        raise LLMError("服务不可用")


class ScriptedDistillLLM:
    """假 LLM：distill_master 经 progress_emitter 发射脚本化事件后返回固定判定。

    事件序列与发射间隔由调用方给定（模拟真 LLM 的批次循环发射——工单 01 的
    发射 seam：假 LLM 与真 LLM 走同一参数）；completion 事件在返回判定后
    置位（断线测试观察"后端正常结束提炼"）。其余职责不会被提炼端点调用，
    按 RaisingLLM 同款直接抛错。
    """

    def __init__(
        self,
        decisions: tuple[FileDecision, ...],
        events: Sequence[ProgressEvent] = (),
        completion: threading.Event | None = None,
        delay: float = 0.0,
    ) -> None:
        self._decisions = decisions
        self._events = tuple(events)
        self._completion = completion
        self._delay = delay

    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[ManifestSummary]
    ) -> ModuleSelection:
        raise LLMError("ScriptedDistillLLM 只服务提炼端点")

    def clarify(
        self, problem_text: str, clarifications: Sequence[tuple[str, str]]
    ) -> tuple[str, ...]:
        raise LLMError("ScriptedDistillLLM 只服务提炼端点")

    def generate_main_skeleton(
        self,
        problem_text: str,
        module_interfaces: Sequence[str],
        reference_fulltexts: Mapping[str, str] | None = None,
    ) -> str:
        raise LLMError("ScriptedDistillLLM 只服务提炼端点")

    def generate_smoke_main(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        raise LLMError("ScriptedDistillLLM 只服务提炼端点")

    def summarize_module(self, code: str) -> str:
        raise LLMError("ScriptedDistillLLM 只服务提炼端点")

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        raise LLMError("ScriptedDistillLLM 只服务提炼端点")

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]:
        for event in self._events:
            if self._delay:
                time.sleep(self._delay)
            if progress_emitter is not None:
                progress_emitter(event)
        if self._completion is not None:
            self._completion.set()
        return self._decisions


# 假工程对的典型 AI 判定（与 tests/test_master.py 同一套素材）
# 公共文件（所有工程内容一致）同样由 AI 判定：基础建设必需 → keep（判例 06）
# 注意：.uvprojx 是工程配置文件（工单 09），由确定性规则处理、不在判定范围
DEFAULT_DECISIONS = (
    FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="官方库配置头，基础必需"),
    FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="系统初始化，基础必需"),
    FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用传感器驱动"),
    FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="上场比赛残留"),
    FileDecision(
        "src/oled.c",
        ACTION_MERGE,
        content="/* 通用 OLED 驱动（整合版） */\n",
        explanation="两版接口一致，整合去重",
        source="proj-b",
        reason="B 版本较新",
    ),
)


@pytest.fixture
def context(tmp_path):
    """已配置的假上下文：假模块库 + 空母版库 + 假 LLM，配置文件路径在 tmp 下。

    返回 (context, holder)；holder["llm"] 是当前 LLM，测试可随时换掉它
    （llm_factory 每次请求读 holder，换 LLM 即换行为）。
    """
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    masters_dir = tmp_path / "masters"
    holder = {"llm": FakeLLM(selection=SELECTION)}
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=masters_dir,
        ),
        llm_factory=lambda config: holder["llm"],
    )
    return ctx, holder


@pytest.fixture
def client(context):
    return TestClient(create_app(context[0]))


def _import_stm32_master(masters_dir, tmp_path) -> None:
    """给 stm32 平台导入一个母版（平台"落地"的判定条件）。"""
    import_master(masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "master_src"))


def _add_fake_k230_modules(library_dir: Path) -> None:
    """给假模块库补 k230 + coord_detect（工单 k230-vision-copilot/04 前端闭环
    素材，与真实库同形态）：k230 = 纯副产物模块（双平台 files 空 + pins 空，
    依赖 coord_detect——串口解析与引脚由它提供）；coord_detect = 真实
    uart_tx/uart_rx 角色声明。"""
    (library_dir / "k230").mkdir(parents=True, exist_ok=True)
    (library_dir / "k230" / "code").mkdir(parents=True, exist_ok=True)
    (library_dir / "k230" / "manifest.json").write_text(
        json.dumps(
            {
                "slug": "k230",
                "description": "K230 视觉副控：色块追踪/球检测的 K230 侧发送端",
                "dependencies": ["coord_detect"],
                "python_artifact": {"template": "code/main.py", "output": "main.py"},
                "platforms": {
                    "stm32": {
                        "files": [],
                        "verified": False,
                        "hardware_bound": True,
                        "notes": "串口解析与引脚由依赖 coord_detect 提供",
                    },
                    "mspm0": {
                        "files": [],
                        "verified": False,
                        "hardware_bound": True,
                        "notes": "串口解析与引脚由依赖 coord_detect 提供",
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (library_dir / "k230" / "code" / "main.py").write_text(
        "sensor.reset()\n# k230 假模板（无占位符，渲染原样透传）\n",
        encoding="utf-8",
    )
    (library_dir / "coord_detect").mkdir(parents=True, exist_ok=True)
    (library_dir / "coord_detect" / "code").mkdir(parents=True, exist_ok=True)
    (library_dir / "coord_detect" / "manifest.json").write_text(
        json.dumps(
            {
                "slug": "coord_detect",
                "description": "K230 视觉帧解析驱动",
                "dependencies": [],
                "platforms": {
                    "stm32": {
                        "files": ["code/coord_detect.c", "code/coord_detect.h"],
                        "verified": True,
                        "hardware_bound": True,
                        "notes": "",
                        "pins": [
                            {
                                "id": "COORD_DETECT_UART_TX",
                                "type": "uart_tx",
                                "default": "PA9",
                                "required": True,
                            },
                            {
                                "id": "COORD_DETECT_UART_RX",
                                "type": "uart_rx",
                                "default": "PA10",
                                "required": True,
                            },
                        ],
                    },
                    "mspm0": {
                        "files": ["code/coord_detect.c", "code/coord_detect.h"],
                        "verified": True,
                        "hardware_bound": True,
                        "notes": "",
                        "pins": [
                            {
                                "id": "COORD_DETECT_UART_TX",
                                "type": "uart_tx",
                                "default": "PA8",
                                "required": True,
                            },
                            {
                                "id": "COORD_DETECT_UART_RX",
                                "type": "uart_rx",
                                "default": "PA9",
                                "required": True,
                            },
                        ],
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (library_dir / "coord_detect" / "code" / "coord_detect.c").write_text(
        "#include \"coord_detect.h\"\n"
        "void coord_detect_init(void) {}\n"
        "void coord_detect_rx_handler(void) {}\n",
        encoding="utf-8",
    )
    (library_dir / "coord_detect" / "code" / "coord_detect.h").write_text(
        "#pragma once\n"
        "void coord_detect_init(void);\n"
        "void coord_detect_rx_handler(void);\n",
        encoding="utf-8",
    )


def _add_fake_led_module(library_dir: Path) -> None:
    """给假模块库补一个 led 多实例模块（stm32 内嵌母版 = files 空，与真实 led
    同形态）——webapp 路由透传 instances 的 happy path 素材。"""
    (library_dir / "led").mkdir(parents=True, exist_ok=True)
    (library_dir / "led" / "manifest.json").write_text(
        json.dumps(
            {
                "slug": "led",
                "description": "LED 指示灯驱动",
                "dependencies": [],
                "multi_instance": {"max": 8, "variant": "color"},
                "platforms": {
                    "stm32": {
                        "files": [],
                        "verified": True,
                        "hardware_bound": False,
                        "notes": "",
                        "kit": "",
                        "source_url": "",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# SSE 提炼流（工单 02）测试助手：解析 + done 载荷提取
# ---------------------------------------------------------------------------


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    """SSE 流解析：[(event 类型, data), ...]，空行分隔（线格式共享契约）。"""
    events = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_type = ""
        data = {}
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        events.append((event_type, data))
    return events


def _distill_stream(client, dirs) -> list[tuple[str, dict]]:
    """POST 提炼端点并解析 SSE 事件序列（断言 HTTP 200 起流 + text/event-stream）。"""
    resp = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": dirs}
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    return _parse_sse(resp.text)


def _distill_report(client, dirs) -> dict:
    """提炼端点 → done 载荷（完整报告）；流以 error 收尾则断言失败。"""
    events = _distill_stream(client, dirs)
    done = [data for kind, data in events if kind == EVENT_DONE]
    assert done, f"流未以 done 结束：{events}"
    return done[0]


def _recommend_stream(client, payload) -> list[tuple[str, dict]]:
    """POST 推荐端点（SSE 流，工单 10）并解析事件序列（HTTP 200 起流）。"""
    resp = client.post("/api/recommend", json=payload)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    return _parse_sse(resp.text)


def _recommend_done(client, payload) -> dict:
    """推荐端点 → done 载荷（推荐结果）；流以 error 收尾则断言失败。"""
    events = _recommend_stream(client, payload)
    done = [data for kind, data in events if kind == EVENT_DONE]
    assert done, f"流未以 done 结束：{events}"
    return done[0]


# ---------------------------------------------------------------------------
# 编译错误修复（工单 compile-error-fix/01）：SSE 流端到端 + 回滚
# ---------------------------------------------------------------------------


def _fix_project(tmp_path) -> Path:
    """生成结果目录样貌：main.c + code/mod.c（修复端到端断言用）。"""
    out = tmp_path / "project"
    out.mkdir()
    (out / "main.c").write_text(
        "int x = 1;\nint main(void) { return x; }\n", encoding="utf-8"
    )
    (out / "code").mkdir()
    (out / "code" / "mod.c").write_text("int mod(void) { return 1; }\n", encoding="utf-8")
    return out


def _fix_stream(client, payload) -> list[tuple[str, dict]]:
    """POST 修复端点并解析 SSE 事件序列（HTTP 200 起流）。"""
    resp = client.post("/api/fix-errors", json=payload)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    return _parse_sse(resp.text)


def _fix_done(client, payload) -> dict:
    """修复端点 → done 载荷；流以 error 收尾则断言失败。"""
    events = _fix_stream(client, payload)
    done = [data for kind, data in events if kind == EVENT_DONE]
    assert done, f"流未以 done 结束：{events}"
    return done[0]


def test_fix_errors_requires_error_text(client):
    resp = client.post("/api/fix-errors", json={"output_dir": "C:\\x"})
    assert resp.status_code == 400
    assert "error_text" in resp.json()["detail"]


def test_fix_errors_requires_existing_output_dir(client, tmp_path):
    resp = client.post(
        "/api/fix-errors",
        json={"output_dir": str(tmp_path / "gone"), "error_text": "main.c(1): error #20: boom"},
    )
    assert resp.status_code == 400
    assert "输出目录不存在" in resp.json()["detail"]


def test_fix_errors_end_to_end_fake_llm(client, context, tmp_path):
    """LLM fake 端到端（验收项）：构造报错 → 文件被正确修改 → 回滚恢复。"""
    out = _fix_project(tmp_path)
    holder = context[1]
    holder["llm"] = FakeLLM(
        fixes=(
            FixSuggestion(
                file="main.c", line=1, old_snippet="int x = 1;",
                new_snippet="int x = 2;", reason="修复初始化",
            ),
            FixSuggestion(
                file="code/mod.c", line=1, old_snippet="return 1;",
                new_snippet="return 0;", reason="修复返回值",
            ),
        )
    )
    done = _fix_done(
        client,
        {
            "output_dir": str(out),
            "error_text": "main.c(1): error #20: identifier \"x\" is undefined\n"
                          "code/mod.c:1: error: return type mismatch",
            "problem_text": "赛题：做个小车",
            "platform": "stm32",
            "slugs": ["dht11", "oled"],
            "main_c": "int main(void) { return 0; }",
        },
    )
    assert done["degraded"] is False
    assert {p["path"] for p in done["parsed"]} == {"main.c", "code/mod.c"}
    assert done["fixes"] == [
        {"file": "main.c", "line": 1, "status": "applied", "reason": ""},
        {"file": "code/mod.c", "line": 1, "status": "applied", "reason": ""},
    ]
    assert done["backup_id"]
    # 文件确实被修改
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 2;\nint main(void) { return x; }\n"
    assert (out / "code" / "mod.c").read_text(encoding="utf-8") == "int mod(void) { return 0; }\n"
    # 回滚恢复原样（验收项：回滚按钮恢复）
    resp = client.post(
        "/api/fix-errors/rollback",
        json={"output_dir": str(out), "backup_id": done["backup_id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["restored"] == ["code/mod.c", "main.c"]
    assert (out / "main.c").read_text(encoding="utf-8") == "int x = 1;\nint main(void) { return x; }\n"
    assert (out / "code" / "mod.c").read_text(encoding="utf-8") == "int mod(void) { return 1; }\n"


def test_fix_errors_event_sequence_and_context_passed(client, context, tmp_path):
    """事件序列契约（决策记录 8）：parse_done → fix_start → apply_result… → done。"""
    out = _fix_project(tmp_path)
    holder = context[1]
    holder["llm"] = FakeLLM(
        fixes=(FixSuggestion(file="main.c", line=1, old_snippet="int x = 1;", new_snippet="int x = 2;", reason=""),)
    )
    events = _fix_stream(
        client,
        {"output_dir": str(out), "error_text": "main.c(1): error #20: boom"},
    )
    assert [kind for kind, _ in events] == [
        EVENT_PARSE_DONE, EVENT_FIX_START, EVENT_APPLY_RESULT, EVENT_DONE,
    ]
    parse_done = events[0][1]
    assert parse_done["error_count"] == 1 and parse_done["file_count"] == 1
    apply_result = events[2][1]
    assert apply_result["file"] == "main.c" and apply_result["status"] == "applied"
    # 上下文（题面 / 平台 / 模块 / main.c）已透传给假 LLM
    call = holder["llm"].fix_errors_calls[0]
    assert call[1] == {"main.c": "int x = 1;\nint main(void) { return x; }\n"}
    assert call[2] == "" and call[3] == "" and call[4] == () and call[5] == ""


def test_fix_errors_sse_emits_content_safe_llm_telemetry(tmp_path):
    """真实 DeepSeekLLM 假传输：fix 流额外发 llm_telemetry，done 终态仍保持原形。"""
    out = _fix_project(tmp_path)
    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "fixes": [
                                    {
                                        "file": "main.c",
                                        "line": 1,
                                        "old_snippet": "int x = 1;",
                                        "new_snippet": "int x = 2;",
                                        "reason": "修复初始化",
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "unsafe_text": "secret-usage-content",
            },
        }
    )
    transport = FakeTransport(body=body)

    def factory(
        config: AppConfig,
        retry_budget=None,
        observation_collector: LLMObservationCollector | None = None,
    ):
        return build_llm(
            config,
            retry_budget=retry_budget,
            observation_collector=observation_collector,
            transport=transport,
        )

    config = AppConfig(
        api_key="sk-secret",
        module_library_dir=tmp_path / "modules",
        masters_dir=tmp_path / "masters",
    )
    ctx = AppContext(
        config=config,
        llm_factory=factory,
    )
    (tmp_path / "modules").mkdir()
    client = TestClient(create_app(ctx))

    events = _fix_stream(
        client,
        {
            "output_dir": str(out),
            "error_text": "main.c(1): error #20: secret-compile-output",
            "problem_text": "secret-problem-text",
        },
    )

    assert [kind for kind, _ in events] == [
        EVENT_PARSE_DONE,
        EVENT_FIX_START,
        EVENT_LLM_TELEMETRY,
        EVENT_APPLY_RESULT,
        EVENT_DONE,
    ]
    telemetry = events[2][1]
    assert telemetry["llm_workflow_id"].startswith("fix-errors:")
    assert telemetry["llm_total_calls"] == 1
    assert telemetry["llm_local_calls"] == 0
    assert telemetry["llm_deepseek_calls"] == 1
    assert telemetry["llm_latest_operation"] == "fix_compile_errors"
    assert telemetry["llm_error_kind"] == ""
    assert telemetry["llm_parse_status"] == "success"
    assert telemetry["llm_latest_http_status"] == 200
    assert telemetry["llm_attempts"] == 1
    assert telemetry["llm_retry_calls"] == 0
    assert telemetry["llm_error_calls"] == 0
    assert telemetry["llm_parse_error_calls"] == 0
    assert telemetry["llm_rate_limit_calls"] == 0
    assert telemetry["llm_network_error_calls"] == 0
    assert telemetry["llm_5xx_calls"] == 0
    assert telemetry["llm_budget_blocked_calls"] == 0
    assert telemetry["llm_request_bytes"] > 0
    assert telemetry["llm_duration_ms"] >= 0
    assert telemetry["llm_usage"] == {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
    assert telemetry["llm_calls"] == [
        {
            "workflow_id": telemetry["llm_workflow_id"],
            "sequence": 1,
            "operation": "fix_compile_errors",
            "provider": "deepseek",
            "route": "remote",
            "model": config.model,
            "duration_ms": telemetry["llm_calls"][0]["duration_ms"],
            "attempts": 1,
            "status": "success",
            "final": True,
            "call_id": 1,
            "budget_attempt": 1,
            "http_status": 200,
            "error_kind": None,
            "parse_status": "success",
            "request_bytes": telemetry["llm_request_bytes"],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }
    ]
    serialized = json.dumps(telemetry, ensure_ascii=False)
    assert "secret-problem-text" not in serialized
    assert "secret-compile-output" not in serialized
    assert "secret-usage-content" not in serialized
    assert "sk-secret" not in serialized
    assert events[-1][0] == EVENT_DONE
    assert "llm" not in events[-1][1]


def test_recent_llm_workflows_endpoint_returns_sanitized_completed_fix_workflow(tmp_path):
    """只读 recent endpoint：fix 流结束后返回 content-safe summary + call details。"""
    out = _fix_project(tmp_path)
    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "fixes": [
                                    {
                                        "file": "main.c",
                                        "line": 1,
                                        "old_snippet": "int x = 1;",
                                        "new_snippet": "int x = 2;",
                                        "reason": "修复初始化",
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "unsafe_text": "secret-usage-content",
            },
        }
    )
    transport = FakeTransport(body=body)

    def factory(
        config: AppConfig,
        retry_budget=None,
        observation_collector: LLMObservationCollector | None = None,
    ):
        return build_llm(
            config,
            retry_budget=retry_budget,
            observation_collector=observation_collector,
            transport=transport,
        )

    config = AppConfig(
        api_key="sk-secret",
        module_library_dir=tmp_path / "modules",
        masters_dir=tmp_path / "masters",
    )
    ctx = AppContext(config=config, llm_factory=factory)
    (tmp_path / "modules").mkdir()
    client = TestClient(create_app(ctx))

    _fix_stream(
        client,
        {
            "output_dir": str(out),
            "error_text": "main.c(1): error #20: secret-compile-output",
            "problem_text": "secret-problem-text",
        },
    )
    resp = client.get("/api/llm-workflows/recent")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["workflows"]) == 1
    workflow = data["workflows"][0]
    assert workflow["workflow_id"].startswith("fix-errors:")
    assert workflow["workflow_name"] == "fix-errors"
    assert workflow["call_count"] == 1
    assert workflow["local_calls"] == 0
    assert workflow["deepseek_calls"] == 1
    assert workflow["request_bytes"] > 0
    assert workflow["duration_ms"] >= 0
    assert workflow["status"] == "success"
    assert workflow["usage"] == {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
    assert workflow["calls"][0]["operation"] == "fix_compile_errors"
    assert workflow["calls"][0]["usage"] == workflow["usage"]
    # 估算字段（工单 llm-cost-control/01）：展示层派生，默认单价下该用量
    # (10 prompt × 2 + 2 completion × 8) / 1e6 ≈ 0，字段存在且为数值即可
    assert set(workflow["est"]) == {"est_cost_actual", "est_cost_deepseek", "est_savings"}
    assert workflow["est"]["est_cost_actual"] >= 0
    assert workflow["est"]["est_cost_deepseek"] >= workflow["est"]["est_cost_actual"]
    serialized = json.dumps(data, ensure_ascii=False)
    assert "secret-problem-text" not in serialized
    assert "secret-compile-output" not in serialized
    assert "secret-usage-content" not in serialized
    assert "sk-secret" not in serialized


def test_fix_errors_unsafe_fix_path_ends_with_error_event(client, context, tmp_path):
    """修复建议越界（../ 逃逸）→ 流内 error 终态 + 中文信息（HTTP 200 起流）。"""
    out = _fix_project(tmp_path)
    holder = context[1]
    holder["llm"] = FakeLLM(
        fixes=(FixSuggestion(file="../evil.c", line=1, old_snippet="a", new_snippet="b", reason=""),)
    )
    events = _fix_stream(
        client,
        {"output_dir": str(out), "error_text": "main.c(1): error #20: boom"},
    )
    errors = [data for kind, data in events if kind == EVENT_ERROR]
    assert errors, f"流未以 error 收尾：{events}"
    assert "路径不安全" in errors[0]["message"]
    # 越界不写任何文件
    assert (out / "main.c").read_text(encoding="utf-8").startswith("int x = 1;")


def test_fix_errors_degraded_mode_no_file_context(client, context, tmp_path):
    """报错无文件引用（链接错误等）→ 降级模式：无文件上下文，仍可 done。"""
    out = _fix_project(tmp_path)
    holder = context[1]
    holder["llm"] = FakeLLM()  # 默认空 fixes
    done = _fix_done(
        client,
        {
            "output_dir": str(out),
            "error_text": "L6200E: Symbol foo multiply defined (by main.o and bar.o)",
        },
    )
    assert done["degraded"] is True
    assert done["fixes"] == [] and done["backup_id"] == ""
    call = holder["llm"].fix_errors_calls[0]
    assert call[1] == {}  # 无文件上下文


def test_fix_errors_rollback_rejects_unsafe_backup_id(client, tmp_path):
    out = _fix_project(tmp_path)
    resp = client.post(
        "/api/fix-errors/rollback",
        json={"output_dir": str(out), "backup_id": "../evil"},
    )
    assert resp.status_code == 400
    assert "非法的备份编号" in resp.json()["detail"]


def test_fix_errors_rollback_missing_backup_raises(client, tmp_path):
    out = _fix_project(tmp_path)
    resp = client.post(
        "/api/fix-errors/rollback",
        json={"output_dir": str(out), "backup_id": "20260812-000000"},
    )
    assert resp.status_code == 400
    assert "备份不存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 自动编译（工单 autocompile-loop/01）：工具链探测 → 子进程编译 → SSE 事件
# ---------------------------------------------------------------------------


def _fake_uv4_bat(tmp_path: Path, exit_code: int, log_lines: list[str]) -> Path:
    """假 UV4：解析 `-o <log>` 参数写日志文件，按指定退出码退出（真实 .bat，
    子进程直接执行；内容与 tests/test_compile_runner.py 同构）。"""
    bat = tmp_path / "fake_uv4.bat"
    bat.write_text(
        "@echo off\r\nset LOG=\r\n:parse\r\nif \"%~1\"==\"\" goto run\r\n"
        'if "%~1"=="-o" set LOG=%~2\r\nshift\r\ngoto parse\r\n'
        ":run\r\n"
        + "".join(
            (f'echo {line} > "%LOG%"\r\n' if i == 0 else f'echo {line} >> "%LOG%"\r\n')
            for i, line in enumerate(line.strip() for line in log_lines)
        )
        + f"exit /b {exit_code}\r\n",
        encoding="utf-8",
    )
    return bat


def _stm32_project(tmp_path: Path) -> Path:
    out = tmp_path / "project"
    (out / "user").mkdir(parents=True)
    (out / "user" / "Project.uvprojx").write_text("<Project/>", encoding="utf-8")
    return out


def _compile_stream(client, payload) -> list[tuple[str, dict]]:
    """POST 编译端点并解析 SSE 事件序列（HTTP 200 起流）。"""
    resp = client.post("/api/compile", json=payload)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    return _parse_sse(resp.text)


def test_compile_requires_output_dir_exists(client, tmp_path):
    resp = client.post(
        "/api/compile",
        json={"platform": PLATFORM_STM32, "output_dir": str(tmp_path / "gone")},
    )
    assert resp.status_code == 400
    assert "输出目录不存在" in resp.json()["detail"]


def test_compile_no_toolchain_400_chinese(client, context, tmp_path, monkeypatch):
    """无工具链 → 400 中文（前端据此置灰按钮回退贴文本模式）。"""
    monkeypatch.setattr("contest_generator.compile_runner.find_uv4", lambda override: None)
    resp = client.post(
        "/api/compile",
        json={"platform": PLATFORM_STM32, "output_dir": str(_stm32_project(tmp_path))},
    )
    assert resp.status_code == 400
    assert "工具链" in resp.json()["detail"]


def test_compile_without_ai_config_streams_done(tmp_path, monkeypatch):
    """无 AI 配置（config=None）→ /api/compile 照常起流出 done（工单
    compile-verdict-align/01：编译不调 LLM，只须工具链路径——无 api_key 的
    用户应能"编译看结果"；修复按钮仍走 AI 配置校验，循环自然停）。"""
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))
    out = _stm32_project(tmp_path)
    fake_uv4 = _fake_uv4_bat(
        tmp_path, 0,
        ["Build started: Project: fake", "0 Error(s) 0 Warning(s)."],
    )
    monkeypatch.setattr("contest_generator.compile_runner.find_uv4", lambda override: fake_uv4)
    events = _compile_stream(client, {"platform": PLATFORM_STM32, "output_dir": str(out)})
    assert [kind for kind, _ in events] == [EVENT_COMPILE_START, EVENT_DONE]
    assert events[1][1]["passed"] is True
    assert events[1][1]["summary"] == {"errors": 0, "warnings": 0}


def test_compile_mspm0_no_make_400_chinese(client, context, tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.compile_runner.find_make", lambda override: None)
    out = tmp_path / "project"
    (out / "Debug").mkdir(parents=True)
    (out / "Debug" / "makefile").write_text("all:\n", encoding="utf-8")
    resp = client.post(
        "/api/compile",
        json={"platform": PLATFORM_MSPM0, "output_dir": str(out)},
    )
    assert resp.status_code == 400
    assert "gmake" in resp.json()["detail"]


def test_compile_stm32_end_to_end_events_and_passed(client, context, tmp_path, monkeypatch):
    """端到端：compile_start → done（exit_code / error_text / passed），假 UV4
    写 -o 日志文件 → 原样采集（与 fix-errors 解析契约对齐）。"""
    out = _stm32_project(tmp_path)
    fake_uv4 = _fake_uv4_bat(tmp_path, 0, ["Build started: Project: fake", "0 Error(s) 0 Warning(s)."])
    monkeypatch.setattr("contest_generator.compile_runner.find_uv4", lambda override: fake_uv4)
    events = _compile_stream(client, {"platform": PLATFORM_STM32, "output_dir": str(out)})
    assert [kind for kind, _ in events] == [EVENT_COMPILE_START, EVENT_DONE]
    done = events[1][1]
    assert done["platform"] == PLATFORM_STM32
    assert done["exit_code"] == 0 and done["passed"] is True and done["timed_out"] is False
    assert "0 Error(s)" in done["error_text"]
    assert "user/Project.uvprojx" in done["project_file"].replace("\\", "/")
    assert "-r" in done["command"]  # 全量重建（决策记录 4）
    assert done["output_dir"] == str(out)


def test_compile_stm32_errors_reported_not_passed(client, context, tmp_path, monkeypatch):
    """编译有错（exit 2）→ done 携带 error_text 与 passed=False（走修复循环）。"""
    out = _stm32_project(tmp_path)
    fake_uv4 = _fake_uv4_bat(
        tmp_path, 2,
        ["Build started: Project: fake", r'..\main.c(10): error #20: identifier "x" is undefined', "1 Error(s) 0 Warning(s)."],
    )
    monkeypatch.setattr("contest_generator.compile_runner.find_uv4", lambda override: fake_uv4)
    done = _compile_stream(client, {"platform": PLATFORM_STM32, "output_dir": str(out)})[-1][1]
    assert done["exit_code"] == 2 and done["passed"] is False
    assert r'..\main.c(10): error #20' in done["error_text"]


def test_compile_structure_error_is_stream_error_event(client, context, tmp_path, monkeypatch):
    """工程结构异常（没有 .uvprojx）→ 流内 error 事件（HTTP 200 起流），文案写具体。"""
    out = tmp_path / "project"
    out.mkdir()
    fake_uv4 = _fake_uv4_bat(tmp_path, 0, ["0 Error(s)"])
    monkeypatch.setattr("contest_generator.compile_runner.find_uv4", lambda override: fake_uv4)
    events = _compile_stream(client, {"platform": PLATFORM_STM32, "output_dir": str(out)})
    errors = [data for kind, data in events if kind == EVENT_ERROR]
    assert errors, f"流未以 error 收尾：{events}"
    assert ".uvprojx" in errors[0]["message"]


def test_compile_done_payload_carries_duration_parsed_summary(
    client, context, tmp_path, monkeypatch
):
    """展示层（工单 compile-experience-ui/01）：done 追加 duration / parsed_errors
    / summary，不改旧字段——红证：实施前本测试断言失败。"""
    out = _stm32_project(tmp_path)
    fake_uv4 = _fake_uv4_bat(
        tmp_path, 2,
        [
            "Build started: Project: fake",
            r'..\main.c(10): error #20: identifier "x" is undefined',
            "1 Error(s), 0 Warning(s).",
        ],
    )
    monkeypatch.setattr("contest_generator.compile_runner.find_uv4", lambda override: fake_uv4)
    done = _compile_stream(client, {"platform": PLATFORM_STM32, "output_dir": str(out)})[-1][1]
    # 既有字段不动
    assert done["exit_code"] == 2 and done["passed"] is False
    assert r'..\main.c(10): error #20' in done["error_text"]
    # 新增字段
    assert isinstance(done["duration"], float) and done["duration"] > 0
    assert done["summary"] == {"errors": 1, "warnings": 0}
    assert done["parsed_errors"] == [
        {
            "path": "../main.c",
            "line": 10,
            "message": r'..\main.c(10): error #20: identifier "x" is undefined',
        }
    ]
    # 与 fix-errors done 的 parsed 同构（同字段集）
    assert set(done["parsed_errors"][0]) == {"path", "line", "message"}


def test_compile_done_success_summary_zero(client, context, tmp_path, monkeypatch):
    """成功编译（汇总行 0 Error 0 Warning）→ summary {0,0}、parsed_errors 空。"""
    out = _stm32_project(tmp_path)
    fake_uv4 = _fake_uv4_bat(tmp_path, 0, ["Build started: Project: fake", "0 Error(s) 0 Warning(s)."])
    monkeypatch.setattr("contest_generator.compile_runner.find_uv4", lambda override: fake_uv4)
    done = _compile_stream(client, {"platform": PLATFORM_STM32, "output_dir": str(out)})[-1][1]
    assert done["summary"] == {"errors": 0, "warnings": 0}
    assert done["parsed_errors"] == []
    assert done["duration"] > 0


# ---------------------------------------------------------------------------
# 源码行接口（工单 compile-experience-ui/01）：薄读取 + 双基准路径判决
# ---------------------------------------------------------------------------


def _source_line(client, output_dir, path, line) -> Any:
    return client.post(
        "/api/compile/source-line",
        json={"output_dir": str(output_dir), "path": path, "line": line},
    )


def test_source_line_hit_returns_current_line(client, tmp_path):
    """命中 → 200 {path_resolved, line_text}（读修复后的当前文件）。"""
    out = tmp_path / "proj"
    out.mkdir()
    (out / "main.c").write_text("int main(void) {\n    return 0;\n}\n", encoding="utf-8")
    resp = _source_line(client, out, "main.c", 2)
    assert resp.status_code == 200
    assert resp.json() == {"path_resolved": "main.c", "line_text": "    return 0;"}


def test_source_line_dual_benchmark_dotdot_hit(client, tmp_path):
    """UV4 `..\\` 形态：uvprojx 在 user/ 子目录，按工程文件基准解析回工程根。"""
    out = tmp_path / "proj"
    (out / "user").mkdir(parents=True)
    (out / "user" / "Project.uvprojx").write_text("<x/>", encoding="utf-8")
    (out / "main.c").write_text("int main(void) {\n    return 0;\n}\n", encoding="utf-8")
    resp = _source_line(client, out, "../main.c", 1)
    assert resp.status_code == 200
    assert resp.json() == {"path_resolved": "main.c", "line_text": "int main(void) {"}


def test_source_line_escape_rejected(client, tmp_path):
    """containment：`..\\..\\` 穿越 → 400 中文（双基准解析后仍越界拒绝）。"""
    out = tmp_path / "proj"
    (out / "user").mkdir(parents=True)
    (out / "user" / "Project.uvprojx").write_text("<x/>", encoding="utf-8")
    (tmp_path / "outside.c").write_text("x", encoding="utf-8")
    for path in ("../../outside.c", "../outside.c"):
        resp = _source_line(client, out, path, 1)
        assert resp.status_code == 400
        assert ("越界" in resp.json()["detail"]) or ("不存在" in resp.json()["detail"])


def test_source_line_missing_file_400(client, tmp_path):
    out = tmp_path / "proj"
    out.mkdir()
    resp = _source_line(client, out, "main.c", 1)
    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


def test_source_line_line_out_of_range_400(client, tmp_path):
    out = tmp_path / "proj"
    out.mkdir()
    (out / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    resp = _source_line(client, out, "main.c", 99)
    assert resp.status_code == 400
    assert "越界" in resp.json()["detail"]


def test_source_line_requires_valid_line(client, tmp_path):
    """line 缺失 / 非数字 / 小于 1 → 400（参数校验）。"""
    out = tmp_path / "proj"
    out.mkdir()
    (out / "main.c").write_text("x", encoding="utf-8")
    for payload in (
        {"output_dir": str(out), "path": "main.c"},
        {"output_dir": str(out), "path": "main.c", "line": "abc"},
        {"output_dir": str(out), "path": "main.c", "line": 0},
    ):
        resp = client.post("/api/compile/source-line", json=payload)
        assert resp.status_code == 400


def test_compile_mspm0_gmake_end_to_end(client, context, tmp_path, monkeypatch):
    """mspm0 线：Debug/makefile + gmake → done（stdout 原样采集）。"""
    out = tmp_path / "project"
    (out / "Debug").mkdir(parents=True)
    (out / "Debug" / "makefile").write_text("all:\n", encoding="utf-8")
    fake_make = tmp_path / "gmake.bat"
    fake_make.write_text(
        "@echo off\r\n"
        "echo gmake: Entering directory Debug\r\n"
        "echo code/main.c:45: error: use of undeclared identifier 'y'\r\n"
        "exit /b 2\r\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("contest_generator.compile_runner.find_make", lambda override: fake_make)
    done = _compile_stream(client, {"platform": PLATFORM_MSPM0, "output_dir": str(out)})[-1][1]
    assert done["exit_code"] == 2 and done["passed"] is False
    assert "undeclared" in done["error_text"]
    assert "-B" in done["command"]  # 全量重建（决策记录 4）


# ---------------------------------------------------------------------------
# 全局状态：平台可用性（验收项 5：未落地平台显示"暂不可用"而非报错）
# ---------------------------------------------------------------------------


def test_state_lists_platforms_with_availability(client, context, tmp_path):
    _import_stm32_master(context[0].config.masters_dir, tmp_path)

    state = client.get("/api/state").json()

    assert state["api_configured"] is True
    platforms = {p["id"]: p for p in state["platforms"]}
    assert set(platforms) == {PLATFORM_STM32, PLATFORM_MSPM0}
    # 有母版 → ready；无母版 → no-master（界面显示"暂不可用"，不报错）
    assert platforms[PLATFORM_STM32]["status"] == "ready"
    assert platforms[PLATFORM_MSPM0]["status"] == "no-master"


def test_state_reports_unconfigured_api(tmp_path):
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))

    state = client.get("/api/state").json()

    assert state["api_configured"] is False
    assert state["llm"] is None
    # 未配置时工作目录展示默认值
    assert state["module_library_dir"]
    assert state["masters_dir"]


def test_pick_directory_returns_absolute_path(context):
    context[0].pick_directory = lambda: r"D:\contest\demo"

    resp = TestClient(create_app(context[0])).post("/api/pick-directory")

    assert resp.status_code == 200
    assert resp.json() == {"path": r"D:\contest\demo"}


def test_pick_directory_cancel_returns_null(context):
    context[0].pick_directory = lambda: None  # 用户取消：null，前端不覆盖手输

    resp = TestClient(create_app(context[0])).post("/api/pick-directory")

    assert resp.status_code == 200
    assert resp.json() == {"path": None}


def test_state_maps_corrupt_master_meta_to_400(client, context, tmp_path):
    # 母版目录在但元数据损坏：state 给 400 提示而非 500
    _import_stm32_master(context[0].config.masters_dir, tmp_path)
    (context[0].config.masters_dir / "stm32.json").write_text("{not json", encoding="utf-8")

    resp = client.get("/api/state")

    assert resp.status_code == 400
    assert "元数据" in resp.json()["detail"]


def test_ai_endpoints_reject_with_hint_when_unconfigured(tmp_path):
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))

    resp = client.post("/api/recommend", json={"problem_text": "题目"})

    assert resp.status_code == 400
    assert "未配置 AI API" in resp.json()["detail"]

    resp = client.post("/api/topic/summarize", json={"problem_text": "题目"})

    assert resp.status_code == 400
    assert "未配置 AI API" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 生成流程（验收项 1）：抽取 → 推荐 → 展开 → 骨架 → 生成
# ---------------------------------------------------------------------------


def test_extract_uploaded_text_file(client):
    resp = client.post(
        "/api/extract", files={"upload": ("题目.txt", "设计一个温湿度采集系统".encode("utf-8"), "text/plain")}
    )

    assert resp.status_code == 200
    assert "温湿度" in resp.json()["text"]


def test_extract_uploaded_docx_file(client, tmp_path):
    docx = make_sample_docx(tmp_path / "题.docx", ["第一题：信号采集", "第二段：显示"])

    resp = client.post(
        "/api/extract",
        files={"upload": ("题.docx", docx.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert resp.status_code == 200
    assert "信号采集" in resp.json()["text"]


def test_extract_unsupported_type_returns_clear_error(client):
    resp = client.post(
        "/api/extract", files={"upload": ("题.exe", b"MZ", "application/octet-stream")}
    )

    assert resp.status_code == 400
    assert "不支持的文件类型" in resp.json()["detail"]


def test_topic_summarize_returns_summary(client, context):
    """赛题简介：单次 LLM 调用返回一句话总览 + 功能要点（只展示，不进下游）。"""
    resp = client.post(
        "/api/topic/summarize", json={"problem_text": "温湿度采集并显示"}
    )

    assert resp.status_code == 200
    assert resp.json() == {"summary": "AI 生成的赛题简介"}
    assert context[1]["llm"].topic_summarize_calls == [("温湿度采集并显示",)]


def test_topic_summarize_requires_problem_text(client):
    resp = client.post("/api/topic/summarize", json={})

    assert resp.status_code == 400
    assert "problem_text" in resp.json()["detail"]


def test_topic_summarize_llm_failure_maps_to_502(client, context):
    context[1]["llm"] = RaisingLLM()

    resp = client.post("/api/topic/summarize", json={"problem_text": "题"})

    assert resp.status_code == 502
    assert resp.json()["detail"] == "AI 服务调用失败：服务不可用"


def test_recommend_returns_modules_with_reasons(client):
    data = _recommend_done(client, {"problem_text": "温湿度采集并显示"})

    # 顶层 modules[] 格式与旧契约一致（下游 selectedSlugs / expand / generate
    # 零改动）；旧假 LLM 无功能需求层 → requirements 为空数组
    assert data["modules"] == [
        {"slug": "dht11", "reason": "赛题要求采集温湿度"},
        {"slug": "oled", "reason": "需要显示测量结果"},
    ]
    assert data["requirements"] == []


def test_expand_resolves_dependencies_and_warns_on_missing_platform(client):
    # oled 只有 stm32 版本：选它在 mspm0 上展开必须给出 missing 警告
    resp = client.post(
        "/api/selection/expand", json={"slugs": ["dht11", "oled"], "platform": PLATFORM_MSPM0}
    )

    assert resp.status_code == 200
    data = resp.json()
    slugs = [m["slug"] for m in data["modules"]]
    # 依赖 delay 被自动带入，且排在依赖方之前
    assert slugs == ["delay", "dht11", "oled"]
    kinds = {w["kind"] for w in data["warnings"]}
    assert "missing" in kinds
    missing = next(w for w in data["warnings"] if w["kind"] == "missing")
    assert "oled" in missing["message"]


def test_expand_reports_unverified_and_hardware_bound(client, context):
    # 给 dht11 的 mspm0 版本打上"未验证 + 硬件绑定"标记后重新展开
    manifest_path = context[0].config.module_library_dir / "dht11" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["platforms"][PLATFORM_MSPM0]["verified"] = False
    data["platforms"][PLATFORM_MSPM0]["hardware_bound"] = True
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    resp = client.post(
        "/api/selection/expand", json={"slugs": ["dht11"], "platform": PLATFORM_MSPM0}
    )

    kinds = {w["kind"] for w in resp.json()["warnings"]}
    assert {"unverified", "hardware_bound"} <= kinds


def test_expand_k230_brings_coord_detect_pins_generically(client, context):
    """工单 k230-vision-copilot/04 验收①：k230（files 空 + pins 空）走现有通用
    机制——模块池 / 展开 / 引脚配置零新 UI；展开后依赖 coord_detect 自动挂上，
    其 uart_tx/uart_rx 角色（k230 不重复声明）就是前端引脚卡的配置项来源。"""
    _add_fake_k230_modules(context[0].config.module_library_dir)

    resp = client.post(
        "/api/selection/expand", json={"slugs": ["k230"], "platform": PLATFORM_STM32}
    )

    assert resp.status_code == 200
    data = resp.json()
    slugs = [m["slug"] for m in data["modules"]]
    assert slugs == ["coord_detect", "k230"]  # 依赖先于使用者，自动带入
    k230 = next(m for m in data["modules"] if m["slug"] == "k230")
    assert k230["platforms"]["stm32"]["files"] == []
    assert k230["platforms"]["stm32"]["pins"] == []  # 串口引脚不重复声明
    coord = next(m for m in data["modules"] if m["slug"] == "coord_detect")
    assert [p["type"] for p in coord["platforms"]["stm32"]["pins"]] == [
        "uart_tx",
        "uart_rx",
    ]
    kinds = {w["kind"] for w in data["warnings"]}
    assert {"unverified", "hardware_bound"} <= kinds  # k230 未上板 + 硬件绑定


def test_generate_with_k230_writes_py_and_summary_lists_it(client, context, tmp_path):
    """工单 k230-vision-copilot/04 验收②：勾选 k230 → 生成产物 = 主控工程
    （coord_detect 解析随依赖进工程）+ K230 main.py 副产物（工程根）；摘要
    python_artifacts 让前端「模块文件」行显示 main.py。"""
    _add_fake_k230_modules(context[0].config.module_library_dir)
    _import_stm32_master(context[0].config.masters_dir, tmp_path)
    output_dir = tmp_path / "out" / "k230_demo"

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["k230"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(output_dir),
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    # 主控工程：依赖 coord_detect 解析代码随生成进工程；k230 自身无 C 子树
    assert (output_dir / "modules" / "coord_detect" / "code" / "coord_detect.c").is_file()
    assert not (output_dir / "modules" / "k230").exists()
    # K230 侧 .py 副产物落在工程根，内容 = 模板渲染结果
    assert (output_dir / "main.py").read_text(encoding="utf-8") == (
        "sensor.reset()\n# k230 假模板（无占位符，渲染原样透传）\n"
    )
    # 摘要：modules 里 k230 files 空，python_artifacts 单独给出副产物清单
    assert {"slug": "k230", "files": []} in data["modules"]
    assert data["python_artifacts"] == [{"slug": "k230", "output": "main.py"}]
    assert "main.py" in data["structure"]


def test_expand_rejects_unknown_module(client):
    resp = client.post(
        "/api/selection/expand", json={"slugs": ["nope"], "platform": PLATFORM_STM32}
    )

    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


def test_skeleton_returns_main_c_and_intercepts_undefined_calls(client, context):
    # 假 LLM 返回的骨架里混了一个接口中不存在的调用 → 改写为注释占位
    context[1]["llm"]._main_skeleton = (
        "int main(void) { float t = dht11_read(); dht11_init(); while (1); }\n"
    )

    resp = client.post(
        "/api/skeleton",
        json={"problem_text": "温湿度采集", "slugs": ["dht11"], "platform": PLATFORM_STM32},
    )

    assert resp.status_code == 200
    main_c = resp.json()["main_c"]
    assert "int main(void)" in main_c
    # 真实接口的调用保留；不存在的调用被占位且名字出现在拦截清单里
    assert "dht11_read();" in main_c
    assert "dht11_init" not in main_c.replace("dht11_init", "", 1) or "TODO" in main_c
    assert resp.json()["intercepted"] == ["dht11_init"]


def test_skeleton_rejects_instances_with_unknown_slug(client):
    """instances 的 slug 不在选中集 → 400 中文（module-multi-instance/04 请求层）。"""
    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "温湿度采集",
            "slugs": ["dht11"],
            "platform": PLATFORM_STM32,
            "instances": {"led": [{"name": "红灯"}]},
        },
    )

    assert resp.status_code == 400
    assert "未选中" in resp.json()["detail"]


def test_skeleton_rejects_instances_with_empty_name(client):
    """instances 的 name 空 → 400 中文。"""
    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "温湿度采集",
            "slugs": ["dht11"],
            "platform": PLATFORM_STM32,
            "instances": {"dht11": [{"name": ""}]},
        },
    )

    assert resp.status_code == 400
    assert "name" in resp.json()["detail"]




def test_llm_factory_receives_shared_retry_budget_and_collector_for_skeleton(tmp_path):
    budgets = []
    collectors = []

    def factory(
        config: AppConfig,
        retry_budget=None,
        observation_collector: LLMObservationCollector | None = None,
    ):
        budgets.append(retry_budget)
        collectors.append(observation_collector)
        return FakeLLM(main_skeleton="int main(void) { while(1) {} }\n")

    modules = make_fake_module_library(tmp_path / "modules")
    masters = tmp_path / "masters"
    import_master(masters, PLATFORM_STM32, make_fake_master_project(tmp_path / "master"))
    ctx = AppContext(
        config=AppConfig(api_key="sk-test", module_library_dir=modules, masters_dir=masters),
        llm_factory=factory,
    )
    client = TestClient(create_app(ctx))

    response = client.post(
        "/api/skeleton",
        json={"problem_text": "赛题", "platform": PLATFORM_STM32, "slugs": []},
    )

    assert response.status_code == 200
    assert len(budgets) >= 2
    assert budgets[0] is not None
    assert budgets[0] is budgets[1]
    assert collectors[0] is not None
    assert collectors[0] is collectors[1]
    assert collectors[0].workflow_id.startswith("skeleton:")


def test_llm_factory_receives_shared_retry_budget_and_collector_for_recommend(tmp_path):
    budgets = []
    collectors = []

    def factory(
        config: AppConfig,
        retry_budget=None,
        observation_collector: LLMObservationCollector | None = None,
    ):
        budgets.append(retry_budget)
        collectors.append(observation_collector)
        return FakeLLM(selection=ModuleSelection(modules=(), reasons={}))

    ctx = AppContext(
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=tmp_path / "modules",
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=factory,
    )
    (tmp_path / "modules").mkdir()
    client = TestClient(create_app(ctx))

    frames = list(client.post("/api/recommend", json={"problem_text": "赛题"}).iter_lines())

    assert any("event: done" in line for line in frames)
    assert len(budgets) >= 2
    assert budgets[0] is not None
    assert budgets[0] is budgets[1]
    assert collectors[0] is not None
    assert collectors[0] is collectors[1]
    assert collectors[0].workflow_id.startswith("recommend:")


def test_skeleton_forwards_instances_to_llm(client, context):
    """instances 透传到骨架接口块：led×2（两个红灯）→ LLM 收到 LED_RED_2 通道
    宏（多实例路径，module-multi-instance/04 请求层接线）。"""
    _add_fake_led_module(context[0].config.module_library_dir)
    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "四个指示灯",
            "slugs": ["led"],
            "platform": PLATFORM_STM32,
            "instances": {
                "led": [
                    {"name": "红灯", "variant": "red"},
                    {"name": "红灯2", "variant": "red"},
                ]
            },
        },
    )

    assert resp.status_code == 200
    interfaces = context[1]["llm"].skeleton_calls[0][1]
    assert any("#define LED_RED_2" in block for block in interfaces)


def test_generate_rejects_instances_with_unknown_slug(client, context, tmp_path):
    """generate 请求层同样校验 instances（slug 不在选中集 → 400 中文）。"""
    _import_stm32_master(context[0].config.masters_dir, tmp_path)
    output_dir = tmp_path / "out" / "demo"
    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(output_dir),
            "instances": {"led": [{"name": "红灯"}]},
        },
    )

    assert resp.status_code == 400
    assert "未选中" in resp.json()["detail"]


def test_generate_assembles_project_with_structure_include_path_and_main(
    client, context, tmp_path
):
    _import_stm32_master(context[0].config.masters_dir, tmp_path)
    output_dir = tmp_path / "out" / "demo"

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11", "oled"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(output_dir),
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    # 验收项 4：工程结构 / include path / main.c 就位
    assert data["output_dir"] == str(output_dir)
    assert (output_dir / "main.c").is_file()
    assert (output_dir / "modules" / "dht11" / "inc" / "dht11.h").is_file()
    assert (output_dir / "modules" / "delay" / "delay.c").is_file()
    # include 目录与生成器实际注册的一致：根目录文件 → modules/<slug>，不含 "/."
    assert data["include_dirs"] == [
        "modules/delay",
        "modules/dht11/stm32/src",
        "modules/dht11/inc",
        "modules/oled/stm32/src",
        "modules/oled/inc",
    ]
    assert "main.c" in data["structure"]
    assert data["build_hint"] == ""  # stm32 无构建脚本提示（工单 mspm0-build-makefiles/01）
    # 未选任何带 python_artifact 声明的模块 → 副产物清单空（旧行为不变）
    assert data["python_artifacts"] == []
    # 修改器生效：.uvprojx 注册了模块分组与 include path
    uvprojx = next(output_dir.glob("*.uvprojx")).read_text(encoding="utf-8")
    assert "modules" in uvprojx
    assert "modules\\dht11\\inc" in uvprojx


def test_generate_mspm0_with_ccs_tools_writes_makefile_set(
    client, context, tmp_path, monkeypatch
):
    """工单 mspm0-build-makefiles/01：mspm0 生成探 CCS 三件套 → 命中则产出
    Debug/makefile 集（一键编译修复通路打通），build_hint 空。"""
    from contest_generator.compile_runner import CcsTools

    import_master(
        context[0].config.masters_dir,
        PLATFORM_MSPM0,
        make_fake_ccs_master_project(tmp_path / "ccs_master_src"),
    )
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    compiler = tmp_path / "compiler"
    compiler.mkdir()
    cli = tmp_path / "cli.bat"
    cli.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "contest_generator.webapp.find_ccs_tools",
        lambda s, c, x: CcsTools(sdk_dir=sdk, compiler_dir=compiler, sysconfig_cli=cli),
    )
    output_dir = tmp_path / "out"

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_MSPM0,
            "slugs": ["dht11", "delay"],
            "main_c": "int main(void) { float t = dht11_read(); while (1); }\n",
            "output_dir": str(output_dir),
        },
    )

    assert resp.status_code == 200
    assert resp.json()["build_hint"] == ""
    makefile = (output_dir / "Debug" / "makefile").read_text(encoding="utf-8")
    assert "-include modules/dht11/mspm0/src/subdir_vars.mk" in makefile
    assert "-include modules/delay/subdir_vars.mk" in makefile


def test_generate_mspm0_without_ccs_tools_succeeds_with_hint(
    client, context, tmp_path, monkeypatch
):
    """探测不到 CCS：生成照常（不阻断，决策记录 3）+ build_hint 非空 + 无
    Debug/（探测是装配层职责，直接生成调用方不传探针 = 确定性跳过）。"""
    from contest_generator.compile_runner import CCS_NOT_FOUND_HINT

    import_master(
        context[0].config.masters_dir,
        PLATFORM_MSPM0,
        make_fake_ccs_master_project(tmp_path / "ccs_master_src"),
    )
    monkeypatch.setattr(
        "contest_generator.webapp.find_ccs_tools", lambda s, c, x: None
    )
    output_dir = tmp_path / "out"

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_MSPM0,
            "slugs": ["dht11", "delay"],
            "main_c": "int main(void) { float t = dht11_read(); while (1); }\n",
            "output_dir": str(output_dir),
        },
    )

    assert resp.status_code == 200
    assert resp.json()["build_hint"] == CCS_NOT_FOUND_HINT
    assert (output_dir / "main.c").is_file()
    assert not (output_dir / "Debug").exists()


def test_generate_rejects_platform_without_master(client, context, tmp_path):
    # mspm0 无母版（未落地）：明确报错而非产出残缺工程
    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_MSPM0,
            "slugs": ["dht11"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(tmp_path / "out"),
        },
    )

    assert resp.status_code == 400
    assert "母版" in resp.json()["detail"]


def test_generate_rejects_main_c_with_undefined_calls(client, context, tmp_path):
    _import_stm32_master(context[0].config.masters_dir, tmp_path)

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": "int main(void) { nonexistent_call(); while (1); }\n",
            "output_dir": str(tmp_path / "out"),
        },
    )

    assert resp.status_code == 400
    assert "不存在的函数" in resp.json()["detail"]


def test_generate_unknown_platform_returns_400_chinese(client, context, tmp_path):
    """实证 bug 修复（工单 C6）：platform 非法（用户可控输入）→ 400 中文。

    UnknownPlatformError 原漏登记（error_to_http 表外）→ 500 "服务器内部
    错误"，用户可控输入打在"真 bug"路径上；登记后 {"platform": "foo"} 得
    可修复的 400，message 带已注册平台清单。
    """
    resp = client.post(
        "/api/generate",
        json={
            "platform": "foo",
            "slugs": ["dht11"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(tmp_path / "out"),
        },
    )

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "未知平台" in detail
    assert "stm32" in detail  # 带已注册平台清单，用户可直接修正重试


# ---------------------------------------------------------------------------
# 校验端点（工单 pin-verdict-seam/01）：POST /api/bindings/validate 跑
# resolve_bindings 返回 {ok} / {ok:false, error}，error 与 generate 400 逐字
# 一致（同一实现）。module_library_dir 指向真库（引脚角色 / 板定义判定需要
# 真 manifest pins；本端点不调 LLM，FakeLLM 不触发）。
# ---------------------------------------------------------------------------

REAL_LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"


@pytest.fixture
def bindings_client(tmp_path):
    """校验端点专用客户端：真模块库（引脚角色判定真值源）+ 空母版库。"""
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=REAL_LIBRARY_MODULES,
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=lambda config: FakeLLM(selection=SELECTION),
    )
    return TestClient(create_app(ctx))


def _validate(client, platform, slugs, bindings):
    return client.post(
        "/api/bindings/validate",
        json={"platform": platform, "slugs": slugs, "bindings": bindings},
    )


def _resolve_verdict(platform, slugs, bindings):
    """端点应该跑同一 resolve_bindings：直接算期望判定（逐字一致性断言源）。

    与端点同源：resolve_selection 的 manifests + board_for_platform 的板——
    保证校验与生成吃同一份输入，逐字比对 error。
    """
    manifests = resolve_selection(REAL_LIBRARY_MODULES, platform, slugs).manifests
    board = board_for_platform(platform)
    try:
        resolve_bindings(manifests, platform, board, bindings)
    except PinBindingError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


def test_bindings_validate_valid_stm32_binding_ok(bindings_client):
    """有效绑定 → {ok:true}（stm32 pwm 类型级：PA6 = TIM3_CH1）。"""
    resp = _validate(bindings_client, PLATFORM_STM32, ["motor"], {"motor.MOTOR_A_PWM": "PA6"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_bindings_validate_empty_and_default_ok(bindings_client):
    """空 bindings / 全默认 = ok:true（旧行为不误拦）——含不发字段与显式 null。"""
    assert _validate(bindings_client, PLATFORM_STM32, ["motor"], {}).json() == {"ok": True}
    assert _validate(bindings_client, PLATFORM_STM32, ["motor"], None).json() == {"ok": True}
    resp = bindings_client.post(
        "/api/bindings/validate", json={"platform": PLATFORM_STM32, "slugs": ["motor"]}
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_bindings_validate_invalid_verbatim_matches_resolve_bindings(bindings_client):
    """各类非法 400 文案逐字一致：端点 error == resolve_bindings 的 PinBindingError
    文案（同一实现，不复制文案）——逐字比对覆盖类型级下限 / 未知角色 /
    mspm0 槽位冲突 / stm32 UART 成对绑定四类拒绝分支。"""
    cases = (
        (PLATFORM_STM32, ["motor"], {"motor.MOTOR_A_PWM": "PB4"}),  # PB4 无 pwm token
        (PLATFORM_STM32, ["motor"], {"motor.NO_SUCH_ROLE": "PA0"}),  # 未知角色
        (PLATFORM_MSPM0, ["huidu", "pid"], {"huidu.L1": "PB2", "pid.GRAY_D1": "PB3"}),  # 槽位冲突
        (PLATFORM_STM32, ["digit_uart"], {"digit_uart.DIGIT_UART_TX": "PB10"}),  # TX/RX 成对
    )
    for platform, slugs, bindings in cases:
        resp = _validate(bindings_client, platform, slugs, bindings)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["error"]  # 非空中文
        assert body == _resolve_verdict(platform, slugs, bindings)


def test_bindings_validate_requires_platform(bindings_client):
    """platform 缺失 → 400（_require_str 必填；slugs 缺省 = 空清单 → ok:true，
    与 generate 同款 _require_str_list 语义）。"""
    resp = bindings_client.post("/api/bindings/validate", json={"slugs": ["motor"]})
    assert resp.status_code == 400
    assert "platform" in resp.json()["detail"]


def test_recommend_llm_failure_ends_stream_with_error_event(client, context):
    """推荐端点（SSE 流）：LLM 失败以流内 error 事件收尾（HTTP 保持 200 起流，
    与提炼端点同款——客户端只认事件，不依赖状态码）。"""
    context[1]["llm"] = RaisingLLM()  # 换掉假 LLM：直接抛 LLMError

    events = _recommend_stream(client, {"problem_text": "题目"})

    assert events[-1][0] == EVENT_ERROR
    assert "AI 服务调用失败" in events[-1][1]["message"]


# ---------------------------------------------------------------------------
# 模块库（工单 07 装配）
# ---------------------------------------------------------------------------


def test_modules_list_returns_all(client):
    resp = client.get("/api/modules")

    assert resp.status_code == 200
    slugs = [m["slug"] for m in resp.json()]
    assert slugs == ["broken", "delay", "dht11", "oled"]
    dht11 = next(m for m in resp.json() if m["slug"] == "dht11")
    assert dht11["dependencies"] == ["delay"]
    assert set(dht11["platforms"]) == {PLATFORM_STM32, PLATFORM_MSPM0}
    # 列表 API 返回新字段：存量无身份字段的条目以空值呈现（迁移不打断）
    assert dht11["platforms"][PLATFORM_STM32]["kit"] == ""
    assert dht11["platforms"][PLATFORM_STM32]["source_url"] == ""


def test_add_module_validates_then_stores(client):
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "超声波测距模块",
            "files": {
                "ultrasonic.c": "float distance(void);\n",
                "ultrasonic.h": "#pragma once\nfloat distance(void);\n",
            },
            "dependencies": ["delay"],
            "notes": "接 PA0",
            "kit": "STM32F103C8T6 最小系统板",
            "source_url": "https://item.jd.com/1000123456.html",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["slug"] == "ultrasonic"
    listed = client.get("/api/modules").json()
    stored = next(m for m in listed if m["slug"] == "ultrasonic")
    assert stored["dependencies"] == ["delay"]
    assert stored["platforms"][PLATFORM_STM32]["notes"] == "接 PA0"
    # 身份字段透传入库，列表 API 返回新字段
    assert stored["platforms"][PLATFORM_STM32]["kit"] == "STM32F103C8T6 最小系统板"
    assert (
        stored["platforms"][PLATFORM_STM32]["source_url"]
        == "https://item.jd.com/1000123456.html"
    )


def test_add_module_drafts_description_when_empty(client):
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "",
            "files": {"ultrasonic.c": "float distance(void);\n"},
        },
    )

    assert resp.status_code == 200
    assert resp.json()["draft"] == "AI 生成的模块简介"
    # 草稿阶段不入库
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_add_module_rejects_inconsistent_description(client, context):
    context[1]["llm"]._validation = ValidationResult(consistent=False, issues="简介与代码不符")

    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "与代码不符的简介",
            "files": {"ultrasonic.c": "float distance(void);\n"},
            "kit": "STM32F103C8T6 最小系统板",
            "source_url": "https://item.jd.com/1000123456.html",
        },
    )

    assert resp.status_code == 400
    assert "不一致" in resp.json()["detail"]
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_add_module_rejects_non_boolean_flags(client):
    # 字符串 "false" 宽松强转会静默翻转硬件绑定标记：必须严格布尔
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "超声波测距模块",
            "hardware_bound": "false",
            "files": {"ultrasonic.c": "float distance(void);\n"},
        },
    )

    assert resp.status_code == 400
    assert "布尔值" in resp.json()["detail"]
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_module_description_update_and_delete(client):
    slug = "dht11"
    resp = client.put(
        f"/api/modules/{slug}/description", json={"description": "温湿度传感器（已编辑）"}
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "温湿度传感器（已编辑）"

    resp = client.delete(f"/api/modules/{slug}")
    assert resp.status_code == 200
    assert slug not in [m["slug"] for m in client.get("/api/modules").json()]


def test_module_add_platform_files(client):
    resp = client.post(
        "/api/modules/oled/platform-files",
        json={
            "platform": PLATFORM_MSPM0,
            "files": {"mspm0/src/oled.c": "void oled_init(void);\n"},
            "kit": "地猛星 MSPM0G3507 开发板",
            "source_url": "https://item.jd.com/6543210001.html",
        },
    )

    assert resp.status_code == 200
    assert PLATFORM_MSPM0 in resp.json()["platforms"]
    # 新增平台版本透传身份字段
    assert resp.json()["platforms"][PLATFORM_MSPM0]["kit"] == "地猛星 MSPM0G3507 开发板"
    assert (
        resp.json()["platforms"][PLATFORM_MSPM0]["source_url"]
        == "https://item.jd.com/6543210001.html"
    )


def test_add_module_rejects_missing_identity_fields(client):
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "超声波测距模块",
            "files": {"ultrasonic.c": "float distance(void);\n"},
            "hardware_bound": True,
        },
    )

    assert resp.status_code == 400
    assert "kit" in resp.json()["detail"]
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_add_module_pure_logic_without_identity_ok(client):
    resp = client.post(
        "/api/modules",
        json={
            "slug": "zone",
            "platform": PLATFORM_STM32,
            "description": "区域判定逻辑（纯软件）",
            "files": {"zone.c": "int zone_determine(void);\n"},
        },
    )

    assert resp.status_code == 200
    entry = resp.json()["platforms"][PLATFORM_STM32]
    assert entry["kit"] == ""
    assert entry["source_url"] == ""
    assert resp.json()["slug"] in [m["slug"] for m in client.get("/api/modules").json()]


def test_add_module_rejects_invalid_source_url(client):
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "超声波测距模块",
            "files": {"ultrasonic.c": "float distance(void);\n"},
            "kit": "STM32F103C8T6 最小系统板",
            "source_url": "item.jd.com/1000.html",  # 无协议
        },
    )

    assert resp.status_code == 400
    assert "格式非法" in resp.json()["detail"]
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_module_add_platform_files_rejects_missing_identity(client, context):
    resp = client.post(
        "/api/modules/oled/platform-files",
        json={
            "platform": PLATFORM_MSPM0,
            "files": {"mspm0/src/oled.c": "void oled_init(void);\n"},
            "hardware_bound": True,
        },
    )

    assert resp.status_code == 400
    assert "kit" in resp.json()["detail"]
    # 拒绝后无残留：新平台版本的文件与 manifest 条目都不落盘
    library_dir = context[0].config.module_library_dir
    assert not (library_dir / "oled" / "mspm0" / "src" / "oled.c").exists()
    listed = next(m for m in client.get("/api/modules").json() if m["slug"] == "oled")
    assert PLATFORM_MSPM0 not in listed["platforms"]


# ---------------------------------------------------------------------------
# 存量身份补填编辑路径（工单 02）：PUT /api/modules/{slug}/platform-identity
# ---------------------------------------------------------------------------


def test_platform_identity_edit_backfills_legacy_entry(client, context):
    """存量无身份字段的平台条目（dht11 stm32）经编辑路径补填：保存成功、
    列表 API 立即可见，且不触发 AI 一致性校验（FakeLLM 无调用记录）。"""
    llm = context[1]["llm"]

    resp = client.put(
        "/api/modules/dht11/platform-identity",
        json={
            "platform": PLATFORM_STM32,
            "kit": "STM32F103C8T6 最小系统板",
            "source_url": "https://item.jd.com/1000123456.html",
        },
    )

    assert resp.status_code == 200
    entry = resp.json()["platforms"][PLATFORM_STM32]
    assert entry["kit"] == "STM32F103C8T6 最小系统板"
    assert entry["source_url"] == "https://item.jd.com/1000123456.html"
    # 保存立即生效：列表 API 可见新字段
    listed = next(m for m in client.get("/api/modules").json() if m["slug"] == "dht11")
    assert listed["platforms"][PLATFORM_STM32]["kit"] == "STM32F103C8T6 最小系统板"
    assert (
        listed["platforms"][PLATFORM_STM32]["source_url"]
        == "https://item.jd.com/1000123456.html"
    )
    # 身份是事实信息：编辑不走 AI 一致性校验
    assert llm.validation_calls == []
    assert llm.summary_calls == []


def test_platform_identity_edit_preserves_other_entry_fields(client, context):
    """只改身份字段：文件列表、验证状态、硬件绑定、备注原样保留。"""
    resp = client.put(
        "/api/modules/dht11/platform-identity",
        json={
            "platform": PLATFORM_STM32,
            "kit": "STM32F103C8T6 最小系统板",
            "source_url": "https://item.jd.com/1000123456.html",
        },
    )

    assert resp.status_code == 200
    entry = resp.json()["platforms"][PLATFORM_STM32]
    assert entry["verified"] is True
    assert entry["hardware_bound"] is False
    assert entry["notes"] == "PA0"
    assert entry["files"] == ["stm32/src/dht11.c", "inc/dht11.h"]


def test_platform_identity_edit_rejects_invalid_source_url(client, context):
    resp = client.put(
        "/api/modules/dht11/platform-identity",
        json={
            "platform": PLATFORM_STM32,
            "kit": "STM32F103C8T6 最小系统板",
            "source_url": "item.jd.com/1000.html",  # 无协议
        },
    )

    assert resp.status_code == 400
    assert "格式非法" in resp.json()["detail"]
    # 拒绝不落盘：列表 API 里身份字段仍为空
    listed = next(m for m in client.get("/api/modules").json() if m["slug"] == "dht11")
    assert listed["platforms"][PLATFORM_STM32]["kit"] == ""
    assert listed["platforms"][PLATFORM_STM32]["source_url"] == ""


def test_platform_identity_edit_rejects_empty_identity(client, context):
    resp = client.put(
        "/api/modules/dht11/platform-identity",
        json={"platform": PLATFORM_STM32, "kit": "", "source_url": ""},
    )

    assert resp.status_code == 400
    assert "至少填写一个硬件身份字段" in resp.json()["detail"]


def test_platform_identity_edit_rejects_missing_platform(client, context):
    resp = client.put(
        "/api/modules/dht11/platform-identity",
        json={"kit": "STM32F103C8T6 最小系统板"},
    )

    assert resp.status_code == 400
    assert "缺少必填字段" in resp.json()["detail"]


def test_platform_identity_edit_unknown_platform_entry(client, context):
    """目标平台条目不存在：明确报错而非静默改别的条目。"""
    resp = client.put(
        "/api/modules/oled/platform-identity",
        json={
            "platform": PLATFORM_MSPM0,
            "kit": "地猛星 MSPM0G3507 开发板",
            "source_url": "https://item.jd.com/6543210001.html",
        },
    )

    assert resp.status_code == 400
    assert "没有平台" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 母版（工单 08 装配）：扫描 → 提炼 → 确认入库 → 浏览 → 删除
# ---------------------------------------------------------------------------


def test_master_flow_scan_distill_confirm_list_delete(client, context, tmp_path):
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]

    scanned = client.post("/api/masters/scan", json={"project_dirs": dirs}).json()
    assert [p["name"] for p in scanned] == ["proj-a", "proj-b"]
    assert all(p["platform"] == PLATFORM_STM32 for p in scanned)

    report = _distill_report(client, dirs)
    assert report["projects"] == ["proj-a", "proj-b"]
    # keep = 规则条目（.uvprojx 工程配置文件，工单 09）+ AI 判定保留
    assert [d["path"] for d in report["keep"]] == [
        "project.uvprojx", "inc/stm32f10x_conf.h", "src/system_stm32f10x.c",
        "sensors/dht11.c",
    ]
    config = next(d for d in report["keep"] if d["path"] == "project.uvprojx")
    assert "确定性模板现写" in config["reason"]
    assert [d["path"] for d in report["merge"]] == ["src/oled.c"]
    # exclude = AI 判定 + 规则识别的残留（带规则化原因，含 IDE 用户选项 .uvoptx）
    # + 旧工程 main.c（模板替代）
    assert [d["path"] for d in report["exclude"]] == [
        "ui/oled_fonts.c",
        "main.c.bak",
        "project.uvoptx",
        "src/oled.hex",
        "src/oled.o",
        "ui/oled_fonts.c~",
        "main.c",
    ]
    residue = next(d for d in report["exclude"] if d["path"] == "src/oled.o")
    assert residue["reason"] == "构建产物：.o 文件"
    uvoptx = next(d for d in report["exclude"] if d["path"] == "project.uvoptx")
    assert uvoptx["reason"] == "IDE 用户选项：编译时自动重建"
    main_c = next(d for d in report["exclude"] if d["path"] == "main.c")
    assert main_c["action"] == ACTION_EXCLUDE
    assert "模板" in main_c["reason"]
    # 报告携带模板 main.c 与 .uvprojx 全文预览：一次确认前用户能看到将要写入
    # 母版的 main.c 与工程文件
    assert report["main_c_preview"] == main_c_template(PLATFORM_STM32)
    assert report["main_c_preview"]
    assert report["uvprojx_preview"]
    assert "STM32F103C8" in report["uvprojx_preview"]

    confirmed = client.post(
        "/api/masters/confirm",
        json={**report, "project_dirs": dirs},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["platform"] == PLATFORM_STM32
    assert confirmed.json()["sources"] == ["proj-a", "proj-b"]

    stored = context[0].config.masters_dir / PLATFORM_STM32
    # 母版 main.c = 确定性模板，旧工程 main.c 不进母版（ADR 0002）
    assert (stored / "main.c").read_text(encoding="utf-8") == main_c_template(
        PLATFORM_STM32
    )
    assert "proj-a 的赛题 main" not in (stored / "main.c").read_text(encoding="utf-8")

    masters = client.get("/api/masters").json()
    assert [m["platform"] for m in masters] == [PLATFORM_STM32]

    resp = client.delete(f"/api/masters/{PLATFORM_STM32}")
    assert resp.status_code == 200
    assert client.get("/api/masters").json() == []


def test_master_confirm_rejects_user_edited_merge_on_unique(client, context, tmp_path):
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]
    report = _distill_report(client, dirs)
    # 用户把 sensors/dht11.c（只有一份内容，没有整合对象）从保留改成合并
    report["keep"] = [d for d in report["keep"] if d["path"] != "sensors/dht11.c"]
    report["merge"].append(
        {
            "path": "sensors/dht11.c",
            "action": ACTION_MERGE,
            "content": "/* 整合 */",
            "explanation": "用户改的",
            "source": "proj-b",
            "reason": "用户改的",
        }
    )

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 400
    assert "只用于" in resp.json()["detail"]
    assert client.get("/api/masters").json() == []  # 确认失败不入库


def test_master_confirm_rejects_restoring_old_main_c(client, context, tmp_path):
    """旧工程 main.c 由模板确定性替代：用户把 main.c 从剔除改成保留 → 拒绝入库。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]
    report = _distill_report(client, dirs)
    # 用户想把旧 main.c 恢复进母版——确定性替代不因用户编辑而失效
    report["exclude"] = [d for d in report["exclude"] if d["path"] != "main.c"]
    report["keep"].append(
        {"path": "main.c", "action": ACTION_KEEP, "reason": "用户改的"}
    )

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 400
    assert "旧工程 main.c 必须剔除" in resp.json()["detail"]
    assert client.get("/api/masters").json() == []  # 确认失败不入库


def test_master_confirm_user_moves_common_to_exclude(client, context, tmp_path):
    """公共文件默认保留，但用户确认时可改为剔除（经 HTTP 端到端）。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]
    report = _distill_report(client, dirs)
    report["keep"] = [d for d in report["keep"] if d["path"] != "inc/stm32f10x_conf.h"]
    report["exclude"].append(
        {"path": "inc/stm32f10x_conf.h", "action": ACTION_EXCLUDE, "reason": "用户确认剔除"}
    )

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 200
    stored = context[0].config.masters_dir / PLATFORM_STM32
    assert not (stored / "inc/stm32f10x_conf.h").exists()
    assert client.get("/api/masters").json() == [{
        "platform": PLATFORM_STM32,
        "sources": ["proj-a", "proj-b"],
        "warnings": [],
    }]


def test_master_confirm_invalid_ai_merged_uvprojx_returns_400(context, tmp_path):
    """.uvprojx 是工程配置文件（工单 09），用户确认时改成剔除 → 业务失败 400
    带中文 message，不裸 500（条目不可改动作，同基础设施强制）。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = (
        FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="必需"),
        FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="必需"),
        FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用"),
        FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="残留"),
        FileDecision(
            "src/oled.c",
            ACTION_MERGE,
            content="/* 整合 */\n",
            explanation="整合",
            source="proj-b",
            reason="整合",
        ),
    )
    client = TestClient(create_app(context[0]), raise_server_exceptions=False)
    dirs = [str(proj_a), str(proj_b)]
    report = _distill_report(client, dirs)
    # 用户确认时把 .uvprojx（工程配置文件）改成剔除——确定性规则处理不可改
    # 动作（工单 09 决策 7）→ 400 带中文 message，不裸 500
    report["keep"] = [d for d in report["keep"] if d["path"] != "project.uvprojx"]
    report["exclude"].append(
        {"path": "project.uvprojx", "action": ACTION_EXCLUDE, "reason": "用户改的"}
    )

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 400
    assert "工程配置文件必须保留" in resp.json()["detail"]
    assert client.get("/api/masters").json() == []  # 失败不入库


def test_master_distill_rejects_ai_on_uvprojx_returns_400(client, context, tmp_path):
    """AI 给工程配置文件（.uvprojx）判定 → 越界 → 提炼阶段流内 error 事件
    （中文 message）而非带病进确认流程。

    .uvprojx 由确定性渲染器现写（工单 09，判例 09 治本）：AI 从未在判定素材
    里见过它，给出判定即越界——在确认前大声失败。HTTP 保持 200 起流，失败
    以 error 事件收尾（客户端只认事件，不依赖状态码）。
    """
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = (
        FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="必需"),
        FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="必需"),
        FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用"),
        FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="残留"),
        FileDecision(
            "project.uvprojx", ACTION_EXCLUDE, reason="AI 认为不需要工程文件"
        ),
        FileDecision(
            "src/oled.c",
            ACTION_MERGE,
            content="/* 整合 */\n",
            explanation="整合",
            source="proj-b",
            reason="整合",
        ),
    )
    dirs = [str(proj_a), str(proj_b)]

    events = _distill_stream(client, dirs)

    assert [kind for kind, _ in events] == [EVENT_ERROR]
    assert "无需 AI 判定" in events[0][1]["message"]
    assert client.get("/api/masters").json() == []  # 失败不入库


# ---------------------------------------------------------------------------
# 母版提炼 SSE 流（工单 02）：事件顺序 / done 载荷 / error 收尾 / 零批次 / 断线
# ---------------------------------------------------------------------------


# 脚本化发射序列：模拟真 LLM 批次循环的完整事件流（阶段 1 带补问轮）
SCRIPTED_EVENTS = (
    ProgressEvent(
        type=EVENT_START, judgment_count=5, summary_batch_count=1, decide_batch_count=1
    ),
    ProgressEvent(
        type=EVENT_BATCH_START,
        phase=PHASE_SUMMARY,
        batch_index=1,
        batch_count=1,
        paths=(
            "inc/stm32f10x_conf.h", "src/system_stm32f10x.c", "sensors/dht11.c",
            "ui/oled_fonts.c", "src/oled.c",
        ),
    ),
    ProgressEvent(
        type=EVENT_RETRY, phase=PHASE_SUMMARY, batch_index=1, retry_round=1, missing_count=1
    ),
    ProgressEvent(
        type=EVENT_BATCH_DONE, phase=PHASE_SUMMARY, batch_index=1, processed_count=5
    ),
    ProgressEvent(type=EVENT_PHASE_DONE, phase=PHASE_SUMMARY, file_count=5),
    ProgressEvent(
        type=EVENT_BATCH_START,
        phase=PHASE_DECIDE,
        batch_index=1,
        batch_count=1,
        paths=(
            "inc/stm32f10x_conf.h", "src/system_stm32f10x.c", "sensors/dht11.c",
            "ui/oled_fonts.c", "src/oled.c",
        ),
    ),
    ProgressEvent(
        type=EVENT_BATCH_DONE, phase=PHASE_DECIDE, batch_index=1, processed_count=5
    ),
    ProgressEvent(type=EVENT_PHASE_DONE, phase=PHASE_DECIDE, file_count=5),
)


def test_distill_streams_progress_events_then_done_with_report(client, context, tmp_path):
    """事件顺序 = 发射序列原样透传（start → 批事件 → 补问 → 阶段完成），
    done 载荷 = 完整报告（与同步路径同构，前端报告渲染原样复用）。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"] = ScriptedDistillLLM(DEFAULT_DECISIONS, events=SCRIPTED_EVENTS)
    dirs = [str(proj_a), str(proj_b)]

    events = _distill_stream(client, dirs)

    assert [kind for kind, _ in events] == [
        EVENT_START, EVENT_BATCH_START, EVENT_RETRY, EVENT_BATCH_DONE, EVENT_PHASE_DONE,
        EVENT_BATCH_START, EVENT_BATCH_DONE, EVENT_PHASE_DONE, EVENT_DONE,
    ]
    # 进度事件字段原样透传（键名 = 工单 01 契约 ProgressEvent）
    start = events[0][1]
    assert start["judgment_count"] == 5
    assert start["summary_batch_count"] == 1
    assert start["decide_batch_count"] == 1
    batch_start = events[1][1]
    assert batch_start["phase"] == PHASE_SUMMARY
    assert batch_start["batch_index"] == 1
    assert batch_start["batch_count"] == 1
    assert batch_start["paths"] == [
        "inc/stm32f10x_conf.h", "src/system_stm32f10x.c", "sensors/dht11.c",
        "ui/oled_fonts.c", "src/oled.c",
    ]
    assert events[2][1]["retry_round"] == 1
    assert events[2][1]["missing_count"] == 1
    assert events[3][1]["processed_count"] == 5
    assert events[4][1]["file_count"] == 5
    assert events[5][1]["phase"] == PHASE_DECIDE
    # done 载荷 = 完整提炼报告：同素材同步提炼（不经 HTTP）的 report.to_dict()
    expected = distill_master(
        ScriptedDistillLLM(DEFAULT_DECISIONS),
        PLATFORM_STM32,
        [scan_project(proj_a), scan_project(proj_b)],
    ).to_dict()
    assert events[-1][0] == EVENT_DONE
    assert events[-1][1] == expected


def test_distill_no_judgment_files_streams_done_directly(client, context, tmp_path):
    """无待判文件（全部文件都是规则处理的残留 / main.c / 配置文件）→ 不发射
    任何批事件、阶段直接完成 → done（spec「批数为 0」），报告只有规则条目。"""
    project = tmp_path / "empty-judgment"
    (project / "src").mkdir(parents=True)
    (project / "main.c").write_text("int main(void) { while (1); }\n", encoding="utf-8")
    (project / "project.uvprojx").write_text(FAKE_DISTILL_UVPROJX_A, encoding="utf-8")
    (project / "project.uvoptx").write_text("<ProjectOpt/>", encoding="utf-8")
    (project / "main.c.bak").write_text("backup", encoding="utf-8")
    (project / "src/oled.hex").write_text("hex junk", encoding="utf-8")
    context[1]["llm"] = ScriptedDistillLLM(
        (),
        events=(
            ProgressEvent(
                type=EVENT_START, judgment_count=0, summary_batch_count=0,
                decide_batch_count=0,
            ),
            ProgressEvent(type=EVENT_PHASE_DONE, phase=PHASE_SUMMARY, file_count=0),
            ProgressEvent(type=EVENT_PHASE_DONE, phase=PHASE_DECIDE, file_count=0),
        ),
    )

    events = _distill_stream(client, [str(project)])

    assert [kind for kind, _ in events] == [
        EVENT_START, EVENT_PHASE_DONE, EVENT_PHASE_DONE, EVENT_DONE,
    ]
    report = events[-1][1]
    assert report["projects"] == ["empty-judgment"]
    # 规则条目照常进报告：工程配置文件 keep，残留 / 旧 main.c exclude（无 AI 判定）
    assert [d["path"] for d in report["keep"]] == ["project.uvprojx"]
    assert [d["path"] for d in report["exclude"]] == [
        "main.c.bak", "project.uvoptx", "src/oled.hex", "main.c",
    ]


def test_distill_llm_error_ends_stream_with_error_event(client, context, tmp_path):
    """AI 服务失败（LLMError）→ 流内 error 事件（中文 message），HTTP 保持
    200 起流 → 流结束，不再有其他事件。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"] = RaisingLLM()

    events = _distill_stream(client, [str(proj_a), str(proj_b)])

    assert events == [(EVENT_ERROR, {"message": "AI 服务调用失败：服务不可用"})]


def test_distill_scan_error_ends_stream_with_error_event(client, context, tmp_path):
    """业务失败（工程目录不存在）→ 流内 error 事件（中文 message）→ 流结束。"""
    events = _distill_stream(client, [str(tmp_path / "nope")])

    assert [kind for kind, _ in events] == [EVENT_ERROR]
    assert "工程目录不存在" in events[0][1]["message"]


def test_distill_disconnect_lets_backend_finish(client, context, tmp_path):
    """客户端提前断开（读到第一个事件后关闭）：后端照常结束本次提炼——发射
    器不抛异常、不堵提炼线程（spec「断线」：确认前不落任何东西，无副作用）。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    completion = threading.Event()
    context[1]["llm"] = ScriptedDistillLLM(
        DEFAULT_DECISIONS, events=SCRIPTED_EVENTS, completion=completion, delay=0.02
    )
    dirs = [str(proj_a), str(proj_b)]

    with client.stream(
        "POST",
        "/api/masters/distill",
        json={"platform": PLATFORM_STM32, "project_dirs": dirs},
    ) as resp:
        assert resp.status_code == 200
        first = next(resp.iter_lines())
        assert first.startswith(f"event: {EVENT_START}")
        # 读到第一个事件后立即断开（退出 with 即关闭响应，流无人消费）

    assert completion.wait(timeout=5), "断线后后端应照常完成本次提炼"


def test_distill_rejects_unconfigured_api_before_streaming(tmp_path):
    """未配置 AI API：起流前 400（不产生 SSE 流，与其他 AI 端点同款提示）。"""
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))

    resp = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": []}
    )

    assert resp.status_code == 400
    assert "未配置 AI API" in resp.json()["detail"]


def test_master_stage_folder_upload_then_scan(client, tmp_path):
    """「选择文件夹」上传（/api/masters/stage）→ 暂存目录 → 可喂扫描 / 提炼。

    浏览器不暴露绝对路径，整夹上传由 multipart 承载：每个文件的文件名 =
    文件夹内相对路径（webkitRelativePath）；返回的暂存目录路径直接进
    project_dirs，目录名保留原文件夹名（扫描 / 报告 / 入库显示原名）。
    """
    proj_a, _ = make_fake_stm32_projects(tmp_path / "old")
    # 浏览器 webkitRelativePath = "原文件夹名/相对路径"（首段是选中的文件夹名）
    files = [
        ("files", (str(p.relative_to(proj_a.parent)).replace("\\", "/"), p.read_bytes()))
        for p in proj_a.rglob("*")
        if p.is_file()
    ]
    resp = client.post("/api/masters/stage", files=files)
    assert resp.status_code == 200, resp.text
    staged = resp.json()["staged"]
    assert [s["name"] for s in staged] == ["proj-a"]
    staged_dir = Path(staged[0]["path"])
    assert staged_dir.is_dir()
    assert (staged_dir / "src" / "oled.c").read_text(encoding="utf-8").startswith("/* 通用 OLED")
    assert not (staged_dir / ".git").exists()   # 版本库跳过，与前端过滤一致
    # 暂存目录可直接进扫描：平台检测 / 文件清单与原目录一致
    scanned = client.post("/api/masters/scan", json={"project_dirs": [str(staged_dir)]}).json()
    assert scanned[0]["name"] == "proj-a"
    assert scanned[0]["platform"] == PLATFORM_STM32
    assert "src/oled.c" in scanned[0]["files"]


def test_master_stage_rejects_bad_relative_paths(client):
    """上传带 .. / 绝对路径 / 盘符的文件名 → 400；空文件名框架级拦截（不落盘）。"""
    for bad in ("../evil.c", "/abs/evil.c", "C:/evil.c"):
        resp = client.post("/api/masters/stage", files=[("files", (bad, b"x"))])
        assert resp.status_code == 400, bad
        assert "非法文件路径" in resp.json()["detail"]
    resp = client.post("/api/masters/stage", files=[("files", ("", b"x"))])
    assert resp.status_code in (400, 422)


def test_master_scan_oserror_returns_400_not_500(context, monkeypatch):
    """/api/masters/scan 漏捕 OSError → 裸 500（评审点名的已知 bug 类）→ 400。

    扫描读文件遇权限 / 占用 / 磁盘满时 scan_project 抛 OSError，旧 catch
    元组只捕 MasterError 让它裸传成 500。统一路由包装后任何 OSError 都经
    error_to_http 表转 400 带中文 message。
    """

    def boom(project_dir):
        raise OSError("权限不足")

    monkeypatch.setattr("contest_generator.webapp.scan_project", boom)
    client = TestClient(create_app(context[0]), raise_server_exceptions=False)

    resp = client.post("/api/masters/scan", json={"project_dirs": ["proj-a"]})

    assert resp.status_code == 400
    assert "文件操作失败" in resp.json()["detail"]


class _OSErrorLLM(RaisingLLM):
    """扫描之后 AI 阶段抛 OSError（模拟读素材 / 写临时文件时的系统失败）。"""

    def distill_master(
        self,
        platform,
        project_names,
        judgment_files,
        comparison_summary,
        progress_emitter=None,
    ):
        raise OSError("磁盘已满")


class _BoomLLM(RaisingLLM):
    """抛未登记异常：任何非已知类型 = 真 bug，必须 500 大声失败。"""

    def distill_master(
        self,
        platform,
        project_names,
        judgment_files,
        comparison_summary,
        progress_emitter=None,
    ):
        raise RuntimeError("内部损坏")


def test_master_distill_oserror_ends_stream_with_error(context, tmp_path):
    """/api/masters/distill 的 OSError（旧 catch 元组漏捕的同类漏洞）→ 流内 error 事件。

    提炼端点 SSE 化后错误以流内 error 事件收尾（HTTP 200 起流，工单 02）：
    OSError 经 _error_message 转"文件操作失败"中文 message，不再有裸 500。
    """
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"] = _OSErrorLLM()
    client = TestClient(create_app(context[0]), raise_server_exceptions=False)

    events = _distill_stream(client, [str(proj_a), str(proj_b)])

    # start / batch_start 先由 llm 层发射器产生，异常后以 error 收尾（流终止）
    assert events[-1][0] == EVENT_ERROR
    assert "文件操作失败" in events[-1][1]["message"]


def test_unknown_exception_ends_stream_with_error(context, tmp_path):
    """未登记异常（SSE 端点）→ 流内 error 事件，不吞成假成功。

    同步端点经 error_to_http 表兜底 500 大声失败（见 _error_response）；SSE
    端点无状态码，后台线程异常统一转流内 error 事件，与同步同一张表、同一
    未登记政策——带类型名大声失败（不原样透传裸 str），同样不静默吞掉——
    测试 raise_server_exceptions=False 时若流假成功会露馅。
    """
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"] = _BoomLLM()
    client = TestClient(create_app(context[0]), raise_server_exceptions=False)

    events = _distill_stream(client, [str(proj_a), str(proj_b)])

    # start / batch_start 先由 llm 层发射器产生，异常后以 error 收尾（流终止）
    assert events[-1][0] == EVENT_ERROR
    assert "服务器内部错误（RuntimeError）" in events[-1][1]["message"]
    assert "内部损坏" in events[-1][1]["message"]


# ---------------------------------------------------------------------------
# 设置：保存后即时生效（验收项 6）
# ---------------------------------------------------------------------------


def test_settings_save_takes_effect_immediately(tmp_path):
    seen_configs = []
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")

    def factory(config):
        seen_configs.append(config)
        return FakeLLM(selection=SELECTION)

    ctx = AppContext(config_path=config_path, config=None, llm_factory=factory)
    client = TestClient(create_app(ctx))

    # 未配置时 AI 端点拒绝
    assert client.post("/api/recommend", json={"problem_text": "题"}).status_code == 400

    resp = client.put(
        "/api/settings",
        json={
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-new-key",
            "model": "deepseek-chat",
            "module_library_dir": str(library_dir),
            "masters_dir": str(tmp_path / "masters"),
        },
    )
    assert resp.status_code == 200

    # 配置文件落盘 + 上下文即时更新：下一次 AI 调用就用新配置
    assert ctx.config.api_key == "sk-new-key"
    resp = client.post("/api/recommend", json={"problem_text": "题"})
    assert resp.status_code == 200
    assert seen_configs[-1].api_key == "sk-new-key"


def test_settings_get_masks_api_key_and_put_keeps_masked_value(client, context):
    current = client.get("/api/settings").json()
    assert current["configured"] is True
    assert current["api_key"] == "sk-t••t"  # 前 4 位 + 圆点(长度-5) + 末位
    assert "sk-test" not in current["api_key"]

    # 提交掩码 = 用户没改 key：沿用旧值，只有 base_url 生效
    resp = client.put(
        "/api/settings",
        json={
            "base_url": "https://other.example.com",
            "api_key": current["api_key"],
            "model": current["model"],
            "module_library_dir": current["module_library_dir"],
            "masters_dir": current["masters_dir"],
        },
    )
    assert resp.status_code == 200
    assert context[0].config.base_url == "https://other.example.com"
    assert context[0].config.api_key == "sk-test"  # 掩码未覆盖真实 key


def test_settings_requires_api_key_on_first_configuration(tmp_path):
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))

    resp = client.put(
        "/api/settings",
        json={
            "base_url": "https://api.deepseek.com",
            "api_key": "",
            "model": "deepseek-chat",
            "module_library_dir": str(tmp_path / "lib"),
            "masters_dir": str(tmp_path / "masters"),
        },
    )

    assert resp.status_code == 400
    assert "API key" in resp.json()["detail"]


def test_settings_toolchain_paths_roundtrip(client, context):
    """uv4_path / gmake_path（工单 autocompile-loop/01）读写透传，缺省空串。"""
    current = client.get("/api/settings").json()
    assert current["uv4_path"] == "" and current["gmake_path"] == ""  # 缺省自动探测

    resp = client.put(
        "/api/settings",
        json={
            "base_url": current["base_url"],
            "api_key": current["api_key"],
            "model": current["model"],
            "module_library_dir": current["module_library_dir"],
            "masters_dir": current["masters_dir"],
            "uv4_path": r"C:\Keil5\Core\UV4\UV4.exe",
            "gmake_path": "gmake",
        },
    )
    assert resp.status_code == 200
    assert context[0].config.uv4_path == r"C:\Keil5\Core\UV4\UV4.exe"
    assert context[0].config.gmake_path == "gmake"
    saved = client.get("/api/settings").json()
    assert saved["uv4_path"] == r"C:\Keil5\Core\UV4\UV4.exe"
    assert saved["gmake_path"] == "gmake"


def test_settings_ccs_toolchain_paths_roundtrip(client, context):
    """ccs 三件套（工单 mspm0-build-makefiles/01）读写透传，缺省空串 = 自动探测。"""
    current = client.get("/api/settings").json()
    assert current["ccs_sdk_dir"] == ""
    assert current["ccs_compiler_dir"] == ""
    assert current["ccs_sysconfig_cli"] == ""

    resp = client.put(
        "/api/settings",
        json={
            "base_url": current["base_url"],
            "api_key": current["api_key"],
            "model": current["model"],
            "module_library_dir": current["module_library_dir"],
            "masters_dir": current["masters_dir"],
            "ccs_sdk_dir": "C:/ti/ccs2051/mspm0_sdk_2_10_00_04",
            "ccs_compiler_dir": (
                "C:/ti/ccs2050/ccs/tools/compiler/ti-cgt-armllvm_4.0.4.LTS"
            ),
            "ccs_sysconfig_cli": "C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat",
        },
    )
    assert resp.status_code == 200
    assert context[0].config.ccs_sdk_dir == "C:/ti/ccs2051/mspm0_sdk_2_10_00_04"
    saved = client.get("/api/settings").json()
    assert saved["ccs_sdk_dir"] == "C:/ti/ccs2051/mspm0_sdk_2_10_00_04"
    assert saved["ccs_compiler_dir"] == (
        "C:/ti/ccs2050/ccs/tools/compiler/ti-cgt-armllvm_4.0.4.LTS"
    )
    assert saved["ccs_sysconfig_cli"] == (
        "C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat"
    )


def test_settings_local_llm_fields_roundtrip(client, context):
    """local_llm_base_url / local_llm_model（工单 local-llm-routing/03）读写透传，
    缺省空串 = 本地路由关闭（前端显示为空输入框）。"""
    current = client.get("/api/settings").json()
    assert current["local_llm_base_url"] == ""
    assert current["local_llm_model"] == ""

    resp = client.put(
        "/api/settings",
        json={
            "base_url": current["base_url"],
            "api_key": current["api_key"],
            "model": current["model"],
            "module_library_dir": current["module_library_dir"],
            "masters_dir": current["masters_dir"],
            "local_llm_base_url": "http://localhost:11434/v1",
            "local_llm_model": "qwen2.5-coder:7b-instruct",
        },
    )
    assert resp.status_code == 200
    assert context[0].config.local_llm_base_url == "http://localhost:11434/v1"
    assert context[0].config.local_llm_model == "qwen2.5-coder:7b-instruct"
    saved = client.get("/api/settings").json()
    assert saved["local_llm_base_url"] == "http://localhost:11434/v1"
    assert saved["local_llm_model"] == "qwen2.5-coder:7b-instruct"


def test_settings_local_llm_put_absent_or_blank_closes(client, context):
    """PUT 缺省 / 空串两字段 = 关闭本地路由（等价于从 config.json 移除）。"""
    current = client.get("/api/settings").json()
    base = {
        "base_url": current["base_url"],
        "api_key": current["api_key"],
        "model": current["model"],
        "module_library_dir": current["module_library_dir"],
        "masters_dir": current["masters_dir"],
    }
    set_local = {
        "local_llm_base_url": "http://localhost:11434/v1",
        "local_llm_model": "qwen2.5-coder:7b-instruct",
    }

    # 先填上本地字段
    resp = client.put("/api/settings", json={**base, **set_local})
    assert resp.status_code == 200
    assert context[0].config.local_llm_base_url == "http://localhost:11434/v1"

    # 缺省字段 → 关闭
    resp = client.put("/api/settings", json=base)
    assert resp.status_code == 200
    assert context[0].config.local_llm_base_url == ""
    assert context[0].config.local_llm_model == ""

    # 再填上，然后空串 → 关闭
    resp = client.put("/api/settings", json={**base, **set_local})
    assert resp.status_code == 200
    resp = client.put("/api/settings", json={**base, "local_llm_base_url": "", "local_llm_model": ""})
    assert resp.status_code == 200
    assert context[0].config.local_llm_base_url == ""
    assert context[0].config.local_llm_model == ""
    saved = client.get("/api/settings").json()
    assert saved["local_llm_base_url"] == ""
    assert saved["local_llm_model"] == ""


def test_settings_local_llm_put_rejects_non_string(client, context):
    """PUT 两字段非字符串 → 400 中文报错（与既有字段同严格度）。"""
    current = client.get("/api/settings").json()
    base = {
        "base_url": current["base_url"],
        "api_key": current["api_key"],
        "model": current["model"],
        "module_library_dir": current["module_library_dir"],
        "masters_dir": current["masters_dir"],
    }

    resp = client.put("/api/settings", json={**base, "local_llm_base_url": 123})
    assert resp.status_code == 400
    assert "local_llm_base_url 必须是字符串" in resp.json()["detail"]

    resp = client.put("/api/settings", json={**base, "local_llm_model": 456})
    assert resp.status_code == 400
    assert "local_llm_model 必须是字符串" in resp.json()["detail"]


def test_settings_llm_prices_roundtrip_and_defaults(client, context):
    """llm_prices（工单 llm-cost-control/01）：GET 返回生效表（默认 + 覆盖合并）；
    PUT 覆盖透传；缺省 / 空对象 = 恢复内置默认。"""
    saved = client.get("/api/settings").json()
    # 未配置覆盖 → 返回内置默认表（deepseek 参考价 + local 零成本）
    assert saved["llm_prices"]["deepseek"]["input_per_million"] > 0
    assert saved["llm_prices"]["local"]["input_per_million"] == 0.0

    base = {
        "base_url": saved["base_url"],
        "api_key": saved["api_key"],
        "model": saved["model"],
        "module_library_dir": saved["module_library_dir"],
        "masters_dir": saved["masters_dir"],
    }
    custom = {
        "llm_prices": {
            "deepseek": {"input_per_million": 8.0, "output_per_million": 32.0},
        }
    }
    resp = client.put("/api/settings", json={**base, **custom})
    assert resp.status_code == 200
    assert context[0].config.llm_prices == custom["llm_prices"]
    saved = client.get("/api/settings").json()
    assert saved["llm_prices"]["deepseek"] == {"input_per_million": 8.0, "output_per_million": 32.0}
    # local 未覆盖仍零成本
    assert saved["llm_prices"]["local"]["input_per_million"] == 0.0

    # 空对象 → 恢复默认（config.llm_prices = None）
    resp = client.put("/api/settings", json={**base, "llm_prices": {}})
    assert resp.status_code == 200
    assert context[0].config.llm_prices is None
    saved = client.get("/api/settings").json()
    assert saved["llm_prices"]["deepseek"]["input_per_million"] > 0


def test_settings_llm_prices_put_rejects_non_object(client, context):
    """PUT llm_prices 非 JSON 对象 → 400（外层形状严格，条目级旁路）。"""
    current = client.get("/api/settings").json()
    base = {
        "base_url": current["base_url"],
        "api_key": current["api_key"],
        "model": current["model"],
        "module_library_dir": current["module_library_dir"],
        "masters_dir": current["masters_dir"],
    }
    resp = client.put("/api/settings", json={**base, "llm_prices": "high"})
    assert resp.status_code == 400
    assert "llm_prices 必须是 JSON 对象" in resp.json()["detail"]


def test_state_reports_toolchain_availability(client, context, monkeypatch):
    """/api/state 携带 toolchains（前端置灰依据）：探测命中 → True，未命中 → False。"""
    monkeypatch.setattr(
        "contest_generator.webapp.find_uv4", lambda override: Path("C:/fake/UV4.exe")
    )
    monkeypatch.setattr("contest_generator.webapp.find_make", lambda override: None)
    state = client.get("/api/state").json()
    assert state["toolchains"] == {PLATFORM_STM32: True, PLATFORM_MSPM0: False}


# ---------------------------------------------------------------------------
# 工单 03：生成流程的历史赛题入口（topic_id / 粘贴题面自动识别）+ 两级注入
# ---------------------------------------------------------------------------


class TopicAwareLLM(FakeLLM):
    """历史赛题入口的记录型假 LLM：记录选模块收到的题面 / 参考文件清单 /
    全文，编号提取固定返回（FakeLLM 只读，扩展走子类）。"""

    def __init__(
        self, selection: ModuleSelection = SELECTION, extracted_key: str | None = "2026C"
    ) -> None:
        super().__init__(selection=selection)
        self._extracted_key = extracted_key
        self.extract_calls = 0
        self.problem_texts: list[str] = []
        self.manifest_slugs: list[tuple[str, ...]] = []
        self.reference_ids: list[tuple[str, ...]] = []
        self.fulltexts: list[dict[str, str]] = []
        self.manual_fulltexts: list[dict[str, str]] = []
        self.clarifications: list[tuple[tuple[str, str], ...]] = []

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
    ) -> ModuleSelection:
        self.problem_texts.append(problem_text)
        self.manifest_slugs.append(tuple(s.slug for s in manifest_summaries))
        self.reference_ids.append(tuple(r.id for r in references))
        self.fulltexts.append(dict(reference_fulltexts or {}))
        self.manual_fulltexts.append(dict(manual_fulltexts or {}))
        self.clarifications.append(tuple(clarifications))
        return self._selection

    def topic_extract_number(self, text: str) -> str | None:
        self.extract_calls += 1
        return self._extracted_key


class ClarifyHistoryTopicLLM(TopicAwareLLM):
    """收敛补问闭环的记录型假 LLM（工单 clarify-history-in-convergence）：
    第一次收敛（无历史）返回补问；带历史后收敛成功——模拟"收敛阶段补问 →
    用户回答重推"的完整路径。select_modules 收到的 clarifications 经
    TopicAwareLLM 记录。"""

    def __init__(self) -> None:
        super().__init__(selection=SELECTION, extracted_key=None)
        self._asked = False

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
        clarifications: Sequence[tuple[str, str]] = (),
    ) -> ModuleSelection:
        super().select_modules(
            problem_text,
            manifest_summaries,
            references,
            reference_fulltexts,
            manual_fulltexts,
            clarifications,
        )
        if not self._asked and not clarifications:
            self._asked = True
            return ModuleSelection(
                modules=(),
                reasons={},
                questions=("题面没有说明识别方式，用摄像头还是传感器？",),
            )
        return self._selection


def _wire_material_libraries(context) -> None:
    """在既有假上下文上补齐素材区：赛题库 / 参考文件库 / 该题专用模块与普通
    候选模块。目录推导与生产同源（config.topic_library_dir / reference_library_dir
    ——构造一致性，手抄消失）。"""
    ctx = context[0]
    make_topic_specific_module(ctx.config.module_library_dir)
    make_kit_candidate_module(ctx.config.module_library_dir)
    make_fake_topic_library(topic_library_dir(ctx.config.module_library_dir))
    make_fake_reference_library(reference_library_dir(ctx.config.module_library_dir))


def test_recommend_with_topic_id_uses_full_text_and_carries_materials(client, context):
    """显式 topic_id：长 PDF 题面全文只在选了该赛题时进上下文；候选清单带
    该题 / 套件关联的参考文件（标题 + 简介清单段）；响应带识别结果。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    data = _recommend_done(
        client, {"problem_text": "用户粘贴的片段", "topic_id": "2026C"}
    )
    llm = holder["llm"]
    assert llm.extract_calls == 0  # 显式编号不需要 AI 提取
    # 收敛循环第 1 轮：题面全文逐句编号后进上下文（"1. " 前缀，编号跨轮稳定）；
    # 第 2 轮收敛确认带上一轮功能需求层（自检修订指令）
    assert llm.problem_texts[0] == "1. " + TOPIC_PROBLEM_TEXT
    assert "上一轮功能需求层" in llm.problem_texts[1]
    assert llm.reference_ids == [
        (TOPIC_REFERENCE_ID, KIT_REFERENCE_ID, UWB_REFERENCE_ID),
        (TOPIC_REFERENCE_ID, KIT_REFERENCE_ID, UWB_REFERENCE_ID),
    ]
    assert data["topic_id"] == "2026C"
    assert data["modules"] == [
        {"slug": "dht11", "reason": "赛题要求采集温湿度"},
        {"slug": "oled", "reason": "需要显示测量结果"},
    ]


def test_recommend_auto_recognizes_number_in_pasted_text(client, context):
    """粘贴题面中出现编号同样可认：AI 提取编号 → 查库得题面全文 + 素材。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION)  # 默认提取到 2026C

    data = _recommend_done(client, {"problem_text": "……2026C 数字钥匙……"})

    llm = holder["llm"]
    assert llm.extract_calls == 1
    assert llm.problem_texts[0] == "1. " + TOPIC_PROBLEM_TEXT
    assert data["topic_id"] == "2026C"


def test_recommend_auto_recognition_falls_back_when_topic_missing(client, context):
    """自动识别查无此条：尽力而为静默降级——按纯粘贴题面流程走，不报错。"""
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION)  # 提取到 2026C 但库里没有

    data = _recommend_done(client, {"problem_text": "粘贴片段"})

    llm = holder["llm"]
    assert llm.problem_texts[0] == "1. 粘贴片段"
    assert "topic_id" not in data


def test_recommend_two_level_injection_reads_fulltexts_when_requested(
    client, context
):
    """两级注入协议端到端（收敛循环第 1 轮内）：模型第一级点名的参考文件取
    全文进第二级上下文；第 2 轮收敛确认同样带已读全文（全文上下文不丢）。"""
    _wire_material_libraries(context)
    holder = context[1]
    selection = ModuleSelection(
        modules=("dht11",),
        reasons={"dht11": "赛题要求采集温湿度"},
        reference_ids=(TOPIC_REFERENCE_ID,),
    )
    holder["llm"] = TopicAwareLLM(selection=selection, extracted_key=None)

    _recommend_done(client, {"problem_text": "粘贴", "topic_id": "2026C"})

    llm = holder["llm"]
    assert llm.fulltexts[0] == {}  # 第一级：只有清单
    assert "/* 数字钥匙例程 */" in llm.fulltexts[1][TOPIC_REFERENCE_ID]  # 第二级：全文
    assert llm.fulltexts[2] == llm.fulltexts[1]  # 第 2 轮收敛确认带已读全文
    assert len(llm.problem_texts) == 3  # 两级 × 第 1 轮 + 第 2 轮确认


def test_recommend_streams_rounds_and_converged_events(client):
    """SSE 契约：round（轮次 / 上限）→ … → converged（收敛轮）→ done（推荐结果）。"""
    events = _recommend_stream(client, {"problem_text": "温湿度采集并显示"})

    assert [kind for kind, _ in events] == ["round", "round", "converged", "done"]
    assert events[0][1]["round"] == 1 and events[0][1]["round_total"] == 4
    assert events[1][1]["round"] == 2
    assert events[2][1]["round"] == 2  # converged 事件携带收敛轮次
    assert "modules" in events[3][1]


def test_recommend_question_ends_stream_with_question_event(client, context):
    """模型拿不准（题面证据不足以判定）→ question 事件收尾（questions 数组），
    流不以 done 结束——前端据此向用户补问。"""
    holder = context[1]
    holder["llm"] = FakeLLM(
        selection=ModuleSelection(
            modules=(),
            reasons={},
            questions=("题面没有说明识别方式，用摄像头还是传感器？",),
        )
    )

    events = _recommend_stream(client, {"problem_text": "识别数字的送药小车"})

    assert [kind for kind, _ in events] == ["round", EVENT_QUESTION]
    assert events[-1][1]["questions"] == [
        "题面没有说明识别方式，用摄像头还是传感器？"
    ]


def test_recommend_clarify_questions_end_stream_with_question_event(client, context):
    """首跑（无澄清历史）澄清阶段先行：clarify 仍有疑问 → question 事件收尾
    （不发 round——澄清阶段不属于收敛轮次，补问不再作废已跑轮次）。"""
    holder = context[1]
    llm = FakeLLM(clarify_questions=("具体要识别什么数字？",))
    holder["llm"] = llm

    events = _recommend_stream(
        client, {"problem_text": "识别数字的送药小车"}
    )

    assert [kind for kind, _ in events] == [EVENT_QUESTION]
    assert events[-1][1]["questions"] == ["具体要识别什么数字？"]
    assert llm.clarify_calls == [("识别数字的送药小车", ())]


def test_recommend_clarify_empty_with_history_goes_straight_to_convergence(
    client, context
):
    """带 clarifications 重发 → 跳过澄清门直进收敛（工单 recommend-speedup/01：
    零 clarify 调用——历史段 + 已答不重问已由 select_modules 承载，补问功能被
    收敛循环覆盖，每轮补问省一次串行调用）；收敛收到的题面保持原文（逐句
    编号），回答不进题面。"""
    holder = context[1]
    llm = TopicAwareLLM(selection=SELECTION, extracted_key=None)
    holder["llm"] = llm

    events = _recommend_stream(
        client,
        {
            "problem_text": "温湿度采集并显示",
            "clarifications": [{"question": "识别方式？", "answer": "摄像头"}],
        },
    )

    assert [kind for kind, _ in events] == [
        "round",
        "round",
        "converged",
        "done",
    ]
    assert llm.clarify_calls == []  # 有历史：clarify 门被跳过
    # 题面保持原文：收敛循环收到的是逐句编号的原始题面，回答不拼进题面
    assert llm.problem_texts[0] == "1. 温湿度采集并显示"
    assert "摄像头" not in llm.problem_texts[0]


def test_recommend_convergence_ask_answers_carried_into_retry(client, context):
    """闭环断言（工单 clarify-history-in-convergence）：收敛阶段补问 → 用户回答
    重推 → 第二次收敛的 select_modules 每轮都收到首次答案——收敛 prompt 不再
    对同一证据不足点换措辞反复问（问答历史贯穿收敛循环，修复闭环断裂）。"""
    holder = context[1]
    llm = ClarifyHistoryTopicLLM()
    holder["llm"] = llm

    first = _recommend_stream(client, {"problem_text": "温湿度采集并显示"})
    assert [kind for kind, _ in first] == ["round", EVENT_QUESTION]
    question = first[-1][1]["questions"][0]

    second = _recommend_stream(
        client,
        {
            "problem_text": "温湿度采集并显示",
            "clarifications": [{"question": question, "answer": "用摄像头"}],
        },
    )
    assert [kind for kind, _ in second] == [
        "round",
        "round",
        "converged",
        "done",
    ]
    # 第二次收敛：每轮 select_modules 都带首次答案（历史保序、贯穿到收敛）
    history = ((question, "用摄像头"),)
    assert llm.clarifications[-2:] == [history, history]
    # 首跑才走澄清门；第二次带历史重推 → 跳过 clarify（工单 recommend-speedup/01，
    # 补问功能由收敛循环覆盖，不会漏问）
    assert llm.clarify_calls == [("温湿度采集并显示", ())]


@pytest.mark.parametrize(
    "bad",
    [
        "字符串",
        [{"question": "q"}],  # 缺 answer
        [{"question": "", "answer": "a"}],  # question 为空
        [{"question": "q", "answer": 123}],  # answer 非字符串
        [{"question": "q", "answer": "a"}, "不是对象"],  # 条目非对象
    ],
)
def test_recommend_clarifications_malformed_rejected(client, bad):
    """clarifications 校验：非数组 / 缺 question / 空 question / 非字符串
    answer / 条目非对象 → 400（字符串对契约，缺省空 = 向后兼容）。"""
    resp = client.post(
        "/api/recommend", json={"problem_text": "题目", "clarifications": bad}
    )

    assert resp.status_code == 400
    assert "clarifications" in resp.json()["detail"]


def test_recommend_carries_requirements_and_isolates_suggestions(client, context):
    """done 载荷：功能需求层（需求 / 对照句 / 库内命中 / 库外建议）随流返回；
    库外建议只展示——不进 modules[]（隔离不变量），当 slug 传给 expand 报错。"""
    holder = context[1]
    holder["llm"] = FakeLLM(
        selection=ModuleSelection(
            modules=("dht11",),
            reasons={"dht11": "测温湿度"},
            requirements=(
                FunctionRequirement(
                    requirement="识别数字",
                    sentence_index=2,
                    modules=("dht11",),
                    suggestions=(
                        OutOfLibrarySuggestion(
                            name="视觉模块", examples=("K230", "OpenMV")
                        ),
                    ),
                ),
            ),
        )
    )

    data = _recommend_done(client, {"problem_text": "送药小车"})

    assert data["modules"] == [{"slug": "dht11", "reason": "测温湿度"}]
    assert data["requirements"] == [
        {
            "requirement": "识别数字",
            "sentence": 2,
            "modules": ["dht11"],
            "suggestions": [
                {"name": "视觉模块", "examples": ["K230", "OpenMV"], "degraded": False}
            ],
        }
    ]
    # 库外建议名绝不出现在 modules[]（只展示、不进 selectedSlugs / expand / generate）
    assert "视觉模块" not in [m["slug"] for m in data["modules"]]
    # 现有严格校验保留：把建议名当 slug 传给 expand → 库中不存在 → 400
    resp = client.post(
        "/api/selection/expand",
        json={"slugs": ["视觉模块"], "platform": PLATFORM_STM32},
    )
    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


def test_skeleton_smoke_mode_generates_smoke_main(client, context):
    """main_mode="smoke"：走 generate_smoke_main（假 LLM 冒烟出稿 + 同款占位兜底）。"""
    context[1]["llm"]._smoke_skeleton = (
        "int main(void) { oled_init(); float t = dht11_read(); dht11_init(); while (1); }\n"
    )

    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "温湿度采集",
            "slugs": ["dht11", "oled"],
            "platform": PLATFORM_STM32,
            "main_mode": "smoke",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "int main(void)" in data["main_c"]
    assert "oled_init();" in data["main_c"]
    assert "dht11_read();" in data["main_c"]
    assert data["intercepted"] == ["dht11_init"]
    assert context[1]["llm"].smoke_calls
    assert not context[1]["llm"].skeleton_calls


def test_skeleton_smoke_requires_oled_or_debug_uart(client, context):
    """自检冒烟必须选 OLED 或 debug_uart 作为输出通道，否则 400 中文。"""
    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "温湿度采集",
            "slugs": ["dht11"],
            "platform": PLATFORM_STM32,
            "main_mode": "smoke",
        },
    )

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "OLED" in detail and "debug_uart" in detail


def test_skeleton_rejects_invalid_main_mode(client, context):
    """main_mode 非法值 400（含空串），不落到生成分支。"""
    for bad in ("banana", ""):
        resp = client.post(
            "/api/skeleton",
            json={
                "problem_text": "温湿度采集",
                "slugs": ["dht11", "oled"],
                "platform": PLATFORM_STM32,
                "main_mode": bad,
            },
        )

        assert resp.status_code == 400
        assert "main_mode" in resp.json()["detail"]


def test_skeleton_with_reference_ids_injects_fulltexts(client, context):
    """骨架阶段 reference_ids：锚定 ∪ 手动全文进骨架 prompt（FakeLLM 记录）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(extracted_key=None)

    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "用户粘贴的片段",
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "topic_id": "2026C",
            "reference_ids": [TOPIC_REFERENCE_ID],
        },
    )

    assert resp.status_code == 200
    refs = holder["llm"].skeleton_ref_calls[0]
    assert TOPIC_REFERENCE_ID in refs
    assert "数字钥匙例程" in refs[TOPIC_REFERENCE_ID]


def test_skeleton_rejects_duplicate_reference_ids(client, context):
    """骨架阶段重复 reference_id：manual_reference_admission → 400 中文。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(extracted_key=None)

    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "用户粘贴的片段",
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "topic_id": "2026C",
            "reference_ids": [TOPIC_REFERENCE_ID, TOPIC_REFERENCE_ID],
        },
    )

    assert resp.status_code == 400
    assert "重复" in resp.json()["detail"]


def test_skeleton_without_reference_ids_records_empty(client, context):
    """缺省零参考回归：不传 reference_ids → generate_skeleton 收到 None（FakeLLM 记 {}）。"""
    holder = context[1]
    holder["llm"] = TopicAwareLLM(extracted_key=None)

    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "温湿度采集",
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
        },
    )

    assert resp.status_code == 200
    assert holder["llm"].skeleton_ref_calls == [{}]


def test_skeleton_with_manual_only_reference_injects_fulltext(client, context):
    """手动选一个非锚定参考（no-topic 唯一准入）：全文直读进骨架 prompt。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(extracted_key=None)

    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "用户粘贴的片段",
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "reference_ids": [OTHER_REFERENCE_ID],
        },
    )

    assert resp.status_code == 200
    refs = holder["llm"].skeleton_ref_calls[0]
    assert refs == {OTHER_REFERENCE_ID: refs[OTHER_REFERENCE_ID]}
    assert "别的套件" in refs[OTHER_REFERENCE_ID]


def test_skeleton_rejects_unknown_reference_id(client, context):
    """骨架阶段幻觉 reference_id：走 manual_reference_admission → 400 中文。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(extracted_key=None)

    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "用户粘贴的片段",
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "topic_id": "2026C",
            "reference_ids": ["nope"],
        },
    )

    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


def test_skeleton_with_topic_id_uses_full_text(client, context):
    """骨架阶段：题面全文进上下文（长 PDF 题面全文只在选了该赛题时进上下文）；
    模块集 = 用户选择原样（工单 module-universalization/07 起不自动并入）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(extracted_key=None)

    resp = client.post(
        "/api/skeleton",
        json={
            "problem_text": "用户粘贴的片段",
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "topic_id": "2026C",
        },
    )

    assert resp.status_code == 200
    llm = holder["llm"]
    assert llm.skeleton_calls[0][0] == TOPIC_PROBLEM_TEXT
    assert not any("lock_control.h" in text for text in llm.skeleton_calls[0][1])


def test_generate_with_topic_id_keeps_selected_modules_only(client, context, tmp_path):
    """生成请求带 topic_id：编号经装配点校验（查无此条 400）；模块集 = 用户
    选择原样展开，不再自动并入"题专用模块"（生成物与手选等价）。"""
    _wire_material_libraries(context)
    _import_stm32_master(context[0].config.masters_dir, tmp_path)
    output_dir = tmp_path / "out" / "demo"

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(output_dir),
            "topic_id": "2026C",
        },
    )

    assert resp.status_code == 200
    assert (output_dir / "modules" / "dht11" / "stm32" / "src" / "dht11.c").is_file()
    assert not (output_dir / "modules" / "lock_control" / "lock_control.c").is_file()


def test_generate_with_unknown_topic_id_returns_400(client, context, tmp_path):
    """生成请求带库中不存在的编号：明确报错（不猜测编造），不产出残缺工程。"""
    _import_stm32_master(context[0].config.masters_dir, tmp_path)

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(tmp_path / "out"),
            "topic_id": "2021F",
        },
    )

    assert resp.status_code == 400
    assert "2021F" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 结构测试（防回退，先例 errors.py 防漏登 / test_categories）：装配不在路由、
# 布局推导唯一出处 = config.py
# ---------------------------------------------------------------------------


def test_webapp_consumes_topic_context_without_reassembling():
    """路由不再自持装配：webapp 模块无 build_manifest_summaries 属性（装配
    函数一个不剩）——候选清单 / 摘要行 / 两级注入只由 generator.resolve_topic_context
    产出，路由只消费（工单 02：赛题入口单一接缝）。list_modules 是 /api/modules
    浏览的唯一合法消费（浏览非装配，工单 Comments 留痕）。"""
    import contest_generator.webapp as webapp

    assert not hasattr(webapp, "build_manifest_summaries")
    assert hasattr(webapp, "list_modules")


def test_layout_dir_derivation_lives_in_config():
    """布局推导唯一出处 = config.py：webapp 不再自持 topics/ / references/
    路径推导私有委托（工单 02 收进 config.topic_library_dir / reference_library_dir），
    测试与生产消费同源。"""
    import contest_generator.config as config
    import contest_generator.webapp as webapp

    assert not hasattr(webapp, "_topic_library_dir")
    assert not hasattr(webapp, "_reference_dir")
    library_dir = Path("work/module_library")
    assert config.topic_library_dir(library_dir) == library_dir.parent / "topics"
    assert (
        config.reference_library_dir(library_dir) == library_dir.parent / "references"
    )


# ---------------------------------------------------------------------------
# 标签会话（启动器模式：关浏览器 = 停服务）
# ---------------------------------------------------------------------------


def test_tabs_register_and_bye_manage_sessions(client, context):
    """登记 / 注销标签会话：注册表增减正确，空 = 没有打开的前端页面。"""
    ctx, _ = context
    assert client.post("/api/tabs/register", json={"tab_id": "t1"}).status_code == 200
    assert len(ctx.tab_registry) == 1
    assert client.post("/api/tabs/bye", json={"tab_id": "t1"}).status_code == 200
    assert len(ctx.tab_registry) == 0


def test_tabs_require_tab_id(client):
    """tab_id 必填非空（与其余端点同款 400 契约）。"""
    assert client.post("/api/tabs/register", json={}).status_code == 400
    assert client.post("/api/tabs/bye", json={}).status_code == 400


def test_tabs_bye_schedules_exit_only_when_last_tab_and_launcher_managed(
    client, context, monkeypatch
):
    """最后一个标签离开 + 启动器模式 → 宽限后退出；还有标签在开 → 不退出。"""
    import contest_generator.webapp as webapp

    ctx, _ = context
    exits = []
    monkeypatch.setattr(webapp, "_EXIT", lambda code: exits.append(code))
    monkeypatch.setattr(webapp, "_launcher_managed", lambda: True)
    monkeypatch.setattr(webapp, "_EXIT_GRACE", 0.01)
    client.post("/api/tabs/register", json={"tab_id": "t1"})
    client.post("/api/tabs/register", json={"tab_id": "t2"})
    client.post("/api/tabs/bye", json={"tab_id": "t1"})
    time.sleep(0.05)
    assert exits == []  # 还有 t2 在开，不退出
    client.post("/api/tabs/bye", json={"tab_id": "t2"})
    time.sleep(0.05)
    assert exits == [0]  # 最后一个离开 → 宽限后退出


def test_tabs_bye_never_exits_outside_launcher_mode(client, context, monkeypatch):
    """非启动器模式（测试 / 手动运行默认）：永不自杀。"""
    import contest_generator.webapp as webapp

    ctx, _ = context
    exits = []
    monkeypatch.setattr(webapp, "_EXIT", lambda code: exits.append(code))
    monkeypatch.setattr(webapp, "_EXIT_GRACE", 0.01)
    client.post("/api/tabs/register", json={"tab_id": "t1"})
    client.post("/api/tabs/bye", json={"tab_id": "t1"})
    time.sleep(0.05)
    assert exits == []


# ---------------------------------------------------------------------------
# 工单 01：手动选参考资料（reference_ids 契约 / 追加准入 / 全文直读 / 幻觉 400 /
# 缺省兼容 / 最终参考清单透明闭环）
# ---------------------------------------------------------------------------


def test_recommend_manual_reference_ids_fulltext_into_first_round(client, context):
    """手动选参考资料：reference_ids 随请求 → 手动全文直读进第一轮（第一级就带，
    无需模型点名）；done 带最终参考清单（锚定 auto + 手动 manual）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    data = _recommend_done(
        client,
        {
            "problem_text": "粘贴",
            "topic_id": "2026C",
            "reference_ids": [OTHER_REFERENCE_ID],
        },
    )

    llm = holder["llm"]
    # 手动全文第一级就带（全文直读强制）
    assert OTHER_REFERENCE_ID in llm.manual_fulltexts[0]
    assert "别的套件" in llm.manual_fulltexts[0][OTHER_REFERENCE_ID]
    assert llm.manual_fulltexts[1] == llm.manual_fulltexts[0]  # 收敛确认轮照旧带上
    # 最终参考清单：锚定 auto + 手动 manual（并集）
    sources = {ref["id"]: ref["source"] for ref in data["references"]}
    assert sources[TOPIC_REFERENCE_ID] == "auto"
    assert sources[OTHER_REFERENCE_ID] == "manual"


def test_recommend_manual_reference_unknown_id_fails_loudly(client, context):
    """手动幻觉 id：400 大声失败（装配点同步校验在起流前——错误映射表已登记
    ManualReferenceError → HTTP 400 中文，前端走非 200 分支提示）。"""
    _wire_material_libraries(context)

    resp = client.post(
        "/api/recommend", json={"problem_text": "粘贴", "reference_ids": ["幻觉 id"]}
    )

    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


def test_recommend_no_topic_manual_reference_is_only_admission(client, context):
    """no-topic + 手动勾选（锚定 none 批次的唯一可用场景）：清单非空、全文直读；
    done 最终清单只含 manual 条目。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    data = _recommend_done(
        client,
        {
            "problem_text": "粘贴题面",  # 无 topic_id、提取失败 → no-topic 形
            "reference_ids": [OTHER_REFERENCE_ID],
        },
    )

    llm = holder["llm"]
    assert llm.reference_ids[0] == (OTHER_REFERENCE_ID,)  # 清单 = 手动条目
    assert OTHER_REFERENCE_ID in llm.manual_fulltexts[0]  # 全文直读
    assert "topic_id" not in data
    assert [ref["id"] for ref in data["references"]] == [OTHER_REFERENCE_ID]
    assert data["references"][0]["source"] == "manual"


def test_recommend_without_reference_ids_keeps_old_behavior(client, context):
    """缺省兼容（回归）：不传 reference_ids → 链路与现状一致（无手动全文、最终
    清单只含锚定 auto）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    data = _recommend_done(client, {"problem_text": "粘贴", "topic_id": "2026C"})

    llm = holder["llm"]
    assert all(not fulltexts for fulltexts in llm.manual_fulltexts)  # 无手动全文
    assert {ref["id"] for ref in data["references"]} == {
        TOPIC_REFERENCE_ID,
        KIT_REFERENCE_ID,
        UWB_REFERENCE_ID,
    }
    assert {ref["source"] for ref in data["references"]} == {"auto"}


def test_recommend_platform_filters_anchored_references(client, context):
    """platform 透传（工单 01）：请求体 platform 随装配点过滤锚定命中——2024H
    巡线模板（platform=mspm0）在 stm32 工程不进清单、mspm0 工程进。"""
    _wire_material_libraries(context)
    add_reference(
        reference_library_dir(context[0].config.module_library_dir),
        title="巡线模板（mspm0）",
        type="参考例程",
        description="mspm0 平台巡线配套例程",
        anchor_kind="topic",
        anchor_value="2026C",
        platform="mspm0",
        files={"xunji.c": "/* 巡线 */\n"},
        kit_vocabulary=(),
    )
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    stm32_data = _recommend_done(
        client, {"problem_text": "粘贴", "topic_id": "2026C", "platform": "stm32"}
    )
    # 清单 = 旧条目（缺省 any）+ 其它锚定；mspm0 条目被过滤
    assert "巡线模板-mspm0" not in [
        ref["id"] for ref in stm32_data["references"]
    ]
    assert TOPIC_REFERENCE_ID in [ref["id"] for ref in stm32_data["references"]]
    # 喂给选模块 LLM 的清单段同样不含 mspm0 条目（透传到装配点）
    assert holder["llm"].reference_ids[0] == (
        TOPIC_REFERENCE_ID,
        KIT_REFERENCE_ID,
        UWB_REFERENCE_ID,
    )

    mspm0_data = _recommend_done(
        client, {"problem_text": "粘贴", "topic_id": "2026C", "platform": "mspm0"}
    )
    assert "巡线模板-mspm0" in [ref["id"] for ref in mspm0_data["references"]]
    assert set(holder["llm"].reference_ids[2]) == {
        TOPIC_REFERENCE_ID,
        KIT_REFERENCE_ID,
        UWB_REFERENCE_ID,
        "巡线模板-mspm0",
    }


def test_recommend_platform_filters_module_candidates(client, context):
    """platform 透传（工单 ref-platform-filter 模块侧对偶）：mspm0 请求的
    模块候选只含本平台有实现的条目——喂给选模块 LLM 的摘要行（可勾选面）
    同源同滤（stm32-only 的 lock_control / oled 不再出现）；stm32 全量库
    不受影响。"""
    _wire_material_libraries(context)
    holder = context[1]
    mspm0_selection = ModuleSelection(
        modules=("dht11",),
        reasons={"dht11": "赛题要求采集温湿度"},
    )
    holder["llm"] = TopicAwareLLM(selection=mspm0_selection, extracted_key=None)

    mspm0_data = _recommend_done(
        client, {"problem_text": "粘贴", "topic_id": "2026C", "platform": "mspm0"}
    )
    llm = holder["llm"]
    # 收敛两轮喂的是同一份过滤后候选（stm32-only 模块模型不可见）
    assert all(set(slugs) == {"dht11", "delay"} for slugs in llm.manifest_slugs)
    assert mspm0_data["modules"] == [
        {"slug": "dht11", "reason": "赛题要求采集温湿度"}
    ]

    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)
    stm32_data = _recommend_done(
        client, {"problem_text": "粘贴", "topic_id": "2026C", "platform": "stm32"}
    )
    llm = holder["llm"]
    assert set(llm.manifest_slugs[0]) == {
        "dht11",
        "delay",
        "oled",
        "broken",
        "lock_control",
        "uwb",
    }


def test_recommend_platform_absent_keeps_old_behavior(client, context):
    """缺省 platform（不传 / 空）：不过滤（向后兼容），与现状逐字节等价。"""
    _wire_material_libraries(context)
    add_reference(
        reference_library_dir(context[0].config.module_library_dir),
        title="巡线模板（mspm0）",
        type="参考例程",
        description="mspm0 平台巡线配套例程",
        anchor_kind="topic",
        anchor_value="2026C",
        platform="mspm0",
        files={"xunji.c": "/* 巡线 */\n"},
        kit_vocabulary=(),
    )
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    data = _recommend_done(client, {"problem_text": "粘贴", "topic_id": "2026C"})

    assert "巡线模板-mspm0" in [ref["id"] for ref in data["references"]]


def test_recommend_manual_reference_bypasses_platform_filter(client, context):
    """手动选不过平台过滤（工单 01）：stm32 工程手动勾选 mspm0 条目仍注入
    （用户显式意图），done 参考清单带 platform 标注供 UI 展示。"""
    _wire_material_libraries(context)
    mspm0_id = "巡线模板-mspm0"
    add_reference(
        reference_library_dir(context[0].config.module_library_dir),
        title="巡线模板（mspm0）",
        type="参考例程",
        description="mspm0 平台巡线配套例程",
        anchor_kind="topic",
        anchor_value="2026C",
        platform="mspm0",
        files={"xunji.c": "/* 巡线 */\n"},
        kit_vocabulary=(),
    )
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    data = _recommend_done(
        client,
        {
            "problem_text": "粘贴",
            "topic_id": "2026C",
            "platform": "stm32",
            "reference_ids": [mspm0_id],
        },
    )

    llm = holder["llm"]
    assert mspm0_id in llm.manual_fulltexts[0]  # 手动全文直读照旧
    refs = {ref["id"]: ref for ref in data["references"]}
    assert refs[mspm0_id]["source"] == "manual"
    assert refs[mspm0_id]["platform"] == "mspm0"  # done 带平台标注


def test_recommend_manual_overlapping_anchor_deduped(client, context):
    """并集去重：同一条目既锚定命中又被手动选 → 最终清单只出现一次（手动标注）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    data = _recommend_done(
        client,
        {
            "problem_text": "粘贴",
            "topic_id": "2026C",
            "reference_ids": [TOPIC_REFERENCE_ID],
        },
    )

    ids = [ref["id"] for ref in data["references"]]
    assert ids.count(TOPIC_REFERENCE_ID) == 1
    topic = next(ref for ref in data["references"] if ref["id"] == TOPIC_REFERENCE_ID)
    assert topic["source"] == "manual"


# ---------------------------------------------------------------------------
# 推荐缓存（工单 llm-cost-control/02）：同题重跑命中直出 done，指纹失效走真实
# ---------------------------------------------------------------------------


def _recommend_payload(topic_id="2026C", **overrides):
    payload = {
        "problem_text": "赛题：做个智能小车，能巡线、能避障。",
        "topic_id": topic_id,
        "platform": "stm32",
    }
    payload.update(overrides)
    return payload


def test_recommend_cache_hit_reuses_done_without_llm(client, context):
    """同题同平台第二次推荐：cache_hit 事件 + done 载荷与首次逐字一致，不调 LLM。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    first = _recommend_done(client, _recommend_payload())
    assert first["modules"]

    # 第二次：把 LLM 换成必抛的——命中缓存则不触达 LLM
    class _BoomLLM:
        def __getattr__(self, name):
            raise AssertionError(f"缓存命中不应调用 LLM：{name}")

    holder["llm"] = _BoomLLM()
    events = _recommend_stream(client, _recommend_payload())
    cache_hits = [data for kind, data in events if kind == "cache_hit"]
    assert cache_hits, f"应发射 cache_hit 事件：{events}"
    assert cache_hits[0]["warns"] == []
    done = [data for kind, data in events if kind == EVENT_DONE]
    assert done and done[0] == first


def test_recommend_cache_invalidated_when_problem_text_changes(client, context):
    """题面变化 → 指纹失效 → 走真实推荐（不命中）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    _recommend_done(client, _recommend_payload())
    events = _recommend_stream(client, _recommend_payload(problem_text="赛题变了：做个小车。"))
    assert not [k for k, _ in events if k == "cache_hit"]
    done = [data for kind, data in events if kind == EVENT_DONE]
    assert done, "题面变应走真实推荐并以 done 收尾"


def test_recommend_cache_skipped_when_disabled_in_settings(client, context):
    """设置页关闭缓存开关后：同题重跑走真实推荐（不 cache_hit）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    _recommend_done(client, _recommend_payload())

    current = client.get("/api/settings").json()
    resp = client.put(
        "/api/settings",
        json={
            "base_url": current["base_url"],
            "api_key": current["api_key"],
            "model": current["model"],
            "module_library_dir": current["module_library_dir"],
            "masters_dir": current["masters_dir"],
            "recommend_cache_enabled": False,
        },
    )
    assert resp.status_code == 200
    assert context[0].config.recommend_cache_enabled is False

    events = _recommend_stream(client, _recommend_payload())
    assert not [k for k, _ in events if k == "cache_hit"]
    done = [data for kind, data in events if kind == EVENT_DONE]
    assert done, "开关关闭应走真实推荐"


def test_recommend_corrupt_cache_falls_back_to_real(client, context, tmp_path):
    """损坏缓存文件 → 静默旁路走真实推荐（Web 交互语义，不报错退出）。"""
    _wire_material_libraries(context)
    holder = context[1]
    holder["llm"] = TopicAwareLLM(selection=SELECTION, extracted_key=None)

    # 预置一个损坏缓存（键 = topic_id）
    cache_dir = context[0].config_path.parent / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "recommend_2026C.json").write_text("{broken", encoding="utf-8")

    events = _recommend_stream(client, _recommend_payload())
    assert not [k for k, _ in events if k == "cache_hit"]
    done = [data for kind, data in events if kind == EVENT_DONE]
    assert done, "坏缓存应静默走真实推荐"


# ---------------------------------------------------------------------------
# 参考文件库：文件名搜索 + 文件清单 + 文件服务（文件名搜索 / 文件打开工单）
# ---------------------------------------------------------------------------


def _add_reference_entry(client, title, files, type_="说明书", anchor="2026C"):
    """经 API 录入参考条目（赛题锚定，无需 kit 词表），返回条目 dict。"""
    resp = client.post(
        "/api/references",
        json={
            "title": title,
            "type": type_,
            "description": "x",
            "anchor_kind": "topic",
            "anchor_value": anchor,
            "files": files,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_references_filename_search_query_param(client, context, tmp_path):
    _add_reference_entry(
        client,
        "塔克小车底盘资料",
        {
            "素材清单.txt": (
                "素材目录（Desktop/塔克）文件清单：\n"
                "\n"
                "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf  632107 bytes\n"
            )
        },
    )
    _add_reference_entry(client, "无线串口模块资料", {"readme.md": "# 无线串口\n"})

    assert [e["title"] for e in client.get("/api/references?filename=TB6612").json()] == [
        "塔克小车底盘资料"
    ]
    assert [e["title"] for e in client.get("/api/references?filename=readme").json()] == [
        "无线串口模块资料"
    ]
    assert client.get("/api/references?filename=不存在").json() == []
    # 与其他过滤可组合；空串 = 不过滤（向后兼容）
    assert client.get("/api/references?filename=TB6612&title=塔克").json() != []
    assert len(client.get("/api/references").json()) == len(
        client.get("/api/references?filename=").json()
    ) == 2
    # 命中文件直出：filename 过滤时带 matched_files，不过滤时无该字段
    hits = client.get("/api/references?filename=TB6612").json()
    assert hits[0]["matched_files"] == [
        "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf"
    ]
    assert "matched_files" not in client.get("/api/references").json()[0]
    assert "matched_files" not in client.get("/api/references?filename=").json()[0]
    # 命中文件可直接经服务端点打开（行内直开路径）
    resp = client.get(
        "/api/references/塔克小车底盘资料/files/"
        + "6 TB6612电机驱动资料/3.芯片手册/TB6612FNG%20Datasheet.pdf"
    )
    assert resp.status_code == 400  # 条目目录无此文件、无 materials 镜像 → 缺失通道 400（错误映射统一）


def test_reference_files_lists_manifest_and_disk(client, context, tmp_path):
    entry = _add_reference_entry(
        client,
        "塔克小车底盘资料",
        {
            "main.c": "/* 例程 */\n",
            "素材清单.txt": (
                "素材目录（Desktop/塔克）文件清单：\n"
                "\n"
                "7 AT8236电机驱动资料/AT8236.pdf  100 bytes\n"
            ),
        },
    )
    entry_id = entry["id"]
    # 条目目录补一个实际文件（含子目录）
    disk = tmp_path / "references" / entry_id / "extra"
    disk.mkdir()
    (disk / "notes.c").write_text("/* 备注 */\n", encoding="utf-8")

    files = client.get(f"/api/references/{entry_id}/files").json()
    by_path = {f["path"]: f["size_bytes"] for f in files}
    assert "7 AT8236电机驱动资料/AT8236.pdf" in by_path
    assert by_path["7 AT8236电机驱动资料/AT8236.pdf"] == 100
    # size = 真实 stat（Windows 文本模式写盘 \n → \r\n，不能按原串 len 算）
    assert by_path["main.c"] == (tmp_path / "references" / entry_id / "main.c").stat().st_size
    assert by_path["extra/notes.c"] == (tmp_path / "references" / entry_id / "extra" / "notes.c").stat().st_size
    assert "reference.json" not in by_path


def test_reference_file_serves_entry_text(client, context, tmp_path):
    entry = _add_reference_entry(client, "塔克小车底盘资料", {"main.c": "/* 例程 */\n"})
    resp = client.get(f"/api/references/{entry['id']}/files/main.c")
    assert resp.status_code == 200
    # 服务的是磁盘字节（Windows 文本模式写盘是 \r\n），按内容断言
    assert resp.text.replace("\r\n", "\n") == "/* 例程 */\n"


def test_reference_file_serves_materials_pdf(client, context, tmp_path):
    entry = _add_reference_entry(client, "塔克小车底盘资料", {"main.c": "/* 例程 */\n"})
    pdf = (
        tmp_path
        / "sources"
        / "materials"
        / entry["title"]
        / "6 TB6612电机驱动资料"
        / "3.芯片手册"
        / "TB6612FNG Datasheet.pdf"
    )
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4\nfake pdf")

    url = (
        f"/api/references/{entry['id']}/files/"
        + quote("6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf", safe="/")
    )
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4\nfake pdf"
    assert resp.headers["content-type"] == "application/pdf"


def test_reference_file_serves_materials_in_repo_layout(client, context, tmp_path):
    """仓库布局兜底：模块库在 library/ 子目录下时，materials 镜像在仓库根。

    素材工具脚本以工作区根为根写备份（firstep/library/modules →
    firstep/sources/materials），config.materials_dir 同级没有时上两级兜底取实况。
    """
    repo = tmp_path / "repo"
    library_dir = make_fake_module_library(repo / "library" / "modules")
    ctx = AppContext(
        config_path=tmp_path / "cfg2" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=repo / "library" / "masters",
        ),
        llm_factory=lambda config: FakeLLM(selection=SELECTION),
    )
    app = TestClient(create_app(ctx))
    added = _add_reference_entry(app, "塔克小车底盘资料", {"main.c": "/* 例程 */\n"})
    pdf = (
        repo
        / "sources"
        / "materials"
        / added["title"]
        / "6 TB6612电机驱动资料"
        / "TB6612FNG Datasheet.pdf"
    )
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4 fake")

    url = (
        f"/api/references/{added['id']}/files/"
        + quote("6 TB6612电机驱动资料/TB6612FNG Datasheet.pdf", safe="/")
    )
    resp = app.get(url)
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 fake"
    assert resp.headers["content-type"] == "application/pdf"


def test_reference_file_missing_400(client, context, tmp_path):
    entry = _add_reference_entry(client, "塔克小车底盘资料", {"main.c": "/* 例程 */\n"})
    # 条目存在但文件两处都没有（materials 根也不存在）= 缺失通道统一 400
    # （错误映射 ReferenceError → 400，与条目不存在同通道，不再有内联 404）
    assert client.get(f"/api/references/{entry['id']}/files/nope.pdf").status_code == 400
    # 条目不存在 → 既有 ReferenceError 映射（400）
    assert client.get("/api/references/missing/files/nope.pdf").status_code == 400


@pytest.mark.parametrize("bad", ["../secret", "..\\secret", "/etc/passwd", "a//b", "c:/win"])
def test_reference_file_rejects_unsafe_paths(client, context, tmp_path, bad):
    entry = _add_reference_entry(client, "塔克小车底盘资料", {"main.c": "/* 例程 */\n"})
    # 按段编码保证到达 handler（\ 在 URL 中字面传，handler 内校验兜底）
    url = f"/api/references/{entry['id']}/files/{quote(bad, safe='')}"
    assert client.get(url).status_code == 400


# ---------------------------------------------------------------------------
# 结构防回退（工单 recommend-orchestration-homing/01）：/api/recommend 路由只
# 取参 + 转调 + sse 包装，两阶段编排整体归 selection.run_recommendation——
# 编排回路由即红（AST 断言，参照 test_autocommit.py 的源码切片断言风格）。
# ---------------------------------------------------------------------------


def _recommend_route_node() -> ast.FunctionDef:
    """webapp.py 源码中的 recommend 路由函数节点（AST，嵌套在 create_app 内）。"""
    module_path = (
        Path(__file__).resolve().parent.parent
        / "src" / "contest_generator" / "webapp.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    routes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "recommend"
    ]
    assert len(routes) == 1, "webapp.py 应恰好一个 recommend 路由函数"
    return routes[0]


# ---------------------------------------------------------------------------
# 本地路由（工单 local-llm-routing/02）：AppContext.llm_factory 默认值 + webapp
# 级派发两路断言（本地组端点走 local、远程组端点走 remote）
# ---------------------------------------------------------------------------


def test_app_context_llm_factory_default_is_build_llm():
    """llm_factory 默认值指向 build_llm：不注入 fake 时路由按配置自动生效。"""
    assert AppContext().llm_factory is build_llm


def test_local_routing_webapp_routes_method_groups(tmp_path):
    """注入 RoutingLLM（remote/local 两个记录型 fake）+ 本地配置：本地组端点
    （赛题简介）走 local、远程组端点（编号提取）走 remote——路由全链路生效。"""
    library_dir = make_fake_module_library(tmp_path / "module_library")
    remote = RecordingLLM("remote")
    local = RecordingLLM("local")
    router = RoutingLLM(remote=remote, local=local)
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=tmp_path / "masters",
            local_llm_base_url="http://localhost:11434/v1",
            local_llm_model="qwen2.5-coder:7b-instruct",
        ),
        llm_factory=lambda config: router,
    )
    client = TestClient(create_app(ctx))

    # 本地组端点：/api/topic/summarize → summarize_topic → local
    resp = client.post("/api/topic/summarize", json={"problem_text": "题面"})
    assert resp.status_code == 200
    assert local.calls == ["summarize_topic"]
    assert remote.calls == []

    # 远程组端点：/api/topics/extract-number → topic_extract_number → remote
    resp = client.post("/api/topics/extract-number", json={"text": "2026C"})
    assert resp.status_code == 200
    assert remote.calls == ["topic_extract_number"]
    assert local.calls == ["summarize_topic"]  # 本地集不被远程调用触碰


def test_local_routing_webapp_local_failure_is_loud(tmp_path):
    """本地失联在 webapp 层大声失败：502 + 可操作提示（错误映射表出口）。"""
    class _FailingLocal(RecordingLLM):
        def summarize_topic(self, problem_text: str) -> str:
            raise LLMError("连接被拒绝", kind="network")

    library_dir = make_fake_module_library(tmp_path / "module_library")
    router = RoutingLLM(remote=RecordingLLM("remote"), local=_FailingLocal("local"))
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=tmp_path / "masters",
            local_llm_base_url="http://localhost:11434/v1",
            local_llm_model="qwen2.5-coder:7b-instruct",
        ),
        llm_factory=lambda config: router,
    )
    client = TestClient(create_app(ctx))

    resp = client.post("/api/topic/summarize", json={"problem_text": "题面"})
    assert resp.status_code == 502
    assert LOCAL_LLM_UNAVAILABLE_MESSAGE in resp.json()["detail"]


def _is_orchestration_call(node: ast.Call) -> bool:
    """编排回路由即红的判据：路由函数体内的编排调用（llm.clarify /
    select_modules_convergent / emit.done / emit.question——全部应只出现在
    selection.run_recommendation 里）。"""
    func = node.func
    if isinstance(func, ast.Name) and func.id == "select_modules_convergent":
        return True
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "llm" and func.attr == "clarify":
            return True
        if func.value.id == "emit" and func.attr in ("done", "question"):
            return True
    return False


def test_recommend_route_body_free_of_orchestration_calls():
    """结构防回退：/api/recommend 路由函数体不含两阶段编排调用——编排归位
    selection.run_recommendation，路由只剩取参 + 转调 + sse 包装。"""
    route = _recommend_route_node()
    forbidden = [
        node
        for node in ast.walk(route)
        if isinstance(node, ast.Call) and _is_orchestration_call(node)
    ]
    assert not forbidden, (
        "/api/recommend 路由含编排调用，编排必须归 selection.run_recommendation："
        + "；".join(ast.unparse(node) for node in forbidden)
    )


# ---------------------------------------------------------------------------
# PDF 资料库（给人看的资料库）：素材库 PDF 浏览 / 搜索 / 直开预览
# ---------------------------------------------------------------------------

def _make_materials_pdfs(tmp_path) -> None:
    """素材镜像（sources/materials，与模块库同级推导）搭两批次 PDF + 干扰文件。"""
    a = tmp_path / "sources" / "materials" / "2026_04_地猛星配套资料" / "6 TB6612电机驱动资料" / "3.芯片手册"
    a.mkdir(parents=True)
    (a / "TB6612FNG Datasheet.pdf").write_bytes(b"%PDF-1.4\nfake a")
    (tmp_path / "sources" / "materials" / "2026_04_地猛星配套资料" / "readme.txt").write_text(
        "not a pdf", encoding="utf-8"
    )
    b = tmp_path / "sources" / "materials" / "2026_06_电赛视觉资料"
    b.mkdir(parents=True)
    (b / "09_泰山派原理图.PDF").write_bytes(b"%PDF-1.4\nfake b")


def test_pdfs_lists_all_sorted_with_batch_and_size(client, context, tmp_path):
    _make_materials_pdfs(tmp_path)
    pdfs = client.get("/api/pdfs").json()
    assert [p["name"] for p in pdfs] == ["TB6612FNG Datasheet.pdf", "09_泰山派原理图.PDF"]
    assert [p["batch"] for p in pdfs] == ["2026_04_地猛星配套资料", "2026_06_电赛视觉资料"]
    assert pdfs[0]["size_bytes"] == len(b"%PDF-1.4\nfake a")
    assert pdfs[0]["rel_path"].endswith("3.芯片手册/TB6612FNG Datasheet.pdf")


def test_pdfs_filters_by_name(client, context, tmp_path):
    _make_materials_pdfs(tmp_path)
    hit = client.get("/api/pdfs", params={"name": "tb6612"}).json()
    assert [p["name"] for p in hit] == ["TB6612FNG Datasheet.pdf"]
    by_batch = client.get("/api/pdfs", params={"name": "视觉资料"}).json()
    assert [p["name"] for p in by_batch] == ["09_泰山派原理图.PDF"]
    assert client.get("/api/pdfs", params={"name": "不存在"}).json() == []


def test_pdf_file_serves_application_pdf(client, context, tmp_path):
    _make_materials_pdfs(tmp_path)
    url = "/api/pdfs/" + quote(
        "2026_04_地猛星配套资料/6 TB6612电机驱动资料/3.芯片手册/TB6612FNG Datasheet.pdf",
        safe="/",
    )
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4\nfake a"
    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.parametrize("bad", ["../secret.pdf", "..\\secret.pdf", "/etc/passwd.pdf", "a//b.pdf", "c:/win.pdf"])
def test_pdf_file_rejects_unsafe_paths(client, context, tmp_path, bad):
    _make_materials_pdfs(tmp_path)
    resp = client.get("/api/pdfs/" + quote(bad, safe=""))
    assert resp.status_code == 400
    assert "非法文件路径" in resp.json()["detail"]


def test_pdf_file_missing_returns_400(client, context, tmp_path):
    _make_materials_pdfs(tmp_path)
    resp = client.get("/api/pdfs/" + quote("不存在/资料.pdf", safe="/"))
    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 更新记录（工单 changelog-tab/01）：GET /api/changelog 按天分组时间轴
# ---------------------------------------------------------------------------


def test_changelog_route_lists_daily_groups(client):
    """更新记录：200 + [{date, items: [{time, text}]}]——repo 根 CHANGELOG.md 实况。"""
    resp = client.get("/api/changelog")
    assert resp.status_code == 200
    data = resp.json()
    assert data, "repo 根 CHANGELOG.md 应有初始内容"
    assert all(
        isinstance(group["date"], str)
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", group["date"])
        and isinstance(group["items"], list)
        and all(
            isinstance(item["time"], str) and isinstance(item["text"], str)
            for item in group["items"]
        )
        for group in data
    )
    # 08-12 条目应带 HH:MM 时间前缀（工单实施当日真实 commit 时间）
    assert re.fullmatch(r"\d{1,2}:\d{2}", data[0]["items"][0]["time"])
