"""第二十二轮探针（工单 real-acceptance/11 方向 ①）：落盘现场原始 instances 形态。

为什么要它：`[PROBE16][域拒绝]` 只打**异常文本**（「模块 k230 不支持多实例」），
看不出模型到底输出了什么——是 `[{...}]`（元素几个？）还是 `[]`。工单 11 的
方向 ②（单元素确定性降级 / ≥2 元素仍拒收）**取决于这个形态**，所以先取证再动刀。

做法：复用 probe-16 的全部装配（真产品链路 run_recommendation，不经 webapp），
在它之上多注入一处诊断——`select_modules.parse` 的域拒绝分支里，把**被拒时
模型输出的原始 JSON**（已解析为 dict 的 data）整份落盘，另附一份 instances
形态摘要（slug / 位置 / 元素数 / 原文）。

产物：`.scratch/recommend-domain-reject/instances-shape-22.txt`
（每行一条 JSON：{"error":…, "forms":[…], "raw":<整份模型输出>}）。

用法（GBK 控制台会因 ⚠ 崩溃，必须先设编码）：
    $env:PYTHONIOENCODING='utf-8'
    $env:PYTHONPATH='src'
    python .scratch/recommend-domain-reject/probe-22-instances-shape.py \
        --topic 2026H --platform mspm0 --attempts 2
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DUMP = HERE / "instances-shape-22.txt"

# 域拒绝分支（selection 的 SelectionError → LLMError 翻译点，锚点唯一），
# 在它之前把 data（本轮的模型原始 JSON，dict）与 instances 形态落盘。
ANCHOR = "            except SelectionError as exc:\n"
INJECTED = (
    "            except SelectionError as exc:\n"
    '                if "多实例" in str(exc):\n'
    "                    try:\n"
    "                        _p22_dump(data, str(exc))\n"
    "                        print('[PROBE22][形态落盘]', str(exc)[:80], flush=True)\n"
    "                    except Exception as _e22:\n"
    "                        print('[PROBE22][落盘失败]', _e22, flush=True)\n"
)

# 形态摘要助手 + 落盘（exec 进 llm 模块命名空间，磁盘源码零改动）
HELPER = '''

def _p22_forms(data):
    """模型输出里的 instances 形态清单：[(位置, slug, 值, 元素数)]。"""
    forms = []
    reqs = data.get("requirements")
    if isinstance(reqs, list):
        for i, req in enumerate(reqs):
            mods = req.get("modules") if isinstance(req, dict) else None
            if not isinstance(mods, list):
                continue
            for j, mod in enumerate(mods):
                if isinstance(mod, dict) and "instances" in mod:
                    value = mod.get("instances")
                    forms.append({
                        "path": "requirements[%d].modules[%d]" % (i, j),
                        "slug": mod.get("slug"),
                        "value": value,
                        "len": len(value) if isinstance(value, list) else None,
                        "type": type(value).__name__,
                    })
    mods = data.get("modules")
    if isinstance(mods, list):
        for i, mod in enumerate(mods):
            if isinstance(mod, dict) and "instances" in mod:
                value = mod.get("instances")
                forms.append({
                    "path": "modules[%d]" % i,
                    "slug": mod.get("slug"),
                    "value": value,
                    "len": len(value) if isinstance(value, list) else None,
                    "type": type(value).__name__,
                })
    return forms


def _p22_dump(data, error):
    from pathlib import Path as _Path
    import json as _json
    record = {"error": error, "forms": _p22_forms(data), "raw": data}
    with _Path(r"__DUMP_PATH__").open("a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record, ensure_ascii=False) + chr(10))
'''.replace("__DUMP_PATH__", str(DUMP))


def inject(src_path: Path) -> None:
    """probe-16 的三处诊断 + 本轮新增的形态落盘，一次 exec 进 llm 模块。"""
    spec = importlib.util.spec_from_file_location(
        "probe16", HERE / "probe-16-recommend-live.py"
    )
    p16 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p16)
    src = src_path.read_text(encoding="utf-8")
    for old, new in p16.ANCHORS:
        n = src.count(old)
        if n != 1:
            print(f"⚠ 锚点命中 {n} 处（跳过该注入点）：{old.strip()[:50]!r}")
            continue
        src = src.replace(old, new)
    n = src.count(ANCHOR)
    if n != 1:
        raise SystemExit(f"⚠ 形态注入锚点命中 {n} 处（应为 1），中止")
    src = src.replace(ANCHOR, INJECTED) + HELPER
    exec(compile(src, str(src_path), "exec"), p16.llm_mod.__dict__)
    return p16


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="2026H")
    parser.add_argument("--platform", default="mspm0")
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--clarify-answers", default="", help="JSON 文件：{问题: 答案}")
    args = parser.parse_args()

    clarify_answers: dict[str, str] = {}
    if args.clarify_answers:
        clarify_answers = json.loads(
            Path(args.clarify_answers).read_text(encoding="utf-8")
        )

    p16 = inject(REPO / "src" / "contest_generator" / "llm.py")
    print(f"[探针] 注入诊断行 + 形态落盘完成（磁盘 llm.py 零改动）；"
          f"topic={args.topic} platform={args.platform} attempts={args.attempts}",
          flush=True)
    DUMP.unlink(missing_ok=True)

    for attempt in range(1, args.attempts + 1):
        print(f"\n===== 第 {attempt}/{args.attempts} 次真实推荐 =====", flush=True)
        kind, data, rounds, questions, _vision = p16.run_once(
            args.topic, args.platform, clarify_answers
        )
        print(f"[结果] 终态 {kind}；收敛轮次 {rounds}；补问 {len(questions)} 条",
              flush=True)

    if not DUMP.exists():
        print("[形态] 本轮未出现「不支持多实例」违规（无现场可取证）", flush=True)
        return 1
    lines = DUMP.read_text(encoding="utf-8").splitlines()
    print(f"\n[形态] 共 {len(lines)} 条违规现场 → {DUMP}", flush=True)
    for line in lines:
        rec = json.loads(line)
        print(f"  · {rec['error']}", flush=True)
        for form in rec["forms"]:
            print(f"      {form['path']} slug={form['slug']} "
                  f"type={form['type']} len={form['len']} "
                  f"value={json.dumps(form['value'], ensure_ascii=False)[:200]}",
                  flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
