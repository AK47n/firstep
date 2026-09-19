# -*- coding: utf-8 -*-
"""工单 module-hwcheck/02 真机口径证据：**走产品端点**生成检测工程 → 真编译。

用法：

    python .scratch/module-hwcheck/verify-02-real-machine.py stm32     # UV4 全量重建
    python .scratch/module-hwcheck/verify-02-real-machine.py mspm0     # gmake（需 SysConfig）

它做四件事（全程产品路径，不另写一套）：

1. `POST /api/hwcheck/generate`（TestClient，真库真母版，输出到
   `.scratch/module-hwcheck/out_compile/`）——生成载荷落证据；
2. 产物树复核：`build_output_tree_corpus` + `run_generation_gates`（与生成前
   同一套门禁，工单 generate-check-parity/01 口径）；
3. `POST /api/compile`（SSE）→ done 载荷（exit_code / passed / 错误列表）；
4. 把上面三段的结论写 `verify-02-<平台>-compile.txt`（证据入库；生成的工程树
   进 .gitignore，不入库——1 MB 的母版副本没有留存价值，日志里有清单与判定）。

判据口径与既有真机脚本一致：**编译绿 = compile_passed（exit_code 0）**，
不是"日志里没看到 error"。
"""

from __future__ import annotations

import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.generator import (  # noqa: E402
    build_output_tree_corpus,
    run_generation_gates,
)
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT_ROOT = HERE / "out_compile"


def _uvprojx_include_dirs(out_dir: Path) -> list[Path]:
    """最终 .uvprojx 的 IncludePath → 绝对目录（产物树复核的搜索目录）。"""
    uvprojx = next(out_dir.rglob("*.uvprojx"), None)
    if uvprojx is None:
        return []
    dirs: list[Path] = []
    try:
        root = ET.parse(uvprojx).getroot()
    except ET.ParseError:
        return []
    for el in root.findall("Targets/Target"):
        path_el = el.find(
            "TargetOption/TargetArmAds/Cads/VariousControls/IncludePath"
        )
        if path_el is None or not path_el.text:
            continue
        for entry in path_el.text.split(";"):
            if not entry.strip():
                continue
            p = Path(entry.strip().replace("\\", "/"))
            resolved = p if p.is_absolute() else (uvprojx.parent / p)
            try:
                dirs.append(resolved.resolve())
            except OSError:
                continue
    return dirs


def _cproject_include_dirs(out_dir: Path) -> list[Path]:
    """最终 .cproject 的 IncludePath → 绝对目录（mspm0 产物树复核用）。"""
    cproject = next(out_dir.rglob(".cproject"), None)
    if cproject is None:
        return []
    dirs: list[Path] = []
    try:
        root = ET.parse(cproject).getroot()
    except ET.ParseError:
        return []
    for opt in root.iter("option"):
        if opt.get("valueType") != "includePath":
            continue
        for vo in opt.findall("listOptionValue"):
            val = (vo.get("value") or "").strip()
            if not val:
                continue
            expanded = val.replace("${PROJECT_LOC}", str(cproject.parent)).replace(
                "${PROJECT_ROOT}", str(cproject.parent)
            )
            if "${" in expanded:
                continue
            try:
                dirs.append(Path(expanded).resolve())
            except OSError:
                continue
    return dirs


def _sse_events(client: TestClient, path: str, payload: dict) -> list[tuple[str, dict]]:
    """POST 一个 SSE 端点 → [(事件类型, data)]（断流前的全部事件）。"""
    events: list[tuple[str, dict]] = []
    with client.stream("POST", path, json=payload) as resp:
        assert resp.status_code == 200, f"{path} HTTP {resp.status_code}"
        event_type = ""
        for raw in resp.iter_lines():
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                body = line.split(":", 1)[1].strip()
                try:
                    events.append((event_type, json.loads(body or "null") or {}))
                except json.JSONDecodeError:
                    events.append((event_type, {"raw": body}))
    return events


