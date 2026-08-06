"""FastAPI 薄壳：端到端装配测试（工单 09）。

用 TestClient + 假上下文（tmp 配置 / 假模块库 / 假母版 / 假 LLM）驱动，
断言全部端点与验收项：生成流程完整可走通、AI 推荐展示理由、平台警告
明确呈现、生成结果就位（结构 / include path / main.c）、未落地平台显示
"暂不可用"、设置保存后即时生效。网络与 LLM 调用不进测试。
"""

from __future__ import annotations

import json
from typing import Sequence

import pytest
from fastapi.testclient import TestClient

from contest_generator.config import AppConfig
from contest_generator.llm import (
    JudgmentFile,
    LLMError,
    ModuleSelection,
    ValidationResult,
)
from contest_generator.report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    FileDecision,
)
from contest_generator.master import import_master, main_c_template
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.webapp import AppContext, create_app
from tests.fakes import (
    FAKE_DISTILL_UVPROJX_A,
    FakeLLM,
    make_fake_ccs_master_project,
    make_fake_master_project,
    make_fake_module_library,
    make_fake_stm32_projects,
    make_sample_docx,
)

SELECTION = ModuleSelection(
    modules=("dht11", "oled"),
    reasons={"dht11": "赛题要求采集温湿度", "oled": "需要显示测量结果"},
)


class RaisingLLM:
    """AI 服务失败用的假 LLM：任何职责都抛 LLMError（对应 502）。"""

    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection:
        raise LLMError("服务不可用")

    def generate_main_skeleton(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        raise LLMError("服务不可用")

    def summarize_module(self, code: str) -> str:
        raise LLMError("服务不可用")

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        raise LLMError("服务不可用")

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
    ) -> tuple[FileDecision, ...]:
        raise LLMError("服务不可用")


# 假工程对的典型 AI 判定（与 tests/test_master.py 同一套素材）
# 公共文件（所有工程内容一致）同样由 AI 判定：基础建设必需 → keep（判例 06）
DEFAULT_DECISIONS = (
    FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="官方库配置头，基础必需"),
    FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="系统初始化，基础必需"),
    FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用传感器驱动"),
    FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="上场比赛残留"),
    FileDecision(
        "project.uvprojx",
        ACTION_MERGE,
        content=FAKE_DISTILL_UVPROJX_A,  # 结构完整的整合产物（入库有结构校验）
        explanation="取 include path 更全的 A 版本",
        source="proj-a",
        reason="include path 更全",
    ),
    FileDecision(
        "src/oled.c",
        ACTION_MERGE,
        content="/* 通用 OLED 驱动（整合版） */\n",
        explanation="两版接口一致，整合去重",
        source="proj-b",
        reason="B 版本较新",
    ),
)


@pytest.fixture
def context(tmp_path):
    """已配置的假上下文：假模块库 + 空母版库 + 假 LLM，配置文件路径在 tmp 下。

    返回 (context, holder)；holder["llm"] 是当前 LLM，测试可随时换掉它
    （llm_factory 每次请求读 holder，换 LLM 即换行为）。
    """
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    masters_dir = tmp_path / "masters"
    holder = {"llm": FakeLLM(selection=SELECTION)}
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=masters_dir,
        ),
        llm_factory=lambda config: holder["llm"],
    )
    return ctx, holder


@pytest.fixture
def client(context):
    return TestClient(create_app(context[0]))


def _import_stm32_master(masters_dir, tmp_path) -> None:
    """给 stm32 平台导入一个母版（平台"落地"的判定条件）。"""
    import_master(masters_dir, PLATFORM_STM32, make_fake_master_project(tmp_path / "master_src"))


# ---------------------------------------------------------------------------
# 全局状态：平台可用性（验收项 5：未落地平台显示"暂不可用"而非报错）
# ---------------------------------------------------------------------------


def test_state_lists_platforms_with_availability(client, context, tmp_path):
    _import_stm32_master(context[0].config.masters_dir, tmp_path)

    state = client.get("/api/state").json()

    assert state["api_configured"] is True
    platforms = {p["id"]: p for p in state["platforms"]}
    assert set(platforms) == {PLATFORM_STM32, PLATFORM_MSPM0}
    # 有母版 → ready；无母版 → no-master（界面显示"暂不可用"，不报错）
    assert platforms[PLATFORM_STM32]["status"] == "ready"
    assert platforms[PLATFORM_MSPM0]["status"] == "no-master"


