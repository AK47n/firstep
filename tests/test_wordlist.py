"""硬件词表（wordlist.py）测试：solutions 解析（工单 buy-guide/01）。

词表解析耦合到包内默认词表（DEFAULT_WORDLIST=load_wordlist() 模块级），
解析用例全部用临时词表文件 + 显式路径，测试自足不依赖库内容；末尾保留
少量真实词表回归（test_default_wordlist_*）钉「库内已有」引用与方案形状。
"""

from __future__ import annotations

import pytest

from contest_generator.wordlist import (
    HardwareWordGroup,
    SolutionOption,
    WordlistError,
    category_names,
    format_wordlist_prompt,
    load_wordlist,
    model_names,
)


def _write(tmp_path, content):
    path = tmp_path / "wordlist.json"
    path.write_text(content, encoding="utf-8")
    return path  # noqa: RET504 路径显式传 load_wordlist


def test_load_wordlist_without_solutions_ok(tmp_path):
    """旧词表（无 solutions 键）向后兼容：解析成功、solutions 空。"""
    path = _write(
        tmp_path, '[{"category": "视觉模块", "models": ["K230", "OpenMV"]}]'
    )
    groups = load_wordlist(path)
    assert len(groups) == 1
    assert groups[0].solutions == ()


def test_load_wordlist_solutions_parsed(tmp_path):
    """solutions 解析：字段映射 + recommended 默认 False + 可空字符串。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "models": ["超声波传感器"], '
        '"solutions": ['
        '{"name": "HC-SR04", "interface": "GPIO", "price": "￥3-8/个", '
        '"note": "测2cm-4m", "suitable": "避障", "recommended": true},'
        '{"name": "JSN-SR04T"}]}]',
    )
    groups = load_wordlist(path)
    solutions = groups[0].solutions
    assert len(solutions) == 2
    assert solutions[0] == SolutionOption(
        name="HC-SR04",
        interface="GPIO",
        price="￥3-8/个",
        note="测2cm-4m",
        suitable="避障",
        recommended=True,
    )
    assert solutions[1].recommended is False
    assert solutions[1].interface == ""


def test_load_wordlist_solutions_missing_name_rejected(tmp_path):
    """solutions 条目缺 name → WordlistError（确定性知识宁缺毋编）。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": [{"price": "￥3"}]}]',
    )
    with pytest.raises(WordlistError, match="缺 name"):
        load_wordlist(path)


def test_load_wordlist_solutions_not_array_rejected(tmp_path):
    """solutions 非数组 → WordlistError。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": {"name": "HC-SR04"}}]',
    )
    with pytest.raises(WordlistError, match="solutions 必须是数组"):
        load_wordlist(path)


def test_load_wordlist_solutions_recommended_not_bool_rejected(tmp_path):
    """recommended 非布尔 → WordlistError（形状硬约束）。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": '
        '[{"name": "HC-SR04", "recommended": "yes"}]}]',
    )
    with pytest.raises(WordlistError, match="recommended 必须是布尔"):
        load_wordlist(path)


def test_format_wordlist_prompt_shows_solution_names(tmp_path):
    """科普段带方案名（紧凑）：名称 + 推荐标记，详情不进 prompt。"""
    groups = (
        HardwareWordGroup(
            category="感知传感器",
            models=("超声波传感器",),
            solutions=(
                SolutionOption(name="HC-SR04", recommended=True),
                SolutionOption(name="JSN-SR04T"),
            ),
        ),
    )
    prompt = format_wordlist_prompt(groups)
    assert "选购方案" in prompt
    assert "HC-SR04（推荐）" in prompt
    assert "JSN-SR04T" in prompt


def test_wordlist_static_helpers():
    """category_names / model_names 仍正确（覆盖 models 跨组收集）。"""
    groups = (
        HardwareWordGroup(category="视觉模块", models=("K230", "OpenMV")),
        HardwareWordGroup(category="声光提示器件", models=("LED",)),
    )
    assert category_names(groups) == {"视觉模块", "声光提示器件"}
    assert model_names(groups) == {"K230", "OpenMV", "LED"}


