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

工单 k230-digit-vision/01 追加 DIGIT 数字识别帧契约（AI 检测）：
- k230_render 新增 DIGIT_FRAME_HEADER / DIGIT_FRAME_LINE_FIELDS（格式由
  字段序派生，confidence {:.2f} 特殊化）/ 消费槽位 / 无检测帧常量，
  + {{digit_frame_header}} / {{digit_frame_line}} 占位符与帧头渲染函数；
- 防漂移：与 digit_uart 双平台（stm32 digit_uart.c / mspm0 digit_uart_mspm0.c）
  parse_digit_line 的 get_field 序机械比对（解析端只消费槽位 0/1/6/7 =
  label/confidence/cx/cy，其余为契约占位）+ 帧头 "---" 守卫 + 无检测帧
  语义（count=0 重置 → 空行帧尾 → best_count>0 最佳帧替换）比对。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from contest_generator.errors import error_entry
from contest_generator.generator import PythonArtifactError, generate, generate_project
from contest_generator.k230_render import (
    COORD_FRAME_FIELDS,
    COORD_FRAME_FORMAT,
    COORD_FRAME_PREFIX,
    DIGIT_FRAME_CONSUMED_INDICES,
    DIGIT_FRAME_HEADER,
    DIGIT_FRAME_LINE_FIELDS,
    DIGIT_FRAME_LINE_FORMAT,
    DIGIT_FRAME_NO_DETECT_COUNT,
    NO_DETECT_FRAME,
    UART_BAUDRATE,
    render_coord_frame,
    render_digit_frame_header,
    render_no_detect_frame,
    render_python_artifact,
)
from contest_generator.manifest import AssetSpec, ManifestError, ModuleManifest
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.selection import (
    DependencyCycleError,
    resolve_selection,
)
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

DIGIT_UART_STM32_C = (
    REPO_ROOT / "library" / "modules" / "digit_uart" / "code" / "digit_uart.c"
)
DIGIT_UART_MSPM0_C = (
    REPO_ROOT / "library" / "modules" / "digit_uart" / "code" / "digit_uart_mspm0.c"
)

# 双平台 parse_digit_line 源（工单 k230-digit-vision/01 防漂移锁定）
DIGIT_UART_C_SOURCES = (DIGIT_UART_STM32_C, DIGIT_UART_MSPM0_C)

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


def test_digit_frame_header_contract_value():
    """DIGIT 帧头单源：`--- frame N | M targets ---`，解析端 line_buf[0..2]
    为 '-' 判帧界（防漂移见 C 侧守卫比对）。"""
    assert DIGIT_FRAME_HEADER == "--- frame {n} | {m} targets ---"
    assert DIGIT_FRAME_HEADER.startswith("---")


def test_digit_frame_line_shape_contract():
    """数据行 10 字段（label,confidence,x1,y1,x2,y2,cx,cy,w,h），格式由
    字段序派生（COORD 同模式）：占位符序列 == 字段序列（位置↔字段名映射
    逐位一致——改字段序不同步格式即 CSV 列错位，解析端按逗号位置消费）；
    confidence 两位小数特殊化 {:.2f}；解析端只消费槽位 0/1/6/7。"""
    assert len(DIGIT_FRAME_LINE_FIELDS) == 10
    assert DIGIT_FRAME_LINE_FIELDS[0] == "label"
    assert DIGIT_FRAME_LINE_FIELDS[1] == "confidence"
    assert DIGIT_FRAME_LINE_FIELDS[6] == "cx"
    assert DIGIT_FRAME_LINE_FIELDS[7] == "cy"
    # 占位符序列（字段名）与字段序列逐位一致
    placeholders = re.findall(r"\{([a-z0-9_]+)", DIGIT_FRAME_LINE_FORMAT)
    assert placeholders == list(DIGIT_FRAME_LINE_FIELDS)
    assert DIGIT_FRAME_LINE_FORMAT == (
        "{label},{confidence:.2f},{x1},{y1},{x2},{y2},{cx},{cy},{w},{h}"
    )
    assert DIGIT_FRAME_CONSUMED_INDICES == (0, 1, 6, 7)


def test_render_digit_frame_header_and_no_detect():
    """DIGIT 帧头渲染单源：n = 帧序号自增占位，count = 目标数；
    无检测帧 = count = DIGIT_FRAME_NO_DETECT_COUNT（0）。"""
    assert render_digit_frame_header(5, 2) == "--- frame 5 | 2 targets ---"
    assert (
        render_digit_frame_header(7, DIGIT_FRAME_NO_DETECT_COUNT)
        == "--- frame 7 | 0 targets ---"
    )
    assert DIGIT_FRAME_NO_DETECT_COUNT == 0


def test_render_python_artifact_substitutes_digit_vars():
    """{{digit_frame_header}} / {{digit_frame_line}} ← 契约值（字符串替换，
    帧头/行格式的花括号不被二次解释，模板里 .format 自行消费 {n}/{m} 与
    字段名前缀）。"""
    template = (
        "HDR = '{{digit_frame_header}}'\n"
        "LINE = '{{digit_frame_line}}'\n"
        "uart.write(HDR.format(n=5, m=2) + '\\n')\n"
        "uart.write(LINE.format(label=3, confidence=0.85, x1=10, y1=20, "
        "x2=30, y2=40, cx=50, cy=60, w=70, h=80) + '\\n')\n"
    )
    assert render_python_artifact(template) == (
        "HDR = '--- frame {n} | {m} targets ---'\n"
        "LINE = '{label},{confidence:.2f},{x1},{y1},{x2},{y2},{cx},{cy},{w},{h}'\n"
        "uart.write(HDR.format(n=5, m=2) + '\\n')\n"
        "uart.write(LINE.format(label=3, confidence=0.85, x1=10, y1=20, "
        "x2=30, y2=40, cx=50, cy=60, w=70, h=80) + '\\n')\n"
    )


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


