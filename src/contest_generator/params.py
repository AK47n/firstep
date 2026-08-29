"""参数速调（工单 param-tune/01）：main.c 可调数值参数的识别、落盘与确定性改值。

独立于任务清单的「改一个数 → 编译 → 烧录」短链路（spec：学生上板调试最频繁
的动作；现状改值要整任务重跑一次 LLM 调用，十几分钟一遍）。识别走一次 LLM
（llm.scan_params），改值零 LLM——参数声明行（anchor）被 scan 时逐字节记录，
apply 时按 anchor 定位做确定性替换，其余代码一字不动。

与 idea_chat / drafts 同构的读写契约：`.contest_params.json`（version=1、
原子 .tmp→replace）；无文件 = 未识别过（read 返回空，不 400）；坏 JSON /
结构非法 = TaskError（400 中文）。

防环：本模块 from task_progress import TaskError（task_progress 不 import
params；与 llm → task_progress 边同向）。deepen / revision 的导入放在函数内
（与 task_progress.run_task 的函数内导入同先例——模块级环风险为零）。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from .events import EVENT_PARAM_APPLYING, EVENT_PARAM_SCANNING, ProgressEvent
from .task_progress import TaskError

if TYPE_CHECKING:
    from .llm import LLM
    from .sse import SseEmitter

# 参数表文件名与版本（读回侧按 version 兼容，当前仅 v1）
PARAMS_FILENAME = ".contest_params.json"
PARAMS_VERSION = 1

# 改值长度上限（spec：只做非空 + 长度校验；64 字符足够覆盖 1.2f / 3000UL 等）
MAX_VALUE_LENGTH = 64

# C 标识符字符集（旧值必须是完整字面量 token：左右邻都不是标识符字符——
# 防止 "#define THRESHOLD 800" 里 "80" 也恰出现 1 次被误当完整值）
_IDENT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


def _old_value_token_ok(anchor: str, old_value: str) -> bool:
    """old_value 是否作为完整字面量唯一出现于 anchor（锚校验单源）。

    条件：① 在 anchor 中恰好出现 1 次；② 该次出现的左右邻都不是标识符字符
    （[A-Za-z0-9_]）——保证 "80" 在 "#define THRESHOLD 800" 中判非完整
    （右邻 '0'），替换才不会把 800 变 9000 击穿「确定性改值」；带后缀字面量
    同理（"800" 在 "800UL" 中右邻 'U' → 非完整，AI 应给 "800UL"）。

    build_params（识别域判决）与 apply_param_change（读回文件防御）共用。
    """
    if anchor.count(old_value) != 1:
        return False
    idx = anchor.find(old_value)
    left_ok = idx == 0 or anchor[idx - 1] not in _IDENT_CHARS
    right = idx + len(old_value)
    right_ok = right >= len(anchor) or anchor[right] not in _IDENT_CHARS
    return left_ok and right_ok


@dataclass(frozen=True)
class ParamItem:
    """一个可调数值参数（spec：识别产物，锚 = 声明行原文）。

    name = 参数标识（如 THRESHOLD）；label = 中文含义（如"循迹阈值"）；
    old_value = 当前值原文（如 800 / 1.2f / 3000UL）；anchor = 声明所在行
    原文（**必须逐字节存在于 main.c 中，且其中 old_value 恰好出现 1 次**——
    build_params 硬校验，不满足 → 整次重问）；unit / range_hint 宽松可选
    （缺省空串）。front 应用前 read 端点逐条重验 anchor 给 valid 标志。
    """

    name: str
    label: str
    old_value: str
    anchor: str
    unit: str = ""
    range_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "old_value": self.old_value,
            "anchor": self.anchor,
            "unit": self.unit,
            "range_hint": self.range_hint,
        }


@dataclass(frozen=True)
class ParamList:
    """参数表（version / generated_at / params）。

    params 可为空元组（识别结果无参数 = 合法——「未发现可调参数」，spec 用户
    故事 6；空表**不落盘**（run_param_scan 跳过写盘）：无文件 = 未识别过，
    空表不产生持久化状态，前端以「已识别但无参数」区分两态）。
    """

    version: int
    generated_at: str
    params: tuple[ParamItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "params": [item.to_dict() for item in self.params],
        }


def _now_stamp() -> str:
    """时间戳（与 idea_chat._now_stamp 同款字符串形状）。"""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def empty_params() -> ParamList:
    """空参数表（未识别过 / 识别结果无参数）。"""
    return ParamList(version=PARAMS_VERSION, generated_at=_now_stamp(), params=())


def build_params(raw: Any, main_c: str) -> ParamList:
    """LLM 输出的域判决（spec：build_params(raw, main_c)）。

    raw = LLM JSON 解析后的对象（必须 dict 且含 params 列表）；逐条校验：
    ① name / label / old_value / anchor 必须非空字符串；② anchor 必须逐字节
    存在于 main_c；③ anchor 内 old_value 恰好出现 1 次（多了 = 无法确定替换
    点，误替换风险 > 价值，整次重问）；unit / range_hint 宽松（非字符串→空串，
    可缺省）。空参数表合法。任何校验失败 → TaskError（中文指明条目）。

    与 build_task_plan 同哲学：域判决错误由 llm 层翻译回 LLMError（_retry_parse
    重问），本模块不 import LLMError（防环）。
    """
    if not isinstance(raw, dict):
        raise TaskError("参数识别结果必须是 JSON 对象")
    raw_params = raw.get("params")
    if not isinstance(raw_params, list):
        raise TaskError("参数识别结果缺少 params 列表")
    items: list[ParamItem] = []
    for index, raw_item in enumerate(raw_params, 1):
        if not isinstance(raw_item, dict):
            raise TaskError(f"第 {index} 个参数不是对象")
        name = raw_item.get("name")
        label = raw_item.get("label")
        old_value = raw_item.get("old_value")
        anchor = raw_item.get("anchor")
        for field, value in (
            ("name", name),
            ("label", label),
            ("old_value", old_value),
            ("anchor", anchor),
        ):
            if not isinstance(value, str) or not value.strip():
                raise TaskError(f"第 {index} 个参数缺少 {field}（模型未输出或为空串）")
        if anchor not in main_c:
            raise TaskError(
                f"第 {index} 个参数 {name} 的锚不在 main.c 中"
                "——模型输出的 anchor 与源码不一致"
            )
        if anchor.count(old_value) != 1:
            raise TaskError(
                f"第 {index} 个参数 {name} 的锚中当前值 {old_value} 出现"
                f" {anchor.count(old_value)} 次（必须恰好 1 次才能确定性替换）"
            )
        if not _old_value_token_ok(anchor, old_value):
            raise TaskError(
                f"第 {index} 个参数 {name} 的当前值 {old_value} 不是锚中的完整"
                "字面量（如带后缀的 800UL / 1.2f 必须写全）——无法确定性替换"
            )
        unit = raw_item.get("unit")
        range_hint = raw_item.get("range_hint")
        items.append(
            ParamItem(
                name=name.strip(),
                label=label.strip(),
                old_value=old_value,
                anchor=anchor,
                unit=unit.strip() if isinstance(unit, str) else "",
                range_hint=range_hint.strip() if isinstance(range_hint, str) else "",
            )
        )
    return ParamList(version=PARAMS_VERSION, generated_at=_now_stamp(), params=tuple(items))


def load_params_file(output_dir: Path) -> ParamList | None:
    """读参数表文件；无文件 = None；坏 JSON / 非对象 → TaskError（400 中文）。

    与 load_idea_chat_file / load_drafts_file 同构（参数 = 输出目录，非完整
    文件路径）：JSON 解析错误与结构错误分开提示（「损坏」vs「必须是 JSON
    对象」），条目级坏数据靠 build_params 校验兜底（本函数只认顶层形状——
    v1 只有 version/generated_at/params 三键，多余键忽略）。
    """
    path = output_dir / PARAMS_FILENAME
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskError(
            f"参数表 {PARAMS_FILENAME} 损坏（不是合法 JSON）：{exc}——请重新识别参数"
        ) from exc
    if not isinstance(raw, dict):
        raise TaskError(f"参数表 {path.name} 必须是 JSON 对象")
    params_raw = raw.get("params")
    if not isinstance(params_raw, list):
        raise TaskError("参数表 params 必须是列表——请重新识别参数")
    sentinel = object()
    generated_at = raw.get("generated_at", sentinel)
    items: list[ParamItem] = []
    for raw_item in params_raw:
        if not isinstance(raw_item, dict):
            continue  # 条目级容错：坏条目忽略（与 idea_chat/drafts 同先例）
        # 关键字段必须都是字符串才能进表（非字符串 = 坏数据，忽略——与
        # build_params 的「宁拒收不静默」同哲学，读回侧不救活坏数据）
        if not all(
            isinstance(raw_item.get(field), str)
            for field in ("name", "label", "old_value", "anchor")
        ):
            continue
        items.append(
            ParamItem(
                name=raw_item["name"],
                label=raw_item["label"],
                old_value=raw_item["old_value"],
                anchor=raw_item["anchor"],
                unit=(
                    raw_item.get("unit", "")
                    if isinstance(raw_item.get("unit"), str)
                    else ""
                ),
                range_hint=(
                    raw_item.get("range_hint", "")
                    if isinstance(raw_item.get("range_hint"), str)
                    else ""
                ),
            )
        )
    return ParamList(
        version=raw.get("version", PARAMS_VERSION),
        generated_at=(
            str(generated_at) if generated_at is not sentinel else _now_stamp()
        ),
        params=tuple(items),
    )


def params_path(output_dir: Path) -> Path:
    """参数表文件路径（输出目录根部）。"""
    return output_dir.joinpath(PARAMS_FILENAME)


def read_params(output_dir: Path) -> ParamList:
    """读参数表；无文件 = 空表（未识别过，不影响独立通道的可用性）。"""
    loaded = load_params_file(output_dir)
    return loaded if loaded is not None else empty_params()


def params_with_valid(param_list: ParamList, main_c: str) -> list[dict[str, Any]]:
    """参数表 → 带 valid 的 dict 列表（单源，工单 params-chat-ai/01 评审整改）。

    逐条重验锚：valid = main_c 非空 且 anchor 逐字节仍在 main_c 中 且
    old_value 仍在锚内（锚失效 = main_c 被任务执行 / 手工编辑改动，前端禁用
    该行并提示「请重新识别」）。/api/tasks/params/read 与 /api/params/chat/send
    共用——两处曾各写一份循环，改一处忘另一处即分叉。
    """
    out: list[dict[str, Any]] = []
    for item in param_list.params:
        valid = bool(main_c) and item.anchor in main_c and item.old_value in item.anchor
        out.append({**item.to_dict(), "valid": valid})
    return out


def write_params(output_dir: Path, param_list: ParamList) -> Path:
    """原子写参数表（.tmp → replace，与 idea_chat/drafts 同构）；返回文件路径。"""
    path = params_path(output_dir)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(param_list.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def find_param(param_list: ParamList, name: str) -> ParamItem | None:
    """按 name 查参数（应用路由用）；找不到 = None（调用方 400）。"""
    for item in param_list.params:
        if item.name == name:
            return item
    return None


def validate_param_value(new_value: str) -> str:
    """新值校验（单源：apply_param_change 与 webapp apply 路由共用——后者
    要在路由体先做 400 分级，不能等到 SSE run 内才流 error）。

    规则（spec 用户故事 7：只做非空 + 长度校验——格式自由：数字 / 1.2f /
    3000UL 均放行）：非空字符串（strip 后）且 ≤ MAX_VALUE_LENGTH；不满足 →
    TaskError（中文）。返回 strip 后的新值（写入用）。
    """
    if not isinstance(new_value, str) or not new_value.strip():
        raise TaskError("新值不能为空")
    if len(new_value) > MAX_VALUE_LENGTH:
        raise TaskError(f"新值过长（超过 {MAX_VALUE_LENGTH} 字符）")
    return new_value.strip()


def apply_param_change(main_c: str, param: ParamItem, new_value: str) -> str:
    """确定性改值（纯函数，零 LLM——spec 关键决策）。

    找 anchor 在 main_c 的首次出现位置 → 仅替换 anchor 子串内 old_value 的
    第一处（str.replace 默认全换会伤到同值多次出现；锚内恰 1 次由 build_params
    保证，此处仍用 count=1 保守替换）→ 拼接。锚失效（anchor 已不在 main_c
    或 old_value 已不在锚内 / 不是完整字面量——main.c 被任务执行 / 手工编辑
    改动，或读回的旧表数据被手改）→ TaskError 中文提示「请重新识别参数」
    （spec 用户故事 5：应用时后端校验拒绝）。

    new_value 先过 validate_param_value（单源校验）；old_value 走
    _old_value_token_ok（与 build_params 同源——防子串式旧值击穿确定性）。
    """
    new_value = validate_param_value(new_value)
    anchor = param.anchor
    if anchor not in main_c:
        raise TaskError(
            "参数锚已失效（main.c 可能被改动）——请重新识别参数"
        )
    idx = main_c.index(anchor)
    if not _old_value_token_ok(anchor, param.old_value):
        raise TaskError(
            "参数锚已失效（old_value 不在锚中或不是完整字面量）——请重新识别参数"
        )
    new_anchor = anchor.replace(param.old_value, new_value, 1)
    return main_c[:idx] + new_anchor + main_c[idx + len(anchor):]


def _refresh_param_after_apply(
    param_list: ParamList, name: str, new_value: str, disk_main_c: str
) -> ParamList:
    """apply 成功后的参数表回写（纯函数，评审整改：apply 不回写表 → /read
    重验把刚改成功的参数标「锚已失效」+ 回填旧值，与「参数修改完成」矛盾）。

    规则：找到 name 对应项 → new_anchor = anchor 内 old_value 替换为 new_value
    （与 apply_param_change 同构，count=1）；new_anchor **逐字节存在于磁盘
    main.c** 才更新该项（old_value=new_value、anchor=new_anchor）——编译失败
    的 AI 修复轮可能改写了该值，此时读盘重验失败 → 保持旧表（前端标失效 =
    诚实提示重新识别）；其余项原样。找不到 name / 无变化 → 返回原对象引用，
    调用方无需写盘（写盘前判 is 或逐字段比较由调用方决定）。
    """
    changed = False
    items: list[ParamItem] = []
    for item in param_list.params:
        if item.name != name:
            items.append(item)
            continue
        new_anchor = item.anchor.replace(item.old_value, new_value, 1)
        if new_anchor in disk_main_c and new_anchor != item.anchor:
            items.append(
                ParamItem(
                    name=item.name,
                    label=item.label,
                    old_value=new_value,
                    anchor=new_anchor,
                    unit=item.unit,
                    range_hint=item.range_hint,
                )
            )
            changed = True
        else:
            items.append(item)
    if not changed:
        return param_list
    return ParamList(
        version=param_list.version,
        generated_at=param_list.generated_at,
        params=tuple(items),
    )


def run_param_scan(
    *,
    llm: LLM,
    main_c: str,
    module_interfaces: Sequence[str],
    output_dir: Path,
    emit: SseEmitter,
) -> ParamList:
    """参数识别编排（spec：scan 一次 LLM → 域判决 → 落盘）。

    事件序列：param_scanning（LLM 识别中，分钟级）；param_result 由 webapp
    路由在 done 前发射（与 idea_result 同款：分析端点序列 idea_analyzing →
    idea_result → done，idea_result 在路由层）。
    """
    emit.progress(ProgressEvent(type=EVENT_PARAM_SCANNING))
    param_list = llm.scan_params(main_c=main_c, module_interfaces=tuple(module_interfaces))
    if not isinstance(param_list, ParamList):
        # 协议契约：scan_params 返回 ParamList（域判决已在 llm 层完成）；
        # 假 LLM / 未来实现偏离契约时兜底拒绝，不静默写坏表。
        raise TaskError("参数识别结果形状非法（应为参数表）")
    if param_list.params:
        # 空表不落盘（spec 用户故事 6 + 评审整改）：无文件 = 未识别过，
        # 空表落盘会让 /read 的 valid 重验与「尚未识别」文案两态无法区分。
        write_params(output_dir, param_list)
    return param_list


def run_param_apply(
    *,
    llm: LLM,
    param: ParamItem,
    new_value: str,
    main_c: str,
    output_dir: Path,
    work_root: Path,
    platform: str,
    module_slugs: Sequence[str],
    uv4_override: str,
    make_override: str,
    emit: SseEmitter,
) -> dict[str, Any]:
    """参数改值编排（spec：改值零 LLM——确定性替换；编译验证闭环与任务执行
    共用 verify_compile_tail 尾段，其首轮编译失败自动修复轮可能调 LLM）。

    事件序列：param_applying（改值 + 编译验证开始）→ compile_start →
    fix_start（仅首轮编译失败）→ verify_result → done（{"status",
    "backup_id", "compile", "main_diff", "message"}，与任务执行/深化尾段
    同形状；**不造任务轮次、不调步骤报告**——diff 即简报，spec 决策）。

    problem_text 不参与（verify 的修复轮只需要平台 / 模块 / 工具链配置与
    main.c——问题文本仅功能修复用；本通道改值不改变功能语义）。
    """
    from .deepen import main_diff, verify_compile_tail
    from .revision import backup_tree, revise_backup_root

    emit.progress(ProgressEvent(type=EVENT_PARAM_APPLYING))
    updated = apply_param_change(main_c, param, new_value)
    backup_id = backup_tree(revise_backup_root(work_root), output_dir)
    (output_dir / "main.c").write_text(updated, encoding="utf-8")
    diff = main_diff(main_c, updated)
    result = verify_compile_tail(
        llm=llm,
        platform=platform,
        output_dir=output_dir,
        work_root=work_root,
        problem_text="",
        module_slugs=module_slugs,
        main_c=updated,
        uv4_override=uv4_override,
        make_override=make_override,
        emit=emit,
        backup_id=backup_id,
        main_diff=diff,
        subject="参数修改",
    )
    _persist_applied_param(output_dir, param, new_value)
    return result


def _persist_applied_param(
    output_dir: Path, param: ParamItem, new_value: str
) -> None:
    """apply 后回写参数表（评审整改）：只更新本次改动的参数（old_value /
    anchor 同步为磁盘状态），其余参数与顺序原样保留；无表 / 磁盘 main.c 不可读
    / 锚已不在盘上（修复轮改值）→ 保持旧表不写（前端 /read 标失效 = 诚实）。

    失败不阻断主流程（结果已定；表回写只是让下次 /read 的 valid 重验不误判）。
    """
    try:
        disk_main_c = (output_dir / "main.c").read_text(encoding="utf-8")
    except OSError:
        return
    try:
        param_list = load_params_file(output_dir)
    except TaskError:
        return  # 表损坏：不覆盖坏文件（保持原样，前端标失效/提示重新识别）
    if param_list is None:
        return
    refreshed = _refresh_param_after_apply(param_list, param.name, new_value, disk_main_c)
    if refreshed is not param_list:
        try:
            write_params(output_dir, refreshed)
        except OSError:
            pass  # 写盘失败不阻断主流程
