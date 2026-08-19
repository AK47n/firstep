"""板级引脚绑定机制层（工单 pin-board-config/02）：bindings 校验 + 双平台
写侧渲染/改写 + 两条新门禁 + 生成集成。

契约（spec）：默认绑定输出与母版逐字节一致；绑定改哪几个角色，只变对应
宏行（stm32 pin_config.h）/ 只换 $assign 引脚值（mspm0 syscfg，实例名/
宏名/通道名不动）；缺省载荷（bindings 不传）= 旧行为逐字节。红证 =
resolve_bindings / 门禁的每个拒绝分支；真库不变量 = 写侧机制的立身之本
（syscfg $assign 引脚值唯一 → 默认值槽位定位成立；stm32 默认单实例 →
实例宏推导成立）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.boards import (
    BOARDS_DIR,
    Board,
    BoardPin,
    board_for_platform,
    load_boards,
    pin_capability_instances,
)
from contest_generator.errors import error_entry
from contest_generator.generator import (
    GateContext,
    ModuleCorpus,
    ModuleFile,
    PinLiteralInMainError,
    TimerConflictError,
    _check_no_pin_literals_in_main,
    _check_pin_bindings,
    _check_timer_instance_conflicts,
    generate,
)
from contest_generator.library import list_modules
from contest_generator.manifest import ModuleManifest, PinDeclaration
from contest_generator.pin_bindings import (
    PinBindingError,
    ResolvedBinding,
    resolve_bindings,
)
from contest_generator.pinwriter import (
    PIN_CONFIG_FILENAME,
    render_pin_config,
    rewrite_syscfg,
)
from contest_generator.syscfg_model import MSPM0_SYSCFG_FILENAME, syscfg_path_matches
from contest_generator.syscfg_prune import prune_syscfg

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
ALL_MANIFESTS = list_modules(LIBRARY_MODULES)
STM32_MASTER_PIN_CONFIG = (STM32_MASTER / PIN_CONFIG_FILENAME).read_text(
    encoding="utf-8", newline=""
)
MSPM0_MASTER_SYSCFG = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
    encoding="utf-8", newline=""
)


def _resolve(platform: str, bindings: dict[str, str]) -> tuple[ResolvedBinding, ...]:
    return resolve_bindings(ALL_MANIFESTS, platform, BOARDS[platform], bindings)


def _bind(role_key: str, pin: str) -> ResolvedBinding:
    """stm32 渲染器测试用：取角色在 stm32 平台的声明（同 id 在 mspm0 也有
    声明时取错平台会拿不到 macros）。实例推导与 resolve 同源（stm32 pwm /
    enc 类型级 = 绑定引脚实例，其余类型 = 默认引脚实例）。"""
    slug, role_id = role_key.split(".")
    for manifest in ALL_MANIFESTS:
        if manifest.slug != slug:
            continue
        entry = manifest.platforms.get("stm32")
        if entry is None:
            continue
        for decl in entry.pins:
            if decl.id == role_id:
                bound_pin = BOARDS["stm32"].pin_index.get(pin)
                default_pin = BOARDS["stm32"].pin_index.get(decl.default)
                instances = (
                    pin_capability_instances(bound_pin, decl.type)
                    if decl.type in ("pwm", "enc") and bound_pin is not None
                    else (
                        pin_capability_instances(default_pin, decl.type)
                        if default_pin is not None
                        else ()
                    )
                )
                return ResolvedBinding(
                    slug=slug,
                    declaration=decl,
                    pin=pin,
                    instances=instances,
                )
    raise AssertionError(f"未找到 stm32 角色 {role_key}")


def _fake_stm32_board(*caps: tuple[str, tuple[str, ...]]) -> Board:
    """假板（enc 类型级下限红证用）：真板扩线后全 io 脚都有 enc token，
    "无 enc token 的脚拒绝"分支只能靠假板直测。"""
    pins = tuple(
        BoardPin(name=name, kind="io", x=0, y=i, side="left", capabilities=cap)
        for i, (name, cap) in enumerate(caps)
    )
    return Board(
        board_id="fake-stm32",
        name="fake",
        platform="stm32",
        pins=pins,
        pin_index={p.name: p for p in pins},
    )


# ---------------------------------------------------------------------------
# bindings 校验（红证）
# ---------------------------------------------------------------------------


def test_resolve_valid_stm32_binding_carries_instances():
    """stm32 enc 角色：实例 = 绑定引脚 enc 线号（类型级，PB4 → enc:4）。"""
    resolved = _resolve("stm32", {"motor.MOTOR_B_ENC": "PB4"})
    assert len(resolved) == 1
    binding = resolved[0]
    assert binding.role_key == "motor.MOTOR_B_ENC"
    assert binding.pin == "PB4"
    assert binding.instances == ("4",)


def test_resolve_empty_and_none_pass_through():
    assert _resolve("stm32", {}) == ()
    assert _resolve("stm32", None) == ()  # type: ignore[arg-type]


def test_resolve_rejects_non_mapping():
    with pytest.raises(PinBindingError, match="bindings 必须是 JSON 对象"):
        resolve_bindings(ALL_MANIFESTS, "stm32", BOARDS["stm32"], "PA0")  # type: ignore[arg-type]


def test_resolve_rejects_bad_key_format():
    with pytest.raises(PinBindingError, match="绑定键格式非法"):
        _resolve("stm32", {"no_dot": "PA0"})
    with pytest.raises(PinBindingError, match="绑定键格式非法"):
        _resolve("stm32", {"a.b.c": "PA0"})
    with pytest.raises(PinBindingError, match="绑定键格式非法"):
        _resolve("stm32", {"": "PA0"})


def test_resolve_rejects_unknown_slug_and_unknown_role():
    with pytest.raises(PinBindingError, match="不存在"):
        _resolve("stm32", {"no_such_module.MOTOR_A_PWM": "PA0"})
    with pytest.raises(PinBindingError, match="不存在"):
        _resolve("stm32", {"motor.NO_SUCH_ROLE": "PA0"})
    # 角色在别的平台声明但本平台没有（motor 的 mspm0 角色不在 stm32 声明）
    with pytest.raises(PinBindingError, match="不存在"):
        _resolve("stm32", {"motor.PWMAB_C0": "PA12"})


def test_resolve_rejects_unknown_pin_board_external():
    """板外脚（mspm0 排针无 PB4/PB5）绑定 = 未知引脚 400（spec 板外默认规则）。"""
    with pytest.raises(PinBindingError, match="PB4"):
        _resolve("mspm0", {"huidu.R3": "PB4"})
    with pytest.raises(PinBindingError, match="PB5"):
        _resolve("mspm0", {"huidu.R4": "PB5"})


def test_resolve_capability_stm32_uart_pair_constraint():
    """uart 类型级（ADR 0012 工单 02）：TX/RX 必须成对同实例——单脚换实例
    （DIGIT_UART_TX→PB10 = UART_3，RX 留默认 UART_1）交集空 → 400 成对绑定；
    成对绑 PB10/PB11 → 两脚实例随绑定引脚推导 ("UART_3",)（旧实例锁：只有
    PA9 有 uart_tx:UART_1，换脚必拒）。"""
    with pytest.raises(PinBindingError, match="必须同实例，请成对绑定"):
        _resolve("stm32", {"digit_uart.DIGIT_UART_TX": "PB10"})
    resolved = _resolve(
        "stm32",
        {"digit_uart.DIGIT_UART_TX": "PB10", "digit_uart.DIGIT_UART_RX": "PB11"},
    )
    assert [b.instances for b in resolved] == [("UART_3",), ("UART_3",)]


def test_resolve_stm32_pwm_type_level_any_pwm_pin():
    """stm32 pwm 类型级（ADR 0011）：任意 pwm:* 脚可绑，实例随**绑定引脚**
    推导喂渲染器（PA6 → TIM3_CH1、PB6 → TIM4_CH1——渲染器写 TIM/CH 宏）。"""
    a = _resolve("stm32", {"motor.MOTOR_A_PWM": "PA6"})
    assert a[0].pin == "PA6"
    assert a[0].instances == ("TIM3_CH1",)
    b = _resolve("stm32", {"motor.MOTOR_A_PWM": "PB6"})
    assert b[0].pin == "PB6"
    assert b[0].instances == ("TIM4_CH1",)


def test_resolve_stm32_pwm_rejects_pin_without_pwm_token():
    """类型级下限：无 pwm token 的脚（PB4 只有 enc/exti）仍拒——报错文案 =
    类型级（不支持角色类型 pwm），非实例锁文案（角色实例随默认引脚锁定）。"""
    with pytest.raises(PinBindingError, match="不支持角色类型 pwm"):
        _resolve("stm32", {"motor.MOTOR_A_PWM": "PB4"})


def test_resolve_capability_stm32_enc_type_level():
    """enc 类型级（ADR 0012 工单 01）：实例（= EXTI 线号）随**绑定引脚**推导
    ——MOTOR_B_ENC 绑 PA6（enc:6）合法（旧同线锁已拆）；无 enc token 的脚拒
    = 类型级下限（假板直测——真板扩线后全 io 脚都有 enc token）。"""
    resolved = _resolve("stm32", {"motor.MOTOR_B_ENC": "PA6"})
    assert resolved[0].pin == "PA6"
    assert resolved[0].instances == ("6",)
    fake = _fake_stm32_board(
        ("PA0", ("enc:0", "gpio_out")),
        ("PB1", ("gpio_out",)),
    )
    with pytest.raises(PinBindingError, match="不支持角色类型 enc"):
        resolve_bindings(ALL_MANIFESTS, "stm32", fake, {"motor.MOTOR_B_ENC": "PB1"})


def test_resolve_capability_mspm0_pwm_full_type_level():
    """mspm0 pwm 全类型级（ADR 0012 工单 04）：PWMAB_C0 通道 C0——PA23 同族
    TIMG 三候选全部随绑定推导（C1 默认 TIMG0 交集非空 → 单脚换位也放行）；
    PA8/PA9 的 TIMA0_C0/C1 跨族合法（03 的族锁已拆）；PB18 只有
    TIMA0_C2N / TIMA1_C1（无 C0 通道）→ 400 通道不匹配。"""
    resolved = _resolve("mspm0", {"motor.PWMAB_C0": "PA23"})
    assert resolved[0].instances == ("TIMG8_C0", "TIMG7_C0", "TIMG0_C0")
    resolved = _resolve(
        "mspm0", {"motor.PWMAB_C0": "PA8", "motor.PWMAB_C1": "PA9"}
    )
    assert next(b for b in resolved if b.role_key == "motor.PWMAB_C0").instances == (
        "TIMA0_C0",
    )
    with pytest.raises(PinBindingError, match="pwm 通道 C0"):
        _resolve("mspm0", {"motor.PWMAB_C0": "PB18"})


def test_resolve_capability_mspm0_single_instance_movable():
    """单实例角色（OLED_SCL 默认 PB2 → i2c_scl:I2C1）可换到同实例脚（PA17）。"""
    resolved = _resolve("mspm0", {"oled.OLED_SCL": "PA17"})
    assert resolved[0].pin == "PA17"
    assert resolved[0].instances == ("I2C1",)


def test_resolve_mspm0_slot_conflict_and_dedupe():
    """同默认引脚 = 同 syscfg 槽位：两角色绑异脚互斥、绑同脚合法（同引脚多
    角色共享 spec 已定）。huidu.L1 与 pid.GRAY_D1 同默认 PA22、同 HUIDU
    实例（module-dep-cleanup 后 DC_MOTOR 只归 motor，key 不再参与）。"""
    with pytest.raises(PinBindingError, match="共用同一槽位"):
        _resolve("mspm0", {"huidu.L1": "PB2", "pid.GRAY_D1": "PB3"})
    assert _resolve("mspm0", {"huidu.L1": "PB2", "pid.GRAY_D1": "PB2"})


def test_resolve_stm32_same_default_different_roles_not_conflicting():
    """stm32 各角色宏族独立：pid.GRAY_D1 与 config.DIP0 同默认 PB12 但宏不同
    （GRAY_D1_* vs DIP_*），绑到不同脚互不冲突（槽位互斥只对 mspm0）。"""
    resolved = _resolve(
        "stm32", {"pid.GRAY_D1": "PB13", "config.DIP0": "PB14"}
    )
    assert {b.role_key for b in resolved} == {"pid.GRAY_D1", "config.DIP0"}


def test_resolve_offboard_default_role_can_bind_inside_board():
    """HUIDU R3 默认已板内（PB6），仍可绑到板内其它脚（PA27）。"""
    resolved = _resolve("mspm0", {"huidu.R3": "PA27"})
    assert resolved[0].pin == "PA27"
    assert resolved[0].instances == ()


def test_error_entry_maps_pin_binding_error_to_400():
    status, message = error_entry(PinBindingError("绑定 motor.X 的引脚 Y 不存在"))
    assert status == 400
    assert "motor.X" in message


# ---------------------------------------------------------------------------
# 真库不变量（写侧机制立身之本）
# ---------------------------------------------------------------------------


def test_syscfg_pin_assign_values_unique_except_intentional_default_overlaps():
    """母版 syscfg 的 $assign 引脚值除刻意默认重叠外唯一：STEP_MOTOR
    SLP2/DIR2 × HUIDU R3/R4（PB6/PB7）与 UWB/Zigbee UART × HUIDU
    （PA23/PA24/PA25/PA26）——全库角色数 > 排针 32 脚数学上无法全互异，
    允许重叠、用户改绑或按模块集裁剪消解。写侧 2026-08-15 起按实例路径
    定位，不再依赖全局唯一。"""
    values = re.findall(
        r'^\s*.+\.\$assign\s*=\s*"([A-Za-z0-9]+)"', MSPM0_MASTER_SYSCFG, re.M
    )
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    assert {v: c for v, c in counts.items() if c != 1} == {
        "PB6": 2,
        "PB7": 2,
        "PA22": 2,
        "PA23": 3,  # HUIDU L2 + UWB_UART TX + DEBUG_UART TX
        "PA24": 3,  # HUIDU L3 + UWB_UART RX + ADC12_0 adcPin3（adc 默认脚）
        "PA25": 2,  # HUIDU L4 + ZIGBEE_UART RX
        "PA26": 2,
        "PA7": 2,  # DC_MOTOR BIN2 + SERVO_PWM ccp0Pin（servo 默认脚）
        "UART2": 2,  # UWB_UART 与 DEBUG_UART 默认同外设（用户改绑消解）
    }


def test_every_mspm0_declared_default_has_path_unique_syscfg_site():
    """全库 mspm0 声明默认值在母版 syscfg 里按实例路径恰一行落点：STEP_MOTOR
    SLP2/DIR2 与 HUIDU R3/R4 默认同值 PB6/PB7 但路径不同（associatedPins 序
    号/实例名不同），改写器按路径形选唯一候选。"""
    sites: dict[str, list[str]] = {}
    for line in MSPM0_MASTER_SYSCFG.splitlines():
        m = re.match(r'^\s*(.+?)\.\$assign\s*=\s*"([A-Za-z0-9]+)"', line)
        if m:
            sites.setdefault(m.group(2), []).append(m.group(1))
    for manifest in ALL_MANIFESTS:
        entry = manifest.platforms.get("mspm0")
        if entry is None:
            continue
        for decl in entry.pins:
            paths = sites.get(decl.default, [])
            matches = [
                p
                for p in paths
                if syscfg_path_matches(decl.type, decl.id, manifest.slug, p)
            ]
            assert len(matches) == 1, (
                f"{manifest.slug}.{decl.id} 默认 {decl.default} 的 syscfg 落点"
                f"按路径形过滤后不是唯一一行（找到 {matches}）"
            )


def test_stm32_declared_defaults_single_instance():
    """stm32 渲染器靠单实例推导宏值（_TIM/_CH/_UART/_INST/_LINE）：全库声明
    默认引脚对角色类型必须单实例（多实例 = 渲染歧义）。"""
    for manifest in ALL_MANIFESTS:
        entry = manifest.platforms.get("stm32")
        if entry is None:
            continue
        for decl in entry.pins:
            default_pin = BOARDS["stm32"].pin_index.get(decl.default)
            if default_pin is None:
                continue  # stm32 无板外默认
            instances = pin_capability_instances(default_pin, decl.type)
            assert len(instances) <= 1, (
                f"{manifest.slug}.{decl.id} 默认 {decl.default} 对"
                f" {decl.type} 多实例 {instances}（渲染歧义）"
            )


# ---------------------------------------------------------------------------
# stm32 pin_config.h 渲染器（逐字节契约）
# ---------------------------------------------------------------------------


def test_render_pin_config_default_bindings_byte_identical():
    """契约核心：空/None/绑定值=默认值 → 与母版逐字节一致。"""
    assert render_pin_config(STM32_MASTER_PIN_CONFIG, ()) == STM32_MASTER_PIN_CONFIG
    assert (
        render_pin_config(
            STM32_MASTER_PIN_CONFIG,
            _resolve("stm32", {"motor.MOTOR_A_PWM": "PA0", "motor.MOTOR_B_ENC": "PA4"}),
        )
        == STM32_MASTER_PIN_CONFIG
    )


def test_render_pin_config_changes_only_bound_macro_lines():
    """绑定改哪几个角色，只变对应宏行：MOTOR_A_DIR → PB12（PORT/PIN 两行）、
    MOTOR_B_ENC → PB4（EXTI 一行——LINE 值不变、DIR 未绑，均不动）。CRLF 保留。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        _resolve("stm32", {"motor.MOTOR_A_DIR": "PB12", "motor.MOTOR_B_ENC": "PB4"}),
    )
    before = STM32_MASTER_PIN_CONFIG.splitlines(True)
    after = out.splitlines(True)
    assert len(before) == len(after)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    changed_lines = [after[i] for i in changed]
    assert changed_lines == [
        "#define MOTOR_A_DIR_PORT    GPIO_B\r\n",
        "#define MOTOR_A_DIR_PIN     Pin_12\r\n",
        "#define MOTOR_B_ENC_EXTI      EXTI_PB4   /* PB4，下降沿触发 */\r\n",
    ]