def _parse_fn_body(source: str, signature: str) -> str:
    """函数体切片：从函数签名到下一节横幅（机械提取防漂移用）。"""
    start = source.index(signature)
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
    pairs = _c_field_order(_parse_fn_body(source, "static void parse_coord_line(const char *line)"))

    assert [index for index, _ in pairs] == list(range(1, 8))  # 逐字段顺序解析
    assert [name for _, name in pairs] == list(COORD_FRAME_FIELDS)


@pytest.mark.parametrize(
    "source_path", COORD_DETECT_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_frame_prefix_and_delimiter_locked_to_contract(source_path):
    """帧前缀与分隔符两侧一致：C 侧守卫 line[0] != 'B' || line[1] != ','
    由契约常量推导比对（改契约前缀 / 分隔符不同步 C 即红）。"""
    source = source_path.read_text(encoding="utf-8")
    body = _parse_fn_body(source, "static void parse_coord_line(const char *line)")
    assert f"line[0] != '{COORD_FRAME_PREFIX}' || line[1] != ','" in body


@pytest.mark.parametrize(
    "source_path", COORD_DETECT_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_no_detect_frame_locked_to_contract(source_path):
    """无检测帧两侧一致：C 侧首字符判 'N'，契约 NO_DETECT_FRAME == "N"。"""
    source = source_path.read_text(encoding="utf-8")
    assert "line[0] == 'N'" in _parse_fn_body(source, "static void parse_coord_line(const char *line)")
    assert NO_DETECT_FRAME == "N"


# ---------------------------------------------------------------------------
# 防漂移：DIGIT 数字识别帧契约与 digit_uart 双平台 parse_digit_line 的
# 机械比对（工单 k230-digit-vision/01，C 侧零改动）
# ---------------------------------------------------------------------------

# parse_digit_line 的字段提取形态：if (get_field(line, N, buf, sizeof(buf))
# == NULL) return; 后跟 d-><name> 赋值（label 为花括号块内 d->label[i++] 拷贝，
# confidence/cx/cy 为 d-><name> = my_atof/my_atoi(buf);）——按调用切段，每段
# 第一个 d-> 字段名即该 get_field 的消费目标（不看注释，防注释漂移）
_DIGIT_FIELD_SPLIT_RE = re.compile(
    r"get_field\(line,\s*(\d+),\s*buf,\s*sizeof\(buf\)\)\s*==\s*NULL\)\s*return;"
)


def _digit_field_order(body: str) -> list[tuple[int, str]]:
    """从 C 源机械提取字段序：(get_field 索引, d-> 字段名) 列表。"""
    parts = _DIGIT_FIELD_SPLIT_RE.split(body)
    order: list[tuple[int, str]] = []
    for i in range(1, len(parts), 2):
        segment = parts[i + 1]
        match = re.search(r"d->([a-z0-9_]+)", segment)
        if match:
            order.append((int(parts[i]), match.group(1)))
    return order


@pytest.mark.parametrize(
    "source_path", DIGIT_UART_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_digit_field_order_locked_to_contract(source_path):
    """防漂移主锁：C 侧 parse_digit_line 的 get_field 序与契约消费槽位
    （DIGIT_FRAME_CONSUMED_INDICES = 0/1/6/7 = label/confidence/cx/cy）
    一一对应，其余字段为契约占位不消费——改 C 字段序 / 契约槽位不同步即红。
    双平台 C 源同锁。"""
    source = source_path.read_text(encoding="utf-8")
    pairs = _digit_field_order(
        _parse_fn_body(source, "static void parse_digit_line(char *line, int idx)")
    )

    expected = [
        (index, DIGIT_FRAME_LINE_FIELDS[index])
        for index in DIGIT_FRAME_CONSUMED_INDICES
    ]
    assert pairs == expected


@pytest.mark.parametrize(
    "source_path", DIGIT_UART_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_digit_frame_header_locked_to_contract(source_path):
    """帧头前缀两侧一致：C 侧 line_buf[0..2] 全 '-' 判帧界，契约帧头以
    "---" 开头（改帧头前缀不同步 C 即红）。"""
    source = source_path.read_text(encoding="utf-8")
    assert (
        "line_buf[0] == '-' && line_buf[1] == '-' && line_buf[2] == '-'"
        in source
    )
    assert DIGIT_FRAME_HEADER.startswith("---")


@pytest.mark.parametrize(
    "source_path", DIGIT_UART_C_SOURCES, ids=["stm32", "mspm0"]
)
def test_c_digit_no_detect_locked_to_contract(source_path):
    """无检测帧语义两侧一致：帧头新帧重置 count=0（m=0 = 无检测）→ 空行
    帧尾结束帧（count=0 不置 updated）→ 批量最佳帧只替换 count>0 的帧
    （best_count > 0），无检测帧永不污染对端结果。"""
    source = source_path.read_text(encoding="utf-8")
    # 帧头分支重置 count=0（无检测 = 帧头 m=0 + 空行帧尾）
    assert "digit_result.count = 0" in source
    # 空行 = 帧尾
    assert "line_buf[0] == '\\0' || line_buf[0] == '\\r'" in source
    assert "in_frame = 0" in source
    # 最佳帧：count=0 不参与 → 无检测帧不替换
    assert "if (best_count > 0)" in source
    assert DIGIT_FRAME_NO_DETECT_COUNT == 0


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
    # 摘要带副产物清单（工单 04 前端「模块文件」行消费）：含 done 模板回显
    assert len(summary.python_artifacts) == 1
    artifact = summary.python_artifacts[0]
    assert artifact.slug == "k230_probe"
    assert artifact.output == "main.py"
    assert artifact.template_id == "default"


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
        if rel == "README.md":
            # README 随 manifest 集渲染（工单 project-readme/01）：probe 多选
            # 一个模块 → README 模块清单自然不同，非「既有生成文件」契约
            continue
        if rel == ".contest_context.json":
            # 上下文清单随 manifest 集渲染（工单 revise-deepen/01）：同 README
            # 语义——记录本次生成输入（slugs 含 probe），非既有生成文件契约
            continue
        if rel == "演示脚本.md":
            # 演示脚本随 manifest 集渲染（工单 report-draft-demo/01）：模块
            # 验证演示节列出全部模块，probe 多选一个 → 内容自然不同，非既有
            # 生成文件契约
            continue
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
    assert [(a.slug, a.output, a.template_id) for a in summary.python_artifacts] == [
        ("k230", "main.py", "blob")
    ]
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
    assert [(a.slug, a.output, a.template_id) for a in summary.python_artifacts] == [
        ("k230", "main.py", "blob")
    ]
    _assert_k230_output(out)


# ---------------------------------------------------------------------------
# k230-multi-template/02：模板选择请求管线（多模板探针）
# ---------------------------------------------------------------------------

K230_RECT_PROBE_TEMPLATE = (
    "# 矩形识别探针模板（测试内构造，工单 02）\n"
    "RECT_MARKER = 1\n"
    "FRAME_FORMAT = '{{coord_frame_format}}'\n"
    "NO_DETECT = '{{no_detect_frame}}'\n"
    "BAUD = {{uart_baudrate}}\n"
    "while True:\n"
    "    uart.write('R\\n')\n"
)


def _add_k230_multi_probe_module(library: Path) -> None:
    """多模板探针：blob（默认，K230_PROBE_TEMPLATE）+ rect（矩形模板）——
    两模板 output 同名 main.py（同一模块一次只渲染一个）。"""
    _add_module(
        library,
        {
            "slug": "k230_multi",
            "description": "K230 多模板链路探针（测试内构造，工单 02）",
            "dependencies": [],
            "python_artifact": {
                "default": "blob",
                "templates": [
                    {
                        "id": "blob",
                        "name": "色块追踪",
                        "description": "默认模板",
                        "template": "code/k230_probe.py",
                        "output": "main.py",
                    },
                    {
                        "id": "rect",
                        "name": "矩形识别",
                        "description": "矩形模板",
                        "template": "code/k230_rect_probe.py",
                        "output": "main.py",
                    },
                ],
            },
            "platforms": {
                "stm32": {"files": [], "verified": True},
                "mspm0": {"files": [], "verified": True},
            },
        },
        {
            "code/k230_probe.py": K230_PROBE_TEMPLATE,
            "code/k230_rect_probe.py": K230_RECT_PROBE_TEMPLATE,
        },
    )


def _multi_probe_library(tmp_path: Path) -> Path:
    library = make_fake_module_library(tmp_path / "modules")
    _add_k230_multi_probe_module(library)
    return library


def test_resolve_python_template_choices_defaults_and_valid(tmp_path):
    from contest_generator.generator import resolve_python_template_choices

    library = _multi_probe_library(tmp_path)
    manifest = ModuleManifest.load(library / "k230_multi")
    assert resolve_python_template_choices([manifest], None) == {}
    assert resolve_python_template_choices([manifest], {}) == {}
    assert resolve_python_template_choices(
        [manifest], {"k230_multi": "rect"}
    ) == {"k230_multi": "rect"}


@pytest.mark.parametrize(
    ("choices", "match"),
    [
        ({"nope": "blob"}, "不在所选模块集内"),
        ({"k230_multi": "nope"}, "不在声明模板列表"),
        ({"k230_multi": ""}, "非空字符串"),
        ({"k230_multi": 3}, "非空字符串"),
    ],
)
def test_resolve_python_template_choices_rejects(tmp_path, choices, match):
    from contest_generator.generator import resolve_python_template_choices

    library = _multi_probe_library(tmp_path)
    manifest = ModuleManifest.load(library / "k230_multi")
    with pytest.raises(PythonArtifactError, match=match):
        resolve_python_template_choices([manifest], choices)


def test_resolve_python_template_choices_rejects_non_mapping(tmp_path):
    from contest_generator.generator import resolve_python_template_choices

    library = _multi_probe_library(tmp_path)
    manifest = ModuleManifest.load(library / "k230_multi")
    with pytest.raises(PythonArtifactError, match="必须是 JSON 对象"):
        resolve_python_template_choices([manifest], ["blob"])  # type: ignore[arg-type]


def test_resolve_python_template_choices_rejects_plain_module(tmp_path):
    """未声明 python_artifact 的模块带选择 = 大声失败（不是静默忽略）。"""
    from contest_generator.generator import resolve_python_template_choices

    library = _probe_library(tmp_path)
    dht11 = ModuleManifest.load(library / "dht11")
    with pytest.raises(PythonArtifactError, match="未声明 python_artifact"):
        resolve_python_template_choices([dht11], {"dht11": "blob"})


def test_generate_selects_rect_template(tmp_path):
    """选择 rect → 渲染 rect 模板写 main.py；缺省 → 渲染 blob（default）。"""
    library = _multi_probe_library(tmp_path)
    master = make_fake_master_project(tmp_path / "master")
    manifest = ModuleManifest.load(library / "k230_multi")

    out_rect = generate(
        platform=PLATFORM_STM32,
        manifests=[manifest],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out_rect",
        main_c_content="int main(void) { while (1); }\n",
        template_choices={"k230_multi": "rect"},
    )[0]
    rect_py = (out_rect / "main.py").read_text(encoding="utf-8")
    assert "RECT_MARKER" in rect_py
    assert "find_blobs" not in rect_py
    # 帧契约占位符仍被渲染（契约单源）
    assert "B,{cx},{cy},{confidence},{x1},{y1},{x2},{y2}" in rect_py

    out_default = generate(
        platform=PLATFORM_STM32,
        manifests=[manifest],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out_default",
        main_c_content="int main(void) { while (1); }\n",
    )[0]
    assert (out_default / "main.py").read_text(encoding="utf-8") == (
        K230_PROBE_EXPECTED
    )


def test_generate_project_passes_template_choices(tmp_path):
    """流程接缝：generate_project 的 python_templates 透传（webapp 同缝）。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    library = _multi_probe_library(tmp_path)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["k230_multi"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=masters_dir,
        python_templates={"k230_multi": "rect"},
    )
    assert "RECT_MARKER" in (summary.output_dir / "main.py").read_text(
        encoding="utf-8"
    )


def test_generate_rejects_unknown_template_at_project_level(tmp_path):
    """generate_project 层非法选择在创建输出目录前大声失败（不留半成品）。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    library = _multi_probe_library(tmp_path)

    with pytest.raises(PythonArtifactError, match="不在声明模板列表"):
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["k230_multi"],
            main_c_content="int main(void) { while (1); }\n",
            output_dir=tmp_path / "out",
            module_library_dir=library,
            masters_dir=masters_dir,
            python_templates={"k230_multi": "nope"},
        )
    assert not (tmp_path / "out").exists()


# ---------------------------------------------------------------------------
# k230-multi-template/03：矩形识别模板落地（真库 k230 多模板）
# ---------------------------------------------------------------------------

K230_RECT_TEMPLATE = (
    REPO_ROOT / "library" / "modules" / "k230" / "code" / "main_rect.py"
)


def test_k230_manifest_multi_template_declared():
    """真库 k230 manifest 为多模板：blob（默认）+ rect + digit（工单
    k230-digit-vision/04），模块级依赖不变（digit 的 digit_uart 是模板级覆盖）。"""
    manifest = ModuleManifest.load(LIBRARY_MODULES / "k230")
    assert manifest.python_artifact is not None
    assert [t.id for t in manifest.python_artifact.templates] == [
        "blob", "rect", "digit",
    ]
    assert manifest.python_artifact.default_id == "blob"
    assert manifest.dependencies == ("coord_detect",)


def test_k230_rect_template_renders_contract_placeholders():
    """rect 模板渲染后帧契约与 C 侧一致（防漂移：改 C 不同步契约即红）。

    占位符渲染后 = COORD_FRAME_FORMAT / NO_DETECT_FRAME / 波特率；模板不
    重抄字面量（占位符原样存在于模板文件）。"""
    template_text = K230_RECT_TEMPLATE.read_text(encoding="utf-8")
    assert "{{coord_frame_format}}" in template_text
    assert "{{no_detect_frame}}" in template_text
    assert "{{uart_baudrate}}" in template_text
    rendered = render_python_artifact(template_text)
    assert COORD_FRAME_FORMAT in rendered
    assert NO_DETECT_FRAME in rendered
    assert str(UART_BAUDRATE) in rendered
    # 识别核心：二值化 + find_rects + corners 外接框
    for marker in ("to_grayscale", "binary", "find_rects", "corners"):
        assert marker in template_text


def test_generate_project_k230_rect_template_selected(tmp_path):
    """生成接缝：k230 选 rect 模板 → main.py 为矩形识别内容（渲染后契约一致）；
    主控侧仍挂 coord_detect（rect 无模板级依赖覆盖）、无部署包（资产是 digit
    模板专属）——旧行为基线不回归。"""
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["k230"],
        main_c_content=K230_MAIN_C_STM32,
        output_dir=tmp_path / "out",
        module_library_dir=LIBRARY_MODULES,
        masters_dir=LIBRARY_MASTERS,
        python_templates={"k230": "rect"},
    )
    py = (summary.output_dir / "main.py").read_text(encoding="utf-8")
    assert "find_rects" in py and "find_blobs" not in py
    assert COORD_FRAME_FORMAT in py  # 帧契约渲染后与主控解析一致
    assert [(a.slug, a.output, a.template_id) for a in summary.python_artifacts] == [
        ("k230", "main.py", "rect")
    ]
    # 旧行为基线：rect 继承模块级依赖 coord_detect（无 digit_uart）、无部署包
    assert (summary.output_dir / "modules" / "coord_detect" / "code" / "coord_detect_stm32.c").is_file()
    assert not (summary.output_dir / "modules" / "digit_uart").exists()
    assert not (summary.output_dir / "mp_deployment_source").exists()


# ---------------------------------------------------------------------------
# k230-digit-vision/02：模板级依赖覆盖（探针）
# ---------------------------------------------------------------------------

DEP_INHERIT_TEMPLATE = "# 继承模块级依赖探针模板\n"
DEP_OVERRIDE_TEMPLATE = "# 覆盖模板依赖探针模板\n"


def _add_deps_probe_module(library: Path) -> None:
    """模板级依赖覆盖探针：a_deps 模块级依赖 dep_base；t_inherit 模板不声明
    dependencies（继承模块级）；t_override 模板声明 dependencies=[dep_alt]
    （覆盖）。dep_base / dep_alt 为带真实文件的依赖模块（main.c 引用其 API，
    生成层断言产物含覆盖后的模块文件）。"""
    for slug, api in (("dep_base", "dep_base_use"), ("dep_alt", "dep_alt_use")):
        _add_module(
            library,
            {
                "slug": slug,
                "description": f"{slug}（模板级依赖探针，测试内构造）",
                "dependencies": [],
                "platforms": {
                    "stm32": {
                        "files": [f"code/{slug}.c", f"code/{slug}.h"],
                        "verified": True,
                    },
                    "mspm0": {"files": [], "verified": True},
                },
            },
            {
                f"code/{slug}.c": f'#include "{slug}.h"\nvoid {api}(void) {{}}\n',
                f"code/{slug}.h": f"#pragma once\nvoid {api}(void);\n",
            },
        )
    _add_module(
        library,
        {
            "slug": "a_deps",
            "description": "模板级依赖覆盖探针（测试内构造，工单 02）",
            "dependencies": ["dep_base"],
            "python_artifact": {
                "default": "t_inherit",
                "templates": [
                    {
                        "id": "t_inherit",
                        "name": "继承依赖",
                        "description": "不声明 dependencies = 继承模块级",
                        "template": "code/dep_inherit.py",
                        "output": "main.py",
                    },
                    {
                        "id": "t_override",
                        "name": "覆盖依赖",
                        "description": "声明 dependencies = 覆盖模块级",
                        "template": "code/dep_override.py",
                        "output": "main.py",
                        "dependencies": ["dep_alt"],
                    },
                ],
            },
            "platforms": {
                "stm32": {"files": [], "verified": True},
                "mspm0": {"files": [], "verified": True},
            },
        },
        {
            "code/dep_inherit.py": DEP_INHERIT_TEMPLATE,
            "code/dep_override.py": DEP_OVERRIDE_TEMPLATE,
        },
    )


def _deps_probe_library(tmp_path: Path) -> Path:
    library = make_fake_module_library(tmp_path / "modules")
    _add_deps_probe_module(library)
    return library


def test_template_dependencies_parse_and_serialize(tmp_path):
    """模板 dependencies 解析：缺省 = None（序列化不落键，旧形状逐字节不变）；
    声明 = 元组；to_dict 往返键集合稳定。"""
    library = _deps_probe_library(tmp_path)
    manifest = ModuleManifest.load(library / "a_deps")
    templates = {t.id: t for t in manifest.python_artifact.templates}
    assert templates["t_inherit"].dependencies is None
    assert templates["t_override"].dependencies == ("dep_alt",)
    # 序列化：None 不落键 / 覆盖落键（默认模板 t_inherit 无键）
    data = manifest.python_artifact.to_dict()
    by_id = {item["id"]: item for item in data["templates"]}
    assert "dependencies" not in by_id["t_inherit"]
    assert by_id["t_override"]["dependencies"] == ["dep_alt"]


@pytest.mark.parametrize(
    "bad",
    ["dep_alt", 1, [], ["dep_alt", ""], [1]],
)
def test_template_dependencies_invalid_rejected(tmp_path, bad):
    """模板 dependencies 类型非法（非字符串数组 / 空数组 / 含空串）→
    ManifestError，不静默容忍——坏值会静默错位依赖展开，[] 会静默清空
    模块依赖（语义黑洞）。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_module(
        library,
        {
            "slug": "bad_deps",
            "description": "坏依赖模板（测试内构造）",
            "dependencies": [],
            "python_artifact": {
                "default": "t",
                "templates": [
                    {
                        "id": "t",
                        "name": "坏",
                        "description": "dependencies 非法",
                        "template": "code/t.py",
                        "output": "main.py",
                        "dependencies": bad,
                    }
                ],
            },
            "platforms": {"stm32": {"files": [], "verified": True}},
        },
        {"code/t.py": "# bad\n"},
    )
    with pytest.raises(ManifestError, match="dependencies"):
        ModuleManifest.load(library / "bad_deps")


def test_resolve_selection_template_deps_override(tmp_path):
    """选中不同模板 → 依赖展开按覆盖走：t_override → [dep_alt, a_deps]；
    t_inherit / 缺省 → [dep_base, a_deps]（模块级保持不变）。"""
    library = _deps_probe_library(tmp_path)

    overridden = resolve_selection(
        library, PLATFORM_STM32, ["a_deps"],
        python_templates={"a_deps": "t_override"},
    )
    assert [m.slug for m in overridden.manifests] == ["dep_alt", "a_deps"]

    inherited = resolve_selection(
        library, PLATFORM_STM32, ["a_deps"],
        python_templates={"a_deps": "t_inherit"},
    )
    assert [m.slug for m in inherited.manifests] == ["dep_base", "a_deps"]

    default = resolve_selection(library, PLATFORM_STM32, ["a_deps"])
    assert [m.slug for m in default.manifests] == ["dep_base", "a_deps"]


def test_list_modules_rejects_phantom_template_dep(tmp_path):
    """库级校验补漏（工单 02）：模板 dependencies 里悬空 slug 在库加载时
    大声失败——生成期只校验选中模板，未选中模板的悬空依赖在加载层拦截
    （与 collect_exclusive_groups 同风格的库错误）。"""
    from contest_generator.library import LibraryError, list_modules

    library = make_fake_module_library(tmp_path / "modules")
    _add_module(
        library,
        {
            "slug": "a_bad",
            "description": "未知依赖模板（测试内构造）",
            "dependencies": [],
            "python_artifact": {
                "default": "t",
                "templates": [
                    {
                        "id": "t",
                        "name": "坏",
                        "description": "依赖指向库外",
                        "template": "code/t.py",
                        "output": "main.py",
                        "dependencies": ["ghost"],
                    }
                ],
            },
            "platforms": {"stm32": {"files": [], "verified": True}},
        },
        {"code/t.py": "# bad\n"},
    )
    with pytest.raises(LibraryError, match="ghost"):
        list_modules(library)


def test_resolve_selection_template_deps_cycle(tmp_path):
    """模板覆盖依赖成环 → DependencyCycleError（覆盖表与模块级同一环检测）。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_module(
        library,
        {
            "slug": "a_cycle",
            "description": "成环模板（测试内构造）",
            "dependencies": [],
            "python_artifact": {
                "default": "t",
                "templates": [
                    {
                        "id": "t",
                        "name": "坏",
                        "description": "依赖指向自身",
                        "template": "code/t.py",
                        "output": "main.py",
                        "dependencies": ["a_cycle"],
                    }
                ],
            },
            "platforms": {"stm32": {"files": [], "verified": True}},
        },
        {"code/t.py": "# bad\n"},
    )
    with pytest.raises(DependencyCycleError, match="成环"):
        resolve_selection(
            library, PLATFORM_STM32, ["a_cycle"],
            python_templates={"a_cycle": "t"},
        )


def test_generate_project_template_deps_overrides_expansion(tmp_path):
    """流程接缝：generate_project 的 python_templates 依赖覆盖进生成产物——
    选中 t_override → 产物含 dep_alt 模块文件、无 dep_base（与 webapp 同缝）。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    library = _deps_probe_library(tmp_path)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["a_deps"],
        main_c_content=(
            '#include "dep_alt.h"\n'
            "int main(void) { dep_alt_use(); while (1); }\n"
        ),
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=masters_dir,
        python_templates={"a_deps": "t_override"},
    )
    # 覆盖生效：产物含 dep_alt 模块文件、无 dep_base
    assert (summary.output_dir / "modules" / "dep_alt" / "code" / "dep_alt.c").is_file()
    assert (summary.output_dir / "modules" / "dep_alt" / "code" / "dep_alt.h").is_file()
    assert not (summary.output_dir / "modules" / "dep_base").exists()
    assert (summary.output_dir / "main.py").is_file()
    assert [(a.slug, a.output, a.template_id) for a in summary.python_artifacts] == [
        ("a_deps", "main.py", "t_override")
    ]


def test_generate_project_rejects_non_mapping_templates(tmp_path):
    """生成层形状校验：python_templates 非 JSON 对象（列表）→
    PythonArtifactError 400 中文——resolve_selection 防御不崩（无覆盖展开），
    校验归 resolve_python_template_choices（不回归成 500 AttributeError）。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    library = _deps_probe_library(tmp_path)

    with pytest.raises(PythonArtifactError, match="必须是 JSON 对象"):
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["a_deps"],
            main_c_content="int main(void) { while (1); }\n",
            output_dir=tmp_path / "out",
            module_library_dir=library,
            masters_dir=masters_dir,
            python_templates=["bad"],  # type: ignore[arg-type]
        )
    assert not (tmp_path / "out").exists()  # 校验失败在创建输出目录之前


# ---------------------------------------------------------------------------
# k230-digit-vision/03：静态资产分发（探针）
# ---------------------------------------------------------------------------

FAKE_KMODEL_BYTES = b"\x00\x01fake-kmodel-payload\xff\xfe"  # 二进制假资产
ASSET_PROBE_MAIN = "# 资产探针模板（测试内构造，工单 03）\nASSET = 1\n"
ASSET_PROBE_DEPLOY = '{"chip_type": "k230", "confidence_threshold": 0.4}\n'


def _add_asset_probe_module(
    library: Path,
    slug: str,
    assets: list[dict],
    present: dict[str, str] | None = None,
    output: str = "main.py",
) -> None:
    """资产探针模块：单模板 + assets 声明；present = 真实存在的资产文件。"""
    _add_module(
        library,
        {
            "slug": slug,
            "description": f"{slug}（资产分发探针，测试内构造）",
            "dependencies": [],
            "python_artifact": {
                "default": "default",
                "templates": [
                    {
                        "id": "default",
                        "name": "默认",
                        "description": "资产探针模板",
                        "template": "code/main.py",
                        "output": output,
                        "assets": assets,
                    }
                ],
            },
            "platforms": {
                "stm32": {"files": [], "verified": True},
                "mspm0": {"files": [], "verified": True},
            },
        },
        {
            "code/main.py": ASSET_PROBE_MAIN,
            **(present or {}),
        },
    )


def test_legacy_single_template_serialization_byte_identical(tmp_path):
    """旧行为回归锁：无增强字段（dependencies/assets）的单模板序列化回
    旧形状逐字节不变（{template, output}）——增强字段单模板走新形状（03
    修复 to_dict 旧形状分支丢增强字段的潜伏洞）。"""
    library = _probe_library(tmp_path)
    manifest = ModuleManifest.load(library / "k230_probe")
    assert manifest.python_artifact.to_dict() == {
        "template": "code/k230_probe.py",
        "output": "main.py",
    }


def test_template_assets_parse_and_serialize(tmp_path):
    """模板 assets 解析：缺省 = 空；{src, dst} 对解析成 AssetSpec；序列化
    落键 / 不落键（旧 manifest 逐字节不变）。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_asset_probe_module(
        library,
        "a_asset",
        [{"src": "code/model.kmodel", "dst": "mp_deployment_source/model.kmodel"}],
        {"code/model.kmodel": "# fake\n"},
    )
    manifest = ModuleManifest.load(library / "a_asset")
    template = manifest.python_artifact.templates[0]
    assert template.assets == (
        AssetSpec(
            src="code/model.kmodel",
            dst="mp_deployment_source/model.kmodel",
        ),
    )
    data = manifest.python_artifact.to_dict()
    assert data["templates"][0]["assets"] == [
        {"src": "code/model.kmodel", "dst": "mp_deployment_source/model.kmodel"}
    ]
    # 无资产模板序列化不落键（_deps_probe_library 的 t_override）
    deps_library = _deps_probe_library(tmp_path / "deps_modules")
    deps_manifest = ModuleManifest.load(deps_library / "a_deps")
    deps_data = deps_manifest.python_artifact.to_dict()
    for item in deps_data["templates"]:
        assert "assets" not in item


@pytest.mark.parametrize(
    ("assets", "match"),
    [
        ([{"src": "", "dst": "a.bin"}], "src 必须是非空字符串"),
        ([{"src": "a.bin", "dst": ""}], "dst 必须是非空字符串"),
        ([{"src": "../outside.bin", "dst": "a.bin"}], "相对且无 \\.\\."),
        ([{"src": "a.bin", "dst": "../up.bin"}], "相对且无 \\.\\."),
        ([{"src": ".", "dst": "a.bin"}], "相对且无 \\.\\."),
        ([{"src": "a.bin", "dst": "."}], "相对且无 \\.\\."),
        (["not-a-dict"], "必须是对象"),
    ],
)
def test_template_assets_invalid_rejected(tmp_path, assets, match):
    """资产声明非法（空 src/dst、越界 ..、非对象）→ ManifestError 大声失败。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_asset_probe_module(library, "bad_asset", assets, {"code/a.bin": "# x\n"})
    with pytest.raises(ManifestError, match=match):
        ModuleManifest.load(library / "bad_asset")


def test_generate_template_assets_copied_byte_identical(tmp_path):
    """生成接缝：模板 assets → 逐字节复制到工程根 dst（含子目录）；摘要
    python_artifacts 列出资产路径。"""
    library = _asset_probe_library(tmp_path)
    master = make_fake_master_project(tmp_path / "master")
    manifest = ModuleManifest.load(library / "a_asset")

    out = generate(
        platform=PLATFORM_STM32,
        manifests=[manifest],
        module_library_dir=library,
        master_project_dir=master,
        output_dir=tmp_path / "out",
        main_c_content="int main(void) { while (1); }\n",
    )[0]

    kmodel = out / "mp_deployment_source" / "model.kmodel"
    assert kmodel.read_bytes() == FAKE_KMODEL_BYTES  # 逐字节（含二进制）
    deploy = out / "mp_deployment_source" / "deploy_config.json"
    assert deploy.read_text(encoding="utf-8") == ASSET_PROBE_DEPLOY
    assert (out / "main.py").is_file()
    assert not (out / "modules" / "a_asset").exists()  # files 空 = 无 C 子树
    # 摘要（generate 直调无 summary；断言走 generate 前的 Describe 请见
    # generate_project 集成测试——此处直接验证产物字节）


def test_generate_project_assets_in_summary(tmp_path):
    """流程接缝：generate_project 摘要 python_artifacts 含资产 dst 列表。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    library = _asset_probe_library(tmp_path)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["a_asset"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=masters_dir,
    )
    assert [a.asset_paths for a in summary.python_artifacts] == [
        (
            "mp_deployment_source/model.kmodel",
            "mp_deployment_source/deploy_config.json",
        )
    ]
    assert not (summary.output_dir / "modules" / "a_asset").exists()


def test_generate_template_asset_missing_fails_cleanly(tmp_path):
    """声明了资产但文件缺失 → 大声失败点名模块与资产路径，输出目录被清。"""
    library = _asset_probe_library(tmp_path)
    master = make_fake_master_project(tmp_path / "master")
    manifest = ModuleManifest.load(library / "a_asset")
    # 移除资产源文件后重新生成
    (library / "a_asset" / "code" / "model.kmodel").unlink()

    with pytest.raises(PythonArtifactError, match="资产缺失"):
        generate(
            platform=PLATFORM_STM32,
            manifests=[manifest],
            module_library_dir=library,
            master_project_dir=master,
            output_dir=tmp_path / "out",
            main_c_content="int main(void) { while (1); }\n",
        )
    assert not (tmp_path / "out").exists()  # 不留半成品


def test_generate_template_asset_dst_clashes_project_file(tmp_path):
    """资产 dst 撞工程既有文件（母版 main.c）→ 大声失败，不静默覆盖。"""
    library = _asset_probe_library(tmp_path)
    # 覆盖 manifest 的资产 dst 指向 main.c（母版既有文件）
    manifest_path = library / "a_asset" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["python_artifact"]["templates"][0]["assets"] = [
        {"src": "code/model.kmodel", "dst": "main.c"}
    ]
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    master = make_fake_master_project(tmp_path / "master")
    manifest = ModuleManifest.load(library / "a_asset")

    with pytest.raises(PythonArtifactError, match="与工程既有文件同名"):
        generate(
            platform=PLATFORM_STM32,
            manifests=[manifest],
            module_library_dir=library,
            master_project_dir=master,
            output_dir=tmp_path / "out",
            main_c_content="int main(void) { while (1); }\n",
        )
    assert not (tmp_path / "out").exists()


def test_generate_asset_dst_cross_module_conflict(tmp_path):
    """跨模板同名资产 dst → 大声失败（同 output 检查同款语义）。"""
    library = make_fake_module_library(tmp_path / "modules")
    shared = [{"src": "code/model.kmodel", "dst": "mp_deployment_source/model.kmodel"}]
    _add_asset_probe_module(
        library, "asset_a", shared, {"code/model.kmodel": "# a\n"}
    )
    _add_asset_probe_module(
        library, "asset_b", shared, {"code/model.kmodel": "# b\n"},
        output="main_b.py",
    )
    master = make_fake_master_project(tmp_path / "master")
    manifests = [
        ModuleManifest.load(library / slug) for slug in ("asset_a", "asset_b")
    ]

    with pytest.raises(PythonArtifactError, match="资产同名"):
        generate(
            platform=PLATFORM_STM32,
            manifests=manifests,
            module_library_dir=library,
            master_project_dir=master,
            output_dir=tmp_path / "out",
            main_c_content="int main(void) { while (1); }\n",
        )
    assert not (tmp_path / "out").exists()


def _asset_probe_library(tmp_path: Path) -> Path:
    library = make_fake_module_library(tmp_path / "modules")
    _add_asset_probe_module(
        library,
        "a_asset",
        [
            {"src": "code/model.kmodel", "dst": "mp_deployment_source/model.kmodel"},
            {"src": "code/deploy.json", "dst": "mp_deployment_source/deploy_config.json"},
        ],
        {"code/deploy.json": ASSET_PROBE_DEPLOY},
    )
    # 二进制假资产绕过 _add_module 的文本管道（write_text），直接写字节
    (library / "a_asset" / "code" / "model.kmodel").write_bytes(FAKE_KMODEL_BYTES)
    return library


# ---------------------------------------------------------------------------
# k230-digit-vision/04：数字识别模板落地（真库 k230 + digit）
# ---------------------------------------------------------------------------

K230_DIGIT_TEMPLATE = (
    REPO_ROOT / "library" / "modules" / "k230" / "code" / "main_digit.py"
)
K230_DIGIT_KMODEL = (
    REPO_ROOT / "library" / "modules" / "k230" / "assets" / "digit8_anchorbase_320.kmodel"
)
K230_DIGIT_DEPLOY = (
    REPO_ROOT / "library" / "modules" / "k230" / "assets" / "deploy_config.json"
)

# 生成层 main.c：只调 digit_uart 的 API（digit 模板的模板级依赖自动挂 digit_uart）
K230_MAIN_C_DIGIT_STM32 = (
    '#include "headfile.h"\n'
    '#include "digit_uart.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    digit_uart_init();\n"
    "    while (1)\n"
    "    {\n"
    "        digit_uart_parse();\n"
    "    }\n"
    "}\n"
)

K230_MAIN_C_DIGIT_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "digit_uart_mspm0.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    digit_uart_init();\n"
    "    while (1)\n"
    "    {\n"
    "        digit_uart_parse();\n"
    "    }\n"
    "}\n"
    "\n"
    "void DIGIT_UART_INST_IRQHandler(void)\n"
    "{\n"
    "    digit_uart_rx_handler();\n"
    "}\n"
)


def test_k230_manifest_digit_template_declared():
    """真库 k230 manifest：templates 含 digit——模板级依赖覆盖 digit_uart
    （blob/rect 零改动：继承模块级 coord_detect）+ assets 部署包两件。"""
    manifest = ModuleManifest.load(LIBRARY_MODULES / "k230")
    specs = {t.id: t for t in manifest.python_artifact.templates}
    assert set(specs) == {"blob", "rect", "digit"}
    digit = specs["digit"]
    assert digit.dependencies == ("digit_uart",)
    assert digit.assets == (
        AssetSpec(
            src="assets/digit8_anchorbase_320.kmodel",
            dst="mp_deployment_source/digit8_anchorbase_320.kmodel",
        ),
        AssetSpec(
            src="assets/deploy_config.json",
            dst="mp_deployment_source/deploy_config.json",
        ),
    )
    # blob/rect 条目零改动：无模板级依赖（继承模块级）、无资产
    assert specs["blob"].dependencies is None and specs["blob"].assets == ()
    assert specs["rect"].dependencies is None and specs["rect"].assets == ()


def test_k230_digit_template_renders_contract_placeholders():
    """digit 模板渲染后 DIGIT 帧契约与主控解析一致（防漂移：改契约/C 侧
    不同步即红）。模板只走占位符不重抄字面量。"""
    template_text = K230_DIGIT_TEMPLATE.read_text(encoding="utf-8")
    assert "{{digit_frame_header}}" in template_text
    assert "{{digit_frame_line}}" in template_text
    assert "{{uart_baudrate}}" in template_text
    rendered = render_python_artifact(template_text)
    assert DIGIT_FRAME_HEADER in rendered
    assert DIGIT_FRAME_LINE_FORMAT in rendered
    assert str(UART_BAUDRATE) in rendered
    # 推理管线素材（21F 例程形态）
    for marker in ("DetectionApp", "PipeLine", "read_json", "det_app.run"):
        assert marker in template_text


def test_generate_project_k230_digit_selected_stm32(tmp_path):
    """生成接缝：k230 选 digit → main.py 渲染后契约一致 + mp_deployment_source
    部署包（kmodel 字节大小 + 配置内容）+ 主控挂 digit_uart 不含 coord_detect
    + 摘要 asset_paths + README 产物清单行。"""
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["k230"],
        main_c_content=K230_MAIN_C_DIGIT_STM32,
        output_dir=tmp_path / "out",
        module_library_dir=LIBRARY_MODULES,
        masters_dir=LIBRARY_MASTERS,
        python_templates={"k230": "digit"},
    )
    out = summary.output_dir
    # main.py = 渲染后模板（契约占位符已注入）
    assert (out / "main.py").read_text(encoding="utf-8") == render_python_artifact(
        K230_DIGIT_TEMPLATE.read_text(encoding="utf-8")
    )
    # 部署包：kmodel 逐字节一致（7,596,008 字节）+ 配置内容（kmodel_path 指向新名）
    kmodel = out / "mp_deployment_source" / "digit8_anchorbase_320.kmodel"
    assert kmodel.read_bytes() == K230_DIGIT_KMODEL.read_bytes()
    assert kmodel.stat().st_size == 7_596_008
    deploy = json.loads(
        (out / "mp_deployment_source" / "deploy_config.json").read_text(encoding="utf-8")
    )
    assert deploy["kmodel_path"] == "digit8_anchorbase_320.kmodel"
    assert deploy["categories"] == [str(i) for i in range(1, 9)]
    assert deploy["confidence_threshold"] == 0.4
    # 模板级依赖覆盖生效：digit_uart 挂上（stm32 版），coord_detect 不出现
    assert (out / "modules" / "digit_uart" / "code" / "digit_uart.c").is_file()
    assert (out / "modules" / "digit_uart" / "code" / "digit_uart.h").is_file()
    assert not (out / "modules" / "coord_detect").exists()
    # 摘要：模板回显 digit + 资产路径列表
    assert [(a.slug, a.output, a.template_id) for a in summary.python_artifacts] == [
        ("k230", "main.py", "digit")
    ]
    assert summary.python_artifacts[0].asset_paths == (
        "mp_deployment_source/digit8_anchorbase_320.kmodel",
        "mp_deployment_source/deploy_config.json",
    )
    # README 产物清单含部署包行
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "mp_deployment_source/" in readme


def test_generate_project_k230_digit_selected_mspm0(tmp_path):
    """mspm0 对端：digit_uart_mspm0 挂上 + DIGIT_UART 共享实例在 syscfg（与
    coord_detect 同实例——digit 选中时由 digit_uart 提供）+ 部署包照复制。"""
    summary = generate_project(
        platform=PLATFORM_MSPM0,
        slugs=["k230"],
        main_c_content=K230_MAIN_C_DIGIT_MSPM0,
        output_dir=tmp_path / "out",
        module_library_dir=LIBRARY_MODULES,
        masters_dir=LIBRARY_MASTERS,
        python_templates={"k230": "digit"},
    )
    out = summary.output_dir
    assert (out / "modules" / "digit_uart" / "code" / "digit_uart_mspm0.c").is_file()
    assert not (out / "modules" / "coord_detect").exists()
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const DIGIT_UART = UART.addInstance();" in syscfg
    assert (out / "mp_deployment_source" / "digit8_anchorbase_320.kmodel").is_file()
    assert [(a.slug, a.output, a.template_id) for a in summary.python_artifacts] == [
        ("k230", "main.py", "digit")
    ]


def test_generate_project_k230_blob_has_no_deploy_package(tmp_path):
    """缺省/选 blob → 无部署包（digit 模板专属 assets），与既有 blob 基线
    逐字节一致（asset 分发不动无资产模板的产物形状）。"""
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["k230"],
        main_c_content=K230_MAIN_C_STM32,
        output_dir=tmp_path / "out",
        module_library_dir=LIBRARY_MODULES,
        masters_dir=LIBRARY_MASTERS,
    )
    out = summary.output_dir
    assert not (out / "mp_deployment_source").exists()
    assert (out / "modules" / "coord_detect" / "code" / "coord_detect_stm32.c").is_file()
    assert summary.python_artifacts[0].asset_paths == ()
