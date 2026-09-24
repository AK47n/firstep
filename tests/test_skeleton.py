"""main.c 骨架生成与静态自检：接口收集、函数提取、自检拦截、注释占位。

自检只认喂给 LLM 的同一份接口块（build_skeleton_interfaces 的输出）——
保证 AI 引用的每个函数都在所选模块头文件中真实存在，不存在的调用被
改写为注释占位，main.c 骨架保证可编译。
"""

from pathlib import Path

import pytest

from contest_generator.errors import error_entry
from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.skeleton import (
    SkeletonError,
    build_skeleton_interfaces,
    ensure_sysconfig_init,
    extract_header_functions,
    find_undefined_calls,
    generate_skeleton,
    generate_smoke_main,
    run_skeleton,
    sanitize_skeleton,
    verify_main_c_interfaces,
)
from contest_generator.clex import strip_comments
from contest_generator.syscfg_model import MSPM0_SYSCFG_INIT_NAME
from tests.fakes import FakeLLM, make_fake_stm32_ml_master


def _manifests(library_dir: Path, *slugs: str) -> list[ModuleManifest]:
    return [ModuleManifest.load(library_dir / slug) for slug in slugs]


# ---------------------------------------------------------------------------
# 接口收集：LLM 骨架生成输入
# ---------------------------------------------------------------------------


def test_build_skeleton_interfaces_lists_selected_module_headers(fake_module_library):
    manifests = _manifests(fake_module_library, "dht11", "delay")

    blocks = build_skeleton_interfaces(manifests, PLATFORM_MSPM0, fake_module_library)

    assert len(blocks) == 2
    assert blocks[0].startswith("### 模块 dht11（inc/dht11.h）")
    assert "float dht11_read(void);" in blocks[0]
    assert blocks[1].startswith("### 模块 delay（delay.h）")
    assert "void delay_ms(int ms);" in blocks[1]
    # 只取头文件接口，.c 实现文件不喂给 LLM
    assert "dht11.c" not in blocks[0]


def test_build_skeleton_interfaces_module_without_platform_version(
    fake_module_library,
):
    oled = _manifests(fake_module_library, "oled")  # oled 没有 mspm0 版本

    blocks = build_skeleton_interfaces(oled, PLATFORM_MSPM0, fake_module_library)

    assert len(blocks) == 1
    assert "无平台 mspm0 版本" in blocks[0]


def test_build_skeleton_interfaces_preserves_manifest_order(fake_module_library):
    manifests = _manifests(fake_module_library, "oled", "dht11")  # 反着传

    blocks = build_skeleton_interfaces(manifests, PLATFORM_STM32, fake_module_library)

    assert [b.splitlines()[0] for b in blocks] == [
        "### 模块 oled（inc/oled.h）",
        "### 模块 dht11（inc/dht11.h）",
    ]


def test_build_skeleton_interfaces_survives_non_utf8_header(fake_module_library):
    """非 UTF-8 头文件不崩：errors="replace" 编码策略单源（与生成门禁同读法）。"""
    (fake_module_library / "dht11" / "inc" / "dht11.h").write_bytes(
        b"float dht11_read(void);\n\xff\xfe\n"
    )

    blocks = build_skeleton_interfaces(
        _manifests(fake_module_library, "dht11"), PLATFORM_MSPM0, fake_module_library
    )

    assert len(blocks) == 1
    assert chr(0xFFFD) in blocks[0]  # 非法字节以替换字符进接口块，不再崩
    assert "float dht11_read(void);" in blocks[0]


def test_build_skeleton_interfaces_includes_master_headers_after_modules(
    fake_module_library, tmp_path
):
    """母版目录给定时接口集并入母版头（headfile.h + ml_*.h），模块块在前。"""
    master = make_fake_stm32_ml_master(tmp_path / "master")

    blocks = build_skeleton_interfaces(
        _manifests(fake_module_library, "dht11"),
        PLATFORM_STM32,
        fake_module_library,
        master,
    )

    assert blocks[0].startswith("### 模块 dht11（inc/dht11.h）")
    master_blocks = [b for b in blocks if b.startswith("### 母版（ml_libs/")]
    assert [b.splitlines()[0] for b in master_blocks] == [
        "### 母版（ml_libs/headfile.h）",
        "### 母版（ml_libs/ml_exti.h）",
        "### 母版（ml_libs/ml_gpio.h）",
        "### 母版（ml_libs/ml_pwm.h）",
    ]
    assert "void pwm_init(TIMn_enum timn, TIMn_CHn_enum timn_chn, int fre);" in (
        "".join(master_blocks)
    )


def test_build_skeleton_interfaces_master_without_ml_libs_contributes_nothing(
    fake_module_library, fake_ccs_master_project
):
    """mspm0 母版无 ml_libs（构建时 SysConfig 生成头）：并入为空、无副作用。"""
    blocks = build_skeleton_interfaces(
        _manifests(fake_module_library, "dht11"),
        PLATFORM_MSPM0,
        fake_module_library,
        fake_ccs_master_project,
    )

    assert len(blocks) == 1
    assert blocks[0].startswith("### 模块 dht11（inc/dht11.h）")


