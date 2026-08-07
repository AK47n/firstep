"""FastAPI 薄壳：装配全部后端能力，形成可用产品（spec 工单 09）。

路由层只做三件事：收 HTTP 请求 → 调核心函数 → 转 JSON 响应；LLM / 文件
抽取是薄壳的一部分，工程生成 / 模块库 / 母版提炼等全部走纯逻辑核心。
用户级设置（AI API / 工作目录）存本机配置文件，写入后即时生效——每次
请求按上下文里的当前配置构造 LLM，不重启服务。

依赖注入：AppContext 持有配置路径 / LLM 工厂，测试注入 tmp 目录与假 LLM，
网络调用不进测试。
"""

from __future__ import annotations

import json
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from queue import Full, Queue
from typing import Any, Callable, Iterator, Sequence

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from .ccs import CcsProjectError
from .config import (
    DEFAULT_CONFIG_PATH,
    AppConfig,
    ConfigError,
    load_config,
    save_config,
)
from .extraction import ExtractionError, extract_file
from .generator import GenerationSummary, GeneratorError, generate_project
from .keil import KeilProjectError
from .library import (
    LibraryError,
    add_module,
    add_platform_files,
    delete_module,
    draft_description,
    list_modules,
    remove_platform_files,
    update_module_description,
    update_platform_identity,
)
from .llm import LLM, LLMError, DeepSeekLLM, ProgressEvent, build_manifest_summaries
from .master import (
    MasterError,
    confirm_distillation,
    delete_master,
    distill_master,
    import_master,
    list_masters,
    scan_project,
)
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32
from .selection import SelectionError, resolve_selection
from .skeleton import generate_skeleton

STATIC_DIR = Path(__file__).parent / "static"

# 平台展示名（仅界面用；平台词表本体在 platforms.py）
PLATFORM_DISPLAY_NAMES = {
    PLATFORM_STM32: "STM32F103C8T6 最小系统板 · Keil5",
    PLATFORM_MSPM0: "地猛星 MSPM0G3507 · CCS",
}

# API key 掩码特征：GET 只回掩码，PUT 收到掩码说明用户没改 key
_API_KEY_MASK_MARKER = "…"


@dataclass
class AppContext:
    """服务上下文：配置路径 + 当前配置（写入后即时生效）+ LLM 工厂（测试注入）。"""

    config_path: Path = DEFAULT_CONFIG_PATH
    config: AppConfig | None = None  # None → 按需从配置文件加载
    llm_factory: Callable[[AppConfig], LLM] = DeepSeekLLM


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


# ---------------------------------------------------------------------------
# 错误映射：核心异常 → HTTP 状态与中文 message
# ---------------------------------------------------------------------------


def _error_message(exc: Exception) -> str:
    """异常 → 中文 message（与 _error_response 同一映射：AI 失败 / 业务失败）。

    提炼的 SSE 流内 error 事件用它（HTTP 保持 200 起流）；普通端点仍走
    _error_response 转状态码。映射改动只在此一处，两端共用不漂移。
    """
    if isinstance(exc, LLMError):
        return f"AI 服务调用失败：{exc}"
    if isinstance(exc, (KeilProjectError, CcsProjectError)):
        # 工程文件（.uvprojx / .cproject）缺失、重复或不是合法 XML：业务失败
        # （旧工程 / AI 整合产物有问题），带中文 message，不裸 500
        return str(exc)
    if isinstance(exc, OSError):
        # 文件系统失败（文件占用 / 权限 / 磁盘满）：本地工具场景用户可处理，
        # 带说明，不裸 500
        return f"文件操作失败：{exc}"
    return str(exc)


def _error_response(exc: Exception) -> HTTPException:
    """业务失败 → 400（message 原样带出）；LLM 服务失败 → 502。"""
    if isinstance(exc, LLMError):
        return HTTPException(502, _error_message(exc))
    return HTTPException(400, _error_message(exc))


# ---------------------------------------------------------------------------
# SSE 线格式共享契约（工单 02，与工单 03 并行开发，精确一致不得单方面改动）
#
# HTTP 200，Content-Type: text/event-stream，无自动重连（断线 = 放弃本次）。
# 每个事件 = "event: <type>\n" + "data: <JSON>\n" + "\n"（空行分隔）；
# type ∈ start / batch_start / batch_done / retry / phase_done / done / error
# （前五者由工单 01 的发射器产生，done / error 由本层发射收尾）；进度事件
# data = ProgressEvent 字段 JSON，done 的 data = 完整报告（report.to_dict()），
# error 的 data = {"message": 中文错误信息}；done 或 error 后流结束。
# ---------------------------------------------------------------------------

