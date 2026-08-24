"""模块 manifest 数据模型。

模块库：磁盘目录即数据库，每个模块一个目录——机器可读的 manifest.json
（本模块负责解析/序列化/校验）+ 各平台版本文件（路径在 platform entry 的
files 里，相对模块目录）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .entry_store import (
    StoreError,
    StoreParseError,
    StoreReadError,
    StoreShapeError,
    is_unsafe_path,
    read_json,
)

MANIFEST_FILENAME = "manifest.json"

# 引脚角色类型词表（单源）：boards 能力 token 与 manifest pins 声明共用——
# 改词表只改这一处（ADR 0010 板级引脚配置；board 能力 token 格式 =
# `<角色类型>[:<实例>]`）。gpio_out/gpio_in 任意 io 脚（无实例）；
# uart_tx/uart_rx 实例 = 串口实例（stm32 = ml_uart 的 UARTn，mspm0 = 外设
# UARTn）；pwm 实例 = 定时器通道（TIM2_CH1 / TIMG0_C0 等）；enc 实例 =
# stm32 EXTI 线号（handler 名绑定线号）、mspm0 无实例（GPIO 组中断任意脚）；
# adc 实例 = 通道（ADC_Channel_0 / A0_0 等）；i2c_scl/i2c_sda 实例 = 软
# I2C 驱动（ml_i2c / ml_oled）或外设（I2C0/I2C1）；spi_* 实例 = 外设 + 通道；
# exti 实例 = stm32 引脚名（ml_exti 的 EXTI_PA0 枚举）。
PIN_ROLE_TYPES = (
    "gpio_out",
    "gpio_in",
    "uart_tx",
    "uart_rx",
    "pwm",
    "enc",
    "adc",
    "i2c_scl",
    "i2c_sda",
    "spi_mosi",
    "spi_miso",
    "spi_sck",
    "spi_cs",
    "exti",
)


class ManifestError(ValueError):
    """manifest 解析或校验失败，message 中说明具体问题。"""


@dataclass(frozen=True)
class PinDeclaration:
    """模块引脚角色声明（ADR 0010：标签 = 模块_用途，如 MOTOR_A_PWM）。

    default = 该角色的默认引脚（板级配置未绑定时照此生成——"打开就能编译"）。
    角色类型词表 = PIN_ROLE_TYPES 单源。实例不落声明：门禁从默认引脚的能力
    token 推导（如 default PA2 的 enc:2 → 绑定引脚必须同线号）。macros =
    stm32 写侧渲染要改的 pin_config.h 宏名（工单 02 渲染器用；mspm0 走
    syscfg $assign，不填）。
    """

    id: str  # 角色 id（载荷绑定键 = <slug>.<id>）
    type: str  # 角色类型（PIN_ROLE_TYPES 之一）
    default: str  # 默认引脚名
    label: str = ""  # 菜单标签（缺省 = id）
    required: bool = False  # 必需接线（未绑定也必须按默认生成）
    macros: tuple[str, ...] = ()  # 该角色控制的 pin_config.h 宏名（stm32）

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label or self.id,
            "default": self.default,
            "required": self.required,
            "macros": list(self.macros),
        }


@dataclass(frozen=True)
class PlatformEntry:
    """单个平台下的模块版本条目。

    files 空 = 该平台实现已内嵌母版（随母版进工程，不复制不注册）——
    平台条目本身仍必填：缺条目 = 该平台无版本，生成必失败（missing 警告）。
    """

    files: tuple[str, ...]  # 相对模块目录的文件路径列表（空 = 实现内嵌母版）
    verified: bool = False  # 该平台版本是否验证过
    hardware_bound: bool = False  # 是否绑定硬件（换平台需移植）
    notes: str = ""  # 备注
    kit: str = ""  # 套件型号（硬件身份字段，由人补填、AI 不猜）
    source_url: str = ""  # 购买链接（硬件身份字段，由人补填、AI 不猜）
    pins: tuple[PinDeclaration, ...] = ()  # 引脚角色声明（per-platform）


@dataclass(frozen=True)
class MultiInstanceSpec:
    """多实例能力声明（模块级）：模块支持一次配置里选多次。

    max = 实例上限（sanity 硬上限守卫，非默认数量——默认数量由推荐链路猜、
    用户增删）；variant = 区分实例的属性名（led = color；beep/key/motor
    以后各用其变体名，作为驱动命名与渲染的 key）。
    """

    max: int
    variant: str

    def to_dict(self) -> dict[str, Any]:
        return {"max": self.max, "variant": self.variant}


@dataclass(frozen=True)
class ExclusiveGroupSpec:
    """功能组互斥声明（模块级，工单 recommend-exclusive-groups/01）。

    同一种功能 / 同一硬件上的多个模块互斥（选一个就够，选多个 = 同功能重复
    配置，如 pid / xunji / huidu 共用同一颗 8 路灰度传感器）。声明 = 模块
    归属哪个组；id = 库内唯一组 id（跨模块相同 = 同组），label = 组名（同组
    id 的各模块 label 必须逐字一致，库级校验见 collect_exclusive_groups），
    role = 本模块在组内的差异定位（选择卡上给用户看的"选它差在哪"）。
    缺省不落键 = 不属任何组（旧 manifest 兼容）。
    """

    id: str
    label: str
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "role": self.role}


@dataclass(frozen=True)
class PythonArtifactTemplate:
    """多模板中的一个模板条目（工单 k230-multi-template/01）。

    id = 模板唯一标识（生成请求 python_templates 的取值键）；name /
    description = 前端下拉与（将来的）AI 推荐消费的展示信息；template /
    output 语义与单模板形状一致（相对模块目录 / 纯文件名）。
    """

    id: str
    name: str
    description: str
    template: str
    output: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "output": self.output,
        }


@dataclass(frozen=True)
class PythonArtifactSpec:
    """Python 副产物能力声明（模块级）：模块除主控 C 代码外，生成时额外
    产出 K230 侧 .py 脚本（如 CanMV main.py）。

    两种形状（工单 k230-multi-template/01，向后兼容）：
    - 旧：`{"template", "output"}`——解析为单模板（id = "default"），
      序列化回旧形状逐字节不变（存量 manifest 契约）；
    - 新：`{"templates": [{id, name, description, template, output}...],
      "default": <id>}`——多模板，default 必须存在于列表。
    统一为 templates 列表 + default_id；template / output property 返回
    default 模板（旧消费方零改动，选择渲染在生成请求层按模板 id 取）。
    """

    templates: tuple[PythonArtifactTemplate, ...]
    default_id: str = "default"

    @property
    def default_template(self) -> PythonArtifactTemplate:
        for template in self.templates:
            if template.id == self.default_id:
                return template
        raise ManifestError(
            f"python_artifact 的 default 模板 {self.default_id!r} 不在模板列表"
            "（解析校验应已拦截，防御路径）"
        )

    @property
    def template(self) -> str:
        """default 模板的 template 路径（旧消费方兼容）。"""
        return self.default_template.template

    @property
    def output(self) -> str:
        """default 模板的 output 文件名（旧消费方兼容）。"""
        return self.default_template.output

    def to_dict(self) -> dict[str, Any]:
        # 单模板（id = default 且无展示信息）序列化回旧形状逐字节不变
        if len(self.templates) == 1 and self.templates[0].id == "default":
            template = self.templates[0]
            return {"template": template.template, "output": template.output}
        return {
            "default": self.default_id,
            "templates": [t.to_dict() for t in self.templates],
        }


@dataclass(frozen=True)
class ModuleManifest:
    """一个模块的机器可读描述。"""

    slug: str  # 模块唯一 id，即模块目录名
    description: str  # 功能简介
    dependencies: tuple[str, ...] = ()  # 依赖模块 slug 列表
    platforms: dict[str, PlatformEntry] = field(default_factory=dict)
    multi_instance: MultiInstanceSpec | None = None  # 多实例能力（缺省 = 单实例）
    python_artifact: PythonArtifactSpec | None = None  # Python 副产物（缺省 = 无）
    exclusive_group: ExclusiveGroupSpec | None = None  # 功能组互斥（缺省 = 无组）

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict。

        multi_instance / python_artifact / exclusive_group 缺省（None）时
        不落键——旧 manifest 序列化产物与基线逐字节一致（save_manifest
        写回存量 manifest 不会平白加一个 null 字段）。
        """
        data: dict[str, Any] = {
            "slug": self.slug,
            "description": self.description,
            "dependencies": list(self.dependencies),
        }
        if self.multi_instance is not None:
            data["multi_instance"] = self.multi_instance.to_dict()
        if self.python_artifact is not None:
            data["python_artifact"] = self.python_artifact.to_dict()
        if self.exclusive_group is not None:
            data["exclusive_group"] = self.exclusive_group.to_dict()
        data["platforms"] = {
            platform: {
                "files": list(entry.files),
                "verified": entry.verified,
                "hardware_bound": entry.hardware_bound,
                "notes": entry.notes,
                "kit": entry.kit,
                "source_url": entry.source_url,
                "pins": [pin.to_dict() for pin in entry.pins],
            }
            for platform, entry in self.platforms.items()
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleManifest":
        """从 dict 解析并校验，任何缺失/非法字段抛 ManifestError。"""
        slug = _require(data, "slug", str)
        description = _require(data, "description", str)
        raw_platforms = _require(data, "platforms", dict)

        platforms: dict[str, PlatformEntry] = {}
        for platform, raw_entry in raw_platforms.items():
            if not isinstance(platform, str) or not platform:
                raise ManifestError(f"平台名必须是非空字符串：{platform!r}")
            if not isinstance(raw_entry, dict):
                raise ManifestError(f"平台 {platform} 的条目必须是对象")
            files_raw = _require(raw_entry, "files", list, platform)
            files = _parse_file_list(files_raw, platform)
            platforms[platform] = PlatformEntry(
                files=files,
                verified=_require_flag(raw_entry, "verified", platform),
                hardware_bound=_require_flag(raw_entry, "hardware_bound", platform),
                notes=_require_notes(raw_entry, platform),
                # 硬件身份字段容忍缺省：存量 manifest 无此字段仍能加载（迁移
                # 不打断现有库）；类型非法（非字符串）直接报错。
                kit=_require_optional_str(raw_entry, "kit", platform),
                source_url=_require_optional_str(raw_entry, "source_url", platform),
                pins=_parse_pins(raw_entry, platform),
            )

        return cls(
            slug=slug,
            description=description,
            dependencies=tuple(_parse_dependencies(data.get("dependencies"))),
            platforms=platforms,
            multi_instance=_parse_multi_instance(data),
            python_artifact=_parse_python_artifact(data),
            exclusive_group=_parse_exclusive_group(data),
        )

    @classmethod
    def load(cls, module_dir: Path) -> "ModuleManifest":
        """读取模块目录下的 manifest.json（读盘 / 解析 / 形状走 entry_store 原语）。"""
        manifest_path = module_dir / MANIFEST_FILENAME
        try:
            data = read_json(module_dir, MANIFEST_FILENAME)
        except (StoreReadError, StoreParseError) as exc:
            raise ManifestError(f"无法读取 {manifest_path}: {exc.error}") from exc
        except StoreShapeError:
            raise ManifestError(f"{manifest_path} 必须是 JSON 对象") from None
        manifest = cls.from_dict(data)
        if manifest.slug != module_dir.name:
            raise ManifestError(
                f"manifest slug {manifest.slug!r} 与目录名 {module_dir.name!r} 不一致"
            )
        return manifest


def _require(data: dict[str, Any], key: str, expected_type: type, platform: str | None = None) -> Any:
    where = f"平台 {platform} 的" if platform else ""
    if key not in data:
        raise ManifestError(f"缺少必填字段：{where}{key}")
    value = data[key]
    if not isinstance(value, expected_type):
        raise ManifestError(f"字段 {where}{key} 必须是 {expected_type.__name__}")
    return value


def _require_flag(entry: dict[str, Any], key: str, platform: str) -> bool:
    """布尔标记严格校验——宽松强转会让错值静默翻转验证状态。"""
    value = entry.get(key, False)
    if not isinstance(value, bool):
        raise ManifestError(f"平台 {platform} 的 {key} 必须是布尔值")
    return value


def _require_optional_str(entry: dict[str, Any], key: str, platform: str) -> str:
    """可选字符串字段：缺省视为空串（存量兼容），类型非法抛 ManifestError。"""
    value = entry.get(key, "")
    if not isinstance(value, str):
        raise ManifestError(f"平台 {platform} 的 {key} 必须是字符串")
    return value


def _require_notes(entry: dict[str, Any], platform: str) -> str:
    return _require_optional_str(entry, "notes", platform)


def _parse_file_list(files: list[Any], platform: str) -> tuple[str, ...]:
    """解析平台条目文件列表：空数组合法 = 该平台实现已内嵌母版（无模块文件
    需复制/注册/校验）；非空时逐项校验路径安全与去重。files 数组本身仍必填
    （缺字段 = 平台条目不完整，报错保留）。"""
    result: list[str] = []
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, str) or not item:
            raise ManifestError(f"平台 {platform} 的文件路径必须是非空字符串：{item!r}")
        if is_unsafe_path(item):
            raise ManifestError(f"平台 {platform} 的文件路径必须是相对且无 .. 的：{item!r}")
        if item in seen:
            raise ManifestError(f"平台 {platform} 的文件列表重复：{item!r}")
        seen.add(item)
        result.append(item)
    return tuple(result)