def test_generate_skeleton_master_ml_api_not_blocked(fake_module_library, tmp_path):
    """骨架自检认母版头：main.c 调母版内嵌实现的 ml_* API 不被打回。"""
    master = make_fake_stm32_ml_master(tmp_path / "master")
    manifests = _manifests(fake_module_library, "dht11")
    llm = FakeLLM(
        main_skeleton=(
            "int main(void) {\n"
            "    float t = dht11_read();\n"
            "    pwm_init(TIM_2, TIM2_CH1, 1000);\n"  # 母版 ml_pwm.h 的真实 API
            "    while (1);\n"
            "}\n"
        )
    )

    main_c, blocked = generate_skeleton(
        llm, "环境监测仪", manifests, PLATFORM_STM32, fake_module_library, master
    )

    assert blocked == ()
    assert "pwm_init(TIM_2, TIM2_CH1, 1000);" in main_c


# ---------------------------------------------------------------------------
# 头文件函数提取
# ---------------------------------------------------------------------------


def test_extract_header_functions_finds_declarations_and_function_macros():
    interfaces = [
        "### 模块 dht11（inc/dht11.h）\n#pragma once\nfloat dht11_read(void);\n",
        "### 模块 delay（delay.h）\n#pragma once\nvoid delay_ms(int ms);\n"
        "#define delay_us(x) delay_ms((x) / 1000)\n",
    ]

    assert extract_header_functions(interfaces) == {"dht11_read", "delay_ms", "delay_us"}


def test_extract_header_functions_ignores_object_macros():
    interfaces = ["#define BUF_SIZE (64)\nfloat read(void);\n"]

    assert extract_header_functions(interfaces) == {"read"}


# ---------------------------------------------------------------------------
# 静态自检：main.c 引用的函数必须存在于所选模块头文件
# ---------------------------------------------------------------------------


def test_find_undefined_calls_flags_only_real_calls():
    main_c = (
        "int main(void) {\n"
        "    float t = dht11_read();\n"  # 头文件里的真函数
        "    delay_ms(100);\n"
        "    dht11_init();\n"  # AI 凭空造的
        "    while (1) {\n"
        "        // dht11_fake() 在注释里不算调用\n"
        "    }\n"
        "}\n"
    )

    assert find_undefined_calls(main_c, {"dht11_read", "delay_ms"}) == ("dht11_init",)


def test_find_undefined_calls_ignores_string_content_but_flags_the_call():
    main_c = 'int main(void) { printf("dht11_init()"); while (1); }\n'

    assert find_undefined_calls(main_c, set()) == ("printf",)


def test_find_undefined_calls_accepts_functions_defined_in_main_c():
    main_c = "int main(void) { helper(); }\nstatic void helper(void) { }\n"

    assert find_undefined_calls(main_c, set()) == ()


def test_find_undefined_calls_accepts_forward_declarations_in_main_c():
    main_c = "void helper(void);\nint main(void) { helper(); }\n"

    assert find_undefined_calls(main_c, set()) == ()


def test_find_undefined_calls_accepts_function_macros_defined_in_main_c():
    main_c = "#define LED_ON() GPIO_PIN_5\nint main(void) { LED_ON(); }\n"

    assert find_undefined_calls(main_c, set()) == ()


def test_find_undefined_calls_ignores_defined_in_preprocessor_condition():
    """判例：2026C 真机 3 连 400 点名 defined——#if defined(X) 的 defined( 是
    预处理器操作符，不是函数调用。"""
    main_c = "#if defined(USE_EXTRA)\nint main(void) { while (1); }\n#endif\n"

    assert find_undefined_calls(main_c, set()) == ()


def test_find_undefined_calls_ignores_calls_in_preprocessor_directives():
    """同族误判：#if fn(...) 条件调用、#pragma pack(...) 等非 define 指令行
    整体剔出调用提取（与 _replace_undefined_calls 同 clex 语义：预处理行不是代码）。"""
    main_c = (
        "#if has_extra(1) && mode_ok()\n"
        "#define LED_ON() GPIO_PIN_5\n"
        "#endif\n"
        "#pragma pack(push, 1)\n"
        "int main(void) { LED_ON(); while (1); }\n"
    )

    assert find_undefined_calls(main_c, set()) == ()


def test_find_undefined_calls_strips_multiline_preprocessor_conditions():
    """跨行 #if 条件的 \\ 续行随指令行一并剔除（续行行首无 #，整段剥不了会漏）。"""
    main_c = (
        "#if defined(USE_A) && \\\n"
        "    defined(USE_B) && \\\n"
        "    has_extra(1)\n"
        "#endif\n"
        "int main(void) { while (1); }\n"
    )

    assert find_undefined_calls(main_c, set()) == ()


