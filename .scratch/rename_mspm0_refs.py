"""参考库 TI MSPM0 SDK 例程条目改名（.scratch 工具脚本）。

批次 04 入库时标题用 SDK 目录名（adc12_single_conversion 之类），一眼看不出
用途。本脚本：标题改中文直观名（如「ADC12 单次转换」），原目录名保留在简介
末尾（SDK 例程：xxx）便于回查 SDK；9 条 CCS 空工程模板删除（README 均为
"Empty project using DriverLib"，与 LCD_EMPTY 同类无参考价值）。

机制：删除走 delete_reference（官方 API）；改名 = 目录 rename + reference.json
title/id/description 改写（文件不动；库无改标题 API，参考 8318b56 库根迁移
先例直接动盘）。跑前把 config.json autocommit_enabled 置 false，跑完手动一条
提交。幂等：旧 id 目录不存在即跳过；目标 id 已存在即告警跳过。
前置自检：mapping 与库内 SDK 条目集合必须完全对上（多/少一个即红）。
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator import config  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    REFERENCE_META_FILENAME,
    _next_entry_id,
    delete_reference,
    list_references,
)

REFERENCE_ROOT = config.reference_library_dir(REPO_ROOT / "library" / "modules")
TYPE = "TI MSPM0 SDK 例程"

# 空工程模板：README 均为 "Empty project using DriverLib"，删除
DELETE_IDS = (
    "GPIO",
    "LCD",
    "PWM_LCD",
    "UART",
    "five-time-led-pwm",
    "heartrate",
    "l",
    "lcd_task",
    "pwm_last",
)

# 旧 id → 中文标题
RENAMES: dict[str, str] = {
    "adc12_14bit_resolution": "ADC12 14 位分辨率",
    "adc12_internal_temp_sensor_mathacl": "ADC12 内部温度传感器（MATHACL 滤波）",
    "adc12_max_freq_dma": "ADC12 最高采样率 DMA 搬运",
    "adc12_max_freq_dma_8bit": "ADC12 最高采样率 DMA 搬运（8 位）",
    "adc12_monitor_supply": "ADC12 电源电压监测",
    "adc12_sequence_conversion": "ADC12 序列通道转换",
    "adc12_simultaneous_trigger_event": "ADC12 事件同步触发",
    "adc12_simultaneous_trigger_event_stop": "ADC12 事件同步触发（停止模式）",
    "adc12_single_conversion": "ADC12 单次转换",
    "adc12_single_conversion_vref_external": "ADC12 单次转换（外部基准）",
    "adc12_single_conversion_vref_internal": "ADC12 单次转换（内部基准）",
    "adc12_triggered_by_timer_event": "ADC12 定时器事件触发",
    "adc12_triggered_by_timer_event_stop": "ADC12 定时器事件触发（停止模式）",
    "adc12_window_comparator": "ADC12 窗口比较器",
    "aes_cbc_256_enc_dec": "AES-256 CBC 加解密",
    "aes_cfb_256_decrypt": "AES-256 CFB 解密",
    "aes_ofb_128_encrypt": "AES-128 OFB 加密",
    "cinit_bypass": "复位后预初始化引导钩子",
    "comp_analog_filter": "比较器模拟滤波",
    "comp_dac_to_timer_event": "比较器 DAC 触发定时器事件",
    "comp_hs_dac_vref_external": "高速比较器 DAC（外部基准）",
    "comp_hs_tima_pwm_fault": "高速比较器 PWM 故障检测",
    "comp_lp_dac_vref_internal": "低功耗比较器 DAC（内部基准）",
    "crc_calculate_checksum": "CRC 校验计算",
    "crc_calculate_checksum_dma": "CRC 校验计算（DMA）",
    "dac12_dma_sampletimegen": "DAC12 DMA 采样时间发生器",
    "dac12_fifo_sampletimegen": "DAC12 FIFO 采样时间发生器",
    "dac12_fifo_timer_event": "DAC12 FIFO 定时器触发",
    "dac12_fixed_voltage_vref_internal": "DAC12 固定电压输出（内部基准）",
    "dma_block_transfer": "DMA 块搬运",
    "dma_fill_data": "DMA 填充数据",
    "dma_table_transfer": "DMA 表搬运",
    "event_input_triggers_output": "GPIO 事件直连输出（无 CPU 介入）",
    "flashctl_blank_verify": "Flash 空白校验",
    "flashctl_dynamic_memory_protection": "Flash 动态内存保护",
    "flashctl_ecc_error_injection": "Flash ECC 错误注入",
    "flashctl_multiple_size_read_verify": "Flash 多尺寸读取校验",
    "flashctl_multiple_size_write": "Flash 多尺寸写入",
    "flashctl_nonmain_memory_write": "Flash 非主存区写入",
    "flashctl_program_with_ecc": "Flash ECC 编程",
    "gpamp_buffer_to_adc": "可编程增益放大器缓冲送 ADC",
    "gpamp_general_purpose_rri": "可编程增益放大器通用模式",
    "gpio_input_capture": "GPIO 输入捕获",
    "gpio_simultaneous_interrupts": "GPIO 多引脚同步中断",
    "gpio_software_poll": "GPIO 软件轮询",
    "gpio_toggle_output": "GPIO 翻转输出",
    "gpio_toggle_output_cpp": "GPIO 翻转输出（C++）",
    "gpio_toggle_output_hiz": "GPIO 翻转输出（高阻）",
    "i2c_controller_rw_multibyte_fifo_interrupts": "I2C 主机多字节 FIFO 读写（中断）",
    "i2c_controller_rw_multibyte_fifo_poll": "I2C 主机多字节 FIFO 读写（轮询）",
    "i2c_controller_target_dynamic_switching": "I2C 主机从机动态切换",
    "i2c_multicontroller_arbitration": "I2C 多主机仲裁",
    "i2c_target_rw_multibyte_fifo_interrupts": "I2C 从机多字节 FIFO 读写（中断）",
    "i2c_target_rw_multibyte_fifo_interrupts_stop": "I2C 从机多字节 FIFO 读写（停止模式）",
    "i2c_target_rw_multibyte_fifo_poll": "I2C 从机多字节 FIFO 读写（轮询）",
    "mathacl_mpy_div_op": "MATHACL 乘除运算",
    "mathacl_trig_op": "MATHACL 三角运算",
    "mcan_loopback": "CAN 环回",
    "mcan_message_rx": "CAN 报文接收",
    "mcan_message_rx_tcan114x": "CAN 报文接收（TCAN114x 收发器）",
    "mcan_multi_message_tx": "CAN 多报文发送",
    "mcan_multi_message_tx_tcan114x": "CAN 多报文发送（TCAN114x 收发器）",
    "mcan_single_message_tx": "CAN 单报文发送",
    "MSPM0G3507_MPU6050": "MPU6050 姿态解算（DMP 库）",
    "nvic_interrupt_disable": "NVIC 中断屏蔽",
    "nvic_interrupt_grouping": "NVIC 中断分组",
    "opa_burnout_current_source_to_adc": "运放断线检测电流源送 ADC",
    "opa_dac8_output_buffer": "运放缓冲 DAC8 输出",
    "opa_general_purpose_rri": "运放通用模式",
    "opa_inverting_pga_with_dac": "反相可编程增益（DAC 配合）",
    "opa_non_inverting_pga": "同相可编程增益",
    "opa_signal_chain_to_adc": "运放信号链送 ADC",
    "rtc_calendar_alarm_standby": "RTC 日历闹钟（待机）",
    "rtc_offset_calibration_lfxt": "RTC 晶振偏移校准",
    "rtc_periodic_alarm_lfosc_standby": "RTC 周期闹钟（内部低频晶振）",
    "rtc_periodic_alarm_lfxt_standby": "RTC 周期闹钟（外部低频晶振）",
    "spi_controller_command_data_control": "SPI 主机命令数据控制",
    "spi_controller_echo_interrupts": "SPI 主机回显（中断）",
    "spi_controller_fifo_dma_interrupts": "SPI 主机 FIFO+DMA（中断）",
    "spi_controller_internal_loopback_poll": "SPI 主机内部环回（轮询）",
    "spi_controller_multibyte_fifo_poll": "SPI 主机多字节 FIFO（轮询）",
    "spi_controller_register_format": "SPI 主机寄存器格式",
    "spi_controller_repeated_fifo_dma_interrupts": "SPI 主机重复 FIFO+DMA（中断）",
    "spi_peripheral_echo_interrupts": "SPI 从机回显（中断）",
    "spi_peripheral_fifo_dma_interrupts": "SPI 从机 FIFO+DMA（中断）",
    "spi_peripheral_multibyte_fifo_poll": "SPI 从机多字节 FIFO（轮询）",
    "spi_peripheral_register_format": "SPI 从机寄存器格式",
    "spi_peripheral_repeated_fifo_dma_interrupts": "SPI 从机重复 FIFO+DMA（中断）",
    "sram_parity": "奇偶校验 SRAM",
    "sysctl_frequency_clock_counter": "时钟频率计数测量",
    "sysctl_hfxt_run": "外部高频晶振运行",
    "sysctl_lfxt_standby": "外部低频晶振（待机）",
    "sysctl_mclk_syspll": "系统时钟 SYS PLL 配置",
    "sysctl_power_policy_sleep_to_standby": "低功耗策略：睡眠→待机",
    "sysctl_power_policy_sleep_to_stop": "低功耗策略：睡眠→停止",
    "sysctl_shutdown": "系统关断模式",
    "systick_periodic_timer": "SysTick 周期定时（睡眠模式）",
    "tima_timer_mode_periodic_repeat_count": "定时器 A 周期模式（重复计数）",
    "tima_timer_mode_pwm_dead_band": "定时器 A PWM 死区",
    "tima_trigger_fail_mechanism": "定时器 A 触发故障检测",
    "timg_32bit_timer_mode_periodic_sleep": "32 位定时器周期模式（睡眠）",
    "timg_32bit_timer_mode_pwm_edge_sleep": "32 位定时器 PWM 边沿对齐（睡眠）",
    "timg_qei_mode": "定时器 QEI 编码器模式",
    "timx_timer_mode_capture_duty_and_period": "定时器捕获占空比与周期",
    "timx_timer_mode_capture_edge_capture": "定时器边沿捕获",
    "timx_timer_mode_compare_edge_count": "定时器比较输出边沿计数",
    "timx_timer_mode_one_shot_standby": "定时器单次模式（待机）",
    "timx_timer_mode_periodic_sleep": "定时器周期模式（睡眠）",
    "timx_timer_mode_periodic_standby": "定时器周期模式（待机）",
    "timx_timer_mode_periodic_stop": "定时器周期模式（停止）",
    "timx_timer_mode_pwm_center_stop": "定时器 PWM 中心对齐（停止）",
    "timx_timer_mode_pwm_edge_sleep": "定时器 PWM 边沿对齐（睡眠）",
    "timx_timer_mode_pwm_edge_sleep_shadow": "定时器 PWM 边沿对齐（影子寄存器）",
    "timx_timer_mode_pwm_x_trig_stop_restore": "定时器 PWM 交叉触发（停止恢复）",
    "trng_sample": "真随机数采样",
    "trng_sample_stop_restore": "真随机数采样（停止恢复）",
    "uart_echo_interrupts_standby": "UART 回显（中断+待机）",
    "uart_extend_irda_receive_packet": "UART IrDA 接收数据包",
    "uart_extend_irda_send_packet": "UART IrDA 发送数据包",
    "uart_extend_manchester_echo": "UART 曼彻斯特编码回显",
    "uart_extend_manchester_send_packet": "UART 曼彻斯特编码发送",
    "uart_external_loopback_interrupt": "UART 外部环回（中断）",
    "uart_internal_loopback_standby_restore": "UART 内部环回（待机恢复）",
    "uart_rs485_receive_packet": "UART RS-485 接收数据包",
    "uart_rs485_send_packet": "UART RS-485 发送数据包",
    "uart_rw_multibyte_fifo_poll": "UART 多字节 FIFO 读写（轮询）",
    "uart_rx_hw_flow_control": "UART 接收硬件流控",
    "uart_rx_multibyte_fifo_dma_interrupts": "UART 接收 FIFO+DMA（中断）",
    "uart_tx_console_multibyte_repeated_fifo_dma": "UART 控制台发送（重复 FIFO+DMA）",
    "uart_tx_hw_flow_control": "UART 发送硬件流控",
    "uart_tx_multibyte_fifo_dma_interrupts": "UART 发送 FIFO+DMA（中断）",
    "wwdt_interval_timer_lfosc_standby": "窗口看门狗间隔定时（内部低频晶振）",
    "wwdt_interval_timer_lfxt_standby": "窗口看门狗间隔定时（外部低频晶振）",
    "wwdt_window_mode_periodic_reset": "窗口看门狗周期复位",
}


def main() -> None:
    current = {e.id for e in list_references(REFERENCE_ROOT) if e.type == TYPE}
    expect = set(RENAMES) | set(DELETE_IDS)
    if current != expect:
        print(f"[自检红] mapping 与库内 SDK 条目不一致——多出：{current - expect}，缺失：{expect - current}")
        sys.exit(1)
    print(f"[自检] {len(current)} 条对齐，开始处理")

    for old_id in DELETE_IDS:
        if not (REFERENCE_ROOT / old_id).is_dir():
            print(f"[跳过] 已不存在：{old_id}")
            continue
        delete_reference(REFERENCE_ROOT, old_id)
        print(f"[删除] 空模板 {old_id}")

    renamed = 0
    for old_id, new_title in RENAMES.items():
        old_dir = REFERENCE_ROOT / old_id
        if not old_dir.is_dir():
            print(f"[跳过] 已不存在：{old_id}")
            continue
        new_id = _next_entry_id(REFERENCE_ROOT, new_title)
        new_dir = REFERENCE_ROOT / new_id
        if new_dir.exists():
            print(f"[告警] 目标已存在，跳过：{old_id} → {new_id}")
            continue
        meta_path = old_dir / REFERENCE_META_FILENAME
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        data["title"] = new_title
        data["id"] = new_id
        data["description"] = data["description"].rstrip() + f"（SDK 例程：{old_id}）"
        shutil.move(str(old_dir), str(new_dir))
        new_dir.joinpath(REFERENCE_META_FILENAME).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        renamed += 1
        print(f"[改名] {old_id} → {new_title}")

    print(f"\n完成：删除 {len(DELETE_IDS)} 条空模板，改名 {renamed} 条")


if __name__ == "__main__":
    main()
