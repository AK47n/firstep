"""FastAPI 薄壳：装配全部后端能力，形成可用产品（spec 工单 09）。

路由层只做三件事：收 HTTP 请求 → 调核心函数 → 转 JSON 响应；LLM / 文件
抽取是薄壳的一部分，工程生成 / 模块库 / 母版提炼等全部走纯逻辑核心。
用户级设置（AI API / 工作目录）存本机配置文件，写入后即时生效——每次
请求按上下文里的当前配置构造 LLM，不重启服务。

依赖注入：AppContext 持有配置路径 / LLM 工厂，测试注入 tmp 目录与假 LLM，
网络调用不进测试。
"""

from __future__ import annotations

import functools
import inspect
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from .config import (
    DEFAULT_CONFIG_PATH,
    AppConfig,
    ConfigError,
    load_config,
    materials_dir,
    reference_library_dir,
    save_config,
    topic_library_dir,
)
from .errors import error_entry
from .extraction import extract_file
from .generator import (
    GenerationSummary,
    TopicContext,
    generate_project,
    resolve_topic_context,
)
from .library import (
    add_module,
    add_platform_files,
    delete_module,
    draft_description,
    list_modules,
    remove_platform_files,
    update_module_description,
    update_platform_identity,
)
from .llm import (
    LLM,
    DeepSeekLLM,
    TOPIC_SPLIT_LLM_CHAR_CAP,
)
from .master import (
    confirm_distillation,
    distill_master,
    scan_project,
)
from .master_store import (
    delete_master,
    import_master,
    list_masters,
    master_project_dir,
)
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32
from .reference_library import (
    PLATFORM_ANY,
    add_reference,
    delete_reference,
    draft_description as reference_draft_description,
    list_entry_files,
    match_entry_files,
    module_kit_vocabulary,
    resolve_entry_file,
    search_references,
)
from .selection import resolve_selection, run_recommendation
from .skeleton import generate_skeleton
from .sse import SseEmitter, run_sse
from .stage import stage_project_files
from .topic_library import (
    confirm_topics,
    delete_topic,
    list_topics,
    parse_confirm_entries,
    resolve_number,
    split_topics_document,
)

STATIC_DIR = Path(__file__).parent / "static"

# 平台展示名（仅界面用；平台词表本体在 platforms.py）
PLATFORM_DISPLAY_NAMES = {
    PLATFORM_STM32: "STM32F103C8T6 最小系统板 · Keil5",
    PLATFORM_MSPM0: "地猛星 MSPM0G3507 · CCS",
}

# API key 掩码特征：GET 只回掩码，PUT 收到掩码说明用户没改 key
_API_KEY_MASK_MARKER = "…"


# ---------------------------------------------------------------------------
# 浏览器标签会话（firstep 启动器）：最后一个标签页关闭 → 服务自动停止
# ---------------------------------------------------------------------------

_LAUNCHER_ENV = "FIRSTEP_LAUNCHER"  # 启动器置 1：启用"关浏览器 = 停服务"
_EXIT_GRACE = 1.5  # 秒：注销后宽限窗口，覆盖 F5 重载的 unload→reload 竞态
_EXIT: Callable[[int], Any] = os._exit  # 可注入（测试断言调度，不真自杀）


class TabRegistry:
    """标签会话注册表：register / unregister，空 = 没有打开的前端页面。

    只记 tab_id 集合、不持业务形状；线程安全（多标签并发注册）。unregister
    返回是否变空，路由据此调度延迟退出（空 → 关浏览器 = 停服务）。
    """

    def __init__(self) -> None:
        self._tabs: set[str] = set()
        self._lock = threading.Lock()

    def register(self, tab_id: str) -> None:
        with self._lock:
            self._tabs.add(tab_id)

    def unregister(self, tab_id: str) -> bool:
        """注销一个标签；返回注销后注册表是否为空（空 = 可退出）。"""
        with self._lock:
            self._tabs.discard(tab_id)
            return not self._tabs

    def __len__(self) -> int:
        with self._lock:
            return len(self._tabs)


def _launcher_managed() -> bool:
    """仅启动器模式启用自动退出（FIRSTEP_LAUNCHER=1）；测试 / 手动运行永不自杀。"""
    return os.environ.get(_LAUNCHER_ENV) == "1"


def _schedule_exit_if_idle(registry: TabRegistry) -> None:
    """最后一个标签关闭后：宽限窗口内无新标签注册 → 退出进程。

    非启动器模式直接返回（正常开发 / 测试运行不受影响）；daemon 线程不
    阻塞请求。本地无状态工具，退出即 os._exit（端口随之释放，双击重启）。
    """
    if not _launcher_managed():
        return

    def delayed() -> None:
        time.sleep(_EXIT_GRACE)
        if len(registry) == 0:
            _EXIT(0)

    threading.Thread(target=delayed, daemon=True).start()


def _tkinter_pick_directory() -> str | None:
    """弹原生文件夹选择对话框，返回绝对路径；取消返回 None。

    浏览器出于安全不暴露用户所选文件夹的绝对路径（webkitdirectory 只能
    整夹上传，见 /api/masters/stage），输出目录必须知道落盘位置——由本地
    服务端弹系统对话框（tkinter 随 Python 自带，无网络依赖），选中路径回填
    前端输入框。tkinter 在无桌面会话的环境（CI / 服务化部署）会抛异常，
    调用方按未登记异常走 500 大声失败；测试注入 fake 不真弹窗。
    """
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口，只留对话框
    # 对话框置顶：本地工具场景下浏览器窗口通常在前台，askdirectory 默认可能
    # 沉到后面（用户曾反馈找不到窗口）；topmost 由父窗口继承，必须传 parent
    root.attributes("-topmost", True)
    try:
        return filedialog.askdirectory(parent=root, title="选择输出目录") or None
    finally:
        root.destroy()