def test_find_undefined_calls_accepts_param_macros_defined_in_main_c():
    """B 陷阱守护：#define 行必须留在提取文本里，参数宏 FOO(x) 的调用
    FOO(1) 才不会被误报未定义（整段剥 # 行即红）。"""
    main_c = "#define FOO(x) ((x) * 2)\nint main(void) { return FOO(1); }\n"

    assert find_undefined_calls(main_c, set()) == ()


def test_find_undefined_calls_audits_calls_inside_define_bodies():
    """#define 行保留的刻意后果：宏体内的未定义调用仍被检出（#define TOGGLE()
    fake_gpio_set(1) 一旦展开即链接期必炸，全剥 # 行会漏掉）。"""
    main_c = "#define TOGGLE() fake_gpio_set(1)\nint main(void) { TOGGLE(); }\n"

    assert find_undefined_calls(main_c, set()) == ("fake_gpio_set",)


# ---------------------------------------------------------------------------
# 占位处理：不存在的调用注释化
# ---------------------------------------------------------------------------


def test_sanitize_comments_out_undefined_calls_keeps_valid_calls():
    main_c = (
        "int main(void) {\n"
        "    dht11_init();\n"
        "    oled_init();\n"
        "    while (1);\n"
        "}\n"
    )

    fixed, blocked = sanitize_skeleton(main_c, {"oled_init"})

    assert blocked == ("dht11_init",)
    assert fixed.startswith("int main(void) {")
    assert fixed.endswith("}\n")
    assert "oled_init();" in fixed
    assert "while (1);" in fixed
    # 原调用文本留在 TODO 注释里，用户知道 AI 想干什么
    assert "dht11_init()" in fixed
    assert "不存在的函数 dht11_init" in fixed


def test_sanitize_returns_unchanged_when_all_calls_exist():
    main_c = "int main(void) { oled_init(); while (1); }\n"

    assert sanitize_skeleton(main_c, {"oled_init"}) == (main_c, ())


def test_sanitize_does_not_touch_calls_inside_comments():
    main_c = (
        "int main(void) {\n"
        "    /* dht11_init(); 留作参考 */\n"
        "    while (1);\n"
        "}\n"
    )

    assert sanitize_skeleton(main_c, set()) == (main_c, ())


def test_sanitize_keeps_single_line_main_compilable():
    """整行注释会连 main 一起干掉——占位必须只在调用处做。"""
    main_c = "int main(void) { dht11_init(); while (1); }\n"

    fixed, blocked = sanitize_skeleton(main_c, set())

    assert blocked == ("dht11_init",)
    assert fixed.startswith("int main(void) {")
    assert fixed.endswith("}\n")
    assert "while (1);" in fixed
    assert "不存在的函数 dht11_init" in fixed


def test_sanitize_replaces_expression_calls_with_zero_placeholder():
    main_c = "int x = dht11_init();\nif (dht11_fake()) { x = 1; }\n"

    fixed, blocked = sanitize_skeleton(main_c, set())

    assert blocked == ("dht11_fake", "dht11_init")
    assert "int x =" in fixed
    assert "if (" in fixed
    assert fixed.count("*/ 0") == 2  # 赋值与条件里的调用都改为 0 占位
    assert "}" in fixed


def test_sanitize_preserves_valid_calls_after_blocked_one_on_same_line():
    main_c = "delay_ms(100); dht11_init();\n"

    fixed, blocked = sanitize_skeleton(main_c, {"delay_ms"})

    assert blocked == ("dht11_init",)
    assert "delay_ms(100);" in fixed


def test_sanitize_ignores_parens_inside_string_arguments():
    main_c = 'print(")");\n'

    fixed, blocked = sanitize_skeleton(main_c, set())

    assert blocked == ("print",)
    assert "不存在的函数 print" in fixed
    assert fixed.endswith(";\n")


# ---------------------------------------------------------------------------
# 全流程：fixture 假 LLM 下生成骨架并自检
# ---------------------------------------------------------------------------


def test_generate_skeleton_feeds_header_interfaces_to_llm(fake_module_library):
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM()

    generate_skeleton(llm, "环境监测仪", manifests, PLATFORM_MSPM0, fake_module_library)

    problem, interfaces = llm.skeleton_calls[0]
    assert problem == "环境监测仪"
    assert interfaces[0].startswith("### 模块 dht11（inc/dht11.h）")
    assert "float dht11_read(void);" in interfaces[0]
    assert interfaces[1].startswith("### 模块 delay（delay.h）")
    assert "void delay_ms(int ms);" in interfaces[1]


def test_generate_skeleton_blocks_hallucinated_calls_under_fake_llm(
    fake_module_library,
):
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM(
        main_skeleton=(
            "int main(void) {\n"
            "    float t = dht11_read();\n"  # 头文件里的真函数
            "    delay_ms(100);\n"
            "    dht11_init();\n"  # 假 LLM 出稿里的幻觉调用
            "    while (1);\n"
            "}\n"
        )
    )

    main_c, blocked = generate_skeleton(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, fake_module_library
    )

    assert blocked == ("dht11_init",)
    assert "dht11_read();" in main_c
    assert "delay_ms(100);" in main_c
    assert "不存在的函数 dht11_init" in main_c


