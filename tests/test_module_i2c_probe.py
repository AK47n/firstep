"""i2c_probe 通用 I2C 总线原语模块（库内新增内部件，双平台）：真实库 + 真实
母版不变量与双平台单选生成。

工单 `.scratch/hwcheck-unknown-device/issues/01-i2c-probe-module.md`。本件的
身份与库内六件软 I2C **不同**：它不是器件，是「借一对脚 + 一条总线给我们用」
的**总线原语**——没有器件语义、没有购买身份字段（`library.MODULE_KIND` 登记为
内部件）、参考关联显式豁免。它存在的理由只有一个：mspm0 上 `main.c` 只准调
「所选模块头里真实存在的函数」，探测代码只能经由库内模块进工程。

三条不变量是本文件的重点（也是后面「陌生器件探测」三张工单的地基）：

1. **接口只有读侧三件事**（`init` / `ping` / `read_reg`）——渲染器的结构守卫
   判据就是「渲染出的调用集 ⊆ 本模块接口列表」，多一个写函数就等于给"猜出来
   的读法"开了后门（spec 范围外：写寄存器 / 读数据）。
2. **mspm0 的 `I2C_0` 实例靠消费者登记存活**——裁剪判据是「消费者 ∩ 选中集」，
   不登记 `i2c_probe` 为消费者，`I2C_0` 连同 PA0/PA1 的 `$assign` 一起被裁掉、
   `I2C_0_INST` 不存在（工单验收项 4 与反证项 9）。
3. **stm32 走自己一组宏的位操作软 I2C**（PA6/PA7，与库内软 I2C 共挂同一条
   总线），**不用**母版 `ml_i2c`（其 I2C_GPIO 硬绑 PA11/PA12 = 蓝药丸 USB
   DM/DP）。

全程无 LLM、无服务。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.library import (  # noqa: E402
    MODULE_KIND,
    MODULE_KIND_REASONS,
    ModuleKind,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.readme import parse_pin_table  # noqa: E402
from contest_generator.reference_library import MODULE_REFERENCE_EXEMPT  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS  # noqa: E402
from contest_generator.syscfg_prune import prune_syscfg  # noqa: E402
from contest_generator.wiring import wiring_rows  # noqa: E402

# 本模块的全部公开接口（**读侧三件事**，判据单源 = 两张头文件）——渲染器的
# 结构守卫（工单 03/04）直接吃这份清单，改接口必须同步这里。
PUBLIC_API = ("i2c_probe_init", "i2c_probe_ping", "i2c_probe_read_reg")

# 生成 main.c：只调本模块 API（证明头文件与实现真能编成工程，照
# test_module_qmc5883l.py 先例）。
MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "i2c_probe.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    uint8_t value = 0u;\n"
    "    i2c_probe_init();\n"
    "    uint8_t got = i2c_probe_ping(0x68u);\n"
    "    got = i2c_probe_read_reg(0x68u, 0x75u, &value);\n"
    "    (void)got;\n"
    "    (void)value;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "i2c_probe_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    uint8_t value = 0u;\n"
    "    i2c_probe_init();\n"
    "    (void)i2c_probe_ping(0x68u);\n"
    "    (void)i2c_probe_read_reg(0x68u, 0x75u, &value);\n"
    "    (void)value;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 剥离注释后不得出现（标准库 / 寄存器直写 / 母版 ml_i2c 调用 / 演示残留）——
# 照 test_module_qmc5883l.py 原表（软 I2C 总线件的共用手册）。
BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bI2C_Init\b|\bI2C_Start\b|\bI2C_Stop\b|\bI2C_SendByte\b", "母版 ml_i2c 调用"),
    (r"\bGPIO_ReadInputDataBit\b", "GPIO_ReadInputDataBit"),
    (r"\bGPIO_WriteBit\b", "GPIO_WriteBit"),
]


def _declared_functions(header_text: str) -> set[str]:
    """头文件里**声明**的公开函数名（注释剥离后按 `i2c_probe_*(` 取）。"""
    return set(re.findall(r"\b(i2c_probe_\w+)\s*\(", strip_comments(header_text)))


def _generated_wiring(platform: str, slug: str) -> dict[str, str]:
    """单选生成的接线行（工单验收项 5 的「页面与工程同源」判据面）。"""
    resolved = resolve_selection(MODULES, platform, [slug])
    return {
        row["role_id"]: row["pin"]
        for row in wiring_rows(platform, resolved.manifests)
        if row["slug"] == slug
    }


# ---------------------------------------------------------------------------
# 接口契约：读侧三件事（渲染器结构守卫的判据源）
# ---------------------------------------------------------------------------


def test_both_headers_declare_only_the_three_read_side_calls():
    """两张头文件的公开接口 = init / ping / read_reg 三项，**没有第四项**。

    「只读」是一条硬约束（spec：不写寄存器、不读数据——猜出来的读法比不测
    更坏）。渲染器的结构守卫吃的就是这份接口清单，所以头里多一个
    `i2c_probe_write_*` 就等于给幻觉调用开了后门。同时钉住「没有第二类语义」：
    不许出现 `whoami` / `id` / `device` 这类器件语义名字。
    """
    for rel in ("code/i2c_probe.h", "code/i2c_probe_stm32.h"):
        header = (MODULES / "i2c_probe" / rel).read_text(encoding="utf-8")
        declared = _declared_functions(header)
        assert declared == set(PUBLIC_API), f"{rel} 公开接口漂移：{sorted(declared)}"
    mspm0 = (MODULES / "i2c_probe" / "code/i2c_probe.h").read_text(encoding="utf-8")
    stm32 = (MODULES / "i2c_probe" / "code/i2c_probe_stm32.h").read_text(
        encoding="utf-8"
    )
    for text in (mspm0, stm32):
        code_only = strip_comments(text)
        for banned in ("_write", "_set_reg", "whoami", "chip_id", "device"):
            assert banned not in code_only.lower(), f"接口出现第二类语义：{banned}"


def test_read_reg_reports_failure_separately_from_the_value():
    """`read_reg` 的失败**不与读到的 0x00 混淆**：返回码 + 出参两分。

    判据 = 头文件把值放在出参上、函数返回 `uint8_t` 状态码（0 = 成功）——
    把两件事塞进一个返回值（如「返回读到的字节，失败返回 0xFF」）就是本工单
    明文要挡的那种混淆；ping 同样返回状态码而不是布尔读值。
    """
    for rel in ("code/i2c_probe.h", "code/i2c_probe_stm32.h"):
        header = strip_comments(
            (MODULES / "i2c_probe" / rel).read_text(encoding="utf-8")
        )
        assert re.search(
            r"uint8_t\s+i2c_probe_read_reg\(uint8_t\s+\w+,\s*uint8_t\s+\w+,\s*"
            r"uint8_t\s*\*\s*\w+\s*\)",
            header,
        ), f"{rel} 的 read_reg 签名不是「状态码 + 出参」"
        assert re.search(r"uint8_t\s+i2c_probe_ping\(uint8_t\s+\w+\s*\)", header)


# ---------------------------------------------------------------------------
# 库内身份：内部件（无购买身份字段）+ 参考关联显式豁免
# ---------------------------------------------------------------------------


def test_i2c_probe_is_an_internal_module_with_a_reason():
    """`MODULE_KIND` 登记为内部件且写明理由（未登记 = 器件，会要求购买链接）。

    判据单源在 `library.MODULE_KIND`：把它漏登记，身份字段守卫会要求 `kit` 与
    `source_url`（一件不是用户会采购的实物，填链接等于伪造数据）。
    """
    assert MODULE_KIND["i2c_probe"] is ModuleKind.INTERNAL
    assert MODULE_KIND_REASONS["i2c_probe"].startswith("内部件")
    assert "总线原语" in MODULE_KIND_REASONS["i2c_probe"]


def test_i2c_probe_entry_has_no_identity_fields():
    """内部件的两平台条目 `kit` / `source_url` 必须为空（判据的反向）。"""
    manifest = ModuleManifest.load(MODULES / "i2c_probe")
    for platform, entry in manifest.platforms.items():
        assert entry.kit == "", f"{platform} 内部件不该有 kit"
        assert entry.source_url == "", f"{platform} 内部件不该有 source_url"


def test_i2c_probe_reference_exemption_reason_matches_kind():
    """参考关联显式豁免，且理由以「内部件」开头（与判据单源一致的表述）。

    参考关联域的判据是「参考库有没有可关联条目」——库内没有「I2C 总线原语」这种
    条目，所以必须登记豁免；理由措辞的类别前缀由
    `tests/test_skeleton_mapping_coverage.py` 断言，这里钉住登记本身存在。
    """
    assert "i2c_probe" in MODULE_REFERENCE_EXEMPT
    assert MODULE_REFERENCE_EXEMPT["i2c_probe"].startswith("内部件")


# ---------------------------------------------------------------------------
# manifest 形状：两平台文件齐、引脚如实声明、notes 交代平台代价
# ---------------------------------------------------------------------------


def test_i2c_probe_manifest_shape_both_platforms():
    """两平台文件齐；stm32 = i2c_scl/i2c_sda（PA6/PA7 + 逐脚端口宏）；
    mspm0 = I2C_0 实例的 sclPin/sdaPin（PA1/PA0，**不带宏**——走 SysConfig）；
    `verified=true`（编译矩阵翻牌）、`hardware_bound=false`、notes 交代
    「未上板」与 mspm0 的两个平台代价（板载 LED 共用 / PA0 上拉位未焊）。"""
    manifest = ModuleManifest.load(MODULES / "i2c_probe")
    assert manifest.slug == "i2c_probe"
    assert manifest.dependencies == ()

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "i2c_probe_stm32.c",
        "i2c_probe_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "i2c_probe" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("I2C_PROBE_SCL", "i2c_scl", "PA6", True,
         ("I2C_PROBE_SCL_GPIO", "I2C_PROBE_SCL_PIN")),
        ("I2C_PROBE_SDA", "i2c_sda", "PA7", True,
         ("I2C_PROBE_SDA_GPIO", "I2C_PROBE_SDA_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    for needle in ("软 I2C", "位操作", "不用母版 ml_i2c", "PA6", "PA7", "未上板"):
        assert needle in stm32.notes, needle

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["i2c_probe.c", "i2c_probe.h"]
    for rel in mspm0.files:
        assert (MODULES / "i2c_probe" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("I2C_0_SCL", "i2c_scl", "PA1", True, ()),
        ("I2C_0_SDA", "i2c_sda", "PA0", True, ()),
    ]
    assert mspm0.verified is True
    assert mspm0.hardware_bound is False
    # 平台已知代价（工单验收项 8）：板载 LED 共用 + PA0 上拉位未焊
    for needle in ("I2C_0", "DL_I2C", "板载 LED", "上拉", "未上板"):
        assert needle in mspm0.notes, needle


def test_i2c_probe_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：四个宏必须在母版 `pin_config.h`，默认 PA6/PA7
    （= 库内软 I2C 总线共享组那条总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+I2C_PROBE_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+I2C_PROBE_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+I2C_PROBE_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+I2C_PROBE_SDA_PIN\s+Pin_7", text)


# ---------------------------------------------------------------------------
# I2C_0 实例的生死：消费者登记（工单验收项 4 + 反证项 9）
# ---------------------------------------------------------------------------


def test_i2c_probe_is_registered_as_an_i2c_0_consumer():
    """`i2c_probe` 必须在 `INSTANCE_CONSUMERS["I2C_0"]` 里。

    裁剪判据 = 「消费者 ∩ 选中集」：不登记 = 选中本模块时 `I2C_0` 被当成噪音
    裁掉，`I2C_0_INST` 与 PA0/PA1 的 `$assign` 一起消失，编译期才发现。
    """
    assert "i2c_probe" in INSTANCE_CONSUMERS["I2C_0"]


def test_i2c_0_survives_pruning_for_i2c_probe_only_selection():
    """**反证的另一半**（正）：只选 `i2c_probe` 时 `I2C_0` 实例整段存活。

    判据面 = 母版 syscfg 裁剪后的文本里仍有 `$name` 行与两条 `$assign`
    （PA0/PA1）——这三行就是生成工程里那对脚的全部来源。
    """
    master = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    kept = prune_syscfg(master, ["i2c_probe"])
    assert 'I2C_0.$name                     = "I2C_0";' in kept
    assert 'I2C_0.peripheral.sdaPin.$assign = "PA0";' in kept
    assert 'I2C_0.peripheral.sclPin.$assign = "PA1";' in kept


def test_i2c_0_is_pruned_when_no_consumer_is_selected():
    """**反证的另一半**（负）：消费者没被选中时 `I2C_0` 确实会被裁掉。

    拿掉消费者登记那一行，上面那条正断言与本条会一起变红——这就是工单反证项
    的判据本体（真跑一遍的读数记在工单里）。
    """
    master = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    pruned = prune_syscfg(master, ["led"])
    assert "I2C_0.$name" not in pruned
    assert "I2C_0.peripheral.sdaPin.$assign" not in pruned
    assert "I2C_0.peripheral.sclPin.$assign" not in pruned


# ---------------------------------------------------------------------------
# 单选生成：文件落盘 + 那两根线真的进工程（页面与工程同源）
# ---------------------------------------------------------------------------


def test_i2c_probe_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、uvprojx 注册
    `i2c_probe_stm32.c`、`pin_config.h` 在工程根、接线行有 PA6/PA7 两根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["i2c_probe"])
    assert {m.slug for m in resolved.manifests} == {"i2c_probe"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/i2c_probe/code/i2c_probe_stm32.c").is_file()
    assert (out / "modules/i2c_probe/code/i2c_probe_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("i2c_probe_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()

    assert _generated_wiring(PLATFORM_STM32, "i2c_probe") == {
        "I2C_PROBE_SCL": "PA6",
        "I2C_PROBE_SDA": "PA7",
    }
    # 工程 README 的接线表同源（页面与工程同源这条不变量）
    readme = (out / "README.md").read_text(encoding="utf-8")
    table = parse_pin_table(readme)
    rows = {
        row["role_id"]: row["pin"] for row in table if row["slug"] == "i2c_probe"
    }
    assert rows == {"I2C_PROBE_SCL": "PA6", "I2C_PROBE_SDA": "PA7"}


def test_i2c_probe_mspm0_single_select_generation(tmp_path):
    """mspm0 单选生成：`I2C_0` 不被裁剪、模块文件落盘、接线行有 PA1/PA0 两根
    （stm32 带宏、mspm0 走 SysConfig——两平台各自如实）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["i2c_probe"])
    assert {m.slug for m in resolved.manifests} == {"i2c_probe"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_MSPM0,
    )
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'I2C_0.peripheral.sdaPin.$assign = "PA0";' in syscfg
    assert 'I2C_0.peripheral.sclPin.$assign = "PA1";' in syscfg
    for drop in ("AHT10", "HUIDU", "OLED", "ADC12_0", "KEY", "WS2812", "SR04"):
        assert f"const {drop}" not in syscfg, drop
    assert (out / "modules/i2c_probe/code/i2c_probe.c").is_file()
    assert (out / "modules/i2c_probe/code/i2c_probe.h").is_file()

    assert _generated_wiring(PLATFORM_MSPM0, "i2c_probe") == {
        "I2C_0_SCL": "PA1",
        "I2C_0_SDA": "PA0",
    }


