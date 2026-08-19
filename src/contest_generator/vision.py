"""视觉通道：GLM-4V-Flash 免费云端识图（工单 vision-eyes/01）。

DeepSeek 纯文本看不见图；本模块给题面示意图 / 上传图片提供「图 → 中文
描述」通道：OpenAI 兼容 chat/completions（content = text + image_url
base64 data URL），默认模型 glm-4v-flash（智谱官方免费多模态 API）。

网络层照 llm.py 先例：标准库 urllib（零第三方依赖）+ 可注入传输接缝
（测试假件）；网络类错误指数退避重试（3 次 1/2/4s，429 限速不重试——
免费层限速重试只会继续 429，直接失败由调用方降级）；describe_image_cached
进程内 sha256 缓存（同图重跑不重复调用/花钱）。

纯函数层：不 import 生成流程、不碰盘；配置（base_url / api_key / model）
与传输由调用方注入（webapp 装配层照 _llm 先例）。
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Protocol

# 智谱开放平台 OpenAI 兼容端点（缺省值；设置页可覆盖）
DEFAULT_VISION_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
# 官方免费多模态模型（无 API 费用；免费层有限速，日常 2-10 张/题够用）
DEFAULT_VISION_MODEL = "glm-4v-flash"

# 网络重试参数（照 llm.py 网络退避先例的简化版）
VISION_NETWORK_RETRIES = 3
VISION_BACKOFF_SECONDS = (1, 2, 4)

# 描述提示词（引导提取对解题有用的要素；调用方可按场景覆写）
DEFAULT_DESCRIBE_PROMPT = (
    "这是电子设计竞赛题面中的示意图，请提取对解题有用的信息："
    "尺寸、标注文字、电路连接、布局结构、机械关系等，用中文简洁描述。"
    "如果图中没有实质内容，只回复「无实质内容」。"
)

# 图片内容哈希缓存（进程内；键 = 图片字节 sha256 → 描述）
# v1 不落盘（重启即清，够用；落盘缓存留后续工单）
_IMAGE_DESCRIBE_CACHE: dict[str, str] = {}


class VisionError(ValueError):
    """视觉通道失败（未配置 / 网络 / 上游返回非法）。

    业务失败 → 400 中文（登记 errors.py）；调用方按「静默降级」政策决定
    是否阻断（抽取链路 = 降级不阻断；图片上传 = 提示配置入口）。
    """


class VisionNotConfiguredError(VisionError):
    """视觉通道未启用（未配 api_key）——调用方据此走降级 / 可操作提示。"""


class Transport(Protocol):
    """HTTP 传输接缝（照 llm.Transport 先例）：生产 urllib，测试注入假件。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str, Mapping[str, str]]:
        """POST JSON，返回（HTTP 状态码, 响应体文本, 响应头）。"""


class ObservationCollector(Protocol):
    """视觉调用观测接缝（避免 vision.py 运行时 import llm.py 造成环）。"""

    def collect(self, **kwargs: Any) -> dict[str, Any]:
        """记录 content-safe 调用事实，形状与 LLMObservationCollector.collect 对齐。"""


