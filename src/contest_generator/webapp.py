"""FastAPI 薄壳：装配全部后端能力，形成可用产品（spec 工单 09）。

路由层只做三件事：收 HTTP 请求 → 调核心函数 → 转 JSON 响应；LLM / 文件
抽取是薄壳的一部分，工程生成 / 模块库 / 母版提炼等全部走纯逻辑核心。
用户级设置（AI API / 工作目录）存本机配置文件，写入后即时生效——每次
请求按上下文里的当前配置构造 LLM，不重启服务。

依赖注入：AppContext 持有配置路径 / LLM 工厂，测试注入 tmp 目录与假 LLM，
网络调用不进测试。
"""

from __future__ import annotations

import base64
import contextlib
import functools
import inspect
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__  # 工具版本（上下文清单 tool_version 字段）
from .boards import BOARDS_DIR, board_for_platform, load_boards
from .changelog import load_changelog
from .compile_runner import (
    CompileRunnerError,
    find_ccs_tools,
    find_make,
    find_uv4,
    resolve_compile_toolchain,
    run_compile,
)
from .config import (
    DEFAULT_CONFIG_PATH,
    AppConfig,
    ConfigError,
    load_config,
    materials_dir,
    pdf_trash_dir,
    reference_library_dir,
    save_config,
    topic_library_dir,
)
from .context_manifest import (
    CONTEXT_MANIFEST_FILENAME,
    ContextError,
    _infer_platform,
    infer_context,
    missing_fields_for,
    read_context_fields,
    read_project_main_c,
    validate_context_fields,
)
from .deepen import DeepenError, run_deepen
from .delivery import DeliveryError, delivery_check, open_project_dir, package_project
from .flash import FlashError, flash_project, resolve_flash_tool
from .task_progress import (
    TaskError,
    backup_task_plan,
    check_plan_replaceable,
    run_task,
    run_task_planning,
    write_task_plan,
)
from .errors import error_entry
from .events import (
    EVENT_CACHE_HIT,
    EVENT_IDEA_ANALYZING,
    EVENT_IDEA_RESULT,
    EVENT_PARAM_RESULT,
    ProgressEvent,
)
from .extraction import (
    IMAGE_FILE_SUFFIXES,
    extract_file,
    extract_image,
    extract_pdf_with_image_notes,
    image_data_url,
    locate_topic_pages_full,
    render_pdf_pages,
    # 页渲染原语按公开名引入（模块级函数 = monkeypatch 接缝，测试以此为
    # 稳定挂载点；工单 topic-pdf-viewer/01 取题面页图展示用）
    _render_page_png as render_page_png,
)
from .vision import (
    DEFAULT_VISION_BASE_URL,
    DEFAULT_VISION_MODEL,
    VisionError,
    describe_image,
    effective_vision_api_key,
    vision_configured,
)
from .vision_qa import answer_figure_question
from .fix_errors import (
    FixError,
    fix_backup_root,
    resolve_source_path,
    restore_backup,
    run_fix_round,
)
from .generator import (
    GenerationSummary,
    TopicContext,
    build_reference_fulltexts,
    build_topic_framework_info,
    generate_project,
    resolve_topic_context,
)
from .generation_output import (
    GenerationBusyError,
    GenerationConflictError,
    backup_project_dir,
    desktop_topic_dir_verdict,
    topic_dir_title,
    with_platform_suffix,
)
from .recent_jobs import (
    clear_recent,
    delete_recent,
    load_recent,
    recent_file,
    record_recent,
    update_recent_status,
)
from .impact import run_impact_analysis
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
from .manifest import ManifestSummary, ModuleManifest
from .llm import (
    LLM,
    LLMError,
    LLMObservationCollector,
    RetryBudget,
    TOPIC_SPLIT_LLM_CHAR_CAP,
    TopicFramework,
    DeepSeekLLM,
    build_llm,
    create_llm_observation_collector,
)
from .readme import _pin_row_text, _pin_rows
from .report_draft import PLACEHOLDER
from .llm_telemetry import bind_llm_telemetry
from .llm_pricing import (
    DEEPSEEK_FLASH_PRICE_REFERENCE,
    price_tables_from_config,
    price_tables_to_config,
)
from .llm_recent_workflows import LLMRecentWorkflowStore, attach_cost_estimates
from .recommend_cache import (
    cache_key,
    cache_recommend,
    clear_recommend_cache,
    library_fingerprint,
    load_recommend,
    parameter_warnings,
    recommend_cache_path,
    validate_recommend,
)
from .master import (
    confirm_distillation,
    distill_master,
    scan_project,
)
from .master_store import (
    delete_master,
    import_master,
    import_master_direct,
    list_masters,
    master_health,
    master_key_files,
    master_project_dir,
    master_stats,
    master_tree_files,
    read_master_file,
    read_master_tree_file,
)
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32
from .patchers import UnknownPlatformError
from .pdf_library import list_pdfs, pdf_page_count, resolve_pdf, trash_pdf
from .pin_bindings import (
    PinBindingError,
    auto_assign_bindings,
    resolve_bindings,
)
from .reference_library import (
    PLATFORM_ANY,
    TOPIC_TYPES,
    ReferenceEntry,
    add_reference,
    delete_reference,
    draft_description as reference_draft_description,
    list_entry_files,
    match_entry_files,
    module_kit_vocabulary,
    resolve_entry_file,
    search_references,
    update_reference,
)
from .revision import restore_revision, revise_backup_root, run_revision
from .selection import (
    default_instance_plan,
    parse_instances,
    parse_score_points,
    resolve_dependencies,
    resolve_selection,
    run_recommendation,
)
from .skeleton import run_skeleton
from .sse import SseEmitter, run_sse
from .stage import stage_project_files
from .topic_library import (

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

STATIC_DIR = Path(__file__).parent / "static"

# 任务执行注册表（工单 stuck-doing-recover/01）：task_id → 正在执行。
# 模块级 = 测试可注入/断言；单进程本地工具的语义：进程活着 = 注册表有记录 =
# 任务真在执行；进程死了 = 注册表自然清空 = 「僵尸 doing 恢复」安全。
# tasks_execute 进 run() 时 add、finally discard（完成 / 异常都清）；
# tasks_status 见占用记录即拒人工改标（防把正在跑的任务恢复为 pending 后
# 并发双写 main.c）。
_running_task_execs: set[str] = set()

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
    llm_factory: Callable[..., LLM] = build_llm
    tab_registry: TabRegistry = field(default_factory=TabRegistry)
    pick_directory: Callable[[], str | None] = _tkinter_pick_directory
    desktop_dir: Callable[[], Path] = lambda: Path.home() / "Desktop"
    recent_llm_workflows: LLMRecentWorkflowStore = field(default_factory=LLMRecentWorkflowStore)
    # 生成互斥注册表（工单 generate-conflict-guard/01）：同键（桌面=题名 /
    # 手动=目录）同时只放一个生成流程进闸，其余 409「正在生成中」——防多
    # 标签页 / 连点攒半成品目录（旧 unique 静默换名行为已废弃）。
    pending_generations: set[str] = field(default_factory=set)
    _generation_lock: threading.Lock = field(default_factory=threading.Lock)


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


def _flash_auto_tools() -> dict:
    """烧录工具自动探测状态（settings GET 用，工单 flash-deploy/02）：按平台
    各探测一次（空覆盖 = 纯自动：which / C:/ti/ccs* 扫 DSLite），返回
    {stm32: {kind, exe, display} | null, mspm0: ...}。探测不到 = null（前端
    不显示「已自动找到」，走设置路径配置）。resolve_flash_tool 对未知平台抛
    FlashError——这里只传 KNOWN_PLATFORMS 两个平台，不会触发。
    """
    def _probe(platform: str) -> dict | None:
        tool = resolve_flash_tool(platform)
        if tool is None:
            return None
        return {"kind": tool.kind, "exe": str(tool.exe), "display": tool.display}

    return {"stm32": _probe(PLATFORM_STM32), "mspm0": _probe(PLATFORM_MSPM0)}


def _require_config(ctx: AppContext) -> AppConfig:
    config = _current_config(ctx)
    if config is None:
        raise HTTPException(
            400, "未配置 AI API：请先到设置页填写 API 后再使用 AI 功能"
        )
    return config


def _module_library_summaries(module_library_dir: Path) -> tuple[ManifestSummary, ...]:
    """模块库摘要行（影响分析 / 修订的 AI 素材）：从库一次扫描构建。

    与推荐装配点（resolve_topic_context 的 manifest_summaries）同源同构——
    修订分析不依赖赛题装配，直接按库全量构建（影响分析需要看到库内全部
    模块才能判断增删）。
    """
    from .manifest import build_manifest_summaries

    if not module_library_dir.is_dir():
        return ()
    return tuple(build_manifest_summaries(list_modules(module_library_dir)))


def _pin_summary_text(platform: str, manifests: Sequence[ModuleManifest]) -> str:
    """引脚表摘要（设计报告草稿 LLM 素材，工单 report-draft-demo/03）：与
    README 同源（readme._pin_rows，生效引脚口径 = 声明默认值——绑定覆盖 /
    多实例行不进素材，docstring 声明口径，评审留痕）；行格式与 README / 报告
    草稿共用（readme._pin_row_text 单一出处）。无声明 = 占位句（LLM 不必硬
    猜）。"""
    rows = _pin_rows(platform, manifests)
    if not rows:
        return "（本工程模块未声明引脚接线）"
    return "\n".join(_pin_row_text(row) for row in rows)


def _load_revision_context(
    output_dir: Path, module_library_dir: Path
) -> tuple[str, dict[str, Any]]:
    """修订 / 深化端点共用的上下文装载（revise-context 与 revise-analyze 单址）。

    有清单直读（read_context_fields 缺字段补空兼容；main.c 现读磁盘覆盖生成
    时快照——手工编辑不丢）；无清单自动反推（infer_context：平台 / 模块 /
    绑定 / main.c 尽力回读）。两者都过形状校验（平台词表 / slugs 库内存在性 /
    绑定键形状，非法 400 中文）。返回 (source, fields)。
    """
    fields = read_context_fields(output_dir)
    if fields is not None:
        validate_context_fields(fields, module_library_dir)
        # main.c 统一现读磁盘（spec「main.c 原样保留，不丢手工编辑」）：
        # 清单里是生成时快照，用户生成后手改过 → 加载必须反映当前内容，
        # 深化/修订基于现读，不基于陈旧快照
        current_main = read_project_main_c(output_dir)
        if current_main:
            fields["main_c"] = current_main
        return "manifest", fields
    fields, _ = infer_context(output_dir, module_library_dir)
    validate_context_fields(fields, module_library_dir)
    return "inferred", fields


def _llm(
    ctx: AppContext,
    retry_budget: RetryBudget | None = None,
    observation_collector: LLMObservationCollector | None = None,
) -> LLM:
    factory = ctx.llm_factory
    config = _require_config(ctx)
    params = list(inspect.signature(factory).parameters.values())
    positional = {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    }
    if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params):
        positional_count = 3
    else:
        positional_count = sum(1 for p in params if p.kind in positional)
    if positional_count >= 3:
        return factory(config, retry_budget, observation_collector)
    if positional_count >= 2:
        return factory(config, retry_budget)
    return factory(config)


def _library_dir(ctx: AppContext) -> Path:
    return _require_config(ctx).module_library_dir


def _instance_known_slugs(module_library_dir: Path, slugs: Sequence[str]) -> list[str]:
    """parse_instances 的合法 slug 集 = 选中 ∪ 依赖展开（工单 instance-config-deps/01）。

    依赖带入的多实例模块（如 led_beep 依赖 led）也允许配实例清单：用户只选了
    声光组合模块也能配多灯（前端实例卡据此显示）。未进工程的模块仍大声失败
    （防幻觉 / 手滑），防线不缩。
    """
    by_slug = {m.slug: m for m in list_modules(module_library_dir)}
    return [m.slug for m in resolve_dependencies(slugs, by_slug)]


def _masters_dir(ctx: AppContext) -> Path:
    return _require_config(ctx).masters_dir