@dataclass
class AppContext:
    """服务上下文：配置路径 + 当前配置（写入后即时生效）+ LLM 工厂（测试注入）。"""

    config_path: Path = DEFAULT_CONFIG_PATH
    config: AppConfig | None = None  # None → 按需从配置文件加载
    llm_factory: Callable[[AppConfig], LLM] = DeepSeekLLM
    tab_registry: TabRegistry = field(default_factory=TabRegistry)
    pick_directory: Callable[[], str | None] = _tkinter_pick_directory


# ---------------------------------------------------------------------------
# 上下文：配置 / LLM
# ---------------------------------------------------------------------------


def _current_config(ctx: AppContext) -> AppConfig | None:
    """返回当前配置；未配置（文件缺失 / 损坏 / 缺 key）返回 None。"""
    if ctx.config is None:
        try:
            ctx.config = load_config(ctx.config_path)
        except ConfigError:
            ctx.config = None  # 未配置：各端点给出"请先到设置页配置"提示
    return ctx.config


def _require_config(ctx: AppContext) -> AppConfig:
    config = _current_config(ctx)
    if config is None:
        raise HTTPException(
            400, "未配置 AI API：请先到设置页填写 API 后再使用 AI 功能"
        )
    return config


def _llm(ctx: AppContext) -> LLM:
    return ctx.llm_factory(_require_config(ctx))


def _library_dir(ctx: AppContext) -> Path:
    return _require_config(ctx).module_library_dir


def _masters_dir(ctx: AppContext) -> Path:
    return _require_config(ctx).masters_dir


def _assemble_topic_context(
    context: AppContext,
    topic_id: str,
    problem_text: str,
    llm: LLM | None,
    reference_ids: Sequence[str] = (),
    platform: str = "",
) -> TopicContext:
    """生成流程的历史赛题入口素材装配（单一 helper，三路由共用）。

    显式 topic_id 或粘贴题面自动识别 → 完整 TopicContext（永远非 None；
    key 为空串 = 未识别到历史赛题，按纯粘贴题面流程走；识别到时题面用库内
    全文——长 PDF 题面全文只在选了该赛题时进上下文）。装配唯一出处 =
    generator.resolve_topic_context，这里只取配置、推导目录、传参；显式编号
    查无此条大声报错；自动识别尽力而为（提取失败 / 查无此条静默降级）。
    推荐 / 骨架传 _llm(context)（自动识别），生成传 None（显式编号路径）。
    reference_ids = 手动选参考资料（工单 01，仅推荐路由传——骨架 / 生成不
    注入参考文件是既有定案）。platform（工单 01 平台属性）= 锚定命中过滤
    依据：仅推荐路由传请求体 platform（骨架 / 生成不注入参考文件，传缺省）。
    """
    config = _require_config(context)
    return resolve_topic_context(
        llm=llm,
        topic_key=topic_id,
        problem_text=problem_text,
        module_library_dir=config.module_library_dir,
        topic_library_dir=topic_library_dir(config.module_library_dir),
        reference_library_dir=reference_library_dir(config.module_library_dir),
        reference_ids=reference_ids,
        platform=platform,
    )




# ---------------------------------------------------------------------------
# 错误映射：取值与包装（error_to_http 表唯一出处 = errors.py，全路由出口）
# ---------------------------------------------------------------------------


def _error_message(exc: Exception) -> str:
    """异常 → 中文 message（error_to_http 表的 SSE 侧取值，与同步同一张表）。

    提炼的 SSE 流内 error 事件用它（HTTP 保持 200 起流）；普通端点仍走
    _error_response 转状态码。未登记异常与同步同政策：带类型名大声失败，
    不原样透传裸 str。表与唯一实现在 errors.py。
    """
    return error_entry(exc)[1]


def _error_response(exc: Exception) -> HTTPException:
    """异常 → HTTPException（error_to_http 表的同步侧取值，与 SSE 同一张表）。

    已知异常：业务失败 → 400（message 原样带出）、LLM 服务失败 → 502、
    文件系统失败 → 400；**未登记的异常 = 真 bug，兜底转 500**——旧实现
    兜底 400 会把真 bug 吞成业务失败（测试 raise_server_exceptions=False
    时静默通过）。新异常类型必须登记，否则按真 bug 大声 500。
    表与唯一实现在 errors.py。
    """
    status, message = error_entry(exc)
    return HTTPException(status, message)


def _map_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """路由包装兜底：路由内任何异常统一经 error_to_http 表映射。

    路由只写业务逻辑、不写 catch 元组——catch 元组漏类型（如漏 OSError）
    是裸 500 的 bug 根源（568cf51 修过 confirm 端点，scan/distill 同款漏洞）。
    HTTPException（参数校验等直接抛出的 400）原样穿透；其余异常由
    _error_response 兜底映射，未登记异常转 500 大声失败。
    """

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as exc:
                raise _error_response(exc) from exc

        return async_wrapper

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as exc:
            raise _error_response(exc) from exc

    return wrapper


# ---------------------------------------------------------------------------
# SSE 线格式与流化运行器：唯一实现在 sse.py（工单 C2 深模块）——线格式
# 契约、事件队列 + 旁路闭包、daemon 线程、stream 生成器；端点只保留入参
# 校验与核心调用，SSE 机制一律经 run_sse。
# ---------------------------------------------------------------------------