def test_state_reports_unconfigured_api(tmp_path):
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))

    state = client.get("/api/state").json()

    assert state["api_configured"] is False
    assert state["llm"] is None
    # 未配置时工作目录展示默认值
    assert state["module_library_dir"]
    assert state["masters_dir"]


def test_state_maps_corrupt_master_meta_to_400(client, context, tmp_path):
    # 母版目录在但元数据损坏：state 给 400 提示而非 500
    _import_stm32_master(context[0].config.masters_dir, tmp_path)
    (context[0].config.masters_dir / "stm32.json").write_text("{not json", encoding="utf-8")

    resp = client.get("/api/state")

    assert resp.status_code == 400
    assert "元数据" in resp.json()["detail"]


def test_ai_endpoints_reject_with_hint_when_unconfigured(tmp_path):
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))

    resp = client.post("/api/recommend", json={"problem_text": "题目"})

    assert resp.status_code == 400
    assert "未配置 AI API" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 生成流程（验收项 1）：抽取 → 推荐 → 展开 → 骨架 → 生成
# ---------------------------------------------------------------------------


def test_extract_uploaded_text_file(client):
    resp = client.post(
        "/api/extract", files={"upload": ("题目.txt", "设计一个温湿度采集系统".encode("utf-8"), "text/plain")}
    )

    assert resp.status_code == 200
    assert "温湿度" in resp.json()["text"]


