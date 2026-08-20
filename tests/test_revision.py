"""修订执行（工单 revise-deepen/03）：备份 / 覆盖式重生成 / 回滚的测试。

只测外部行为：整树备份与回滚（逐文件比对一致）、模块集变化重生成（新骨架
替换、旧版在备份）、模块集不变保全 main.c（手工编辑不丢）、失败路径（备份
保留 = 可回滚）、webapp 执行与回滚端点（SSE 事件序列 + 同步回滚）。素材 =
假模块库 + 假母版 + 假 LLM（fakes.py 先例）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contest_generator.context_manifest import CONTEXT_MANIFEST_FILENAME
from contest_generator.platforms import PLATFORM_STM32
from contest_generator.revision import (
    RevisionError,
    backup_tree,
    restore_revision,
    revise_backup_root,
    run_revision,
)
from contest_generator.webapp import AppContext, AppConfig, create_app
from tests.fakes import (
    FakeLLM,
    make_fake_master_project,
    make_fake_module_library,
)
from tests.test_impact import _RecordEmitter, _sse_events


# ---------------------------------------------------------------------------
# 备份 / 回滚原语
# ---------------------------------------------------------------------------


def test_backup_tree_and_restore_roundtrip(tmp_path):
    """整树备份（带编号、输出目录外）+ 回滚后目录内容与备份逐文件一致。"""
    out = tmp_path / "out"
    out.mkdir()
    (out / "main.c").write_text("int main(void) {}\n", encoding="utf-8")
    (out / "pin_config.h").write_text("#define X 1\n", encoding="utf-8")
    (out / "sub").mkdir()
    (out / "sub" / "a.c").write_text("/* a */\n", encoding="utf-8")

    root = revise_backup_root(tmp_path / "work")
    backup_id = backup_tree(root, out)
    backup_dir = root / backup_id
    assert backup_dir.is_dir()
    assert (backup_dir / "main.c").read_text(encoding="utf-8") == "int main(void) {}\n"

    # 修订后目录内容变化（模拟）→ 回滚恢复
    (out / "main.c").write_text("/* revised */\n", encoding="utf-8")
    (out / "sub" / "a.c").unlink()
    (out / "extra.c").write_text("/* extra */\n", encoding="utf-8")
    restored = restore_revision(root, backup_id, out)
    assert (out / "main.c").read_text(encoding="utf-8") == "int main(void) {}\n"
    assert (out / "sub" / "a.c").is_file()
    assert not (out / "extra.c").exists()  # 回滚 = 恢复备份内容，修订残留全清
    assert "main.c" in restored


def test_backup_tree_missing_output_raises(tmp_path):
    with pytest.raises(RevisionError, match="输出目录不存在"):
        backup_tree(revise_backup_root(tmp_path / "work"), tmp_path / "nope")


def test_restore_revision_unsafe_backup_id_raises(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(RevisionError, match="非法的备份编号"):
        restore_revision(tmp_path / "work", "../evil", out)


# ---------------------------------------------------------------------------
# 编排：备份 → （变化时）重生成 → diff 记录
# ---------------------------------------------------------------------------


def _revision_env(tmp_path):
    """假模块库 + 假母版（生成素材）。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    return library, tmp_path