def main() -> int:
    platform = (sys.argv[1] if len(sys.argv) > 1 else "stm32").strip()
    if platform not in ("stm32", "mspm0"):
        print("用法：verify-02-real-machine.py [stm32|mspm0]")
        return 2

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT, ignore_errors=True)
    OUT_ROOT.mkdir(parents=True)

    ctx = AppContext(
        config_path=OUT_ROOT / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=REPO / "library" / "modules",
            masters_dir=REPO / "library" / "masters",
        ),
        desktop_dir=lambda: OUT_ROOT,
    )
    client = TestClient(create_app(ctx))

    lines: list[str] = [f"# 工单 module-hwcheck/02 真机口径：{platform}", ""]

    # ① 走产品端点生成（只开串口：mspm0 双通道默认撞 PA22 是已知的库级默认重叠）
    payload = {
        "platform": platform,
        "debug_uart": True,
        "oled": False,
        "parent_dir": str(OUT_ROOT),
    }
    response = client.post("/api/hwcheck/generate", json=payload)
    lines.append(f"## ① POST /api/hwcheck/generate → HTTP {response.status_code}")
    assert response.status_code == 200, response.text
    generated = response.json()
    out_dir = Path(generated["output_dir"])
    lines.append(f"output_dir = {out_dir}")
    lines.append(f"modules    = {generated['modules']}")
    lines.append(f"checklist  = {[item['id'] for item in generated['checklist']]}")
    lines.append(f"build_hint = {generated['build_hint'] or '(空)'}")
    lines.append("")

    # ② 产物树复核（与生成前同一套门禁）
    search_dirs = (
        _uvprojx_include_dirs(out_dir) if platform == "stm32"
        else _cproject_include_dirs(out_dir)
    )
    corpus = build_output_tree_corpus(out_dir, platform, search_dirs)
    try:
        run_generation_gates(corpus, [], platform)
        lines.append("## ② 产物树门禁复核：PASS（0 问题）")
    except Exception as exc:  # noqa: BLE001 - 证据脚本要如实记下任何失败
        lines.append(f"## ② 产物树门禁复核：FAIL {type(exc).__name__}: {exc}")
    lines.append("")

    # ③ 真编译（产品端点，SSE）
    events = _sse_events(client, "/api/compile", {"output_dir": str(out_dir)})
    done = next((data for kind, data in events if kind == "done"), None)
    error = next((data for kind, data in events if kind == "error"), None)
    lines.append("## ③ POST /api/compile → SSE")
    lines.append(f"事件序列 = {[kind for kind, _ in events]}")
    if error is not None:
        lines.append(f"error = {error.get('message')}")
    if done is None:
        lines.append("**没有 done 事件 = 编译未完成（判据不成立）**")
    else:
        lines.append(f"command     = {' '.join(done.get('command') or [])}")
        lines.append(f"project_file= {done.get('project_file')}")
        lines.append(f"exit_code   = {done.get('exit_code')}")
        lines.append(f"passed      = {done.get('passed')}")
        lines.append(f"timed_out   = {done.get('timed_out')}")
        lines.append(f"duration    = {done.get('duration')}")
        lines.append(f"summary     = {done.get('summary')}")
        lines.append(f"parsed_errors = {json.dumps(done.get('parsed_errors'), ensure_ascii=False)}")
        lines.append("")
        lines.append("### 编译输出原文")
        lines.append("```")
        lines.append((done.get("error_text") or "").strip())
        lines.append("```")
    lines.append("")
    lines.append(f"结论：{'编译绿（passed=True）' if done and done.get('passed') else '未通过/未完成 —— 见上'}")
    lines.append("")

    # ④ 静态面：页面与新旧前端模块都真的能取到（新栏目/新端点要重启才生效，
    #    这里用进程内的 app 直接取，证明磁盘上的产物本身没问题）
    lines.append("## ④ 静态资源挂载")
    for path in ("/", "/js/fx/hwcheck.js", "/js/ui/hwcheck.js"):
        resp = client.get(path)
        lines.append(f"GET {path} → {resp.status_code}"
                     + (f"（{len(resp.content)} 字节）" if resp.status_code == 200 else ""))

    report = HERE / f"verify-02-{platform}-compile.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[证据已写入] {report}")
    return 0 if (done and done.get("passed")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