def _parse_pins(raw_entry: dict[str, Any], platform: str) -> tuple[PinDeclaration, ...]:
    """解析平台条目的 pins 声明（缺省 = 空元组，存量 manifest 兼容）。

    校验：id 非空且平台内唯一、type 在 PIN_ROLE_TYPES 词表内、default 非空、
    label/required/macros 类型严格（宽松强转会让错值静默进绑定校验）。
    """
    raw_pins = raw_entry.get("pins", [])
    if raw_pins is None:
        return ()
    if not isinstance(raw_pins, list):
        raise ManifestError(f"平台 {platform} 的 pins 必须是数组")
    result: list[PinDeclaration] = []
    seen_ids: set[str] = set()
    for item in raw_pins:
        if not isinstance(item, dict):
            raise ManifestError(f"平台 {platform} 的 pins 条目必须是对象")
        pin_id = _require(item, "id", str, platform)
        if not pin_id:
            raise ManifestError(f"平台 {platform} 的引脚角色 id 不能为空")
        if pin_id in seen_ids:
            raise ManifestError(f"平台 {platform} 的引脚角色 id 重复：{pin_id}")
        seen_ids.add(pin_id)
        role_type = _require(item, "type", str, platform)
        if role_type not in PIN_ROLE_TYPES:
            raise ManifestError(
                f"平台 {platform} 的角色 {pin_id} 的 type {role_type!r}"
                f" 不在词表 {PIN_ROLE_TYPES} 内"
            )
        default = _require(item, "default", str, platform)
        if not default:
            raise ManifestError(f"平台 {platform} 的角色 {pin_id} 的 default 不能为空")
        label = item.get("label", "")
        if not isinstance(label, str):
            raise ManifestError(f"平台 {platform} 的角色 {pin_id} 的 label 必须是字符串")
        if label == pin_id:
            label = ""  # label==id 视为缺省（to_dict 落 id，序列化往返稳定）
        required = item.get("required", False)
        if not isinstance(required, bool):
            raise ManifestError(
                f"平台 {platform} 的角色 {pin_id} 的 required 必须是布尔值"
            )
        macros_raw = item.get("macros", [])
        if not isinstance(macros_raw, list):
            raise ManifestError(
                f"平台 {platform} 的角色 {pin_id} 的 macros 必须是数组"
            )
        macros: list[str] = []
        for macro in macros_raw:
            if not isinstance(macro, str) or not macro:
                raise ManifestError(
                    f"平台 {platform} 的角色 {pin_id} 的 macros 必须是非空字符串"
                )
            macros.append(macro)
        result.append(
            PinDeclaration(
                id=pin_id,
                type=role_type,
                default=default,
                label=label,
                required=required,
                macros=tuple(macros),
            )
        )
    return tuple(result)


