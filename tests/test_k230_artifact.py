"""K230 视觉副控 Python 副产物（工单 k230-vision-copilot/02）。

两层测试：
1. 契约单源（k230_render 纯函数）：帧格式常量 / 帧渲染 / 模板占位符——
   与主控侧 ball_detect_stm32.c parse_ball_line 的字段序机械比对锁定
   （防漂移：改 C 不同步契约即红）+ ml_uart.c 波特率比对；C 侧照旧零改动；
2. 生成层：选中带 python_artifact 声明的模块 → 产物工程根含渲染后的 .py；
   未选 → 产物与现在逐字节一致；同名 output / 模板缺失 → 大声失败且不留
   半成品。真 k230 模块留工单 03，本层用测试内构造的最小模块走通机制。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.errors import error_entry
from contest_generator.generator import PythonArtifactError, generate, generate_project
from contest_generator.k230_render import (
    BALL_FRAME_FIELDS,
    BALL_FRAME_FORMAT,
    BALL_FRAME_PREFIX,
    NO_DETECT_FRAME,
    UART_BAUDRATE,
    render_ball_frame,
    render_no_detect_frame,
    render_python_artifact,
)
from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.treewalk import iter_project_files
from tests.fakes import (
    MAIN_SKELETON,
    _add_module,
    make_fake_ccs_theia_master_project,
    make_fake_master_project,
    make_fake_module_library,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BALL_DETECT_STM32_C = (
    REPO_ROOT / "library" / "modules" / "ball_detect" / "code" / "ball_detect_stm32.c"
)
ML_UART_C = REPO_ROOT / "library" / "masters" / "stm32" / "ml_libs" / "ml_uart.c"

# ---------------------------------------------------------------------------
# 契约单测（k230_render 纯函数）
# ---------------------------------------------------------------------------


def test_ball_frame_format_derived_from_fields():
    """帧格式由字段序派生（单源）：B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>。"""
    assert BALL_FRAME_FORMAT == "B,{cx},{cy},{confidence},{x1},{y1},{x2},{y2}"


def test_render_ball_frame_orders_fields():
    """帧渲染按契约序落位（x1/y1/x2/y2 与 cx/cy 不混）。"""
    assert render_ball_frame(12, 34, 0.87, 100, 110, 400, 420) == (
        "B,12,34,0.87,100,110,400,420"
    )


def test_render_no_detect_frame():
    assert render_no_detect_frame() == "N"


def test_uart_baudrate_contract_value():
    assert UART_BAUDRATE == 115200


def test_render_python_artifact_substitutes_contract_vars():
    """模板占位符 ← 契约值（字符串替换，帧格式的花括号不被二次解释）。"""
    template = (
        "uart = UART(1, {{uart_baudrate}})\n"
        "uart.write('{{no_detect_frame}}\\n')\n"
        "fmt = '{{ball_frame_format}}'\n"
    )
    assert render_python_artifact(template) == (
        "uart = UART(1, 115200)\n"
        "uart.write('N\\n')\n"
        "fmt = 'B,{cx},{cy},{confidence},{x1},{y1},{x2},{y2}'\n"
    )


def test_render_python_artifact_passthrough_without_placeholders():
    """无占位符模板原样透传（纯文本模板逐字节不变）。"""
    plain = "# 无占位符模板\nprint('hello')\n"
    assert render_python_artifact(plain) == plain


# ---------------------------------------------------------------------------
# 防漂移：契约与主控侧 C 解析的机械比对（C 侧零改动）
# ---------------------------------------------------------------------------

# parse_ball_line 的字段提取形态：if (get_field(line, N, buf, sizeof(buf))
# == NULL) return; 后跟 ball_result.<name> = my_atoi/my_atof(buf);——(N, name)
# 序即解析序（不看注释，防注释漂移）
_C_FIELD_ASSIGN_RE = re.compile(
    r"get_field\(line,\s*(\d+),\s*buf,\s*sizeof\(buf\)\)\s*==\s*NULL\)\s*return;\s*"
    r"ball_result\.([a-z0-9_]+)\s*=\s*(?:my_atoi|my_atof)\(buf\);"
)


def _parse_ball_line_body(source: str) -> str:
    """parse_ball_line 函数体：从函数签名到下一节横幅。"""
    start = source.index("static void parse_ball_line(const char *line)")
    end = source.index("// ====", start)
    return source[start:end]


def _c_field_order(body: str) -> list[tuple[int, str]]:
    """从 C 源机械提取字段序：(get_field 索引, ball_result 字段名) 列表。"""
    return [(int(index), name) for index, name in _C_FIELD_ASSIGN_RE.findall(body)]


def test_c_parse_ball_line_field_order_locked_to_contract():
    """防漂移主锁：C 侧 parse_ball_line 的 get_field 序（1..7 逐字段）与
    BALL_FRAME_FIELDS 严格一致——改 C 字段序 / 改名不同步本契约即红。"""
    source = BALL_DETECT_STM32_C.read_text(encoding="utf-8")
    pairs = _c_field_order(_parse_ball_line_body(source))

    assert [index for index, _ in pairs] == list(range(1, 8))  # 逐字段顺序解析
    assert [name for _, name in pairs] == list(BALL_FRAME_FIELDS)


def test_c_frame_prefix_and_delimiter_locked_to_contract():
    """帧前缀与分隔符两侧一致：C 侧守卫 line[0] != 'B' || line[1] != ','
    由契约常量推导比对（改契约前缀 / 分隔符不同步 C 即红）。"""
    source = BALL_DETECT_STM32_C.read_text(encoding="utf-8")
    body = _parse_ball_line_body(source)
    assert f"line[0] != '{BALL_FRAME_PREFIX}' || line[1] != ','" in body


def test_c_no_detect_frame_locked_to_contract():
    """无检测帧两侧一致：C 侧首字符判 'N'，契约 NO_DETECT_FRAME == "N"。"""
    source = BALL_DETECT_STM32_C.read_text(encoding="utf-8")
    assert "line[0] == 'N'" in _parse_ball_line_body(source)
    assert NO_DETECT_FRAME == "N"


def test_c_uart_baudrate_locked_to_contract():
    """波特率两侧一致：ml_uart.c 全库角色配置的 uart_baud_config 波特率
    含契约 UART_BAUDRATE——C 侧单独改即红（契约 = 115200 另有常量断言）。"""
    # 母版旧工程可能是 GBK 等编码（master.py 同规），errors="replace" 读——
    # 正则只吃 ASCII 的 uart_baud_config 调用，替换字符无碍
    source = ML_UART_C.read_text(encoding="utf-8", errors="replace")
    values = {
        int(value)
        for value in re.findall(r"uart_baud_config\(uartn,\s*(\d+)\)", source)
    }
    assert UART_BAUDRATE in values


# ---------------------------------------------------------------------------
# 生成层：测试内构造的最小 k230 模块（manifest 带 python_artifact + 最小模板，
# 脚本只 sensor 初始化 + 串口发 N；真 k230 模块留工单 03）
# ---------------------------------------------------------------------------

K230_PROBE_TEMPLATE = (
    "# K230 视觉副控最小链路探针（工单 02 测试内构造）：sensor 初始化 + 串口只发无检测帧\n"
    "import sensor, time\n"
    "from machine import UART\n"
    "\n"
    "sensor.reset()\n"
    "sensor.set_pixformat(sensor.RGB565)\n"
    "\n"
    "uart = UART(1, {{uart_baudrate}})\n"
    "\n"
    "while True:\n"
    "    uart.write('{{no_detect_frame}}\\n')\n"
    "    time.sleep_ms(50)\n"
)

K230_PROBE_EXPECTED = (
    "# K230 视觉副控最小链路探针（工单 02 测试内构造）：sensor 初始化 + 串口只发无检测帧\n"
    "import sensor, time\n"
    "from machine import UART\n"
    "\n"
    "sensor.reset()\n"
    "sensor.set_pixformat(sensor.RGB565)\n"
    "\n"
    "uart = UART(1, 115200)\n"
    "\n"
    "while True:\n"
    "    uart.write('N\\n')\n"
    "    time.sleep_ms(50)\n"
)


def _add_k230_probe_module(library: Path) -> None:
    """最小 k230 探针模块：双平台空 files 条目（无 C 代码进主控工程）+
    python_artifact 声明（模板 + 输出 main.py）。"""
    _add_module(
        library,
        {
            "slug": "k230_probe",
            "description": "K230 视觉副控最小链路探针（测试内构造，真模块工单 03）",
            "dependencies": [],
            "python_artifact": {
                "template": "code/k230_probe.py",
                "output": "main.py",
            },
            "platforms": {
                "stm32": {"files": [], "verified": True},
                "mspm0": {"files": [], "verified": True},
            },
        },
        {"code/k230_probe.py": K230_PROBE_TEMPLATE},
    )


def _probe_library(tmp_path: Path) -> Path:
    library = make_fake_module_library(tmp_path / "modules")
    _add_k230_probe_module(library)
    return library


def test_generate_stm32_selected_artifact_writes_py(tmp_path):
    """选中带声明的模块 → 产物工程根出现渲染后的 .py；不注册进 .uvprojx；
    空 files 平台条目不复制 C 子树。"""
    library = _probe_library(tmp_path)
    master = make_fake_master_project(tmp_path / "master")
    probe = ModuleManifest.load(library / "k230_probe")

    out = generate(
        platform=PLATFORM_STM32,
        manifests=[probe],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content="int main(void) { while (1); }\n",
    )[0]

    assert (out / "main.py").read_text(encoding="utf-8") == K230_PROBE_EXPECTED
    assert "main.py" not in (out / "project.uvprojx").read_text(encoding="utf-8")
    assert not (out / "modules").exists()  # 空 files：无 C 子树


def test_generate_mspm0_selected_artifact_writes_py(tmp_path):
    """mspm0 线同样产出 .py（副产物与主控平台无关，syscfg 单 pipeline 后照写）。"""
    library = _probe_library(tmp_path)
    master = make_fake_ccs_theia_master_project(tmp_path / "master")
    probe = ModuleManifest.load(library / "k230_probe")

    out = generate(
        platform=PLATFORM_MSPM0,
        manifests=[probe],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content="int main(void) { while (1); }\n",
    )[0]

    assert (out / "main.py").read_text(encoding="utf-8") == K230_PROBE_EXPECTED


def test_generate_project_summary_lists_python_artifact(tmp_path):
    """流程接缝：摘要结构清单含 .py（describe_generation 读产物树）。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    library = _probe_library(tmp_path)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["k230_probe"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=masters_dir,
    )

    assert "main.py" in summary.structure
    assert (summary.output_dir / "main.py").is_file()