def test_extract_uploaded_docx_file(client, tmp_path):
    docx = make_sample_docx(tmp_path / "题.docx", ["第一题：信号采集", "第二段：显示"])

    resp = client.post(
        "/api/extract",
        files={"upload": ("题.docx", docx.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert resp.status_code == 200
    assert "信号采集" in resp.json()["text"]


def test_extract_unsupported_type_returns_clear_error(client):
    resp = client.post(
        "/api/extract", files={"upload": ("题.exe", b"MZ", "application/octet-stream")}
    )

    assert resp.status_code == 400
    assert "不支持的文件类型" in resp.json()["detail"]


def test_recommend_returns_modules_with_reasons(client):
    resp = client.post("/api/recommend", json={"problem_text": "温湿度采集并显示"})

    assert resp.status_code == 200
    assert resp.json()["modules"] == [
        {"slug": "dht11", "reason": "赛题要求采集温湿度"},
        {"slug": "oled", "reason": "需要显示测量结果"},
    ]


def test_expand_resolves_dependencies_and_warns_on_missing_platform(client):
    # oled 只有 stm32 版本：选它在 mspm0 上展开必须给出 missing 警告
    resp = client.post(
        "/api/selection/expand", json={"slugs": ["dht11", "oled"], "platform": PLATFORM_MSPM0}
    )

    assert resp.status_code == 200
    data = resp.json()
    slugs = [m["slug"] for m in data["modules"]]
    # 依赖 delay 被自动带入，且排在依赖方之前
    assert slugs == ["delay", "dht11", "oled"]
    kinds = {w["kind"] for w in data["warnings"]}
    assert "missing" in kinds
    missing = next(w for w in data["warnings"] if w["kind"] == "missing")
    assert "oled" in missing["message"]


def test_expand_reports_unverified_and_hardware_bound(client, context):
    # 给 dht11 的 mspm0 版本打上"未验证 + 硬件绑定"标记后重新展开
    manifest_path = context[0].config.module_library_dir / "dht11" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["platforms"][PLATFORM_MSPM0]["verified"] = False
    data["platforms"][PLATFORM_MSPM0]["hardware_bound"] = True
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    resp = client.post(
        "/api/selection/expand", json={"slugs": ["dht11"], "platform": PLATFORM_MSPM0}
    )

    kinds = {w["kind"] for w in resp.json()["warnings"]}
    assert {"unverified", "hardware_bound"} <= kinds


def test_expand_rejects_unknown_module(client):
    resp = client.post(
        "/api/selection/expand", json={"slugs": ["nope"], "platform": PLATFORM_STM32}
    )

    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


def test_skeleton_returns_main_c_and_intercepts_undefined_calls(client, context):
    # 假 LLM 返回的骨架里混了一个接口中不存在的调用 → 改写为注释占位
    context[1]["llm"]._main_skeleton = (
        "int main(void) { float t = dht11_read(); dht11_init(); while (1); }\n"
    )

    resp = client.post(
        "/api/skeleton",
        json={"problem_text": "温湿度采集", "slugs": ["dht11"], "platform": PLATFORM_STM32},
    )

    assert resp.status_code == 200
    main_c = resp.json()["main_c"]
    assert "int main(void)" in main_c
    # 真实接口的调用保留；不存在的调用被占位且名字出现在拦截清单里
    assert "dht11_read();" in main_c
    assert "dht11_init" not in main_c.replace("dht11_init", "", 1) or "TODO" in main_c
    assert resp.json()["intercepted"] == ["dht11_init"]


def test_generate_assembles_project_with_structure_include_path_and_main(
    client, context, tmp_path
):
    _import_stm32_master(context[0].config.masters_dir, tmp_path)
    output_dir = tmp_path / "out" / "demo"

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11", "oled"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(output_dir),
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    # 验收项 4：工程结构 / include path / main.c 就位
    assert data["output_dir"] == str(output_dir)
    assert (output_dir / "main.c").is_file()
    assert (output_dir / "modules" / "dht11" / "inc" / "dht11.h").is_file()
    assert (output_dir / "modules" / "delay" / "delay.c").is_file()
    # include 目录与生成器实际注册的一致：根目录文件 → modules/<slug>，不含 "/."
    assert data["include_dirs"] == [
        "modules/delay",
        "modules/dht11/stm32/src",
        "modules/dht11/inc",
        "modules/oled/stm32/src",
        "modules/oled/inc",
    ]
    assert "main.c" in data["structure"]
    # 修改器生效：.uvprojx 注册了模块分组与 include path
    uvprojx = next(output_dir.glob("*.uvprojx")).read_text(encoding="utf-8")
    assert "modules" in uvprojx
    assert "modules\\dht11\\inc" in uvprojx


def test_generate_rejects_platform_without_master(client, context, tmp_path):
    # mspm0 无母版（未落地）：明确报错而非产出残缺工程
    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_MSPM0,
            "slugs": ["dht11"],
            "main_c": "int main(void) { while (1); }\n",
            "output_dir": str(tmp_path / "out"),
        },
    )

    assert resp.status_code == 400
    assert "母版" in resp.json()["detail"]


def test_generate_rejects_main_c_with_undefined_calls(client, context, tmp_path):
    _import_stm32_master(context[0].config.masters_dir, tmp_path)

    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": "int main(void) { nonexistent_call(); while (1); }\n",
            "output_dir": str(tmp_path / "out"),
        },
    )

    assert resp.status_code == 400
    assert "不存在的函数" in resp.json()["detail"]


def test_llm_failure_maps_to_502(client, context):
    context[1]["llm"] = RaisingLLM()  # 换掉假 LLM：直接抛 LLMError

    resp = client.post("/api/recommend", json={"problem_text": "题目"})

    assert resp.status_code == 502
    assert "AI 服务调用失败" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 模块库（工单 07 装配）
# ---------------------------------------------------------------------------


def test_modules_list_returns_all(client):
    resp = client.get("/api/modules")

    assert resp.status_code == 200
    slugs = [m["slug"] for m in resp.json()]
    assert slugs == ["broken", "delay", "dht11", "oled"]
    dht11 = next(m for m in resp.json() if m["slug"] == "dht11")
    assert dht11["dependencies"] == ["delay"]
    assert set(dht11["platforms"]) == {PLATFORM_STM32, PLATFORM_MSPM0}


def test_add_module_validates_then_stores(client):
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "超声波测距模块",
            "files": {
                "ultrasonic.c": "float distance(void);\n",
                "ultrasonic.h": "#pragma once\nfloat distance(void);\n",
            },
            "dependencies": ["delay"],
            "notes": "接 PA0",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["slug"] == "ultrasonic"
    listed = client.get("/api/modules").json()
    stored = next(m for m in listed if m["slug"] == "ultrasonic")
    assert stored["dependencies"] == ["delay"]
    assert stored["platforms"][PLATFORM_STM32]["notes"] == "接 PA0"