def test_load_wordlist_solutions_lib_modules_parsed(tmp_path):
    """lib_modules 解析：缺失=()；数组映射 tuple；to_dict 带出列表。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "models": [], "solutions": ['
        '{"name": "红外对管循迹数组（低价替代）", "lib_modules": ["xunji", "pid"]},'
        '{"name": "超声波测距（HC-SR04）"}]}]',
    )
    groups = load_wordlist(path, lib_slugs=frozenset({"xunji", "pid"}))
    solutions = groups[0].solutions
    assert solutions[0].lib_modules == ("xunji", "pid")
    assert solutions[1].lib_modules == ()
    assert solutions[0].to_dict()["lib_modules"] == ["xunji", "pid"]
    assert solutions[1].to_dict()["lib_modules"] == []


def test_load_wordlist_solutions_lib_modules_not_array_rejected(tmp_path):
    """lib_modules 非数组 → WordlistError（形状硬约束，与 recommended 同严格度）。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": '
        '[{"name": "A", "lib_modules": "xunji"}]}]',
    )
    with pytest.raises(WordlistError, match="lib_modules 必须是数组"):
        load_wordlist(path)


def test_load_wordlist_solutions_lib_modules_bad_element_rejected(tmp_path):
    """lib_modules 元素非字符串 / 空串 → WordlistError。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": '
        '[{"name": "A", "lib_modules": ["xunji", 3]}]}]',
    )
    with pytest.raises(WordlistError, match="lib_modules 的元素必须是非空字符串"):
        load_wordlist(path)
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": '
        '[{"name": "A", "lib_modules": [""]}]}]',
    )
    with pytest.raises(WordlistError, match="lib_modules 的元素必须是非空字符串"):
        load_wordlist(path)


def test_load_wordlist_lib_modules_unknown_slug_rejected(tmp_path):
    """显式 lib_slugs 校验：引用未知 slug → WordlistError（文案含组/条目索引与 slug）。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "models": [], "solutions": ['
        '{"name": "A", "lib_modules": ["xunji", "ghost"]}]}]',
    )
    with pytest.raises(WordlistError, match=r"ghost"):
        load_wordlist(path, lib_slugs=frozenset({"xunji", "pid"}))