def test_generate_skeleton_then_project_keeps_only_real_calls(
    fake_module_library, make_ccs_project, tmp_path
):
    """骨架自检 → 生成器落盘：幻觉调用以占位注释进工程，真调用保留。

    生成器落盘前还会静态自检一遍（UndefinedCallsError 兜底），这里验证
    sanitize 后的骨架能顺利通过并写进工程。
    """
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM(
        main_skeleton=(
            "int main(void) {\n"
            "    float t = dht11_read();\n"
            "    dht11_init();\n"  # 假 LLM 出稿里的幻觉调用 → 占位
            "    while (1);\n"
            "}\n"
        )
    )

    main_c, blocked = generate_skeleton(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, fake_module_library
    )
    assert blocked == ("dht11_init",)

    out = make_ccs_project(
        manifests=manifests, output_dir=tmp_path / "out", main_c_content=main_c
    )
    content = (out / "main.c").read_text(encoding="utf-8")

    assert "int main(void) {" in content
    assert "dht11_read();" in content
    assert "不存在的函数 dht11_init" in content


# ---------------------------------------------------------------------------
# verify_main_c_interfaces：生成器落盘前的静态自检（与骨架阶段同一份接口块）
# ---------------------------------------------------------------------------


def test_verify_main_c_interfaces_flags_calls_outside_module_headers(
    fake_module_library,
):
    manifests = _manifests(fake_module_library, "dht11", "delay")
    main_c = "int main(void) { float t = dht11_read(); dht11_init(); while (1); }\n"

    interfaces = build_skeleton_interfaces(manifests, PLATFORM_MSPM0, fake_module_library)
    undefined = verify_main_c_interfaces(main_c, interfaces)

    assert undefined == ("dht11_init",)


def test_verify_main_c_interfaces_passes_clean_main_c(fake_module_library):
    manifests = _manifests(fake_module_library, "dht11", "delay")
    main_c = "int main(void) { float t = dht11_read(); delay_ms(100); while (1); }\n"

    interfaces = build_skeleton_interfaces(manifests, PLATFORM_MSPM0, fake_module_library)
    undefined = verify_main_c_interfaces(main_c, interfaces)

    assert undefined == ()


def test_generate_skeleton_with_reference_fulltexts_feeds_them_to_llm(
    fake_module_library,
):
    """参考实现进骨架：reference_fulltexts 非空时喂给 LLM（FakeLLM 记录）。"""
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM()

    generate_skeleton(
        llm,
        "环境监测仪",
        manifests,
        PLATFORM_MSPM0,
        fake_module_library,
        reference_fulltexts={"ref-1": "巡线决策参考实现全文"},
    )

    assert llm.skeleton_ref_calls == [{"ref-1": "巡线决策参考实现全文"}]


def test_sanitize_call_with_string_literal_args_spans_regions():
    """实参含字符串字面量时调用跨词法区域：替换后不得残留实参尾巴（真机
    sprintf 判例——旧实现把 \"%s %s\" 起的实参段重复拼出，生成物编译失败）。"""
    main_c = '    sprintf(buf, "%s %s", module, ok ? "OK" : "FAIL");\n'

    fixed, blocked = sanitize_skeleton(main_c, set())

    assert blocked == ("sprintf",)
    assert "已注释占位" in fixed
    assert fixed.rstrip().endswith(";")  # 注释占位后只剩独立分号
    assert fixed.count('"%s %s"') == 1  # 实参尾巴不重复


def test_generate_smoke_main_feeds_interfaces_and_sanitizes(fake_module_library):
    """自检冒烟入口：接口块同源喂给 LLM，出稿走 sanitize_skeleton 同款兜底。"""
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM(
        smoke_skeleton=(
            "int main(void) {\n"
            "    float t = dht11_read();\n"
            "    delay_ms(100);\n"
            "    dht11_init();\n"  # 假 LLM 出稿里的幻觉调用
            "    while (1);\n"
            "}\n"
        )
    )

    main_c, blocked = generate_smoke_main(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, fake_module_library
    )

    problem, interfaces = llm.smoke_calls[0]
    assert problem == "环境监测仪"
    assert interfaces[0].startswith("### 模块 dht11（inc/dht11.h）")
    assert "float dht11_read(void);" in interfaces[0]
    assert blocked == ("dht11_init",)
    assert "dht11_read();" in main_c
    assert "不存在的函数 dht11_init" in main_c