def test_run_revision_regenerates_when_modules_change(tmp_path):
    """模块集变化 → 新骨架替换 main.c（旧版在备份）+ 覆盖式重生成 + 清单更新。"""
    from contest_generator.generator import generate_project

    library, env = _revision_env(tmp_path)
    output_dir = tmp_path / "out"
    generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content="int main(void) { /* 旧骨架 */ while (1); }\n",
        output_dir=output_dir,
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        problem_text="2024 巡线小车",
        qa_text="旧答疑",
        requirements=[{"requirement": "循迹", "sentence": 1}],
    )
    llm = FakeLLM(main_skeleton="int main(void) { /* 新骨架 */ while (1); }\n")
    emitter = _RecordEmitter()
    result = run_revision(
        llm=llm,
        problem_text="2024 巡线小车",
        qa_text="旧答疑",
        requirements=[{"requirement": "循迹", "sentence": 1}],
        references=(),
        current_slugs=["delay", "dht11", "oled"],
        confirmed_slugs=["delay", "dht11"],
        new_qa_text="新答疑：不要 OLED",
        platform=PLATFORM_STM32,
        library_dir=library,
        masters_dir=tmp_path / "masters",
        output_dir=output_dir,
        backup_root=revise_backup_root(tmp_path / "work"),
        emit=emitter,  # type: ignore[arg-type]
    )
    assert emitter.events == ["revision_backup", "revision_generating"]
    assert result["regenerated"] is True
    assert result["diff"] == {"added": [], "removed": ["oled"]}
    assert result["backup_id"]
    # 新骨架替换 main.c；旧版在备份里
    assert (output_dir / "main.c").read_text(
        encoding="utf-8"
    ) == "int main(void) { /* 新骨架 */ while (1); }\n"
    backup_main = (
        revise_backup_root(tmp_path / "work") / result["backup_id"] / "main.c"
    ).read_text(encoding="utf-8")
    assert "旧骨架" in backup_main
    # 覆盖式重生成：oled 模块不再在产物里
    assert not (output_dir / "modules" / "oled").exists()
    assert (output_dir / "modules" / "dht11").is_dir()
    # 上下文清单同步更新（新 slugs + Q&A 并入）
    fields = json.loads(
        (output_dir / CONTEXT_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert fields["slugs"] == ["delay", "dht11"]
    assert "新答疑" in fields["qa_text"]
    assert "旧答疑" in fields["qa_text"]


def test_run_revision_keeps_main_c_when_modules_unchanged(tmp_path):
    """模块集不变 → 不重生成、main.c 原样保留（手工编辑不丢），清单 Q&A 更新。"""
    from contest_generator.generator import generate_project

    library, env = _revision_env(tmp_path)
    output_dir = tmp_path / "out"
    generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "oled"],
        main_c_content="int main(void) { /* 骨架 */ while (1); }\n",
        output_dir=output_dir,
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        problem_text="2024 巡线小车",
        qa_text="",
        requirements=(),
    )
    edited = "int main(void) { /* 手工补充的逻辑 */ while (1); }\n"
    (output_dir / "main.c").write_text(edited, encoding="utf-8")
    llm = FakeLLM(main_skeleton="int main(void) { /* 不该用 */ }\n")
    emitter = _RecordEmitter()
    result = run_revision(
        llm=llm,
        problem_text="2024 巡线小车",
        qa_text="",
        requirements=(),
        references=(),
        current_slugs=["delay", "dht11", "oled"],
        confirmed_slugs=["delay", "dht11", "oled"],
        new_qa_text="新答疑：确认原方案",
        platform=PLATFORM_STM32,
        library_dir=library,
        masters_dir=tmp_path / "masters",
        output_dir=output_dir,
        backup_root=revise_backup_root(tmp_path / "work"),
        emit=emitter,  # type: ignore[arg-type]
    )
    assert emitter.events == ["revision_backup"]  # 无 generating 事件
    assert result["regenerated"] is False
    assert result["diff"] == {"added": [], "removed": []}
    # main.c 原样保留（不丢手工编辑）
    assert (output_dir / "main.c").read_text(encoding="utf-8") == edited
    # 上下文清单 Q&A 并入新答疑
    fields = json.loads(
        (output_dir / CONTEXT_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert fields["qa_text"] == "新答疑：确认原方案"
    assert llm.impact_calls == []  # 未调用影响分析（无 LLM 骨架调用）


def test_run_revision_failure_keeps_backup(tmp_path):
    """失败路径：备份成功但重生成失败 → 抛错、备份保留（目录保持可回滚）。"""
    from contest_generator.generator import generate_project

    library, env = _revision_env(tmp_path)
    output_dir = tmp_path / "out"
    generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=output_dir,
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        problem_text="题面",
    )
    backup_root = revise_backup_root(tmp_path / "work")
    llm = FakeLLM()
    emitter = _RecordEmitter()
    # 确认集含库外模块 → resolve_selection 抛错（UnknownModuleError）
    with pytest.raises(Exception):
        run_revision(
            llm=llm,
            problem_text="题面",
            qa_text="",
            requirements=(),
            references=(),
            current_slugs=["delay", "dht11"],
            confirmed_slugs=["delay", "nope"],
            new_qa_text="Q&A",
            platform=PLATFORM_STM32,
            library_dir=library,
            masters_dir=tmp_path / "masters",
            output_dir=output_dir,
            backup_root=backup_root,
            emit=emitter,  # type: ignore[arg-type]
        )
    # 备份保留（可回滚），输出目录未被清空（失败发生在清空之前）
    backups = list(backup_root.iterdir())
    assert len(backups) == 1
    assert (output_dir / "main.c").is_file()


# ---------------------------------------------------------------------------
# webapp：执行（SSE）与回滚（同步）
# ---------------------------------------------------------------------------


@pytest.fixture
def apply_client(tmp_path):
    """已配置的假上下文：假模块库 + 假母版 + 假 LLM。"""
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    holder: dict = {"llm": FakeLLM()}
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=lambda config: holder["llm"],
    )
    return TestClient(create_app(ctx)), holder, tmp_path


