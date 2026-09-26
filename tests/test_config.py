"""本机配置文件：读写、默认值、错误处理。

AI API key 存用户主目录下的配置文件（版本库之外，不入库）；工作目录
（模块库 / 母版）默认在工具工作目录下，可配置。
"""

import json
import os
import subprocess
import sys

import pytest

from contest_generator.config import (
    DEFAULT_BASE_URL,
    DEFAULT_CONFIG_PATH,
    DEFAULT_MASTERS_DIR,
    DEFAULT_MODEL,
    DEFAULT_MODULE_LIBRARY_DIR,
    AppConfig,
    ConfigError,
    bundled_library_dirs,
    config_path,
    load_config,
    materials_dir,
    save_config,
)
from contest_generator.tool_root import find_tool_root


def test_save_then_load_roundtrip_preserves_config(tmp_path):
    path = tmp_path / "cfg" / "config.json"  # 父目录不存在，save 应自动创建

    save_config(
        AppConfig(
            base_url="https://example.com/api",
            api_key="sk-test",
            model="deepseek-reasoner",
            module_library_dir=tmp_path / "lib",
            masters_dir=tmp_path / "masters",
        ),
        path,
    )

    assert load_config(path) == AppConfig(
        base_url="https://example.com/api",
        api_key="sk-test",
        model="deepseek-reasoner",
        module_library_dir=tmp_path / "lib",
        masters_dir=tmp_path / "masters",
    )


def test_load_applies_defaults_for_optional_fields(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    loaded = load_config(path)

    assert loaded.base_url == DEFAULT_BASE_URL
    assert loaded.model == DEFAULT_MODEL
    # 工作目录缺省时落在工具工作目录下的默认位置
    assert loaded.module_library_dir == DEFAULT_MODULE_LIBRARY_DIR
    assert loaded.masters_dir == DEFAULT_MASTERS_DIR


def test_load_missing_file_raises_with_hint(tmp_path, monkeypatch):
    """随包库也不在时，缺配置仍报「不存在」并给出提示（工单 ci-gate-fixes/01）。

    这条原先直接 `load_config(tmp_path / "no-config.json")` 就期望抛错，隐含前提是
    「配置缺失一律报错」。本单给了一个**唯一例外**：配置缺失 + 随包库在场 → 用随包库
    （干净检出直接起服务）。所以这里显式把随包库也拿掉，判的仍是原来那件事；
    「随包库在场 → 回退」由 `test_load_missing_config_falls_back_to_bundled_library` 判。
    """
    monkeypatch.setattr("contest_generator.config.find_tool_root", _FakeToolRoot(tmp_path))

    with pytest.raises(ConfigError, match="不存在"):
        load_config(tmp_path / "no-config.json")


def test_load_invalid_json_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigError, match="JSON"):
        load_config(path)


@pytest.mark.parametrize("api_key", [None, "", 123])
def test_load_missing_or_invalid_api_key_raises(tmp_path, api_key):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": api_key}), encoding="utf-8")

    with pytest.raises(ConfigError, match="api_key"):
        load_config(path)


def test_saved_file_is_plain_json(tmp_path):
    path = tmp_path / "config.json"

    save_config(AppConfig(api_key="sk-test"), path)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "base_url": DEFAULT_BASE_URL,
        "api_key": "sk-test",
        "model": DEFAULT_MODEL,
        "module_library_dir": str(DEFAULT_MODULE_LIBRARY_DIR),
        "masters_dir": str(DEFAULT_MASTERS_DIR),
        "autocommit_enabled": True,
        # 工具链可选覆盖（工单 autocompile-loop/01）：缺省空串 = 自动探测
        "uv4_path": "",
        "gmake_path": "",
        # CCS 三件套可选覆盖（工单 mspm0-build-makefiles/01）：缺省空串 = 自动探测
        "ccs_sdk_dir": "",
        "ccs_compiler_dir": "",
        "ccs_sysconfig_cli": "",
        # 烧录工具可选覆盖（工单 flash-deploy/01）：缺省空串 = 自动探测
        "openocd_path": "",
        "stflash_path": "",
        "dslite_path": "",
        # 本地 LLM 端点（工单 local-llm-routing/01）：缺省空串 = 本地路由关闭
        "local_llm_base_url": "",
        "local_llm_model": "",
        # 视觉通道（工单 vision-deepseek-native/01）：api_key 空 = 复用主 key，base/model 有默认
        "vision_base_url": "https://api.deepseek.com",
        "vision_api_key": "",
        "vision_model": "deepseek-flash",
        # 问答式精注记开关（工单 vision-detail-qa/01）：缺省开
        "vision_detail_qa": True,
        # 推荐缓存开关（工单 llm-cost-control/02）：缺省开
        "recommend_cache_enabled": True,
        # 推荐收敛轮数上限（工单 recommend-speedup-v2/01）：缺省 4
        "recommend_max_rounds": 4,
        # 计费时段（工单 01 扩展）：缺省 off_peak（2026-08 起默认低谷）
        "llm_price_period": "off_peak",
    }