def _parse_dependencies(dependencies: Any) -> list[str]:
    if dependencies is None:
        return []
    if not isinstance(dependencies, list) or not all(
        isinstance(dep, str) and dep for dep in dependencies
    ):
        raise ManifestError("dependencies 必须是字符串列表")
    return dependencies


def _parse_multi_instance(data: dict[str, Any]) -> MultiInstanceSpec | None:
    """解析模块级 multi_instance 能力块（缺省 / null = None，旧 manifest 兼容）。

    存在则严格校验：max 正整数（布尔显式拒绝——bool 是 int 子类，宽松强转
    会静默放行 True）、variant 非空字符串；错值大声失败（照 _require 系列，
    不静默强转）。
    """
    raw = data.get("multi_instance")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ManifestError("multi_instance 必须是对象")
    max_value = raw.get("max")
    if isinstance(max_value, bool) or not isinstance(max_value, int):
        raise ManifestError("multi_instance 的 max 必须是正整数")
    if max_value < 1:
        raise ManifestError("multi_instance 的 max 必须是正整数")
    variant = raw.get("variant")
    if not isinstance(variant, str) or not variant:
        raise ManifestError("multi_instance 的 variant 必须是非空字符串")
    return MultiInstanceSpec(max=max_value, variant=variant)


def _parse_exclusive_group(data: dict[str, Any]) -> ExclusiveGroupSpec | None:
    """解析模块级 exclusive_group 声明（缺省 / null = None，旧 manifest 兼容）。

    存在则严格校验：id / label / role 全为非空字符串——`isinstance(x, str)`
    已天然拒绝 bool（bool 不是 str 子类），再叠加 `or not x` 拒绝空串；错值
    大声失败（不静默强转）。组内 label 一致性（同 id 各模块 label 逐字一致）
    是库级校验，归 collect_exclusive_groups——单模块解析看不见其他模块。
    """
    raw = data.get("exclusive_group")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ManifestError("exclusive_group 必须是对象")
    group_id = raw.get("id")
    if not isinstance(group_id, str) or not group_id:
        raise ManifestError("exclusive_group 的 id 必须是非空字符串")
    label = raw.get("label")
    if not isinstance(label, str) or not label:
        raise ManifestError("exclusive_group 的 label 必须是非空字符串")
    role = raw.get("role")
    if not isinstance(role, str) or not role:
        raise ManifestError("exclusive_group 的 role 必须是非空字符串")
    return ExclusiveGroupSpec(id=group_id, label=label, role=role)


