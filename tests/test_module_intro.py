"""模块简介拆段（工单 module-intro-detail/01）：四问分类 / 零丢字 / API 投影。

推荐区「这是什么」入口读的就是这份拆段：简介（`manifest.description`）单源不改写，
后端按标点与词法机械拆成「这是干什么的 / 怎么接线 / 怎么用（接口） / 什么时候用」，
前端只渲染不判规则。本文件钉三件事——分类判据、零丢信息、`/api/modules` 载荷带
`intro`（含真实库与真实 ir_beam 简介，防回退）。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contest_generator.manifest import ModuleManifest
from contest_generator.module_intro import (
    LABEL_OTHER,
    LABEL_OVERVIEW,
    LABEL_SCENARIO,
    LABEL_USAGE,
    LABEL_WIRING,
    intro_sections,
    split_sentences,
)
from contest_generator.webapp import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES = REPO_ROOT / "library" / "modules"

# 样板简介：四拍齐全（物理是什么 / 怎么接 / 怎么用 / 什么时候用）——
# 与 library/modules/ir_beam/manifest.json 逐字同形，改简介时同步这里即红。
IR_BEAM_DESC = (
    "红外对射传感器：一对红外发射管和接收管相对安装，中间的光束被物体挡住时"
    "接收管收不到光，模块据此判断“有没有东西挡在中间”——最常用的"
    "“物体经过/到位”检测件。"
    "三线制接线（VCC 电源 / GND 地 / OUT 信号），只占 1 个 GPIO——OUT 默认 PA8，"
    "两个平台同脚。"
    "驱动接口：ir_beam_init() 初始化、ir_beam_read() 读一次状态，"
    "返回 1 = 光束被遮挡（有物体）、0 = 无遮挡。"
    "默认按上拉输入判断（遮挡 = 高电平），实物极性相反时改 IR_BEAM_BLOCKED_LEVEL"
    " 一个宏即可。"
    "适用于物体经过检测、出入口遮挡检测、防夹、载物在位等赛题功能。"
)

# 简介四拍书写规范的 pilot 批次（工单 module-intro-detail/02）：推荐链路高频 /
# 易误解的模块。新写法守卫只钉这批——存量简介分批重写（spec「范围外」）。
PILOT_MODULES = (
    "ir_beam", "sr04", "servo", "step_motor", "led", "beep", "pid", "xunji", "ws2812",
)


def _text_of(section) -> str:
    """段落文本：拆段结果（IntroSection）与 API 载荷（dict）通用。"""
    return section["text"] if isinstance(section, dict) else section.text


def _normalize(text: str) -> str:
    """单句归一化：去空白 + 去全部切句标点（**文字内容一字不动**）。"""
    return re.sub(r"[。；！？;\s]+", "", text)


def _sentence_bag(text: str) -> Counter:
    """文本 → 句子多重集（与实现同一套切句规则，避免测试自己归一化造成假绿）。"""
    return Counter(_normalize(s) for s in split_sentences(text) if _normalize(s))


def _assert_no_content_lost(description: str, sections) -> None:
    """拆段不丢句：原简介句子多重集 = 各段句子多重集（不丢、不重、不造内容）。

    段间重排是设计内行为（四问固定顺序 vs 原简介书写顺序），拼接字符串会跟着变，
    所以口径是句子多重集——它同时抓住丢句、重复句、以及凭空添内容。
    """
    rendered = "。".join(_text_of(s) for s in sections)
    assert _sentence_bag(rendered) == _sentence_bag(description)


def test_four_sections_in_fixed_order():
    """四拍各自归位，顺序固定（其它说明垫底）。"""
    sections = intro_sections(IR_BEAM_DESC)
    assert [s.label for s in sections] == [
        LABEL_OVERVIEW, LABEL_WIRING, LABEL_USAGE, LABEL_SCENARIO,
    ]
    by_label = {s.label: s.text for s in sections}
    # ① 这是干什么的：物理本质（对射 + 挡住收不到光）
    assert "红外发射管" in by_label[LABEL_OVERVIEW]
    assert "有没有东西挡在中间" in by_label[LABEL_OVERVIEW]
    # ② 怎么接线：线制 / 三根线各是什么 / 占几个脚 / 默认脚
    assert "三线制" in by_label[LABEL_WIRING]
    assert "PA8" in by_label[LABEL_WIRING]
    # ③ 怎么用：函数名 + 返回值语义 + 极性宏
    assert "ir_beam_init()" in by_label[LABEL_USAGE]
    assert "ir_beam_read()" in by_label[LABEL_USAGE]
    assert "IR_BEAM_BLOCKED_LEVEL" in by_label[LABEL_USAGE]
    # ④ 什么时候用：适用赛题功能
    assert "适用于" in by_label[LABEL_SCENARIO]


def test_sections_lose_no_text():
    """拆段只切不改写：句子多重集相等（不丢句、不重复、不造内容）+ 段内可读。"""
    sections = intro_sections(IR_BEAM_DESC)
    _assert_no_content_lost(IR_BEAM_DESC, sections)
    # 段内句子用句号连接（不是把原标点原样堆上去：`…检测；。适用于…` 这种）
    assert "；。" not in "".join(s.text for s in sections)


def test_same_label_merges_in_original_order():
    """同类句子合并成一段（同标题只出一段），段内保持原顺序。"""
    sections = intro_sections(
        "温度传感器模块。适用于冷链测温。也适用于粮仓测温。"
    )
    labels = [s.label for s in sections]
    assert labels.count(LABEL_SCENARIO) == 1
    scenario = next(s for s in sections if s.label == LABEL_SCENARIO)
    assert scenario.text.index("冷链") < scenario.text.index("粮仓")


def test_interface_sentence_beats_wiring_keywords():
    """一句话同时像「接线」和「接口」→ 归接口（优先级：接口 > 接线 > 场景）。

    `IR_BEAM_GPIO` 这类引脚宏名不带括号，不误判成函数调用。首句恒归「这是干什么的」
    （定义槽），故判据句放第二句。
    """
    sections = intro_sections("对射传感器驱动。引脚宏 IR_BEAM_GPIO 是 OUT 脚，读状态请调 ir_beam_read()。")
    assert [s.label for s in sections] == [LABEL_OVERVIEW, LABEL_USAGE]
    macro_only = intro_sections("对射传感器驱动。引脚宏 IR_BEAM_GPIO 对应 OUT 脚，占用一个 GPIO。")
    assert [s.label for s in macro_only] == [LABEL_OVERVIEW, LABEL_WIRING]


def test_unclassifiable_sentence_goes_to_tail_not_dropped():
    """分不类的句子（非首句）落「其它说明」——不丢信息。

    首句是唯一的例外：它默认就是「这是干什么的」（简介第一句照约定讲这东西是什么）。
    """
    sections = intro_sections("某种模块。注意事项另见库内说明。")
    assert [s.label for s in sections] == [LABEL_OVERVIEW, LABEL_OTHER]
    assert "注意事项另见库内说明" in sections[-1].text


def test_single_sentence_and_no_punctuation():
    """单句无标点 / 只有一个词 → 一段，不炸也不切碎。"""
    only = intro_sections("红外对射传感器")
    assert [s.label for s in only] == [LABEL_OVERVIEW]
    assert only[0].text == "红外对射传感器"
    one_sentence = intro_sections("红外对射传感器：一对发射管和接收管相对安装。")
    assert [s.label for s in one_sentence] == [LABEL_OVERVIEW]


def test_empty_description_yields_no_sections():
    """空简介 / 全空白 / None → 空元组（调用方回落原样简介）。"""
    assert intro_sections("") == ()
    assert intro_sections("   \n\t ") == ()
    assert intro_sections(None) == ()


def test_identifier_with_dot_is_not_split():
    """英文句点不切句：`HX711_GAP_VALUE`、`1.0`、`pin_config.h` 不被切坏。"""
    description = "称重模块。校准除数见 HX711_GAP_VALUE（默认 1.0），引脚在 pin_config.h。"
    sections = intro_sections(description)
    _assert_no_content_lost(description, sections)
    assert any("1.0" in s.text for s in sections)
    assert any("pin_config.h" in s.text for s in sections)


def test_first_sentence_is_always_the_definition_slot():
    """首句恒归「这是干什么的」——哪怕它含函数名（存量简介把定义与接口压在一句）。

    relay 真实简介：`…GPIO 输出（1 脚…），relay_init 初始断开 + relay_set(…)；适用于…`
    ——若让词法覆盖首句，弹窗第一段标题会变成「怎么用（接口）」，用户最想看的
    「这是什么」被埋掉（全库 93 个模块里 57 个会这样）。
    """
    sections = intro_sections(
        "1 路 5V 继电器模块驱动：GPIO 输出，relay_init 初始断开 + relay_set(1=吸合)；"
        "适用于继电器通断控制、火警联动断电等赛题功能。"
    )
    assert sections[0].label == LABEL_OVERVIEW
    assert "继电器模块驱动" in sections[0].text
    assert [s.label for s in sections] == [LABEL_OVERVIEW, LABEL_SCENARIO]


def test_weak_scenario_words_do_not_hijack_sections():
    """弱词（检测/识别/显示/测量）不当段判据——它们描述「怎么干活」，不是适用场景。

    否则几乎每句都被塞进「什么时候用」（实测 93 个模块里 80 个），分段等于没分。
    """
    labels = [
        s.label for s in intro_sections("传感器模块。软 I2C 位操作读取，做黑线检测与坐标识别。")
    ]
    assert labels == [LABEL_OVERVIEW, LABEL_OTHER]
    strong = [s.label for s in intro_sections("传感器模块。适用于黑线检测与坐标识别。")]
    assert strong == [LABEL_OVERVIEW, LABEL_SCENARIO]


@pytest.mark.parametrize("slug", PILOT_MODULES)
def test_pilot_modules_carry_all_four_beats(slug):
    """pilot 批次简介四拍齐全（工单 module-intro-detail/02 的写法守卫，防回退）。

    「推荐区模块名旁边点开就能看懂」的前提是简介按四拍写：讲清这东西是什么、
    怎么接、怎么用、什么时候用。少了任何一拍，弹窗就缺一块用户真正要看的信息
    ——这正是本工单要治的痛点，所以钉死。
    """
    manifest = ModuleManifest.load(MODULES / slug)
    labels = [s.label for s in intro_sections(manifest.description)]
    for label in (LABEL_OVERVIEW, LABEL_WIRING, LABEL_USAGE, LABEL_SCENARIO):
        assert label in labels, f"{slug} 简介缺「{label}」拍：{manifest.description}"


@pytest.mark.parametrize("slug", PILOT_MODULES)
def test_pilot_description_starts_with_plain_language(slug):
    """pilot 简介首句讲「是什么」，不能是函数名/协议/ADR 编号开头的内部口径。

    反例（改前）：ir_beam 首句「红外对射传感器读取（双平台）：ir_beam_init /
    ir_beam_read 按光束遮挡返回 0/1」——不懂的人读完仍不知道它是个什么东西。
    """
    manifest = ModuleManifest.load(MODULES / slug)
    first = intro_sections(manifest.description)[0].text
    for jargon in ("ADR ", "纯驱动", "驱动切片", "位操作", "环形缓冲"):
        assert jargon not in first, f"{slug} 首句是内部口径（{jargon}）：{first}"


def test_ir_beam_fixture_matches_real_manifest():
    """测试样板与真实 manifest 逐字同形（样板漂移 = 上面几条断言变成假绿）。"""
    manifest = ModuleManifest.load(MODULES / "ir_beam")
    assert IR_BEAM_DESC == manifest.description


def test_paragraph_breaks_are_preserved_as_sentences():
    """空行分段同样切（简介常按空行分节），段内容不丢。"""
    description = "模块甲。\n\n第二段讲接线：三线制，占用一个 GPIO。"
    sections = intro_sections(description)
    _assert_no_content_lost(description, sections)
    assert [s.label for s in sections] == [LABEL_OVERVIEW, LABEL_WIRING]


@pytest.mark.parametrize(
    "slug", sorted(p.name for p in MODULES.iterdir() if (p / "manifest.json").is_file())
)
def test_every_real_module_loses_no_content(slug):
    """全库真实简介逐条零丢内容（存量紧凑简介没按四拍写也能拆——只是分段可能粗些）。"""
    manifest = ModuleManifest.load(MODULES / slug)
    _assert_no_content_lost(manifest.description, intro_sections(manifest.description))


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    """带**注入配置**的 app（不能裸 `create_app()`）。

    2026-09-16 CI 抓到的环境耦合：裸 `create_app()` 会去读 `~/.contest_generator/config.json`，
    本机有配置（所以全绿），CI / 新 clone 上没有 → `/api/modules` 直接 **400「未配置 AI API」**，
    看起来像产品坏了，其实是用例把「本机装过工具」当成了夹具。
    这里改成注入最小配置（真库目录 + 临时配置路径 + 假 key），与 `test_webapp.py` 同一姿势。
    """
    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext

    work = tmp_path_factory.mktemp("module_intro_ctx")
    ctx = AppContext(
        config_path=work / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=MODULES,
            masters_dir=REPO_ROOT / "library" / "masters",
            autocommit_enabled=False,  # 只读浏览，不写库不提交
        ),
    )
    return TestClient(create_app(ctx))


def test_api_modules_projects_intro(client):
    """/api/modules 每条带 intro（判据单源投影），段落形状 = {label, text}。"""
    response = client.get("/api/modules")
    assert response.status_code == 200
    modules = response.json()
    assert modules
    for module in modules:
        assert "intro" in module, module["slug"]
        assert isinstance(module["intro"], list)
        for section in module["intro"]:
            assert set(section) == {"label", "text"}
            assert section["label"] and section["text"]
        # 零丢内容：拆段覆盖原简介每个非空白字符（段间重排是设计内行为）
        _assert_no_content_lost(module["description"], module["intro"])


def test_api_modules_intro_labels_come_from_single_source(client):
    """标签值来自后端单源（前端只渲染）：载荷里出现的标题都在四问 + 兜底之内。"""
    modules = {m["slug"]: m for m in client.get("/api/modules").json()}
    labels = {s["label"] for m in modules.values() for s in m["intro"]}
    assert labels
    assert labels <= {
        LABEL_OVERVIEW, LABEL_WIRING, LABEL_USAGE, LABEL_SCENARIO, LABEL_OTHER,
    }
