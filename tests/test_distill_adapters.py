"""蒸馏侧平台适配接缝（工单 04）：平台行为（摘要读 / 渲染 / 启动候选谓词）
per platform 经适配器分派；守卫错误翻译在缝内归 MasterError；mspm0 显式
无操作。行为零变化：报告形状 / 预览空串 / 去重语义逐字节不变。
"""

from pathlib import Path

import pytest

from contest_generator.distill_adapters import (
    CcsDistillAdapter,
    KeilDistillAdapter,
    get_distill_adapter,
)
from contest_generator.master_store import MasterError
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32


# ---------------------------------------------------------------------------
# 分派：get_distill_adapter
# ---------------------------------------------------------------------------


def test_get_distill_adapter_dispatches_by_platform():
    assert isinstance(get_distill_adapter(PLATFORM_STM32), KeilDistillAdapter)
    assert isinstance(get_distill_adapter(PLATFORM_MSPM0), CcsDistillAdapter)


def test_get_distill_adapter_rejects_unknown_platform():
    with pytest.raises(MasterError, match="未知平台"):
        get_distill_adapter("esp32")


# ---------------------------------------------------------------------------
# mspm0 显式无操作（判例 09 保留首份）：renders_config=False / render_config
# 恒 "" / 谓词恒 False / write_config 无操作
# ---------------------------------------------------------------------------


def test_mspm0_adapter_explicit_noop():
    adapter = get_distill_adapter(PLATFORM_MSPM0)

    assert adapter.renders_config is False
    # 无现写：预览恒空串（报告 .uvprojx 预览为空）
    assert adapter.render_config([], None, []) == ""
    # 无 .s 启动文件（TI/CCS 启动为 .c，不在基础设施词表）：谓词恒 False，
    # 启动去重对 mspm0 不生效
    assert adapter.is_startup_candidate("startup_mspm0g3507.s") is False
    assert adapter.is_md_startup("startup_mspm0g3507.s") is False
    # 显式无操作的落盘形态：apply_distillation 的 renders_config 分派下
    # 永不调用，返回 None 是契约形态
    assert adapter.write_config(Path("ignored"), [], None, []) is None


# ---------------------------------------------------------------------------
# stm32 适配器：渲染委托 keil，守卫翻译归 MasterError（message 原样）
# ---------------------------------------------------------------------------


def test_keil_adapter_renders_config(tmp_path):
    adapter = get_distill_adapter(PLATFORM_STM32)

    assert adapter.renders_config is True
    xml = adapter.render_config(
        ["main.c", "sys/startup_stm32f10x_md.s"], "sys/startup_stm32f10x_md.s", ["inc"]
    )
    assert "STM32F103C8" in xml
    assert "startup_stm32f10x_md.s" in xml

    target = adapter.write_config(tmp_path, ["main.c"], "sys/startup_stm32f10x_md.s", [])
    assert target == tmp_path / "user" / "Project.uvprojx"
    assert target.is_file()


def test_keil_adapter_guard_translated_to_master_error(tmp_path):
    """密度守卫翻译（工单 04）：保留启动文件非 _md → build_master_uvprojx
    抛 KeilProjectError，适配器 message 原样翻成 MasterError——契约兑现
    distill_master 的 docstring（HTTP 层 MasterError 同映射 400），
    KeilProjectError 不再逃出蒸馏缝。"""
    adapter = get_distill_adapter(PLATFORM_STM32)

    with pytest.raises(MasterError, match="导入工程与目标板 STM32F103C8T6 不符"):
        adapter.render_config(["main.c"], "sys/startup_stm32f10x_hd.s", [])
    with pytest.raises(MasterError, match="导入工程与目标板 STM32F103C8T6 不符"):
        adapter.write_config(tmp_path, ["main.c"], "sys/startup_stm32f10x_hd.s", [])


def test_keil_adapter_config_summary_soft_failure(tmp_path):
    """软失败语义（原 master._config_summary 的 catch 逻辑逐字下移）：工程
    配置文件缺失时转成一行摘要，扫描不因单个工程带病中断。"""
    adapter = get_distill_adapter(PLATFORM_STM32)

    summary = adapter.config_summary(tmp_path)

    assert summary == (f"{PLATFORM_STM32} 工程配置读取失败：工程目录里没有 .uvprojx 文件：{tmp_path}",)


def test_ccs_adapter_config_summary_soft_failure(tmp_path):
    """mspm0 摘要真实现（非无操作）：缺失 .cproject 同样转成一行软失败。"""
    adapter = get_distill_adapter(PLATFORM_MSPM0)

    summary = adapter.config_summary(tmp_path)

    assert summary == (f"{PLATFORM_MSPM0} 工程配置读取失败：工程目录里没有 .cproject 文件：{tmp_path}",)


# ---------------------------------------------------------------------------
# 结构测试（防回退，先例 errors.py 防漏登）：不 import patchers（生成侧
# registry 零改动）
# ---------------------------------------------------------------------------


def test_distill_adapters_no_patcher_registry():
    import contest_generator.distill_adapters as distill_adapters

    assert not hasattr(distill_adapters, "PatcherRegistry")