def _generate_project(client, tmp_path) -> str:
    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11", "oled"],
            "main_c": "int main(void) { while (1); }\n",
            "problem_text": "2024 巡线小车",
            "output_dir": str(tmp_path / "out"),
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["output_dir"]


def test_revise_apply_sse_flow_and_rollback(apply_client):
    """执行端点：backup → generating → done（diff 记录）；回滚端点恢复。"""
    client, holder, tmp_path = apply_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(main_skeleton="int main(void) { /* 新骨架 */ }\n")
    resp = client.post(
        "/api/revise/apply",
        json={
            "output_dir": output_dir,
            "confirmed_slugs": ["dht11", "oled", "delay"],
            "new_qa_text": "新答疑",
        },
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [event_type for event_type, _ in events]
    assert types[-1] == "done"
    done = events[-1][1]
    assert done["regenerated"] is False  # 确认集 = 依赖展开后的相同集
    backup_id = done["backup_id"]
    assert "revision_backup" in types

    # 手工改 main.c 模拟修订后状态 → 回滚
    (Path(output_dir) / "main.c").write_text("/* 改坏了 */\n", encoding="utf-8")
    rollback = client.post(
        "/api/revise/rollback",
        json={"output_dir": output_dir, "backup_id": backup_id},
    )
    assert rollback.status_code == 200, rollback.text
    restored = rollback.json()["restored"]
    assert "main.c" in restored
    assert "改坏了" not in (Path(output_dir) / "main.c").read_text(encoding="utf-8")


def test_revise_apply_regenerates_with_new_modules(apply_client):
    """执行端点：确认集含新模块 → 重生成（done.regenerated=True，diff 增）。"""
    client, holder, tmp_path = apply_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(main_skeleton="int main(void) { /* 新骨架 */ }\n")
    # dht11 依赖 delay——确认集省略 delay 会让 resolve_selection 展开补回，
    # 因此用"去掉 oled"制造变化
    resp = client.post(
        "/api/revise/apply",
        json={
            "output_dir": output_dir,
            "confirmed_slugs": ["dht11", "delay"],
            "new_qa_text": "不要显示屏",
        },
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    done = events[-1][1]
    assert done["regenerated"] is True
    assert done["diff"]["removed"] == ["oled"]
    assert "revision_generating" in [event_type for event_type, _ in events]
    assert not (Path(output_dir) / "modules" / "oled").exists()


def test_revise_apply_rollback_missing_backup_400(apply_client):
    client, _, tmp_path = apply_client
    output_dir = _generate_project(client, tmp_path)
    resp = client.post(
        "/api/revise/rollback",
        json={"output_dir": output_dir, "backup_id": "20200101-000000"},
    )
    assert resp.status_code == 400
    assert "备份不存在" in resp.json()["detail"]