def test_generate_without_artifact_module_is_byte_identical(tmp_path):
    """未选任何带声明模块 → 产物与现在逐字节一致：唯一差异 = 副产物本身。"""
    library = _probe_library(tmp_path)
    master = make_fake_master_project(tmp_path / "master")
    dht11 = ModuleManifest.load(library / "dht11")
    probe = ModuleManifest.load(library / "k230_probe")

    def _files(root: Path) -> dict[str, bytes]:
        return {
            p.relative_to(root).as_posix(): p.read_bytes()
            for p in iter_project_files(root)
        }

    baseline = generate(
        platform=PLATFORM_STM32,
        manifests=[dht11],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out_base",
        main_c_content=MAIN_SKELETON,
    )[0]
    with_probe = generate(
        platform=PLATFORM_STM32,
        manifests=[dht11, probe],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out_probe",
        main_c_content=MAIN_SKELETON,
    )[0]

    base_files = _files(baseline)
    probe_files = _files(with_probe)
    assert not any(rel.endswith(".py") for rel in base_files)  # 未选 = 无 .py
    assert set(probe_files) == set(base_files) | {"main.py"}
    for rel, content in base_files.items():
        assert probe_files[rel] == content  # 共现文件逐字节一致


# ---------------------------------------------------------------------------
# 生成层失败路径：同名 output / 模板缺失 → 大声失败，不留半成品
# ---------------------------------------------------------------------------


