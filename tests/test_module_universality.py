"""模块普适性机械拦截（工单 module-universalization/01）：题号/年份/题名黑名单。

ADR 0009：模块 = 纯驱动切片，"XX 题专用"不再是合法模块类别，简介判据④ =
无题绑定。本文件用仓库内真实模块库断言不变量（防回退）：库内模块的简介与
代码不得绑定具体赛题。黑名单词表 + 能力词白名单单源 = library.py（结构测试
与补录流程共用，改词表只改那一处——维护位置见 library.py 的
BANNED_TOPIC_WORDS / CAPABILITY_WORDS 注释）。

红证（2026-08-12 实施时）：注册表置空跑全库扫描，11 个模块命中黑名单——
其中 xunji / pid / ball_detect / lock_control / zone 五个题专用模块为工单
02~05 清理对象（输出见 .scratch/module-universalization/issues/01 实施记录）。
EXCEPTION_REGISTRY = 当前仍携带题词的模块清单（逐条理由）：02~05 清理各自
模块后必须同步删除对应条目（清理后不删条目 = 存量校验红，防漏同步）；新增
模块带题词不登记 = 红。扫描范围 = 简介（manifest.description）+ 全部 .c/.h；
manifest 的 notes 是补录/验证历史（如 delay/led_beep/oled/motor 的
"2026C/21F 真机编译过"），非简介，不拦截。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.library import find_topic_word_hits  # 判据④词表单源
from contest_generator.manifest import ModuleManifest

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"

# 已登记例外注册表（唯一出处）：当前仍携带题词的模块 → 理由。
# 条目随 02~05 工单清理删除——清理后不删条目 = test_exception_registry_entries_are_real_contamination 红。
# 已清理移除：xunji（工单 02，2026-08-12 剥离决策层为纯驱动）。
EXCEPTION_REGISTRY: dict[str, str] = {
    "pid": "工单 03 清理范围：2021F 巡线送药版 + 2026H 滚球版双题决策层",
    "ball_detect": "工单 04 清理范围：描述带 2026H H 题（代码已驱动形态）",
    "lock_control": "工单 05 清理范围（可解散）：2026C 数字钥匙状态机",
    "zone": "工单 05 清理范围（可解散）：2026C 区域划分",
    "config": "2026C 数字钥匙集中配置头——05 工单明确不动，无工单覆盖",
    "debug_uart": "2026C 门锁端调试串口（描述 + 命令注释）——无工单覆盖",
    "zigbee_uart": "2026C 门锁端 Zigbee DL-20 接收——05 工单明确不动",
    "zigbee_uart_key": "2026C 钥匙端 Zigbee DL-20 发送——05 工单明确不动",
    "filter": "描述带 2026C 出身注记（逻辑自证通用）——无工单覆盖",
    "uwb_uart": "代码注释带 2026C 遗留词（旧钥匙数据）——无工单覆盖",
}


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
