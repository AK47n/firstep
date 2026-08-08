"""main.c 骨架生成与静态自检：接口收集、函数提取、自检拦截、注释占位。

自检只认喂给 LLM 的同一份接口块（build_skeleton_interfaces 的输出）——
保证 AI 引用的每个函数都在所选模块头文件中真实存在，不存在的调用被
改写为注释占位，main.c 骨架保证可编译。
"""

from pathlib import Path

from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.skeleton import (
    build_skeleton_interfaces,
    extract_header_functions,
    find_undefined_calls,
    generate_skeleton,
    sanitize_skeleton,
    strip_code_fences,
    verify_main_c,
)
from tests.fakes import FakeLLM


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
# verify_main_c：生成器落盘前的静态自检（与骨架阶段同一份接口块）
# ---------------------------------------------------------------------------


def test_verify_main_c_flags_calls_outside_module_headers(fake_module_library):
    manifests = _manifests(fake_module_library, "dht11", "delay")
    main_c = "int main(void) { float t = dht11_read(); dht11_init(); while (1); }\n"

    undefined = verify_main_c(main_c, manifests, PLATFORM_MSPM0, fake_module_library)

    assert undefined == ("dht11_init",)


def test_verify_main_c_passes_clean_main_c(fake_module_library):
    manifests = _manifests(fake_module_library, "dht11", "delay")

    undefined = verify_main_c(
        "int main(void) { float t = dht11_read(); delay_ms(100); while (1); }\n",
        manifests,
        PLATFORM_MSPM0,
        fake_module_library,
    )

    assert undefined == ()


# ---------------------------------------------------------------------------
# strip_code_fences：LLM 围栏输出剥离（判例：围栏落盘 → Keil unrecognized token）
# ---------------------------------------------------------------------------


def test_strip_code_fences_removes_leading_and_trailing_fence():
    raw = "```c\nint main(void) { return 0; }\n```\n"

    assert strip_code_fences(raw) == "int main(void) { return 0; }\n"


def test_strip_code_fences_handles_tilde_fence_and_no_lang():
    raw = "~~~\nint main(void) {}\n~~~"

    assert strip_code_fences(raw) == "int main(void) {}\n"


def test_strip_code_fences_passthrough_without_fences():
    code = "int main(void) { return 0; }\n"

    assert strip_code_fences(code) == code


def test_strip_code_fences_does_not_touch_middle_fence_lines():
    # 围栏在中间 = 不是包裹形态（可能是注释里的示例代码），不剥
    code = "// ```c\nint main(void) {}\n"

    assert strip_code_fences(code) == code


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


def test_strip_comments_keep_preprocessor_preserves_include_filename_on_later_lines():
    """判例：pid.c 第 2 行的 #include 文件名曾因行首判断失误被当字符串剥掉。"""
    from contest_generator.skeleton import _strip_comments_keep_preprocessor

    code = (
        '#include "headfile.h"\n'
        '#include "digit_uart.h"\n'
        '// #include "commented.h"\n'
        'void f(void) {}\n'
    )

    stripped = _strip_comments_keep_preprocessor(code)

    assert '"digit_uart.h"' in stripped
    assert '"headfile.h"' in stripped
    assert "commented.h" not in stripped  # 注释里的 include 不算数