def test_generate_smoke_main_strips_multiple_fences(fake_module_library):
    """LLM 三重围栏：首尾剥后残留的围栏行也全剥（真机 502→400 判例）。"""
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM(
        smoke_skeleton=(
            "```c\n```\n"
            "int main(void) {\n"
            "    float t = dht11_read();\n"
            "    delay_ms(100);\n"
            "    while (1);\n"
            "}\n"
            "```\n"
        )
    )

    main_c, blocked = generate_smoke_main(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, fake_module_library
    )

    assert blocked == ()
    assert "```" not in main_c
    assert main_c.startswith("int main(void) {")


def test_generate_smoke_main_strips_fenced_llm_output(fake_module_library):
    """冒烟出稿的代码围栏同样剥掉（与 generate_skeleton 同款容错）。"""
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM(
        smoke_skeleton=(
            "```c\n"
            "int main(void) {\n"
            "    float t = dht11_read();\n"
            "    delay_ms(100);\n"
            "    while (1);\n"
            "}\n"
            "```\n"
        )
    )

    main_c, blocked = generate_smoke_main(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, fake_module_library
    )

    assert blocked == ()
    assert "```" not in main_c
    assert main_c.startswith("int main(void) {")


def test_generate_skeleton_strips_fenced_llm_output(fake_module_library):
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM(
        main_skeleton=(
            "```c\n"
            "int main(void) {\n"
            "    float t = dht11_read();\n"
            "    delay_ms(100);\n"
            "    while (1);\n"
            "}\n"
            "```\n"
        )
    )

    main_c, blocked = generate_skeleton(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, fake_module_library
    )

    assert blocked == ()
    assert "```" not in main_c
    assert main_c.startswith("int main(void) {")


# ---------------------------------------------------------------------------
# 占位形态：注释后的独立语句、死循环后不可达 return（Keil #174-D/#111-D）
# ---------------------------------------------------------------------------


def test_sanitize_statement_after_comment_line_uses_comment_placeholder():
    """上一行是注释的独立调用必须走注释占位，不能变 0;（#174-D 判例：
    2021F 骨架第一处 strcpy 占位——名字前是非空白字符 */，被误判表达式）。"""
    main_c = (
        "    /* OLED 显示缓冲初始化（实际刷新函数未提供，由外部处理） */\n"
        '    strcpy(oled_line1, "Medicine Car");\n'
        "    oled_dirty = 1;\n"
    )

    fixed, blocked = sanitize_skeleton(main_c, set())

    assert blocked == ("strcpy",)
    assert "不存在的函数 strcpy" in fixed
    assert "已注释占位" in fixed
    assert "*/ 0" not in fixed  # 不能落成 0; 占位
    assert "oled_dirty = 1;" in fixed


def test_sanitize_comments_out_unreachable_return_after_while_loop():
    """while(1) 死循环块后的 return 0; 不可达 → 注释占位（#111-D 判例）。"""
    main_c = (
        "int main(void) {\n"
        "    while (1) {\n"
        "        oled_init();\n"
        "    }\n"
        "    return 0;\n"
        "}\n"
    )

    fixed, blocked = sanitize_skeleton(main_c, {"oled_init"})

    assert blocked == ()
    assert "\n    return 0;\n" not in fixed  # 语句位置的 return 已移除（注释里保留原文）
    assert "while(1) 死循环后不可达" in fixed
    assert "while (1) {" in fixed
    assert "oled_init();" in fixed


def test_sanitize_keeps_return_inside_while_loop():
    """循环体内的 return（可达路径）不动。"""
    main_c = (
        "int main(void) {\n"
        "    while (1) {\n"
        "        if (x) return 0;\n"
        "    }\n"
        "}\n"
    )

    fixed, blocked = sanitize_skeleton(main_c, set())

    assert blocked == ()
    assert "if (x) return 0;" in fixed


def test_sanitize_keeps_return_without_infinite_loop():
    """非死循环后的 return 是合法路径，不动。"""
    main_c = "int main(void) { oled_init(); return 0; }\n"

    fixed, blocked = sanitize_skeleton(main_c, {"oled_init"})

    assert blocked == ()
    assert fixed == main_c


# ---------------------------------------------------------------------------
# run_skeleton 域编排（工单 route-orchestration-homing/01）：main_mode 分支 +
# 冒烟守卫（缺 OLED / debug_uart → SkeletonError 400）+ generate_* 分派直测
# （对照 test_selection 的 run_recommendation 直测先例，不依赖 HTTP）
# ---------------------------------------------------------------------------


def test_run_skeleton_smoke_dispatches_generate_smoke_main(fake_module_library):
    """main_mode="smoke"：走 generate_smoke_main（假 LLM 冒烟出稿 + 同款占位）。"""
    manifests = _manifests(fake_module_library, "dht11", "oled")
    llm = FakeLLM(smoke_skeleton="int main(void) { oled_init(); while (1); }\n")

    result = run_skeleton(
        llm=llm,
        problem_text="温湿度采集",
        manifests=manifests,
        slugs=["dht11", "oled"],
        platform=PLATFORM_STM32,
        library_dir=fake_module_library,
        main_mode="smoke",
    )

    assert set(result) == {"main_c", "intercepted"}
    assert "oled_init();" in result["main_c"]
    assert llm.smoke_calls  # 冒烟分支
    assert not llm.skeleton_calls