def test_load_wordlist_lib_modules_known_slugs_ok(tmp_path):
    """显式 lib_slugs 校验：全部已知 → 通过。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "models": [], "solutions": '
        '[{"name": "A", "lib_modules": ["xunji", "pid"]}]}]',
    )
    groups = load_wordlist(path, lib_slugs=frozenset({"xunji", "pid"}))
    assert groups[0].solutions[0].lib_modules == ("xunji", "pid")


def test_default_wordlist_lib_modules_references_exist():
    """真实词表回归（工单 wordlist-lib-modules/01）：DEFAULT_WORDLIST 的全部
    lib_modules 引用必须命中源码树模块库（仓库根 library/modules）——手补词表
    引入失效引用 → 加载/测试立即红。"""
    from contest_generator.wordlist import DEFAULT_WORDLIST, source_module_slugs

    slugs = source_module_slugs()
    assert slugs, "仓库源码树应存在 library/modules（词表校验前提）"
    referenced = {
        slug
        for group in DEFAULT_WORDLIST
        for solution in group.solutions
        for slug in solution.lib_modules
    }
    assert referenced, "词表应有方案声明 lib_modules（本特性迁移后）"
    assert referenced <= slugs, f"词表引用了库中不存在的模块 slug：{referenced - slugs}"


def test_default_wordlist_wireless_group_has_zigbee_lib():
    """真词表回归（工单 zigbee-link/03）：「无线通信模块」组含 Zigbee 方案且
    挂库内 zigbee_link（买件指引显示「库内已有」）；组内 recommended ≤2。"""
    from contest_generator.wordlist import DEFAULT_WORDLIST

    wireless = next(
        (g for g in DEFAULT_WORDLIST if g.category == "无线通信模块"), None
    )
    assert wireless is not None, "默认词表应含「无线通信模块」组"
    zigbee = next(
        (s for s in wireless.solutions if s.name == "Zigbee 模块（DL-20 串口透传）"),
        None,
    )
    assert zigbee is not None, "无线通信模块组应含 Zigbee（DL-20 串口透传）方案"
    assert zigbee.interface == "UART 串口透传（115200 点对点）"
    assert zigbee.price == "￥10-20/个"
    assert "zigbee_link" in zigbee.note
    assert "115200" in zigbee.note
    assert "不要" not in zigbee.note  # note 应说明不需要，而非歧义措辞
    assert zigbee.suitable == "双机/双车无线数据通信、遥控指令、遥测上报"
    assert zigbee.lib_modules == ("zigbee_link",)
    assert zigbee.recommended is False
    assert sum(1 for s in wireless.solutions if s.recommended) <= 2


def test_default_wordlist_sensor_group_has_ir_beam_lib():
    """真词表回归（工单 ir-beam-module/02）：「感知传感器」组含红外对射方案且
    挂库内 ir_beam（买件指引显示「库内已有」，ticket 02 钉防回退）。"""
    from contest_generator.wordlist import DEFAULT_WORDLIST

    sensor = next(
        (g for g in DEFAULT_WORDLIST if g.category == "感知传感器"), None
    )
    assert sensor is not None, "默认词表应含「感知传感器」组"
    ir = next(
        (s for s in sensor.solutions if s.name == "红外对射传感器（遮挡检测）"),
        None,
    )
    assert ir is not None, "感知传感器组应含红外对射（遮挡检测）方案"
    assert ir.interface == "GPIO 数字量（三线制 VCC/GND/OUT）"
    assert ir.price == "￥3-10/套"
    assert "ir_beam" in ir.note
    assert "IR_BEAM_BLOCKED_LEVEL" in ir.note  # 极性翻转提示
    assert ir.suitable == "门洞/出入口遮挡检测、物体经过计数、防夹、载物在位"
    assert ir.lib_modules == ("ir_beam",)
    assert ir.recommended is False


# 器件 vs 内部件（工单 library-hookup-and-invariants/01；判据归位 identity-fields/01）：
# 用户会为它单独采购的器件必须挂接（买件指引标「库内已有」+ 预筛 lib_boost 加分）；
# 库内以头文件/工具形态存在的内部件不挂（挂了只会让买件清单变噪）。
# **名单不再手写**：判据单源 = library.MODULE_KIND（未登记 = 器件），本文件从它派生，
# 新增内部件只改那一处。
def _device_slugs() -> tuple[str, ...]:
    """非内部件/协议切片的库内模块（= 器件，需挂接）。"""
    from contest_generator.library import device_slugs
    from contest_generator.wordlist import source_module_slugs

    slugs = source_module_slugs() or frozenset()
    return device_slugs(sorted(slugs))


def _internal_slugs() -> tuple[str, ...]:
    """内部件 + 协议切片（= 不许挂接）。"""
    from contest_generator.library import MODULE_KIND, ModuleKind

    return tuple(
        slug
        for slug, value in MODULE_KIND.items()
        if value in (ModuleKind.INTERNAL, ModuleKind.PROTOCOL)
    )

def _hooked_slugs() -> set[str]:
    from contest_generator.wordlist import DEFAULT_WORDLIST

    return {
        slug
        for group in DEFAULT_WORDLIST
        for solution in group.solutions
        for slug in solution.lib_modules
    }


def test_default_wordlist_device_modules_are_hooked():
    """器件类模块必须被某个选购方案挂接（买件指引能标「库内已有」）。

    回归口径（工单 library-hookup-and-invariants/01）：8 个 slug 此前一条方案都没有
    ——用户买舵机/步进电机/OLED/MPU6050/声光件/按键时，指引不说库里已有现成驱动，
    AI 推荐也少一条词表挂接加分路径。

    名单取源（工单 identity-fields/01）：从库内单源 `library.MODULE_KIND` 派生
    （未登记 = 器件），不再手写——新增器件自动进本守卫。"""
    hooked = _hooked_slugs()
    missing = [slug for slug in _device_slugs() if slug not in hooked]
    assert not missing, f"器件类模块未被任何选购方案挂接：{'、'.join(missing)}"


def test_default_wordlist_internal_modules_are_not_hooked():
    """内部件/协议切片不被挂接（判据的反向守卫）：它们不是用户单独采购的器件。

    adc/delay/filter/uart/config/各 uart 是库内以头文件或工具形态存在的件；
    huidu/ntb_time 同理（灰度读取与时间戳）；coord_detect/zigbee_uart(_key) 是与
    上位器件绑定的帧解析切片（实物归 k230 / zigbee_link）。若哪天被顺手挂上，
    买件清单会混入不需要采购的条目。

    名单取源同前：库内单源 `library.MODULE_KIND` 的 INTERNAL / PROTOCOL 两类。"""
    hooked = _hooked_slugs()
    offenders = [slug for slug in _internal_slugs() if slug in hooked]
    assert not offenders, f"内部件/协议切片被误挂接：{'、'.join(offenders)}"


# 「方案名 → 合法 name」口径守卫（工单 real-acceptance/08）：
# 提示词 format_wordlist_prompt 把方案名摆在模型眼前，闸的合法 name 域却是
# 类别名 ∪ models（selection._solution_group 单源）——模型照抄方案名即被拒。
# 用户拍板 B1：solutions 保持导览语义、models 是唯一合法 name 域、**补数据零代码**。
# 判据（工单「修复方向 2 裁定规则」）：裸名是电赛真会买的硬件（能写进采购单的名词
# 短语）→ 入 models；平台/主控本身、上位概念、句子或组合描述、与既有条目重复 → 不入。
ONSITE_REJECTED_NAMES = (
    "红外对管循迹数组",
    "红外测距传感器",
    "直流减速电机 + TB6612 双路驱动板",
    "串口摄像头（JPEG 输出 UART 转接）",
)
MUST_STAY_REJECTED_NAMES = ("TI MSPM0 主控板",)

# 顺延批 27 条（工单 real-acceptance/10）：单 08 因预算不足顺延的「规则可入的
# 方案裸名」，单 05 把全文段 25600→23400 后余量已够（权威口径实测 +1375B、
# 收下后 mspm0 余量 2173B ≥ REQUEST_RESERVE_BYTES），本批全收。
# 落点由机械反查得出（.scratch/recommend-domain-reject/
# probe-21-deferred-placement.py，判据 = name 命中某行 solutions[].name 或其
# 去括号裸名）——跨 7 行，不是单 08 那批的「感知传感器 + 执行机构」两行。
DEFERRED_BATCH_NAMES = (
    # 感知传感器（16）
    "SHT30 温湿度传感器",
    "红外对射传感器",
    "磁力计指南针",
    "BMP180 气压/海拔传感器",
    "MS5611 高精度气压传感器",
    "GP2Y1014AU 粉尘传感器",
    "S12SD 紫外线传感器",
    "BH1750 光照度传感器",
    "TTP224 4 路电容触摸按键",
    "TCS34725 颜色识别传感器",
    "MLX90614 非接触红外测温",
    "MQ-2 烟雾/可燃气体传感器",
    "MQ-135 空气质量传感器",
    "DS18B20 单总线温度传感器",
    "SHT20 温湿度传感器",
    "JY61P 六轴姿态传感器",
    # 执行机构（3）
    "L298N 大电流驱动板",
    "1 路 5V 继电器模块",
    "PCA9685 16 路舵机板",
    # 语音模块（2）
    "JQ8900 语音播报模块",
    "SYN6288 语音合成模块",
    # 显示模块（2）
    "0.96 寸 OLED 单色屏",
    "MAX7219 数码管/点阵",
    # 遥控接收（2）
    "双轴摇杆按键",
    "红外遥控接收头 VS1838B",
    # 声光提示器件（1）
    "有源蜂鸣器模块",
    # 无线通信模块（1）
    "RC522 射频 IC 卡读卡器",
)


def _suggestion_verdict(name: str) -> str:
    """现算一条库外建议名的判决（真跑 build_module_selection，不模拟判据）。

    返回 "合法" 或 "拒收"——与工单红证脚本 measure-18-wordlist-coverage.py
    同一调用形态（同一闸、同一默认词表）。
    """
    from contest_generator.llm import DEFAULT_WORDLIST
    from contest_generator.selection import SelectionError, build_module_selection

    raw = {
        "requirements": [
            {
                "requirement": "循迹",
                "sentence": 1,
                "modules": [],
                "suggestions": [{"name": name}],
            }
        ]
    }
    try:
        build_module_selection(raw, known_slugs=(), hardware_words=DEFAULT_WORDLIST)
    except SelectionError:
        return "拒收"
    return "合法"


def test_default_wordlist_onsite_rejected_names_are_legal_now():
    """现场被拒名不得再被拒（工单 real-acceptance/08 结构守卫，防空转）。

    2022C 历史上**连续三轮**挂在这一类名字上（模型逐字照抄提示词「选购方案」段里的
    方案名，于是被词表闸拒收）——本条把这些名字钉成回归锚：**B1 数据一旦被回滚/
    被改坏，本用例立即红**（不用等真机复跑）。

    口径：合法域 = 类别名 ∪ 该行 models；四条现场名（`串口摄像头` 那条是**全名**，
    见工单 08「裁定结果」的偏差说明）现算必须走「命中」而不是「降级」。
    """
    verdicts = {name: _suggestion_verdict(name) for name in ONSITE_REJECTED_NAMES}
    rejected = [name for name, verdict in verdicts.items() if verdict != "合法"]
    assert not rejected, f"现场被拒名又被拒收了（B1 数据回滚？）：{'、'.join(rejected)}"


def test_default_wordlist_deferred_batch_names_are_legal_now():
    """顺延批 27 条不得再被拒收（工单 real-acceptance/10 结构守卫，防空转）。

    单 08 把这 27 条**规则可入**的方案裸名按预算顺延（当时全文段 25600、边界余量
    只剩 731B）；单 05 把全文段降到 23400 后余量已够（权威口径实测补数据 +1375B，
    mspm0 最坏形态 126851B、余量 2173B ≥ `REQUEST_RESERVE_BYTES`），本批全收。

    本条与 `test_default_wordlist_onsite_rejected_names_are_legal_now` 同型同口径
    （`DEFAULT_WORDLIST` + `build_module_selection` 直测，真跑闸不模拟判据）：
    **数据一旦被回滚/被改坏立即红**，不用等真机复跑。名字按落点行分组（跨 7 行，
    机械反查得出——见 DEFERRED_BATCH_NAMES 上方注释），名单本身即「提示词给模型
    看过的方案裸名」的回归锚。
    """
    verdicts = {name: _suggestion_verdict(name) for name in DEFERRED_BATCH_NAMES}
    rejected = [name for name, verdict in verdicts.items() if verdict != "合法"]
    assert not rejected, (
        f"顺延批裸名又被拒收了（工单 10 数据回滚 / 落点行写错？）：{'、'.join(rejected)}"
    )


def test_default_wordlist_deferred_batch_landed_in_home_rows():
    """顺延批落点守卫：裸名必须落在**反查得出的那一行**，不能落在别的行。

    判据（工单 10「27 条的落点」）：name 命中某行 `solutions[].name` 或它的
    **去括号裸名** → 落该行 category。落错行不会让上面那条用例红（闸只要任何
    一行认它就放行），所以单独守一层：`_solution_group` 命中的行必须就是
    「该名字作为方案名/裸名出现的那一行」。
    """
    import re

    from contest_generator.llm import DEFAULT_WORDLIST
    from contest_generator.selection import _solution_group

    def bare(name: str) -> str:
        return re.sub(r"（[^）]*）", "", name).strip()

    # 反查：顺延名 → 它作为方案全名/裸名出现的类别行（必须恰好一行）
    homes: dict[str, set[str]] = {name: set() for name in DEFERRED_BATCH_NAMES}
    for group in DEFAULT_WORDLIST:
        for option in group.solutions:
            for candidate in (option.name, bare(option.name)):
                if candidate in homes:
                    homes[candidate].add(group.category)
    unmatched = [name for name, cats in homes.items() if not cats]
    assert not unmatched, f"顺延名在词表里找不到落点行：{'、'.join(unmatched)}"
    ambiguous = [name for name, cats in homes.items() if len(cats) > 1]
    assert not ambiguous, (
        "顺延名落点歧义（命中多行）："
        + "；".join(f"{n} → {'/'.join(sorted(homes[n]))}" for n in ambiguous)
    )

    wrong = []
    for name in DEFERRED_BATCH_NAMES:
        matched = _solution_group(name, DEFAULT_WORDLIST)
        assert matched is not None, f"{name} 未命中任何词表行"
        home = next(iter(homes[name]))
        if matched.category != home:
            wrong.append(f"{name}：落 {matched.category}（应为 {home}）")
    assert not wrong, "顺延名落错行：" + "；".join(wrong)


def test_default_wordlist_platform_name_stays_rejected():
    """对照：平台名仍拒收（工单 real-acceptance/08——闸不得被放宽成万金油）。

    `TI MSPM0 主控板` 是平台本身（裁定规则①），词表无对应类别行 → **拒收正确**。
    本条与上一条成对：只有「该放的放、该拦的还拦」才算口径对齐，而不是把闸拆了。
    """
    for name in MUST_STAY_REJECTED_NAMES:
        assert _suggestion_verdict(name) == "拒收", (
            f"{name} 应当仍被拒收（平台/主控本身，不是可采购的在库外建议）"
        )