# ---------------------------------------------------------------------------
# 平台实现守卫
# ---------------------------------------------------------------------------


def test_i2c_probe_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零母版 ml_i2c
    调用；软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；读寄存器走
    **重复起始**（读阶段不再发停止条件）。"""
    c = (MODULES / "i2c_probe" / "code" / "i2c_probe_stm32.c").read_text(
        encoding="utf-8"
    )
    code_only = strip_comments(c, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(
        r"#define\s+I2C_PROBE_SDA_OUT\(\)\s+gpio_init\(I2C_PROBE_SDA_GPIO, "
        r"I2C_PROBE_SDA_PIN, OUT_OD\)",
        code_only,
    )
    assert re.search(
        r"#define\s+I2C_PROBE_SDA_IN\(\)\s+gpio_init\(I2C_PROBE_SDA_GPIO, "
        r"I2C_PROBE_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+I2C_PROBE_SDA\(x\)\s+gpio_set", code_only)
    for primitive in (
        "i2c_probe_iic_start",
        "i2c_probe_iic_stop",
        "i2c_probe_iic_wait_ack",
        "i2c_probe_iic_send_byte",
        "i2c_probe_iic_read_byte",
    ):
        assert primitive in code_only, primitive

    # SCL 必须显式初始化（F1 复位浮空输入、ODR 写入无效——不初始化 = 总线死）
    assert re.search(
        r"gpio_init\(I2C_PROBE_SCL_GPIO, I2C_PROBE_SCL_PIN, OUT_OD\)", code_only
    )
    assert "I2C_PROBE_SCL(1)" in code_only

    # 地址语义：7 位地址左移一位，读/写位显式拼装（不写魔法值 0x70 之类）
    assert "I2C_PROBE_ADDR_WRITE(addr7)" in code_only
    assert "I2C_PROBE_ADDR_READ(addr7)" in code_only
    assert re.search(r"<<\s*1", code_only)


def test_i2c_probe_stm32_read_reg_uses_repeated_start():
    """读寄存器 = 写寄存器指针 → **重复起始** → 读地址 → 读 1 字节，
    中途不发停止条件（发停止条件会让一部分器件复位寄存器指针，读回错值）。

    判据 = `read_reg` 函数体里 START 出现两次、STOP 只出现一次。
    """
    c = (MODULES / "i2c_probe" / "code" / "i2c_probe_stm32.c").read_text(
        encoding="utf-8"
    )
    code_only = strip_comments(c, keep_preprocessor=True)
    body = code_only.split("uint8_t i2c_probe_read_reg", 1)[1]
    body = body.split("\n}", 1)[0]
    assert body.count("i2c_probe_iic_start()") == 2, body
    assert body.count("i2c_probe_iic_stop()") == 1, body


def test_i2c_probe_mspm0_code_guards():
    """mspm0 代码层守卫：`DL_I2C_*` 全部封在模块 `.c` 里（母版一个 `.h` 都
    没有，`DL_*` 写进 `main.c` 会被生成门禁的 UndefinedCallsError 拒），
    头文件只声明读侧三件事、零 `DL_` 符号；超时失败有返回码（不忙等死循环）。"""
    header = (MODULES / "i2c_probe" / "code" / "i2c_probe.h").read_text(
        encoding="utf-8"
    )
    header_code = strip_comments(header)
    assert "DL_" not in header_code
    assert "ti_msp_dl_config.h" not in header_code
    assert _declared_functions(header) == set(PUBLIC_API)

    c = (MODULES / "i2c_probe" / "code" / "i2c_probe.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert '#include "ti_msp_dl_config.h"' in c
    for symbol in (
        "DL_I2C_startControllerTransfer",
        "DL_I2C_getControllerStatus",
        "DL_I2C_receiveControllerData",
        "I2C_0_INST",
    ):
        assert symbol in code_only, symbol
    # 应答判定用状态位（不是「读回 0 就算通」）
    assert "DL_I2C_CONTROLLER_STATUS_ADDR_ACK" in code_only
    # **每个等待循环都有超时出口**：`timeout` 声明次数 = 有界等待循环个数，
    # 每次声明都必须配一个 `--timeout == 0` 的出口（忙等死循环 = 板子卡死）
    assert code_only.count("--timeout == 0") == code_only.count("uint32_t timeout")


def test_i2c_probe_stm32_bus_is_the_shared_soft_i2c_bus():
    """默认脚落在库内软 I2C 总线共享组（PA6/PA7）——两件软 I2C 件同选时
    共挂一条总线（器件地址各异、多挂协议允许 = 合法共享，既有 11 件先例）。"""
    for slug in ("aht10", "qmc5883l", "i2c_probe"):
        manifest = ModuleManifest.load(MODULES / slug)
        defaults = [p.default for p in manifest.platforms["stm32"].pins]
        assert defaults == ["PA6", "PA7"], slug


def test_api_modules_lists_i2c_probe_as_an_internal_module(tmp_path):
    """工单验收项 1：`GET /api/modules` 能看到它，身份判据按**内部件**。

    判据面 = 真端点（注入配置的 app，照 `test_module_intro.py` 的夹具姿势——
    裸 `create_app()` 会去读本机 `~/.contest_generator/config.json`，CI 上没有
    → 400「未配置 AI API」，那是把「本机装过工具」当夹具）。载荷里
    `kind=internal` + `requires_identity=false` = 「不要求 kit / source_url」，
    页面因此不会给它渲染两行「待补」的购买信息。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app

    ctx = AppContext(
        config_path=tmp_path / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=MODULES,
            masters_dir=LIBRARY_ROOT / "masters",
            autocommit_enabled=False,  # 只读浏览，不写库不提交
        ),
    )
    listed = {m["slug"]: m for m in TestClient(create_app(ctx)).get("/api/modules").json()}
    assert "i2c_probe" in listed, "模块库里看不到 i2c_probe"
    entry = listed["i2c_probe"]
    assert entry["kind"] == "internal"
    assert entry["requires_identity"] is False
    assert entry["description"].strip()
    # 两平台条目都在（两平台实现齐 = 选中哪个平台都有东西可用）
    assert set(entry["platforms"]) == {"mspm0", "stm32"}


