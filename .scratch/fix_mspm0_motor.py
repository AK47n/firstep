"""参考库条目修复（.scratch 工具脚本）：MSPM0_MOTOR参考例程 GBK 补录 + 剥负载 + 拆 3 条。

现条目「MSPM0_MOTOR参考例程」1630 文件 39MB 名不副实，三处问题：
①核心电机源码 7 个 GBK 编码文件（motor_crc.{c,h} / motor_read_enc.c /
motor_set_speed.{c,h} / user.h / m0imu/imu.c）被 register_materials.py 的
iter_text_files（只试 UTF-8、失败静默跳过）漏录——"电机控制参考例程"条目里
没有电机控制实现代码；②source/（1585 个 TI SDK 副本文件 37MB）+ gcc/iar/keil/
ticlang 工具链胶水 + keil/Objects 构建产物违反 driverlib 批次排除规则（commit
5052b67 明确排除同一批树）；③素材清单.txt 129575 字符排 files 首位，全文回读
4000 字符截断下模型一个代码字符都看不到。

修：GBK 转码补录 7 文件（读镜像 bytes → gbk 解码 → utf-8 写入库，转码失败
大声报错不静默；empty.c 同为 GBK 但空模板按 driverlib 先例不保，前置自检照读
留痕）、剥垃圾负载（镜像保真不动 + 旧清单留痕，脚本打印对照）、拆 3 条——
「MSPM0 Motor_Ctrl 电机控制例程」「MSPM0 m0imu 姿态例程」（type=参考例程）+「MSPM0
MOTOR 例程移植笔记」（type=移植笔记）。素材清单.txt 用 build_material_manifest 对
镜像对应子目录重新生成（MSP_Motor_Ctrl / m0imu 各自）。

机制：新条目走 add_reference 结构校验入库（条目目录名由标题生成），旧条目走
delete_reference 删除（官方 API）。写库自动提交（autocommit）照常触发——每条
写入各一条 git 提交（只含 library/ 子树），跑完按惯例 squash 成一条（本脚本
不碰 config.json）。

幂等：旧 id 目录不存在且 3 条新条目俱在即跳过（修复已完成）；目标条目已存在
即红（半成品残留，需人工清理后重跑）。前置自检：GBK 文件逐件解码自检；旧条目
files 按「续留 8 文件 / 剥离其余」完全划分且剥离文件全部仍在镜像（镜像保真，
不丢数据）；7 个 GBK 文件不在旧条目 files 里（补录前提）。收尾自检：3 条新条目
逐条回读 + 转码文件 utf-8 全文可见。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# Windows 控制台默认 GBK 会打花中文日志：脚本输出统一 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from contest_generator import config  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    _next_entry_id,
    add_reference,
    build_material_manifest,
    delete_reference,
    get_reference,
)

MODULE_ROOT = REPO_ROOT / "library" / "modules"
REFERENCE_ROOT = config.reference_library_dir(MODULE_ROOT)
MATERIALS_ROOT = config.materials_dir(MODULE_ROOT)

OLD_ID = "MSPM0_MOTOR参考例程"
MIRROR = MATERIALS_ROOT / OLD_ID  # 保真镜像（sources/materials），只读
MANIFEST_NAME = "素材清单.txt"

# 镜像中 GBK 编码、被 UTF-8 直读静默跳过的核心源码（相对镜像根，补录对象）
GBK_FILES: tuple[tuple[str, str], ...] = (
    ("MSP_Motor_Ctrl/motor_crc.c", "motor_crc.c"),
    ("MSP_Motor_Ctrl/motor_crc.h", "motor_crc.h"),
    ("MSP_Motor_Ctrl/motor_read_enc.c", "motor_read_enc.c"),
    ("MSP_Motor_Ctrl/motor_set_speed.c", "motor_set_speed.c"),
    ("MSP_Motor_Ctrl/motor_set_speed.h", "motor_set_speed.h"),
    ("MSP_Motor_Ctrl/user.h", "user.h"),
    ("m0imu/imu.c", "imu.c"),
)
# 同为 GBK 但空模板按 driverlib 先例不保（前置自检照读留痕，不入库）
GBK_EXCLUDED = "empty.c"

# 旧条目 files 中续留的 8 个文件（镜像同路径读取，新条目内去子目录前缀 / 原名）
CARRIED_FILES: tuple[tuple[str, str], ...] = (
    ("MSP_Motor_Ctrl/motor_read_enc.h", "motor_read_enc.h"),
    ("MSP_Motor_Ctrl/user.c", "user.c"),
    ("m0imu/imu.h", "imu.h"),
    ("README.md", "README.md"),
    ("移植.md", "移植.md"),
    ("empty.syscfg", "empty.syscfg"),
    ("ti_msp_dl_config.c", "ti_msp_dl_config.c"),
    ("ti_msp_dl_config.h", "ti_msp_dl_config.h"),
)
# 每个新条目共享的工程底板文件（镜像根，原名入库）
SHARED_FILES = ("ti_msp_dl_config.c", "ti_msp_dl_config.h", "empty.syscfg")

MOTOR_TITLE = "MSPM0 Motor_Ctrl 电机控制例程"
IMU_TITLE = "MSPM0 m0imu 姿态例程"
NOTES_TITLE = "MSPM0 MOTOR 例程移植笔记"

TYPE_EXAMPLE = "参考例程"
TYPE_NOTES = "移植笔记"

MOTOR_DESCRIPTION = (
    "TI MSPM0G3507 电机控制参考例程（MSP_Motor_Ctrl）：经 UART 以类 Modbus "
    "协议与电机驱动器通信，实现 4 路电机速度控制与编码器值回读。文件构成："
    "motor_set_speed 组帧下发（写多寄存器命令 0x10 设 4 路速度 / 写单寄存器命令 "
    "0x06 设闭环模式），motor_read_enc 接收状态机解析驱动器上报的编码器寄存器帧"
    "（0x0A 从站地址 + CRC16 校验 + 高低字节拼接，结果存 modbus_date[8] 累计编码"
    "器值），motor_crc 为 CRC16 查表实现，user 为 Keil 微库 stdio 适配；"
    "ti_msp_dl_config / empty.syscfg 为 SysConfig 时钟与 UART 初始化（MFCLK 4MHz "
    "波特率基准，115200 8N1）。SDK 依赖：TI MSPM0 SDK DriverLib（DL_UART_Main_"
    "transmitData / DL_UART_Main_receiveData 等）；README.md 为工程底板（SDK empty "
    "例程）说明。工具链工程与 SDK 副本树（source/ 1585 文件、gcc / iar / keil / "
    "ticlang）不入库，保留在 sources/materials 镜像。"
)

IMU_DESCRIPTION = (
    "TI MSPM0G3507 姿态参考例程（m0imu）：经 UART（115200 8N1）以类 ModbusRTU "
    "协议读取 IMU 陀螺仪模块的角度与角速度。imu.c 的 Gyro_ParseFrame 接收状态机"
    "解析数据帧 0A 03 04 [角度H/L][角速度H/L][CRC_L/CRC_H]（0x0A 帧头 + CRC16 "
    "校验，结果存 gyro_angle_raw / gyro_dps_raw / gyro_rx_done），"
    "Gyro_ConfigReportRateRx 发送 AA 06 01 01 01 AD 00 配置命令开启数据上报；"
    "CRC16 依赖 motor_crc.c/h（在「MSPM0 Motor_Ctrl 电机控制例程」条目）。"
    "SDK 依赖：DriverLib + SysConfig 生成 ti_msp_dl_config / empty.syscfg（MFCLK "
    "4MHz 波特率基准）。移植要点（引脚映射 / 波特率计算 / 中断配置 / 调试诊断）见"
    "「MSPM0 MOTOR 例程移植笔记」条目。"
)

NOTES_DESCRIPTION = (
    "TI MSPM0G3507 IMU 陀螺仪模块（m0imu）移植指南笔记：把参考例程的 IMU 模块"
    "移植到地猛星开发板的完整过程。覆盖：模块概览（UART 115200 8N1、类 "
    "ModbusRTU 协议、0xAA 配置 / 0x0A 数据从站地址、数据帧与配置命令格式、依赖 "
    "motor_crc）→ 移植前检查清单（UART 引脚映射、MFCLK 必须 4MHz 的时钟树推导与 "
    "IBRD/FBRD 波特率除数计算表、UART RX 中断配置）→ 移植步骤（复制文件 / "
    "SysConfig 配 UART / 关键宏确认）→ 调试诊断（示波器抓波形 / 回环测试等分层"
    "定位）→ 快速问题排查表 → 稳定性改进建议（超时恢复、帧头搜索、动态 CRC）→ "
    "关键经验总结（内部 RC 振荡器精度、RX 引脚上拉、上电时序、中断优先级）。"
)

# 剥负载前缀（旧条目 files 中这些路径一律不续留；镜像保真 + 旧清单留痕）
STRIPPED_PREFIXES = ("source/", "gcc/", "iar/", "keil/", "ticlang/")
STRIPPED_TOP_LEVEL = ("素材清单.txt", "Event.dot", "README.html")


def _read_transcoded(mirror_rel: str) -> str:
    """镜像 GBK 文件 → utf-8 文本（\r\n 归一化，与库内既有文本一致）；失败大声报错。"""
    data = (MIRROR / mirror_rel).read_bytes()
    try:
        content = data.decode("gbk")
    except UnicodeDecodeError as exc:
        print(f"[转码红] {mirror_rel} GBK 解码失败：{exc}")
        sys.exit(1)
    return content.replace("\r\n", "\n")


def _check_gbk_roundtrip() -> None:
    """前置自检：7 个补录文件逐件 gbk 解码通过 + utf-8 直读必失败（状态与工单核实一致）。"""
    for mirror_rel, _new_rel in GBK_FILES:
        data = (MIRROR / mirror_rel).read_bytes()
        data.decode("gbk")  # 失败即抛（大声）
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        print(f"[自检红] {mirror_rel} 已是 UTF-8——镜像状态与工单核实不符，停下人工核对")
        sys.exit(1)
    empty_data = (MIRROR / GBK_EXCLUDED).read_bytes()
    empty_data.decode("gbk")  # 照读留痕（空模板按 driverlib 先例不保）
    print(f"[自检] 7 个 GBK 补录文件逐件解码通过（utf-8 直读全失败，与漏录机理一致）；"
          f"empty.c 同为 GBK、空模板不保（{len(empty_data)}B 留镜像）")


def _read_utf8(mirror_rel: str) -> str:
    """镜像 UTF-8 文件直读（严格）；失败大声报错。"""
    try:
        return (MIRROR / mirror_rel).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        print(f"[读取红] {mirror_rel} 非 UTF-8：{exc}")
        sys.exit(1)


def main() -> None:
    if not MIRROR.is_dir():
        print(f"[自检红] 镜像目录不存在：{MIRROR}（保真件缺失，停下人工核对）")
        sys.exit(1)

    old_dir = REFERENCE_ROOT / OLD_ID
    new_titles = (MOTOR_TITLE, IMU_TITLE, NOTES_TITLE)
    new_ids = {title: _next_entry_id(REFERENCE_ROOT, title) for title in new_titles}

    if not old_dir.is_dir():
        # 幂等：旧条目已删——3 条新条目俱在 = 修复已完成；否则 = 半成品残留
        missing = [t for t in new_titles if not (REFERENCE_ROOT / new_ids[t]).is_dir()]
        if missing:
            print(f"[自检红] 旧条目已不存在但新条目缺失：{missing}——人工核对后清理残留")
            sys.exit(1)
        print(f"[跳过] 旧条目已不存在、3 条新条目俱在，修复已完成：{OLD_ID}")
        return

    # 目标条目不可已存在（半成品残留 = 需人工清理，不静默跳过也不加 -2 后缀重名）
    for title in new_titles:
        if (REFERENCE_ROOT / new_ids[title]).exists():
            print(f"[自检红] 目标条目已存在：{new_ids[title]}（{title}）——人工清理后重跑")
            sys.exit(1)

    _check_gbk_roundtrip()

    old = get_reference(REFERENCE_ROOT, OLD_ID)
    old_files = set(old.files)

    # 前置自检：补录的 7 个 GBK 文件不在旧条目 files 里（漏录前提，否则状态不符）
    in_old = [f for f, _ in GBK_FILES if f in old_files]
    if in_old:
        print(f"[自检红] 以下文件已在旧条目 files 里，与「GBK 漏录」核实不符：{in_old}")
        sys.exit(1)

    # 前置自检：旧条目 files 按「续留 8 文件 / 剥离其余」完全划分 + 剥离文件全在镜像
    carried = {mirror_rel for mirror_rel, _ in CARRIED_FILES}
    missing_carried = carried - old_files
    if missing_carried:
        print(f"[自检红] 续留文件不在旧条目 files 里：{sorted(missing_carried)}")
        sys.exit(1)
    stripped = old_files - carried
    for rel in sorted(stripped):
        # 素材清单.txt 是注册时由镜像生成的索引（镜像本无此文件），留痕靠
        # git 历史（旧清单 1729 行）；其余剥离文件必须仍在镜像（保真件）
        if rel == MANIFEST_NAME:
            continue
        if not (MIRROR / rel).is_file():
            print(f"[自检红] 剥离文件不在镜像（保真缺失）：{rel}")
            sys.exit(1)
    # 剥离面必须正是工单核实的负载类别（多剥/错剥即红）
    unexpected = {
        rel
        for rel in stripped
        if not any(
            rel == name or rel.startswith(prefix)
            for name in STRIPPED_TOP_LEVEL
            for prefix in (name, *STRIPPED_PREFIXES)
        )
    }
    if unexpected:
        print(f"[自检红] 剥离面超出核实范围：{sorted(unexpected)}")
        sys.exit(1)
    by_top = {rel.split("/", 1)[0]: 0 for rel in stripped}
    for rel in stripped:
        by_top[rel.split("/", 1)[0]] += 1
    print(f"[自检] 旧条目 {len(old_files)} 文件：续留 {len(carried)} + 剥离 {len(stripped)}"
          f"（全部仍在镜像，镜像保真对照通过）")
    print(f"[对照] 剥离负载：{sorted(by_top.items(), key=lambda kv: -kv[1])}")
    print(f"[对照] 剥离负载在镜像 + 旧清单（{len(old_files)} 条记录）留痕，"
          f"git 历史可查——不丢数据")

    # 组 3 条新条目 files：GBK 转码补录 + 镜像 UTF-8 直读 + 素材清单重新生成
    motor_files: dict[str, str] = {}
    for mirror_rel, new_rel in GBK_FILES:
        if mirror_rel.startswith("MSP_Motor_Ctrl/"):
            motor_files[new_rel] = _read_transcoded(mirror_rel)
    for mirror_rel, new_rel in CARRIED_FILES:
        if mirror_rel.startswith("MSP_Motor_Ctrl/"):
            motor_files[new_rel] = _read_utf8(mirror_rel)
    for name in SHARED_FILES:
        motor_files[name] = _read_utf8(name)
    motor_files["README.md"] = _read_utf8("README.md")
    motor_files[MANIFEST_NAME] = build_material_manifest(MIRROR / "MSP_Motor_Ctrl")

    imu_files: dict[str, str] = {}
    for mirror_rel, new_rel in GBK_FILES:
        if mirror_rel.startswith("m0imu/"):
            imu_files[new_rel] = _read_transcoded(mirror_rel)
    imu_files["imu.h"] = _read_utf8("m0imu/imu.h")
    for name in SHARED_FILES:
        imu_files[name] = _read_utf8(name)
    imu_files[MANIFEST_NAME] = build_material_manifest(MIRROR / "m0imu")

    notes_files = {"移植.md": _read_utf8("移植.md")}

    # 收尾自检（写库前）：电机条目 = GBK 6 + 续留 2 + 共享 3 + README + 清单 = 13
    expect_motor = 6 + 2 + 3 + 1 + 1
    if len(motor_files) != expect_motor:
        print(f"[自检红] 电机条目文件数 {len(motor_files)} != {expect_motor}")
        sys.exit(1)

    for title, type_, description, files in (
        (MOTOR_TITLE, TYPE_EXAMPLE, MOTOR_DESCRIPTION, motor_files),
        (IMU_TITLE, TYPE_EXAMPLE, IMU_DESCRIPTION, imu_files),
        (NOTES_TITLE, TYPE_NOTES, NOTES_DESCRIPTION, notes_files),
    ):
        entry = add_reference(
            REFERENCE_ROOT,
            title=title,
            type=type_,
            description=description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            files=files,
            kit_vocabulary=(),
            platform=PLATFORM_MSPM0,
        )
        print(f"[新增] {entry.id}（{len(entry.files)} 文件）")

    delete_reference(REFERENCE_ROOT, OLD_ID)
    print(f"[删除] {OLD_ID}")

    # 收尾自检：3 条新条目回读 + 转码文件 utf-8 全文可见（motor_set_speed.c 中文注释）
    for title, new_rel, marker in (
        (MOTOR_TITLE, "motor_set_speed.c", "从站地址"),
        (MOTOR_TITLE, "motor_read_enc.c", "存储累计编码器值"),
        (IMU_TITLE, "imu.c", "Gyro_ParseFrame"),
    ):
        entry = get_reference(REFERENCE_ROOT, new_ids[title])
        content = (REFERENCE_ROOT / entry.id / new_rel).read_text(encoding="utf-8")
        if marker not in content:
            print(f"[收尾红] {entry.id}/{new_rel} 全文回读不见 {marker!r}")
            sys.exit(1)
        print(f"[收尾] {entry.id}/{new_rel} utf-8 全文回读可见（{marker}，{len(content)} 字符）")

    print(f"\n完成：GBK 补录 7 文件 + 拆 3 条新条目 + 删除旧条目"
          f"（自动提交 4 条，事后 squash 成一条）")


if __name__ == "__main__":
    main()
