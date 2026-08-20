"""生成上下文清单：随工程落盘的纯新增隐藏文件 + 读侧 + 历史目录反推（工单 revise-deepen/01）。

**写侧**：generate 尾部把本次生成的输入（题面 / 平台 / 模块 slugs / 绑定 /
多实例 / 副产物模板 / Q&A / 功能需求清单 / 参考条目 / main.c / 时间 / 工具版本）
落盘为工程根 `.contest_context.json`——纯新增文件，不触碰任何既有生成文件
（README.md 先例），缺省路径（不传任何上下文字段）时既有文件逐字节不变。

**读侧**：`read_context_fields` 缺字段 / 旧版本清单向后兼容（缺字段 = 补空串/
空集，由调用方走反推或要求用户补，不崩）；坏 JSON / 非对象 → ContextError
（400 中文）。

**反推**（历史工程无清单）：`infer_context` 从产物树回读——平台 = 工程配置
文件后缀识别（platforms.PLATFORM_CONFIG_FILE_SUFFIXES 单源）；模块 =
modules/<slug>/ 目录名；绑定 = stm32 pin_config.h 宏现值（写侧逆运算：遍历
板排针引脚计算宏值与现值完全匹配）或 mspm0.syscfg $assign 落点值
（syscfg_path_matches 原语）；main.c 现读。题面 / Q&A / 需求清单反推不了 →
空值 + missing 标记（前端要求用户补）。

**形状校验**：`validate_context_fields` 平台词表 / slugs 库内存在性 / 绑定
键形状 / 列表字段类型，非法 → ContextError（400 中文，加载 API 与读侧共用）。

反推是尽力而为：单个角色绑定回读失败（宏不在 pin_config.h / 落点不匹配 /
母版漂移）静默跳过，不阻断整树加载——历史工程允许部分恢复，缺失部分由
前端手动勾选兜底；平台识别失败与清单损坏才大声失败（这两项无兜底路径）。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .boards import BoardError, board_for_platform, board_pin, pin_capability_instances
from .library import list_modules
from .manifest import ModuleManifest
from .pin_bindings import PinBindingError
from .pinwriter import PIN_CONFIG_FILENAME, _DEFINE_LINE_RE, _stm32_macro_value
from .platforms import KNOWN_PLATFORMS, PLATFORM_CONFIG_FILE_SUFFIXES
from .syscfg_model import MSPM0_SYSCFG_FILENAME, parse_syscfg, syscfg_path_matches

# 清单文件名（生成写侧单源，generator / 加载 API / 前端共用）
CONTEXT_MANIFEST_FILENAME = ".contest_context.json"

# 清单版本：向后兼容读（未知版本容忍：只读已知字段，缺省补空）
CONTEXT_MANIFEST_VERSION = 1


class ContextError(ValueError):
    """上下文清单损坏 / 形状非法 / 平台无法识别（400 中文，登记 errors.py）。"""


def build_context_fields(
    *,
    platform: str,
    slugs: Sequence[str],
    main_c: str,
    problem_text: str = "",
    topic_id: str = "",
    qa_text: str = "",
    requirements: Sequence[Mapping[str, Any]] | None = None,
    references: Sequence[str] = (),
    bindings: Mapping[str, str] | None = None,
    instances: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    python_templates: Mapping[str, str] | None = None,
    tool_version: str = "",
) -> dict[str, Any]:
    """组装清单字段（写侧单源：generate 尾部与测试共用同一形状）。

    字段 = spec 清单（题面 / 平台 / slugs / 绑定 / 多实例 / 副产物模板 /
    Q&A / 功能需求清单 / 参考条目 / 生成时间 / 工具版本）+ 两个输入类扩展：
    main_c（生成时骨架快照，深化工单消费）与 topic_id（历史赛题入口）。
    可选字段缺省 = 空/空集（缺省生成路径 = 旧行为逐字节，清单内容自洽：
    什么也没传就记什么也没用）。生成结果类字段（score_points 等）不入清单
    ——清单只记生成输入，结果可随时从产物树重算。
    """
    return {
        "version": CONTEXT_MANIFEST_VERSION,
        "platform": platform,
        "slugs": list(slugs),
        "main_c": main_c,
        "problem_text": problem_text,
        "topic_id": topic_id,
        "qa_text": qa_text,
        "requirements": list(requirements or ()),
        "references": list(references),
        "bindings": dict(bindings or {}),
        "instances": {slug: list(items) for slug, items in (instances or {}).items()},
        "python_templates": dict(python_templates or {}),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tool_version": tool_version,
    }


def write_context_manifest(output_dir: Path, fields: Mapping[str, Any]) -> Path:
    """清单落盘（纯新增文件，工程根；写失败由 generate 的 rmtree 兜底）。"""
    path = output_dir / CONTEXT_MANIFEST_FILENAME
    path.write_text(
        json.dumps(dict(fields), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_context_manifest(output_dir: Path) -> dict[str, Any] | None:
    """读清单原始字段；无清单 = None；坏 JSON / 非对象 = ContextError（400）。

    未知版本容忍（只读已知字段，见 read_context_fields）；版本字段缺失同样
    容忍（旧版本清单），不在这里拒绝。
    """
    path = output_dir / CONTEXT_MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextError(
            f"上下文清单 {CONTEXT_MANIFEST_FILENAME} 损坏（不是合法 JSON）：{exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ContextError(
            f"上下文清单 {CONTEXT_MANIFEST_FILENAME} 必须是 JSON 对象"
        )
    return data


def read_context_fields(output_dir: Path) -> dict[str, Any] | None:
    """读侧（缺字段 / 旧版本向后兼容）：清单 → 完整字段（缺字段补空）。

    与 build_context_fields 形状对齐——缺字段 = 补空串/空集（调用方据此走
    反推或要求用户补，不崩）；未知版本字段只读已知键。返回 None = 无清单。
    """
    data = load_context_manifest(output_dir)
    if data is None:
        return None
    return {
        "version": data.get("version", 1),
        "platform": data.get("platform", ""),
        "slugs": data.get("slugs", []) if isinstance(data.get("slugs"), list) else [],
        "main_c": data.get("main_c", "") if isinstance(data.get("main_c"), str) else "",
        "problem_text": (
            data.get("problem_text", "") if isinstance(data.get("problem_text"), str) else ""
        ),
        "topic_id": data.get("topic_id", "") if isinstance(data.get("topic_id"), str) else "",
        "qa_text": data.get("qa_text", "") if isinstance(data.get("qa_text"), str) else "",
        "requirements": (
            data.get("requirements", [])
            if isinstance(data.get("requirements"), list)
            else []
        ),
        "references": (
            data.get("references", []) if isinstance(data.get("references"), list) else []
        ),
        "bindings": (
            data.get("bindings", {}) if isinstance(data.get("bindings"), dict) else {}
        ),
        "instances": (
            data.get("instances", {}) if isinstance(data.get("instances"), dict) else {}
        ),
        "python_templates": (
            data.get("python_templates", {})
            if isinstance(data.get("python_templates"), dict)
            else {}
        ),
        "generated_at": (
            data.get("generated_at", "")
            if isinstance(data.get("generated_at"), str)
            else ""
        ),
        "tool_version": (
            data.get("tool_version", "") if isinstance(data.get("tool_version"), str) else ""
        ),
    }


def missing_fields_for(fields: Mapping[str, Any]) -> list[str]:
    """修订 / 深化流程必需的字段缺失清单（spec「缺字段 = 走反推或要求补」）。

    有清单但字段为空（旧版本清单 / 生成时没填）与反推不了同样标记——前端
    据此提示用户补：题面（影响分析必需）、功能需求清单（深化必需）、模块集
    （产物树 modules/ 缺失 = 全内嵌或手工工程，需手动勾选兜底）；Q&A / 参考
    条目为空 = 没有即可，不标记（避免常态误报）。
    """
    missing: list[str] = []
    if not fields.get("problem_text"):
        missing.append("problem_text")
    if not fields.get("requirements"):
        missing.append("requirements")
    if not fields.get("main_c"):
        missing.append("main_c")
    if not fields.get("slugs"):
        missing.append("slugs")
    return missing


# ---------------------------------------------------------------------------
# 历史目录反推（无清单时）：平台 / 模块 / 绑定 / main.c 尽力回读
# ---------------------------------------------------------------------------


def infer_context(
    output_dir: Path, module_library_dir: Path
) -> tuple[dict[str, Any], list[str]]:
    """从产物树反推上下文字段（无清单路径）。

    返回 (fields, missing)——missing = 反推不了、需要用户补的字段名
    （problem_text / topic_id / qa_text / requirements 恒缺：产物里没有）。

    平台 = 工程配置文件后缀识别（两种配置都有或都没有 → ContextError 400，
    无兜底路径）；模块 = modules/<slug>/ 目录名（生成契约，直接读）；绑定 =
    平台写侧逆运算（尽力而为，单角色失败静默跳过）；main_c 现读（无 = 空串，
    加载 API 返回 missing 提示）。
    """
    platform = _infer_platform(output_dir)
    slugs = _infer_slugs(output_dir)
    manifests = _load_known_manifests(module_library_dir, slugs)
    bindings = _infer_bindings(output_dir, platform, manifests)
    main_c = read_project_main_c(output_dir)
    fields = build_context_fields(
        platform=platform,
        slugs=slugs,
        main_c=main_c,
        bindings=bindings,
    )
    return fields, missing_fields_for(fields)


def _infer_platform(output_dir: Path) -> str:
    """平台识别：工程配置文件后缀（platforms 表单源，master._detect_platform
    同款：任意层级 rglob）。两者都有 / 都没有 → ContextError（400 中文）。"""
    found = [
        platform
        for platform in KNOWN_PLATFORMS
        if any(
            any(output_dir.rglob(f"*{suffix}"))  # rglob 是生成器，需内层 any 判空
            for suffix in PLATFORM_CONFIG_FILE_SUFFIXES[platform]
        )
    ]
    if len(found) > 1:
        raise ContextError("工程同时含 stm32 与 mspm0 的工程配置文件，无法判定平台")
    if found:
        return found[0]
    raise ContextError("工程里没有工程配置文件（.uvprojx / .cproject / .project），无法判定平台")


def _infer_slugs(output_dir: Path) -> list[str]:
    """模块 = 产物树 modules/ 下的目录名（生成契约 modules/<slug>/；排序确定）。"""
    modules_dir = output_dir / "modules"
    if not modules_dir.is_dir():
        return []
    return sorted(p.name for p in modules_dir.iterdir() if p.is_dir())


def _load_known_manifests(module_library_dir: Path, slugs: Sequence[str]) -> list[ModuleManifest]:
    """库内模块 manifest 加载（反推绑定用）；库外 slug（历史手工目录）跳过——
    其绑定无法回读，留给前端手动配置兜底。库不存在 / 非目录 = 空清单（不崩）。"""
    if not module_library_dir.is_dir():
        return []
    known = {m.slug for m in list_modules(module_library_dir)}
    manifests: list[ModuleManifest] = []
    for slug in slugs:
        if slug not in known:
            continue
        try:
            manifests.append(ModuleManifest.load(module_library_dir / slug))
        except Exception:
            continue  # 单模块 manifest 损坏不阻断整树反推
    return manifests


def read_project_main_c(output_dir: Path) -> str:
    """main.c 现读（工程根；缺失 = 空串）。加载 API 两条路径共用——有清单也
    现读（清单里是生成时快照，用户手改后必须反映当前内容）。"""
    path = output_dir / "main.c"
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _infer_bindings(
    output_dir: Path, platform: str, manifests: Sequence[ModuleManifest]
) -> dict[str, str]:
    """绑定回读（尽力而为）：stm32 = pin_config.h 宏现值逆运算；mspm0 =
    syscfg $assign 落点值。单角色回读失败静默跳过（不阻断整树加载）。

    只回读"与默认值不同的"绑定（写侧"不变不写"语义的对偶——宏值/落点值
    等于默认推导值 = 未绑定，载荷省略；生成契约：绑定载荷只含覆盖值）。
    """
    if platform == "stm32":
        return _infer_stm32_bindings(output_dir, manifests)
    if platform == "mspm0":
        return _infer_mspm0_bindings(output_dir, manifests)
    return {}


def _infer_stm32_bindings(
    output_dir: Path, manifests: Sequence[ModuleManifest]
) -> dict[str, str]:
    """stm32 绑定回读：pin_config.h 宏现值 → 绑定引脚（写侧逆运算）。

    对每个角色声明：宏现值 = pin_config.h 中 macros 现值；先与"默认引脚 +
    默认实例"的推导值比对——全等 = 未绑定（跳过）；否则遍历板排针引脚计算
    宏值，与现值**完全匹配**的引脚 = 绑定引脚（宏组合唯一标识引脚；匹配
    不到 = 母版漂移/手工改过，跳过不报错）。无 pin_config.h / 无板定义 =
    空载荷（防御，不崩）。
    """
    path = output_dir / PIN_CONFIG_FILENAME
    if not path.is_file():
        return {}
    try:
        board = board_for_platform("stm32")
    except BoardError:
        return {}
    index: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _DEFINE_LINE_RE.match(line)
        if m:
            index[m.group("name")] = m.group("rest").strip().split(None, 1)[0]

    bindings: dict[str, str] = {}
    for manifest in manifests:
        entry = manifest.platforms.get("stm32")
        if entry is None:
            continue
        for decl in entry.pins:
            if not decl.macros:
                continue
            role_key = f"{manifest.slug}.{decl.id}"
            current = [index.get(macro) for macro in decl.macros]
            if any(value is None for value in current):
                continue  # 宏不在 pin_config.h = 数据不可控于此文件，跳过
            default_pin = board_pin(board, decl.default)
            default_instances = (
                pin_capability_instances(default_pin, decl.type)
                if default_pin is not None
                else ()
            )
            try:
                default_values = [
                    _stm32_macro_value(role_key, macro, decl.default, default_instances)
                    for macro in decl.macros
                ]
            except PinBindingError:
                continue  # 默认引脚实例歧义 → 该角色无法判定绑定，跳过（尽力而为）
            if default_values == current:
                continue  # 未绑定（默认值，写侧 no-op 语义）
            bound = _match_stm32_pin(board, role_key, decl.macros, current)
            if bound is not None:
                bindings[role_key] = bound
    return bindings


def _match_stm32_pin(
    board: Any, role_key: str, macros: Sequence[str], current: Sequence[str | None]
) -> str | None:
    """宏现值 → 引脚（遍历板排针引脚计算宏值，完全匹配 = 命中）。

    单实例歧义（默认/候选引脚多实例）时 _stm32_macro_value 抛 PinBindingError
    ——该角色回读失败，跳过（尽力而为）。返回 None = 未匹配。
    """
    for pin in board.pins:
        instances = pin_capability_instances(pin, _role_type_for_macros(macros))
        try:
            values = [
                _stm32_macro_value(role_key, macro, pin.name, instances)
                for macro in macros
            ]
        except PinBindingError:
            continue  # 候选引脚实例歧义（多实例）→ 该引脚算不出宏值，跳过
        if values == list(current):
            return pin.name
    return None


def _role_type_for_macros(macros: Sequence[str]) -> str:
    """宏尾形 → 角色类型（能力实例推导用；_TIM/_CH → pwm、_UART/_INST →
    uart_tx、_LINE/_EXTI → enc、其余（_GPIO/_PORT/_PIN）→ 无实例类型空串
    （pin_capability_instances 空实例 = 只查类型，gpio 类角色天然正确）。"""
    if any(m.endswith(("_TIM", "_CH")) for m in macros):
        return "pwm"
    if any(m.endswith(("_UART", "_INST")) for m in macros):
        return "uart_tx"
    if any(m.endswith(("_LINE", "_EXTI")) for m in macros):
        return "enc"
    return ""


def _infer_mspm0_bindings(
    output_dir: Path, manifests: Sequence[ModuleManifest]
) -> dict[str, str]:
    """mspm0 绑定回读：syscfg $assign 落点值（syscfg_path_matches 原语）。

    对每个角色声明：遍历 $assign 落点，路径匹配（角色类型 × slug 消费实例
    表）→ 读引脚值；值 != 声明默认值 → 绑定载荷。找不到落点 = 跳过
    （母版漂移/该角色不在 syscfg，尽力而为）。无 syscfg = 空载荷。
    """
    path = output_dir / MSPM0_SYSCFG_FILENAME
    if not path.is_file():
        return {}
    try:
        model = parse_syscfg(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}  # syscfg 解析失败（历史手工工程）：绑定无法回读，跳过
    bindings: dict[str, str] = {}
    for manifest in manifests:
        entry = manifest.platforms.get("mspm0")
        if entry is None:
            continue
        for decl in entry.pins:
            role_key = f"{manifest.slug}.{decl.id}"
            for assign in model.assigns:
                if not syscfg_path_matches(decl.type, decl.id, manifest.slug, assign.path):
                    continue
                if assign.pin != decl.default:
                    bindings[role_key] = assign.pin
                break
    return bindings


# ---------------------------------------------------------------------------
# 形状校验（读侧与加载 API 共用）：平台词表 / slugs 存在性 / 绑定形状
# ---------------------------------------------------------------------------


def validate_context_fields(
    fields: Mapping[str, Any], module_library_dir: Path
) -> None:
    """上下文字段形状校验（加载 API 的 400 关口）：平台词表 / slugs 库内
    存在性 / bindings 键形状与值类型 / 列表字段类型。非法 → ContextError。

    反推路径的库外 slug 同样在这里拦（校验失败 = 前端手动勾选兜底入口）。
    """
    platform = fields.get("platform", "")
    if platform not in KNOWN_PLATFORMS:
        raise ContextError(
            f"未知平台 {platform!r}（应为 {'、'.join(KNOWN_PLATFORMS)}）"
        )
    slugs = fields.get("slugs")
    if not isinstance(slugs, list) or any(not isinstance(s, str) for s in slugs):
        raise ContextError("slugs 必须是字符串数组")
    if module_library_dir.is_dir():
        known = {m.slug for m in list_modules(module_library_dir)}
        unknown = [slug for slug in slugs if slug not in known]
        if unknown:
            raise ContextError(
                "模块不在模块库内："
                + "、".join(unknown)
                + " —— 请在模块勾选处手动核对"
            )
    bindings = fields.get("bindings")
    if not isinstance(bindings, dict) or any(
        not isinstance(k, str) or k.count(".") != 1 or not isinstance(v, str)
        for k, v in bindings.items()
    ):
        raise ContextError(
            "bindings 必须是 JSON 对象（形如 {\"模块.角色\": \"引脚\"}）"
        )
    for key, field in (
        ("requirements", list),
        ("references", list),
        ("instances", dict),
        ("python_templates", dict),
        ("score_points", list),
    ):
        value = fields.get(key)
        if value is not None and not isinstance(value, field):
            raise ContextError(f"{key} 形状非法（应为 {field.__name__}）")
