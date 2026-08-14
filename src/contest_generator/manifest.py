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
class ModuleManifest:
    """一个模块的机器可读描述。"""

    slug: str  # 模块唯一 id，即模块目录名
    description: str  # 功能简介
    dependencies: tuple[str, ...] = ()  # 依赖模块 slug 列表
    platforms: dict[str, PlatformEntry] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict。"""
        return {
            "slug": self.slug,
            "description": self.description,
            "dependencies": list(self.dependencies),
            "platforms": {
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
            },
        }

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

    @classmethod
    def from_manifest(cls, manifest: ModuleManifest) -> "ManifestSummary":
        return cls(
            slug=manifest.slug,
            description=manifest.description,
            kits=tuple(collect_kits([manifest])),
            dependencies=manifest.dependencies,
        )

    def to_line(self) -> str:
        """摘要行：`- slug: description（套件: kit; 依赖: ...）`。

        套件段聚合各平台条目的 kit（去重保序走 collect_kits 单源，有 kit 才
        显示，AI 靠它分辨"哪个套件的 UWB"）；依赖段有依赖才显示。行格式
        的唯一出处——只进 LLM prompt，不再有反向解析方。
        """
        line = f"- {self.slug}: {self.description}"
        if self.kits:
            line += f"（套件: {'、'.join(self.kits)}"
            if self.dependencies:
                line += f"; 依赖: {', '.join(self.dependencies)}"
            line += "）"
        elif self.dependencies:
            line += f"（依赖: {', '.join(self.dependencies)}）"
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
