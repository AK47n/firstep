"""参考库条目拆分（.scratch 工具脚本）：塔克R3两驱小车底盘资料 → 6 条独立条目。

现条目「塔克R3两驱小车底盘资料」把 6 个互相独立的完整工程装成一条（193 文件）：
DB20_1 直流电机调速 / DB20_2 编码器数据采集 / DB20_3 PID 速度控制 / DB20_4 PID
位置控制 / DB20_5 舵机角度控制（STM32F10x 标准库）+ 编码器电机小车控制源码
V1.0.230626（STM32F4xx）。一条 entry 的后果：标题/简介只覆盖"底盘资料"整体，
搜"舵机角度"命中不了；全文回读被 4000 字符总截断卡死在前几个文件。拆成 6 条
（driverlib 每例一条同款先例），每条独立标题/简介/文件集，搜索、推荐、全文
三处可精确命中。

机制：新条目走 add_reference 结构校验入库（条目目录名由标题生成），旧条目走
delete_reference 删除（官方 API）。每条目带 素材清单.txt（复制旧清单全文，
索引同源 PDF/zip，6 条共享无害）；O 资料更新记录.txt 归入 DB20_1 条目，保证
并集不丢。写库自动提交（autocommit）照常触发——每条写入各一条 git 提交，
跑完按惯例 squash 成一条（本脚本不碰 config.json，与 rename_mspm0_refs.py
先例不同处在于自动提交改为事后 squash）。

幂等：旧 id 目录不存在即跳过（拆分已完成）；目标条目已存在即红（半成品残留，
需人工清理后重跑）。前置自检：旧条目 files 按 6 个子工程目录 + 2 个顶层文件
完全划分且数量逐条对齐（多/少即红）；拆分后 6 条 files 回挂旧前缀取并集 vs
旧条目 files 并集逐条对照（不丢不重）。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator import config  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    _next_entry_id,
    add_reference,
    delete_reference,
    get_reference,
)

REFERENCE_ROOT = config.reference_library_dir(REPO_ROOT / "library" / "modules")

OLD_ID = "塔克R3两驱小车底盘资料"
TYPE = "小车底盘例程"
MANIFEST_NAME = "素材清单.txt"
UPDATE_LOG_NAME = "O 资料更新记录.txt"
# 顶层共享文件（旧条目 files 中不带子工程前缀的整文件）
TOP_LEVEL_NAMES = (MANIFEST_NAME, UPDATE_LOG_NAME)

# (新标题, 旧子工程目录前缀, 简介, 期望子工程文件数) —— 数量与工单现状核实对齐
SPLITS: tuple[tuple[str, str, str, int], ...] = (
    (
        "塔克R3 DB20 直流电机调速",
        "DB20_1直流电机调速",
        "塔克创新 R3 系列两驱小车底盘 DB20 电机 PID 闭环教程第 1 例：直流电机 PWM "
        "调速开环演示。STM32F103C8T6 + 标准外设库 V3.5.0（X-CTR000 控制器，72MHz）："
        "AX_MOTOR_Init 设置 10K PWM 频率，AX_MOTOR_SetSpeed 占空比 0→2000 逐档变速、"
        "正转与反转交替运行，OLED 实时显示速度值。文件构成：Doc 说明 + User 主程序 + "
        "X-SOFT 全套 ax_* 封装驱动（电机 / 编码器 / 舵机 / 按键 / OLED / 调试串口等）；"
        "本条目另收资料包 O 资料更新记录.txt。第 2 例起依次引入编码器测量与 PID 闭环。",
        31,
    ),
    (
        "塔克R3 DB20 编码器数据采集",
        "DB20_2编码器数据采集",
        "塔克创新 R3 系列两驱小车底盘 DB20 电机 PID 闭环教程第 2 例：正交 AB 编码器 "
        "数据采集。STM32F103C8T6 + 标准外设库 V3.5.0（X-CTR000 控制器）：AX_ENCODER_Init "
        "配置正交计数，每 200ms 读取计数值经调试串口打印并 OLED 显示，手动转动电机即可"
        "观察数值变化——是第 3/4 例速度环与位置环的测量基础。文件构成：Doc 说明 + "
        "User 主程序 + X-SOFT 全套 ax_* 封装驱动。",
        31,
    ),
    (
        "塔克R3 DB20 PID 速度控制",
        "DB20_3PID速度控制",
        "塔克创新 R3 系列两驱小车底盘 DB20 电机 PID 闭环教程第 3 例：PID 速度闭环。"
        "STM32F103C8T6 + 标准外设库 V3.5.0（X-CTR000 控制器）：以编码器周期增量值为"
        "速度反馈，PID_MotorVelocityPidCtl 对目标速度（±250）做速度环，OLED 显示目标 / "
        "当前速度与 PID 参数，X-PrintfScope 上位机可设定目标速度与 PID 参数并绘制速度"
        "曲线。与第 4 例的区别：本例闭环对象是速度增量，第 4 例是位置绝对值。文件构成："
        "Doc 说明 + User 主程序 + X-SOFT 全套 ax_* 封装驱动。",
        31,
    ),
    (
        "塔克R3 DB20 PID 位置控制",
        "DB20_4PID位置控制",
        "塔克创新 R3 系列两驱小车底盘 DB20 电机 PID 闭环教程第 4 例：PID 位置闭环。"
        "STM32F103C8T6 + 标准外设库 V3.5.0（X-CTR000 控制器）：以编码器绝对计数值为"
        "位置反馈，PID_MotorPositionPidCtl 对目标位置（±250，上位机可设 ±32767）做 "
        "位置环，OLED 显示目标 / 当前位置与 PID 参数，X-PrintfScope 上位机可设定目标"
        "位置与 PID 参数并绘制位置曲线。与第 3 例的区别：本例闭环对象是位置绝对值，"
        "第 3 例是速度增量。文件构成：Doc 说明 + User 主程序 + X-SOFT 全套 ax_* 封装驱动。",
        33,
    ),
    (
        "塔克R3 DB20 舵机角度控制",
        "DB20_5舵机角度控制",
        "塔克创新 R3 系列两驱小车底盘 DB20 电机 PID 闭环教程第 5 例：8 路舵机角度控制。"
        "STM32F103C8T6 + 标准外设库 V3.5.0（X-CTR000 控制器）：ax_timer_int 定时器中断 "
        "产生多路 PWM，ax_servo 驱动最多 8 路舵机在 30°/90°/150° 间隔循环运动（多路 "
        "舵机 / 大扭矩负载时注意供电能力）。文件构成：Doc 说明 + User 主程序（含定时器"
        "中断）+ X-SOFT 全套 ax_* 封装驱动。",
        33,
    ),
    (
        "塔克R3 编码器电机小车控制源码",
        "编码器电机小车控制源码V1.0.230626",
        "塔克创新 R3 系列两驱小车底盘控制源码 V1.0.230626：OpenCTR H60 V3.2 控制器 / "
        "STM32F407VET6（168MHz）整车工程。功能：五种底盘（麦轮 / 四轮差速 / 两轮差速 / "
        "阿克曼 / 三轮全向）正逆运动学解析、车轮 PID 速度控制、PS2 手柄与上位机控制"
        "（塔克通用 X-Protocol 串口协议，20ms / 50Hz 周期调度）。文件构成：Robot（main + "
        "ax_kinematics 运动学 / ax_robot 底盘速度 / ax_speed 车轮 PID）+ Driver 层 ax_* "
        "封装驱动（电机 / 编码器 / PS2 / 舵机 / 串口等）。与 DB20 五例（F103 单功能教学"
        "例程）不同，本工程是 F4 整车底盘控制源码。",
        32,
    ),
)


def _read_files(old_dir: Path, old_files: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """按拆分表把旧条目 files 重排成 6 份 {新相对路径: 内容}。

    子工程文件去掉旧前缀入库；素材清单.txt 全文复制进每条（自持优先）；
    O 资料更新记录.txt 归入 DB20_1 条目。
    """
    new_files: dict[str, dict[str, str]] = {}
    for title, prefix, _description, _count in SPLITS:
        files: dict[str, str] = {}
        for rel in old_files:
            if rel.startswith(prefix + "/"):
                files[rel[len(prefix) + 1 :]] = (old_dir / rel).read_text(encoding="utf-8")
        files[MANIFEST_NAME] = (old_dir / MANIFEST_NAME).read_text(encoding="utf-8")
        if prefix == "DB20_1直流电机调速":
            files[UPDATE_LOG_NAME] = (old_dir / UPDATE_LOG_NAME).read_text(encoding="utf-8")
        new_files[title] = files
    return new_files


def _rebuilt_union(new_files: dict[str, dict[str, str]]) -> set[str]:
    """6 条新条目 files 回挂旧前缀取并集（顶层共享文件原样计入，集合语义）。"""
    rebuilt: set[str] = set()
    for _title, prefix, _description, _count in SPLITS:
        for rel in new_files[_title]:
            if rel in TOP_LEVEL_NAMES:
                rebuilt.add(rel)
            else:
                rebuilt.add(f"{prefix}/{rel}")
    return rebuilt


def main() -> None:
    old_dir = REFERENCE_ROOT / OLD_ID
    if not old_dir.is_dir():
        print(f"[跳过] 旧条目已不存在，拆分已完成：{OLD_ID}")
        return

    # 目标条目不可已存在（半成品残留 = 需人工清理，不静默跳过也不加 -2 后缀重名）
    for title, _prefix, _description, _count in SPLITS:
        entry_id = _next_entry_id(REFERENCE_ROOT, title)
        if (REFERENCE_ROOT / entry_id).exists():
            print(f"[自检红] 目标条目已存在：{entry_id}（{title}）——人工清理后重跑")
            sys.exit(1)

    old = get_reference(REFERENCE_ROOT, OLD_ID)
    old_files = set(old.files)

    # 前置自检：旧条目 files 按 6 个子工程 + 2 个顶层文件完全划分且数量对齐
    by_prefix: dict[str, set[str]] = {}
    for rel in old_files:
        by_prefix.setdefault(rel.split("/", 1)[0], set()).add(rel)
    expect_prefixes = {prefix for _t, prefix, _d, _c in SPLITS} | set(TOP_LEVEL_NAMES)
    if set(by_prefix) != expect_prefixes:
        print(f"[自检红] 旧条目顶层划分不对——多出：{set(by_prefix) - expect_prefixes}，"
              f"缺失：{expect_prefixes - set(by_prefix)}")
        sys.exit(1)
    for _title, prefix, _description, expect_count in SPLITS:
        if len(by_prefix[prefix]) != expect_count:
            print(f"[自检红] {prefix} 文件数 {len(by_prefix[prefix])} != {expect_count}")
            sys.exit(1)
    for name in TOP_LEVEL_NAMES:
        if by_prefix[name] != {name}:
            print(f"[自检红] 顶层文件形态异常：{name} → {by_prefix[name]}")
            sys.exit(1)
    print(f"[自检] 旧条目 {len(old_files)} 文件按 6 子工程 + 2 顶层文件完全划分")

    new_files = _read_files(old_dir, old.files)

    # 并集自检：拆分后 6 条 files 并集 vs 旧条目 files 并集逐条对照（不丢不重）
    rebuilt = _rebuilt_union(new_files)
    if rebuilt != old_files:
        print(f"[自检红] 并集不等——缺失：{sorted(old_files - rebuilt)}，"
              f"多出：{sorted(rebuilt - old_files)}")
        sys.exit(1)
    print(f"[自检] 6 条 files 并集 == 旧条目 files 并集（{len(old_files)} 文件，不丢不重）")

    for title, _prefix, description, _count in SPLITS:
        entry = add_reference(
            REFERENCE_ROOT,
            title=title,
            type=TYPE,
            description=description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            files=new_files[title],
            kit_vocabulary=(),
            platform=PLATFORM_STM32,
        )
        print(f"[新增] {entry.id}（{len(entry.files)} 文件）")

    delete_reference(REFERENCE_ROOT, OLD_ID)
    print(f"[删除] {OLD_ID}")
    print(f"\n完成：拆分 6 条新条目 + 删除旧条目（自动提交 7 条，事后 squash 成一条）")


if __name__ == "__main__":
    main()
