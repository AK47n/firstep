"""工单 pin-capacity/02 验收探针：HTTP 路径上 400 中文是否带容量数字。

**零额度**：走 FastAPI TestClient（进程内真 HTTP 路径、真路由、真门禁），并用
「一被调用就抛错」的假 LLM 工厂兜底——本探针证明生成链路在读题面之前就被门禁拦下。

四种形态（payload 与前端同形：`desktop:false` + 显式 `output_dir` = 手动目录模式，
不触发 AI 起名）：

| 形态 | 期望 |
|---|---|
| 2026H/mspm0 12 选中（无 bindings） | **400**，文案带 13/42/31/27/7 组/剩 3 组/至少去掉 3；输出目录未产生 |
| motor+servo（无 bindings） | **400**，文案带容量段且说「可解开」、**无**「至少要去掉」 |
| motor+servo + bindings 解掉撞脚 | **200 放行**（本单只改文案、未加拦截；输出目录产生） |
| motor 单模块 | **200 放行**（无冲突、无容量段） |

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-capacity/probe-05-http-acceptance.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

CACHE = REPO / ".scratch" / "real-run" / "cache" / "recommend_2026H.json"
OUT_ROOT = REPO / ".scratch" / "pin-capacity" / "_http"
LIB = REPO / "library" / "modules"


class _LlmTrap:
    """被调用即抛错：本探针的每一跑都必须在任何 LLM 调用之前结束。"""

    def __getattr__(self, name: str):
        def _boom(*_args, **_kwargs):
            raise AssertionError(f"本探针不得触发 LLM 调用（被调 {name}）")

        return _boom


def _client() -> TestClient:
    ctx = AppContext(
        config_path=OUT_ROOT / "config.json",
        config=AppConfig(
            api_key="sk-not-used",
            module_library_dir=LIB,
            masters_dir=REPO / "library" / "masters",
        ),
        llm_factory=lambda _config: _LlmTrap(),
    )
    return TestClient(create_app(ctx), raise_server_exceptions=False)


def _run(label: str, slugs: list[str], out_name: str, bindings=None) -> dict:
    out_dir = OUT_ROOT / out_name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    payload = {
        "platform": "mspm0",
        "slugs": slugs,
        "main_c": "int main(void) { while (1); }\n",
        "output_dir": str(out_dir),
        "desktop": False,
        "references": [],
    }
    if bindings is not None:
        payload["bindings"] = bindings
    resp = _client().post("/api/generate", json=payload)
    detail = resp.json().get("detail", "") if resp.headers.get("content-type", "").startswith("application/json") else ""
    print(f"\n===== {label} =====")
    print(f"[HTTP] {resp.status_code}")
    print(f"[输出目录] 产生 = {out_dir.exists()}")
    if resp.status_code != 200:
        print("[文案]")
        print(detail)
    else:
        print(f"[放行] 摘要键 = {sorted(resp.json().keys())[:6]} …")
    return {
        "label": label,
        "status": resp.status_code,
        "detail": detail,
        "out_dir_created": out_dir.exists(),
    }


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    cached = json.loads(CACHE.read_text(encoding="utf-8"))
    slugs = [m["slug"] for m in cached["done"]["modules"]]

    results = [
        _run("① 2026H 12 选中（无 bindings）→ 期望 400 带容量数字", slugs, "out-2026h"),
        _run(
            "② motor+servo（无 bindings）→ 期望 400 带容量段、说可解开",
            ["motor", "servo"],
            "out-motor-servo",
        ),
        _run(
            "③ motor+servo + bindings 解撞脚 → 期望 200 放行（只改文案未加拦截）",
            ["motor", "servo"],
            "out-motor-servo-bound",
            bindings={"servo.SERVO_PWM_C0": "PA0"},
        ),
        _run("④ motor 单模块 → 期望 200 放行（无冲突）", ["motor"], "out-motor"),
    ]

    text = json.dumps(results, ensure_ascii=False, indent=2)
    (REPO / ".scratch" / "pin-capacity" / "verify-02-http-acceptance.json").write_text(
        text, encoding="utf-8"
    )
    print("\n[汇总]", [(r["label"][:6], r["status"], r["out_dir_created"]) for r in results])
    ok = (
        results[0]["status"] == 400
        and not results[0]["out_dir_created"]
        and "【引脚容量】" in results[0]["detail"]
        and results[1]["status"] == 400
        and "【引脚容量】" in results[1]["detail"]
        and results[2]["status"] == 200
        and results[3]["status"] == 200
    )
    print(f"[判据] 四形态全部符合期望 = {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