def _require_str(payload: dict, key: str) -> str:
    """必填非空字符串；缺失 / 空白抛 400。"""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(400, f"缺少必填字段：{key}")
    return value.strip()


def _require_str_list(
    payload: dict, key: str, *, default: Sequence[str] | None = None
) -> list[str]:
    """非空字符串列表（缺省 None / 空元组 / 空列表视为缺省）。"""
    value = payload.get(key, default)
    if value in (None, (), []):
        return []
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise HTTPException(400, f"{key} 必须是非空字符串列表")
    return [item.strip() for item in value]


def _require_flag(payload: dict, key: str, *, default: bool = False) -> bool:
    """严格布尔校验——宽松强转会静默翻转硬件绑定 / 验证标记。"""
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise HTTPException(400, f"{key} 必须是布尔值")
    return value


def _require_clarifications(
    payload: dict, key: str = "clarifications"
) -> list[tuple[str, str]]:
    """可选问答历史：[{question, answer}] 字符串对（缺省空 = 向后兼容）。

    question 必填非空；answer 可为空串（回答输入框允许留空——空回答 = 用户
    明确不给补充，同样进历史，防止澄清无限循环）。
    """
    value = payload.get(key)
    if value in (None, (), []):
        return []
    if not isinstance(value, list):
        raise HTTPException(400, f"{key} 必须是 [question, answer] 数组")
    result: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise HTTPException(400, f"{key}[{index}] 必须是对象")
        question = item.get("question")
        if not isinstance(question, str) or not question.strip():
            raise HTTPException(400, f"{key}[{index}] 缺 question")
        answer = item.get("answer")
        if not isinstance(answer, str):
            raise HTTPException(400, f"{key}[{index}] 的 answer 必须是字符串")
        result.append((question.strip(), answer))
    return result


def _optional_str(payload: dict, key: str) -> str:
    """可选字符串：缺省 / null → 空串；类型非法抛 400（勿让 null 变成 'None'）。"""
    value = payload.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise HTTPException(400, f"{key} 必须是字符串")
    return value.strip()


def _mask_api_key(api_key: str) -> str:
    """API key 掩码（判定用）：只露前 4 位 + 省略号（PUT 收到掩码形态视为用户没改 key）。"""
    if not api_key:
        return ""
    return api_key[:4] + _API_KEY_MASK_MARKER


def _mask_api_key_display(api_key: str) -> str:
    """API key 掩码（显示用）：前 4 位 + 圆点 + 末位，圆点个数 = 真实长度 - 5。

    前端填入普通文本框：前缀 + 末位可见以确认 key 无误，圆点数能看出真实长度。
    长度 ≤5 时只露前缀（短 key 再露末位等于全泄露）。
    """
    if not api_key:
        return ""
    if len(api_key) <= 5:
        return api_key[:4] + "•" * (len(api_key) - 4)
    return api_key[:4] + "•" * (len(api_key) - 5) + api_key[-1]


async def _save_upload(upload: UploadFile) -> Path:
    """上传文件 → 临时文件（保留原后缀，抽取 / 录入按后缀选解析器）。

    返回临时文件路径，调用方负责 finally unlink（与 /api/extract 同款
    临时文件生命周期；本助手供新增上传路由复用）。
    """
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(upload.filename or "").suffix
    ) as tmp:
        tmp.write(await upload.read())
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# 应用工厂（测试注入上下文用）
# ---------------------------------------------------------------------------