def _parse_python_artifact(data: dict[str, Any]) -> PythonArtifactSpec | None:
    """解析模块级 python_artifact 能力块（缺省 / null = None，旧 manifest 兼容）。

    两种形状（工单 k230-multi-template/01）：
    - 旧：template/output 单模板 → id="default" 单模板列表（存量 manifest
      逐字节兼容，序列化回旧形状）；
    - 新：templates 数组 + default id——id 唯一非空、default 必须在列表、
      template 为安全相对路径、output 为纯文件名（照旧口径），任一非法
      大声失败。
    """
    raw = data.get("python_artifact")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ManifestError("python_artifact 必须是对象")

    def _parse_template_item(
        item: dict[str, Any], index: int
    ) -> PythonArtifactTemplate:
        tid = item.get("id")
        if not isinstance(tid, str) or not tid:
            raise ManifestError(f"python_artifact.templates[{index}] 的 id 必须是非空字符串")
        template = item.get("template")
        if not isinstance(template, str) or not template:
            raise ManifestError(
                f"python_artifact.templates[{index}] 的 template 必须是非空字符串"
            )
        if is_unsafe_path(template) or template == ".":
            raise ManifestError(
                f"python_artifact.templates[{index}] 的 template 必须是相对且无"
                f" .. 的文件路径：{template!r}"
            )
        output = item.get("output")
        if not isinstance(output, str) or not output:
            raise ManifestError(
                f"python_artifact.templates[{index}] 的 output 必须是非空字符串"
            )
        if is_unsafe_path(output) or "/" in output or output == ".":
            raise ManifestError(
                f"python_artifact.templates[{index}] 的 output 必须是纯文件名："
                f"{output!r}"
            )
        name = item.get("name")
        if name is None:
            name = ""
        if not isinstance(name, str):
            raise ManifestError(
                f"python_artifact.templates[{index}] 的 name 必须是字符串"
            )
        description = item.get("description")
        if description is None:
            description = ""
        if not isinstance(description, str):
            raise ManifestError(
                f"python_artifact.templates[{index}] 的 description 必须是字符串"
            )
        return PythonArtifactTemplate(
            id=tid, name=name, description=description,
            template=template, output=output,
        )

    if "templates" in raw:
        templates_raw = raw["templates"]
        if not isinstance(templates_raw, list) or not templates_raw:
            raise ManifestError("python_artifact.templates 必须是非空数组")
        templates: list[PythonArtifactTemplate] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(templates_raw):
            if not isinstance(item, dict):
                raise ManifestError(f"python_artifact.templates[{index}] 必须是对象")
            parsed = _parse_template_item(item, index)
            if parsed.id in seen_ids:
                raise ManifestError(
                    f"python_artifact.templates 的 id 重复：{parsed.id!r}"
                )
            seen_ids.add(parsed.id)
            templates.append(parsed)
        default = raw.get("default")
        if not isinstance(default, str) or not default:
            raise ManifestError("python_artifact 的 default 必须是非空字符串")
        if default not in seen_ids:
            raise ManifestError(
                f"python_artifact 的 default {default!r} 不在模板 id 列表"
                f"（{'、'.join(sorted(seen_ids))}）"
            )
        return PythonArtifactSpec(templates=tuple(templates), default_id=default)

    template = raw.get("template")
    if not isinstance(template, str) or not template:
        raise ManifestError("python_artifact 的 template 必须是非空字符串")
    if is_unsafe_path(template) or template == ".":
        raise ManifestError(
            f"python_artifact 的 template 必须是相对且无 .. 的文件路径：{template!r}"
        )
    output = raw.get("output")
    if not isinstance(output, str) or not output:
        raise ManifestError("python_artifact 的 output 必须是非空字符串")
    if is_unsafe_path(output) or "/" in output or output == ".":
        raise ManifestError(f"python_artifact 的 output 必须是纯文件名：{output!r}")
    return PythonArtifactSpec(
        templates=(
            PythonArtifactTemplate(
                id="default", name="", description="",
                template=template, output=output,
            ),
        ),
        default_id="default",
    )


