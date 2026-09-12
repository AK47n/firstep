"""模块普适性机械拦截（工单 module-universalization/01）：题号/年份/题名黑名单。

ADR 0009：模块 = 纯驱动切片，"XX 题专用"不再是合法模块类别，简介判据④ =
无题绑定。本文件用仓库内真实模块库断言不变量（防回退）：库内模块的简介与
代码不得绑定具体赛题。黑名单词表 + 能力词白名单单源 = library.py（结构测试
与补录流程共用，改词表只改那一处——维护位置见 library.py 的
BANNED_TOPIC_WORDS / CAPABILITY_WORDS 注释）。

红证（2026-08-12 实施时）：注册表置空跑全库扫描，11 个模块命中黑名单——
其中 xunji / pid / coord_detect / lock_control / zone 五个题专用模块为工单
02~05 清理对象（输出见 .scratch/module-universalization/issues/01 实施记录；
02 xunji / 03 pid / 04 coord_detect 已清理并从注册表删除对应条目；
05 lock_control / zone 已解散删除；06 config / debug_uart / zigbee_uart /
zigbee_uart_key / filter / uwb_uart 六模块题词清理完成，2026-08-12——
五条简介按四要素重写，六模块代码注释中性化，注册表清空 = 全库无题词）。
EXCEPTION_REGISTRY = 当前仍携带题词的模块清单（逐条理由）：02~06 清理各自
模块后必须同步删除对应条目（清理后不删条目 = 存量校验红，防漏同步）；新增
模块带题词不登记 = 红。扫描范围 = 简介（manifest.description）+ 全部 .c/.h；
manifest 的 notes 是补录/验证历史（如 delay/led_beep/oled/motor 的
"2026C/21F 真机编译过"），非简介，不拦截。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.library import find_topic_word_hits  # 判据④词表单源
from contest_generator.manifest import ModuleManifest, collect_exclusive_groups

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"

# 已登记例外注册表（唯一出处）：当前仍携带题词的模块 → 理由。
# 条目随 02~06 工单清理删除——清理后不删条目 = test_exception_registry_entries_are_real_contamination 红。
# 已清理移除：xunji（工单 02，2026-08-12 剥离决策层为纯驱动）；pid（工单 03，
# 2026-08-12 剥离双平台决策层为纯驱动——十字路口/启停线/LAP 状态机归骨架，
# 决策素材归档参考文件库）；coord_detect（工单 04，2026-08-12 清理 manifest
# 描述题绑定——代码本为纯驱动，描述改 K230 视觉帧解析能力方向）；lock_control /
# zone（工单 05，2026-08-12 解散——决策层归骨架，驱动残留由骨架经 config.h 宏
# + 母版 ml_gpio 内联承担，模块目录删除）；config / debug_uart / zigbee_uart /
# zigbee_uart_key / filter / uwb_uart（工单 06，2026-08-12 五条简介四要素重写 +
# 六模块代码注释中性化——注册表清空 = 全库无题词；config 代码侧专用判定参数
# 剥离另立工单 08）。
EXCEPTION_REGISTRY: dict[str, str] = {}


def _module_hits(slug: str) -> list[str]:
    """模块的简介 + 全部 .c/.h 文本的判据④命中词（能力词白名单已扣除，去重排序）。

    简介 = manifest.description；.c/.h 全量读（errors="replace"，与骨架读盘同
    容错）；notes 不扫（补录/验证历史，非简介）。
    """
    module_dir = LIBRARY_MODULES / slug
    texts: list[str] = [ModuleManifest.load(module_dir).description]
    for path in sorted(module_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".c", ".h"):
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
    hits: list[str] = []
    for text in texts:
        hits.extend(find_topic_word_hits(text))
    return sorted(set(hits))


def _all_module_hits() -> dict[str, list[str]]:
    """全库扫描：slug → 命中词（无命中不收录）。"""
    return {
        path.name: hits
        for path in sorted(LIBRARY_MODULES.iterdir())
        if path.is_dir() and (hits := _module_hits(path.name))
    }


def test_no_topic_bindings_outside_exception_registry():
    """库内不得有注册表外模块绑定具体赛题（防回退；新增模块带题词不登记 = 红）。

    红证：注册表为空时存量 11 个模块命中（含 02~05 的五个题专用模块），见本
    文件 docstring 与工单 01 实施记录。注册表 = 当前遗留清单，02~05 清理各自
    模块后删除对应条目。
    """
    offenders = {
        slug: hits
        for slug, hits in _all_module_hits().items()
        if slug not in EXCEPTION_REGISTRY
    }
    assert not offenders, (
        "以下模块绑定具体赛题（判据④ 无题绑定，ADR 0009）："
        + "；".join(f"{slug}={ '、'.join(hits)}" for slug, hits in sorted(offenders.items()))
    )


def test_exception_registry_entries_are_real_contamination():
    """注册表条目必须对应真实命中：02~05 清理模块后不删条目 = 红（防漏同步）。

    注册表是"已知遗留"清单而非永久豁免：模块清理后命中消失，条目必须在同一
    工单删除——残留条目说明清理未同步。
    """
    stale = sorted(slug for slug in EXCEPTION_REGISTRY if not _module_hits(slug))
    assert not stale, "注册表条目已无命中，应随清理删除：" + "、".join(stale)


def test_capability_words_are_not_flagged():
    """能力词白名单防误伤：只含能力词的简介不命中（巡线是能力词，不能禁）。"""
    for text in (
        "灰度循迹驱动：8 路灰度读取 + 加权质心",
        "PID 闭环控制 + 灰度循迹",
        "循迹小车电机驱动",
    ):
        assert find_topic_word_hits(text) == []


def test_topic_words_are_flagged():
    """黑名单词（题号/年份/题名词）命中即红。"""
    assert "2024H" in find_topic_word_hits("2024H 巡线题专用层")
    assert "2026C" in find_topic_word_hits("2026C 数字钥匙题专用")
    assert "钥匙" in find_topic_word_hits("解析钥匙端 DIP-4 ID 帧")
    assert "2021F" in find_topic_word_hits("2021F 巡线送药版")


def test_capability_word_does_not_shield_topic_phrase():
    """能力词不遮蔽题名引用：黑名单"巡线题"命中含能力词"巡线"但不在其区间内 → 仍红。"""
    hits = find_topic_word_hits(
        "2024H 巡线题专用", banned=("2024H", "巡线题"), capability=("巡线",)
    )
    assert hits == ["2024H", "巡线题"]


def test_blacklist_hit_inside_capability_word_is_ignored():
    """命中区间落在能力词内不计：词表把"锁"加进黑名单时，"锁定"（latch 语境）不误伤。"""
    assert find_topic_word_hits("锁定方向", banned=("锁",), capability=("锁定",)) == []


def _real_manifests() -> list[ModuleManifest]:
    return [
        ModuleManifest.load(path)
        for path in sorted(LIBRARY_MODULES.iterdir())
        if path.is_dir()
    ]


def test_exclusive_groups_aggregate_on_the_real_library():
    """真库功能组声明聚合正确（防回退，工单 recommend-exclusive-groups/01）。

    冒烟基准（2026-09-13 更新，工单 exclusive-group-gap-audit/01 全库排查同功能件）：
    gray-track = huidu/pid/xunji（8 路灰度传感器驱动），
    attitude-hold = imu_uart/jy61p/ml_mpu6050（航向保持 / 姿态传感器——三者是同一功能的
    三种硬件，用户报告「已选姿态传感器，需求句里又出现另一个姿态件」后补入 jy61p）；
    同 id label 不一致会在 collect 时抛 ManifestError（本测试能通过 = 声明一致）；
    本轮全库排查再补四组（每组都有库内文字 + 默认脚证据，见
    .scratch/exclusive-group-gap-audit/audit.md）：
    display = lcd/oled/max7219/ili9341/ili9488/st7789_para（显示 / 屏幕——「显示族互替
    同脚，一次选一块屏」）、distance = us016/ir_distance/vl53l0x/sr04（距离测量 / 测距
    传感器——「与 ir_distance 互替件同脚」）、barometer = bmp180/ms5611（气压 / 海拔
    传感器——stm32 侧同址 0xEE 不可同挂）、sound-prompt = beep/jq8900（提示输出 / 声
    ——「语音播报与蜂鸣器为提示输出互替」）。
    平台投影：mspm0 侧七组完整（neo_6m 之类单平台件不进组）；stm32 侧
    gray-track（仅 pid）与 attitude-hold（仅 ml_mpu6050）单成员 → 剔除。
    """
    manifests = _real_manifests()
    groups = collect_exclusive_groups(manifests)
    assert {g.id for g in groups} == {
        "gray-track",
        "attitude-hold",
        "zigbee-rx",
        "display",
        "distance",
        "barometer",
        "sound-prompt",
    }
    by_id = {g.id: g for g in groups}
    assert by_id["gray-track"].label == "8 路灰度传感器驱动"
    assert [m.slug for m in by_id["gray-track"].members] == ["huidu", "pid", "xunji"]
    assert by_id["attitude-hold"].label == "航向保持 / 姿态传感器"
    assert [m.slug for m in by_id["attitude-hold"].members] == [
        "imu_uart",
        "jy61p",
        "ml_mpu6050",
    ]
    assert by_id["zigbee-rx"].label == "Zigbee 无线链路（接收侧）"
    assert [m.slug for m in by_id["zigbee-rx"].members] == ["zigbee_link", "zigbee_uart"]
    assert {
        m.slug: m.role for m in by_id["zigbee-rx"].members
    } == {
        "zigbee_link": "任意字节帧收发（双机/双车无线数据通信）",
        "zigbee_uart": "固定 DIP-4 ID 帧接收（身份识别/信标上报，与 zigbee_uart_key 配对）",
    }
    # 本轮新增四组：成员清单按库登记序（模块目录字典序）
    assert by_id["display"].label == "显示 / 屏幕"
    assert [m.slug for m in by_id["display"].members] == [
        "ili9341",
        "ili9488",
        "lcd",
        "max7219",
        "oled",
        "st7789_para",
    ]
    assert by_id["distance"].label == "距离测量 / 测距传感器"
    assert [m.slug for m in by_id["distance"].members] == [
        "ir_distance",
        "sr04",
        "us016",
        "vl53l0x",
    ]
    assert by_id["barometer"].label == "气压 / 海拔传感器"
    assert [m.slug for m in by_id["barometer"].members] == ["bmp180", "ms5611"]
    assert by_id["sound-prompt"].label == "提示输出 / 声"
    assert [m.slug for m in by_id["sound-prompt"].members] == ["beep", "jq8900"]
    # mspm0 侧七组完整；stm32 侧 gray/attitude 两组单成员 → 剔除
    msp_groups = collect_exclusive_groups(manifests, platform="mspm0")
    assert {g.id for g in msp_groups} == {
        "gray-track",
        "attitude-hold",
        "zigbee-rx",
        "display",
        "distance",
        "barometer",
        "sound-prompt",
    }
    assert [g.id for g in collect_exclusive_groups(manifests, platform="stm32")] == [
        "sound-prompt",
        "barometer",
        "display",
        "distance",
        "zigbee-rx",
    ]


def test_hard_exclusive_pairs_are_covered_by_manifest_groups():
    """生成侧硬互斥对（generator.HARD_EXCLUSIVE_PAIRS）必须是某 manifest 互斥
    组的同组成员（双源防漂移：组加成员不自动进硬表 = 静默空洞，本测试拦截）。"""
    from contest_generator.generator import HARD_EXCLUSIVE_PAIRS

    manifests = _real_manifests()
    groups = collect_exclusive_groups(manifests)
    for left, right, _reason in HARD_EXCLUSIVE_PAIRS:
        same_group = any(
            {left, right} <= {m.slug for m in group.members} for group in groups
        )
        assert same_group, f"硬互斥对 {left}/{right} 未在任一 manifest 互斥组内"