def test_render_pin_config_enc_line_macro_untouched_when_same_line():
    """enc 换线保线号：MOTOR_B_ENC→PB4（enc:4）时 MOTOR_B_ENC_LINE 值仍是
    4（handler 按此宏条件编译），该行逐字节不动；EXTI 行换成 EXTI_PB4。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG, _resolve("stm32", {"motor.MOTOR_B_ENC": "PB4"})
    )
    assert "MOTOR_B_ENC_LINE      4          /* EXTI 线号（handler 按此条件编译） */\r\n" in out
    assert "EXTI_PA4" not in out
    assert "EXTI_PB4   /* PB4，下降沿触发 */" in out


def test_render_pin_config_gpio_value_shapes():
    """gpio 宏值形状：_PORT → GPIO_<口>、_PIN → Pin_<号>（PB12 → GPIO_B/
    Pin_12；PC13 → GPIO_C/Pin_13——DIR 默认 PA6 之外的真实可绑脚）。"""
    for old_pin, port, pin_no in (("PB12", "GPIO_B", "Pin_12"), ("PC13", "GPIO_C", "Pin_13")):
        binding = _bind("motor.MOTOR_A_DIR", old_pin)
        out = render_pin_config(STM32_MASTER_PIN_CONFIG, (binding,))
        assert f"MOTOR_A_DIR_PORT    {port}\r\n" in out
        assert f"MOTOR_A_DIR_PIN     {pin_no}\r\n" in out


def test_render_pin_config_i2c_binding_now_legal():
    """软 I2C 参数化（ADR 0011 工单 02）：mpu6050 绑非默认脚合法——I2C 宏已
    迁入 pin_config.h（旧预期：宏不在母版 → 大声失败）。PB12 → GPIO_B/Pin_12。"""
    binding = _bind("ml_mpu6050.MPU6050_SCL", "PB12")
    out = render_pin_config(STM32_MASTER_PIN_CONFIG, (binding,))
    assert "#define I2C_GPIO          GPIO_B\r\n" in out
    assert "#define I2C_SCL_GPIO_Pin  Pin_12\r\n" in out


def test_render_pin_config_ambiguous_instance_loud_failure():
    """实例歧义（多实例）→ 渲染器大声失败（真库不变量测试保证现状单实例）。"""
    decl = _bind("motor.MOTOR_A_PWM", "PA0").declaration
    binding = ResolvedBinding(
        slug="motor",
        declaration=decl,
        pin="PA6",
        instances=("TIM2_CH1", "TIM3_CH1"),
    )
    with pytest.raises(PinBindingError, match="实例歧义"):
        render_pin_config(STM32_MASTER_PIN_CONFIG, (binding,))


def test_render_pin_config_instance_macro_shapes():
    """实例宏值形状（防御路径——实例锁下真机不可达，渲染器纯函数直测）：
    _TIM/_CH/_UART/_INST。TIM3_CH1 → TIM_3 / TIM3_CH1；UART_3 → UART_3 /
    USART3；注释旧引脚字样同步替换。"""
    pwm_decl = _bind("motor.MOTOR_A_PWM", "PA0").declaration
    uart_decl = _bind("digit_uart.DIGIT_UART_TX", "PA9").declaration
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        (
            ResolvedBinding(
                slug="motor", declaration=pwm_decl, pin="PA6",
                instances=("TIM3_CH1",),
            ),
            ResolvedBinding(
                slug="digit_uart", declaration=uart_decl, pin="PB10",
                instances=("UART_3",),
            ),
        ),
    )
    assert "#define MOTOR_A_PWM_TIM     TIM_3\r\n" in out
    assert "#define MOTOR_A_PWM_CH      TIM3_CH1   /* PA6 */\r\n" in out
    assert "#define DIGIT_UART             UART_3\r\n" in out
    assert "#define DIGIT_UART_INST        USART3\r\n" in out


# ---------------------------------------------------------------------------
# mspm0 syscfg 改写器（逐字节契约 + 结构钉）
# ---------------------------------------------------------------------------


def test_rewrite_syscfg_default_bindings_byte_identical():
    assert rewrite_syscfg(MSPM0_MASTER_SYSCFG, ()) == MSPM0_MASTER_SYSCFG
    assert (
        rewrite_syscfg(
            MSPM0_MASTER_SYSCFG,
            _resolve("mspm0", {"led.LED": "PA15"}),
        )
        == MSPM0_MASTER_SYSCFG
    )


def test_rewrite_syscfg_changes_only_target_assign_lines():
    """LED 换脚只动 LED_BEEP 一行；HUIDU R3/R4 默认 PB6/PB7 未绑不动。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve("mspm0", {"led.LED": "PA12"}),
    )
    before = MSPM0_MASTER_SYSCFG.splitlines(True)
    after = out.splitlines(True)
    assert len(before) == len(after)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(changed) == 1
    assert after[changed[0]].rstrip("\r\n").endswith('pin.$assign  = "PA12";')
    assert '= "PB6";' in out and '= "PB7";' in out  # R3/R4 未绑照旧