def _add_artifact_module(
    library: Path, slug: str, output: str, files: dict[str, str]
) -> None:
    _add_module(
        library,
        {
            "slug": slug,
            "description": f"{slug}（副产物冲突测试）",
            "dependencies": [],
            "python_artifact": {"template": "code/script.py", "output": output},
            "platforms": {"stm32": {"files": [], "verified": True}},
        },
        files,
    )


def test_generate_artifact_output_collision_fails_cleanly(tmp_path):
    """跨模块同名 output → 大声失败（不静默覆盖），输出目录被清（rmtree 兜底）。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_artifact_module(library, "k230_a", "main.py", {"code/script.py": "# a\n"})
    _add_artifact_module(library, "k230_b", "main.py", {"code/script.py": "# b\n"})
    master = make_fake_master_project(tmp_path / "master")
    manifests = [
        ModuleManifest.load(library / slug) for slug in ("k230_a", "k230_b")
    ]
    output_dir = tmp_path / "out"

    with pytest.raises(PythonArtifactError, match="k230_a.*k230_b.*main.py"):
        generate(
            platform=PLATFORM_STM32,
            manifests=manifests,
            module_library_dir=library,
            master_project_dir=master,
            output_dir=output_dir,
            main_c_content="int main(void) { while (1); }\n",
        )

    assert not output_dir.exists()  # 不留半成品


def test_generate_artifact_output_clobbers_project_file_fails(tmp_path):
    """output 撞工程既有文件（母版 main.c）→ 大声失败，不静默覆盖也不被
    后续 main.c 落盘反向覆盖（副产物静默丢失）。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_artifact_module(library, "k230_bad", "main.c", {"code/script.py": "# x\n"})
    master = make_fake_master_project(tmp_path / "master")
    bad = ModuleManifest.load(library / "k230_bad")
    output_dir = tmp_path / "out"

    with pytest.raises(PythonArtifactError, match="main.c.*既有文件"):
        generate(
            platform=PLATFORM_STM32,
            manifests=[bad],
            module_library_dir=library,
            master_project_dir=master,
            output_dir=output_dir,
            main_c_content="int main(void) { while (1); }\n",
        )

    assert not output_dir.exists()  # 不留半成品