class UrllibTransport:
    """基于标准库 urllib 的传输实现（项目零第三方依赖）。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str, Mapping[str, str]]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return (
                    response.status,
                    response.read().decode("utf-8"),
                    dict(response.headers.items()),
                )
        except urllib.error.HTTPError as exc:
            return (
                exc.code,
                exc.read().decode("utf-8", errors="replace"),
                dict(exc.headers.items()) if exc.headers else {},
            )
        except (urllib.error.URLError, OSError) as exc:
            raise VisionError(f"无法连接视觉服务 {url}: {exc}") from exc


def vision_configured(api_key: str) -> bool:
    """视觉通道是否启用（api_key 非空）。"""
    return bool(api_key and api_key.strip())


def _image_data_url(image_bytes: bytes, mime: str) -> str:
    """图片字节 → data URL（视觉请求的 image_url 形态）。"""
    return "data:{mime};base64,{b64}".format(
        mime=mime or "image/png", b64=base64.b64encode(image_bytes).decode("ascii")
    )


def describe_image(
    image_bytes: bytes,
    mime: str,
    prompt: str = DEFAULT_DESCRIBE_PROMPT,
    *,
    base_url: str = DEFAULT_VISION_BASE_URL,
    api_key: str = "",
    model: str = DEFAULT_VISION_MODEL,
    transport: Transport | None = None,
    observation_collector: ObservationCollector | None = None,
    timeout: float = 60.0,
) -> str:
    """图片 → 中文描述（OpenAI 兼容 chat/completions + base64 image_url）。

    未配 api_key → VisionNotConfiguredError（调用方降级/提示）；网络类错误
    指数退避重试 VISION_NETWORK_RETRIES 次；429（免费限速）不重试直接抛；
    上游返回非法（非 JSON / 无 choices / content 非文本）→ VisionError。
    传输可注入（测试假件，照 llm.Transport 先例）。
    """
    if not vision_configured(api_key):
        raise VisionNotConfiguredError(
            "视觉通道未配置：请到设置页填写视觉 API key（免费 GLM-4V-Flash）"
        )
    base_url = base_url.strip() or DEFAULT_VISION_BASE_URL
    model = model.strip() or DEFAULT_VISION_MODEL
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(image_bytes, mime)},
                    },
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = base_url.rstrip("/") + "/chat/completions"
    http = transport or UrllibTransport()

    last_error: VisionError | None = None
    started_at = time.monotonic()
    request_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    last_http_status: int | None = None
    attempts = 0

    def record(status_text: str, parse_status: str, error_kind: str | None) -> None:
        if observation_collector is None:
            return
        try:
            observation_collector.collect(
                operation="vision_describe",
                provider="zhipu",
                route="vision",
                model=model,
                duration_ms=round((time.monotonic() - started_at) * 1000),
                attempts=attempts,
                status=status_text,
                final=True,
                call_id=None,
                budget_attempt=None,
                http_status=last_http_status,
                error_kind=error_kind,
                parse_status=parse_status,
                request_bytes=request_bytes,
                usage=None,
            )
        except Exception:
            pass

    try:
        for attempt in range(VISION_NETWORK_RETRIES):
            attempts = attempt + 1
            try:
                status, body, _headers = http.post(url, headers, payload, timeout)
            except VisionError as exc:
                if attempt + 1 < VISION_NETWORK_RETRIES:
                    _backoff_sleep(VISION_BACKOFF_SECONDS[attempt])
                last_error = exc
                continue
            last_http_status = status
            if status == 429:
                raise VisionError(
                    f"视觉服务限流（HTTP 429，免费层有限速）：{body[:200]}"
                )
            if status >= 500:
                if attempt + 1 < VISION_NETWORK_RETRIES:
                    _backoff_sleep(VISION_BACKOFF_SECONDS[attempt])
                last_error = VisionError(f"视觉服务返回 HTTP {status}：{body[:200]}")
                continue
            if status != 200:
                raise VisionError(f"视觉服务返回 HTTP {status}：{body[:200]}")
            description = _parse_description(body)
            record("success", "success", None)
            return description
        assert last_error is not None  # 循环必赋值（重试次数 ≥ 1）
        raise last_error
    except VisionError as exc:
        if last_http_status == 429:
            error_kind = "rate_limit"
        elif last_http_status is not None and last_http_status >= 500:
            error_kind = "network"
        elif last_http_status is not None:
            error_kind = "client"
        else:
            error_kind = "network"
        record("error", "parse_error", error_kind)
        raise exc


def _parse_description(body: str) -> str:
    """响应体 → 描述文本（choices[0].message.content；兼容字符串与内容数组）。"""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise VisionError(f"视觉服务返回的不是 JSON：{body[:200]}") from exc
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionError(f"视觉服务响应缺少 choices/message/content：{body[:200]}") from exc
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        text = "".join(parts)
    else:
        raise VisionError(f"视觉服务响应 content 形态非法：{content!r}")
    text = text.strip()
    if not text:
        raise VisionError("视觉服务返回空描述")
    return text


def describe_image_cached(
    image_bytes: bytes,
    mime: str,
    prompt: str = DEFAULT_DESCRIBE_PROMPT,
    **kwargs: Any,
) -> str:
    """带进程内缓存（键 = 图片内容 sha256）：同图重复调用不重发请求/花钱。

    缓存键只吃图片字节（prompt 变体由调用方保证同图同 prompt——描述提示词
    是模块内常量，实际不会变）。失败不缓存（下次重试）。"""
    digest = hashlib.sha256(image_bytes).hexdigest()
    cached = _IMAGE_DESCRIBE_CACHE.get(digest)
    if cached is not None:
        return cached
    description = describe_image(image_bytes, mime, prompt, **kwargs)
    _IMAGE_DESCRIBE_CACHE[digest] = description
    return description


def clear_describe_cache() -> None:
    """清空进程内缓存（测试用 / 设置变更后调用）。"""
    _IMAGE_DESCRIBE_CACHE.clear()


def _backoff_sleep(seconds: float) -> None:
    """退避等待（独立函数 = 测试 monkeypatch 接缝，照 llm._backoff_sleep）。"""
    time.sleep(seconds)
