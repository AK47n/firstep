"""上下文清单（工单 revise-deepen/01）：写侧落盘 / 读侧兼容 / 历史目录反推 /
加载 API 的测试。

只测外部行为：清单字段落盘与回读、缺字段兼容、反推回读一致性、形状校验
（400 中文）、加载 API 两条路径（有清单直读 / 无清单反推）。反推素材 =
假模块库 + 假母版（fakes.py 先例），绑定回读用真实板数据（boards 包内静态
数据）做写侧逆运算断言。
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from contest_generator.context_manifest import (
    CONTEXT_MANIFEST_FILENAME,
    ContextError,
    build_context_fields,
    infer_context,
    read_context_fields,
    validate_context_fields,
    write_context_manifest,
)
from contest_generator.generator import generate_project
from contest_generator.manifest import ModuleManifest
from contest_generator.pin_bindings import resolve_bindings
from contest_generator.pinwriter import render_pin_config
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.webapp import AppContext, AppConfig, create_app
from tests.fakes import (
    MAIN_SKELETON,
    make_fake_ccs_theia_master_project,
    make_fake_master_project,
    make_fake_module_library,
    make_fake_stm32_ml_master,
)

# 自造带引脚角色的 stm32 模块（母版 pin_config.h 有 MOTOR_A_PWM 宏，
# 与真实 motor 模块同构：引脚走宏；files 非空 → 产物树有 modules/<slug>/ 可反推）
MOTOR_MANIFEST = {
    "slug": "mymotor",
    "description": "测试用电机模块",
    "dependencies": [],
    "platforms": {
        "stm32": {
            "files": ["code/motor.c", "code/motor.h"],
            "verified": True,
            "pins": [
                {
                    "id": "MOTOR_A_PWM",
                    "type": "pwm",
                    "default": "PA0",
                    "macros": ["MOTOR_A_PWM_TIM", "MOTOR_A_PWM_CH"],
                }
            ],
        }
    },
}

MOTOR_FILES = {
    "code/motor.c": '#include "motor.h"\n/* motor */\nvoid motor_init(void);\n',
    "code/motor.h": "#pragma once\nvoid motor_init(void);\n",
}

# 带 MOTOR_A_PWM 宏的 pin_config.h（母版默认：PA0 → TIM_2/TIM2_CH1）
MOTOR_PIN_CONFIG_H = (
    "#ifndef __PIN_CONFIG_H\n#define __PIN_CONFIG_H\n"
    "#define MOTOR_A_PWM_TIM TIM_2\n#define MOTOR_A_PWM_CH TIM2_CH1\n"
    "#endif\n"
)

# 自造 mspm0 模块（slug = led，落在 syscfg 实例消费表内——prune 保留
# LED_BEEP 实例；gpio_out 角色，真实 led 形态）
LED_MANIFEST = {
    "slug": "led",
    "description": "测试用 LED 模块",
    "dependencies": [],
    "platforms": {
        "mspm0": {
            "files": ["code/led.c", "code/led.h"],
            "verified": True,
            "pins": [
                {"id": "LED", "type": "gpio_out", "default": "PA15", "required": True}
            ],
        }
    },
}

LED_FILES = {
    "code/led.c": '#include "led.h"\n/* led */\nvoid led_init(void);\n',
    "code/led.h": "#pragma once\nvoid led_init(void);\n",
}

# 带 LED_BEEP 实例与 $assign 落点的 syscfg（真实母版同构：GPIO.addInstance +
# associatedPins[n].pin.$assign）
MSPM0_SYSCFG = (
    '//@cliArgs --device "MSPM0G350X" --package "LQFP-64(PM)" --part "Default"\n'
    "\n"
    'const SYSCTL = scripting.addModule("/ti/driverlib/SYSCTL");\n'
    "\n"
    "const LED_BEEP = GPIO.addInstance();\n"
    'LED_BEEP.associatedPins[0].pin.$assign  = "PA15";\n'
    "\n"
)


def _add_library_module(library_dir, manifest: dict, files: dict[str, str]) -> None:
    """向假模块库补一个模块（与 fakes._add_module 同构，测试内联素材）。"""
    (library_dir / manifest["slug"]).mkdir(parents=True, exist_ok=True)
    (library_dir / manifest["slug"] / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    for rel, text in files.items():
        path = library_dir / manifest["slug"] / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _make_motor_library(tmp_path) -> tuple:
    """假模块库 + 带 MOTOR_A_PWM 宏的 stm32 母版（反推绑定素材）。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_library_module(library, MOTOR_MANIFEST, MOTOR_FILES)
    master = make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    (master / "pin_config.h").write_text(MOTOR_PIN_CONFIG_H, encoding="utf-8")
    return library, master