def collect_kits(manifests: Sequence[ModuleManifest]) -> list[str]:
    """平台条目 kit 词表（保序去重、空值跳过）：硬件身份词表的唯一实现。

    调用方（reference_library.module_kit_vocabulary / selection 的关联参考
    收集 / manifest 摘要对象）都从这里取——顺序 = manifests 顺序 × 平台条目
    插入顺序 × 首次出现。字段所有者是 PlatformEntry.kit，词表语义只在此
    一处（改语义同步改调用方测试）。
    """
    kits: list[str] = []
    seen: set[str] = set()
    for manifest in manifests:
        for entry in manifest.platforms.values():
            if entry.kit and entry.kit not in seen:
                seen.add(entry.kit)
                kits.append(entry.kit)
    return kits


@dataclass(frozen=True)
class ExclusiveGroupMember:
    """功能组成员：slug + 组内差异定位（role，选择卡展示用）+ 所在平台。

    platforms 供组内平台成员过滤（build_exclusive_groups 按目标平台只留
    该平台有条目的成员）；不进对外载荷（契约成员形状 = {slug, role}）。
    """

    slug: str
    role: str
    platforms: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExclusiveGroup:
    """功能组定义（库级汇总）：同 id 各模块聚合为成员清单（库登记顺序）。

    members 按 manifests 传入顺序保序；成员可多平台，平台投影（该平台
    有条目才算候选）统一由 scope_group_members 定义，collect 平台视图与
    推荐链路 build_exclusive_groups 各自调用。
    """

    id: str
    label: str
    members: tuple[ExclusiveGroupMember, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "members": [
                {"slug": member.slug, "role": member.role}
                for member in self.members
            ],
        }