def test_ping_asks_the_same_question_on_both_platforms():
    """**两平台 ping 的线上字节对齐**（评审整改的判据化）：都问「这个地址的
    **读方向**有没有东西应答」——mspm0 发读位、stm32 也发读位。

    为什么值得钉：第一版两边不同向（mspm0 读位、stm32 写位），同一件器件会
    在 mspm0 上说通、在 stm32 上说通不了（只应答写地址的从机正是这种）。
    本件的 ping 判定直接写进学生看到的结论（「器件没应答」vs「应答了但寄存器
    不对」），两平台口径分家 = 同一件器件两种结论。这条一旦有人改回写位就红。
    """
    stm32 = strip_comments(
        (MODULES / "i2c_probe" / "code" / "i2c_probe_stm32.c").read_text(
            encoding="utf-8"
        ),
        keep_preprocessor=True,
    )
    ping_body = stm32.split("uint8_t i2c_probe_ping", 1)[1].split("\n}", 1)[0]
    assert "I2C_PROBE_ADDR_READ(addr7)" in ping_body
    assert "I2C_PROBE_ADDR_WRITE(addr7)" not in ping_body

    mspm0 = strip_comments(
        (MODULES / "i2c_probe" / "code" / "i2c_probe.c").read_text(encoding="utf-8"),
        keep_preprocessor=True,
    )
    mspm0_ping = mspm0.split("uint8_t i2c_probe_ping", 1)[1].split("\n}", 1)[0]
    assert "DL_I2C_CONTROLLER_DIRECTION_RX" in mspm0_ping
    assert "DL_I2C_CONTROLLER_DIRECTION_TX" not in mspm0_ping