EVENT_DONE = "done"
EVENT_ERROR = "error"

# 事件缓冲上限与终端事件等待超时：进度事件只在批次边界产生（分钟级），
# 100 个缓冲对在线消费方绰绰有余；客户端断开后队列无人消费——进度事件满即丢
# （put_nowait，旁路），终端事件等超时后也丢——提炼线程（daemon）不因断线卡死。
_SSE_QUEUE_MAXSIZE = 100
_SSE_TERMINAL_TIMEOUT = 10  # 秒


def _sse_frame(event_type: str, data: dict[str, Any]) -> str:
    """SSE 帧：event 行 + data 行 + 空行（线格式共享契约的唯一实现点）。

    json.dumps 默认转义字符串内换行——data 恒为单行，SSE 解析不歧义。
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 事件队列条目：进度事件原样入队；终端条目 = (kind, data)，kind ∈ done/error
# （done 的 data = 报告 dict，error 的 data = 中文 message）
_QueueItem = ProgressEvent | tuple[str, Any]


def _put_terminal(events: Queue[_QueueItem], kind: str, data: Any) -> None:
    """终端事件（done / error）入队：客户端已断开（队列满、无人消费）时等
    超时后丢弃——提炼线程不因断线卡死（spec「断线」）。"""
    try:
        events.put((kind, data), timeout=_SSE_TERMINAL_TIMEOUT)
    except Full:
        pass


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


def _optional_str(payload: dict, key: str) -> str:
    """可选字符串：缺省 / null → 空串；类型非法抛 400（勿让 null 变成 'None'）。"""
    value = payload.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise HTTPException(400, f"{key} 必须是字符串")
    return value.strip()


def _mask_api_key(api_key: str) -> str:
    """API key 掩码：只露前 4 位（PUT 收到掩码形态视为用户没改 key）。"""
    if not api_key:
        return ""
    return api_key[:4] + _API_KEY_MASK_MARKER


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
    def state() -> dict:
        """首页状态：配置状态 + 平台可用性（母版缺失的平台标记暂不可用）。"""
        config = _current_config(context)
        dirs = config or AppConfig()  # 未配置时展示默认工作目录
        try:
            masters = (
                list_masters(dirs.masters_dir) if dirs.masters_dir.is_dir() else []
            )
        except MasterError as exc:
            raise _error_response(exc) from exc
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

    # ------------------------------------------------------------------
    # 生成流程：贴题或传文件 → 选平台 → AI 推荐可增删 → 骨架 → 生成
    # ------------------------------------------------------------------

    @app.post("/api/extract")
    async def extract(upload: UploadFile = File(...)) -> dict:
        """上传赛题文件（PDF / .docx / .txt / .md）→ 抽取纯文本。"""
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(upload.filename or "").suffix
            ) as tmp:
                tmp.write(await upload.read())
                tmp_path = Path(tmp.name)
            try:
                return {"text": extract_file(tmp_path)}
            finally:
                tmp_path.unlink(missing_ok=True)
        except ExtractionError as exc:
            raise _error_response(exc) from exc

    @app.post("/api/recommend")
    def recommend(payload: dict) -> dict:
        """AI 按赛题推荐模块并给出理由（未展开依赖、未检查平台可用性）。"""
        problem_text = _require_str(payload, "problem_text")
        try:
            library_dir = _library_dir(context)
            summaries = build_manifest_summaries(list_modules(library_dir))
            selection = _llm(context).select_modules(problem_text, summaries)
            return {
                "modules": [
                    {"slug": slug, "reason": selection.reasons.get(slug, "")}
                    for slug in selection.modules
                ]
            }
        except (LibraryError, LLMError) as exc:
            raise _error_response(exc) from exc

    @app.post("/api/selection/expand")
    def expand_selection(payload: dict) -> dict:
        """展开依赖 + 平台可用性检查：用户增删选择后重跑一次即可。"""
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        try:
            resolved = resolve_selection(_library_dir(context), platform, slugs)
            return {
                "modules": [m.to_dict() for m in resolved.manifests],
                "warnings": [
                    {"slug": w.slug, "kind": w.kind, "message": w.message}
                    for w in resolved.warnings
                ],
            }
        except (LibraryError, SelectionError) as exc:
            raise _error_response(exc) from exc

    @app.post("/api/skeleton")
    def skeleton(payload: dict) -> dict:
        """main.c 骨架：LLM 出稿 + 静态自检（不存在的调用改写为注释占位）。"""
        problem_text = _require_str(payload, "problem_text")
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        try:
            resolved = resolve_selection(_library_dir(context), platform, slugs)
            main_c, intercepted = generate_skeleton(
                _llm(context), problem_text, resolved.manifests, platform, _library_dir(context)
            )
            return {"main_c": main_c, "intercepted": list(intercepted)}
        except (LibraryError, SelectionError, LLMError) as exc:
            raise _error_response(exc) from exc

    @app.post("/api/generate")
    def generate(payload: dict) -> dict:
        """完整生成：选模块 → 母版 → 生成 → 摘要（流程在 generate_project）。"""
        platform = _require_str(payload, "platform")
        slugs = _require_str_list(payload, "slugs")
        main_c = _require_str(payload, "main_c")
        output_dir = Path(_require_str(payload, "output_dir"))
        try:
            config = _require_config(context)
            summary = generate_project(
                platform=platform,
                slugs=slugs,
                main_c_content=main_c,
                output_dir=output_dir,
                module_library_dir=config.module_library_dir,
                masters_dir=config.masters_dir,
            )
            return _generation_result(summary)
        except (
            LibraryError,
            SelectionError,
            GeneratorError,
            MasterError,
            KeilProjectError,
            CcsProjectError,
            OSError,
        ) as exc:
            raise _error_response(exc) from exc

    # ------------------------------------------------------------------
    # 模块库（工单 07）：浏览 / AI 录入 / 编辑简介 / 多平台版本 / 删除
    # ------------------------------------------------------------------

    @app.get("/api/modules")
    def modules() -> list[dict]:
        """浏览模块库（磁盘目录即数据库，实时读盘）。"""
        try:
            return [m.to_dict() for m in list_modules(_library_dir(context))]
        except LibraryError as exc:
            raise _error_response(exc) from exc

    @app.post("/api/modules")
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
        try:
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
        except (LibraryError, LLMError) as exc:
            raise _error_response(exc) from exc

    @app.put("/api/modules/{slug}/description")
    def module_description(slug: str, payload: dict) -> dict:
        """编辑简介：AI 校验新简介与代码一致后才写回。"""
        try:
            manifest = update_module_description(
                _llm(context), _library_dir(context), slug, _require_str(payload, "description")
            )
            return manifest.to_dict()
        except (LibraryError, LLMError) as exc:
            raise _error_response(exc) from exc

    @app.post("/api/modules/{slug}/platform-files")
    def module_platform_files(slug: str, payload: dict) -> dict:
        """给模块添加某平台版本文件（内容一致的共享路径复用）。"""
        platform = _require_str(payload, "platform")
        files = payload.get("files")
        if not isinstance(files, dict):
            raise HTTPException(400, "files 必须是 {文件名: 内容} 对象")
        try:
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
        except (LibraryError, LLMError) as exc:
            raise _error_response(exc) from exc

    @app.delete("/api/modules/{slug}/platform-files")
    def module_platform_files_delete(slug: str, payload: dict) -> dict:
        """删除某平台版本的文件（共享文件只移出条目，磁盘保留）。"""
        platform = _require_str(payload, "platform")
        filenames = _require_str_list(payload, "filenames")
        try:
            manifest = remove_platform_files(
                _library_dir(context), slug, platform, filenames
            )
            return manifest.to_dict()
        except LibraryError as exc:
            raise _error_response(exc) from exc

    @app.put("/api/modules/{slug}/platform-identity")
    def module_platform_identity(slug: str, payload: dict) -> dict:
        """编辑平台条目的硬件身份（kit / source_url，工单 02）。

        存量条目的补填 / 修改入口：只做格式校验（提供值须合法——kit 非空、
        source_url URL 格式），不走 AI 一致性校验——身份是事实信息、由人
        确认，AI 判不了真假；只改身份字段，该条目的文件列表 / 验证状态 /
        硬件绑定原样保留。空值视为未提供、保留原值（补填是逐步的）。
        """
        try:
            manifest = update_platform_identity(
                _library_dir(context),
                slug,
                _require_str(payload, "platform"),
                kit=_optional_str(payload, "kit"),
                source_url=_optional_str(payload, "source_url"),
            )
            return manifest.to_dict()
        except LibraryError as exc:
            raise _error_response(exc) from exc

    @app.delete("/api/modules/{slug}")
    def module_delete(slug: str) -> dict:
        """删除模块：整个目录移除。"""
        try:
            delete_module(_library_dir(context), slug)
            return {"ok": True}
        except LibraryError as exc:
            raise _error_response(exc) from exc

    # ------------------------------------------------------------------
    # 母版提炼（工单 08）：导入旧工程 → AI 报告 → 确认入库
    # ------------------------------------------------------------------

    @app.post("/api/masters/scan")
    def masters_scan(payload: dict) -> list[dict]:
        """逐个扫描导入的旧工程：平台检测 + 文件清单 + 配置摘要。"""
        try:
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
        except MasterError as exc:
            raise _error_response(exc) from exc

    @app.post("/api/masters/distill")
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
        events: Queue[_QueueItem] = Queue(maxsize=_SSE_QUEUE_MAXSIZE)

        def emit(event: ProgressEvent) -> None:
            # 旁路（工单 01 决策）：客户端断开后队列满 → 丢进度事件，不堵提炼线程
            try:
                events.put_nowait(event)
            except Full:
                pass

        def run() -> None:
            try:
                projects = [scan_project(Path(d)) for d in project_dirs]
                report = distill_master(llm, platform, projects, emit)
                _put_terminal(events, EVENT_DONE, report.to_dict())
            except Exception as exc:
                _put_terminal(events, EVENT_ERROR, _error_message(exc))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        def stream() -> Iterator[str]:
            while True:
                item = events.get()
                if isinstance(item, ProgressEvent):
                    yield _sse_frame(item.type, asdict(item))
                    continue
                kind, data = item
                if kind == EVENT_DONE:
                    yield _sse_frame(EVENT_DONE, data)
                else:
                    yield _sse_frame(EVENT_ERROR, {"message": data})
                return

        return StreamingResponse(stream(), headers={"Content-Type": "text/event-stream"})

    @app.post("/api/masters/confirm")
    def masters_confirm(payload: dict) -> dict:
        """确认报告：落盘母版候选 → 结构分析 → 入库（事务在 confirm_distillation）。"""
        try:
            project_dirs = [Path(d) for d in _require_str_list(payload, "project_dirs")]
            meta = confirm_distillation(_masters_dir(context), project_dirs, payload)
            return {
                "platform": meta.platform,
                "sources": list(meta.sources),
                "warnings": list(meta.warnings),
            }
        except (MasterError, KeilProjectError, CcsProjectError, OSError) as exc:
            raise _error_response(exc) from exc

    @app.get("/api/masters")
    def masters() -> list[dict]:
        """浏览母版库（每平台一个母版）。"""
        try:
            return [
                {"platform": m.platform, "sources": list(m.sources), "warnings": list(m.warnings)}
                for m in list_masters(_masters_dir(context))
            ]
        except MasterError as exc:
            raise _error_response(exc) from exc

    @app.delete("/api/masters/{platform}")
    def master_delete(platform: str) -> dict:
        try:
            delete_master(_masters_dir(context), platform)
            return {"ok": True}
        except MasterError as exc:
            raise _error_response(exc) from exc

    # ------------------------------------------------------------------
    # 设置：读写配置，写入后即时生效（后续请求即用新配置）
    # ------------------------------------------------------------------

    @app.get("/api/settings")
    def settings_get() -> dict:
        """读取设置；API key 只回掩码，不回明文。"""
        config = _current_config(context)
        api_key = config.api_key if config is not None else ""
        return {
            "configured": config is not None,
            "base_url": (config.base_url if config is not None else ""),
            "model": (config.model if config is not None else ""),
            "api_key": _mask_api_key(api_key),
            "module_library_dir": str(
                config.module_library_dir if config is not None else AppConfig().module_library_dir
            ),
            "masters_dir": str(
                config.masters_dir if config is not None else AppConfig().masters_dir
            ),
            "config_path": str(context.config_path),
        }

    @app.put("/api/settings")
    def settings_put(payload: dict) -> dict:
        """保存设置并立即生效；api_key 收到掩码说明用户没改，沿用旧值。"""
        existing = _current_config(context)
        api_key = str(payload.get("api_key", "")).strip()
        # 空或等于当前 key 的掩码形态 → 用户没改 key，沿用旧值
        if not api_key or (
            existing is not None and api_key == _mask_api_key(existing.api_key)
        ):
            if existing is None:
                raise HTTPException(400, "首次配置必须填写 API key")
            api_key = existing.api_key
        try:
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
        except ConfigError as exc:
            raise HTTPException(400, str(exc)) from exc

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