def scope_group_members(
    members: Sequence[ExclusiveGroupMember], platform: str
) -> tuple[ExclusiveGroupMember, ...]:
    """组内成员平台投影（平台过滤唯一实现）。

    platform 非空 = 只留该平台有条目的成员；platform 空串 = 全成员（不过滤）。
    调用方自行决定是否做单成员剔除（collect 平台视图与推荐链路出卡语义不同：
    collect 仅在平台视图剔除，出卡侧恒剔除无可选组）。
    """
    if not platform:
        return tuple(members)
    return tuple(member for member in members if platform in member.platforms)


def collect_exclusive_groups(
    manifests: Sequence[ModuleManifest], platform: str = ""
) -> list[ExclusiveGroup]:
    """按 exclusive_group 声明汇总功能组（工单 recommend-exclusive-groups/01）。

    同 id 的 label 逐字一致（不一致 = 库错误，ManifestError 大声失败——组名
    漂移会让选择卡标题出现在不同模块上各不相同）；members 按库登记顺序
    （manifests 传入顺序）保序。platform 非空 = 平台视图：成员经
    scope_group_members 投影后仅 1 成员的组 = 无意义组（无可选），不返回。
    platform 空串 = 全平台视图（不做投影、不做单成员剔除——供校验与全库清单）。
    """
    by_id: dict[str, tuple[str, list[ExclusiveGroupMember]]] = {}
    for manifest in manifests:
        spec = manifest.exclusive_group
        if spec is None:
            continue
        known = by_id.get(spec.id)
        if known is None:
            by_id[spec.id] = (spec.label, [])
        elif known[0] != spec.label:
            raise ManifestError(
                f"功能组 {spec.id!r} 的 label 不一致：{known[0]!r} vs {spec.label!r}"
            )
        by_id[spec.id][1].append(
            ExclusiveGroupMember(
                slug=manifest.slug,
                role=spec.role,
                platforms=tuple(manifest.platforms),
            )
        )
    result: list[ExclusiveGroup] = []
    if platform:
        for group_id, (label, members) in by_id.items():
            filtered = scope_group_members(members, platform)
            if len(filtered) < 2:
                # 该平台只有 1 个候选（或没有）→ 无可选，组不出卡
                continue
            result.append(
                ExclusiveGroup(id=group_id, label=label, members=filtered)
            )
    else:
        for group_id, (label, members) in by_id.items():
            result.append(
                ExclusiveGroup(id=group_id, label=label, members=tuple(members))
            )
    return result


