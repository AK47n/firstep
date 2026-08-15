"""mspm0 syscfg 按选中模块动态裁剪（工单 syscfg-prune/01）。

母版 mspm0.syscfg = 全量实例（默认布局理论上限）。生成时按本次选中的模块集
裁剪：未选模块的实例不落盘，其引脚空出来可绑——bindings 写到这些脚不再撞
SysConfig Resource conflict。实例 → 消费模块映射是本模块单源表（manifest
note / 模块代码宏消费面归纳，改库增实例时同步这里）。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .pinwriter import MSPM0_SYSCFG_FILENAME

# 实例名 → 消费模块 slug 元组。任一消费模块被选中即保留；全部未选才裁剪。
# 共享实例：DC_MOTOR 由 motor/key 共用（编码器中断在 key），HUIDU 由
# huidu/pid(mspm0 GRAY_D1-8)/xunji 共用（灰度槽位）。
INSTANCE_CONSUMERS: dict[str, tuple[str, ...]] = {
    "PWMAB": ("motor",),
    "DCC_100_PWM2": ("step_motor",),
    "MOTOR_PID": ("motor", "pid"),
    "NTB": ("ntb_time",),
    "DC_MOTOR": ("motor", "key"),
    "HUIDU": ("huidu", "pid", "xunji"),
    "KEY": ("key",),
    "LED_BEEP": ("led_beep",),
    "STEP_MOTOR": ("step_motor",),
    "IMU601": ("imu_uart",),
    "DIGIT_UART": ("digit_uart", "ball_detect"),
    "OLED": ("oled",),
    "I2C_0": ("ml_mpu6050",),
}

_INSTANCE_DECL_RE = re.compile(
    r"^\s*const\s+(?P<instance>[A-Za-z_]\w*)\s*=\s*(?P<module>[A-Za-z_]\w*)\.addInstance\(\);?\s*(?P<eol>\r?\n)?$"
)
_MODULE_DECL_RE = re.compile(
    r"^\s*const\s+(?P<module>[A-Za-z_]\w*)\s*=\s*scripting\.addModule\(.*$"
)


def prune_syscfg(
    master_text: str, selected_slugs: Iterable[str]
) -> str:
    """按选中模块裁剪 mspm0.syscfg 全文。

    规则：实例的消费模块集与 selected_slugs 交集为空 → 裁掉该实例的
    `const X = MOD.addInstance();` 行与所有 `X.` 配置行；某模块变量
    （UART/I2C/TIMER/GPIO/PWM）的全部实例被裁 → 连 `const MOD =
    scripting.addModule(...)` 行一起裁。Board/SYSCTL 与文件头注释不动。
    """
    selected = set(selected_slugs)
    lines = master_text.splitlines(keepends=True)

    module_instances: dict[str, list[str]] = {}
    for line in lines:
        m = _INSTANCE_DECL_RE.match(line)
        if m:
            module_instances.setdefault(m.group("module"), []).append(
                m.group("instance")
            )

    pruned_instances = {
        instance
        for instance, consumers in INSTANCE_CONSUMERS.items()
        if not (set(consumers) & selected)
    }
    # 防御：映射表里没登记的实例（母版新增实例忘记更新映射）默认保留——
    # 宁多勿裁，误裁会让选中模块编译炸。
    for instances in module_instances.values():
        for instance in instances:
            if instance not in INSTANCE_CONSUMERS:
                pruned_instances.discard(instance)

    pruned_modules = {
        module
        for module, instances in module_instances.items()
        if instances and all(i in pruned_instances for i in instances)
    }

    kept: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        inst_decl = _INSTANCE_DECL_RE.match(line)
        if inst_decl and inst_decl.group("instance") in pruned_instances:
            continue
        mod_decl = _MODULE_DECL_RE.match(line)
        if mod_decl and mod_decl.group("module") in pruned_modules:
            continue
        if stripped:
            first_token = stripped.split()[0]
            if any(
                first_token.startswith(instance + ".")
                for instance in pruned_instances
            ):
                # `INSTANCE.xxx` 配置行（含 `INSTANCE.associatedPins[n].pin`）
                continue
        kept.append(line)
    return "".join(kept)


def prune_mspm0_syscfg_file(
    output_dir: Path, selected_slugs: Iterable[str]
) -> Path | None:
    """生成挂钩：读输出目录的 mspm0.syscfg、裁剪、文本有变化才落盘。

    返回改写后的文件路径；无变化（全选理论模块 = 母版）返回 None。
    """
    path = output_dir / MSPM0_SYSCFG_FILENAME
    if not path.is_file():
        return None  # 假母版/测试树可能无 syscfg；真母版必有，防御跳过
    original = path.read_text(encoding="utf-8", newline="")
    pruned = prune_syscfg(original, selected_slugs)
    if pruned == original:
        return None
    path.write_text(pruned, encoding="utf-8", newline="")
    return path