def test_add_module_drafts_description_when_empty(client):
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "",
            "files": {"ultrasonic.c": "float distance(void);\n"},
        },
    )

    assert resp.status_code == 200
    assert resp.json()["draft"] == "AI 生成的模块简介"
    # 草稿阶段不入库
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_add_module_rejects_inconsistent_description(client, context):
    context[1]["llm"]._validation = ValidationResult(consistent=False, issues="简介与代码不符")

    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "与代码不符的简介",
            "files": {"ultrasonic.c": "float distance(void);\n"},
        },
    )

    assert resp.status_code == 400
    assert "不一致" in resp.json()["detail"]
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_add_module_rejects_non_boolean_flags(client):
    # 字符串 "false" 宽松强转会静默翻转硬件绑定标记：必须严格布尔
    resp = client.post(
        "/api/modules",
        json={
            "slug": "ultrasonic",
            "platform": PLATFORM_STM32,
            "description": "超声波测距模块",
            "hardware_bound": "false",
            "files": {"ultrasonic.c": "float distance(void);\n"},
        },
    )

    assert resp.status_code == 400
    assert "布尔值" in resp.json()["detail"]
    assert "ultrasonic" not in [m["slug"] for m in client.get("/api/modules").json()]


def test_module_description_update_and_delete(client):
    slug = "dht11"
    resp = client.put(
        f"/api/modules/{slug}/description", json={"description": "温湿度传感器（已编辑）"}
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "温湿度传感器（已编辑）"

    resp = client.delete(f"/api/modules/{slug}")
    assert resp.status_code == 200
    assert slug not in [m["slug"] for m in client.get("/api/modules").json()]


def test_module_add_platform_files(client):
    resp = client.post(
        "/api/modules/oled/platform-files",
        json={"platform": PLATFORM_MSPM0, "files": {"mspm0/src/oled.c": "void oled_init(void);\n"}},
    )

    assert resp.status_code == 200
    assert PLATFORM_MSPM0 in resp.json()["platforms"]


# ---------------------------------------------------------------------------
# 母版（工单 08 装配）：扫描 → 提炼 → 确认入库 → 浏览 → 删除
# ---------------------------------------------------------------------------


def test_master_flow_scan_distill_confirm_list_delete(client, context, tmp_path):
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]

    scanned = client.post("/api/masters/scan", json={"project_dirs": dirs}).json()
    assert [p["name"] for p in scanned] == ["proj-a", "proj-b"]
    assert all(p["platform"] == PLATFORM_STM32 for p in scanned)

    report = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": dirs}
    ).json()
    assert report["projects"] == ["proj-a", "proj-b"]
    assert [d["path"] for d in report["keep"]] == [
        "inc/stm32f10x_conf.h", "src/system_stm32f10x.c", "sensors/dht11.c",
    ]
    assert [d["path"] for d in report["merge"]] == ["project.uvprojx", "src/oled.c"]
    # exclude = AI 判定 + 规则识别的残留（带规则化原因）+ 旧工程 main.c（模板替代）
    assert [d["path"] for d in report["exclude"]] == [
        "ui/oled_fonts.c",
        "main.c.bak",
        "src/oled.hex",
        "src/oled.o",
        "ui/oled_fonts.c~",
        "main.c",
    ]
    residue = next(d for d in report["exclude"] if d["path"] == "src/oled.o")
    assert residue["reason"] == "构建产物：.o 文件"
    main_c = next(d for d in report["exclude"] if d["path"] == "main.c")
    assert main_c["action"] == ACTION_EXCLUDE
    assert "模板" in main_c["reason"]
    # 报告携带模板 main.c 全文预览：一次确认前用户能看到将要写入母版的 main.c
    assert report["main_c_preview"] == main_c_template(PLATFORM_STM32)
    assert report["main_c_preview"]

    confirmed = client.post(
        "/api/masters/confirm",
        json={**report, "project_dirs": dirs},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["platform"] == PLATFORM_STM32
    assert confirmed.json()["sources"] == ["proj-a", "proj-b"]

    stored = context[0].config.masters_dir / PLATFORM_STM32
    # 母版 main.c = 确定性模板，旧工程 main.c 不进母版（ADR 0002）
    assert (stored / "main.c").read_text(encoding="utf-8") == main_c_template(
        PLATFORM_STM32
    )
    assert "proj-a 的赛题 main" not in (stored / "main.c").read_text(encoding="utf-8")

    masters = client.get("/api/masters").json()
    assert [m["platform"] for m in masters] == [PLATFORM_STM32]

    resp = client.delete(f"/api/masters/{PLATFORM_STM32}")
    assert resp.status_code == 200
    assert client.get("/api/masters").json() == []


def test_master_confirm_rejects_user_edited_merge_on_unique(client, context, tmp_path):
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]
    report = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": dirs}
    ).json()
    # 用户把 sensors/dht11.c（只有一份内容，没有整合对象）从保留改成合并
    report["keep"] = [d for d in report["keep"] if d["path"] != "sensors/dht11.c"]
    report["merge"].append(
        {
            "path": "sensors/dht11.c",
            "action": ACTION_MERGE,
            "content": "/* 整合 */",
            "explanation": "用户改的",
            "source": "proj-b",
            "reason": "用户改的",
        }
    )

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 400
    assert "只用于" in resp.json()["detail"]
    assert client.get("/api/masters").json() == []  # 确认失败不入库


