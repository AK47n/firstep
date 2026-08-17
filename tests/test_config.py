"""本机配置文件：读写、默认值、错误处理。

AI API key 存用户主目录下的配置文件（版本库之外，不入库）；工作目录
（模块库 / 母版）默认在工具工作目录下，可配置。
"""

import json

import pytest

from contest_generator.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MASTERS_DIR,
    DEFAULT_MODEL,
    DEFAULT_MODULE_LIBRARY_DIR,
    AppConfig,
    ConfigError,
    load_config,
    materials_dir,
    save_config,
)


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


def test_load_missing_file_raises_with_hint(tmp_path):
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
        # 本地 LLM 端点（工单 local-llm-routing/01）：缺省空串 = 本地路由关闭
        "local_llm_base_url": "",
        "local_llm_model": "",
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