def test_run_skeleton_skeleton_mode_dispatches_generate_skeleton(fake_module_library):
    """缺省 / main_mode="skeleton"：走 generate_skeleton（参考全文透传）。"""
    manifests = _manifests(fake_module_library, "dht11", "delay")
    llm = FakeLLM(main_skeleton="int main(void) { dht11_read(); while (1); }\n")

    result = run_skeleton(
        llm=llm,
        problem_text="环境监测仪",
        manifests=manifests,
        slugs=["dht11"],
        platform=PLATFORM_MSPM0,
        library_dir=fake_module_library,
        reference_fulltexts={"ref-1": "参考全文"},
    )

    assert set(result) == {"main_c", "intercepted"}
    assert "dht11_read();" in result["main_c"]
    assert llm.skeleton_calls and not llm.smoke_calls
    assert llm.skeleton_ref_calls == [{"ref-1": "参考全文"}]


def test_run_skeleton_smoke_guard_missing_channel_400(fake_module_library):
    """冒烟守卫：缺 OLED + debug_uart 输出通道 → SkeletonError（400 中文）。"""
    manifests = _manifests(fake_module_library, "dht11")

    with pytest.raises(SkeletonError, match="OLED") as exc_info:
        run_skeleton(
            llm=FakeLLM(),
            problem_text="温湿度采集",
            manifests=manifests,
            slugs=["dht11"],
            platform=PLATFORM_STM32,
            library_dir=fake_module_library,
            main_mode="smoke",
        )

    status, message = error_entry(exc_info.value)
    assert status == 400
    assert "debug_uart" in message


def test_run_skeleton_invalid_main_mode_400(fake_module_library):
    """main_mode 非法值 → SkeletonError（400 中文），不落到生成分支。"""
    manifests = _manifests(fake_module_library, "dht11", "oled")

    with pytest.raises(SkeletonError, match="main_mode") as exc_info:
        run_skeleton(
            llm=FakeLLM(),
            problem_text="温湿度采集",
            manifests=manifests,
            slugs=["dht11", "oled"],
            platform=PLATFORM_STM32,
            library_dir=fake_module_library,
            main_mode="banana",
        )

    status, _ = error_entry(exc_info.value)
    assert status == 400


def test_skeleton_error_registered_400_chinese():
    """SkeletonError 已登记 errors.py → 400 + 中文 message（验收：拒绝 400 中文）。"""
    status, message = error_entry(
        SkeletonError("自检骨架需要 OLED 或 debug_uart 模块作为输出通道")
    )
    assert status == 400
    assert message == "自检骨架需要 OLED 或 debug_uart 模块作为输出通道"


# ---------------------------------------------------------------------------
# 工单 hwcheck-acceptance/01：mspm0 的构建期外部接口面（SysConfig 的 SYSCFG_DL_*）
# ---------------------------------------------------------------------------
#
# 缺口现场：`SYSCFG_DL_init` 由 SysConfig **构建期**生成（`ti_msp_dl_config.h`
# 生成时还不存在），既不在模块头里也不在母版树里——接口面里没有它，sanitize
# 就把 `SYSCFG_DL_init();` 注释掉，学生烧进去"灯不闪、串口一个字没有"。
#
# 这一批用**真母版真 syscfg**（判据是母版现算的，假件测不出真判据）：
# `_syscfg_init_functions(真母版 mspm0.syscfg, 选中集)` 与喂 LLM 的接口块、
# 与 `ensure_sysconfig_init` 的补行，三者必须一致。


def _real_mspm0_master() -> Path:
    return Path(__file__).resolve().parents[1] / "library" / "masters" / "mspm0"


def _real_library() -> Path:
    return Path(__file__).resolve().parents[1] / "library" / "modules"


def _real_manifests(*slugs: str) -> list[ModuleManifest]:
    return _manifests(_real_library(), *slugs)


def _mspm0_syscfg_names(master: Path) -> tuple[str, ...]:
    """真母版 syscfg 现算出的构建期接口面（与产品侧同一处判据，不手抄名字）。"""
    from contest_generator.syscfg_model import parse_syscfg, syscfg_init_functions

    text = (master / "mspm0.syscfg").read_text(encoding="utf-8")
    return syscfg_init_functions(parse_syscfg(text))


