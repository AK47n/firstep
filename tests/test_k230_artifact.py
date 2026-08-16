"""K230 视觉副控 Python 副产物（工单 k230-vision-copilot/02 + 03）。

两层测试（工单 02）：
1. 契约单源（k230_render 纯函数）：帧格式常量 / 帧渲染 / 模板占位符——
   与主控侧 coord_detect parse_coord_line 的字段序机械比对锁定（stm32 + mspm0
   双平台 C 源，防漂移：改 C 不同步契约即红）+ ml_uart.c / mspm0 syscfg
   波特率比对；C 侧照旧零改动；
2. 生成层：选中带 python_artifact 声明的模块 → 产物工程根含渲染后的 .py；
   未选 → 产物与现在逐字节一致；同名 output / 模板缺失 → 大声失败且不留
   半成品。该层用测试内构造的最小探针模块走通机制。

工单 03 追加真实 k230 模块（真库 + 真母版）：manifest 形状 / 真实模板契约
渲染（帧格式与契约常量逐字一致，模板只走占位符不重抄字面量）/ 生成层依赖
展开（选中 k230 → coord_detect 自动挂上 + main.py 副产物，双平台对端可配）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.errors import error_entry
from contest_generator.generator import PythonArtifactError, generate, generate_project
from contest_generator.k230_render import (
    COORD_FRAME_FIELDS,
    COORD_FRAME_FORMAT,
    COORD_FRAME_PREFIX,
    NO_DETECT_FRAME,
    UART_BAUDRATE,
    render_coord_frame,
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
COORD_DETECT_STM32_C = (
    REPO_ROOT / "library" / "modules" / "coord_detect" / "code" / "coord_detect_stm32.c"
)
COORD_DETECT_MSPM0_C = (
    REPO_ROOT / "library" / "modules" / "coord_detect" / "code" / "coord_detect.c"
)
ML_UART_C = REPO_ROOT / "library" / "masters" / "stm32" / "ml_libs" / "ml_uart.c"
MSPM0_SYSCFG = REPO_ROOT / "library" / "masters" / "mspm0" / "mspm0.syscfg"

# 双平台 parse_coord_line 源（防漂移锁定同吃一份契约，工单 03 扩 mspm0）
COORD_DETECT_C_SOURCES = (COORD_DETECT_STM32_C, COORD_DETECT_MSPM0_C)

# ---------------------------------------------------------------------------
# 契约单测（k230_render 纯函数）
# ---------------------------------------------------------------------------


def test_coord_frame_format_derived_from_fields():
    """帧格式由字段序派生（单源）：B,<cx>,<cy>,<confidence>,<x1>,<y1>,<x2>,<y2>。"""
    assert COORD_FRAME_FORMAT == "B,{cx},{cy},{confidence},{x1},{y1},{x2},{y2}"


def test_render_coord_frame_orders_fields():
    """帧渲染按契约序落位（x1/y1/x2/y2 与 cx/cy 不混）。"""
    assert render_coord_frame(12, 34, 0.87, 100, 110, 400, 420) == (
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
        "fmt = '{{coord_frame_format}}'\n"
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

# parse_coord_line 的字段提取形态：if (get_field(line, N, buf, sizeof(buf))
# == NULL) return; 后跟 coord_result.<name> = my_atoi/my_atof(buf);——(N, name)
# 序即解析序（不看注释，防注释漂移）
_C_FIELD_ASSIGN_RE = re.compile(
    r"get_field\(line,\s*(\d+),\s*buf,\s*sizeof\(buf\)\)\s*==\s*NULL\)\s*return;\s*"
    r"coord_result\.([a-z0-9_]+)\s*=\s*(?:my_atoi|my_atof)\(buf\);"
)


def _parse_coord_line_body(source: str) -> str:
    """parse_coord_line 函数体：从函数签名到下一节横幅。"""
    start = source.index("static void parse_coord_line(const char *line)")
    end = source.index("// ====", start)
    return source[start:end]


def _c_field_order(body: str) -> list[tuple[int, str]]:
    """从 C 源机械提取字段序：(get_field 索引, coord_result 字段名) 列表。"""
    return [(int(index), name) for index, name in _C_FIELD_ASSIGN_RE.findall(body)]


@pytest.mark.parametrize(
    "source_path", COORD_DETECT_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_parse_coord_line_field_order_locked_to_contract(source_path):
    """防漂移主锁：C 侧 parse_coord_line 的 get_field 序（1..7 逐字段）与
    COORD_FRAME_FIELDS 严格一致——改 C 字段序 / 改名不同步本契约即红。
    双平台 C 源同锁（stm32 coord_detect_stm32.c + mspm0 coord_detect.c）。"""
    source = source_path.read_text(encoding="utf-8")
    pairs = _c_field_order(_parse_coord_line_body(source))

    assert [index for index, _ in pairs] == list(range(1, 8))  # 逐字段顺序解析
    assert [name for _, name in pairs] == list(COORD_FRAME_FIELDS)


@pytest.mark.parametrize(
    "source_path", COORD_DETECT_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_frame_prefix_and_delimiter_locked_to_contract(source_path):
    """帧前缀与分隔符两侧一致：C 侧守卫 line[0] != 'B' || line[1] != ','
    由契约常量推导比对（改契约前缀 / 分隔符不同步 C 即红）。"""
    source = source_path.read_text(encoding="utf-8")
    body = _parse_coord_line_body(source)
    assert f"line[0] != '{COORD_FRAME_PREFIX}' || line[1] != ','" in body


@pytest.mark.parametrize(
    "source_path", COORD_DETECT_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_no_detect_frame_locked_to_contract(source_path):
    """无检测帧两侧一致：C 侧首字符判 'N'，契约 NO_DETECT_FRAME == "N"。"""
    source = source_path.read_text(encoding="utf-8")
    assert "line[0] == 'N'" in _parse_coord_line_body(source)
    assert NO_DETECT_FRAME == "N"


def test_mspm0_syscfg_digit_uart_baudrate_locked_to_contract():
    """波特率两侧一致（mspm0 侧）：母版 syscfg DIGIT_UART 实例（coord_detect
    共享）的 targetBaudRate == 契约 UART_BAUDRATE——C 侧单独改即红。"""
    text = MSPM0_SYSCFG.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^DIGIT_UART\.targetBaudRate\s*=\s*(\d+);", text, re.M)
    assert match and int(match.group(1)) == UART_BAUDRATE


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
    # 摘要带副产物清单（工单 04 前端「模块文件」行消费）：(slug, 输出文件名)
    assert summary.python_artifacts == (("k230_probe", "main.py"),)


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


# ---------------------------------------------------------------------------
# 工单 03：真实 k230 模块（真库 + 真母版）——manifest 形状 + 真实模板契约
# 渲染 + 生成层依赖展开（选中 k230 → coord_detect 自动挂上 + main.py 副产物）
# ---------------------------------------------------------------------------

LIBRARY_MODULES = REPO_ROOT / "library" / "modules"
LIBRARY_MASTERS = REPO_ROOT / "library" / "masters"
K230_MODULE = LIBRARY_MODULES / "k230"
K230_TEMPLATE = K230_MODULE / "code" / "main.py"


def test_k230_manifest_shape_and_contract_dependency():
    """k230 = 纯副产物模块：双平台 files 空（主控侧无自有 C 文件）、依赖
    coord_detect（串口解析 + 引脚由它提供，k230 不重复声明串口 pins）、
    python_artifact 指向真实模板文件。"""
    manifest = ModuleManifest.load(K230_MODULE)
    assert manifest.dependencies == ("coord_detect",)
    assert manifest.python_artifact is not None
    assert manifest.python_artifact.template == "code/main.py"
    assert manifest.python_artifact.output == "main.py"
    for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
        entry = manifest.platforms[platform]
        assert entry.files == ()  # 主控侧无自有 C 文件，不复制不注册
        assert entry.pins == ()  # 串口引脚由 coord_detect 声明，避免实例撞车
    # 依赖侧的串口解析与引脚真实存在（展开后主控工程才"打开就能编译"）
    coord = ModuleManifest.load(LIBRARY_MODULES / "coord_detect")
    for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
        assert coord.platforms[platform].files
        assert {p.type for p in coord.platforms[platform].pins} == {
            "uart_tx",
            "uart_rx",
        }
    assert K230_TEMPLATE.is_file()


def test_k230_template_renders_real_vision_script():
    """真实模板契约渲染：占位符 ← 契约常量（模板不重抄字面量），渲染产物含
    视觉四要素（sensor / find_blobs / 组帧 / uart），帧格式与契约逐字一致
    ——与主控侧 parse_coord_line 的对齐经 COORD_FRAME_FORMAT 单源传递（本文件
    前半的 C 侧锁同吃该单源）。"""
    template = K230_TEMPLATE.read_text(encoding="utf-8")
    # 帧格式 / 无检测帧 / 波特率全走占位符（勿各抄一份字面量）
    for placeholder in (
        "{{coord_frame_format}}",
        "{{no_detect_frame}}",
        "{{uart_baudrate}}",
    ):
        assert placeholder in template, placeholder
    assert COORD_FRAME_FORMAT not in template  # 模板正文不重抄帧格式字面量
    assert "115200" not in template  # 波特率同样只走占位符

    rendered = render_python_artifact(template)
    assert "{{" not in rendered  # 占位符全替换，无残留

    # 视觉四要素齐备：sensor 初始化 / find_blobs / 组帧 / UART 发送
    for marker in (
        "Sensor(width=1024, height=768)",
        "sensor.set_pixformat(Sensor.RGB565)",
        "MediaManager.init()",
        "find_blobs(",
        "FRAME_FORMAT.format(",
        "uart.write(",
    ):
        assert marker in rendered, marker

    # 帧契约单源：渲染后的帧格式 / 无检测帧 / 波特率与契约常量逐字一致
    frame_match = re.search(r"FRAME_FORMAT\s*=\s*'([^']*)'", rendered)
    assert frame_match and frame_match.group(1) == COORD_FRAME_FORMAT
    no_detect_match = re.search(r"NO_DETECT_FRAME\s*=\s*'([^']*)'", rendered)
    assert no_detect_match and no_detect_match.group(1) == NO_DETECT_FRAME
    assert f"UART(UART.UART2, {UART_BAUDRATE})" in rendered
    # 组帧调用按契约字段落位（kwarg 名 = 契约字段全集）
    for field in COORD_FRAME_FIELDS:
        assert f"{field}=" in rendered, field


# 生成层 main.c：只调 coord_detect 的 API（k230 主控侧无自有文件可调）——
# 与 test_module_protocol_mspm0 同形态（真实库 + 真实母版直驱生成）
K230_MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "coord_detect_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    coord_detect_init();\n"
    "    while (1)\n"
    "    {\n"
    "        coord_detect_parse();\n"
    "    }\n"
    "}\n"
)

K230_MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "coord_detect.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    coord_detect_init();\n"
    "    while (1)\n"
    "    {\n"
    "        coord_detect_parse();\n"
    "    }\n"
    "}\n"
    "\n"
    "void DIGIT_UART_INST_IRQHandler(void)\n"
    "{\n"
    "    coord_detect_rx_handler();\n"
    "}\n"
)


def _assert_k230_output(out: Path) -> None:
    """生成产物断言：K230 侧 = 渲染后的真实模板；k230 自身无 C 子树。"""
    py = (out / "main.py").read_text(encoding="utf-8")
    assert py == render_python_artifact(K230_TEMPLATE.read_text(encoding="utf-8"))
    for marker in ("sensor", "find_blobs", "FRAME_FORMAT", "uart.write"):
        assert marker in py
    assert not (out / "modules" / "k230").exists()  # files 空 = 无 C 子树


def test_generate_project_stm32_k230_expands_dependency_and_writes_py(tmp_path):
    """stm32 生成接缝：选中 k230 → 依赖自动展开挂上 coord_detect 解析 +
    K230 侧 main.py（流程入口 generate_project，与 webapp 同接缝）。"""
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["k230"],
        main_c_content=K230_MAIN_C_STM32,
        output_dir=tmp_path / "out",
        module_library_dir=LIBRARY_MODULES,
        masters_dir=LIBRARY_MASTERS,
    )
    out = summary.output_dir
    assert (out / "modules" / "coord_detect" / "code" / "coord_detect_stm32.c").is_file()
    assert (out / "modules" / "coord_detect" / "code" / "coord_detect_stm32.h").is_file()
    assert "main.py" in summary.structure
    # 摘要副产物清单（工单 04）：k230 的 files 空，前端靠它显示 main.py
    assert summary.python_artifacts == (("k230", "main.py"),)
    _assert_k230_output(out)


def test_generate_project_mspm0_k230_expands_dependency_and_writes_py(tmp_path):
    """mspm0 生成接缝（对端可配）：coord_detect 挂上 + DIGIT_UART 共享实例随
    依赖保留在 syscfg + main.py（副产物与主控平台无关）。"""
    summary = generate_project(
        platform=PLATFORM_MSPM0,
        slugs=["k230"],
        main_c_content=K230_MAIN_C_MSPM0,
        output_dir=tmp_path / "out",
        module_library_dir=LIBRARY_MODULES,
        masters_dir=LIBRARY_MASTERS,
    )
    out = summary.output_dir
    assert (out / "modules" / "coord_detect" / "code" / "coord_detect.c").is_file()
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const DIGIT_UART = UART.addInstance();" in syscfg  # coord_detect 共享实例
    assert summary.python_artifacts == (("k230", "main.py"),)
    _assert_k230_output(out)