def create_app(ctx: AppContext | None = None) -> FastAPI:
    context = ctx or AppContext()
    app = FastAPI(title="电赛工程生成器")

    # 生成流程页（单页应用）
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    # 全局状态：平台可用性 / 配置状态 / 工作目录
    @app.get("/api/state")
    @_map_errors
    def state() -> dict:
        """首页状态：配置状态 + 平台可用性（母版缺失的平台标记暂不可用）。"""
        config = _current_config(context)
        dirs = config or AppConfig()  # 未配置时展示默认工作目录
        masters = (
            list_masters(dirs.masters_dir) if dirs.masters_dir.is_dir() else []
        )
        master_platforms = {meta.platform for meta in masters}
        return {
            "api_configured": config is not None,
            "llm": (
                {"base_url": config.base_url, "model": config.model}
                if config is not None
                else None
            ),
            "module_library_dir": str(dirs.module_library_dir),
            "masters_dir": str(dirs.masters_dir),
            "platforms": [
                {
                    "id": platform,
                    "name": PLATFORM_DISPLAY_NAMES[platform],
                    "status": (
                        "ready" if platform in master_platforms else "no-master"
                    ),
                }
                for platform in KNOWN_PLATFORMS
            ],
        }

    # 标签会话（启动器模式）：前端打开登记、关闭注销；最后一个离开 →
    # 宽限后自动停服务（"关浏览器 = 停止"）。非启动器模式零影响。
    @app.post("/api/tabs/register")
    @_map_errors
    def tabs_register(payload: dict) -> dict:
        """标签页打开时登记（tab_id 由前端 sessionStorage 生成，跨刷新稳定）。"""
        tab_id = _require_str(payload, "tab_id")
        context.tab_registry.register(tab_id)
        return {"ok": True}

    @app.post("/api/tabs/bye")
    @_map_errors
    def tabs_bye(payload: dict) -> dict:
        """标签页关闭时注销（pagehide + sendBeacon）；最后一个离开 → 停服务。"""
        tab_id = _require_str(payload, "tab_id")
        if context.tab_registry.unregister(tab_id):
            _schedule_exit_if_idle(context.tab_registry)
        return {"ok": True}

    # ------------------------------------------------------------------
    # 生成流程：贴题或传文件 → 选平台 → AI 推荐可增删 → 骨架 → 生成
    # ------------------------------------------------------------------

    @app.post("/api/extract")
    @_map_errors
    async def extract(upload: UploadFile = File(...)) -> dict:
        """上传赛题文件（PDF / .docx / .txt / .md）→ 抽取纯文本。"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(upload.filename or "").suffix
        ) as tmp:
            tmp.write(await upload.read())
            tmp_path = Path(tmp.name)
        try:
            return {"text": extract_file(tmp_path)}
        finally:
            tmp_path.unlink(missing_ok=True)

    @app.post("/api/recommend")
    @_map_errors
    def recommend(payload: dict) -> StreamingResponse:
        """AI 按赛题推荐模块（SSE 流，工单 10）：round → … → converged →
        done（推荐结果）或 question（向用户补问）或 error（中文信息）→ 流结束。

        请求体契约：problem_text（必填）；topic_id（可选，历史赛题显式入口）；
        reference_ids（可选 list[str]，手动选参考资料——幻觉 / 重复 id 大声
        失败 400）；platform（可选，锚定命中按生成平台过滤）；clarifications
        （可选 [{question, answer}] 字符串对，缺省空 = 向后兼容，回答随请求体
        走、不拼进题面）。事件形状：done 的 data = 推荐结果 dict（顶层
        modules[] + requirements + 识别到历史赛题时带 topic_id + references
        最终参考清单 auto / manual 标注），question 的 data =
        {"questions": [...]}，error 的 data = {"message": 中文信息}——逐字
        契约与两阶段编排（澄清先行 → 收敛 → done 载荷组装）见
        selection.run_recommendation，本路由只取参 + 转调 + sse 包装。
        错误语义：参数校验失败 400，LLM 服务失败 502，流内错误经 error 终态
        补发（文案走错误映射表）。

        阻塞调用（每轮 2-4K token）放独立线程跑，事件经队列送流生成器——不占
        事件循环；断线后队列无人消费：进度事件旁路丢弃（满即丢），后端照常
        结束本次推荐（与提炼端点同款，spec「断线」）。"""
        problem_text = _require_str(payload, "problem_text")
        topic_id = _optional_str(payload, "topic_id")
        reference_ids = _require_str_list(payload, "reference_ids")
        platform = _optional_str(payload, "platform")
        # 澄清历史（工单 01 推荐先澄清后收敛）：[{question, answer}] 字符串对，
        # 缺省空 = 向后兼容；回答随请求体走、不拼进题面（题面保持原文——收敛
        # 判定的"两轮一致"对照依赖逐句编号，题面被污染会让判定失真）
        clarifications = _require_clarifications(payload)
        # 完整上下文已在装配点（resolve_topic_context）一次备好：两级注入的
        # 清单段 / 全文回读 / 模块库摘要行都由它携带，路由只消费（key 空 =
        # 未识别到历史赛题，no-topic 形同样携带全模块摘要）；手动选参考资料
        # 的准入 / 全文直读同样在装配点完成。platform（工单 01）= 锚定命中
        # 按生成平台过滤（手动选不过滤），缺省 / 空 = 现状不过滤
        topic = _assemble_topic_context(
            context, topic_id, problem_text, _llm(context), reference_ids, platform
        )

        def run(emit: SseEmitter) -> None:
            # 两阶段编排归 selection.run_recommendation（澄清先行 → 收敛 →
            # done 载荷组装），路由只转调——终态一律由域函数发出，路由不分支；
            # run 抛错由运行器补发 error 终态（终态保证归运行器）
            run_recommendation(topic, _llm(context), clarifications, emit=emit)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/topic/summarize")
    @_map_errors
    def topic_summarize(payload: dict) -> dict:
        """赛题简介（赛题简介步骤，wait-what 效果）：AI 预读题面给一句话
        总览 + 功能要点。

        让用户在选平台 / 推荐模块之前对"这个赛题要实现什么"有简短认知；
        只做展示、不进任何下游流程（推荐 / 骨架有自己的题面处理，这里不
        注入）。文本模式单次 LLM 调用，失败走错误映射表（LLM 服务失败 →
        502）。"""
        problem_text = _require_str(payload, "problem_text")
        return {"summary": _llm(context).summarize_topic(problem_text)}

    @app.post("/api/selection/expand")
    @_map_errors
    def expand_selection(payload: dict) -> dict:
        """展开依赖 + 平台可用性检查：用户增删选择后重跑一次即可。"""
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        resolved = resolve_selection(_library_dir(context), platform, slugs)
        return {
            "modules": [m.to_dict() for m in resolved.manifests],
            "warnings": [
                {"slug": w.slug, "kind": w.kind, "message": w.message}
                for w in resolved.warnings
            ],
        }

    @app.post("/api/skeleton")
    @_map_errors
    def skeleton(payload: dict) -> dict:
        """main.c 骨架：LLM 出稿 + 静态自检（不存在的调用改写为注释占位）。

        历史赛题入口：选中某题时题面用库内全文（长 PDF 题面全文只在选了该赛
        题时进上下文）；骨架阶段不注入参考文件、不自动并入模块（模块选择由
        用户 / 推荐链路决定——spec Out of Scope，等真实用例再评估）。"""
        problem_text = _require_str(payload, "problem_text")
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        topic_id = _optional_str(payload, "topic_id")
        topic = _assemble_topic_context(
            context, topic_id, problem_text, _llm(context)
        )
        resolved = resolve_selection(_library_dir(context), platform, slugs)
        main_c, intercepted = generate_skeleton(
            _llm(context),
            topic.problem_text,
            resolved.manifests,
            platform,
            _library_dir(context),
            master_project_dir(_require_config(context).masters_dir, platform),
        )
        return {"main_c": main_c, "intercepted": list(intercepted)}

    @app.post("/api/pick-directory")
    @_map_errors
    def pick_directory() -> dict:
        """弹原生文件夹选择对话框（本地工具专用），返回 {"path": 绝对路径}。

        浏览器拿不到所选文件夹的绝对路径（见 _tkinter_pick_directory），
        由服务端弹系统对话框；用户取消时 path 为 null，前端不覆盖输入框。
        """
        return {"path": context.pick_directory()}

    @app.post("/api/generate")
    @_map_errors
    def generate(payload: dict) -> dict:
        """完整生成：选模块 → 母版 → 生成 → 摘要（流程在 generate_project）。

        历史赛题入口：topic_id 给定时装配点（resolve_topic_context）校验编号
        查库——查无此条明确报错（不猜测编造）；模块集 = 用户选择原样展开
        （工单 module-universalization/07 起不再自动并入"题专用模块"）。"""
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        main_c = _require_str(payload, "main_c")
        output_dir = Path(_require_str(payload, "output_dir"))
        topic_id = _optional_str(payload, "topic_id")
        config = _require_config(context)
        if topic_id:
            # 显式编号路径不需要 AI 提取（题面 / 关联素材已装配）；查无此条大声报错
            _assemble_topic_context(context, topic_id, "", None)
        summary = generate_project(
            platform=platform,
            slugs=slugs,
            main_c_content=main_c,
            output_dir=output_dir,
            module_library_dir=config.module_library_dir,
            masters_dir=config.masters_dir,
        )
        return _generation_result(summary)

    # ------------------------------------------------------------------
    # 模块库（工单 07）：浏览 / AI 录入 / 编辑简介 / 多平台版本 / 删除
    # ------------------------------------------------------------------

    @app.get("/api/modules")
    @_map_errors
    def modules() -> list[dict]:
        """浏览模块库（磁盘目录即数据库，实时读盘）。"""
        return [m.to_dict() for m in list_modules(_library_dir(context))]

    @app.post("/api/modules")
    @_map_errors
    def module_add(payload: dict) -> dict:
        """AI 录入：通读代码出简介草稿 → 用户填简介 → 一致性校验通过才入库。

        description 为空时先让 AI 出草稿（草稿本身不校验，由用户确认）。
        """
        slug = _require_str(payload, "slug")
        platform = _require_str(payload, "platform")
        description = str(payload.get("description", "")).strip()
        files = payload.get("files")
        if not isinstance(files, dict):
            raise HTTPException(400, "files 必须是 {文件名: 内容} 对象")
        llm = _llm(context)
        if not description:
            description = draft_description(llm, files)
            return {"draft": description}
        manifest = add_module(
            llm,
            _library_dir(context),
            slug=slug,
            platform=platform,
            description=description,
            files=files,
            dependencies=_require_str_list(payload, "dependencies", default=()),
            hardware_bound=_require_flag(payload, "hardware_bound"),
            verified=_require_flag(payload, "verified"),
            notes=str(payload.get("notes", "")),
            # 硬件身份字段透传（必填 / URL 格式校验在核心层，缺省走 LibraryError）
            kit=_optional_str(payload, "kit"),
            source_url=_optional_str(payload, "source_url"),
        )
        return manifest.to_dict()

    @app.put("/api/modules/{slug}/description")
    @_map_errors
    def module_description(slug: str, payload: dict) -> dict:
        """编辑简介：AI 校验新简介与代码一致后才写回。"""
        manifest = update_module_description(
            _llm(context), _library_dir(context), slug, _require_str(payload, "description")
        )
        return manifest.to_dict()

    @app.post("/api/modules/{slug}/platform-files")
    @_map_errors
    def module_platform_files(slug: str, payload: dict) -> dict:
        """给模块添加某平台版本文件（内容一致的共享路径复用）。"""
        platform = _require_str(payload, "platform")
        files = payload.get("files")
        if not isinstance(files, dict):
            raise HTTPException(400, "files 必须是 {文件名: 内容} 对象")
        manifest = add_platform_files(
            _library_dir(context),
            slug,
            platform,
            files,
            hardware_bound=_require_flag(payload, "hardware_bound"),
            kit=_optional_str(payload, "kit"),
            source_url=_optional_str(payload, "source_url"),
        )
        return manifest.to_dict()

    @app.delete("/api/modules/{slug}/platform-files")
    @_map_errors
    def module_platform_files_delete(slug: str, payload: dict) -> dict:
        """删除某平台版本的文件（共享文件只移出条目，磁盘保留）。"""
        platform = _require_str(payload, "platform")
        filenames = _require_str_list(payload, "filenames")
        manifest = remove_platform_files(
            _library_dir(context), slug, platform, filenames
        )
        return manifest.to_dict()

    @app.put("/api/modules/{slug}/platform-identity")
    @_map_errors
    def module_platform_identity(slug: str, payload: dict) -> dict:
        """编辑平台条目的硬件身份（kit / source_url，工单 02）。

        存量条目的补填 / 修改入口：只做格式校验（提供值须合法——kit 非空、
        source_url URL 格式），不走 AI 一致性校验——身份是事实信息、由人
        确认，AI 判不了真假；只改身份字段，该条目的文件列表 / 验证状态 /
        硬件绑定原样保留。空值视为未提供、保留原值（补填是逐步的）。
        """
        manifest = update_platform_identity(
            _library_dir(context),
            slug,
            _require_str(payload, "platform"),
            kit=_optional_str(payload, "kit"),
            source_url=_optional_str(payload, "source_url"),
        )
        return manifest.to_dict()

    @app.delete("/api/modules/{slug}")
    @_map_errors
    def module_delete(slug: str) -> dict:
        """删除模块：整个目录移除。"""
        delete_module(_library_dir(context), slug)
        return {"ok": True}

    # ------------------------------------------------------------------
    # 母版提炼（工单 08）：导入旧工程 → AI 报告 → 确认入库
    # ------------------------------------------------------------------

    @app.post("/api/masters/stage")
    @_map_errors
    async def masters_stage(files: list[UploadFile] = File(...)) -> dict:
        """「选择文件夹」上传（浏览器 webkitdirectory）→ 暂存目录 → 可喂扫描。

        浏览器出于安全不暴露绝对路径，选中的旧工程文件夹只能整夹上传：每个
        文件的文件名 = 文件夹内相对路径（webkitRelativePath，'/' 分隔），
        服务端按相对路径原样落到 masters 目录同级 staged/<原文件夹名> 下——
        目录名保留原名（重名覆盖写），扫描 / 报告 / 入库全程显示原名，前端
        无需二次映射。暂存语义（穿越拒绝 / 目录名清洗 / 噪音跳过 = .git
        任意深度 + 构建产物 Debug/Release/Listings/Objects、单次上限 512MB）
        归 stage.py 单源：穿越吃 entry_store.is_unsafe_path、噪音吃
        treewalk.skip_project_noise，路由只收参数转调。暂存目录是普通目录，
        扫描后即用，不自动清理。
        """
        staged = stage_project_files(
            _masters_dir(context),
            [(f.filename or "", await f.read()) for f in files],
        )
        return {"staged": [{"path": str(staged), "name": staged.name}]}

    @app.post("/api/masters/scan")
    @_map_errors
    def masters_scan(payload: dict) -> list[dict]:
        """逐个扫描导入的旧工程：平台检测 + 文件清单 + 配置摘要。"""
        return [
            {
                "name": structure.name,
                "platform": structure.platform,
                "files": list(structure.files),
                "config_summary": list(structure.config_summary),
            }
            for structure in (
                scan_project(Path(d))
                for d in _require_str_list(payload, "project_dirs")
            )
        ]

    @app.post("/api/masters/distill")
    @_map_errors
    def masters_distill(payload: dict) -> StreamingResponse:
        """AI 提炼报告（SSE 流，工单 02）：start → 进度事件 → done（完整报告）
        或 error（中文信息）→ 流结束。HTTP 200 起流，失败以流内 error 事件收尾
        （客户端只认事件，不依赖状态码）；确认前不落任何东西、服务端无状态，
        报告必须随流返回（没有二次查询的可能）。

        提炼是阻塞调用（单批 2-5 分钟）：放独立线程跑，事件经队列送流生成器
        ——不占事件循环。断线（客户端关闭）后队列无人消费：进度事件旁路丢弃
        （满即丢，不堵提炼线程），后端照常结束本次提炼（无副作用）。
        扫描 / 对比 / 拼装是瞬间步骤，不发事件，直接以 start（带总量）开头、
        done 收尾——start 由 llm 层发射器产生（工单 01：总量先算定）。
        """
        platform = _require_str(payload, "platform")
        project_dirs = _require_str_list(payload, "project_dirs")
        llm = _llm(context)

        def run(emit: SseEmitter) -> None:
            projects = [scan_project(Path(d)) for d in project_dirs]
            report = distill_master(llm, platform, projects, emit.progress)
            emit.done(report.to_dict())

        # 终态保证归运行器：run 抛错由 run_sse 补发 error 终态（文案走错误映射表）
        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/masters/confirm")
    @_map_errors
    def masters_confirm(payload: dict) -> dict:
        """确认报告：落盘母版候选 → 结构分析 → 入库（事务在 confirm_distillation）。

        报告含归档动作（工单 02）时，归档条目随确认事务一起提交（LLM 判定 +
        复制入库、锚定该题）；AI 服务与参考文件库目录按需取用——无归档动作的
        确认不要求 AI 配置（与现状一致）。
        """
        project_dirs = [Path(d) for d in _require_str_list(payload, "project_dirs")]
        config = _require_config(context)
        meta = confirm_distillation(
            _masters_dir(context),
            project_dirs,
            payload,
            llm_factory=lambda: _llm(context),
            reference_library_dir=reference_library_dir(config.module_library_dir),
        )
        return {
            "platform": meta.platform,
            "sources": list(meta.sources),
            "warnings": list(meta.warnings),
        }

    @app.get("/api/masters")
    @_map_errors
    def masters() -> list[dict]:
        """浏览母版库（每平台一个母版）。"""
        return [
            {"platform": m.platform, "sources": list(m.sources), "warnings": list(m.warnings)}
            for m in list_masters(_masters_dir(context))
        ]

    @app.delete("/api/masters/{platform}")
    @_map_errors
    def master_delete(platform: str) -> dict:
        delete_master(_masters_dir(context), platform)
        return {"ok": True}

    # ------------------------------------------------------------------
    # 设置：读写配置，写入后即时生效（后续请求即用新配置）
    # ------------------------------------------------------------------

    @app.get("/api/settings")
    @_map_errors
    def settings_get() -> dict:
        """读取设置；API key 只回掩码（前 4 位 + 与真实长度一致的圆点），不回明文。"""
        config = _current_config(context)
        api_key = config.api_key if config is not None else ""
        return {
            "configured": config is not None,
            "base_url": (config.base_url if config is not None else ""),
            "model": (config.model if config is not None else ""),
            "api_key": _mask_api_key_display(api_key),
            "module_library_dir": str(
                config.module_library_dir if config is not None else AppConfig().module_library_dir
            ),
            "masters_dir": str(
                config.masters_dir if config is not None else AppConfig().masters_dir
            ),
            "config_path": str(context.config_path),
        }

    @app.put("/api/settings")
    @_map_errors
    def settings_put(payload: dict) -> dict:
        """保存设置并立即生效；api_key 收到掩码说明用户没改，沿用旧值。"""
        existing = _current_config(context)
        api_key = str(payload.get("api_key", "")).strip()
        # 空或等于当前 key 的任一掩码形态（省略号版 / 圆点版）→ 用户没改 key，沿用旧值
        if not api_key or (
            existing is not None
            and api_key
            in (_mask_api_key(existing.api_key), _mask_api_key_display(existing.api_key))
        ):
            if existing is None:
                raise HTTPException(400, "首次配置必须填写 API key")
            api_key = existing.api_key
        config = AppConfig(
            base_url=_require_str(payload, "base_url"),
            api_key=api_key,
            model=_require_str(payload, "model"),
            module_library_dir=Path(_require_str(payload, "module_library_dir")),
            masters_dir=Path(_require_str(payload, "masters_dir")),
        )
        save_config(config, context.config_path)
        context.config = config  # 即时生效：后续请求直接用新配置
        return {"ok": True}

    # ------------------------------------------------------------------
    # 参考文件库（工单 02）：浏览 / 搜索 / AI 简介草稿 / 入库 / 删除
    # ------------------------------------------------------------------

    @app.get("/api/references")
    @_map_errors
    def references(
        title: str = "", type: str = "", anchor: str = "", filename: str = ""
    ) -> list[dict]:
        """浏览参考文件库：按标题 / 类型 / 锚定值 / 文件名子串过滤（可组合，空 = 全量）。

        文件名过滤时每条目附 matched_files（命中文件路径列表）——搜索直出
        文件，免"查看 → 清单 → 翻找"两跳；未过滤时不含该字段（向后兼容）。
        """
        config = _require_config(context)
        reference_root = reference_library_dir(config.module_library_dir)
        entries = []
        for entry in search_references(
            reference_root,
            title=title,
            type=type,
            anchor=anchor,
            filename=filename,
        ):
            data = entry.to_dict()
            if filename.strip():
                data["matched_files"] = match_entry_files(
                    reference_root, entry.id, filename
                )
            entries.append(data)
        return entries

    @app.post("/api/references/draft")
    @_map_errors
    def reference_draft(payload: dict) -> dict:
        """AI 通读素材生成简介草稿（草稿不校验、由用户确认后入库）。"""
        files = payload.get("files")
        if not isinstance(files, dict):
            raise HTTPException(400, "files 必须是 {文件名: 内容} 对象")
        return {"draft": reference_draft_description(_llm(context), files)}

    @app.post("/api/references")
    @_map_errors
    def reference_add(payload: dict) -> dict:
        """参考文件入库：结构校验（锚定词表 / 格式 / 文件路径）通过才落盘。

        锚定套件型号必须取自模块库已有 kit 词表（不新打字）；赛题编号做格式
        校验（查库确认待赛题库落地后接入）。
        """
        files = payload.get("files")
        if not isinstance(files, dict):
            raise HTTPException(400, "files 必须是 {文件名: 内容} 对象")
        config = _require_config(context)
        entry = add_reference(
            reference_library_dir(config.module_library_dir),
            title=_require_str(payload, "title"),
            type=_require_str(payload, "type"),
            description=_require_str(payload, "description"),
            anchor_kind=_require_str(payload, "anchor_kind"),
            anchor_value=_require_str(payload, "anchor_value"),
            files=files,
            kit_vocabulary=module_kit_vocabulary(config.module_library_dir),
            # 平台属性（工单 01）：缺省 / 空 = any（平台无关，向后兼容）；
            # 词表外值由 add_reference 大声失败（400）
            platform=_optional_str(payload, "platform") or PLATFORM_ANY,
        )
        return entry.to_dict()

    @app.delete("/api/references/{entry_id}")
    @_map_errors
    def reference_delete(entry_id: str) -> dict:
        """删除参考文件条目：整个目录移除。"""
        delete_reference(
            reference_library_dir(_require_config(context).module_library_dir),
            entry_id,
        )
        return {"ok": True}

    @app.get("/api/references/{entry_id}/files")
    @_map_errors
    def reference_files(entry_id: str) -> list[dict]:
        """条目文件清单：素材清单.txt 记录 + 条目目录实际文件（size 取实况）。"""
        config = _require_config(context)
        return list_entry_files(
            reference_library_dir(config.module_library_dir), entry_id
        )

    @app.get("/api/references/{entry_id}/files/{rel_path:path}")
    @_map_errors
    def reference_file(entry_id: str, rel_path: str) -> FileResponse:
        """条目文件服务：条目目录命中 = 文本内联；materials 镜像命中 = PDF 预览 /
        扩展名下载；两处都找不到抛 ReferenceError（映射 400，与条目不存在同通道，
        不再有内联 404）。路径安全校验在库内（is_unsafe_path → 400）。"""
        config = _require_config(context)
        path, media_type = resolve_entry_file(
            reference_library_dir(config.module_library_dir),
            materials_dir(config.module_library_dir),
            entry_id,
            rel_path,
        )
        return FileResponse(path, media_type=media_type)

    # ------------------------------------------------------------------
    # 赛题库（工单 01/05）：长 PDF 拆条 → 用户逐条校对 → 确认入库（事务）
    # + 编号解析 + 浏览 / 删除
    # ------------------------------------------------------------------

    @app.get("/api/topics")
    @_map_errors
    def topics() -> list[dict]:
        """浏览赛题库：全部条目按编号排序（浏览列表用）。

        列表一次性算好返回，前端不再按条回查——单条 GET /api/topics/{key}
        是生成入口素材，与浏览列表各司其职。
        """
        config = _require_config(context)
        return [
            entry.to_dict()
            for entry in list_topics(topic_library_dir(config.module_library_dir))
        ]

    @app.post("/api/topics/split")
    @_map_errors
    async def topics_split(upload: UploadFile = File(...)) -> dict:
        """上传历年真题长 PDF → 拆条（年份 / 编号 / 题面全文）→ 草稿列表。

        路由按全文长度分流（flash 模型输出预算有限，多年长 PDF 一次拆会被
        截断而静默漏题）：≤ TOPIC_SPLIT_LLM_CHAR_CAP 单次调 LLM 拆条（支持
        任意格式，单题短 PDF 的既有路径）；超长走确定性分块
        （split_topics_document：年份章节 + 题目标记切到单题，零 AI 改写，
        格式不匹配大声失败，不静默漏题）。取舍：超长不选"分批调 LLM"——大
        年份 8 题 ≈ 20K 字符输出仍超 flash 输出预算，块变小只是缩小不消除
        漏题；确定性切分无输出预算问题，且已真机验证 69/69 全对。拆条是
        草稿：用户逐条校对（改年份 / 题号 / 题面）后回传 /api/topics/confirm
        确认入库。
        """
        tmp_path = await _save_upload(upload)
        try:
            text = extract_file(tmp_path)
            if len(text) <= TOPIC_SPLIT_LLM_CHAR_CAP:
                drafts = _llm(context).topic_split_topics(text)
            else:
                drafts = split_topics_document(text)
        finally:
            tmp_path.unlink(missing_ok=True)
        return {"topics": [draft.to_dict() for draft in drafts]}

    @app.post("/api/topics/confirm")
    @_map_errors
    async def topics_confirm(
        pdf: UploadFile = File(...), payload: str = Form(...)
    ) -> dict:
        """确认入库（事务）：一条目一目录，题面 .md + manifest + 原 PDF 副本。

        multipart：pdf = 原 PDF 文件（复制进每个条目目录，AI 拆错可查原文）；
        payload = Form 里的 JSON：{entries: [{year, number, problem_text}],
        program_dirs: [附带程序目录，引用方式存绝对路径]}。任何校验失败都
        不落半成品（事务在 confirm_topics）。
        """
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, f"payload 不是合法 JSON：{exc}") from exc
        if not isinstance(data, dict):
            raise HTTPException(400, "payload 必须是 JSON 对象")
        entries = parse_confirm_entries(data)
        program_dirs = _require_str_list(data, "program_dirs", default=())
        tmp_path = await _save_upload(pdf)
        try:
            stored = confirm_topics(
                topic_library_dir(_require_config(context).module_library_dir),
                tmp_path,
                entries,
                program_dirs=program_dirs,
                pdf_filename=pdf.filename or "",
            )
        finally:
            tmp_path.unlink(missing_ok=True)
        return {"topics": [entry.to_dict() for entry in stored]}

    @app.post("/api/topics/extract-number")
    @_map_errors
    def topics_extract_number(payload: dict) -> dict:
        """AI 从文本提取赛题编号（如 "2026C"）；不是赛题文本返回 key=null。

        与编号解析配套：粘贴题面自动识别编号后走 GET /api/topics/{key} 取题面。
        """
        key = _llm(context).topic_extract_number(_require_str(payload, "text"))
        return {"key": key}

    @app.get("/api/topics/{key}")
    @_map_errors
    def topic_get(key: str) -> dict:
        """编号解析："2026C" → 题面全文 + 附带程序（生成入口素材）。

        查无此条明确报错（不猜测编造）。
        """
        config = _require_config(context)
        entry = resolve_number(topic_library_dir(config.module_library_dir), key)
        return entry.to_dict()

    @app.delete("/api/topics/{key}")
    @_map_errors
    def topic_delete(key: str) -> dict:
        """删除赛题条目：整个目录移除（含题面与原 PDF 副本）。

        查无此条明确报错（不猜测编造）；编号格式非法先拒绝（入口拦截路径
        穿越）。
        """
        delete_topic(topic_library_dir(_require_config(context).module_library_dir), key)
        return {"ok": True}

    return app


# ---------------------------------------------------------------------------
# 辅助：响应拼装
# ---------------------------------------------------------------------------


def _generation_result(summary: GenerationSummary) -> dict:
    """生成结果摘要 → JSON（推导逻辑在核心 describe_generation，这里只做形态转换）。"""
    return {
        "output_dir": str(summary.output_dir),
        "structure": list(summary.structure),
        "include_dirs": list(summary.include_dirs),
        "modules": [
            {"slug": slug, "files": list(files)} for slug, files in summary.modules
        ],
    }


app = create_app()


def main() -> None:
    """本地服务入口：python -m contest_generator.webapp 或 contest-generator。"""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
