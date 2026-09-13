# -*- coding: utf-8 -*-
"""工单 07 前置诊断：**替换环节**为什么在工单 06 档③ 里没走完（零下载）。

假设：工单 06 的 `verify-06-tier3.py` 搭一次性工具根时只复制了 `src/` 与四个
顶层文件，**没复制 `tools/`**，于是 `full_apply.apply_full_package` 的拉起前
预检（`tool_root/tools/update-app.py` 是否存在）直接判不 ok。

这个探针不碰网络、不下载任何东西，只回答一件事：
**把 `tools/` 一起铺进工具根之后，预检过不过。**

用法：`python .scratch/resumable-download/probe-07-stage-preflight.py`
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# 与 verify-06-tier3.py 同款防带偏：site-packages 里残留的 editable 元数据指向
# firstep-sim 那份旧源码（见 docs/agents/local-environment.md 2.5）。
sys.path.insert(0, str(REPO / "src"))
for _name in [n for n in list(sys.modules)
              if n == "contest_generator" or n.startswith("contest_generator.")]:
    del sys.modules[_name]

from contest_generator import full_apply  # noqa: E402

LINES: list[str] = []


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


# 工单 06 那次实际铺进工具根的清单（照 verify-06-tier3.py 的 copytree 段）
TIER3_EXTRA_FILES = ("VERSIONS.md", "README.md", "requirements.txt", "pyproject.toml")


def stage(tool_root: Path, *, with_tools: bool) -> None:
    shutil.copytree(REPO / "src", tool_root / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for extra in TIER3_EXTRA_FILES:
        source = REPO / extra
        if source.is_file():
            shutil.copy2(source, tool_root / extra)
    if with_tools:
        (tool_root / "tools").mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / "tools" / "update-app.py",
                     tool_root / "tools" / "update-app.py")
        shutil.copy2(REPO / "tools" / "launcher-log.ps1",
                     tool_root / "tools" / "launcher-log.ps1")
    for script in ("start-app.vbs", "start-app.bat"):
        if (REPO / script).is_file():
            shutil.copy2(REPO / script, tool_root / script)


def try_apply(tool_root: Path, *, label: str) -> dict:
    """用假分卷 + 假 spawn 跑一次 apply_full_package：只验预检与命令构造。"""
    parts_dir = tool_root / "_fake"
    parts_dir.mkdir(parents=True, exist_ok=True)
    fake_zip = parts_dir / "firstep-full-v1.1.1.zip"
    fake_zip.write_bytes(b"PK\x05\x06" + b"\x00" * 18)   # 空 zip（只为过 is_file）
    spawned: list[list[str]] = []

    def fake_spawn(command, cwd, log_path):  # noqa: ANN001
        spawned.append(list(command))
        return 4242

    result = full_apply.apply_full_package(
        parts=[{"name": fake_zip.name, "path": str(fake_zip)}],
        updates_dir=tool_root / "_updates",
        tool_root=tool_root,
        version="v1.1.1",
        manifest_url="https://example.invalid/firstep-full-v1.1.1.manifest.json",
        port=8020,
        python=sys.executable,
        spawn=fake_spawn,
    )
    log(f"  [{label}] ok={result.ok}")
    log(f"           message={result.message}")
    log(f"           command={spawned[0] if spawned else '（没拉起）'}")
    return {"label": label, "ok": result.ok, "message": result.message,
            "command": spawned[0] if spawned else []}


def main() -> int:
    log("# 工单 07 前置诊断：替换环节的拉起前预检（零下载、零网络）")
    log("")
    log(f"仓库：{REPO}")
    log("")

    results: list[dict] = []
    work = Path(tempfile.mkdtemp(prefix="firstep-preflight-"))
    try:
        log("## 一、照工单 06 那次的口径铺工具根（只有 src/ + 四个顶层文件）")
        old = work / "tier3-way"
        stage(old, with_tools=False)
        log(f"  工具根：{old}")
        log(f"  tools/ 存在：{(old / 'tools').is_dir()}")
        results.append(try_apply(old, label="工单 06 口径"))

        log("")
        log("## 二、补上 tools/ 之后再跑一次")
        new = work / "with-tools"
        stage(new, with_tools=True)
        log(f"  工具根：{new}")
        log(f"  tools/update-app.py 存在：{(new / 'tools' / 'update-app.py').is_file()}")
        results.append(try_apply(new, label="补 tools/ 后"))

        log("")
        log("## 三、结论")
        passed = [r for r in results if r["ok"]]
        log(f"  预检通过：{len(passed)}/{len(results)}")
        if len(passed) == 1 and passed[0]["label"] == "补 tools/ 后":
            log("  → 假设成立：**工单 06 档③ 卡在「工具根没铺 tools/」，不是产品缺陷**。")
            log("     产品侧的拉起前预检工作正常（正因它拦下，才没出现「以为更新了其实没更新」）。")
        elif not passed:
            log("  → 两次都没过：还有别的缺失，见上面的 message。")
        else:
            log("  → 出乎意料：不带 tools/ 也过了，得另找原因。")
        (HERE / "verify-07-preflight.txt").write_text("\n".join(LINES) + "\n",
                                                     encoding="utf-8")
        (HERE / "verify-07-preflight.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        log("\n临时目录已清理")

    print("证据已写：verify-07-preflight.txt / .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
