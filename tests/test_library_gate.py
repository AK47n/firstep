# -*- coding: utf-8 -*-
"""工单 ci-gate-fixes/04：**库相关的端点不该被「先配 API」那道闸挡住**。

判据面（本文件的分类依据，逐条对应工单 Comments 里的两类清单）：

* **只需要「库在哪」**（本单放行）：模块库 / 母版库 / 赛题库 / 参考文件库的浏览与
  读取、PDF 与 Markdown 资料库这类纯读盘端点，以及只恢复文件、不派发模型的
  回滚 / 上下文加载端点。
* **真的需要 AI**（本单不动）：推荐 / 生成 / 骨架 / 摘要抽取 / 蒸馏 / 修订分析 /
  任务推进 / 参数 / 排障 —— 它们照旧在缺 key 时 400 中文。

「库在哪」的三条来源都要走同一条路（工单验收标准③）：

1. **引导态**：`install.bat` 写的那份配置（库路径齐全 + `api_key` 空串）
   ——`load_config` 按「缺 api_key」大声拒绝，但库的位置写在文件里（`raw_library_dirs`）。
   本文件的主体测的就是这一条。
2. **随包库回退**：配置文件根本不在 + 随包库在场 —— 走 `load_config` 的回退分支，
   在 `tests/test_config.py::test_app_context_resolves_default_path_at_construction`
   里以子进程真起服务的方式验（那里才是缺省路径解析的真实入口）。
3. **哪都没有**：库的位置定不出来 → 仍然是 400，但文案说的是「库在哪」，
   不是「未配置 AI API」（否则用户被指去填一个跟这件事无关的 key）。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi.testclient import TestClient

from contest_generator.config import AppConfig
from contest_generator.webapp import AppContext, create_app
from tests.fakes import DHT11_H, make_fake_module_library

#: 本仓 src（结构判据读源码真身；`find_tool_root` 那套在测试里另有先例，这里只需定位）
REPO_SRC = Path(__file__).resolve().parents[1] / "src"

#: 缺 key 时仍然要 400 中文的 AI 端点（反向判据：本单只放行「库在哪」那一类）
AI_ENDPOINTS: tuple[tuple[str, str, dict], ...] = (
    ("POST", "/api/recommend", {"problem_text": "题目"}),
    ("POST", "/api/topic/preread", {"problem_text": "题目"}),
    ("POST", "/api/my-devices/draft", {"text": "BMP280 地址 0x76"}),
    ("POST", "/api/topics/extract-number", {"text": "2026C 题目"}),
)

AI_REJECTION = "未配置 AI API"
#: 库位置定不出来时的出路文案（本单新增；不再借 AI 那句）
LIBRARY_REJECTION = "还没配置模块库目录"


def _seed_library(tmp_path: Path) -> tuple[Path, Path]:
    """假库：模块库（有 dht11 / oled 等真条目）+ 空母版库。"""
    library = make_fake_module_library(tmp_path / "library" / "modules")
    masters = tmp_path / "library" / "masters"
    masters.mkdir(parents=True, exist_ok=True)
    return library, masters


def bootstrap_client(tmp_path: Path) -> TestClient:
    """引导态：配置文件在，库路径齐全，`api_key` 是空串（install.bat 写的形态）。"""
    library, masters = _seed_library(tmp_path)
    return _bootstrap_client(tmp_path, library, masters)


def bootstrap_client_with_real_library(tmp_path: Path) -> TestClient:
    """引导态 + **检出内那份真库** —— `install.bat` 写出来的就是这个组合。

    检测页那条链要真模块（框架的心跳 LED、通道模块都得在库里有 manifest 与引脚
    声明），假库满足不了；真库那份也正是用户第一次起服务时会看到的库。
    """
    return _bootstrap_client(
        tmp_path, REPO_SRC.parent / "library" / "modules",
        REPO_SRC.parent / "library" / "masters",
    )


def _bootstrap_client(tmp_path: Path, library: Path, masters: Path) -> TestClient:
    config_path = tmp_path / "cfg" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "api_key": "",
                "module_library_dir": str(library),
                "masters_dir": str(masters),
            }
        ),
        encoding="utf-8",
    )
    return TestClient(create_app(AppContext(config_path=config_path, config=None)))


def test_bootstrap_state_serves_the_module_library(tmp_path):
    """引导态：库的位置写在配置里（key 空）⇒ 模块库列表读得出来。

    这是用户拿到工具的第一个动作——「看看里面有什么模块」。早先它答 400
    「未配置 AI API」，把一件跟 AI 无关的事说成了 AI 的事。
    """
    client = bootstrap_client(tmp_path)

    resp = client.get("/api/modules")

    assert resp.status_code == 200, resp.text
    assert {m["slug"] for m in resp.json()} >= {"dht11", "oled"}


def test_bootstrap_state_serves_a_module_file(tmp_path):
    """同一来源下，模块源码单文件也读得出来（浏览不只停在清单）。"""
    client = bootstrap_client(tmp_path)

    resp = client.get("/api/modules/dht11/files/inc/dht11.h")

    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == DHT11_H   # 假库里那份头文件的原文（期望值来自夹具，不是重算）


def test_bootstrap_state_serves_the_other_three_libraries(tmp_path):
    """母版库 / 赛题库 / 参考文件库同一条路：缺 key 一样读得出来。

    空库返回空列表也是 200——「库在这台机器上、只是还没入库」不该被当成未配置。
    """
    client = bootstrap_client(tmp_path)

    for path in ("/api/masters", "/api/topics", "/api/references"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text}"
        assert resp.json() == [], f"{path} 空库应为空列表"


def test_bootstrap_state_serves_the_material_libraries(tmp_path):
    """PDF / Markdown 资料库（素材根）：同为「库在哪」，缺 key 一样读得出来。"""
    client = bootstrap_client(tmp_path)

    for path in ("/api/pdfs", "/api/materials-md"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text}"


def test_bootstrap_state_serves_material_file_content(tmp_path):
    """素材不只要列得出来，还要读得出来（清单 200 / 正文 400 是最容易漏的一半）。

    素材根按 `config.materials_dir` 从模块库同级推（`library/sources/materials`），
    这里把它真造出来，走一遍清单 → 单文件全文。
    """
    materials = tmp_path / "library" / "sources" / "materials" / "批次甲"
    materials.mkdir(parents=True, exist_ok=True)
    (materials / "手册.md").write_text("# 手册正文\n", encoding="utf-8")
    client = bootstrap_client(tmp_path)

    listed = client.get("/api/materials-md")
    assert listed.status_code == 200, listed.text
    assert [item["name"] for item in listed.json()] == ["手册.md"]

    resp = client.get("/api/materials-md/批次甲/手册.md")
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == "# 手册正文\n"


def test_bootstrap_state_serves_binding_endpoints(tmp_path):
    """引脚板图与依赖展开同属「只需要库在哪」；`/api/bindings/matrix` 正是
    CI 夹具当初撞见 400 的那个端点（spec「实测读数」表里的后端日志）。

    板图判据来自库内 manifest + 板定义，一个模型都不派发——没 key 不该 400。
    """
    client = bootstrap_client(tmp_path)

    matrix = client.post(
        "/api/bindings/matrix", json={"platform": "stm32", "slugs": ["dht11"]}
    )
    assert matrix.status_code == 200, matrix.text
    # 只判"闸门放行 + 载荷形状"：假库那几个模块没声明 pin 角色，roles 本来就该是空的
    # （板图内容归 test_bindings_matrix.py，本文件只管闸门）
    assert "roles" in matrix.json(), matrix.text

    expand = client.post(
        "/api/selection/expand", json={"platform": "stm32", "slugs": ["dht11"]}
    )
    assert expand.status_code == 200, expand.text


def test_bootstrap_state_serves_the_hardware_check_page(tmp_path):
    """检测页也走同一条库闸（评审补口）：它自己 docstring 就写着「硬件检测不需要 AI」。

    早先它独占一道 `_current_config` 闸 ⇒ 引导态下**同一台机器上两套说法**：
    库端点 200、检测页 400。判据取预览端点（检测页装配那条链的入口），
    库用检出内那份真库——`install.bat` 写出来的正是这个组合。
    """
    client = bootstrap_client_with_real_library(tmp_path)

    resp = client.post(
        "/api/hwcheck/preview",
        json={"platform": "stm32", "devices": []},
    )

    assert resp.status_code == 200, resp.text


def test_bootstrap_state_still_rejects_ai_endpoints(tmp_path):
    """反向判据：AI 端点照旧缺 key 就 400 中文（放行的只是「库在哪」那一类）。"""
    client = bootstrap_client(tmp_path)

    for method, path, payload in AI_ENDPOINTS:
        resp = client.request(method, path, json=payload)
        assert resp.status_code == 400, f"{path} → {resp.status_code} {resp.text}"
        assert AI_REJECTION in resp.json()["detail"], f"{path} → {resp.text}"


def test_no_library_at_all_says_the_library_is_unconfigured(tmp_path):
    """库的位置**定不出来**时仍然是 400，但说的是「库在哪」这件事。

    这条钉的是文案归属：早先库端点借的是 AI 那句提示，用户会去填一个
    跟「看不见库」无关的 key。AI 端点那边保持原话不变（上一条用例）。
    """
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "never-written.json",
        config=None,
    )
    client = TestClient(create_app(ctx))

    resp = client.get("/api/modules")

    assert resp.status_code == 400, resp.text
    assert LIBRARY_REJECTION in resp.json()["detail"], resp.text
    assert AI_REJECTION not in resp.json()["detail"], resp.text


def test_configured_context_keeps_serving_config_fields(tmp_path):
    """有 key 的常规配置不受影响：两个访问器仍拿得到配置里的那一对路径。

    放在这里是因为本单把 `_library_dir` / `_masters_dir` 从 `_require_config`
    上摘了下来——正方向（有配置照旧）必须同时钉住，免得「缺 key 放行」
    变成「配置被忽略」。
    """
    library, masters = _seed_library(tmp_path)
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test", module_library_dir=library, masters_dir=masters
        ),
    )
    client = TestClient(create_app(ctx))

    assert client.get("/api/modules").status_code == 200
    assert client.get("/api/masters").status_code == 200


def test_keyless_config_without_library_fields_is_not_a_library_source(tmp_path):
    """配置在、key 空、**库路径也没写** ⇒ 不算「库在哪」。

    这是「引导态」与「什么都没说」的分界：`install.bat` 写的那份一定带两个库目录，
    所以本单只认**文件里真写了**的那一对（`raw_library_dirs`）。什么都不写就退回
    缺省位置 = 拿一个多半不存在的目录假装有库——比 400 指路更坏。
    """
    config_path = tmp_path / "cfg" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({"api_key": ""}), encoding="utf-8")
    client = TestClient(create_app(AppContext(config_path=config_path, config=None)))

    resp = client.get("/api/modules")

    assert resp.status_code == 400, resp.text
    assert LIBRARY_REJECTION in resp.json()["detail"], resp.text


# ---------------------------------------------------------------------------
# 分类注册表（结构判据）：把工单 Comments 里那张「真需要 AI」的表钉进源码事实
# ---------------------------------------------------------------------------

#: 走 AI 闸（`_require_config`）的函数 —— 工单 Comments「A 表」的机器可读版。
#: 判据是**源码事实**（谁真的调了 `_require_config`），不是这里的名单本身：
#: 两个方向都判，见下面那条用例。
AI_GATED_FUNCTIONS = frozenset({
    "_assemble_topic_context",   # 题面装配（自动识别编号要 LLM）
    "_llm",                      # LLM 工厂本身：所有 AI 端点的必经口
    "extract",                   # 上传件视觉图注
    "fix_errors",                # 编译错误修复
    "generate",                  # 生成
    "masters_confirm",           # 蒸馏确认（归档动作要 LLM 判定）
    "params_chat_send",          # 参数问答
    "recommend",                 # 推荐
    "revise_analyze",            # 修订影响分析
    "revise_apply",              # 修订套用
    "revise_deepen",             # 深化
    "skeleton",                  # 骨架
    "tasks_discuss",             # 任务对话
    "tasks_execute",             # 任务执行
    "tasks_idea_analyze",        # 想法分析
    "tasks_idea_chat_send",      # 想法对话
    "tasks_idea_fix",            # 想法修复
    "tasks_params_apply",        # 参数套用
    "tasks_params_scan",         # 参数扫描
    "tasks_plan",                # 任务计划
    "topics_split",              # 长 PDF 拆条
})


def _ai_gated_functions_in_source() -> set[str]:
    """webapp.py 里**真的**调了 `_require_config(` 的函数名（取最内层那个）。

    取最内层是关键：路由都嵌在 `create_app` 里，若按"包含该行"算，`create_app`
    会把所有调用都算上（那样这条判据就成了恒真的废话）。
    """
    source = (REPO_SRC / "contest_generator" / "webapp.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    funcs = [
        (node.lineno, node.end_lineno or node.lineno, node.name)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    found: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_require_config"
        ):
            continue
        enclosing = [f for f in funcs if f[0] <= node.lineno <= f[1]]
        enclosing.sort(key=lambda f: f[1] - f[0])
        found.add(enclosing[0][2])
    return found


def test_ai_gate_registry_matches_source():
    """结构判据：`_require_config` 的调用点 = 「真需要 AI」那张表。

    两个方向都判，两个方向都对应一类真事故：

    * **表里有、源码里没了** —— 某个 AI 端点的 key 闸门被静默摘掉
      （用户没配 key 也能把请求打到模型上）；
    * **源码里有、表里没有** —— 新增 AI 端点没登记（漏了闸门或漏了记账），
      或者**某个库端点又被挂回 AI 闸**——后者正是本单在治的病
      （库端点只看"库在哪"，不看 key）。

    改动意图是前者或后者时，改这张表并在工单里说清为什么，别让判据自己漂。
    """
    assert _ai_gated_functions_in_source() == set(AI_GATED_FUNCTIONS)


def test_library_accessors_never_consult_the_api_key():
    """结构判据：两个库访问器与 `_library_config` 都不许看 `api_key`。

    本单的核心不变量就这一句。行为面由上面的端点用例守着，这里钉**源码形状**
    ——免得将来有人图省事把 `_require_config` 塞回访问器里（那时端点用例会红一大片，
    但红的原因要排查半天；这一条直接点名）。
    """
    source = (REPO_SRC / "contest_generator" / "webapp.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    bodies = {
        node.name: _code_without_docstring(source, node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in ("_library_config", "_library_dir", "_masters_dir",
                 "_bootstrap_library_config"):
        body = bodies[name]
        assert "_require_config" not in body, f"{name} 又挂回了 AI 闸"
        assert ".api_key" not in body, f"{name} 开始看 api_key 了——库闸不该看它"


def _code_without_docstring(source: str, node: ast.AST) -> str:
    """函数的**可执行代码**（剥掉 docstring）。

    必须剥：这几条的 docstring 正是用来说清"不看 `api_key`"的，把说明当成代码
    就是自证其反（第一版这么写，当场假红）。
    """
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return "\n".join(ast.get_source_segment(source, stmt) or "" for stmt in body)