@dataclass(frozen=True)
class ManifestSummary:
    """模块库摘要对象（喂给 LLM 的可用模块清单——协议层收对象，字符串只在
    prompt 边界渲染一次，不再有两端解析耦合）。

    行渲染唯一实现 = to_line()（原 build_manifest_summaries 的行文法逐字
    搬入）；known_slugs 直接取 slug 字段，不再反向解析行。
    """

    slug: str
    description: str
    kits: tuple[str, ...] = ()  # collect_kits 单源（保序去重，有 kit 才显示）
    dependencies: tuple[str, ...] = ()
    multi_instance: MultiInstanceSpec | None = None  # 多实例能力（缺省 = 单实例）
    python_artifact: PythonArtifactSpec | None = None  # Python 副产物（缺省 = 无）
    exclusive_group: ExclusiveGroupSpec | None = None  # 功能组互斥（缺省 = 无组）

    @classmethod
    def from_manifest(cls, manifest: ModuleManifest) -> "ManifestSummary":
        return cls(
            slug=manifest.slug,
            description=manifest.description,
            kits=tuple(collect_kits([manifest])),
            dependencies=manifest.dependencies,
            multi_instance=manifest.multi_instance,
            python_artifact=manifest.python_artifact,
            exclusive_group=manifest.exclusive_group,
        )

    def to_line(self) -> str:
        """摘要行：`- slug: description（套件: kit; 依赖: ...）`。

        套件段聚合各平台条目的 kit（去重保序走 collect_kits 单源，有 kit 才
        显示，AI 靠它分辨"哪个套件的 UWB"）；依赖段有依赖才显示；多实例段
        （工单 module-multi-instance/06）有 multi_instance 能力才显示——AI
        据此知道哪些模块可多实例、上限多少（选模块猜实例数的能力证据）。
        行格式的唯一出处——只进 LLM prompt，不再有反向解析方。
        """
        line = f"- {self.slug}: {self.description}"
        if self.kits:
            line += f"（套件: {'、'.join(self.kits)}"
            if self.dependencies:
                line += f"; 依赖: {', '.join(self.dependencies)}"
            line += "）"
        elif self.dependencies:
            line += f"（依赖: {', '.join(self.dependencies)}）"
        if self.multi_instance is not None:
            line += (
                f"（多实例：上限 {self.multi_instance.max}，"
                f"变体 = {self.multi_instance.variant}）"
            )
        if self.python_artifact is not None and len(self.python_artifact.templates) > 1:
            names = [
                t.name or t.id for t in self.python_artifact.templates
            ]
            line += (
                f"（副产物模板可选：{'、'.join(names)}，"
                f"默认 = {self.python_artifact.default_id}）"
            )
        if self.exclusive_group is not None:
            line += (
                f"（同组互斥：{self.exclusive_group.label}，"
                "组内仅选其一）"
            )
        return line


def build_manifest_summaries(
    manifests: Sequence[ModuleManifest],
) -> list[ManifestSummary]:
    """模块库摘要对象（喂给 LLM 的可用模块清单）。

    形状归 manifest.ManifestSummary（slug/description/kits/依赖），行渲染
    唯一实现 = ManifestSummary.to_line()——本函数只是批量投影，协议层不再
    传字符串、不再有反向解析（_summary_slugs 已删除）。
    """
    return [ManifestSummary.from_manifest(m) for m in manifests]