def test_rewrite_syscfg_swap_bindings_applied_simultaneously():
    """同槽位组互换（L1 ↔ L2）：全部绑定对照原始文本定位（先换后查会撞重复
    值——PA23 会同时出现在两行）。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve("mspm0", {"huidu.L1": "PA23", "huidu.L2": "PA22"}),
    )
    assert 'HUIDU.associatedPins[0].pin.$assign = "PA23";' in out
    assert 'HUIDU.associatedPins[1].pin.$assign = "PA22";' in out


def test_rewrite_syscfg_xunji_permuted_slot_by_default_value():
    """xunji P1-P8 与 HUIDU 槽位错序共享：P1 默认 PA24 → HUIDU L3 槽位
    （默认值槽位定位天然对位，无需映射表）。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG, _resolve("mspm0", {"xunji.P1": "PA25"})
    )
    assert 'HUIDU.associatedPins[2].pin.$assign = "PA25";' in out


def test_rewrite_syscfg_duplicate_default_pb6_selects_by_path():
    """默认重叠 PB6（HUIDU R3 vs STEP_MOTOR SLP2）：改绑按实例路径定位——
    绑 STEP_MOTOR 只碰 STEP_MOTOR 行，绑 HUIDU 只碰 HUIDU 行。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve("mspm0", {"step_motor.STEP_MOTOR_SLP2": "PB2"}),
    )
    assert 'STEP_MOTOR.associatedPins[1].pin.$assign  = "PB2";' in out
    assert 'HUIDU.associatedPins[6].pin.$assign = "PB6";' in out

    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG, _resolve("mspm0", {"huidu.R3": "PA27"})
    )
    assert 'HUIDU.associatedPins[6].pin.$assign = "PA27";' in out
    assert 'STEP_MOTOR.associatedPins[1].pin.$assign  = "PB6";' in out


def test_rewrite_syscfg_offboard_default_rewrites_legacy_value():
    """HUIDU R3 默认 PB6 绑到 PA27 → 对应 $assign 行被换掉。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG, _resolve("mspm0", {"huidu.R3": "PA27"})
    )
    assert 'HUIDU.associatedPins[6].pin.$assign = "PA27";' in out