def test_generate_artifact_missing_template_fails_cleanly(tmp_path):
    """声明了模板但文件缺失 → 大声失败点名模块与模板路径，输出目录被清。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_module(
        library,
        {
            "slug": "k230_ghost",
            "description": "模板缺失的坏模块",
            "dependencies": [],
            "python_artifact": {"template": "code/ghost.py", "output": "main.py"},
            "platforms": {"stm32": {"files": [], "verified": True}},
        },
        {},
    )
    master = make_fake_master_project(tmp_path / "master")
    ghost = ModuleManifest.load(library / "k230_ghost")
    output_dir = tmp_path / "out"

    with pytest.raises(PythonArtifactError, match="ghost.py") as excinfo:
        generate(
            platform=PLATFORM_STM32,
            manifests=[ghost],
            module_library_dir=library,
            master_project_dir=master,
            output_dir=output_dir,
            main_c_content="int main(void) { while (1); }\n",
        )

    assert "k230_ghost" in str(excinfo.value)
    assert not output_dir.exists()  # 不留半成品


def test_python_artifact_error_registered_as_400():
    """错误映射：PythonArtifactError 登记 400 中文（结构测试另有全量反射兜底）。"""
    status, message = error_entry(
        PythonArtifactError(
            "模块 k230_a 与模块 k230_b 的 python_artifact 输出同名 main.py"
        )
    )
    assert status == 400
    assert "同名 main.py" in message
