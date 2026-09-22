# -*- coding: utf-8 -*-
"""两个 app 实例共不共享会话态：收走前 / 收走后同一支探针（工单 webapp-state-into-ctx/01、02）。

只读探针：不碰仓库文件，只在本进程里起**两个** TestClient（两个各自的 `AppContext`），
看「A 实例的会话态」会不会被 **B 实例**的端点看见。会话态的注入缝随版本自动识别——
新代码在 `ctx.running_task_execs` / `ctx.materials_last_check`，旧代码在
`contest_generator.webapp` 的模块级同名全局（带下划线）。同一支探针因此在改动前后各跑一次，
读数可直接对读：**这是本条「并行跑用例更安全」那张卖点的证据**。

读数含义：
- 执行注册表：A 标 `t1`「正在执行」→ 看 B 的改标端点会不会跟着拒（会 = 两边共享）。
- 资料库白名单：把一份 check 结果放进 A → 看 B 的 apply 认不认这个批次（认 = 两边共享）。

不打网络、不起服务器：check 结果直接注入状态缝（不走 check 端点），资料库任务用桩类替掉
`webapp.ApplyTask`（否则 apply 会真起下载线程去打那个假 URL）。

用法：
    python .scratch/webapp-state-into-ctx/probe-00-sharing.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from fastapi.testclient import TestClient  # noqa: E402

import contest_generator.webapp as webapp_mod  # noqa: E402
from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402
from contest_generator.task_progress import (  # noqa: E402
    TASKS_MANIFEST_FILENAME,
    Task,
    TaskPlan,
)
from contest_generator.webapp import AppContext, create_app  # noqa: E402
from tests.fakes import (  # noqa: E402
    FakeLLM,
    make_fake_master_project,
    make_fake_module_library,
)


class _StubApplyTask:
    """资料库任务的桩（探针不允许真起下载线程 / 真打网络）。"""

    def __init__(self, task_dir, batches, on_complete=None, **_kw) -> None:
        self.task_dir = task_dir
        self.batches = batches
        self._on_complete = on_complete
        self.state = type("S", (), {"value": "downloading"})()

    def run(self) -> None:  # 端点用 daemon 线程包一层，这里什么都不做
        return None

    def cancel(self) -> None:
        return None


def _two_instances(root: Path):
    """两个 app 实例（两个各自的 AppContext），照 tests/test_task_progress.py 的夹具先例。"""
    made = []
    for name in ("a", "b"):
        base = root / name
        holder: dict = {"llm": FakeLLM()}
        ctx = AppContext(
            config_path=base / "cfg" / "config.json",
            config=AppConfig(
                api_key="sk-test",
                module_library_dir=make_fake_module_library(base / "module_library"),
                masters_dir=base / "masters",
            ),
            # 形状必须吃住 `_llm` 的可变元数派发（它按签名决定传 1/2/3 个位置参数）
            llm_factory=lambda config, *args, holder=holder: holder["llm"],
            desktop_dir=lambda base=base: base / "Desktop",
        )
        make_fake_master_project(ctx.config.masters_dir / PLATFORM_STM32)
        made.append((ctx, TestClient(create_app(ctx)), holder))
    return made


def _mark_running(ctx: AppContext, task_id: str) -> str:
    """把 task 标成「正在执行」——注入缝随版本自动识别（旧代码 = 模块级全局）。"""
    if hasattr(ctx, "running_task_execs"):
        ctx.running_task_execs.add(task_id)
        return "ctx.running_task_execs"
    webapp_mod._running_task_execs.add(task_id)  # type: ignore[attr-defined]
    return "webapp._running_task_execs（模块级）"


def _seed_check(ctx: AppContext, check: dict) -> str:
    """把一份 check 结果放进 A 的会话态——注入缝同样自动识别。"""
    if hasattr(ctx, "materials_last_check"):
        ctx.materials_last_check.update(check)
        return "ctx.materials_last_check"
    webapp_mod._MATERIALS_LAST_CHECK.update(check)  # type: ignore[attr-defined]
    return "webapp._MATERIALS_LAST_CHECK（模块级）"


def _make_task_plan(client: TestClient, holder: dict, out_dir: Path) -> Path:
    """造一份真清单：/api/generate → /api/tasks/plan → 该任务改 doing（僵尸恢复的前置）。

    返回**端点实际用的**输出目录（照 tests 的 `_generate_project`：桌面模式下目录名由
    服务端裁决，payload 里的 output_dir 不是它）。
    """
    gen = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": "int main(void) { /* TODO */ while (1); }\n",
            "problem_text": "2024 巡线小车",
            "output_dir": str(out_dir),
            "requirements": [{"requirement": "循迹", "sentence": 1, "modules": ["dht11"]}],
            "score_points": [
                {"id": "s1", "part": "basic", "description": "循迹", "score": 20}
            ],
        },
    )
    assert gen.status_code == 200, f"生成失败：{gen.status_code} {gen.text}"
    out_dir = Path(gen.json()["output_dir"])
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    plan = client.post("/api/tasks/plan", json={"output_dir": str(out_dir)})
    assert plan.status_code == 200, f"拆解失败：{plan.status_code} {plan.text}"
    path = out_dir / TASKS_MANIFEST_FILENAME
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["tasks"][0]["status"] = "doing"
    path.write_text(json.dumps(saved), encoding="utf-8")
    return out_dir


def _check_result() -> dict:
    return {
        "current_version": "v1.0.0",
        "latest_version": "v1.1.0",
        "update_available": True,
        "total_size_bytes": 100,
        "batches": [
            {
                "slug": "k230",
                "name": "k230资料",
                "size_bytes": 100,
                "parts": [
                    {
                        "zip_url": "https://example.invalid/k230.zip",
                        "size_bytes": 100,
                        "sha256": "a" * 64,
                        "zip_name": "k230.zip",
                    }
                ],
            }
        ],
        "deleted_batches": [],
        "error": "",
        "message": "",
    }


def main() -> int:
    webapp_mod.ApplyTask = _StubApplyTask  # type: ignore[assignment]
    rows: list[str] = []
    with tempfile.TemporaryDirectory(prefix="firstep-sharing-") as tmp:
        root = Path(tmp)
        (ctx_a, client_a, holder_a), (ctx_b, client_b, _) = _two_instances(root)

        # ① 执行注册表 ---------------------------------------------------
        out_dir = _make_task_plan(client_a, holder_a, root / "out")
        seam = _mark_running(ctx_a, "t1")
        resp_a = client_a.post(
            "/api/tasks/status",
            json={"output_dir": str(out_dir), "task_id": "t1", "status": "pending"},
        )
        resp_b = client_b.post(
            "/api/tasks/status",
            json={"output_dir": str(out_dir), "task_id": "t1", "status": "pending"},
        )
        rows.append(f"  注入缝 = {seam}")
        rows.append(f"  A（持有状态的实例）改标 → {resp_a.status_code}")
        rows.append(
            f"  B（另一个实例）改标   → {resp_b.status_code}"
            f"{'  ← 跟着拒了 = 两个实例共享同一张注册表' if resp_b.status_code == 400 else '  ← 看不见 = 各实例一份'}"
        )

        # ② 资料库批次白名单 ---------------------------------------------
        seam2 = _seed_check(ctx_a, _check_result())
        resp_b2 = client_b.post("/api/update/materials/apply", json={"batches": ["k230"]})
        rows.append(f"  注入缝 = {seam2}")
        rows.append(
            f"  B（另一个实例）apply A 的批次 → {resp_b2.status_code}"
            f"{'  ← 认了 = 两边共用白名单' if resp_b2.status_code == 200 else '  ← 不认 = 各实例一份'}"
        )

    print("== 两个 app 实例共不共享会话态 ==")
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
