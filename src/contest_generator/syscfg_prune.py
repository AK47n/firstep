"""mspm0 syscfg 按选中模块动态裁剪（工单 syscfg-prune/01）。

母版 mspm0.syscfg = 全量实例（默认布局理论上限）。生成时按本次选中的模块集
裁剪：未选模块的实例不落盘，其引脚空出来可绑——bindings 写到这些脚不再撞
SysConfig Resource conflict。实例 → 消费模块映射单源表在
syscfg_instances.py（manifest note / 模块代码宏消费面归纳，改库增实例时
同步那里；本模块保留 INSTANCE_CONSUMERS 旧导入路径兼容）。

裁剪文法已收敛到 syscfg_model（工单 syscfg-file-model/02）：prune_syscfg
委托给 SyscfgModel.prune，本模块不再持有实例/模块声明正则。
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .pinwriter import MSPM0_SYSCFG_FILENAME
from .syscfg_instances import INSTANCE_CONSUMERS  # noqa: F401  # 旧导入路径兼容
from .syscfg_model import parse_syscfg

__all__ = ["INSTANCE_CONSUMERS", "prune_syscfg"]


def prune_syscfg(
    master_text: str, selected_slugs: Iterable[str]
) -> str:
    """按选中模块裁剪 mspm0.syscfg 全文。

    规则：实例的消费模块集与 selected_slugs 交集为空 → 裁掉该实例的
    `const X = MOD.addInstance();` 行与所有 `X.` 配置行；某模块变量
    （UART/I2C/TIMER/GPIO/PWM）的全部实例被裁 → 连 `const MOD =
    scripting.addModule(...)` 行一起裁。Board/SYSCTL 与文件头注释不动。

    委托给文件模型 SyscfgModel.prune（工单 syscfg-file-model/02），文法与
    裁剪逻辑单源；行为与迁移前逐字节一致。
    """
    return parse_syscfg(master_text).prune(selected_slugs).to_text()


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