def test_master_confirm_rejects_restoring_old_main_c(client, context, tmp_path):
    """旧工程 main.c 由模板确定性替代：用户把 main.c 从剔除改成保留 → 拒绝入库。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]
    report = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": dirs}
    ).json()
    # 用户想把旧 main.c 恢复进母版——确定性替代不因用户编辑而失效
    report["exclude"] = [d for d in report["exclude"] if d["path"] != "main.c"]
    report["keep"].append(
        {"path": "main.c", "action": ACTION_KEEP, "reason": "用户改的"}
    )

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 400
    assert "旧工程 main.c 必须剔除" in resp.json()["detail"]
    assert client.get("/api/masters").json() == []  # 确认失败不入库


def test_master_confirm_user_moves_common_to_exclude(client, context, tmp_path):
    """公共文件默认保留，但用户确认时可改为剔除（经 HTTP 端到端）。"""
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = DEFAULT_DECISIONS
    dirs = [str(proj_a), str(proj_b)]
    report = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": dirs}
    ).json()
    report["keep"] = [d for d in report["keep"] if d["path"] != "inc/stm32f10x_conf.h"]
    report["exclude"].append(
        {"path": "inc/stm32f10x_conf.h", "action": ACTION_EXCLUDE, "reason": "用户确认剔除"}
    )

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 200
    stored = context[0].config.masters_dir / PLATFORM_STM32
    assert not (stored / "inc/stm32f10x_conf.h").exists()
    assert client.get("/api/masters").json() == [{
        "platform": PLATFORM_STM32,
        "sources": ["proj-a", "proj-b"],
        "warnings": [],
    }]


def test_master_confirm_invalid_ai_merged_uvprojx_returns_400(context, tmp_path):
    """AI 整合出的 .uvprojx 是截断 XML → 业务失败 400 带中文 message，不裸 500。

    真实 LLM 整合 .uvprojx 时可能输出截断 / 转义错误的 XML，落盘阶段
    rewrite_project_references 解析失败——此前 KeilProjectError 未被确认端点
    捕获，浏览器只看到裸 500 且界面停在"落盘与入库中"。
    """
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = (
        FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="必需"),
        FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="必需"),
        FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用"),
        FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="残留"),
        FileDecision(
            "project.uvprojx",
            ACTION_MERGE,
            content="<Project>\n  <Targets>\n    <Target>\n      <TargetName>proj",  # 截断
            explanation="整合",
            source="proj-a",
            reason="整合",
        ),
        FileDecision(
            "src/oled.c",
            ACTION_MERGE,
            content="/* 整合 */\n",
            explanation="整合",
            source="proj-b",
            reason="整合",
        ),
    )
    client = TestClient(create_app(context[0]), raise_server_exceptions=False)
    dirs = [str(proj_a), str(proj_b)]
    report = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": dirs}
    ).json()

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 400
    assert "不是合法 XML" in resp.json()["detail"]
    assert client.get("/api/masters").json() == []  # 失败不入库


def test_master_confirm_uvprojx_excluded_returns_400(context, tmp_path):
    """AI 把 .uvprojx 判为剔除 → 落盘重写找不到工程文件 → 400 而非 500。

    .uvprojx 是 Keil 工程的"工程文件"，AI 判 exclude 后母版目录没有
    .uvprojx，rewrite_project_references 找不到目标——同样是 KeilProjectError
    裸传 500 的漏网点。
    """
    proj_a, proj_b = make_fake_stm32_projects(tmp_path / "old_projects")
    context[1]["llm"]._distillation = (
        FileDecision("inc/stm32f10x_conf.h", ACTION_KEEP, reason="必需"),
        FileDecision("src/system_stm32f10x.c", ACTION_KEEP, reason="必需"),
        FileDecision("sensors/dht11.c", ACTION_KEEP, reason="通用"),
        FileDecision("ui/oled_fonts.c", ACTION_EXCLUDE, reason="残留"),
        FileDecision(
            "project.uvprojx", ACTION_EXCLUDE, reason="AI 认为不需要工程文件"
        ),
        FileDecision(
            "src/oled.c",
            ACTION_MERGE,
            content="/* 整合 */\n",
            explanation="整合",
            source="proj-b",
            reason="整合",
        ),
    )
    client = TestClient(create_app(context[0]), raise_server_exceptions=False)
    dirs = [str(proj_a), str(proj_b)]
    report = client.post(
        "/api/masters/distill", json={"platform": PLATFORM_STM32, "project_dirs": dirs}
    ).json()

    resp = client.post("/api/masters/confirm", json={**report, "project_dirs": dirs})

    assert resp.status_code == 400
    assert "uvprojx" in resp.json()["detail"].lower()
    assert client.get("/api/masters").json() == []  # 失败不入库


# ---------------------------------------------------------------------------
# 设置：保存后即时生效（验收项 6）
# ---------------------------------------------------------------------------


def test_settings_save_takes_effect_immediately(tmp_path):
    seen_configs = []
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")

    def factory(config):
        seen_configs.append(config)
        return FakeLLM(selection=SELECTION)

    ctx = AppContext(config_path=config_path, config=None, llm_factory=factory)
    client = TestClient(create_app(ctx))

    # 未配置时 AI 端点拒绝
    assert client.post("/api/recommend", json={"problem_text": "题"}).status_code == 400

    resp = client.put(
        "/api/settings",
        json={
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-new-key",
            "model": "deepseek-chat",
            "module_library_dir": str(library_dir),
            "masters_dir": str(tmp_path / "masters"),
        },
    )
    assert resp.status_code == 200

    # 配置文件落盘 + 上下文即时更新：下一次 AI 调用就用新配置
    assert ctx.config.api_key == "sk-new-key"
    resp = client.post("/api/recommend", json={"problem_text": "题"})
    assert resp.status_code == 200
    assert seen_configs[-1].api_key == "sk-new-key"


def test_settings_get_masks_api_key_and_put_keeps_masked_value(client, context):
    current = client.get("/api/settings").json()
    assert current["configured"] is True
    assert "…" in current["api_key"]
    assert "sk-test" not in current["api_key"]

    # 提交掩码 = 用户没改 key：沿用旧值，只有 base_url 生效
    resp = client.put(
        "/api/settings",
        json={
            "base_url": "https://other.example.com",
            "api_key": current["api_key"],
            "model": current["model"],
            "module_library_dir": current["module_library_dir"],
            "masters_dir": current["masters_dir"],
        },
    )
    assert resp.status_code == 200
    assert context[0].config.base_url == "https://other.example.com"
    assert context[0].config.api_key == "sk-test"  # 掩码未覆盖真实 key


def test_settings_requires_api_key_on_first_configuration(tmp_path):
    ctx = AppContext(config_path=tmp_path / "cfg" / "config.json", config=None)
    client = TestClient(create_app(ctx))

    resp = client.put(
        "/api/settings",
        json={
            "base_url": "https://api.deepseek.com",
            "api_key": "",
            "model": "deepseek-chat",
            "module_library_dir": str(tmp_path / "lib"),
            "masters_dir": str(tmp_path / "masters"),
        },
    )

    assert resp.status_code == 400
    assert "API key" in resp.json()["detail"]