def _make_led_library(tmp_path) -> tuple:
    """假模块库 + 带 LED_BEEP 落点的 mspm0 母版（反推绑定素材）。"""
    library = make_fake_module_library(tmp_path / "modules")
    _add_library_module(library, LED_MANIFEST, LED_FILES)
    master = make_fake_ccs_theia_master_project(tmp_path / "masters" / PLATFORM_MSPM0)
    (master / "mspm0.syscfg").write_text(MSPM0_SYSCFG, encoding="utf-8")
    return library, master


# ---------------------------------------------------------------------------
# 写侧：生成尾部落盘
# ---------------------------------------------------------------------------


def test_generate_writes_context_manifest_with_all_fields(tmp_path):
    """生成带全上下文字段 → .contest_context.json 落盘，字段 roundtrip。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        problem_text="2024 巡线小车赛题",
        topic_id="2024H",
        qa_text="可以复用上一届的电机模块",
        requirements=[
            {"requirement": "循迹", "sentence": 1, "modules": ["dht11"], "suggestions": []}
        ],
        references=["car-1-1"],
        tool_version="0.1.0-test",
    )
    path = summary.output_dir / CONTEXT_MANIFEST_FILENAME
    assert path.is_file()
    fields = json.loads(path.read_text(encoding="utf-8"))
    assert fields["version"] == 1
    assert fields["platform"] == PLATFORM_STM32
    assert fields["slugs"] == ["delay", "dht11", "oled"]  # 依赖展开后序
    assert fields["main_c"] == MAIN_SKELETON
    assert fields["problem_text"] == "2024 巡线小车赛题"
    assert fields["topic_id"] == "2024H"
    assert fields["qa_text"] == "可以复用上一届的电机模块"
    assert fields["requirements"] == [
        {"requirement": "循迹", "sentence": 1, "modules": ["dht11"], "suggestions": []}
    ]
    assert fields["references"] == ["car-1-1"]
    assert fields["tool_version"] == "0.1.0-test"
    assert fields["generated_at"]


def test_generate_default_manifest_has_empty_optional_fields(tmp_path):
    """缺省路径（不带上下文字段）：清单内容缺省（空串/空集），生成仍成功。"""
    library = make_fake_module_library(tmp_path / "modules")
    master = make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
    )
    fields = json.loads(
        (summary.output_dir / CONTEXT_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert fields["problem_text"] == ""
    assert fields["qa_text"] == ""
    assert fields["requirements"] == []
    assert fields["references"] == []
    assert fields["bindings"] == {}
    # 既有母版文件逐字节保留（清单写侧不触碰任何既有生成文件——main.c /
    # README / uvprojx 是骨架替换与 patcher/渲染器各自契约内改动，其余母版
    # 文件原样）
    for p in master.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.name in ("main.c", "project.uvprojx"):
            continue
        rel = p.relative_to(master)
        assert (summary.output_dir / rel).read_bytes() == p.read_bytes(), rel
    # 清单之外的所有生成文件与第二次生成逐字节一致（确定性 + 无副作用）
    first = {
        p.relative_to(summary.output_dir).as_posix(): p.read_bytes()
        for p in summary.output_dir.rglob("*")
        if p.is_file() and p.name != CONTEXT_MANIFEST_FILENAME
    }
    second = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out2",
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
    )
    second_files = {
        p.relative_to(second.output_dir).as_posix(): p.read_bytes()
        for p in second.output_dir.rglob("*")
        if p.is_file() and p.name != CONTEXT_MANIFEST_FILENAME
    }
    assert second_files == first


# ---------------------------------------------------------------------------
# 读侧：roundtrip / 缺字段兼容 / 坏 JSON
# ---------------------------------------------------------------------------


def test_read_context_fields_roundtrip(tmp_path):
    """build → write → read：字段一致（除 generated_at 由写侧生成）。"""
    fields = build_context_fields(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c="int main(void) {}\n",
        problem_text="题面",
        qa_text="答疑",
        requirements=[{"requirement": "R", "sentence": 1}],
        bindings={"dht11.DHT11": "PA1"},
    )
    out = tmp_path / "out"
    out.mkdir()
    write_context_manifest(out, fields)
    read = read_context_fields(out)
    assert read is not None
    for key in (
        "platform", "slugs", "main_c", "problem_text", "qa_text",
        "requirements", "bindings", "instances", "python_templates",
        "references", "tool_version",
    ):
        assert read[key] == fields[key], key
    assert read["generated_at"]


def test_read_context_fields_tolerates_missing_keys(tmp_path):
    """旧版本 / 缺字段清单：读侧补空不崩（向后兼容）。"""
    out = tmp_path / "out"
    out.mkdir()
    (out / CONTEXT_MANIFEST_FILENAME).write_text(
        json.dumps({"platform": "stm32", "slugs": ["dht11"]}), encoding="utf-8"
    )
    fields = read_context_fields(out)
    assert fields["platform"] == "stm32"
    assert fields["slugs"] == ["dht11"]
    assert fields["problem_text"] == ""
    assert fields["bindings"] == {}
    assert fields["requirements"] == []
    assert fields["main_c"] == ""


def test_read_context_fields_none_without_manifest(tmp_path):
    """无清单目录 → 读侧返回 None（调用方走反推路径）。"""
    assert read_context_fields(tmp_path) is None


def test_read_context_fields_bad_json_raises(tmp_path):
    """清单损坏（非 JSON）→ ContextError（400 中文，不静默吞）。"""
    out = tmp_path / "out"
    out.mkdir()
    (out / CONTEXT_MANIFEST_FILENAME).write_text("{not json", encoding="utf-8")
    with pytest.raises(ContextError):
        read_context_fields(out)


# ---------------------------------------------------------------------------
# 反推：平台 / 模块 / 绑定 / main.c（无清单历史目录）
# ---------------------------------------------------------------------------


def test_infer_context_stm32_reads_back_bindings(tmp_path):
    """stm32 生成（带绑定）→ 删清单 → 反推回读平台/模块/绑定/main.c。"""
    library, master = _make_motor_library(tmp_path)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["mymotor"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        bindings={"mymotor.MOTOR_A_PWM": "PA6"},
    )
    # 写侧确实把 PA0 → PA6 写进 pin_config.h（TIM_2/TIM2_CH1 → TIM_3/TIM3_CH1）
    pin_config = (summary.output_dir / "pin_config.h").read_text(encoding="utf-8")
    assert "#define MOTOR_A_PWM_TIM TIM_3" in pin_config
    assert "#define MOTOR_A_PWM_CH TIM3_CH1" in pin_config
    # 删清单 → 走反推
    (summary.output_dir / CONTEXT_MANIFEST_FILENAME).unlink()
    fields, missing = infer_context(summary.output_dir, library)
    assert fields["platform"] == PLATFORM_STM32
    assert fields["slugs"] == ["mymotor"]
    assert fields["bindings"] == {"mymotor.MOTOR_A_PWM": "PA6"}
    assert fields["main_c"] == "int main(void) { while (1); }\n"
    assert "problem_text" in missing
    assert "main_c" not in missing  # main.c 现读成功


def test_infer_context_stm32_default_bindings_omitted(tmp_path):
    """默认绑定（未覆盖）：反推载荷省略该角色（写侧 no-op 语义对偶）。"""
    library, master = _make_motor_library(tmp_path)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["mymotor"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
    )
    (summary.output_dir / CONTEXT_MANIFEST_FILENAME).unlink()
    fields, _ = infer_context(summary.output_dir, library)
    assert fields["bindings"] == {}


def test_infer_context_mspm0_reads_back_bindings(tmp_path):
    """mspm0 生成（带绑定）→ 删清单 → 反推回读 syscfg $assign 落点值。"""
    library, master = _make_led_library(tmp_path)
    summary = generate_project(
        platform=PLATFORM_MSPM0,
        slugs=["led"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        bindings={"led.LED": "PA22"},
    )
    syscfg = (summary.output_dir / "mspm0.syscfg").read_text(encoding="utf-8")
    assert '"PA22"' in syscfg  # 写侧把 PA15 → PA22
    (summary.output_dir / CONTEXT_MANIFEST_FILENAME).unlink()
    fields, _ = infer_context(summary.output_dir, library)
    assert fields["platform"] == PLATFORM_MSPM0
    assert fields["slugs"] == ["led"]
    assert fields["bindings"] == {"led.LED": "PA22"}


def test_infer_context_platform_unrecognized_raises(tmp_path):
    """没有工程配置文件的目录 → ContextError（400 中文，无兜底路径）。"""
    out = tmp_path / "out"
    out.mkdir()
    (out / "main.c").write_text("int main(void) {}\n", encoding="utf-8")
    with pytest.raises(ContextError, match="无法判定平台"):
        infer_context(out, tmp_path / "modules")


# ---------------------------------------------------------------------------
# 形状校验：平台词表 / slugs 库内存在性 / 绑定形状
# ---------------------------------------------------------------------------


def test_validate_context_fields_rejects_unknown_platform(tmp_path):
    """平台不在词表 → ContextError（加载 API 400 关口）。"""
    library = make_fake_module_library(tmp_path / "modules")
    fields = build_context_fields(platform="riscv", slugs=["dht11"], main_c="")
    with pytest.raises(ContextError, match="未知平台"):
        validate_context_fields(fields, library)


def test_validate_context_fields_rejects_unknown_slugs(tmp_path):
    """slugs 有库外模块 → ContextError（前端手动勾选兜底入口）。"""
    library = make_fake_module_library(tmp_path / "modules")
    fields = build_context_fields(platform=PLATFORM_STM32, slugs=["nope"], main_c="")
    with pytest.raises(ContextError, match="不在模块库内"):
        validate_context_fields(fields, library)


def test_validate_context_fields_rejects_bad_bindings_shape(tmp_path):
    """bindings 键没有 <slug>.<role> 形态 → ContextError。"""
    library = make_fake_module_library(tmp_path / "modules")
    fields = build_context_fields(platform=PLATFORM_STM32, slugs=["dht11"], main_c="")
    fields["bindings"] = {"badkey": "PA1"}  # 键没有 <slug>.<role> 形态
    with pytest.raises(ContextError, match="bindings"):
        validate_context_fields(fields, library)


def test_validate_context_fields_accepts_known_slugs(tmp_path):
    """合法字段（库内 slugs + 空绑定）→ 不抛。"""
    library = make_fake_module_library(tmp_path / "modules")
    fields = build_context_fields(platform=PLATFORM_STM32, slugs=["dht11"], main_c="")
    validate_context_fields(fields, library)  # 不抛


# ---------------------------------------------------------------------------
# 加载 API（/api/revise/context）：有清单直读 / 无清单反推 / 错误路径
# ---------------------------------------------------------------------------


@pytest.fixture
def revise_client(tmp_path):
    """已配置的假上下文（test_webapp 同款）：假模块库 + 空母版库 + 假 LLM。"""
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(api_key="sk-test", module_library_dir=library_dir),
        llm_factory=lambda config: _DummyLLM(),
    )
    return TestClient(create_app(ctx)), library_dir, tmp_path


class _DummyLLM:
    """加载 API 不触 LLM；占位实现满足 llm_factory 契约。"""

    def __getattr__(self, name):
        raise AssertionError(f"加载 API 不应调用 LLM：{name}")


def test_revise_context_reads_manifest_directly(revise_client):
    client, library_dir, tmp_path = revise_client
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=library_dir,
        masters_dir=tmp_path / "masters",
        problem_text="2024 巡线小车",
    )
    resp = client.post("/api/revise/context", json={"output_dir": str(summary.output_dir)})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "manifest"
    assert data["context"]["platform"] == PLATFORM_STM32
    assert data["context"]["slugs"] == ["delay", "dht11", "oled"]
    assert data["context"]["problem_text"] == "2024 巡线小车"
    assert data["context"]["main_c"] == MAIN_SKELETON
    # 题面已落盘；功能需求清单为空（本次生成没回传）→ 标记 missing 提示补
    assert data["missing"] == ["requirements"]


def test_revise_context_reads_fresh_main_c_after_manual_edit(revise_client):
    """有清单路径 main.c 现读磁盘（不返回清单里的生成时快照——手工编辑保留）。"""
    client, library_dir, tmp_path = revise_client
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=library_dir,
        masters_dir=tmp_path / "masters",
    )
    edited = "int main(void) { /* 手工补充的逻辑 */ while (1); }\n"
    (summary.output_dir / "main.c").write_text(edited, encoding="utf-8")
    resp = client.post("/api/revise/context", json={"output_dir": str(summary.output_dir)})
    assert resp.status_code == 200, resp.text
    assert resp.json()["context"]["main_c"] == edited


def test_revise_context_infers_without_manifest(revise_client):
    client, library_dir, tmp_path = revise_client
    master = make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=library_dir,
        masters_dir=tmp_path / "masters",
    )
    (summary.output_dir / CONTEXT_MANIFEST_FILENAME).unlink()
    resp = client.post("/api/revise/context", json={"output_dir": str(summary.output_dir)})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "inferred"
    assert data["context"]["platform"] == PLATFORM_STM32
    assert data["context"]["slugs"] == ["delay", "dht11", "oled"]
    assert "problem_text" in data["missing"]
    assert "requirements" in data["missing"]


def test_revise_context_output_dir_missing_400(revise_client):
    client, _, tmp_path = revise_client
    resp = client.post("/api/revise/context", json={"output_dir": str(tmp_path / "nope")})
    assert resp.status_code == 400
    assert "输出目录不存在" in resp.json()["detail"]


def test_revise_context_corrupt_manifest_400(revise_client):
    client, _, tmp_path = revise_client
    out = tmp_path / "out"
    out.mkdir()
    (out / "project.uvprojx").write_text("<Project/>", encoding="utf-8")
    (out / CONTEXT_MANIFEST_FILENAME).write_text("{bad", encoding="utf-8")
    resp = client.post("/api/revise/context", json={"output_dir": str(out)})
    assert resp.status_code == 400
    assert "损坏" in resp.json()["detail"]


def test_revise_context_invalid_platform_400(revise_client):
    client, _, tmp_path = revise_client
    out = tmp_path / "out"
    out.mkdir()
    (out / CONTEXT_MANIFEST_FILENAME).write_text(
        json.dumps({"platform": "riscv", "slugs": []}), encoding="utf-8"
    )
    resp = client.post("/api/revise/context", json={"output_dir": str(out)})
    assert resp.status_code == 400
    assert "未知平台" in resp.json()["detail"]