def test_rewrite_syscfg_instance_and_channel_names_unchanged():
    """结构钉：改写后实例名（$name）/ 宏名 / 通道名（ti_driverlib_*）集合与
    母版一致——改写器只碰 $assign 引号值，DCC100_CC0 通道名先例防炸。"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve("mspm0", {
            "led.LED": "PA12",
            "oled.OLED_SCL": "PA17",
            "key.KEY_START": "PA8",
        }),
    )

    def names(text: str) -> set[str]:
        return set(re.findall(r'\.\$name\s*=\s*"([^"]+)"', text)) | set(
            re.findall(r'"\s*(ti_driverlib_\w+)\s*"', text)
        )

    assert names(out) == names(MSPM0_MASTER_SYSCFG)
    assert 'ti_driverlib_pwm_DCC100_CC0' in out  # 通道名逐字未动


def test_rewrite_syscfg_same_slot_same_pin_applied_once():
    """huidu.L1 与 pid.GRAY_D1 同槽位同引脚 → 该槽位一行改动（dedupe）。
    （全文件另有 OLED sclPin 默认 PB2，逐槽位断言。）"""
    out = rewrite_syscfg(
        MSPM0_MASTER_SYSCFG,
        _resolve("mspm0", {"huidu.L1": "PB2", "pid.GRAY_D1": "PB2"}),
    )
    assert out.count('HUIDU.associatedPins[0].pin.$assign = "PB2";') == 1


# ---------------------------------------------------------------------------
# 门禁（骨架引脚字面量 / 绑定校验 / 骨架定时器冲突）
# ---------------------------------------------------------------------------


def _corpus(main_c: str) -> ModuleCorpus:
    return ModuleCorpus(
        platform="stm32",
        modules=(),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(),
        search_dir_headers=(),
        master_project_dir=Path("."),
        main_c=main_c,
    )


def test_no_pin_literals_gate_rejects_code_literals():
    """main.c 内联引脚字面量 → PinLiteralInMainError（GeneratorError 族，
    errors 表 400 中文）。"""
    for bad in (
        "int main(void) { gpio_init(GPIO_A, Pin_0, OUT); while (1); }\n",
        "int main(void) { EXTI_Init(EXTI_PA2); while (1); }\n",
        "#define MY_PIN PA0\nint main(void) { while (1); }\n",
        "int main(void) { GPIO_Pin_13; while (1); }\n",
        "int main(void) { volatile int x = PA28; while (1); }\n",
    ):
        with pytest.raises(PinLiteralInMainError):
            _check_no_pin_literals_in_main(
                _corpus(bad), (), "stm32", GateContext()
            )


def test_no_pin_literals_gate_comment_and_string_exempt():
    """注释里的 PA11 字样（历史产物判例）/ 字符串字面量不误伤；宏名后缀
    （PA12_PORT）不算字面量。"""
    clean = [
        "int main(void) { /* 历史接线注记：PA11 被 USB 占用 */ while (1); }\n",
        'int main(void) { printf("当前引脚 PA12\\n"); while (1); }\n',
        "int main(void) { gpio_init(HUIDU_L1_PORT, HUIDU_L1_PIN, IN); }\n",
        "int main(void) { while (1); }\n",
    ]
    for main_c in clean:
        _check_no_pin_literals_in_main(_corpus(main_c), (), "stm32", GateContext())


def test_no_pin_literals_gate_mspm0_pin_names():
    """mspm0 引脚名（PA28/PB24）同样被拦。"""
    with pytest.raises(PinLiteralInMainError):
        _check_no_pin_literals_in_main(
            _corpus("int main(void) { int x = PA28; while (1); }\n"),
            (), "mspm0", GateContext(),
        )


def test_timer_conflict_gate_rejects_bound_pwm_on_skeleton_timer():
    """骨架 tim_interrupt_ms_init(TIM_3, ...) × 绑定 MOTOR_A_PWM→PA6
    （TIM3_CH1）→ TimerConflictError 400 中文（ADR 0011 门禁 2：同一 TIM 被
    骨架调度占用 = 编译绿运行坏，生成前拦截）。"""
    main_c = (
        "int main(void) { tim_interrupt_ms_init(TIM_3, 10, 0); while (1); }\n"
    )
    with pytest.raises(TimerConflictError, match="TIM3_CH1") as excinfo:
        _check_timer_instance_conflicts(
            _corpus(main_c), ALL_MANIFESTS, "stm32",
            GateContext(
                bindings={"motor.MOTOR_A_PWM": "PA6"}, board=BOARDS["stm32"]
            ),
        )
    assert "TIM_3" in str(excinfo.value)


def test_timer_conflict_gate_both_timer_spellings():
    """TIM_2 / TIM2 两写法都拦（枚举名 TIM_2 与 LLM 换写 TIM2 兼容）：
    MOTOR_B_PWM→PA3 = TIM2_CH4 × 骨架 TIM2 滴答。"""
    for call in ("tim_interrupt_ms_init(TIM_2, 1, 0)", "tim_interrupt_ms_init(TIM2, 1, 0)"):
        with pytest.raises(TimerConflictError, match="TIM2_CH4"):
            _check_timer_instance_conflicts(
                _corpus(f"int main(void) {{ {call}; while (1); }}\n"),
                ALL_MANIFESTS, "stm32",
                GateContext(
                    bindings={"motor.MOTOR_B_PWM": "PA3"}, board=BOARDS["stm32"]
                ),
            )


def test_timer_conflict_gate_comment_exempt():
    """注释里的 tim_interrupt_ms_init 字样不误伤（同 no_pin_literals 先例——
    clex 注释剥离后判定，spec 关键事实：参考 main.c 注释里出现过该调用）。"""
    main_c = (
        "int main(void) {\n"
        "    /* 预留：tim_interrupt_ms_init(TIM_3, 10, 0); */\n"
        "    while (1);\n"
        "}\n"
    )
    _check_timer_instance_conflicts(
        _corpus(main_c), ALL_MANIFESTS, "stm32",
        GateContext(
            bindings={"motor.MOTOR_A_PWM": "PA6"}, board=BOARDS["stm32"]
        ),
    )


def test_timer_conflict_gate_passes_unconflicting_and_default_bindings():
    """骨架 TIM_3 × 绑定 PB6（TIM4_CH1）不冲突直过；绑定 = 默认值（PA0，
    no-op）不触发——默认组合冲突是现状性质不拦（spec 留痕）；空载荷直过。"""
    main_c = (
        "int main(void) { tim_interrupt_ms_init(TIM_3, 10, 0); while (1); }\n"
    )
    _check_timer_instance_conflicts(
        _corpus(main_c), ALL_MANIFESTS, "stm32",
        GateContext(
            bindings={"motor.MOTOR_A_PWM": "PB6"}, board=BOARDS["stm32"]
        ),
    )
    main_c2 = (
        "int main(void) { tim_interrupt_ms_init(TIM_2, 1, 0); while (1); }\n"
    )
    _check_timer_instance_conflicts(
        _corpus(main_c2), ALL_MANIFESTS, "stm32",
        GateContext(
            bindings={"motor.MOTOR_A_PWM": "PA0"}, board=BOARDS["stm32"]
        ),
    )
    _check_timer_instance_conflicts(
        _corpus(main_c2), ALL_MANIFESTS, "stm32", GateContext()
    )


def test_error_entry_maps_timer_conflict_error_to_400():
    """TimerConflictError 显式登记 error_to_http 表 → 400 中文（结构测试
    test_errors.py 反射兜底防漏登）。"""
    status, message = error_entry(
        TimerConflictError(
            "PWM 绑定 TIM3_CH1（motor.MOTOR_A_PWM）与骨架调度定时器 TIM_3 冲突"
        )
    )
    assert status == 400
    assert "TIM3_CH1" in message


def test_pin_bindings_gate_empty_context_passes():
    """缺省空载荷直过（generate_check 产物复核 / 存量测试形态）。"""
    _check_pin_bindings(_corpus(""), (), "stm32", GateContext())


def test_pin_bindings_gate_rejects_invalid_payload():
    with pytest.raises(PinBindingError, match="不存在"):
        _check_pin_bindings(
            _corpus(""), ALL_MANIFESTS, "stm32",
            GateContext(
                bindings={"motor.NO_SUCH_ROLE": "PA0"}, board=BOARDS["stm32"]
            ),
        )


def test_pin_bindings_gate_requires_board_when_bindings_present():
    with pytest.raises(PinBindingError, match="板定义"):
        _check_pin_bindings(
            _corpus(""), ALL_MANIFESTS, "stm32",
            GateContext(bindings={"motor.MOTOR_A_PWM": "PA0"}, board=None),
        )


# ---------------------------------------------------------------------------
# generate() 集成（真母版）：写侧挂钩 + 缺省路径回归
# ---------------------------------------------------------------------------


def test_generate_stm32_with_bindings_rewrites_pin_config(tmp_path):
    """带绑定生成：pin_config.h 只变绑定宏行；无绑定：与母版逐字节一致。"""
    motor = next(m for m in ALL_MANIFESTS if m.slug == "motor")
    # 带绑定
    out_dir = tmp_path / "out_bound"
    generate(
        platform="stm32",
        manifests=[motor],
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out_dir,
        main_c_content="int main(void) { while (1); }\n",
        bindings={"motor.MOTOR_B_ENC": "PB4"},
    )
    written = (out_dir / PIN_CONFIG_FILENAME).read_text(encoding="utf-8", newline="")
    assert "EXTI_PB4" in written
    assert written != STM32_MASTER_PIN_CONFIG
    # 无绑定回归：缺省路径 = 旧行为逐字节
    out_dir2 = tmp_path / "out_default"
    generate(
        platform="stm32",
        manifests=[motor],
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out_dir2,
        main_c_content="int main(void) { while (1); }\n",
    )
    assert (
        out_dir2 / PIN_CONFIG_FILENAME
    ).read_text(encoding="utf-8", newline="") == STM32_MASTER_PIN_CONFIG


def test_generate_mspm0_with_bindings_rewrites_syscfg(tmp_path):
    """带绑定生成：syscfg 先按选中模块裁剪（syscfg-prune/01）再写 $assign；
    无绑定 = 裁剪后基线（不再 == 全量母版，全选理论模块才 == 母版）。"""
    led = next(m for m in ALL_MANIFESTS if m.slug == "led")
    out_dir = tmp_path / "out"
    generate(
        platform="mspm0",
        manifests=[led],
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out_dir,
        main_c_content="int main(void) { while (1); }\n",
        bindings={"led.LED": "PA12"},
    )
    written = (
        out_dir / MSPM0_SYSCFG_FILENAME
    ).read_text(encoding="utf-8", newline="")
    assert 'pin.$assign  = "PA12";' in written
    assert "LED_BEEP.$name" in written
    assert "IMU601.$name" not in written  # 未选 imu_uart → 实例被裁
    assert written != MSPM0_MASTER_SYSCFG
    out_dir2 = tmp_path / "out_default"
    generate(
        platform="mspm0",
        manifests=[led],
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out_dir2,
        main_c_content="int main(void) { while (1); }\n",
    )
    assert (
        out_dir2 / MSPM0_SYSCFG_FILENAME
    ).read_text(encoding="utf-8", newline="") == prune_syscfg(
        MSPM0_MASTER_SYSCFG, ["led"]
    )


def test_generate_with_invalid_bindings_creates_no_output_dir(tmp_path):
    """非法绑定在创建输出目录之前失败（门禁先于 mkdir），不留半成品。"""
    motor = next(m for m in ALL_MANIFESTS if m.slug == "motor")
    out_dir = tmp_path / "out"
    with pytest.raises(PinBindingError, match="pwm"):
        generate(
            platform="stm32",
            manifests=[motor],
            module_library_dir=LIBRARY_MODULES,
            master_project_dir=STM32_MASTER,
            output_dir=out_dir,
            main_c_content="int main(void) { while (1); }\n",
            bindings={"motor.MOTOR_A_PWM": "PB4"},  # PB4 无 pwm token（类型级下限）
        )
    assert not out_dir.exists()
