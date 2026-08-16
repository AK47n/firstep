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
    extract_header_functions,
    find_undefined_calls,
    generate_skeleton,
    generate_smoke_main,
    run_skeleton,
    sanitize_skeleton,
    verify_main_c_interfaces,
)
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