def test_i2c_probe_pins_surface_the_board_notes_on_the_detection_page():
    """**检测页可见处**（工单验收项 8 后半）：选中本件时，PA0/PA1 的板载注记
    （「板载 LED 共用，通信期间微闪」）真的挂到这两条接线行上。

    判据面 = 检测页装配的唯一出处 `hwcheck_board_view`（`hwcheck_view` 与四个
    端点共用这一处）；注记本体来自板定义 `boards/mspm0-dimx.json` 的
    `BoardPin.notes`——不是本模块自己编的文案。这条把「平台已知代价学生看得见」
    从「恰好有基础设施」钉成「有判据」。
    """
    from contest_generator.boards import board_for_platform
    from contest_generator.hwcheck_board import hwcheck_board_view

    manifests = resolve_selection(MODULES, PLATFORM_MSPM0, ["i2c_probe"]).manifests
    view = hwcheck_board_view(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0)
    )
    by_pin = {row["pin"]: row for row in view.rows if row["slug"] == "i2c_probe"}
    assert set(by_pin) == {"PA0", "PA1"}
    for pin in ("PA0", "PA1"):
        assert "板载 LED 共用" in by_pin[pin]["pin_note"], by_pin[pin]
    # 上拉位未焊那条也必须在（PA0 的板注记里）
    assert "上拉位未焊" in by_pin["PA0"]["pin_note"], by_pin["PA0"]
    # 板上共享单独成列（页面据此单列一条，不只挂在行上）
    shares = {item["pin"]: item for item in view.board_shares}
    assert set(shares) >= {"PA0", "PA1"}
    assert shares["PA0"]["roles"] == ["i2c_probe.I2C_0_SDA"]
    assert shares["PA1"]["roles"] == ["i2c_probe.I2C_0_SCL"]
