"""真机验收（工单 fix-loop-progress/01）：2026C 注错 → 驱动 8000 服务复刻
前端修复中心主循环（index.html startFixCenter 状态机）——首编失败 → 每轮
fix-errors（previous_fixes 回喂上轮 done.fixes）→ applied==0 停（决策 1）/
>0 重编译验证，≤3 轮。

前置：8000 服务跑新代码（PYTHONPATH=src python -m contest_generator.webapp，
worktree 内启动）；2026C 赛题已在 ~/.contest_generator/topics/2026C。
运行：python .scratch/fix-loop-progress/real_fix_loop.py
产物：~/.contest_generator/real-tests/fix-loop-2026C（生成 + 注错 + 修复写回）
"""
import json
import shutil
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
OUT = Path.home() / ".contest_generator/real-tests/fix-loop-2026C"
WORK_ROOT = Path.home() / ".contest_generator"
PLATFORM = "stm32"
SLUGS = ["zigbee_uart", "zigbee_uart_key"]

# 生成用 main.c（骨架门禁只允许调用选中模块头文件里真实存在的函数）
MAIN_C_CLEAN = (
    '#include "zigbee_uart.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    zigbee_uart_init();\n"
    "    while (1)\n"
    "    {\n"
    "        if (g_key_id_updated)\n"
    "        {\n"
    "            g_key_id_updated = 0;\n"
    "        }\n"
    "    }\n"
    "}\n"
)

# 注错场景（sys.argv[1] 选择；缺省 comment = 工单验收场景——行尾注释干扰形态，
# 历史第 1 轮 skipped 高发）：
#   comment：裸行 + 行尾注释各一处（若第 1 轮部分 skipped → 第 2 轮回喂）
#   dup：裸行 + 两句完全相同的函数体（歧义 = 文档化 skipped 诱因——验证
#         0 applied 停滞停止 / 回喂后第 2 轮收敛两种终态）
INJECTIONS = {
    "comment": [
        "int zzz_fix_probe = UNDECLARED_SYMBOL_ZZZ;   /* 验收注入：制造编译错误 */\n",
        "int yyy_fix_probe = UNDECLARED_SYMBOL_YYY;\n",
    ],
    "dup": [
        "int yyy_fix_probe = UNDECLARED_SYMBOL_YYY;   /* 验收注入：制造编译错误 */\n",
        "\n",
        "int probe_a(void) { return UNDECLARED_DUP_ZZZ; }\n",
        "int probe_b(void) { return UNDECLARED_DUP_ZZZ; }\n",
    ],
}


def _sse(url: str, payload: dict) -> dict:
    """POST SSE 端点，收集事件为 {type: data}（终态 done / error 必须出现）。"""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    events: dict[str, dict] = {}
    with urllib.request.urlopen(request, timeout=600) as response:
        event_type = None
        for raw in response:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if line.startswith("event: "):
                event_type = line[len("event: "):].strip()
            elif line.startswith("data: ") and event_type:
                events[event_type] = json.loads(line[len("data: "):])
                event_type = None
    return events


def _post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def _main_c_content() -> str:
    return (OUT / "main.c").read_text(encoding="utf-8", errors="replace")


def _context_payload(error_text: str, previous_fixes: list | None) -> dict:
    payload: dict = {
        "output_dir": str(OUT),
        "error_text": error_text,
        "problem_text": (WORK_ROOT / "topics/2026C/topic.md").read_text(
            encoding="utf-8", errors="replace"
        ),
        "platform": PLATFORM,
        "slugs": SLUGS,
        "main_c": MAIN_C_CLEAN,  # 前端文本域内容（生成时骨架，修复后不更新——既有行为）
    }
    if previous_fixes is not None:
        payload["previous_fixes"] = previous_fixes
    return payload


def main() -> None:
    scenario = sys.argv[1] if len(sys.argv) > 1 else "comment"
    injection = INJECTIONS[scenario]
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows GBK 控制台防花
    print("=== 0) 生成 2026C stm32 工程（场景=%s） ===" % scenario)
    if OUT.exists():
        shutil.rmtree(OUT)
    result = _post_json(
        BASE + "/api/generate",
        {
            "platform": PLATFORM,
            "slugs": SLUGS,
            "main_c": MAIN_C_CLEAN,
            "output_dir": str(OUT),
            "topic_id": "2026C",
        },
    )
    print("generate ok:", result.get("output_dir", OUT))

    print("\n=== 1) 首编（正常工程 → 应 passed，循环不启动） ===")
    events = _sse(
        BASE + "/api/compile", {"platform": PLATFORM, "output_dir": str(OUT)}
    )
    first = events.get("done", {})
    print("passed:", first.get("passed"), "summary:", first.get("summary"))

    print("\n=== 2) 注错（场景=%s） ===" % scenario)
    lines = _main_c_content().splitlines(keepends=True)
    lines[1:1] = injection
    (OUT / "main.c").write_text("".join(lines), encoding="utf-8")
    print("injected at main.c:2-3")

    print("\n=== 3) 修复循环（复刻前端状态机 ≤3 轮，停滞检测 + 回喂） ===")
    events = _sse(
        BASE + "/api/compile", {"platform": PLATFORM, "output_dir": str(OUT)}
    )
    compile_done = events.get("done", {})
    error_text = compile_done.get("error_text", "")
    summary = compile_done.get("summary") or {}
    print(
        "首编注错后：passed=%s errors=%s"
        % (compile_done.get("passed"), summary.get("errors"))
    )
    previous_fixes = None  # 第 1 轮无回喂（与前端 lastFixDone=null 一致）
    for round_no in range(1, 4):
        print("\n--- 第 %d 轮修复（previous_fixes=%s） ---" % (
            round_no, "上轮 done.fixes" if previous_fixes is not None else "无"))
        events = _sse(BASE + "/api/fix-errors", _context_payload(error_text, previous_fixes))
        done = events.get("done") or {}
        fixes = done.get("fixes") or []
        applied = [f for f in fixes if f.get("status") == "applied"]
        skipped = [f for f in fixes if f.get("status") != "applied"]
        print("done.fixes 分布：applied=%d skipped=%d" % (len(applied), len(skipped)))
        for f in fixes:
            print("  [%s] %s:%s — %s" % (f["status"], f["file"], f["line"], f["reason"]))
        if not applied:
            print("STALL-STOP：本轮 0 applied → 停止循环（前端决策 1 文案，"
                  "不再白跑第 %d 轮重编译）" % (round_no + 1))
            return
        print("--- 第 %d 轮重编译验证 ---" % round_no)
        events = _sse(
            BASE + "/api/compile", {"platform": PLATFORM, "output_dir": str(OUT)}
        )
        compile_done = events.get("done", {})
        summary = compile_done.get("summary") or {}
        print("passed=%s errors=%s warnings=%s"
              % (compile_done.get("passed"), summary.get("errors"), summary.get("warnings")))
        if compile_done.get("passed"):
            print("CONVERGED：第 %d 轮重编译通过（0 Error）" % round_no)
            return
        error_text = compile_done.get("error_text", "")
        previous_fixes = fixes  # 回喂上轮 fixes（前端 lastFixDone 透传）
    print("达 3 轮上限仍未收敛：", summary)


if __name__ == "__main__":
    main()