def _assemble_topic_context(
    context: AppContext,
    topic_id: str,
    problem_text: str,
    llm: LLM | None,
    reference_ids: Sequence[str] = (),
    platform: str = "",
    slugs: Sequence[str] = (),
) -> TopicContext:
    """生成流程的历史赛题入口素材装配（单一 helper，三路由共用）。

    显式 topic_id 或粘贴题面自动识别 → 完整 TopicContext（永远非 None；
    key 为空串 = 未识别到历史赛题，按纯粘贴题面流程走；识别到时题面用库内
    全文——长 PDF 题面全文只在选了该赛题时进上下文）。装配唯一出处 =
    generator.resolve_topic_context，这里只取配置、推导目录、传参；显式编号
    查无此条大声报错；自动识别尽力而为（提取失败 / 查无此条静默降级）。
    推荐 / 骨架传 _llm(context)（自动识别），生成传 None（显式编号路径）。
    reference_ids = 手动选参考资料（工单 01；推荐与骨架路由传——骨架阶段
    注入参考实现草稿，生成不注入，见 ADR 0006 修订）。platform（工单 01
    平台属性）= 锚定命中过滤依据：推荐与骨架路由传请求体 platform（生成
    不注入参考文件，传缺省）。slugs（修订）= 套件锚定只收选中模块的 kit：
    骨架路由传（选了这套件给配套例程）；推荐 / 生成不传（推荐无选中集，
    生成不注入参考）。
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
        slugs=slugs,
    )


def _topic_framework_response(
    framework: TopicFramework | None, entry: ReferenceEntry | None
) -> dict[str, Any]:
    """/api/skeleton 返回体的 topic_framework 字段形状（工单 topic-framework/04）：
    injected 恒有；为真时带 topic_type / source（= 条目标题，展示用）。"""
    if framework is None:
        return {"injected": False}
    return {
        "injected": True,
        "topic_type": framework.topic_type,
        "source": framework.source,
    }


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


def _require_str(payload: dict, key: str, *, allow_empty: bool = False) -> str:
    """必填字符串字段（键缺失或非字符串抛 400）；allow_empty=False（缺省）
    时空白也拒——空串合法性由领域校验裁决（如未锚定条目的锚定值必须为空，
    topic / kit 锚定不可为空），故仅 anchor_value 传 allow_empty=True。"""
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise HTTPException(400, f"缺少必填字段：{key}")
    return value.strip()


def _parse_chat_history(payload: dict) -> list[tuple[str, str]]:
    """聊天 history 归一化（单源，工单 params-chat-ai/01 评审整改）。

    两个持久化聊天端点（全局商量 / 参数速调咨询）共用同一契约：history 必须
    是非空数组（旧 → 新），逐条为 {role: user|assistant, content: str}，且
    末条强制 user（误传 assistant 结尾会把 AI 文本错标为 user 落盘——持久化
    聊天后果重）。任何不满足 → TaskError 400 中文。返回 [(role, content), ...]。
    """
    raw_history = payload.get("history")
    if not isinstance(raw_history, list) or not raw_history:
        raise TaskError(
            "history 必须是数组（旧 → 新的讨论记录，最后一条 = 本轮消息）"
        )
    history: list[tuple[str, str]] = []
    for index, item in enumerate(raw_history, 1):
        if not isinstance(item, dict):
            raise TaskError(f"history 第 {index} 条必须是对象")
        role = item.get("role")
        if role not in ("user", "assistant"):
            raise TaskError(
                f"history 第 {index} 条 role 必须是 user 或 assistant"
            )
        content = item.get("content")
        if not isinstance(content, str):
            raise TaskError(f"history 第 {index} 条 content 必须是字符串")
        history.append((role, content))
    if history[-1][0] != "user":
        raise TaskError(
            "history 最后一条必须是 user（本轮消息）——请检查讨论记录形状"
        )
    return history


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


def _read_global_note(output_dir: Path) -> str:
    """读工程级全局结论（工单 idea-suite/01）：全局商量采纳的结论 → 注入
    每步任务执行 / 直接修正的 prompt；无文件 / 未采纳 = 空串（既有调用形状
    逐字节不变）。坏 JSON → TaskError 400（与聊天路由同日径：读侧宁拒收不吞）。
    """
    from .idea_chat import read_idea_chat

    return read_idea_chat(output_dir).note


def _optional_dict(payload: dict, key: str) -> dict | None:
    """可选 dict：缺省 / null / 空对象 → None（恢复默认）；类型非法抛 400。

    条目级校验由消费侧（price_tables_from_config）旁路跳过，这里只保外层形状。
    """
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise HTTPException(400, f"{key} 必须是 JSON 对象")
    return value or None


def _optional_bool(payload: dict, key: str, *, default: bool) -> bool:
    """可选布尔：缺省 / null → default；类型非法抛 400。"""
    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise HTTPException(400, f"{key} 必须是布尔值")
    return value


def _optional_choice(
    payload: dict, key: str, *, default: str, choices: tuple[str, ...]
) -> str:
    """可选枚举：缺省 / null → default；值不在词表抛 400（工单 01 计费时段）。"""
    value = payload.get(key)
    if value is None:
        return default
    if value not in choices:
        raise HTTPException(400, f"{key} 必须是 {'、'.join(choices)} 之一")
    return value


def _optional_int_range(
    payload: dict, key: str, *, default: int, low: int, high: int
) -> int:
    """可选整数（范围约束）：缺省 / null → default；类型非法 / 越界抛 400。"""
    value = payload.get(key)
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool):
        raise HTTPException(400, f"{key} 必须是整数")
    if not low <= value <= high:
        raise HTTPException(400, f"{key} 必须在 {low}-{high} 之间")
    return value


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


def _masked_optional_key(
    payload: dict, key: str, existing: str
) -> str:
    """可选密钥字段（工单 vision-eyes/01）：缺省 / 空串 = 关闭；收到掩码形态
    （前 4 位 + 省略号） = 用户没改，沿用旧值；其余 = 新值。"""
    value = _optional_str(payload, key)
    if not value:
        return ""
    if value in (_mask_api_key(existing), _mask_api_key_display(existing)):
        return existing
    return value


def _resolve_vision(config: AppConfig) -> tuple[str, str, str]:
    """装配层解析有效视觉参数 (base_url, api_key, model)（工单
    vision-deepseek-native/01）：视觉 key 留空 + DeepSeek 官方端点 = 复用主
    key；config 保持原始值语义（设置页回显不因复用失真）。四个消费点共用，
    防装配漂移。"""
    return (
        config.vision_base_url,
        effective_vision_api_key(
            config.vision_api_key, config.api_key, config.vision_base_url
        ),
        config.vision_model,
    )


# 视觉通道自检（工单 vision-selfcheck/01）：内置 1×1 PNG（与测试同款常量）
# + 独立自检 prompt——describe_image 无缓存真实调用一次，通过 = 配置当前可用
VISION_SELFCHECK_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
    "DwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
VISION_SELFCHECK_PROMPT = (
    "这是一张 1×1 像素测试图，请用一句话描述你看到的内容；若看不清，"
    "直接回复「测试图」。"
)


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


def _desktop_output_requested(payload: dict) -> bool:
    """桌面输出开关：显式值优先；旧请求无 problem_text 时保持手填目录。"""
    if "create_desktop_topic_dir" in payload:
        return _optional_bool(payload, "create_desktop_topic_dir", default=False)
    return bool(_optional_str(payload, "problem_text"))


@contextlib.contextmanager
def _generation_guard(context: AppContext, key: str) -> Iterator[None]:
    """同键生成互斥（工单 generate-conflict-guard/01）。

    键已注册 = 同名工程生成中 → GenerationBusyError（409 中文，路由透传）；
    未注册 → 注册后 yield，生成完成 / 失败后在 finally 注销。注册表是
    AppContext 共享 set + Lock：多标签页进程内并发请求都走同一把闸。"""
    with context._generation_lock:
        if key in context.pending_generations:
            raise GenerationBusyError("同名工程正在生成中，请等待生成完成后再试")
        context.pending_generations.add(key)
    try:
        yield
    finally:
        with context._generation_lock:
            context.pending_generations.discard(key)


def _open_in_explorer(directory: Path) -> None:
    """生成成功后自动打开资源管理器（工单 generate-conflict-guard/04）。"""
    try:
        subprocess.Popen(
            ["explorer.exe", str(directory)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass  # 打不开资源管理器：生成已成功，静默（不因聚焦失败报 500）


def _resolve_generation_output_dir(
    context: AppContext,
    payload: dict,
) -> tuple[Path, str]:
    """生成请求 → (最终 output_dir, 目录裁决 verdict)。

    历史赛题（topic_id 给定）：确定性取「编号 + 英文短名 + 平台后缀」（如
    `2024H_Auto_Car_STM32`，topic_dir_title + with_platform_suffix + 内置字典）
    ——不依赖 AI 简介（省一次 LLM 调用，目录名稳定可预期，且纯 ASCII 绕开
    CCS/gmake 中文路径乱码，工单 ascii-project-name/01、desktop-platform-suffix/01）；
    粘贴题面（无 topic_id）：AI 起英文短名为目录名（name_topic_english，工单
    ascii-project-name/02），同样带平台后缀。

    verdict（工单 generate-conflict-guard/01）：桌面模式 = desktop_topic_dir_verdict
    三分支 new / clean / exists（路由按 verdict：new 直接生成、clean 清理
    残渣后生成、exists 400 拒绝——不再静默换名攒目录）；手动模式 = "manual"
    （目录判定归 generate_project 非空检查兜底，路由不为手动模式清理）。
    """
    if not _desktop_output_requested(payload):
        return Path(_require_str(payload, "output_dir")), "manual"
    problem_text = _require_str(payload, "problem_text")
    topic_id = _optional_str(payload, "topic_id")
    platform = _require_str(payload, "platform")
    if platform not in KNOWN_PLATFORMS:
        # 未知平台（用户可控输入，工单 C6 先例）：桌面模式在拼后缀前就校验，
        # 400 中文带已注册平台清单——不落到 with_platform_suffix 的未登记
        # ValueError（500 大声失败只留给真 bug 漂移）。
        raise UnknownPlatformError(
            f"未知平台 {platform!r}，已注册的平台：{', '.join(KNOWN_PLATFORMS)}"
        )
    if topic_id:
        config = _require_config(context)
        entry = resolve_number(
            topic_library_dir(config.module_library_dir), topic_id
        )
        title = topic_dir_title(entry.key, entry.problem_text)
    else:
        title = _llm(context).name_topic_english(problem_text)
    # 平台后缀（工单 desktop-platform-suffix/01）：同题双平台目录自动分流
    # （Auto_Car_STM32 / Auto_Car_MSPM0）；后缀在裁决前拼——desktop_topic_dir_verdict
    # 看到的已是带后缀的标题，护栏 / 锁键 / 失败清理 / explorer 聚焦全部自动
    # 跟随目录名，无需另改。未知平台由 with_platform_suffix 大声失败。
    return desktop_topic_dir_verdict(
        context.desktop_dir(),
        with_platform_suffix(title, platform),
    )




def create_app(ctx: AppContext | None = None) -> FastAPI:
    context = ctx or AppContext()
    app = FastAPI(title="电赛工程生成器")

    # 生成流程页（单页应用）
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    # 前端纯函数模块（工单 frontend-es-modules/01）：/js/fx/*.js 静态直挂，
    # 无构建步骤（浏览器原生 ESM）；STATIC_DIR/js 下有 package.json {"type":"module"}
    # 供 node 端测试按 ESM import
    app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")

    # 进程存活探针（工单 newcomer-onboarding/02）：启动器用它判定「端口 8000
    # 上是不是本应用」——是本应用则直接开浏览器（已在运行），是别的东西则
    # 提示端口被占。故意不依赖任何配置（未配 key 也 200），否则用户第一次
    # 启动前探测就会失败。
    @app.get("/api/health")
    def health() -> dict:
        return {"app": "contest-generator", "version": __version__, "ok": True}

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
        # 工具链可用性（工单 autocompile-loop/01）：前端据此决定"一键编译修复"
        # 按钮置灰 / 生成后自动编译；探测是瞬间操作（is_file / which），未配置
        # 时按默认值探测
        uv4 = find_uv4(dirs.uv4_path)
        make = find_make(dirs.gmake_path)
        return {
            "api_configured": config is not None,
            "toolchains": {
                PLATFORM_STM32: uv4 is not None,
                PLATFORM_MSPM0: make is not None,
            },
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

    # 环境体检静态聚合（工单 env-check-center/01）：只读探测、零 LLM 调用；
    # 体检语义 = 报问题不炸端点（模块库/目录异常落入字段描述，绝不 500）
    @app.get("/api/env/status")
    @_map_errors
    def env_status() -> dict:
        config = _current_config(context)
        dirs = config or AppConfig()  # 未配置时按默认路径探测
        masters = (
            list_masters(dirs.masters_dir) if dirs.masters_dir.is_dir() else []
        )
        master_platforms = {meta.platform for meta in masters}
        uv4 = find_uv4(dirs.uv4_path)
        make = find_make(dirs.gmake_path)
        lib_exists = dirs.module_library_dir.is_dir()
        lib_count = 0
        lib_error = None
        if not lib_exists:
            lib_error = "模块库目录不存在"
        else:
            try:
                lib_count = len(list_modules(dirs.module_library_dir))
            except Exception as e:  # 畸形 manifest 等：报问题，不打断体检
                lib_error = f"模块库加载失败：{e}"
        desktop = context.desktop_dir()
        return {
            "api_configured": config is not None,
            "llm": (
                {
                    "base_url": config.base_url,
                    "model": config.model,
                    "local_llm_base_url": config.local_llm_base_url or "",
                }
                if config is not None
                else None
            ),
            "toolchains": {
                PLATFORM_STM32: {
                    "found": uv4 is not None,
                    "path": str(uv4) if uv4 is not None else None,
                    "override": bool(config.uv4_path if config else ""),
                },
                PLATFORM_MSPM0: {
                    "found": make is not None,
                    "path": str(make) if make is not None else None,
                    "override": bool(config.gmake_path if config else ""),
                },
            },
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
            "module_library": {
                "dir": str(dirs.module_library_dir),
                "exists": lib_exists,
                "count": lib_count,
                "error": lib_error,
            },
            "masters_dir": {
                "dir": str(dirs.masters_dir),
                "exists": dirs.masters_dir.is_dir(),
            },
            "output_dir": {
                "dir": str(desktop),
                "exists": desktop.is_dir(),
                "writable": os.access(desktop, os.W_OK) if desktop.is_dir() else False,
            },
        }

    # 板定义（板图坐标/能力集单源，工单 pin-board-config/01）：前端板图
    # （工单 03 SVG）与生成门禁（工单 02 绑定校验）同吃这份数据
    @app.get("/api/boards")
    @_map_errors
    def boards(platform: str = ""):
        """板定义清单；platform 可选过滤（未知平台 = 空列表，不报错）。"""
        loaded = load_boards(BOARDS_DIR)
        if platform:
            loaded = [b for b in loaded if b.platform == platform]
        return {"boards": [b.to_dict() for b in loaded]}

    @app.get("/api/wiring")
    @_map_errors
    def wiring_read(output_dir: str = "") -> dict:
        """接线快照读取（只读端点，工单 task-wiring-diagram/04 + 05）：输出
        目录 → {platform, board, rows}。

        board = 快照内嵌板定义（与 /api/boards 同平台板一致：引脚坐标/丝印/
        固定资源）；rows = 接线行（与 README「引脚接线表」同源——生成时同一
        推导函数落盘）。快照缺失 → **旧工程兜底**（read_wiring_snapshot_legacy：
        README「引脚接线表」同源解析 + context platform + 静态板定义——恢复
        生成时同一数据，不做猜测；同脚冗余行按模块库声明集判定来源后仅删
        「实例行与既有行同脚」的重复（工单 07，模块库缺失 → 保守不去重））；
        兜底也失败（无 README / 无 context / 坏
        JSON / 未知平台）→ 空载荷（platform 空串、board None、rows []）——
        前端走退化路径，绝不 500（条目级容错与既有任务数据读取风格一致）。
        """
        from .wiring import read_wiring_snapshot, read_wiring_snapshot_legacy

        empty = {"platform": "", "board": None, "rows": []}
        if not output_dir:
            return empty
        snapshot = read_wiring_snapshot(output_dir)
        if snapshot is None:
            config = _current_config(context)
            snapshot = read_wiring_snapshot_legacy(
                output_dir,
                config.module_library_dir if config is not None else None,
            )
        if snapshot is None:
            return empty
        platform = snapshot.get("platform", "")
        rows = snapshot.get("rows")
        return {
            "platform": platform if isinstance(platform, str) else "",
            "board": snapshot.get("board"),
            "rows": rows if isinstance(rows, list) else [],
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
        """上传赛题文件（PDF / .docx / .txt / .md / 图片）→ 抽取文本。

        PDF 且视觉通道可用（工单 vision-eyes/02 + vision-deepseek-native/01）：
        文本后追加嵌入示意图描述（[示意图N：…]）；视觉 key 留空 + DeepSeek
        官方端点 = 复用主 key（零额外配置）；未配置 = 纯文本（现状逐字节一致）；
        视觉失败静默降级。图片（工单 vision-eyes/03）：直接走视觉描述。"""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(upload.filename or "").suffix
        ) as tmp:
            tmp.write(await upload.read())
            tmp_path = Path(tmp.name)
        try:
            config = _require_config(context)
            vision_base_url, vision_api_key, vision_model = _resolve_vision(config)
            suffix = tmp_path.suffix.lower()
            if suffix in IMAGE_FILE_SUFFIXES:
                collector = create_llm_observation_collector("vision-describe")
                result = extract_image(
                    tmp_path,
                    vision_base_url=vision_base_url,
                    vision_api_key=vision_api_key,
                    vision_model=vision_model,
                    observation_collector=collector,
                    detail_qa=config.vision_detail_qa,
                )
                context.recent_llm_workflows.add_completed(collector)
                # 上传原图（工单 upload-image-preview/01）：视觉描述之外回传原图
                # data URL，前端直接显示；读失败 → None（仅文字，不阻塞）
                return {"text": result, "image_data_url": image_data_url(tmp_path)}
            if suffix == ".pdf":
                collector = create_llm_observation_collector("vision-describe")
                result = extract_pdf_with_image_notes(
                    tmp_path,
                    vision_base_url=vision_base_url,
                    vision_api_key=vision_api_key,
                    vision_model=vision_model,
                    observation_collector=collector,
                    detail_qa=config.vision_detail_qa,
                )
                context.recent_llm_workflows.add_completed(collector)
                # 上传页图（工单 upload-pdf-pages/01）：与题库 /pages 同款渲染，
                # 前端页图展示；渲染失败降级为空 → 前端只显示文字，不阻塞
                pages, total_pages = render_pdf_pages(tmp_path)
                return {"text": result, "pages": pages, "total_pages": total_pages}
            return {"text": extract_file(tmp_path)}
        finally:
            tmp_path.unlink(missing_ok=True)

    class _CacheWriterEmitter(SseEmitter):
        """转发 SseEmitter 四方法；done 时先写推荐缓存（尽力而为）再转发。

        路由装配细节（工单 llm-cost-control/02）：done 载荷在域内
        （run_recommendation）组装，路由经此包装拦截写缓存——写失败不阻塞
        终态发射（旁路），question / error 终态原样透传。
        """

        def __init__(
            self, inner: SseEmitter, write_cb: Callable[[dict], None]
        ) -> None:
            self._inner = inner
            self._write_cb = write_cb

        def progress(self, event: ProgressEvent) -> None:
            self._inner.progress(event)

        def done(self, data: dict) -> None:
            try:
                self._write_cb(data)
            except Exception:
                pass  # 旁路：缓存写失败不阻塞 done 终态
            self._inner.done(data)

        def question(self, data: dict) -> None:
            self._inner.question(data)

        def error(self, data: dict) -> None:
            self._inner.error(data)

    def _load_recommend_safely(path: Path) -> dict | None:
        """读推荐缓存：损坏 / 形状非法 → None（旁路走真实推荐，不报错退出）。

        Web 是交互工具（对照 CLI 回归脚本的"缺失即报错"）：坏缓存静默重算。
        """
        try:
            return load_recommend(path)
        except ValueError:
            return None

    def _emit_cached_recommend(
        emit: SseEmitter, cached: Mapping[str, Any], warns: Sequence[str]
    ) -> None:
        """推荐缓存命中的终态发射（工单 llm-cost-control/02，路由装配细节）。

        独立于路由函数体（结构防回退：/api/recommend 路由体内不出现
        emit.done / emit.question——本函数是运行器旁路的专用发射点）：
        cache_hit 进度事件 + done 终态（载荷 = 缓存 done 逐字）。
        """
        emit.progress(ProgressEvent(type=EVENT_CACHE_HIT, warns=tuple(warns)))
        emit.done(cached["done"])

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
        # 赛题答疑 Q&A（工单 qa-material/01）：赛事组对题面的澄清问答，推荐时
        # 作题面后独立段注入（权威材料）；空 = 旧行为逐字节。参与缓存指纹
        # （qa_sha256，Q&A 变化缓存失效走真实推荐）
        qa_text = _optional_str(payload, "qa_text")
        # 澄清历史（工单 01 推荐先澄清后收敛）：[{question, answer}] 字符串对，
        # 缺省空 = 向后兼容；回答随请求体走、不拼进题面（题面保持原文——收敛
        # 判定的"两轮一致"对照依赖逐句编号，题面被污染会让判定失真）
        clarifications = _require_clarifications(payload)
        # 完整上下文已在装配点（resolve_topic_context）一次备好：两级注入的
        # 清单段 / 全文回读 / 模块库摘要行都由它携带，路由只消费（key 空 =
        # 未识别到历史赛题，no-topic 形同样携带全模块摘要）；手动选参考资料
        # 的准入 / 全文直读同样在装配点完成。platform（工单 01）= 锚定命中
        # 按生成平台过滤（手动选不过滤），缺省 / 空 = 现状不过滤
        budget = RetryBudget()
        collector = create_llm_observation_collector("recommend")
        topic = _assemble_topic_context(
            context,
            topic_id,
            problem_text,
            _llm(context, budget, collector),
            reference_ids,
            platform,
        )
        # 推荐缓存（工单 llm-cost-control/02）：同题重跑命中直出 done 载荷，
        # 省最贵的推荐段 LLM 调用；缓存目录 = 配置目录同级 cache/（与 CLI
        # generate_check 缓存格式逐字兼容，双客户端对偶）
        config = _require_config(context)
        cache_enabled = config.recommend_cache_enabled
        ckey = cache_key(topic_id, problem_text)
        cpath = recommend_cache_path(ckey, cache_dir=context.config_path.parent / "cache")
        clarify_maps = [{"question": q, "answer": a} for q, a in clarifications]
        # 收敛轮数上限（工单 recommend-speedup-v2/01）：设置项透传，缺省 4
        max_rounds = config.recommend_max_rounds
        # 模块库指纹（工单 recommend-cache-fingerprint/01）：模型看到的摘要行
        # 排序 hash——库变（模块增删/简介/能力/多实例标注）缓存失效走真实推荐；
        # 装配点已产出 manifest_summaries，写缓存与校验同源一次计算两用
        lib_fp = library_fingerprint(topic.manifest_summaries)
        # 按需视觉问答（工单 recommend-vision-qa/02）：视觉已配置（effective
        # key 非空——含主 key 复用）且条目带原 PDF → 注入供给回调（澄清 /
        # 补问的图内问题自动消化：渲染题面页 + 视觉模型作答）；否则 None =
        # 01 的未注入路径，行为逐字节不变。闭包在 run 外构造一次（多次 run
        # 复用）；视觉调用成本进独立观测器（finally 一并结算）
        vision_qa: Callable[[str], str | None] | None = None
        vision_qa_collector = None
        if topic.figure_pdf is not None:
            vision_base_url, vision_api_key, vision_model = _resolve_vision(config)
            if vision_configured(vision_api_key):
                vision_qa_collector = create_llm_observation_collector("vision-qa")

                def vision_qa(question: str) -> str | None:
                    """图内问题 → 条目 PDF 渲染 + 视觉模型针对性作答（02 工单）。"""
                    assert topic.figure_pdf is not None
                    return answer_figure_question(
                        topic.figure_pdf,
                        topic.problem_text,
                        question,
                        vision_base_url=vision_base_url,
                        vision_api_key=vision_api_key,
                        vision_model=vision_model,
                        observation_collector=vision_qa_collector,
                    )

        def _write_cache(done_data: dict) -> None:
            """真实推荐 done 载荷落缓存（尽力而为：写失败静默旁路）。"""
            if not cache_enabled:
                return
            cache_recommend(
                cpath,
                done_data,
                topic_key=ckey,
                problem_text=problem_text,
                platform=platform or "",
                reference_ids=reference_ids,
                clarify_hist=clarify_maps,
                qa_text=qa_text or "",
                library_fingerprint=lib_fp,
            )

        def run(emit: SseEmitter) -> None:
            # 两阶段编排归 selection.run_recommendation（澄清先行 → 收敛 →
            # done 载荷组装），路由只转调——终态一律由域函数发出，路由不分支；
            # run 抛错由运行器补发 error 终态（终态保证归运行器）
            try:
                if cache_enabled:
                    cached = _load_recommend_safely(cpath)
                    if cached is not None:
                        ok, _ = validate_recommend(
                            cached,
                            topic_key=ckey,
                            problem_text=problem_text,
                            platform=platform or "",
                            qa_text=qa_text or "",
                            library_fingerprint=lib_fp,
                        )
                        if ok:
                            warns = parameter_warnings(
                                cached,
                                reference_ids=reference_ids,
                                clarify_hist=clarify_maps,
                            )
                            _emit_cached_recommend(emit, cached, warns)
                            return
                with bind_llm_telemetry(collector, emit.progress):
                    run_recommendation(
                        topic,
                        _llm(context, budget, collector),
                        clarifications,
                        emit=_CacheWriterEmitter(emit, _write_cache),
                        max_rounds=max_rounds,
                        platform=platform or "",
                        qa_material=qa_text or "",
                        vision_qa=vision_qa,
                    )
            finally:
                context.recent_llm_workflows.add_completed(collector)
                if vision_qa_collector is not None:
                    context.recent_llm_workflows.add_completed(vision_qa_collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/topic/preread")
    @_map_errors
    def topic_preread(payload: dict) -> dict:
        """赛题预读（生成页步骤 2）：AI 预读题面给一句话总览 + 决策点提醒
        列表（每条 = 影响步骤 + 提醒文本 + 题面原文引用）。

        让用户在选平台 / 推荐模块之前对「题面已经锁死了什么」有数——用户
        自己会通读题面，这里不复述功能，只提炼限定/约束/指定类事实；只做
        展示、不进任何下游流程（推荐 / 骨架有自己的题面处理，这里不注入）。
        结构化 JSON 单次 LLM 调用 + 机械校验（topic_preread 域），失败走
        错误映射表（LLM 服务失败 → 502）。"""
        problem_text = _require_str(payload, "problem_text")
        return _llm(context).preread_topic(problem_text).to_dict()

    @app.post("/api/selection/expand")
    @_map_errors
    def expand_selection(payload: dict) -> dict:
        """展开依赖 + 平台可用性检查：用户增删选择后重跑一次即可。

        多实例模块附带 default_instances（工单 instance-config-defaults/01）：
        展示端实例卡首次呈现即预填平台默认（AI 未猜 / 依赖带入的多实例模块
        也有「第一版」可改）——default_instance_plan 单源，与「不配置 = 单
        默认实例」的生成结果等价；前端键已存在（AI 猜过 / 用户配过）不覆盖。
        """
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        resolved = resolve_selection(_library_dir(context), platform, slugs)
        modules = [m.to_dict() for m in resolved.manifests]
        defaults = default_instance_plan(platform)
        if defaults:
            for manifest, module in zip(resolved.manifests, modules):
                if manifest.multi_instance is not None:
                    module["default_instances"] = [inst.to_dict() for inst in defaults]
        return {
            "modules": modules,
            "warnings": [
                {"slug": w.slug, "kind": w.kind, "message": w.message}
                for w in resolved.warnings
            ],
        }

    @app.post("/api/skeleton")
    @_map_errors
    def skeleton(payload: dict) -> dict:
        """main.c 骨架 / 自检冒烟：LLM 出稿 + 静态自检（不存在的调用改写为注释占位）。

        main_mode：`skeleton`（缺省，现行为）| `smoke`（自检冒烟——只自检不写
        赛题逻辑，OLED 为主 / debug_uart 串口为辅，两者都没选 → 400）。
        历史赛题入口：选中某题时题面用库内全文（长 PDF 题面全文只在选了该赛
        题时进上下文）；骨架阶段经 reference_ids 注入参考实现草稿（锚定 ∪
        手动全文，ADR 0006 修订），不自动并入模块（模块选择由用户 / 推荐
        链路决定）。main_mode 分支 + 冒烟守卫 + 分派在 skeleton.run_skeleton
        （对照 run_recommendation / run_fix_round 先例），本路由只取参 +
        装配输入 + 返回。"""
        problem_text = _require_str(payload, "problem_text")
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        topic_id = _optional_str(payload, "topic_id")
        reference_ids = _require_str_list(payload, "reference_ids")
        # 多实例清单（工单 module-multi-instance/04）：形状判决归 selection.parse_instances
        # （SelectionError → 400 中文），缺省 / 空 = 现行为（单默认实例）。
        # known_slugs = 选中 ∪ 依赖展开（工单 instance-config-deps/01）：依赖带入的
        # 多实例模块（led_beep → led）也允许配实例清单。
        instances = parse_instances(
            payload.get("instances"),
            known_slugs=_instance_known_slugs(_library_dir(context), slugs),
        )
        # main_mode 非法值 / 冒烟守卫的 400 归 run_skeleton（SkeletonError → 400
        # 中文），路由只做缺省回填（未提供 = skeleton）
        main_mode = (
            _optional_str(payload, "main_mode") if "main_mode" in payload else "skeleton"
        )
        budget = RetryBudget()
        collector = create_llm_observation_collector("skeleton")
        try:
            topic = _assemble_topic_context(
                context,
                topic_id,
                problem_text,
                _llm(context, budget, collector),
                reference_ids=reference_ids,
                platform=platform,
                slugs=slugs,
            )
            resolved = resolve_selection(
                _library_dir(context), platform, slugs, instances=instances
            )
            # 题型框架（工单 topic-framework/04）：与参考全文同域装配（域函数
            # build_topic_framework_info——锚定 ∪ 手动、平台匹配、首个 topic_type
            # 非空条目）。冒烟模式不注入（不写题逻辑，见 run_skeleton 分派）。
            # main_mode 分支 + 冒烟守卫 + 分派归 skeleton.run_skeleton（对照
            # run_recommendation / run_fix_round 先例），路由只装配输入 + 返回
            ref_root = reference_library_dir(_require_config(context).module_library_dir)
            framework, framework_entry = (
                build_topic_framework_info(ref_root, topic, platform)
                if main_mode == "skeleton"
                else (None, None)
            )
            result = run_skeleton(
                llm=_llm(context, budget, collector),
                problem_text=topic.problem_text,
                manifests=resolved.manifests,
                slugs=slugs,
                platform=platform,
                library_dir=_library_dir(context),
                master_project_dir=master_project_dir(
                    _require_config(context).masters_dir, platform
                ),
                instances=instances,
                reference_fulltexts=build_reference_fulltexts(topic),
                main_mode=main_mode,
                topic_framework=framework if main_mode == "skeleton" else None,
            )
            result["topic_framework"] = _topic_framework_response(framework, framework_entry)
            return result
        finally:
            context.recent_llm_workflows.add_completed(collector)

    @app.post("/api/pick-directory")
    @_map_errors
    def pick_directory() -> dict:
        """弹原生文件夹选择对话框（本地工具专用），返回 {"path": 绝对路径}。

        浏览器拿不到所选文件夹的绝对路径（见 _tkinter_pick_directory），
        由服务端弹系统对话框；用户取消时 path 为 null，前端不覆盖输入框。
        """
        return {"path": context.pick_directory()}

    @app.post("/api/bindings/validate")
    @_map_errors
    def bindings_validate(payload: dict) -> dict:
        """引脚绑定校验（工单 pin-verdict-seam/01）：跑 resolve_bindings 返回
        结构化结果，供前端离开引脚配置步骤、进入生成前调用——跨角色冲突
        （mspm0 槽位 / GPIO 同端口 / PWM 通道对 / 成对实例）在生成前暴露，
        不再走到 generate 才撞 400。

        契约：{platform, slugs, bindings} → {ok:true} 或 {ok:false, error}；
        error 与 generate 400 文案逐字一致（同一 resolve_bindings，不复制
        文案）。空 bindings / 全默认 = ok:true（旧行为不误拦）。module 集
        与板定义解析与 generate 同源（resolve_selection + board_for_platform），
        保证校验与生成吃同一份 manifests / board。
        """
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        bindings = payload.get("bindings") or None  # 形状判决归域层（400 中文）
        resolved = resolve_selection(_library_dir(context), platform, slugs)
        board = board_for_platform(platform)
        try:
            resolve_bindings(resolved.manifests, platform, board, bindings)
        except PinBindingError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True}

    @app.post("/api/bindings/auto")
    @_map_errors
    def bindings_auto(payload: dict) -> dict:
        """自动配置（工单 pin-auto-assign/01）：一键解冲突——确定性算法把真
        冲突角色（能力 / UART 成对 / mspm0 槽位互斥 / 类型级实例约束）重新
        分配到不冲突引脚，合法共享保留并标注；只动冲突角色，用户合法绑定
        不动。校验与 validate / generate 同源（resolve_bindings + 同一份
        manifests / board）。

        契约：{platform, slugs, bindings} → {ok:true, bindings(增量),
        fixed(调整说明), shared(保留共享标注)} 或 {ok:false, error}。
        """
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        bindings = payload.get("bindings") or None  # 形状判决归域层（400 中文）
        resolved = resolve_selection(_library_dir(context), platform, slugs)
        board = board_for_platform(platform)
        try:
            result = auto_assign_bindings(
                resolved.manifests, platform, board, bindings
            )
        except PinBindingError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "bindings": result.bindings,
            "fixed": list(result.fixed),
            "shared": [dict(item) for item in result.shared],
        }

    @app.post("/api/generate")
    @_map_errors
    def generate(payload: dict) -> dict:
        """完整生成：选模块 → 母版 → 生成 → 摘要（流程在 generate_project）。

        历史赛题入口：topic_id 给定时装配点（resolve_topic_context）校验编号
        查库——查无此条明确报错（不猜测编造）；模块集 = 用户选择原样展开
        （工单 module-universalization/07 起不再自动并入"题专用模块"）。

        bindings（工单 pin-board-config/02）：可选板级引脚绑定载荷
        {"<slug>.<role_id>": "<PIN>"}，缺省 = 全默认（向后兼容，旧请求行为
        逐字节不变）。形状校验归域层 resolve_bindings（PinBindingError → 400
        中文），路由只透传。"""
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        main_c = _require_str(payload, "main_c")
        output_dir, output_verdict = _resolve_generation_output_dir(context, payload)
        topic_id = _optional_str(payload, "topic_id")
        # 覆盖确认（工单 generate-overwrite/01）：严格 `is True`——非布尔（如
        # 字符串 "true"）视为缺省（护栏宁严勿松），旧请求行为逐字节不变。
        overwrite = payload.get("overwrite") is True
        bindings = payload.get("bindings") or None  # 形状判决归域层（400 中文）
        # 多实例清单（工单 module-multi-instance/04）：形状判决归 selection.parse_instances
        # （SelectionError → 400 中文），缺省 / 空 = 现行为（单默认实例）。
        # known_slugs = 选中 ∪ 依赖展开（工单 instance-config-deps/01）：依赖带入的
        # 多实例模块（led_beep → led）也允许配实例清单。
        instances = parse_instances(
            payload.get("instances"),
            known_slugs=_instance_known_slugs(_library_dir(context), slugs),
        )
        # Python 副产物模板选择（工单 k230-multi-template/02）：形状判决归
        # generator.resolve_python_template_choices（PythonArtifactError →
        # 400 中文），缺省 = 全默认模板（旧行为逐字节不变）。
        python_templates = payload.get("python_templates")
        score_points = parse_score_points(payload.get("score_points"))
        config = _require_config(context)
        if topic_id:
            # 显式编号路径不需要 AI 提取（题面 / 关联素材已装配）；查无此条大声报错
            _assemble_topic_context(context, topic_id, "", None)
        # 上下文清单字段（工单 revise-deepen/01）：随生成请求回传并落盘——
        # 题面 / Q&A / 功能需求清单（推荐产物摘要）/ 参考条目 / 工具版本；
        # 缺省 = 清单内容缺省（旧行为逐字节）。requirements 必须是数组，
        # 非法形状 400 中文（其余字段 _optional_str 已有类型闸）。
        problem_text = _optional_str(payload, "problem_text")
        qa_text = _optional_str(payload, "qa_text")
        requirements = payload.get("requirements")
        if requirements is not None and not isinstance(requirements, list):
            raise ContextError("requirements 必须是数组（推荐产物摘要）")
        references = _require_str_list(payload, "references")
        # CCS 三件套探测（工单 mspm0-build-makefiles/01）：config 覆盖 > 自动
        # 扫描；mspm0 生成自动产出 Debug/makefile 集（探测不到 = 生成照常 +
        # build_hint 提示，不阻断）。stm32 不探。
        ccs_tools = None
        if platform == PLATFORM_MSPM0:
            ccs_tools = find_ccs_tools(
                config.ccs_sdk_dir,
                config.ccs_compiler_dir,
                config.ccs_sysconfig_cli,
            )
        # 设计报告草稿 LLM 输出层（工单 report-draft-demo/03）：生成前一次
        # 调用产出 {rationale, workflow} → 拼接 report_draft_text 传
        # generate_project（报告渲染层 = 纯确定性，LLM 文本是入参——骨架先
        # 例）。题面空 = 不调（无题面无可论证，走缺省路径不写报告文件）；
        # LLMError（网络 / 解析 / 预算）→ 占位文本进报告（报告仍写、LLM 节
        # 中文占位，spec 失败策略），生成主链不阻断；LLM telemetry 照常采集
        # （_retry_parse 观测 + recent_llm_workflows 收尾）。
        report_draft_text = ""
        if problem_text:
            collector = create_llm_observation_collector("generate-report-draft")
            try:
                llm = _llm(context, RetryBudget(), collector)
                selected_manifests = resolve_selection(
                    _library_dir(context), platform, slugs
                ).manifests
                from .manifest import build_manifest_summaries

                rationale, workflow = llm.generate_report_draft(
                    problem_text=problem_text,
                    requirements=requirements or (),
                    manifest_summaries=build_manifest_summaries(selected_manifests),
                    pin_summary=_pin_summary_text(platform, selected_manifests),
                )
                report_draft_text = f"{rationale}\n\n{workflow}"
            except LLMError:
                report_draft_text = f"{PLACEHOLDER}\n\n{PLACEHOLDER}"
            finally:
                context.recent_llm_workflows.add_completed(collector)
        # 同键互斥 + 目录裁决（工单 generate-conflict-guard/01）：锁键 = 桌面
        # 用题名 / 手动用输出目录；已存在完整同名工程 → 400（不静默改名攒
        # 目录，不覆盖）；半成品残渣 → 清理后生成；失败 → 桌面模式不留半成品。
        lock_key = (
            f"desktop:{output_dir.name}"
            if _desktop_output_requested(payload)
            else f"manual:{output_dir}"
        )
        with _generation_guard(context, lock_key):
            if output_verdict == "exists":
                if not overwrite:
                    raise GenerationConflictError(
                        f"桌面上已有同名工程「{output_dir.name}」：为避免覆盖你的"
                        "已有工程，请先删除该目录或修改题名后再生成（不会自动"
                        "改名或覆盖）。同一赛题换平台再生成时，会自动使用带平台"
                        "后缀的新目录（如 Auto_Car_MSPM0），不会误删旧工程"
                    )
                # 覆盖通道（工单 generate-overwrite/01）：用户确认后先快照
                # （旧工程整体改名为 <name>.bak，单份策略）再生成——备份失败
                # （OSError → 400 文件操作失败）时原名目录未动，数据不丢。
                backup_project_dir(output_dir)
            if output_verdict == "clean":
                shutil.rmtree(output_dir, ignore_errors=True)
            try:
                summary = generate_project(
                    platform=platform,
                    slugs=slugs,
                    main_c_content=main_c,
                    output_dir=output_dir,
                    module_library_dir=config.module_library_dir,
                    masters_dir=config.masters_dir,
                    ccs_tools=ccs_tools,
                    bindings=bindings,
                    instances=instances,
                    python_templates=python_templates,
                    score_points=score_points,
                    problem_text=problem_text,
                    topic_id=topic_id,
                    qa_text=qa_text,
                    requirements=requirements,
                    references=references,
                    tool_version=__version__,
                    report_draft_text=report_draft_text,
                )
            except GenerationConflictError:
                raise
            except Exception:
                if _desktop_output_requested(payload):
                    shutil.rmtree(output_dir, ignore_errors=True)
                raise
        if _desktop_output_requested(payload):
            # 生成成功 → 自动打开资源管理器聚焦工程目录（用户「要」）
            _open_in_explorer(output_dir)
        # 最近生成记录（工单 recent-jobs/01）：生成成功自动落盘
        # （status=generated；编译状态由前端随后上报更新）。写失败不阻断
        # 生成主流程——本地工具，记录坏掉不能挡住刚生成的工程。
        try:
            record_recent(
                recent_file(context.config_path),
                output_dir=str(summary.output_dir),
                platform=platform,
                slugs=slugs,
                topic_id=topic_id,
            )
        except OSError:
            pass
        return _generation_result(summary)

    @app.get("/api/recent")
    @_map_errors
    def recent_list() -> list[dict]:
        """最近生成记录（工单 recent-jobs/01）：新 → 旧，cap 20；
        未配置 = 空列表（没配置自然没有生成记录）。"""
        config = _current_config(context)
        if config is None:
            return []
        return load_recent(recent_file(context.config_path))

    @app.post("/api/recent/status")
    @_map_errors
    def recent_status(payload: dict) -> dict:
        """编译状态上报（工单 recent-jobs/01）：前端每次编译完成调一次；
        状态白名单 / 400 中文由 RecentStatusError 经 errors.py 统一映射
        （路由薄壳，不重复校验）；目录无记录 → 忽略不建（手动模式直接编译
        未生成的路径不产生脏记录）。"""
        output_dir = _require_str(payload, "output_dir")
        status = _require_str(payload, "status")
        config = _current_config(context)
        if config is None:
            return {"ok": True, "updated": False}
        updated = update_recent_status(recent_file(context.config_path), output_dir, status)
        return {"ok": True, "updated": updated is not None}

    @app.delete("/api/recent/{entry_id}")
    @_map_errors
    def recent_delete(entry_id: str) -> dict:
        """删除一条最近生成记录（清错记）；不存在 → 404 中文。"""
        config = _current_config(context)
        if config is None or not delete_recent(recent_file(context.config_path), entry_id):
            raise HTTPException(404, "最近生成记录不存在")
        return {"ok": True}

    # ------------------------------------------------------------------
    # 修订与深化 · 上下文加载（工单 revise-deepen/01）：给一个输出目录，
    # 返回可修订的上下文——有上下文清单（.contest_context.json）直读；无
    # 清单（历史工程）自动反推平台 / 模块 / 绑定 / main.c。域判决在
    # context_manifest（反推尽力而为），路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/revise/context")
    @_map_errors
    def revise_context(payload: dict) -> dict:
        """加载生成上下文（同步端点）：{output_dir} → 可修订的上下文。

        有清单直读（read_context_fields，缺字段补空兼容）；无清单自动反推
        （infer_context：工程配置文件认平台、modules/<slug>/ 认模块、写侧
        逆运算回读绑定、main.c 现读）。两者都过形状校验（validate_context_fields：
        平台词表 / slugs 库内存在性 / 绑定键形状，非法 400 中文——库外模块
        校验失败 = 前端手动勾选兜底入口）。

        返回 {"source": "manifest" | "inferred", "context": {...字段...},
        "missing": [反推不了需用户补的字段名]}。目录不存在 / 平台无法识别 /
        清单损坏 → ContextError 400 中文。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise ContextError(f"输出目录不存在：{output_dir}")
        config = _require_config(context)
        module_library_dir = config.module_library_dir

        source, fields = _load_revision_context(output_dir, module_library_dir)
        return {
            "source": source,
            "context": fields,
            "missing": missing_fields_for(fields),
        }

    # ------------------------------------------------------------------
    # 修订与深化 · 影响分析（工单 revise-deepen/02）：粘贴新 Q&A → AI 逐条
    # 影响结论 + 建议模块集 → 确定性 diff + 平台警告重算。域判决在 impact.py
    # （对照 run_recommendation 先例），路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/revise/analyze")
    @_map_errors
    def revise_analyze(payload: dict) -> StreamingResponse:
        """修订影响分析（SSE 流）：影响分析中 → diff 就绪 → done（影响产物）。

        请求体契约：output_dir（必填，生成结果目录）；new_qa_text（必填，
        新增赛题答疑 Q&A 原文）；qa_count（可选整数，Q&A 条数——给定时影响
        结论必须逐条覆盖，漏判大声失败）；slugs / platform（可选覆盖——用户
        手动调整模块集或平台后分析）。服务端重新加载上下文（清单直读 / 无清单
        反推，与 /api/revise/context 同源），覆盖后过形状校验（400 中文）。

        事件序列：impact_analyzing（LLM 分钟级）→ diff_ready（diff + 平台
        警告就绪）→ done（{"impacts": [...], "suggested_slugs": [...],
        "diff": {"added/removed/unchanged"}, "warnings": [...],
        "platform": ...}）或 error（中文信息）→ 流结束。HTTP 200 起流，失败
        以流内 error 事件收尾（sse 运行器终态保证）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise ContextError(f"输出目录不存在：{output_dir}")
        new_qa_text = _require_str(payload, "new_qa_text")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        # 服务端重新加载上下文（前端不直传——清单 / 反推单址，防陈旧回传）；
        # 可选覆盖：用户手动调整模块集 / 平台后分析
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if payload.get("slugs") is not None:
            fields["slugs"] = _require_str_list(payload, "slugs")
            validate_context_fields(fields, module_library_dir)
        if payload.get("platform") is not None:
            fields["platform"] = _require_str(payload, "platform")
            validate_context_fields(fields, module_library_dir)
        # 题面覆盖（历史目录补题面流程）：前端补的题面是上下文的一部分——
        # 覆盖后分析 / 执行 / 深化都能用（缺题面 400 之前）
        if payload.get("problem_text") is not None:
            fields["problem_text"] = _require_str(payload, "problem_text")
        if not fields.get("problem_text"):
            raise ContextError("缺少赛题原文——请先补题面（修订分析需要题面证据）")
        qa_count = payload.get("qa_count")
        if qa_count is not None and (
            not isinstance(qa_count, int)
            or isinstance(qa_count, bool)
            or qa_count < 1
        ):
            raise ContextError("qa_count 必须是正整数（新 Q&A 条数）")

        budget = RetryBudget()
        collector = create_llm_observation_collector("revise-analyze")
        summaries = _module_library_summaries(module_library_dir)
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_impact_analysis(
                        llm=llm,
                        problem_text=fields["problem_text"],
                        requirements=fields.get("requirements") or (),
                        current_slugs=fields["slugs"],
                        manifest_summaries=summaries,
                        new_qa_text=new_qa_text,
                        platform=fields["platform"],
                        library_dir=module_library_dir,
                        emit=emit,
                        qa_count=qa_count,
                    )
                emit.done(result)
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    # ------------------------------------------------------------------
    # 修订与深化 · 修订执行（工单 revise-deepen/03）：确认载荷 → 备份 →
    # 覆盖式重生成 → diff 记录；回滚 = 恢复备份。域判决在 revision.py
    # （对照 run_recommendation 先例），路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/revise/apply")
    @_map_errors
    def revise_apply(payload: dict) -> StreamingResponse:
        """修订执行（SSE 流）：备份 → （模块集变化时）重生成 → 完成（diff 记录）。

        请求体契约：output_dir（必填，生成结果目录）；confirmed_slugs（必填，
        用户确认后的模块集——影响分析的 diff 展示后由用户确认）；new_qa_text
        （必填，本次修订的新 Q&A 原文，进 diff 记录与上下文清单）；impacts
        （可选，影响结论记录，随 diff 记录留痕）。

        事件序列：revision_backup（整树备份）→ revision_generating（重生成
        中，仅模块集变化时）→ done（{"backup_id", "regenerated", "diff":
        {"added", "removed"}, "impacts", "qa_text", "output_dir",
        "generated_at"}）或 error（中文信息）→ 流结束。失败路径：备份成功但
        重生成失败 → error 终态（备份保留 = 目录保持可回滚）。HTTP 200 起流，
        失败以流内 error 事件收尾（sse 运行器终态保证）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise ContextError(f"输出目录不存在：{output_dir}")
        confirmed_slugs = _require_str_list(payload, "confirmed_slugs")
        new_qa_text = _require_str(payload, "new_qa_text")
        # 影响结论记录（可选，分析阶段产物——随 diff 记录留痕，不参与判决）
        impacts = payload.get("impacts")
        if impacts is not None and not isinstance(impacts, list):
            raise ContextError("impacts 必须是数组（影响结论记录）")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        # 确认载荷的形状校验（平台 / 绑定 / 多实例 / 副产物模板）——库外模块
        # 在 validate 拦（400 中文，前端手动勾选兜底）
        validate_context_fields(fields, module_library_dir)
        # 题面覆盖（历史目录补题面流程）：补的题面进重生成骨架上下文
        if payload.get("problem_text") is not None:
            fields["problem_text"] = _require_str(payload, "problem_text")
        bindings = fields.get("bindings") or None
        instances = parse_instances(
            fields.get("instances") or None,
            known_slugs=_instance_known_slugs(module_library_dir, confirmed_slugs),
        )
        python_templates = fields.get("python_templates") or None
        # CCS 三件套探测（与 /api/generate 同款）：mspm0 修订重生成要复用
        # 构建脚本全链路（spec「复用既有生成管线…构建脚本」）；stm32 不探。
        ccs_tools = None
        if fields["platform"] == PLATFORM_MSPM0:
            ccs_tools = find_ccs_tools(
                config.ccs_sdk_dir,
                config.ccs_compiler_dir,
                config.ccs_sysconfig_cli,
            )
        budget = RetryBudget()
        collector = create_llm_observation_collector("revise-apply")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_revision(
                        llm=llm,
                        problem_text=fields.get("problem_text", ""),
                        qa_text=fields.get("qa_text", ""),
                        requirements=fields.get("requirements") or (),
                        references=fields.get("references") or (),
                        current_slugs=fields["slugs"],
                        confirmed_slugs=confirmed_slugs,
                        new_qa_text=new_qa_text,
                        platform=fields["platform"],
                        library_dir=module_library_dir,
                        masters_dir=config.masters_dir,
                        output_dir=output_dir,
                        backup_root=revise_backup_root(
                            config.masters_dir.parent
                        ),
                        bindings=bindings,
                        instances=instances,
                        python_templates=python_templates,
                        emit=emit,
                        tool_version=__version__,
                        impacts=impacts or (),
                        topic_id=fields.get("topic_id", ""),
                        ccs_tools=ccs_tools,
                    )
                emit.done(result)
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/revise/rollback")
    @_map_errors
    def revise_rollback(payload: dict) -> dict:
        """修订回滚（同步端点）：把 <backup_root>/<backup_id>/ 备份内容整体
        恢复回输出目录（回滚 = 目录内容恢复为备份内容，修订残留全清）。

        backup_id 必须是安全目录名（is_unsafe_path 拒绝对 `..` / 绝对路径）；
        备份或输出目录不存在 → RevisionError（400 中文）。返回恢复的文件
        相对路径列表。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        backup_id = _require_str(payload, "backup_id")
        restored = restore_revision(
            revise_backup_root(_require_config(context).masters_dir.parent),
            backup_id,
            output_dir,
        )
        return {"restored": list(restored)}

    # ------------------------------------------------------------------
    # 修订与深化 · 深化（工单 revise-deepen/04）：AI 按功能需求填 main.c
    # TODO + 编译验证闭环（绿 = 已验证；无工具链 = 大声降级）。域判决在
    # deepen.py（对照 run_recommendation 先例），路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/revise/deepen")
    @_map_errors
    def revise_deepen(payload: dict) -> StreamingResponse:
        """深化（SSE 流）：填 TODO → 备份 → 写盘 → 编译验证闭环 → 完成。

        请求体契约：output_dir（必填，生成结果目录）；main_c（可选，深化前
        的 main.c 内容——缺省 = 服务端现读磁盘，手工编辑天然保留）。

        事件序列：deepening_start（LLM 填 TODO）→ compile_start（编译中）→
        fix_start（失败修复中，仅首轮编译失败时）→ verify_result → done
        （{"status": verified | unverified | failed, "backup_id", "compile",
        "message"}）或 error（中文信息）→ 流结束。无工具链 = 大声降级
        （status = unverified，结果保留）；修一轮仍红 = failed。HTTP 200 起流，
        失败以流内 error 事件收尾（sse 运行器终态保证）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise ContextError(f"输出目录不存在：{output_dir}")
        main_c = _optional_str(payload, "main_c")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        # 题面覆盖（历史目录补题面流程）：补的题面进深化 prompt
        if payload.get("problem_text") is not None:
            fields["problem_text"] = _require_str(payload, "problem_text")
        if not main_c:
            main_c = read_project_main_c(output_dir)
        if not main_c:
            raise DeepenError("工程 main.c 为空，无法深化（请先生成或修订工程）")
        platform = fields["platform"]
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        budget = RetryBudget()
        collector = create_llm_observation_collector("revise-deepen")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_deepen(
                        llm=llm,
                        problem_text=fields.get("problem_text", ""),
                        qa_text=fields.get("qa_text", ""),
                        requirements=fields.get("requirements") or (),
                        manifests=resolved.manifests,
                        platform=platform,
                        library_dir=module_library_dir,
                        master_project_dir=master_project_dir(
                            config.masters_dir, platform
                        ),
                        main_c=main_c,
                        output_dir=output_dir,
                        work_root=config.masters_dir.parent,
                        emit=emit,
                        uv4_override=config.uv4_path,
                        make_override=config.gmake_path,
                        module_slugs=fields["slugs"],
                    )
                emit.done(result)
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    # ------------------------------------------------------------------
    # 任务推进 · 拆解（工单 task-progress/01）：AI 把题面 + 功能需求 +
    # 评分点 + 模块接口 + 当前 main.c 拆成有序任务清单 → 落盘
    # .contest_tasks.json。域判决在 task_progress.py（照 run_deepen 先例），
    # 路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/plan")
    @_map_errors
    def tasks_plan(payload: dict) -> StreamingResponse:
        """任务拆解（SSE 流）：拆解中 → done（任务清单）或 error（中文信息）。

        请求体契约：output_dir（必填，生成结果目录）；problem_text（可选覆盖，
        历史目录补题面流程）；score_points（可选，当前会话推荐结果——历史
        目录缺省空，任务不带分值标注）；force（可选布尔，重新拆解——旧清单
        备档 .contest_tasks.json.bak 后覆盖）。

        事件序列：task_planning（LLM 拆解中，分钟级）→ done（{"version",
        "generated_at", "tasks": [...]}，任务状态全部 pending）或 error
        （中文信息）→ 流结束。HTTP 200 起流，失败以流内 error 事件收尾。

        缺上下文（无题面 / 无功能需求清单 / main.c 空）→ 400 中文提示
        （照 /api/revise/deepen 判断口径）；清单已存在且未带 force →
        TaskError（前端引导用「重新拆解」，防误覆盖进度）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if payload.get("problem_text") is not None:
            fields["problem_text"] = _require_str(payload, "problem_text")
        if not fields.get("problem_text"):
            raise TaskError(
                "缺少赛题原文——请先补题面（任务拆解需要题面证据，历史工程"
                "请粘贴题面后重试）"
            )
        if not fields.get("requirements"):
            raise TaskError(
                "缺少功能需求清单——任务拆解依赖功能需求层"
                "（请用含上下文清单的新工程，或重新生成 / 修订）"
            )
        platform = fields["platform"]
        # main.c 现读（与深化同口径：手工编辑保留，拆解基于当前内容）
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        if not main_c:
            raise TaskError("工程 main.c 为空，无法拆解任务")
        # 评分点：当前会话推荐结果直传；历史目录 / 未选 = 空（拆解仍可进行）
        score_points = parse_score_points(payload.get("score_points"))
        force = payload.get("force") is True
        # 防误覆盖守卫：清单已存在且未 force → 同步 400（起流前明确失败，
        # 前端据 deatil 引导「重新拆解」；域编排内部另有背兜）
        check_plan_replaceable(output_dir, force)
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        budget = RetryBudget()
        collector = create_llm_observation_collector("tasks-plan")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_task_planning(
                        llm=llm,
                        problem_text=fields["problem_text"],
                        qa_text=fields.get("qa_text", ""),
                        requirements=fields.get("requirements") or (),
                        score_points=[p.to_dict() for p in score_points],
                        manifests=resolved.manifests,
                        platform=platform,
                        library_dir=module_library_dir,
                        master_project_dir=master_project_dir(
                            config.masters_dir, platform
                        ),
                        main_c=main_c,
                        output_dir=output_dir,
                        emit=emit,
                        force=force,
                    )
                emit.done(result)
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    # ------------------------------------------------------------------
    # 任务推进 · 单任务执行（工单 task-progress/02）：一次 LLM 调用实现
    # 一个任务 → 备份 → 写盘 → 编译验证闭环（与深化共用尾段）→ 状态回填。
    # 域判决在 task_progress.run_task（照 run_deepen 先例），路由薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/execute")
    @_map_errors
    def tasks_execute(payload: dict) -> StreamingResponse:
        """单任务执行（SSE 流）：执行中 → 编译验证 → done（任务 + 状态）或
        error（中文信息）。

        请求体契约：output_dir（必填，生成结果目录）；task_id（必填，任务
        id）；note（可选字符串，补充框——用户对本次执行的附加说明，透传
        LLM）；feedback（可选字符串，上板实测反馈——用户烧录运行后描述的
        实际现象，透传 LLM 按反馈修复轮；非字符串 400）；problem_text
        （可选覆盖，历史目录补题面流程）。

        事件序列：task_executing（LLM 实现中，分钟级）→ compile_start →
        fix_start（仅首轮编译失败）→ verify_result → task_reporting（AI
        总结本步「做了什么 + 接下来你要做什么」，秒级）→ done（{"task",
        "status", "backup_id", "compile", "main_diff", "message"}，与深化
        尾段同形状 + task 为清单回填后的最新形状）或 error（中文信息）→
        流结束。HTTP 200 起流，失败以流内 error 事件收尾。

        缺上下文（无题面 / 无需求清单）→ 400 中文提示；清单未拆解 / 任务
        不存在 → 400（TaskError）；工具链缺失 = 大声降级（status =
        unverified，结果保留）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        task_id = _require_str(payload, "task_id")
        note = _optional_str(payload, "note") or ""
        feedback = _optional_str(payload, "feedback") or ""
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if payload.get("problem_text") is not None:
            fields["problem_text"] = _require_str(payload, "problem_text")
        if not fields.get("problem_text"):
            raise TaskError("缺少赛题原文——请先补题面（任务执行需要题面证据）")
        platform = fields["platform"]
        # main.c 现读（手工编辑保留，与拆解 / 深化同口径）
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        # 工程级全局结论（工单 idea-suite/01）：全局商量采纳的结论 → 注入
        # 本步执行 prompt（空串 = 未采纳，调用形状不变）
        global_note = _read_global_note(output_dir)
        budget = RetryBudget()
        collector = create_llm_observation_collector("tasks-execute")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            _running_task_execs.add(task_id)
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_task(
                        llm=llm,
                        task_id=task_id,
                        note=note,
                        problem_text=fields["problem_text"],
                        qa_text=fields.get("qa_text", ""),
                        manifests=resolved.manifests,
                        platform=platform,
                        library_dir=module_library_dir,
                        master_project_dir=master_project_dir(
                            config.masters_dir, platform
                        ),
                        main_c=main_c,
                        output_dir=output_dir,
                        work_root=config.masters_dir.parent,
                        emit=emit,
                        uv4_override=config.uv4_path,
                        make_override=config.gmake_path,
                        module_slugs=fields["slugs"],
                        feedback=feedback,
                        global_note=global_note,
                    )
                emit.done(result)
            finally:
                _running_task_execs.discard(task_id)
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    # ------------------------------------------------------------------
    # 任务推进 · 清单读取（工单 task-progress/02）：回滚后 / 重新打开时前端
    # 重读磁盘任务清单（执行 / 改标落盘 = 磁盘态即真相，内存态只作展示缓存）。
    # 域判决在 task_progress.read_task_plan，路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/plan-read")
    @_map_errors
    def tasks_plan_read(payload: dict) -> dict:
        """任务清单读取（同步端点）：{output_dir} → {plan}（缺 = None）。

        返回 {"plan": {"version", "generated_at", "tasks": [...]} | None}——
        未拆解 = None（前端显示占位）；坏 JSON = TaskError 400 中文。
        """
        from .task_progress import read_task_plan

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        plan = read_task_plan(output_dir)
        return {"plan": plan.to_dict() if plan is not None else None}

    # ------------------------------------------------------------------
    # 参数速调（工单 param-tune/01）：识别 main.c 可调数值参数 + 确定性改值
    # + 编译验证。与任务清单独立（main.c 存在即可用）。识别走 LLM；改值零
    # LLM（锚定位替换）→ 备份 → 写盘 → 编译验证闭环（共用 verify 尾段）。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/params/scan")
    @_map_errors
    def tasks_params_scan(payload: dict) -> StreamingResponse:
        """参数识别（SSE 流）：→ param_result → done（{params}）或
        error（中文信息）。

        请求体契约：output_dir（必填，生成结果目录）。

        事件序列：param_scanning（LLM 识别中，分钟级）→ param_result →
        done（{"params": [ParamItem...]}，与参数表文件同形状）或 error →
        流结束。HTTP 200 起流，失败以流内 error 事件收尾。

        缺上下文（无题面）→ 400 中文提示；LLM 识别结果域判决失败 →
        流内 error（重试由前端引导）；不要求已拆解任务清单。
        """
        from .params import run_param_scan
        from .skeleton import build_skeleton_interfaces

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        platform = fields["platform"]
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        if not main_c.strip():
            raise TaskError("工程 main.c 为空，无法识别参数（请先生成或修订工程）")
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        interfaces = build_skeleton_interfaces(
            resolved.manifests,
            platform,
            module_library_dir,
            master_project_dir(config.masters_dir, platform),
        )
        budget = RetryBudget()
        collector = create_llm_observation_collector("tasks-params-scan")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    param_list = run_param_scan(
                        llm=llm,
                        main_c=main_c,
                        module_interfaces=interfaces,
                        output_dir=output_dir,
                        emit=emit,
                    )
                emit.progress(ProgressEvent(type=EVENT_PARAM_RESULT))
                emit.done({"params": [item.to_dict() for item in param_list.params]})
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/tasks/params/apply")
    @_map_errors
    def tasks_params_apply(payload: dict) -> StreamingResponse:
        """参数改值（SSE 流）：→ compile_start → fix_start → verify_result →
        done（{status, backup_id, compile, main_diff, message}）或 error。

        请求体契约：output_dir（必填）；name（必填，参数名——从参数表
        .contest_params.json 里找）；value（必填，新值文本，非空 + ≤64 字符）。

        事件序列：param_applying（改值 + 编译验证开始）→ compile_start →
        fix_start（仅首轮编译失败）→ verify_result → done（与任务执行尾段
        同形状）或 error → 流结束。**改值零 LLM**；首轮编译失败的自动修复
        轮可能调 LLM（verify_compile_tail 既有闭环）。

        参数表不存在 / name 不在表内 / 新值非法 → 400；锚已失效（main.c
        被改动）→ 流内 error 中文提示「请重新识别参数」。
        """
        from .params import (
            find_param,
            read_params,
            run_param_apply,
            validate_param_value,
        )

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        name = _require_str(payload, "name")
        value = validate_param_value(_optional_str(payload, "value") or "")
        param_list = read_params(output_dir)
        param = find_param(param_list, name)
        if param is None:
            raise TaskError(f"参数表里没有参数 {name}——请先「识别 main.c 参数」")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        if not main_c.strip():
            raise TaskError("工程 main.c 为空，无法应用参数（请先生成或修订工程）")
        budget = RetryBudget()
        collector = create_llm_observation_collector("tasks-params-apply")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_param_apply(
                        llm=llm,
                        param=param,
                        new_value=value,
                        main_c=main_c,
                        output_dir=output_dir,
                        work_root=config.masters_dir.parent,
                        platform=fields["platform"],
                        module_slugs=fields["slugs"],
                        uv4_override=config.uv4_path,
                        make_override=config.gmake_path,
                        emit=emit,
                    )
                emit.done(result)
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/tasks/params/read")
    @_map_errors
    def tasks_params_read(payload: dict) -> dict:
        """参数表读取（同步端点）：{output_dir} → {params: [..+valid], scanned}。

        逐参数读当前 main.c 重验 anchor（锚失效 = main.c 被任务执行 / 手工
        编辑改动，前端禁用该行并提示「请重新识别」）；valid = anchor 逐字节
        仍在 main.c 中（old_value 也在锚内）。无文件 = 空列表不 400；
        scanned = 磁盘是否存在参数表（无表 = 未识别过，前端「尚未识别」与
        「已识别但无参数」两态区分——空表不落盘，spec 用户故事 6）。
        """
        from .params import load_params_file, params_with_valid, read_params

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        param_list = read_params(output_dir)
        scanned = load_params_file(output_dir) is not None
        main_c = read_project_main_c(output_dir) or ""
        return {"params": params_with_valid(param_list, main_c), "scanned": scanned}

    # ------------------------------------------------------------------
    # 参数速调咨询（工单 params-chat-ai/01）：不绑任务卡的多轮诊断对话——学生
    # 不知道现象该调哪个参数时来问；每轮把当前已识别参数清单（逐条 valid）+
    # 题面 + 任务清单现状喂给 LLM（discuss_params，调参顾问），回复可点名
    # 参数（前端渲染成可点击定位 chip）。历史落盘 .contest_params_chat.json
    # （与全局商量 .contest_idea_chat.json 独立），不做采纳为全局结论。
    # ------------------------------------------------------------------

    @app.post("/api/params/chat/read")
    @_map_errors
    def params_chat_read(payload: dict) -> dict:
        """读参数速调咨询记录（同步端点）：{output_dir} → {chat}。

        无文件 = 空聊天（未聊过，不 400——照 idea chat read 先例）；坏 JSON /
        非对象 → TaskError 400 中文；chat 形状与全局商量同（note 恒空——
        调参咨询不做采纳为全局结论）。
        """
        from .idea_chat import PARAMS_CHAT_FILENAME, read_idea_chat

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        return {"chat": read_idea_chat(output_dir, PARAMS_CHAT_FILENAME).to_dict()}

    @app.post("/api/params/chat/send")
    @_map_errors
    def params_chat_send(payload: dict) -> dict:
        """参数速调咨询一轮（同步端点）：{output_dir, history} → {reply, chat}。

        request 契约与 /api/tasks/idea/chat/send 同构：history 单通道（旧 → 新，
        末条 user = 本轮消息）。服务端读 .contest_params.json（当前已识别参数
        清单，逐条重验 valid）+ 题面 + 任务清单现状 → LLM 调参顾问 → 成功才
        追加 user+assistant 两条落盘（.contest_params_chat.json）→ {reply, chat}
        （原子轮次：LLM 失败 → 502 且不落半轮）。缺题面 → 400。

        与全局商量不同：参数表未识别 = 空清单照常可聊（AI 如实告知先识别），
        不 400——调参咨询的价值正在「还没识别时引导识别」。
        """
        from .idea_chat import (
            PARAMS_CHAT_FILENAME,
            append_chat_message,
            read_idea_chat,
            write_idea_chat,
        )
        from .params import params_with_valid, read_params
        from .task_progress import read_task_plan

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        history = _parse_chat_history(payload)
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if not fields.get("problem_text"):
            raise TaskError("缺少赛题原文——请先补题面（调参诊断需要题面证据）")
        param_list = read_params(output_dir)
        main_c = read_project_main_c(output_dir) or ""
        params_out = params_with_valid(param_list, main_c)
        plan = read_task_plan(output_dir)
        chat = read_idea_chat(output_dir, PARAMS_CHAT_FILENAME)

        collector = create_llm_observation_collector("params-chat")
        try:
            llm = _llm(context, RetryBudget(), collector)
            discussion = llm.discuss_params(
                problem_text=fields["problem_text"],
                params=params_out,
                plan=plan.to_dict() if plan is not None else None,
                history=history,
            )
        finally:
            context.recent_llm_workflows.add_completed(collector)
        # 原子轮次：LLM 成功才追加两条消息落盘（失败 = 502，历史不动）
        chat = append_chat_message(chat, "user", history[-1][1])
        chat = append_chat_message(chat, "assistant", discussion.reply)
        write_idea_chat(output_dir, chat, PARAMS_CHAT_FILENAME)
        return {"reply": discussion.reply, "chat": chat.to_dict()}

    # ------------------------------------------------------------------
    # 任务推进 · 人工改标（工单 task-progress/03）：跳过 / 重做 / 上板
    # 确认改标（verified）。转移表在 task_progress.ALLOWED_STATUS_TRANSITIONS
    # 单源，路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/status")
    @_map_errors
    def tasks_status(payload: dict) -> dict:
        """任务状态改标（同步端点）：{output_dir, task_id, status} → 落盘。

        status ∈ pending（重做 / 执行中断恢复）/ verified（上板人工确认）/
        skipped（跳过）。非法转移 → TaskError 400 中文（消息带允许目标清单）；
        正在执行中（_running_task_execs 占用）拒绝人工改标——防止「僵尸恢复」
        误伤真实运行的任务；清单未拆解 / 任务不存在 → TaskError。

        返回 {"task": 改标后的任务 to_dict, "plan": 全量清单 to_dict}——
        前端据此单卡重渲染 + 进度刷新。
        """
        from .task_progress import apply_task_status

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        task_id = _require_str(payload, "task_id")
        if task_id in _running_task_execs:
            raise TaskError(
                f"任务 {task_id} 正在执行中，无法恢复——请等待完成"
                "（或重启服务终止旧执行）"
            )
        status = _require_str(payload, "status")
        return apply_task_status(output_dir, task_id, status)

    # ------------------------------------------------------------------
    # 任务推进 · 轮次回滚（工单 task-feedback/03）：撤销到指定轮次之前。
    # 域判决在 task_progress.rollback_task_iteration（复用修订回滚
    # restore_revision），路由只做薄壳装配（seq 正整数校验）。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/rollback-iteration")
    @_map_errors
    def tasks_rollback_iteration(payload: dict) -> dict:
        """轮次回滚（同步端点）：{output_dir, task_id, seq} → 撤销该轮。

        seq = 迭代记录轮次序号（1 起正整数，非正整数 → TaskError 400）。
        撤销语义：恢复该轮执行前的整树快照（备份在写盘前）+ 状态恢复为该轮
        之前的终态（无前轮 → pending）；迭代历史保留。轮次 / 任务 / 清单
        不存在 → TaskError 400；备份损坏 → RevisionError 400。

        返回 {"task", "plan", "restored"}——前端单卡重渲染 + 进度刷新。
        """
        from .task_progress import rollback_task_iteration

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        task_id = _require_str(payload, "task_id")
        seq = payload.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
            raise TaskError("seq 必须是正整数（轮次序号）")
        config = _require_config(context)
        return rollback_task_iteration(
            output_dir,
            task_id,
            seq,
            revise_backup_root(config.masters_dir.parent),
        )

    # ------------------------------------------------------------------
    # 任务推进 · 对话结论采纳（工单 task-chat/01）：用户在某条 AI 回复上点
    # 「采纳这条结论」→ 写入任务 dialog_note（落盘，刷新不丢）；下次执行
    # 时作为独立 prompt 段注入。text 空串 = 清除采纳。域判决在
    # task_progress.set_task_dialog_note，路由只做薄壳装配。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/dialog-adopt")
    @_map_errors
    def tasks_dialog_adopt(payload: dict) -> dict:
        """对话结论采纳（同步端点）：{output_dir, task_id, text} → 落盘。

        text 非字符串 → TaskError 400 中文（bool 也是 int 之外先判）；
        text 空串 = 清除采纳（取消）。输出目录不存在 / 未拆解 / 任务不存在
        → TaskError 400。

        返回 {"task": 采纳后任务 to_dict, "plan": 全量清单 to_dict}——
        前端据此单卡重渲染 + 徽标刷新。
        """
        from .task_progress import set_task_dialog_note

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        task_id = _require_str(payload, "task_id")
        text = payload.get("text")
        if not isinstance(text, str):
            raise TaskError("text 必须是字符串（空串 = 清除采纳）")
        return set_task_dialog_note(output_dir, task_id, text)

    # ------------------------------------------------------------------
    # 任务推进 · 任务商量（工单 task-chat/02）：每卡「和 AI 商量」的一轮
    # 讨论——用户发表想法/纠正 → LLM 任务顾问回应（可行性/影响/建议）。
    # 同步端点（照 /api/buy/discuss 先例：校验 → 装配 → 一轮调用 →
    # add_completed 收尾）；对话结论采纳走 /api/tasks/dialog-adopt。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/discuss")
    @_map_errors
    def tasks_discuss(payload: dict) -> dict:
        """任务商量（同步端点）：{output_dir, task_id, history} → {reply}。

        请求契约：output_dir（必填，生成结果目录）；task_id（必填，任务 id）；
        history（必填非空数组，旧 → 新，[{role: user|assistant, content}]，
        前端逐轮积累——最后一条 user = 本轮消息，service 侧 prompt 以
        history[-1] 为「你的最新消息」，与 /api/buy/discuss 单通道同款，无
        独立 message 参数（评审整改：double channel 会丢消息——非前端客户端
        若分离 message 与 history，最新消息即错位）。
        服务端读 .contest_context.json（题面 / Q&A / 需求 / 模块集）+ 现读
        main.c + 任务清单（任务须存在）→ LLM 任务顾问 → {reply}。

        校验失败 → TaskError 400 中文；LLM 失败 → 502（error_to_http 表）。
        缺题面 / 工程 main.c 为空 → 400（讨论需要题面与实现现状；评审判定
        合理防御保留）。telemetry 照常采集——同步端点无 SSE 通道，观测进
        recent_llm_workflows 记录。
        """
        from .skeleton import build_skeleton_interfaces
        from .task_progress import find_task, read_task_plan

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        task_id = _require_str(payload, "task_id")
        raw_history = payload.get("history")
        if not isinstance(raw_history, list) or not raw_history:
            raise TaskError(
                "history 必须是数组（旧 → 新的讨论记录，最后一条 = 本轮消息）"
            )
        history: list[tuple[str, str]] = []
        for index, item in enumerate(raw_history, 1):
            if not isinstance(item, dict):
                raise TaskError(f"history 第 {index} 条必须是对象")
            role = item.get("role")
            if role not in ("user", "assistant"):
                raise TaskError(
                    f"history 第 {index} 条 role 必须是 user 或 assistant"
                )
            content = item.get("content")
            if not isinstance(content, str):
                raise TaskError(f"history 第 {index} 条 content 必须是字符串")
            history.append((role, content))
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if not fields.get("problem_text"):
            raise TaskError("缺少赛题原文——请先补题面（任务商量需要题面证据）")
        # main.c 现读（手工编辑保留，与拆解 / 深化同口径）
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        if not main_c.strip():
            raise TaskError("工程 main.c 为空，无法就实现现状商量")
        platform = fields["platform"]
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        interfaces = build_skeleton_interfaces(
            resolved.manifests,
            platform,
            module_library_dir,
            master_project_dir(config.masters_dir, platform),
        )
        plan = read_task_plan(output_dir)
        if plan is None:
            raise TaskError("该目录尚未拆解任务——请先点「拆解任务」生成任务清单")
        task = find_task(plan, task_id)

        collector = create_llm_observation_collector("tasks-discuss")
        try:
            llm = _llm(context, RetryBudget(), collector)
            discussion = llm.discuss_task(
                task=task.to_dict(),
                problem_text=fields["problem_text"],
                qa_text=fields.get("qa_text", ""),
                requirements=fields.get("requirements", []) or [],
                module_interfaces=interfaces,
                main_c=main_c,
                history=history,
            )
        finally:
            context.recent_llm_workflows.add_completed(collector)
        return {"reply": discussion.reply}

    # ------------------------------------------------------------------
    # 全局工程级商量（工单 idea-suite/01）：不绑任务卡的多轮对话——针对
    # 整个工程的连续追问（架构 / 策略 / 方案选型），历史落盘
    # .contest_idea_chat.json（与任务卡商量会话级不落盘不同）；回复可
    # 「转成任务 / 转成修正」（走 idea 落地通道）/「采纳为全局结论」
    # （note 落盘，后续每步任务执行与直接修正注入 prompt）。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/idea/chat/read")
    @_map_errors
    def tasks_idea_chat_read(payload: dict) -> dict:
        """读全局商量记录（同步端点）：{output_dir} → {chat}。

        无文件 = 空聊天（未聊过，不 400——与 plan-read 同先例）；坏 JSON /
        非对象 → TaskError 400 中文。chat = {version, generated_at,
        messages: [{role, content, at}...], note}（note = 已采纳的全局结论，
        空串 = 未采纳）。
        """
        from .idea_chat import read_idea_chat

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        return {"chat": read_idea_chat(output_dir).to_dict()}

    @app.post("/api/tasks/idea/chat/send")
    @_map_errors
    def tasks_idea_chat_send(payload: dict) -> dict:
        """全局商量一轮（同步端点）：{output_dir, history} → {reply, chat}。

        request 契约与 /api/tasks/discuss 同构：history（必填非空数组，旧 → 新，
        [{role: user|assistant, content}]，最后一条 user = 本轮消息——单通道，
        无独立 message 参数，防错位设计）。服务端读 .contest_context.json
        （题面 / Q&A / 需求 / 模块集）+ 现读 main.c + 任务清单（未拆解允许——
        全局商量不依赖清单）+ 已采纳全局结论 → LLM 工程总顾问 → 成功才追加
        user+assistant 两条消息落盘 → {reply, chat}（原子轮次：LLM 失败 →
        502 且不落半轮，刷新后历史仍是上一轮——回复为空无意义，本轮消息也
        不追加）。

        缺题面 → 400（商量需要题面证据）。
        """
        from .idea_chat import append_chat_message, read_idea_chat, write_idea_chat
        from .skeleton import build_skeleton_interfaces
        from .task_progress import read_task_plan

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        history = _parse_chat_history(payload)
        # 末条强制 user（评审整改）+：误传 assistant 结尾会把 AI 文本错标为
        # user 落盘——全局聊天持久化落盘，比 task-discuss（会话级）后果重。
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if not fields.get("problem_text"):
            raise TaskError("缺少赛题原文——请先补题面（全局商量需要题面证据）")
        platform = fields["platform"]
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        interfaces = build_skeleton_interfaces(
            resolved.manifests,
            platform,
            module_library_dir,
            master_project_dir(config.masters_dir, platform),
        )
        plan = read_task_plan(output_dir)
        score_points = parse_score_points(payload.get("score_points"))
        chat = read_idea_chat(output_dir)

        collector = create_llm_observation_collector("tasks-idea-chat")
        try:
            llm = _llm(context, RetryBudget(), collector)
            discussion = llm.discuss_global_idea(
                problem_text=fields["problem_text"],
                qa_text=fields.get("qa_text", ""),
                requirements=fields.get("requirements", []) or [],
                score_points=[p.to_dict() for p in score_points],
                module_interfaces=interfaces,
                main_c=main_c,
                plan=plan.to_dict() if plan is not None else None,
                global_note=chat.note,
                history=history,
            )
        finally:
            context.recent_llm_workflows.add_completed(collector)
        # 原子轮次：LLM 成功才追加两条消息落盘（失败 = 502，历史不动）
        chat = append_chat_message(chat, "user", history[-1][1])
        chat = append_chat_message(chat, "assistant", discussion.reply)
        write_idea_chat(output_dir, chat)
        return {"reply": discussion.reply, "chat": chat.to_dict()}

    @app.post("/api/tasks/idea/chat/adopt")
    @_map_errors
    def tasks_idea_chat_adopt(payload: dict) -> dict:
        """采纳 / 清除全局结论（同步端点）：{output_dir, text} → {chat}。

        text 为字符串（空串 = 清除采纳——采纳错了可撤销）；写入 note 落盘
        （最新覆盖），后续每步任务执行与直接修正注入 prompt。text 非字符串
        由本路由校验（照 dialog-adopt 先例）；返回 {chat}。
        """
        from .idea_chat import read_idea_chat, set_chat_note, write_idea_chat

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        text = payload.get("text")
        if not isinstance(text, str):
            raise TaskError("text 必须是字符串（空串 = 清除采纳）")
        chat = read_idea_chat(output_dir)
        updated = set_chat_note(chat, text)
        write_idea_chat(output_dir, updated)
        return {"chat": updated.to_dict()}

    # ------------------------------------------------------------------
    # 灵活修正（工单 idea-fix/01）：全局「新想法 / 问题」入口——分析（分类）
    # / 插入任务卡 / 直接修正（复用编译验证尾段与备份回滚入口）/ 标记重做。
    # 域判决在 task_progress（insert_task_from_idea / set_tasks_needs_redo /
    # run_direct_fix），路由薄壳装配（照 tasks 系列先例）。
    # ------------------------------------------------------------------

    @app.post("/api/tasks/idea/analyze")
    @_map_errors
    def tasks_idea_analyze(payload: dict) -> StreamingResponse:
        """新想法分析（SSE 流）：分析中 → 分析完成 → done（分类结果）。

        请求体契约：output_dir（必填，生成结果目录）；idea（必填非空字符串，
        用户的新想法 / 发现的问题）；problem_text（可选覆盖，历史目录补题面
        流程）。

        事件序列：idea_analyzing（LLM 分析中，分钟级）→ idea_result（分析
        完成）→ done（{"analysis": {"kind", "reply", "new_task",
        "fix_summary", "affected_task_ids"}}）或 error（中文信息）→ 流结束。
        HTTP 200 起流，失败以流内 error 事件收尾。

        缺题面 → 400 中文（分析需要题面证据）；LLM 失败 → 流内 error（错误
        映射 502）。清单未拆解允许（analysis.new_task 无依赖语境；AI 仍可
        分类讨论 / 新功能）。
        """
        from .task_progress import read_task_plan
        from .skeleton import build_skeleton_interfaces

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        idea = _require_str(payload, "idea")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if payload.get("problem_text") is not None:
            fields["problem_text"] = _require_str(payload, "problem_text")
        if not fields.get("problem_text"):
            raise TaskError("缺少赛题原文——请先补题面（想法分析需要题面证据）")
        platform = fields["platform"]
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        interfaces = build_skeleton_interfaces(
            resolved.manifests,
            platform,
            module_library_dir,
            master_project_dir(config.masters_dir, platform),
        )
        plan = read_task_plan(output_dir)
        score_points = parse_score_points(payload.get("score_points"))
        budget = RetryBudget()
        collector = create_llm_observation_collector("tasks-idea-analyze")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                emit.progress(ProgressEvent(type=EVENT_IDEA_ANALYZING))
                with bind_llm_telemetry(collector, emit.progress):
                    analysis = llm.analyze_idea(
                        idea=idea,
                        problem_text=fields["problem_text"],
                        qa_text=fields.get("qa_text", ""),
                        requirements=fields.get("requirements") or (),
                        score_points=[p.to_dict() for p in score_points],
                        module_interfaces=interfaces,
                        main_c=main_c,
                        plan=plan.to_dict() if plan is not None else None,
                    )
                emit.progress(ProgressEvent(type=EVENT_IDEA_RESULT))
                emit.done({"analysis": analysis.to_dict()})
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/tasks/idea/insert")
    @_map_errors
    def tasks_idea_insert(payload: dict) -> dict:
        """思路转化为任务卡（同步端点）：{output_dir, new_task} → {plan}。

        new_task = 想法分析给出的建议任务（title/description/score_refs/
        depends_on/verify，须为对象）。插入 = 清单末尾追加 t{n+1}（依赖用
        1 起序号引用既有任务）；旧清单先备档 .contest_tasks.json.bak（与
        重新拆解同入口）再覆盖；清单未拆解也允许（建新清单只含该任务）。
        校验失败 → TaskError 400 中文；返回 {"plan": 落盘后全量清单}。
        """
        from .task_progress import (
            TaskPlan,
            insert_task_from_idea,
            read_task_plan,
        )

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        raw_new_task = payload.get("new_task")
        if not isinstance(raw_new_task, dict):
            raise TaskError("new_task 必须是对象（title/description/score_refs/"
                            "depends_on/verify）")
        plan = read_task_plan(output_dir)
        # 先纯函数校验与构造（失败 = 不动盘面——校验失败决不吞掉现有清单，
        # 对照 run_task_planning 的「拆解成功后才备份」顺序：backup 是 move 语义）
        updated = insert_task_from_idea(plan or TaskPlan(), raw_new_task)
        backup_task_plan(output_dir)  # 校验通过后旧清单备档（无旧清单 = False）
        write_task_plan(output_dir, updated)
        return {"plan": updated.to_dict()}

    @app.post("/api/tasks/idea/edit")
    @_map_errors
    def tasks_idea_edit(payload: dict) -> dict:
        """任务卡微编辑（同步端点，工单 idea-suite/03）：{output_dir, task_id,
        fields} → {task, plan}。

        fields = {title?, description?, depends_on?, verify?, score_refs?}——缺
        省字段 = 保留原值；depends_on = 1 起序号数组（→ t{n} 引用既有任务；
        序号基于当前数组顺序——调序后序号随之变化，编辑时以卡面序号为准）。
        校验失败 → 400 中文且清单不动（先纯函数后备份再写——backup 是 move
        语义；insert 同款顺序）；status / note / dialog_note / needs_redo /
        iterations 一律保留（微编辑不动进度）。
        """
        from .task_progress import (
            backup_task_plan,
            find_task,
            read_task_plan,
            update_task_fields,
            write_task_plan,
        )

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        task_id = _require_str(payload, "task_id")
        raw_fields = payload.get("fields")
        if not isinstance(raw_fields, dict):
            raise TaskError(
                "fields 必须是对象（title/description/depends_on/verify/score_refs）"
            )
        plan = read_task_plan(output_dir)
        find_task(plan, task_id)  # 先查存在（未拆解 / 任务不存在 → 400 中文）
        updated = update_task_fields(
            plan,
            task_id,
            title=raw_fields.get("title"),
            description=raw_fields.get("description"),
            depends_on=raw_fields.get("depends_on"),
            verify=raw_fields.get("verify"),
            score_refs=raw_fields.get("score_refs"),
        )
        backup_task_plan(output_dir)  # 校验通过后才备档（失败 = 盘面不动）
        write_task_plan(output_dir, updated)
        return {
            "task": next(t.to_dict() for t in updated.tasks if t.id == task_id),
            "plan": updated.to_dict(),
        }

    @app.post("/api/tasks/idea/move")
    @_map_errors
    def tasks_idea_move(payload: dict) -> dict:
        """任务卡调序（同步端点，工单 idea-suite/03）：{output_dir, task_id,
        direction} → {plan}。up / down 相邻换位（数组顺序 = 展示顺序）；id 不变
        （依赖引用与 needs_redo 不受影响）；首卡 up / 末卡 down / direction 词
        表外 → 400 中文；先校验后备份再写（backup 是 move 语义）。
        """
        from .task_progress import (
            backup_task_plan,
            move_task,
            read_task_plan,
            write_task_plan,
        )

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        task_id = _require_str(payload, "task_id")
        direction = payload.get("direction")
        if direction not in ("up", "down"):
            raise TaskError("direction 必须是 up 或 down")
        plan = read_task_plan(output_dir)
        updated = move_task(plan, task_id, direction)  # 校验（含未拆解）在纯函数内
        backup_task_plan(output_dir)
        write_task_plan(output_dir, updated)
        return {"plan": updated.to_dict()}

    @app.post("/api/tasks/idea/drafts/read")
    @_map_errors
    def tasks_idea_drafts_read(payload: dict) -> dict:
        """草稿箱读取（同步端点，工单 idea-suite/05）：{output_dir} → {drafts}。

        无文件 = []（不 400——照全局商量 chat/read 先例）；坏 JSON → 400
        中文（宁拒收不吞）。"""
        from .drafts import read_drafts

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        return {
            "drafts": [draft.to_dict() for draft in read_drafts(output_dir).drafts]
        }

    @app.post("/api/tasks/idea/drafts/add")
    @_map_errors
    def tasks_idea_drafts_add(payload: dict) -> dict:
        """存草稿（同步端点，工单 idea-suite/05）：{output_dir, text} → {drafts}。

        text 空 / 纯空白 → 400；同文本已存在 → 不重复插入（去重，返回原
        集合）；落盘 = 原子写（.tmp → replace——增删草稿是小步操作，原子写
        已保证不写碎文件，不再另设 .bak；对照清单文件 .bak 仅用于整份覆盖
        场景）。"""
        from .drafts import add_draft, read_drafts, write_drafts

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        text = payload.get("text")  # 非空校验在 add_draft（照 dialog-adopt 先例）
        updated = add_draft(read_drafts(output_dir), text)
        write_drafts(output_dir, updated)
        return {"drafts": [draft.to_dict() for draft in updated.drafts]}

    @app.post("/api/tasks/idea/drafts/delete")
    @_map_errors
    def tasks_idea_drafts_delete(payload: dict) -> dict:
        """删草稿（同步端点，工单 idea-suite/05）：{output_dir, id} → {drafts}。

        未知 id 静默（幂等——双击删除按钮不是错误）；id 非字符串 → 400。"""
        from .drafts import delete_draft, read_drafts, write_drafts

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        draft_id = payload.get("id")
        if not isinstance(draft_id, str) or not draft_id.strip():
            raise TaskError("id 必须是非空字符串")
        updated = delete_draft(read_drafts(output_dir), draft_id)
        write_drafts(output_dir, updated)
        return {"drafts": [draft.to_dict() for draft in updated.drafts]}

    @app.post("/api/tasks/idea/fix")
    @_map_errors
    def tasks_idea_fix(payload: dict) -> StreamingResponse:
        """想法直接修正（SSE 流）：修正中 → 编译验证 → done（结果 + 受影响）。

        请求体契约：output_dir（必填）；idea（必填非空字符串）；fix_summary
        （可选字符串，想法分析给出的修正建议——透传 LLM 按此修正）；
        affected_task_ids（可选字符串数组，受影响任务——成功后标
        needs_redo=True 并落盘）；problem_text（可选覆盖）。

        事件序列：compile_start → fix_start（仅首轮编译失败）→ verify_result
        → task_reporting（AI 总结本步「做了什么 + 接下来做什么」，秒级）→
        done（{"status", "backup_id", "compile", "main_diff", "message",
        "step_report", "affected"}）或 error（中文信息）→ 流结束。HTTP 200
        起流，失败以流内 error 事件收尾（复用执行事件词表，不新增）。

        缺题面 / main.c 空 → 400；修正成功后才标记受影响任务（不落失败
        半成品）；备份可经 /api/revise/rollback 回滚（复用入口）。
        """
        from .task_progress import (
            read_task_plan,
            run_direct_fix,
            set_tasks_needs_redo,
        )

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        idea = _require_str(payload, "idea")
        fix_summary = _optional_str(payload, "fix_summary") or ""
        raw_affected = payload.get("affected_task_ids")
        if raw_affected in (None, []):
            affected: list[str] = []
        elif isinstance(raw_affected, list) and all(
            isinstance(item, str) for item in raw_affected
        ):
            affected = [item.strip() for item in raw_affected if item.strip()]
        else:
            raise TaskError("affected_task_ids 必须是字符串数组")
        config = _require_config(context)
        module_library_dir = config.module_library_dir
        _, fields = _load_revision_context(output_dir, module_library_dir)
        if payload.get("problem_text") is not None:
            fields["problem_text"] = _require_str(payload, "problem_text")
        if not fields.get("problem_text"):
            raise TaskError("缺少赛题原文——请先补题面（直接修正需要题面证据）")
        platform = fields["platform"]
        main_c = read_project_main_c(output_dir) or fields.get("main_c", "")
        if not main_c.strip():
            raise TaskError("工程 main.c 为空，无法执行修正")
        resolved = resolve_selection(module_library_dir, platform, fields["slugs"])
        plan = read_task_plan(output_dir)
        if affected and plan is None:
            raise TaskError("该目录尚未拆解任务——无法标记受影响任务，请先拆解")
        # 工程级全局结论（工单 idea-suite/01）：注入本步修正 prompt（空串 = 未采纳）
        global_note = _read_global_note(output_dir)
        budget = RetryBudget()
        collector = create_llm_observation_collector("tasks-idea-fix")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_direct_fix(
                        llm=llm,
                        idea=idea,
                        fix_summary=fix_summary,
                        affected=affected,
                        problem_text=fields["problem_text"],
                        qa_text=fields.get("qa_text", ""),
                        manifests=resolved.manifests,
                        platform=platform,
                        library_dir=module_library_dir,
                        master_project_dir=master_project_dir(
                            config.masters_dir, platform
                        ),
                        main_c=main_c,
                        output_dir=output_dir,
                        work_root=config.masters_dir.parent,
                        emit=emit,
                        uv4_override=config.uv4_path,
                        make_override=config.gmake_path,
                        module_slugs=fields["slugs"],
                        global_note=global_note,
                    )
                # 修正成功落盘后：受影响任务标「建议重做」（不落失败半成品）
                if affected and plan is not None:
                    updated_plan = set_tasks_needs_redo(plan, affected, True)
                    write_task_plan(output_dir, updated_plan)
                emit.done({**result, "affected": list(affected)})
            finally:
                context.recent_llm_workflows.add_completed(collector)

        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/tasks/idea/mark-redo")
    @_map_errors
    def tasks_idea_mark_redo(payload: dict) -> dict:
        """标记 / 清除「建议重做」（同步端点）：{output_dir, task_ids,
        needs_redo?} → {plan}。

        task_ids 必填字符串数组；needs_redo 可选布尔（缺省 True——标记；
        False = 清除，用户重做后调用）。未知 id 静默忽略（AI 可能编造 id）。
        清单未拆解 → TaskError 400；返回 {"plan": 落盘后全量清单}。
        """
        from .task_progress import read_task_plan, set_tasks_needs_redo

        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise TaskError(f"输出目录不存在：{output_dir}")
        raw_ids = payload.get("task_ids")
        if not isinstance(raw_ids, list) or any(
            not isinstance(item, str) for item in raw_ids
        ):
            raise TaskError("task_ids 必须是字符串数组")
        needs_redo = payload.get("needs_redo", True)
        if not isinstance(needs_redo, bool):
            raise TaskError("needs_redo 必须是布尔值")
        plan = read_task_plan(output_dir)
        if plan is None:
            raise TaskError("该目录尚未拆解任务——请先点「拆解任务」生成任务清单")
        updated = set_tasks_needs_redo(
            plan, [item.strip() for item in raw_ids if item.strip()], needs_redo
        )
        write_task_plan(output_dir, updated)
        return {"plan": updated.to_dict()}

    @app.post("/api/buy/discuss")
    @_map_errors
    def buy_discuss(payload: dict) -> dict:
        """买件方案商量（同步端点，工单 buy-discuss/03）：一轮讨论 → {reply, review}。

        请求 {problem_text 必填, requirement?, platform?, suggestion_name?
        （词表行匹配 → 该行 solutions 注入讨论），history: [{role: user|
        assistant, content}] 必填数组（旧 → 新，前端积累）}。服务端按
        suggestion_name 匹配词表行（selection._solution_group——类别名或
        型号名都能命中），词表外 = 空方案（仅题面/需求/历史讨论，不编造方案
        文本）；缺题面 / history 非数组 / 条目非对象 / role 词表外 / content
        非字符串 → BuyError 400 中文；LLM 失败 → 502（error_to_http 表）。
        telemetry 照常采集（观测收集绑定 _llm 实例）——同步端点无 SSE 通道，
        观测进 recent_llm_workflows 记录。
        """
        from .selection import BuyError, _solutions_for
        from .wordlist import DEFAULT_WORDLIST

        problem_text = _optional_str(payload, "problem_text")
        if not problem_text:
            raise BuyError("缺赛题原文（problem_text）：讨论必须结合题面")
        requirement = _optional_str(payload, "requirement")
        platform = _optional_str(payload, "platform")
        suggestion_name = _optional_str(payload, "suggestion_name")
        raw_history = payload.get("history")
        if not isinstance(raw_history, list) or not raw_history:
            raise BuyError("history 必须是数组（讨论历史，旧 → 新）")
        history: list[tuple[str, str]] = []
        for index, item in enumerate(raw_history):
            if not isinstance(item, dict):
                raise BuyError(f"history[{index}] 必须是对象（role + content）")
            role = item.get("role")
            if role not in ("user", "assistant"):
                raise BuyError(f"history[{index}] 的 role 必须是 user 或 assistant")
            content = item.get("content")
            if not isinstance(content, str):
                raise BuyError(f"history[{index}] 的 content 必须是字符串")
            history.append((role, content))

        solutions = _solutions_for(suggestion_name, DEFAULT_WORDLIST)

        collector = create_llm_observation_collector("buy-discuss")
        try:
            llm = _llm(context, RetryBudget(), collector)
            discussion = llm.discuss_buy_options(
                problem_text=problem_text,
                requirement=requirement,
                platform=platform,
                solutions=solutions,
                history=tuple(history),
            )
        finally:
            # 观测收尾（评审项 spec/①）：漏调则观察面板 recent_llm_workflows
            # 看不到 buy-discuss——docstring 承诺必须兑现
            context.recent_llm_workflows.add_completed(collector)
        return {
            "reply": discussion.reply,
            "review": discussion.review.to_dict() if discussion.review is not None else None,
        }

    @app.post("/api/fix-errors")
    @_map_errors
    def fix_errors(payload: dict) -> StreamingResponse:
        """编译错误修复（SSE 流）：贴报错 → 逐条修复 → 直接写回工程文件。

        事件序列：parse_done（解析结果）→ fix_start（LLM 修复中，分钟级）→
        llm_telemetry（脱敏 LLM 调用快照，可能随每次记录更新）→ apply_result…
        （逐处应用结果）→ done（修复结果 + 备份编号）或 error（中文信息）→
        流结束。HTTP 200 起流，失败以流内 error 事件收尾
        （sse 运行器终态保证）；参数校验失败 / 输出目录不存在 400。

        请求体契约：error_text（必填，编译报错全文）；output_dir（必填，生成
        结果目录，必须已存在）；problem_text / platform / slugs / main_c
        （可选上下文，决策记录 6）；previous_fixes（可选，上一轮 done 载荷的
        fixes 数组，工单 fix-loop-progress/01——原样透传 run_fix_round，形状
        判决归域层，路由不做校验）。路径安全：解析出的文件必须 resolve 后在
        输出目录内（is_unsafe_path + containment），写回白名单 .c/.h/.s——
        修复建议越界由修复域拒绝（FixError → 400 中文，登记 errors.py）。

        五步编排（解析 → 定位 → 读上下文 → LLM 修复 → 应用 + 事件发射 +
        done 载荷拼装）在 run_fix_round（对照 run_recommendation 先例），
        本路由只取参 + 转调 + SSE 包装。
        """
        error_text = _require_str(payload, "error_text")
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise FixError(f"输出目录不存在：{output_dir}")
        problem_text = _optional_str(payload, "problem_text")
        platform = _optional_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        main_c = _optional_str(payload, "main_c")
        # 可选数组原样透传（形状判决归 run_fix_round 域校验——_optional_str
        # 系列不适用，非法形状由域层 FixError → 400 中文）
        previous_fixes = payload.get("previous_fixes", ())
        backup_root = fix_backup_root(
            _require_config(context).masters_dir.parent
        )
        budget = RetryBudget()
        collector = create_llm_observation_collector("fix-errors")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            # 五步编排归 run_fix_round（对照 run_recommendation 归位先例）：事件
            # 发射在域内（_emit 旁路），done 载荷由本路由 emit.done 收尾（终态
            # 保证仍归运行器，run 抛错补发 error 终态）
            try:
                with bind_llm_telemetry(collector, emit.progress):
                    result = run_fix_round(
                        llm,
                        error_text=error_text,
                        output_dir=output_dir,
                        backup_root=backup_root,
                        problem_text=problem_text,
                        platform=platform,
                        module_slugs=slugs,
                        main_c=main_c,
                        previous_fixes=previous_fixes,
                        emit=emit.progress,
                    )
                emit.done(result)
            finally:
                context.recent_llm_workflows.add_completed(collector)

        # 终态保证归运行器：run 抛错由 run_sse 补发 error 终态（文案走错误映射表）
        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/fix-errors/rollback")
    @_map_errors
    def fix_errors_rollback(payload: dict) -> dict:
        """回滚本次修复（决策记录 2）：把 <backup>/<backup_id>/ 备份的文件
        复制回输出目录。backup_id 必须是安全目录名（is_unsafe_path 拒绝对
        `..` / 绝对路径）；备份或输出目录不存在 → FixError（400 中文）。
        同步端点（文件复制是瞬间操作）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        backup_id = _require_str(payload, "backup_id")
        restored = restore_backup(
            fix_backup_root(_require_config(context).masters_dir.parent),
            backup_id,
            output_dir,
        )
        return {"restored": list(restored)}

    # ------------------------------------------------------------------
    # 自动编译（工单 autocompile-loop/01）：服务端探测工具链 → 子进程全量
    # 重建 → 原样采集编译输出。域判决在 compile_runner.py，路由只做薄壳
    # 装配（前端状态机驱动循环，本路由单次编译）。
    # ------------------------------------------------------------------

    @app.post("/api/compile")
    @_map_errors
    def compile_project(payload: dict) -> StreamingResponse:
        """自动编译（SSE 流，工单 autocompile-loop/01）：compile_start → done
        （exit_code / error_text / passed / timed_out）或 error → 流结束。

        请求体契约：platform（stm32 / mspm0，必填）；output_dir（必填，生成
        结果目录，必须已存在）。工具链缺失在起流前判定 → 400 中文（登记
        errors.py，前端据此置灰按钮回退贴文本模式）；工程结构异常（没有
        .uvprojx / Debug/makefile）发生在流内 → error 事件如实报告（文案
        写具体，不沿用泛化文案——工单观察记录 2）。超时 → done 携带
        timed_out=True（如实报告不静默）。

        done 的 data：platform / output_dir / exit_code（超时为 null）/
        error_text（编译输出原样采集，与 fix-errors 解析契约对齐）/
        passed（域模块 compile_passed 判定，前端循环不自己判退出码）/
        timed_out / project_file（定位到的工程文件）/ command（实际命令，
        可复述）；展示层追加（工单 compile-experience-ui/01，只增不改旧字段）：
        duration（秒，float，子进程实际耗时）/ parsed_errors（[{path, line,
        message}]，parse_compile_errors 解析——与 fix-errors 的 parsed 同源
        同构）/ summary（{errors, warnings}，summarize_compile_output：UV4
        汇总行优先、无汇总退行级）。不要求 AI 配置（工单
        compile-verdict-align/01：编译不调 LLM，只须工具链路径——无 api_key
        的用户也应能"编译看结果"；修复按钮仍走 AI 配置校验，400 如实报、
        循环自然停）。阻塞调用（编译分钟级以内）放独立线程跑，
        事件经队列送流生成器（与提炼 / 修复端点同款终态保证，断线旁路）。
        工具链探测（起流前 400）与流内编排（compile_start → collect → parse
        → done 11 字段）在 compile_runner（resolve_compile_toolchain /
        run_compile），本路由只取参 + 转调 + SSE 包装。"""
        platform = _require_str(payload, "platform")
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise CompileRunnerError(f"输出目录不存在：{output_dir}")
        # 编译不调 LLM，不要求 AI 配置（工单 compile-verdict-align/01）：未配置
        # 时 uv4_path / gmake_path 覆盖为空，走自动探测（find_uv4/find_make
        # 空覆盖语义 = 常见路径 + PATH）
        config = _current_config(context)
        # 工具链探测（config 覆盖 + 自动）：缺失 → 400 中文（前端回退贴文本）。
        # 探测归 compile_runner.resolve_compile_toolchain——必须在起流前判（400
        # 而非流内 error），故不进 run_sse 的 run 回调
        uv4, make = resolve_compile_toolchain(
            platform,
            uv4_override=config.uv4_path if config else "",
            make_override=config.gmake_path if config else "",
        )

        def run(emit: SseEmitter) -> None:
            # 流内编排归 compile_runner.run_compile（compile_start → collect →
            # parse → done 11 字段，对照 run_recommendation / run_fix_round 先例），
            # 路由只转调
            run_compile(platform, output_dir, uv4=uv4, make=make, emit=emit)

        # 终态保证归运行器：run 抛错由 run_sse 补发 error 终态（文案走错误映射表）
        return StreamingResponse(
            run_sse(run, error_message=_error_message),
            headers={"Content-Type": "text/event-stream"},
        )

    @app.post("/api/compile/source-line")
    @_map_errors
    def compile_source_line(payload: dict) -> dict:
        """错误列表点击展开的源码行（薄接口，工单 compile-experience-ui/01）。

        请求体契约：output_dir（必填，生成结果目录）；path（必填，错误列表里
        的相对路径，POSIX 或 UV4 反斜杠形态都收）；line（必填，正整数 1 起）。
        → 200 {path_resolved, line_text}（line_text 为第 line 行内容，不含
        行尾；读的是修复后的当前文件——展示修复结果，不做快照）。

        路径安全：复用 fix-errors 双基准解析（工程根 + .uvprojx/.cproject
        父目录，UV4 `..\\` 形态）与 containment 校验——resolve 后必须在
        输出目录内，`../..` 穿越 / 绝对路径越界拒绝；文件不存在 / 行号越界
        → 400 中文（FixError 登记 errors.py）。同步端点（单行读取是瞬间操作）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        path = _require_str(payload, "path")
        line = payload.get("line")
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise HTTPException(400, "line 必须是正整数（1 起）")
        target = resolve_source_path(output_dir, path)
        if target is None:
            raise FixError(f"源码文件不存在或路径越界：{path}")
        try:
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise FixError(f"读取源码失败：{path}（{exc}）") from exc
        if line > len(lines):
            raise FixError(f"行号越界：{path} 第 {line} 行（文件共 {len(lines)} 行）")
        return {
            "path_resolved": target.relative_to(output_dir.resolve()).as_posix(),
            "line_text": lines[line - 1],
        }

    @app.post("/api/flash")
    @_map_errors
    def flash_firmware(payload: dict) -> dict:
        """烧录到板子（同步端点，工单 flash-deploy/01）：定位产物 → 探测工具
        → 构建命令 → 执行 → 中文结果。

        请求体契约：output_dir（必填，生成结果目录，必须已存在）；平台从产物
        树反推（context_manifest._infer_platform 复用——.uvprojx → stm32 /
        .cproject/.project → mspm0，两者都有或都没有 → 400 中文）。不要求 AI
        配置（与 /api/compile 同规：烧录不调 LLM，只须工具路径——config 覆盖
        为空时走自动探测）。

        失败分级：平台未知 / 产物缺失（未先编译）/ 工具缺失（MSPM0 无
        DSLite、STM32 无 OpenOCD 且无 st-flash）→ 400 中文（FlashError 登记
        errors.py，message 带指引，前端渲染指引卡）；烧录失败（工具报错 /
        探针未接 / 超时）→ 200 {ok: False} 携带输出尾 + 排查提示（正常返回，
        不是异常）。成功 → 200 {ok: True, tool, command, firmware, output,
        message, duration}。烧录秒级~分钟级（180s 超时），同步阻塞可接受
        （前端 busy 文案防重）；事件流不加（观察后按需升级，决策记录 10）。
        """
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise FlashError(f"输出目录不存在：{output_dir}")
        platform = _infer_platform(output_dir)
        config = _current_config(context)
        return flash_project(
            platform,
            output_dir,
            dslite_path=config.dslite_path if config else "",
            openocd_path=config.openocd_path if config else "",
            stflash_path=config.stflash_path if config else "",
        )

    # ------------------------------------------------------------------
    # 交付（工单 delivery-suite/01）：打开工程 / 交付检查 / 一键打包
    # ------------------------------------------------------------------

    @app.post("/api/delivery/open-ide")
    @_map_errors
    def delivery_open_ide(payload: dict) -> dict:
        """打开工程（同步端点，工单 delivery-suite/01）：平台自适应——stm32
        优先拉起 Keil（uv4_path 配置覆盖 > C:/Keil*/UV4/UV4.exe 探测 > 系统
        关联 startfile），兜底 explorer 打开文件夹；mspm0 = explorer 打开
        文件夹（CCS 手动导入）。返回 {mode: "ide"|"folder", target,
        message}；目录缺失 / 平台未知 → 400 中文（DeliveryError）。
        启动进程/关联打开的失败都降级为 message，不抛异常。"""
        output_dir = Path(_require_str(payload, "output_dir"))
        if not output_dir.is_dir():
            raise DeliveryError(f"输出目录不存在：{output_dir}")
        config = _current_config(context)
        return open_project_dir(
            output_dir, uv4_path=config.uv4_path if config else ""
        )

    @app.post("/api/delivery/check")
    @_map_errors
    def delivery_check_endpoint(payload: dict) -> dict:
        """交付前检查（同步端点，工单 delivery-suite/01）：任务清单完成度
        汇总（verified+skipped = 完成）+ 未完成清单逐条列出（失败一眼可见）。
        返回 {ok, plan_present, stats: null|计数, incomplete, message}；
        未拆解清单 = ok False + 中文提示（不 400）；目录缺失 → 400。"""
        output_dir = Path(_require_str(payload, "output_dir"))
        return delivery_check(output_dir)

    @app.post("/api/delivery/package")
    @_map_errors
    def delivery_package(payload: dict) -> dict:
        """一键打包（同步端点，工单 delivery-suite/01）：工程目录 → zip（父
        目录，时间戳命名不覆盖旧包；排除 .contest_* 内部文件与 *.tmp /
        *.bak）。返回 {zip_path, size, files, message}；目录缺失 → 400。"""
        output_dir = Path(_require_str(payload, "output_dir"))
        return package_project(output_dir)

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
        budget = RetryBudget()
        collector = create_llm_observation_collector("masters-distill")
        llm = _llm(context, budget, collector)

        def run(emit: SseEmitter) -> None:
            try:
                projects = [scan_project(Path(d)) for d in project_dirs]
                with bind_llm_telemetry(collector, emit.progress):
                    report = distill_master(llm, platform, projects, emit.progress)
                emit.done(report.to_dict())
            finally:
                context.recent_llm_workflows.add_completed(collector)

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
        budget = RetryBudget()
        collector = create_llm_observation_collector("masters-confirm")

        def archive_llm_factory() -> LLM:
            return _llm(context, budget, collector)

        try:
            meta = confirm_distillation(
                _masters_dir(context),
                project_dirs,
                payload,
                llm_factory=archive_llm_factory,
                reference_library_dir=reference_library_dir(config.module_library_dir),
            )
        finally:
            context.recent_llm_workflows.add_completed(collector)
        return {
            "platform": meta.platform,
            "sources": list(meta.sources),
            "warnings": list(meta.warnings),
        }

    @app.get("/api/masters")
    @_map_errors
    def masters() -> list[dict]:
        """浏览母版库（每平台一个母版）。

        每条带 platform_label（平台展示名，仅界面用）、key_files 关键文件
        目录（path / label / size_bytes / exists 实况，不含内容——内容经
        内容端点按需取）与 health / stats 体检实况（工单 master-library-ui/01
        与 master-library-ui-2/01：关键词缺失 / 配置文件 / 构建产物残留 +
        体积统计，一次算好不按条回查）。
        """
        masters_dir = _masters_dir(context)
        return [
            {
                **m.to_dict(),
                "platform_label": PLATFORM_DISPLAY_NAMES.get(m.platform, m.platform),
                "key_files": [
                    info.to_dict()
                    for info in master_key_files(masters_dir, m.platform)
                ],
                "health": master_health(masters_dir, m.platform).to_dict(),
                "stats": master_stats(masters_dir, m.platform).to_dict(),
            }
            for m in list_masters(masters_dir)
        ]

    @app.delete("/api/masters/{platform}")
    @_map_errors
    def master_delete(platform: str) -> dict:
        delete_master(_masters_dir(context), platform)
        return {"ok": True}

    @app.get("/api/masters/{platform}/files/{path:path}")
    @_map_errors
    def master_file(platform: str, path: str) -> dict:
        """母版关键文件内容（只读预览，工单 master-library-ui/02）。

        白名单墙（MASTER_KEY_FILES 单源）：清单外路径 / 平台不存在 / 文件缺失
        一律 400 中文；成功返回 {path, label, size_bytes, content}（utf-8
        errors=\"replace\" 读取）。
        """
        return read_master_file(_masters_dir(context), platform, path)

    @app.post("/api/masters/import")
    @_map_errors
    def masters_import(payload: dict) -> dict:
        """母版免提炼快速导入（工单 master-library-ui-2/04）。

        project_dir = 服务器本地绝对路径（与 /api/masters/scan 同风险面——
        本机工具语义，用户显式提供）；复用既有入库编排（结构校验 + 临时目录
        + 原子替换 + 备份回滚 + autocommit），全程零 LLM 调用；失败 400
        中文（结构校验失败不动盘）。
        """
        platform = _require_str(payload, "platform")
        project_dir = _require_str(payload, "project_dir")
        return import_master_direct(
            _masters_dir(context), platform, Path(project_dir)
        ).to_dict()

    @app.get("/api/masters/{platform}/tree")
    @_map_errors
    def master_tree(platform: str) -> list[dict]:
        """母版全部文件的树清单（工单 master-library-ui-2/02）：统一噪音
        跳过（构建产物目录 / .git 不计入），每条 {path, size_bytes} 一次算好；
        前端渲染递归树，与关键文件白名单端点（/files）两条路线并存。
        """
        return [
            info.to_dict()
            for info in master_tree_files(_masters_dir(context), platform)
        ]

    @app.get("/api/masters/{platform}/tree/{path:path}")
    @_map_errors
    def master_tree_file(platform: str, path: str) -> dict:
        """母版树内文件内容（工单 master-library-ui-2/02）：平台目录内任意
        文本文件——路径安全 / 二进制 / 超 1MB 三类均 400 中文；成功返回
        {path, size_bytes, content}（utf-8 errors="replace" 读取 + 换行归一化，
        与关键文件端点同文案惯例）。
        """
        return read_master_tree_file(_masters_dir(context), platform, path)

    # ------------------------------------------------------------------
    # 设置：读写配置，写入后即时生效（后续请求即用新配置）
    # ------------------------------------------------------------------

    @app.get("/api/llm-workflows/recent")
    @_map_errors
    def llm_workflows_recent() -> dict:
        """最近已完成 LLM 工作流：只读、内存态、content-safe，不写 config / 磁盘。

        载荷按当前生效单价表附加估算字段（est：实际 / 全 DeepSeek 对照 / 节省）；
        估算纯展示派生，单价表缺失 / 配置未就绪时用内置默认（旁路不炸）。
        """
        config = _current_config(context)
        tables = price_tables_from_config(
            config.llm_prices if config else None,
            (config.llm_price_period if config else "off_peak"),
        )
        return attach_cost_estimates(context.recent_llm_workflows.to_dict(), tables)

    @app.get("/api/settings")
    @_map_errors
    def settings_get() -> dict:
        """读取设置；API key 只回掩码（前 4 位 + 与真实长度一致的圆点），不回明文。"""
        config = _current_config(context)
        api_key = config.api_key if config is not None else ""
        defaults = AppConfig()
        return {
            "configured": config is not None,
            "base_url": (config.base_url if config is not None else ""),
            "model": (config.model if config is not None else ""),
            "api_key": _mask_api_key_display(api_key),
            "module_library_dir": str(
                config.module_library_dir if config is not None else defaults.module_library_dir
            ),
            "masters_dir": str(
                config.masters_dir if config is not None else defaults.masters_dir
            ),
            # 工具链可选覆盖（工单 autocompile-loop/01）：空串 = 自动探测
            "uv4_path": config.uv4_path if config is not None else "",
            "gmake_path": config.gmake_path if config is not None else "",
            # CCS 三件套可选覆盖（工单 mspm0-build-makefiles/01）：空串 = 自动探测
            "ccs_sdk_dir": config.ccs_sdk_dir if config is not None else "",
            "ccs_compiler_dir": config.ccs_compiler_dir if config is not None else "",
            "ccs_sysconfig_cli": config.ccs_sysconfig_cli if config is not None else "",
            # 烧录工具可选覆盖（工单 flash-deploy/01）：空串 = 自动探测
            "openocd_path": config.openocd_path if config is not None else "",
            "stflash_path": config.stflash_path if config is not None else "",
            "dslite_path": config.dslite_path if config is not None else "",
            # 本地 LLM 端点（工单 local-llm-routing/01-03）：空串 = 本地路由关闭
            "local_llm_base_url": config.local_llm_base_url if config is not None else "",
            "local_llm_model": config.local_llm_model if config is not None else "",
            # 视觉通道（工单 vision-eyes/01）：base/model 缺省官方免费通道；
            # api_key 掩码同主 key（显示形态 = 前 4 位 + 长度圆点 + 末位），空 key = 视觉关闭
            "vision_base_url": (
                config.vision_base_url if config is not None else DEFAULT_VISION_BASE_URL
            ),
            "vision_api_key": (
                _mask_api_key_display(config.vision_api_key)
                if config is not None and config.vision_api_key
                else ""
            ),
            "vision_model": (
                config.vision_model if config is not None else DEFAULT_VISION_MODEL
            ),
            # 问答式精注记开关（工单 vision-detail-qa/01）：图注一轮描述后追加
            # 二轮视觉追问补细节；缺省开
            "vision_detail_qa": (
                config.vision_detail_qa if config is not None else True
            ),
            # LLM 单价（工单 llm-cost-control/01）：返回当前生效表（默认 + 覆盖
            # 合并），前端可直接显示；未配置 / 无覆盖 = 内置默认
            "llm_prices": price_tables_to_config(
                price_tables_from_config(
                    config.llm_prices if config else None,
                    (config.llm_price_period if config else "off_peak"),
                )
            ),
            # 用户显式覆盖原文（None = 无覆盖）：前端据此区分「留空 = 用时段
            # 基准价」与「填值 = 自定义覆盖」
            "llm_prices_override": config.llm_prices if config is not None else None,
            # 计费时段（工单 01 扩展）：peak 高峰 / off_peak 空闲，缺省 off_peak
            "llm_price_period": (
                config.llm_price_period if config is not None else "off_peak"
            ),
            # DeepSeek Flash 官方价格参考（工单 llm-cost-control 更新）：单源
            # = llm_pricing.DEEPSEEK_FLASH_PRICE_REFERENCE，设置页折叠面板渲染
            "price_reference": DEEPSEEK_FLASH_PRICE_REFERENCE,
            # 推荐缓存开关（工单 llm-cost-control/02）：缺省开
            "recommend_cache_enabled": (
                config.recommend_cache_enabled if config is not None else True
            ),
            # 推荐收敛轮数上限（工单 recommend-speedup-v2/01）：缺省 4
            "recommend_max_rounds": (
                config.recommend_max_rounds if config is not None else 4
            ),
            # 烧录工具自动探测状态（工单 flash-deploy/02，spec 故事 8「自动探测
            # 到则显示已自动找到」）：覆盖为空时前端据此渲染「已自动找到：<工具>」；
            # 探测是纯本地 glob/which（秒级），settings GET 实时算不等缓存
            "flash_auto_tools": _flash_auto_tools(),
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
            # 工具链可选覆盖（工单 autocompile-loop/01）：缺省 = 自动探测
            uv4_path=_optional_str(payload, "uv4_path"),
            gmake_path=_optional_str(payload, "gmake_path"),
            # CCS 三件套可选覆盖（工单 mspm0-build-makefiles/01）：缺省 = 自动探测
            ccs_sdk_dir=_optional_str(payload, "ccs_sdk_dir"),
            ccs_compiler_dir=_optional_str(payload, "ccs_compiler_dir"),
            ccs_sysconfig_cli=_optional_str(payload, "ccs_sysconfig_cli"),
            # 烧录工具可选覆盖（工单 flash-deploy/01）：缺省 = 自动探测
            openocd_path=_optional_str(payload, "openocd_path"),
            stflash_path=_optional_str(payload, "stflash_path"),
            dslite_path=_optional_str(payload, "dslite_path"),
            # 本地 LLM 端点（工单 local-llm-routing/03）：缺省 / 空串 = 关闭本地路由
            local_llm_base_url=_optional_str(payload, "local_llm_base_url"),
            local_llm_model=_optional_str(payload, "local_llm_model"),
            # 视觉通道（工单 vision-eyes/01）：缺省 / 空串 = 官方免费通道；key 掩码
            # 沿用旧值（与 api_key 同款语义），空 key = 关闭视觉
            vision_base_url=(
                _optional_str(payload, "vision_base_url") or DEFAULT_VISION_BASE_URL
            ),
            vision_api_key=_masked_optional_key(
                payload, "vision_api_key", existing.vision_api_key if existing else ""
            ),
            vision_model=(
                _optional_str(payload, "vision_model") or DEFAULT_VISION_MODEL
            ),
            # 问答式精注记开关（工单 vision-detail-qa/01）：缺省开；非布尔 400
            vision_detail_qa=_optional_bool(
                payload, "vision_detail_qa", default=True
            ),
            # LLM 单价覆盖（工单 llm-cost-control/01）：缺省 / 空对象 = 恢复内置默认
            llm_prices=_optional_dict(payload, "llm_prices"),
            # 计费时段（工单 01 扩展）：缺省 off_peak；非法值 400
            llm_price_period=_optional_choice(
                payload, "llm_price_period", default="off_peak", choices=("peak", "off_peak")
            ),
            # 推荐缓存开关（工单 llm-cost-control/02）：缺省开；非布尔 400
            recommend_cache_enabled=_optional_bool(
                payload, "recommend_cache_enabled", default=True
            ),
            # 推荐收敛轮数上限（工单 recommend-speedup-v2/01）：2-4，缺省 4
            recommend_max_rounds=_optional_int_range(
                payload, "recommend_max_rounds", default=4, low=2, high=4
            ),
        )
        save_config(config, context.config_path)
        context.config = config  # 即时生效：后续请求直接用新配置
        return {"ok": True}

    @app.post("/api/reset-records")
    @_map_errors
    def reset_records() -> dict:
        """重置本地记录（工单 reset-local-records/01）：清空服务端题相关记录
        ——最近生成列表（recent.json）与 AI 推荐缓存（cache/recommend_*.json），
        返回各自清除条数。

        换题语义：API 配置（config.json）、任务修复备份、日志与工程目录文件
        一律不动；无记录 → 计数 0（清理尽力而为，绝不报错，前端即可安心
        一键调用）。
        """
        config_path = context.config_path
        return {
            "recent_entries": clear_recent(recent_file(config_path)),
            "cache_files": clear_recommend_cache(config_path.parent / "cache"),
        }

    @app.post("/api/vision/selfcheck")
    @_map_errors
    def vision_selfcheck() -> dict:
        """视觉通道自检（工单 vision-selfcheck/01）：用当前生效的视觉参数
        （_resolve_vision 同源：DeepSeek 官方端点视觉 key 留空 = 复用主 key）
        对内置 1×1 PNG 做一次无缓存真实识别——通过 = 配置当前可用（模型 /
        耗时 / 描述一并回显，用户可核对模型是否配错）。

        失败策略与业务一致：未配置 / 网络 / 上游非法 → 400 中文（含设置页
        引导），前端统一走 handle() 错误提取直接展示。自检不做二轮精注记
        （detail_qa）——只验证可用性，省一次视觉调用。
        """
        config = _current_config(context)
        if config is None:
            raise HTTPException(400, "请先保存主 API key 配置")
        base_url, api_key, model = _resolve_vision(config)
        # 未配置与调用失败分开对待（工单 vision-selfcheck/01 评审意见）：
        # 空 key = 配置问题 → 直接引导设置页；VisionError = 链路问题 → 报原因
        if not api_key:
            raise HTTPException(
                400,
                "视觉通道未配置：请到设置页填写视觉 API key"
                "（DeepSeek 官方端点且主 key 已配置时，视觉 key 留空自动复用主 key）",
            )
        started_at = time.monotonic()
        try:
            message = describe_image(
                base64.b64decode(VISION_SELFCHECK_PNG_B64),
                "image/png",
                VISION_SELFCHECK_PROMPT,
                base_url=base_url,
                api_key=api_key,
                model=model,
            )
        except VisionError as e:
            raise HTTPException(400, f"视觉自检失败：{e}")
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        return {
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "model": model,
            "message": message,
        }

    @app.post("/api/llm/selfcheck")
    @_map_errors
    def llm_selfcheck() -> dict:
        """主 LLM 文本通道自检（工单 env-check-center/01）：云端主通道直连
        （不走 RoutingLLM——本地路由只服务摘要类调用，主通道才是一切流程的
        底座）、单次探针不重试（探测语义）、极小成本（max_tokens=16 +
        thinking_disabled）。契约与 vision_selfcheck 同构：未配置先于调用
        错误区分（配置问题 vs 链路问题）。
        """
        config = _current_config(context)
        if config is None:
            raise HTTPException(400, "请先保存主 API key 配置")
        if not config.api_key:
            raise HTTPException(400, "主 LLM 未配置：请到设置页填写 API key")
        started_at = time.monotonic()
        try:
            llm = DeepSeekLLM(config)
            result = llm._chat_once(
                [{"role": "user", "content": "请只回复：PONG"}],
                operation="llm_selfcheck",
                max_tokens=16,
                thinking_disabled=True,
            )
        except LLMError as e:
            raise HTTPException(400, f"文本通道自检失败：{e}")
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        return {
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "model": config.model,
            "reply": (result.content or "").strip()[:100],
        }

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

    @app.get("/api/references/topic-types")
    @_map_errors
    def reference_topic_types() -> list[str]:
        """题型词表（工单 topic-framework/04）：前端下拉选项的单源（词表常量
        经 webapp 一次带出——前端不硬编码，后端校验同源）。"""
        return list(TOPIC_TYPES)

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
            # 未锚定条目提交空串是合法（anchor_value 允许空，非空由域校验裁决）
            anchor_value=_require_str(payload, "anchor_value", allow_empty=True),
            files=files,
            kit_vocabulary=module_kit_vocabulary(config.module_library_dir),
            # 平台属性（工单 01）：缺省 / 空 = any（平台无关，向后兼容）；
            # 词表外值由 add_reference 大声失败（400）
            platform=_optional_str(payload, "platform") or PLATFORM_ANY,
            # 题型标记（工单 topic-framework/01）：缺省 / 空 = 未标记；词表外值
            # 由 add_reference 大声失败（400）
            topic_type=_optional_str(payload, "topic_type") or "",
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

    @app.put("/api/references/{entry_id}")
    @_map_errors
    def reference_update(entry_id: str, payload: dict) -> dict:
        """编辑参考文件条目（工单 reference-library-ui/01）：元数据全量 +
        文件增量一次事务；校验与录入同源，失败磁盘零变化。

        body 契约：{title, type, description, anchor_kind, anchor_value, platform,
        add_files?: {文件名: 内容}, remove_files?: [相对路径, ...]}；元数据全量
        必填（PUT 是替换语义——platform 缺省兜底 any 会把存量条目平台静默降级，
        故强制提供）；add_files / remove_files 缺省 = 不增不减。编辑不改条目
        id / 目录名。
        """
        add_files = payload.get("add_files")
        if add_files is None:
            add_files = {}
        if not isinstance(add_files, dict):
            raise HTTPException(400, "add_files 必须是 {文件名: 内容} 对象")
        remove_files = payload.get("remove_files")
        if remove_files is None:
            remove_files = []
        if not isinstance(remove_files, list) or not all(
            isinstance(item, str) for item in remove_files
        ):
            raise HTTPException(400, "remove_files 必须是字符串列表")
        config = _require_config(context)
        entry = update_reference(
            reference_library_dir(config.module_library_dir),
            entry_id,
            title=_require_str(payload, "title"),
            type=_require_str(payload, "type"),
            description=_require_str(payload, "description"),
            anchor_kind=_require_str(payload, "anchor_kind"),
            anchor_value=_require_str(payload, "anchor_value", allow_empty=True),
            add_files=add_files,
            remove_files=tuple(remove_files),
            kit_vocabulary=module_kit_vocabulary(config.module_library_dir),
            platform=_require_str(payload, "platform"),
            # 题型标记（工单 topic-framework/01）：可选，缺省 = 未标记（与 POST
            # 同语义）；词表外值由 update_reference 大声失败（400）
            topic_type=_optional_str(payload, "topic_type") or "",
        )
        return entry.to_dict()

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
    # PDF 资料库（给人看的资料库）：素材库全量 PDF 浏览 / 搜索 / 直开预览
    # ------------------------------------------------------------------

    @app.get("/api/pdfs")
    @_map_errors
    def pdfs(name: str = "") -> list[dict]:
        """浏览素材库 PDF：全量清单（批次 / 文件名 / 大小 / 修改时间），名字串过滤。"""
        config = _require_config(context)
        return list_pdfs(materials_dir(config.module_library_dir), name=name)

    # 注意：/pages 必须注册在 /api/pdfs/{rel_path:path}（贪婪 path 匹配）之前，
    # 否则 GET `xxx.pdf/pages` 会被文件预览路由吞掉（解析出 `xxx.pdf/pages`
    # 这一整段做路径查找 → 400）。/trash 同为 POST 方法不会被 GET 文件路由
    # 吞噬（Starlette 对方法不匹配只记 partial），但与 /pages 同纪律注册在
    # 前，防将来有人把 trash 改成 GET 时无声破坏。
    @app.get("/api/pdfs/{rel_path:path}/pages")
    @_map_errors
    def pdf_pages_count(rel_path: str) -> dict:
        """单文件页数（PyMuPDF 按需读取）：损坏 / 0 字节 / 非法路径 → 400。"""
        config = _require_config(context)
        return {"pages": pdf_page_count(materials_dir(config.module_library_dir), rel_path)}

    @app.post("/api/pdfs/{rel_path:path}/trash")
    @_map_errors
    def pdf_trash(rel_path: str) -> dict:
        """回收疑似重复组文件：移入 sources/.trash-pdf/<日期>/（不真删，git 忽略）。"""
        config = _require_config(context)
        materials = materials_dir(config.module_library_dir)
        return {
            "rel_path": rel_path,
            "to": trash_pdf(materials, rel_path, pdf_trash_dir(materials)),
        }

    @app.get("/api/pdfs/{rel_path:path}")
    @_map_errors
    def pdf_file(rel_path: str) -> FileResponse:
        """PDF 直开：application/pdf 返回供浏览器原生预览（路径安全在库内）。"""
        config = _require_config(context)
        return FileResponse(
            resolve_pdf(materials_dir(config.module_library_dir), rel_path),
            media_type="application/pdf",
        )

    # ------------------------------------------------------------------
    # 更新记录（工单 changelog-tab/01）：CHANGELOG.md → 按天分组
    # 文件由 post-commit 钩子调用 changelog.update_changelog() 自动补录
    # ------------------------------------------------------------------

    @app.get("/api/changelog")
    @_map_errors
    def changelog() -> list[dict]:
        """更新记录：仓库根 CHANGELOG.md → [{date, items}]（文件顺序）。

        数据源是自动维护的 markdown（格式契约见 changelog.py：`## YYYY-MM-DD`
        严格日期 + 组内 `- ` 条目；git log 自动补录见 update_changelog）。
        纯展示数据：文件缺失 / 损坏 → []（前端显示「暂无更新记录」），不因
        展示数据损坏阻塞工具——不走"大声失败"。
        """
        return load_changelog(Path(__file__).resolve().parents[2] / "CHANGELOG.md")

    # ------------------------------------------------------------------
    # 赛题库（工单 01/05）：长 PDF 拆条 → 用户逐条校对 → 确认入库（事务）
    # + 编号解析 + 浏览 / 删除
    # ------------------------------------------------------------------

    @app.get("/api/topics")
    @_map_errors
    def topics() -> list[dict]:
        """浏览赛题库：全部条目按编号排序 + 每条的 health 实况（浏览列表用）。

        列表一次性算好返回，前端不再按条回查——单条 GET /api/topics/{key}
        是生成入口素材（不带 health，字段现状保持），与浏览列表各司其职。
        """
        config = _require_config(context)
        topics_dir = topic_library_dir(config.module_library_dir)
        return [
            {**entry.to_dict(), "health": topic_health(topics_dir, entry).to_dict()}
            for entry in list_topics(topics_dir)
        ]

    @app.post("/api/topics/split")
    @_map_errors
    async def topics_split(upload: UploadFile = File(...)) -> dict:
        """上传历年真题长 PDF → 拆条（年份 / 编号 / 题面全文）→ 草稿列表。

        视觉通道可用时（工单 topic-vision-notes/01 + vision-deepseek-native/01）：
        先做嵌入图视觉图注（[示意图N：…] 段，照 /api/extract 同款），拆出的
        题面草稿自带图注；视觉 key 留空 + DeepSeek 官方端点 = 复用主 key；
        未配置 = 纯文本（现状逐字节一致）。视觉失败静默降级，不阻塞拆条。

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
            config = _require_config(context)
            vision_base_url, vision_api_key, vision_model = _resolve_vision(config)
            if vision_configured(vision_api_key):
                collector = create_llm_observation_collector("vision-describe")
                text = extract_pdf_with_image_notes(
                    tmp_path,
                    vision_base_url=vision_base_url,
                    vision_api_key=vision_api_key,
                    vision_model=vision_model,
                    observation_collector=collector,
                    detail_qa=config.vision_detail_qa,
                )
                context.recent_llm_workflows.add_completed(collector)
            else:
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

    @app.put("/api/topics/{key}")
    @_map_errors
    def topic_update(key: str, payload: dict) -> dict:
        """编辑赛题条目（工单 topic-library-ui/02）：题面全文 / 附带程序 /
        功能组全量一次保存；校验与确认入库同口径，失败磁盘零变化。

        body 契约：{problem_text, programs: [绝对路径...], hint_module_groups:
        [组 id...]}——三字段全量必填（表单总是提交完整值）；其余键一概忽略
        （身份键不可改：year / number / original_pdf / problem_md 由后端
        保持，前端表单只读展示）。
        """
        programs = payload.get("programs")
        if not isinstance(programs, list) or not all(
            isinstance(item, str) for item in programs
        ):
            raise HTTPException(400, "programs 必须是字符串列表")
        hint_module_groups = payload.get("hint_module_groups")
        if not isinstance(hint_module_groups, list) or not all(
            isinstance(item, str) for item in hint_module_groups
        ):
            raise HTTPException(400, "hint_module_groups 必须是字符串列表")
        config = _require_config(context)
        entry = update_topic(
            topic_library_dir(config.module_library_dir),
            key,
            problem_text=_require_str(payload, "problem_text"),
            programs=tuple(programs),
            hint_module_groups=tuple(hint_module_groups),
        )
        return entry.to_dict()

    @app.get("/api/topics/{key}")
    @_map_errors
    def topic_get(key: str) -> dict:
        """编号解析："2026C" → 题面全文 + 附带程序（生成入口素材）。

        视觉通道可用时（工单 topic-vision-notes/02 + vision-deepseek-native/01）：
        存量条目题面引用图但无图注 → 自动对条目内原 PDF 补图注并写回（幂等），
        返回带图注题面；视觉 key 留空 + DeepSeek 官方端点 = 复用主 key；
        任何视觉失败降级返回原题面（视觉是增强不是阻塞）。未配置 =
        与现状逐字节一致。

        查无此条明确报错（不猜测编造）。
        """
        config = _require_config(context)
        topics_dir = topic_library_dir(config.module_library_dir)
        entry = resolve_number(topics_dir, key)
        vision_base_url, vision_api_key, vision_model = _resolve_vision(config)
        if vision_configured(vision_api_key):
            try:
                collector = create_llm_observation_collector("vision-describe")
                entry = enrich_topic_image_notes(
                    topics_dir,
                    key,
                    vision_base_url=vision_base_url,
                    vision_api_key=vision_api_key,
                    vision_model=vision_model,
                    observation_collector=collector,
                    detail_qa=config.vision_detail_qa,
                )
                context.recent_llm_workflows.add_completed(collector)
            except Exception:
                pass  # 视觉失败降级：返回原题面
        return entry.to_dict()

    @app.get("/api/topics/{key}/pages")
    @_map_errors
    def topic_pages_get(key: str) -> dict:
        """取题面页图（工单 topic-pdf-viewer/01）：条目原 PDF 的题面页渲染 PNG。

        取题面后默认直接展示原题 PDF 页（用户诉求「直接给我展示pdf就行了，
        不要像现在这样给我展示文字」）：题面独特文本（去空白前 20 字符）逐页
        匹配文本层定位题面页 → 完整页范围逐页渲染（工单 topic-pdf-viewer/02：
        汇总 PDF 页脚总页数扩展——2021F 共 4 页不再被截断；无页脚回退既有
        2 页 span；PyMuPDF，既有 2 倍缩放参数）→ base64 data URL 列表，
        前端页图叠放展示。

        纯展示功能不阻塞主流程：条目无原 PDF / 文件缺失 / 页定位失败 /
        渲染全失败 → 400 中文错误（各自说明原因），文字框照常可用。查无
        此条与取题面同一编号解析契约（明确报错，不猜测编造）。
        """
        config = _require_config(context)
        topics_dir = topic_library_dir(config.module_library_dir)
        entry = resolve_number(topics_dir, key)
        if not entry.original_pdf:
            raise HTTPException(400, "该赛题条目没有原 PDF 文件")
        pdf_path = topics_dir / key / entry.original_pdf
        if not pdf_path.is_file():
            raise HTTPException(400, f"原 PDF 文件不存在：{entry.original_pdf}")
        located = locate_topic_pages_full(pdf_path, entry.problem_text)
        if located is None:
            raise HTTPException(
                400, "未能定位题面在 PDF 中的页范围（可能是扫描件或文本不匹配）"
            )
        pages: list[dict[str, Any]] = []
        start, end = located
        for page_no in range(start, end):
            png = render_page_png(pdf_path, page_no)
            if png is None:
                continue  # 单页渲染失败跳过（范围右端越界页天然落这里）
            pages.append(
                {
                    "page_no": page_no,
                    "data_url": "data:image/png;base64,"
                    + base64.b64encode(png).decode("ascii"),
                }
            )
        if not pages:
            raise HTTPException(400, "题面页渲染失败（缺少 PyMuPDF 或 PDF 损坏）")
        return {"key": entry.key, "pages": pages}

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
    result = {
        "output_dir": str(summary.output_dir),
        "structure": list(summary.structure),
        "include_dirs": list(summary.include_dirs),
        "modules": [
            {"slug": slug, "files": list(files)} for slug, files in summary.modules
        ],
        # Python 副产物（工单 k230-vision-copilot/04）：选中模块的 .py
        # （slug → 输出文件名，工程根）——前端摘要「模块文件」行显示 k230
        # 这类 files 空模块的 main.py；未选任何带声明模块 = 空数组
        "python_artifacts": [
            {
                "slug": artifact.slug,
                "output": artifact.output,
                "template_id": artifact.template_id,
                "template_name": artifact.template_name,
                "template_description": artifact.template_description,
            }
            for artifact in summary.python_artifacts
        ],
        # 构建脚本提示（工单 mspm0-build-makefiles/01）：mspm0 未探测到 CCS
        # 工具链时非空，前端摘要区展示一行提示
        "build_hint": summary.build_hint,
    }
    if summary.score_points:
        result["score_points"] = [point.to_dict() for point in summary.score_points]
    return result


app = create_app()


def main() -> None:
    """本地服务入口：python -m contest_generator.webapp 或 contest-generator。"""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
