# -*- coding: utf-8 -*-
"""临时探针（不属于 B3 证据）：直调生成函数，把 500 的服务端栈逼出来。

为什么需要它：`/api/generate` 的 `_map_errors` 只回一句通用中文 500，
栈进的是服务端 stderr（uvicorn 日志），HTTP 侧拿不到。B3 要的是**端点**行为，
所以证据仍以端点为准；这里只为「为什么 500」定位。
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(r"C:\Users\luoji\Desktop\firstep")
SAMPLE = REPO / ".scratch" / "real-run" / "out_16_mspm0_min" / ".contest_context.json"
sys.path.insert(0, str(REPO / "src"))

from contest_generator.generator import generate_project  # noqa: E402

sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
out = Path(tempfile.mkdtemp(prefix="probe-b3-")) / "out_mspm0"
try:
    summary = generate_project(
        platform=sample["platform"],
        slugs=sample["slugs"],
        main_c_content=sample["main_c"],
        output_dir=out,
        module_library_dir=REPO / "library" / "modules",
        masters_dir=REPO / "library" / "masters",
        ccs_tools=None,
        bindings=None,
        instances=[],
        python_templates=None,
        score_points=None,
        problem_text="",
        topic_id="",
        qa_text="",
        requirements=[],
        references=[],
        tool_version="1.2.1",
        report_draft_text="",
    )
    print("OK:", summary.output_dir)
    print("settings:", sorted(p.name for p in (out / ".settings").glob("*")))
except Exception:
    traceback.print_exc()