def test_toolchain_paths_default_blank_and_roundtrip(tmp_path):
    """uv4_path / gmake_path（工单 autocompile-loop/01）：缺省空串；非空回写。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")
    assert load_config(path).uv4_path == ""
    assert load_config(path).gmake_path == ""

    save_config(
        AppConfig(
            api_key="sk-test",
            uv4_path=r"C:\Keil5\Core\UV4\UV4.exe",
            gmake_path="gmake",
        ),
        path,
    )
    loaded = load_config(path)
    assert loaded.uv4_path == r"C:\Keil5\Core\UV4\UV4.exe"
    assert loaded.gmake_path == "gmake"

    path.write_text(
        json.dumps({"api_key": "sk-test", "uv4_path": 123}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="uv4_path"):
        load_config(path)  # 类型非法大声失败（与其余字段同严格度）


def test_ccs_toolchain_paths_default_blank_and_roundtrip(tmp_path):
    """ccs 三件套（工单 mspm0-build-makefiles/01）：缺省空串 = 自动探测；
    非空回写；类型非法大声失败（uv4_path 同款）。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")
    loaded = load_config(path)
    assert loaded.ccs_sdk_dir == ""
    assert loaded.ccs_compiler_dir == ""
    assert loaded.ccs_sysconfig_cli == ""

    save_config(
        AppConfig(
            api_key="sk-test",
            ccs_sdk_dir="C:/ti/ccs2051/mspm0_sdk_2_10_00_04",
            ccs_compiler_dir=(
                "C:/ti/ccs2050/ccs/tools/compiler/ti-cgt-armllvm_4.0.4.LTS"
            ),
            ccs_sysconfig_cli="C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat",
        ),
        path,
    )
    loaded = load_config(path)
    assert loaded.ccs_sdk_dir == "C:/ti/ccs2051/mspm0_sdk_2_10_00_04"
    assert loaded.ccs_compiler_dir == (
        "C:/ti/ccs2050/ccs/tools/compiler/ti-cgt-armllvm_4.0.4.LTS"
    )
    assert loaded.ccs_sysconfig_cli == "C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat"

    path.write_text(
        json.dumps({"api_key": "sk-test", "ccs_sdk_dir": 123}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="ccs_sdk_dir"):
        load_config(path)  # 类型非法大声失败（与其余字段同严格度）


def test_vision_fields_default_and_roundtrip(tmp_path):
    """视觉通道（工单 vision-deepseek-native/01）：缺省 base/model = DeepSeek
    官方端点与模型；key 空串 = 复用主 key（装配层判定）；非空回写；类型非法
    大声失败（local_llm 同款）。roundtrip 用自定义值验证「旧配置读回不变」。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")
    loaded = load_config(path)
    assert loaded.vision_base_url == "https://api.deepseek.com"
    assert loaded.vision_api_key == ""
    assert loaded.vision_model == "deepseek-flash"

    save_config(
        AppConfig(
            api_key="sk-test",
            vision_base_url="https://open.bigmodel.cn/api/paas/v4",
            vision_api_key="sk-vision",
            vision_model="glm-4.6v-flash",
        ),
        path,
    )
    loaded = load_config(path)
    assert loaded.vision_base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert loaded.vision_api_key == "sk-vision"
    assert loaded.vision_model == "glm-4.6v-flash"

    path.write_text(
        json.dumps({"api_key": "sk-test", "vision_api_key": 123}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="vision_api_key"):
        load_config(path)


def test_llm_price_period_default_and_roundtrip(tmp_path):
    """计费时段（工单 01 扩展）：缺省 off_peak（2026-08 起默认低谷）；peak
    回写；非法值大声失败。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")
    assert load_config(path).llm_price_period == "off_peak"

    save_config(AppConfig(api_key="sk-test", llm_price_period="peak"), path)
    assert load_config(path).llm_price_period == "peak"

    path.write_text(
        json.dumps({"api_key": "sk-test", "llm_price_period": "evening"}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="llm_price_period"):
        load_config(path)


def test_local_llm_fields_default_blank_and_roundtrip(tmp_path):
    """local_llm_base_url / local_llm_model（工单 local-llm-routing/01）：缺省空串
    = 本地路由关闭；非空回写；类型非法大声失败（uv4_path 同款）。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")
    loaded = load_config(path)
    assert loaded.local_llm_base_url == ""
    assert loaded.local_llm_model == ""

    save_config(
        AppConfig(
            api_key="sk-test",
            local_llm_base_url="http://localhost:11434/v1",
            local_llm_model="qwen2.5-coder:7b-instruct",
        ),
        path,
    )
    loaded = load_config(path)
    assert loaded.local_llm_base_url == "http://localhost:11434/v1"
    assert loaded.local_llm_model == "qwen2.5-coder:7b-instruct"

    path.write_text(
        json.dumps({"api_key": "sk-test", "local_llm_base_url": 123}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="local_llm_base_url"):
        load_config(path)  # 类型非法大声失败（与其余字段同严格度）

    path.write_text(
        json.dumps({"api_key": "sk-test", "local_llm_model": 456}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="local_llm_model"):
        load_config(path)


def test_autocommit_enabled_defaults_on_and_roundtrips(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    assert load_config(path).autocommit_enabled is True  # 缺省开（工单 01）

    save_config(AppConfig(api_key="sk-test", autocommit_enabled=False), path)
    assert load_config(path).autocommit_enabled is False

    path.write_text(
        json.dumps({"api_key": "sk-test", "autocommit_enabled": "yes"}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="autocommit_enabled"):
        load_config(path)  # 非布尔值大声失败（与其余字段同严格度）


def test_vision_detail_qa_defaults_on_and_roundtrips(tmp_path):
    """问答式精注记开关（工单 vision-detail-qa/01）：缺省开；False 往返；非布尔报错。"""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-test"}), encoding="utf-8")

    assert load_config(path).vision_detail_qa is True  # 缺省开

    save_config(AppConfig(api_key="sk-test", vision_detail_qa=False), path)
    assert load_config(path).vision_detail_qa is False

    path.write_text(
        json.dumps({"api_key": "sk-test", "vision_detail_qa": "no"}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="vision_detail_qa"):
        load_config(path)  # 非布尔值大声失败（与其余字段同严格度）


def test_materials_dir_prefers_sibling_when_exists(tmp_path):
    """默认布局：模块库 ~/.contest_generator/modules → 同级 sources/materials 优先。"""
    module_library_dir = tmp_path / "modules"
    sibling = tmp_path / "sources" / "materials"
    sibling.mkdir(parents=True)
    assert materials_dir(module_library_dir) == sibling


def test_materials_dir_falls_back_to_repo_root(tmp_path):
    """仓库布局：模块库在 library/ 子目录下 → 备份在仓库根 sources/materials。"""
    module_library_dir = tmp_path / "repo" / "library" / "modules"
    repo_root = tmp_path / "repo" / "sources" / "materials"
    repo_root.mkdir(parents=True)
    assert materials_dir(module_library_dir) == repo_root


def test_materials_dir_missing_everywhere_returns_sibling(tmp_path):
    """两处都没有 = 返回优先候选（文件服务端对缺失文件抛 ReferenceError → 400）。"""
    module_library_dir = tmp_path / "modules"
    assert materials_dir(module_library_dir) == tmp_path / "sources" / "materials"


# ---------------------------------------------------------------------------
# 干净检出直接起服务（spec ci-gate-fixes/01）：
# 配置缺失时回退随包库 + 配置路径覆盖口
# ---------------------------------------------------------------------------


class _FakeToolRoot:
    """把「随包库」伪造成 tmp 下一对目录（猴补 tool_root.find_tool_root 用）。"""

    def __init__(self, root):
        self.root = root

    def __call__(self, *_args, **_kwargs):
        return self.root


def _make_bundled_library(tool_root):
    """造一份像样的随包库：<工具根>/library/{modules,masters}。"""
    modules = tool_root / "library" / "modules"
    masters = tool_root / "library" / "masters"
    modules.mkdir(parents=True)
    masters.mkdir(parents=True)
    return modules, masters


def test_load_missing_config_falls_back_to_bundled_library(tmp_path, monkeypatch):
    """缺省位置（未指定路径）+ 随包库在场 → 用随包库，而不是报「未配置」。

    干净 clone 直接起服务就是这条路：用户还没配 API，但库随软件分发（ADR 0008），
    起服务就该看得见库。夹具则改用 `FIRSTEP_CONFIG_PATH` 显式指配置（另测）。
    """
    modules, masters = _make_bundled_library(tmp_path / "tool")
    monkeypatch.setattr("contest_generator.config.find_tool_root", _FakeToolRoot(tmp_path / "tool"))
    # 缺省位置指向一个不存在的文件，才走得到回退
    monkeypatch.setenv("FIRSTEP_CONFIG_PATH", str(tmp_path / "nowhere" / "config.json"))

    loaded = load_config()

    assert loaded.module_library_dir == modules
    assert loaded.masters_dir == masters
    assert loaded.api_key == ""  # 引导态：AI 功能仍不可用，但那由「未配置 AI API」那条路说
    assert loaded.base_url == DEFAULT_BASE_URL
    assert loaded.model == DEFAULT_MODEL


def test_load_missing_config_without_bundled_library_still_raises(tmp_path, monkeypatch):
    """缺省位置 + 随包库也不在（站点包安装等）→ 保持既有行为，不假装有库。"""
    tool_root = tmp_path / "tool"
    tool_root.mkdir()  # 没有 library/
    monkeypatch.setattr("contest_generator.config.find_tool_root", _FakeToolRoot(tool_root))
    monkeypatch.setenv("FIRSTEP_CONFIG_PATH", str(tmp_path / "nowhere" / "config.json"))

    with pytest.raises(ConfigError, match="不存在"):
        load_config()


def test_explicit_path_never_falls_back_to_bundled_library(tmp_path, monkeypatch):
    """**显式给了 path 就是显式意图**：文件不在照旧抛错，不拿随包库去替。

    这条是那个坑的守卫：测试用 `AppContext(config_path=…/"never-written.json")`
    表达「这台机器没配置」，若显式路径也回退，9 条「未配置」用例会集体静默翻向
    反方向（实测 `api_configured` 从 False 变 True）。
    """
    _make_bundled_library(tmp_path / "tool")  # 随包库**在场**
    monkeypatch.setattr("contest_generator.config.find_tool_root", _FakeToolRoot(tmp_path / "tool"))

    with pytest.raises(ConfigError, match="不存在"):
        load_config(tmp_path / "never-written.json")


def test_load_existing_config_ignores_bundled_library(tmp_path, monkeypatch):
    """配置存在就一律按配置走——不静默覆盖用户写的东西。"""
    modules, _masters = _make_bundled_library(tmp_path / "tool")
    monkeypatch.setattr("contest_generator.config.find_tool_root", _FakeToolRoot(tmp_path / "tool"))
    path = tmp_path / "config.json"
    mine = tmp_path / "my-own-lib"
    path.write_text(
        json.dumps({"api_key": "sk-test", "module_library_dir": str(mine)}),
        encoding="utf-8",
    )

    loaded = load_config(path)

    assert loaded.module_library_dir == mine != modules


def test_bundled_library_dirs_absent_when_no_library(tmp_path, monkeypatch):
    monkeypatch.setattr("contest_generator.config.find_tool_root", _FakeToolRoot(tmp_path))
    assert bundled_library_dirs() is None


def test_bundled_library_dirs_points_at_tool_root_library(tmp_path, monkeypatch):
    """判据 = 工具根单源下的 library/（与 install.bat 写给用户的是同一对路径）。"""
    modules, masters = _make_bundled_library(tmp_path / "tool")
    monkeypatch.setattr("contest_generator.config.find_tool_root", _FakeToolRoot(tmp_path / "tool"))

    assert bundled_library_dirs() == (modules, masters)


def test_config_path_env_override(monkeypatch, tmp_path):
    """显式覆盖口：夹具 / CI 指到自己的配置，不必伪造 HOME。"""
    mine = tmp_path / "elsewhere.json"
    monkeypatch.setenv("FIRSTEP_CONFIG_PATH", str(mine))
    assert config_path() == mine

    # 空串 / 纯空白 = 没设（回退缺省）
    monkeypatch.setenv("FIRSTEP_CONFIG_PATH", "   ")
    assert config_path() == DEFAULT_CONFIG_PATH


def test_load_config_default_path_follows_env_override(tmp_path, monkeypatch):
    """缺省路径必须**调用期**解析，否则子进程里设的环境变量不生效。"""
    mine = tmp_path / "seeded.json"
    mine.write_text(json.dumps({"api_key": "sk-seeded"}), encoding="utf-8")
    monkeypatch.setenv("FIRSTEP_CONFIG_PATH", str(mine))

    assert load_config().api_key == "sk-seeded"


def test_app_context_resolves_default_path_at_construction(tmp_path):
    """**走真实应用路径**（不猴补）：`AppContext()` → `create_app()` 也认得环境变量。

    这条是本单唯一盖得住主路径的判据，补它的原因值得写下来（2026-09-25 评审实测
    抓到的一条假绿）：早先的实现让"这是不是缺省位置"**在两处各记一次账**——
    `__post_init__` 里解析一次、`_current_config` 里再 `isinstance` 判一次，
    两处口径不一致 ⇒ 回退在生产路径上**完全不可达**，而其余用例只直调
    `load_config()`，于是整组全绿、CI 那条红却原封不动。判据必须钉在
    **服务真的答得出来**上，不是钉在"某个函数被调过"。

    子进程内跑：`config_path()` 是进程级环境读取，且 `AppContext()` 的解析发生在
    构造期——同一进程里已被 import 的模块不好干净地重来一遍（也会干扰同进程的
    其它用例）。
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    missing = tmp_path / "never-written.json"
    script = (
        "import json\n"
        "from contest_generator.webapp import AppContext, create_app\n"
        "from fastapi.testclient import TestClient\n"
        "ctx = AppContext()\n"
        "client = TestClient(create_app(ctx))\n"
        "modules = client.get('/api/modules')\n"   # 只打一发：状态与非空从同一份响应读
        "print(json.dumps({\n"
        "    'modules_status': modules.status_code,\n"
        "    'modules_count': (\n"
        "        len(modules.json()) if modules.status_code == 200 else None),\n"
        "    'masters_status': client.get('/api/masters').status_code,\n"
        "    'topics_status': client.get('/api/topics').status_code,\n"
        "    'references_status': client.get('/api/references').status_code,\n"
        "    'modules_dir': client.get('/api/settings').json()['module_library_dir'],\n"
        "    'api_configured': client.get('/api/env/status').json()['api_configured'],\n"
        "    'recommend_status': client.post('/api/recommend',\n"
        "                                    json={'problem_text': 'x'}).status_code,\n"
        "}))\n"
    )
    env = {
        **os.environ,
        "FIRSTEP_CONFIG_PATH": str(missing),
        "USERPROFILE": str(fake_home),
        "HOME": str(fake_home),
        "PYTHONIOENCODING": "utf-8",
        # PYTHONPATH 钉成**本仓** src：本机全局 site-packages 里那份 editable 安装
        # 可能指向另一个 clone（`.githooks/pre-push` 为此也钉过同一处），
        # 不钉就会测到别人的代码。
        "PYTHONPATH": str(find_tool_root(__file__) / "src"),
    }
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=120,
    )
    assert out.returncode == 0, f"子进程失败：{out.stderr[-800:]}"
    result = json.loads(out.stdout.strip().splitlines()[-1])

    # ① 主目标：干净机器上**库的位置**从缺省位置也认得出来（工单 ci-gate-fixes/01）。
    #    机器上没有任何 ~/.contest_generator，也没有显式指过路径。
    tool_root = find_tool_root(__file__)
    assert result["modules_dir"] == str(tool_root / "library" / "modules"), result
    # ② AI 面如实：key 是空的 ⇒ 未配置 + AI 端点中文拒绝（不再是拿空 key 往下跑）
    assert result["api_configured"] is False, result
    assert result["recommend_status"] == 400, result
    # ③ 库面可用（工单 ci-gate-fixes/04）：库的位置认得出来 ⇒ 库相关的只读端点
    #    就该读得出来。② 与 ③ 并立正是这单的形状——「没配 AI」不等于「没有库」。
    #    四库各打一发，模块库另判**非空**（本仓 library/modules 真有模块；
    #    只判 200 的话，"空目录也算答得出来"会把回退到错位置放过去）。
    assert result["modules_status"] == 200, result
    assert result["modules_count"] > 0, result
    assert result["masters_status"] == 200, result
    assert result["topics_status"] == 200, result
    assert result["references_status"] == 200, result


# ---------------------------------------------------------------------------
# 引导配置（工单 beginner-guide-enrich/03）：install.bat 首次自动指向随包库
# ---------------------------------------------------------------------------


def test_write_bootstrap_config_writes_minimal_and_keeps_unconfigured(tmp_path):
    from contest_generator.config import write_bootstrap_config

    path = tmp_path / "cfg" / "config.json"
    ok = write_bootstrap_config(
        tmp_path / "repo" / "library" / "modules",
        tmp_path / "repo" / "library" / "masters",
        path,
    )
    assert ok is True
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["api_key"] == ""  # 空 key = 应用保持「未配置」引导态
    assert data["module_library_dir"] == str(tmp_path / "repo" / "library" / "modules")
    assert data["masters_dir"] == str(tmp_path / "repo" / "library" / "masters")
    # 未配 key：load_config 仍拒绝（现有「请先到设置页配置」提示路径不变）
    with pytest.raises(ConfigError, match="api_key"):
        load_config(path)


def test_write_bootstrap_config_never_overwrites_existing(tmp_path):
    from contest_generator.config import write_bootstrap_config

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_key": "sk-keep"}), encoding="utf-8")
    assert write_bootstrap_config(tmp_path / "lib", tmp_path / "mas", path) is False
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["api_key"] == "sk-keep"  # 已有配置一律不动（幂等、尊重用户）
    assert "module_library_dir" not in data


def test_raw_library_dirs_reads_bootstrap_without_key(tmp_path):
    from contest_generator.config import raw_library_dirs

    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "api_key": "",
                "module_library_dir": str(tmp_path / "lib" / "modules"),
                "masters_dir": str(tmp_path / "lib" / "masters"),
            }
        ),
        encoding="utf-8",
    )
    mod, mas = raw_library_dirs(path)
    assert mod == tmp_path / "lib" / "modules"
    assert mas == tmp_path / "lib" / "masters"


def test_raw_library_dirs_fallbacks(tmp_path):
    from contest_generator.config import raw_library_dirs

    # 文件不存在 → 双 None
    assert raw_library_dirs(tmp_path / "nope" / "config.json") == (None, None)
    # 损坏 JSON → 双 None
    bad = tmp_path / "bad.json"
    bad.write_text("{broken", encoding="utf-8")
    assert raw_library_dirs(bad) == (None, None)
    # 字段缺失 / 空串 / 非字符串 → 该项 None
    partial = tmp_path / "partial.json"
    partial.write_text(json.dumps({"api_key": "sk", "masters_dir": "  "}), encoding="utf-8")
    mod, mas = raw_library_dirs(partial)
    assert mod is None and mas is None