def test_mspm0_interface_block_carries_the_build_time_surface():
    """喂 LLM 的接口块 = SysConfig 构建期会生成的名字（恒有四个 + 按实例现算）。

    判据不是手抄名字清单，而是与产品侧同一处判据（`syscfg_init_functions`）
    现算——两块文本必须一致，否则"喂 LLM 的"与"门禁认的"又会分家。
    """
    master = _real_mspm0_master()
    manifests = _real_manifests("led", "delay", "debug_uart")

    blocks = build_skeleton_interfaces(
        manifests, PLATFORM_MSPM0, _real_library(), master
    )
    block = next(b for b in blocks if b.startswith("### 平台外部接口（构建期生成"))

    from contest_generator.syscfg_model import parse_syscfg, syscfg_init_functions

    model = parse_syscfg(
        (master / "mspm0.syscfg").read_text(encoding="utf-8")
    ).prune([m.slug for m in manifests])
    expected = syscfg_init_functions(model)
    for name in expected:
        assert f"void {name}(void);" in block, name
        assert name in extract_header_functions([block]), name
    # 没选中的实例、拼错名、条件生成的 save/restore 都不在
    assert "SYSCFG_DL_LCD_init" not in block
    assert "SYSCFG_DL_TYPO_init" not in block
    assert "SYSCFG_DL_saveConfiguration" not in block
    assert "SYSCFG_DL_restoreConfiguration" not in block
    # stm32 侧一个字都不加（平台外部接口是 mspm0 的事实）
    stm32_blocks = build_skeleton_interfaces(
        manifests, PLATFORM_STM32, _real_library(), master
    )
    assert not [b for b in stm32_blocks if "平台外部接口" in b]


def test_mspm0_skeleton_keeps_syscfg_init_as_a_live_call():
    """**骨架这一路**：LLM 写了 `SYSCFG_DL_init();` 就不再被 sanitize 注释掉。

    缺口现场的原始形态就在这里——修之前这条会红（sanitize 判它"不存在的调用"
    → `/* SYSCFG_DL_init(); */` + TODO），也就是本单的票面第一条验收。
    """
    master = _real_mspm0_master()
    manifests = _real_manifests("led", "delay", "debug_uart")
    llm = FakeLLM(
        main_skeleton=(
            "int main(void)\n"
            "{\n"
            "    SYSCFG_DL_init();\n"
            "    led_init(LED_RED);\n"
            "    while (1) { led_toggle(LED_RED); delay_ms(500); }\n"
            "}\n"
        )
    )

    main_c, blocked = generate_skeleton(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, _real_library(), master
    )

    assert blocked == ()
    assert "SYSCFG_DL_init();" in strip_comments(main_c)
    assert "TODO" not in main_c  # 没被改写为注释占位
    assert "/* SYSCFG_DL_init(); */" not in main_c


def test_mspm0_skeleton_inserts_syscfg_init_when_the_llm_forgot_it():
    """**确定性补行**：LLM 完全没写 init → 落盘 main.c 仍有活调用，且只出现一次。

    门禁放宽接口面只解决"别删"，"LLM 压根没写"同样等于没初始化——现象与注释掉
    一样（灯不闪、串口一个字没有）。所以补行是**确定性**的，不赌 LLM 想起来。
    缩进沿用出稿风格（这里是两格）。
    """
    master = _real_mspm0_master()
    manifests = _real_manifests("led", "delay")
    llm = FakeLLM(
        main_skeleton=(
            "int main(void)\n"
            "{\n"
            "  led_init(LED_RED);\n"
            "  while (1) { led_toggle(LED_RED); delay_ms(500); }\n"
            "}\n"
        )
    )

    main_c, blocked = generate_skeleton(
        llm, "环境监测仪", manifests, PLATFORM_MSPM0, _real_library(), master
    )

    assert blocked == ()
    live = [
        line for line in strip_comments(main_c).splitlines()
        if "SYSCFG_DL_init()" in line
    ]
    assert len(live) == 1, live
    assert live[0].strip() == "SYSCFG_DL_init();"
    assert live[0].startswith("  ") and not live[0].startswith("   "), (
        "缩进沿用 LLM 出稿（这里是两格）：" + repr(live[0])
    )
    assert "板子上什么都不动" in main_c  # 那一行自己带的中文说明
    # 补行后的文本再跑一遍不再插（幂等）
    assert ensure_sysconfig_init(main_c, MSPM0_SYSCFG_INIT_NAME) == main_c


def test_mspm0_skeleton_does_not_duplicate_an_existing_live_call():
    """LLM 已经写了活调用 → 补行**一个字都不改**（不重复插）。"""
    master = _real_mspm0_master()
    llm = FakeLLM(
        main_skeleton=(
            "int main(void)\n"
            "{\n"
            "    SYSCFG_DL_init();\n"
            "    while (1) { }\n"
            "}\n"
        )
    )

    main_c, _ = generate_skeleton(
        llm, "环境监测仪", _real_manifests("led", "delay"), PLATFORM_MSPM0,
        _real_library(), master,
    )

    assert main_c == (
        "int main(void)\n"
        "{\n"
        "    SYSCFG_DL_init();\n"
        "    while (1) { }\n"
        "}\n"
    )


def test_mspm0_skeleton_replaces_the_old_comment_placeholder():
    """旧的注释占位（`/* SYSCFG_DL_init(); */`，本单要消灭的形态）不算"已写"。

    判据是**词法级**的（`iter_c_regions` / 注释剥离）：注释里的调用不算，
    字符串里的同名字样同样不算——所以两种情况都会补出活的调用。

    补法是**就地复活那一行**（不是另插一行）：`SYSCFG_DL_init();` 紧跟一行
    `/* SYSCFG_DL_init(); */` 会读成"还得我再取消注释一次"——正是本单要消灭的
    困惑，所以旧占位必须消失，且活调用恰好一处。
    """
    master = _real_mspm0_master()
    commented = (
        "int main(void)\n"
        "{\n"
        "    /* SYSCFG_DL_init(); */\n"
        "    while (1) { }\n"
        "}\n"
    )

    fixed = ensure_sysconfig_init(commented, MSPM0_SYSCFG_INIT_NAME)

    assert "SYSCFG_DL_init();" in strip_comments(fixed)
    assert fixed.index("SYSCFG_DL_init();") < fixed.index("while (1)")
    assert "/* SYSCFG_DL_init(); */" not in fixed, (
        "旧占位要就地复活，不能与活调用并排：\n" + fixed
    )
    assert strip_comments(fixed).count("SYSCFG_DL_init();") == 1, fixed
    assert fixed == (
        "int main(void)\n"
        "{\n"
        "    SYSCFG_DL_init();\n"
        "    while (1) { }\n"
        "}\n"
    ), "就地复活 = 只换那一段注释文本，缩进与其余行逐字不动：\n" + fixed
    # 字符串里的同名字样（比如一句提示文案）也不许被当成"已经初始化了"
    quoted = (
        "int main(void)\n"
        "{\n"
        '    DEBUG_PRINTF("SYSCFG_DL_init() 没写");\n'
        "    while (1) { }\n"
        "}\n"
    )
    assert "SYSCFG_DL_init();" not in strip_comments(
        quoted.replace('DEBUG_PRINTF("SYSCFG_DL_init() 没写");', "")
    )
    assert "SYSCFG_DL_init();" in strip_comments(
        ensure_sysconfig_init(quoted, MSPM0_SYSCFG_INIT_NAME)
    )


def test_mspm0_skeleton_insertion_is_lexical_not_string_matching():
    """补行的判据是**词法级**的：`MY_SYSCFG_DL_init()` 不算"已经有 init"。

    名字按标识符边界匹配，前缀/后缀相似的名字不冒充——否则真正的初始化照样
    缺失，而补行以为已经写过了（假阴性）。
    """
    master = _real_mspm0_master()
    other = (
        "int main(void)\n"
        "{\n"
        "    MY_SYSCFG_DL_init();\n"
        "    while (1) { }\n"
        "}\n"
    )

    fixed = ensure_sysconfig_init(other, MSPM0_SYSCFG_INIT_NAME)

    assert "    SYSCFG_DL_init();" in fixed
    assert fixed.count("MY_SYSCFG_DL_init();") == 1


def test_mspm0_syscfg_insertion_survives_a_formatted_main_and_stm32_is_untouched():
    """缩进风格保留（四空格）＋ stm32 路径一个字符都不动。

    stm32 那一半是硬性约定：本单的补行只在 mspm0 生效——`main.c` 里插一行
    `SYSCFG_DL_init()` 到 stm32 工程就是编译错误。
    """
    formatted = "int main(void)\n{\n    x();\n}\n"
    assert ensure_sysconfig_init(formatted, MSPM0_SYSCFG_INIT_NAME) == (
        "int main(void)\n{\n"
        "    /* SYSCFG_DL_init()：SysConfig 外设初始化（构建期生成）"
        "——缺了它板子上什么都不动 */\n"
        "    SYSCFG_DL_init();\n"
        "    x();\n}\n"
    )
    # 没有函数体的残缺稿不猜（原样返回）；stm32（init_function=None）同样原样返回
    assert ensure_sysconfig_init("/* main 还没写 */\n", None) == "/* main 还没写 */\n"
    assert ensure_sysconfig_init(formatted, None) == formatted
    # stm32：同一条出稿管线跑下来，main.c 里绝不能出现这个名字
    stm32_llm = FakeLLM(main_skeleton="int main(void)\n{\n    dht11_read();\n}\n")
    stm32_main, _ = generate_skeleton(
        stm32_llm, "环境监测仪", _real_manifests("aht10", "delay"), PLATFORM_STM32,
        _real_library(), _real_mspm0_master(),
    )
    assert "SYSCFG_DL" not in stm32_main


def test_mspm0_smoke_main_gets_the_same_deterministic_insertion():
    """冒烟出稿与骨架共用 `_generate_main_c` → 补行同样生效（两条路一起修）。"""
    master = _real_mspm0_master()
    llm = FakeLLM(smoke_skeleton="int main(void)\n{\n    led_init(LED_RED);\n}\n")

    main_c, _ = generate_smoke_main(
        llm, "环境监测仪", _real_manifests("led", "delay"), PLATFORM_MSPM0,
        _real_library(), master,
    )

    assert "SYSCFG_DL_init();" in strip_comments(main_c)
