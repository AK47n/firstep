"""第十六轮诊断探针：捕获 select_modules 的真实拒绝理由（**不改 src**）。

背景（挂账单 A8 实测）：2026H / mspm0 推荐真机跑出
「AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足或请求内容不被接受）」
—— 遥测显示 http_status=200 / parse_status=parse_error / error_kind=client /
attempts=1（未重试），说明是**产品自己**判定的确定性失败，但错误文案被
`errors.llm_error_message` 的 client 分支统一换成了一句通用话术，**真实理由
看不见**。本探针用同一份 `llm.py` 源码（内存注入一行行号标记，磁盘文件零改动）
复跑一次真实的 select_modules，把真实异常打出来定性。

做法：读 `src/contest_generator/llm.py` 源码 → 在
`raise LLMError(str(exc), kind=ERROR_KIND_CLIENT) from exc`（选模块域拒绝翻译点）
与 `_raise_retry_exhausted` 调用前各插一行 `print`（带 `# PROBE16` 标记）→
`exec` 到 `contest_generator.llm` 的模块命名空间中（`exec(code, mod.__dict__)`）
——所有既有符号原地更新，import 链、dataclass 注册、其它模块已持有的引用全部
不变（比 importlib.reload 稳）。`print` 在 exec 时解析该命名空间的 `__builtins__`，
不受影响。

用法：
    $env:PYTHONPATH='src'; python .scratch/recommend-domain-reject/probe-16-select-reject.py \
        --topic 2026H --platform mspm0
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

import contest_generator.llm as llm_mod  # noqa: E402
from contest_generator.config import load_config  # noqa: E402
from contest_generator.generator import resolve_topic_context  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402

# 注入点（逐字匹配 llm.py 现状；匹配不到就大声失败，不静默跳过）
ANCHORS = (
    (
        '                raise LLMError(str(exc), kind=ERROR_KIND_CLIENT) from exc\n',
        '                print("[PROBE16] 域拒绝 SelectionError →", type(exc).__name__,\n'
        '                      "|", str(exc)[:900], flush=True)\n'
        '                raise LLMError(str(exc), kind=ERROR_KIND_CLIENT) from exc\n',
    ),
    (
        '        _raise_retry_exhausted(label, attempts, last_error)\n',
        '        print("[PROBE16] _retry_parse 重试耗尽 last_error=", type(last_error).__name__,\n'
        '              "| kind=", getattr(last_error, "kind", None),\n'
        '              "|", str(last_error)[:900], flush=True)\n'
        '        _raise_retry_exhausted(label, attempts, last_error)\n',
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="2026H")
    parser.add_argument("--platform", default="mspm0")
    args = parser.parse_args()

    src = (REPO / "src" / "contest_generator" / "llm.py").read_text(encoding="utf-8")
    original = src
    for old, new in ANCHORS:
        if src.count(old) != 1:
            print(f"✗ 注入锚点不唯一（{src.count(old)} 处）：{old[:60]!r}")
            return 2
        src = src.replace(old, new)
    print(f"[探针] 注入 {len(ANCHORS)} 处诊断行（磁盘 llm.py 零改动，"
          f"{len(original)} → {len(src)} 字符）")
    try:
        exec(compile(src, str(REPO / "src/contest_generator/llm.py"), "exec"),
             llm_mod.__dict__)
    except Exception as exc:  # noqa: BLE001
        print(f"✗ exec 注入版 llm.py 失败：{type(exc).__name__}: {exc}")
        return 2

    cfg = load_config()
    topic_md = REPO / "library" / "topics" / args.topic / "topic.md"
    problem_text = topic_md.read_text(encoding="utf-8")
    entries = list_modules(REPO / "library" / "modules")
    manifests = list(entries)   # list_modules 直接返回 ModuleManifest 序列
    manifest_summaries = build_manifest_summaries(manifests)
    print(f"[探针] 题面 {topic_md.name} {len(problem_text)} 字符；"
          f"摘要行 {len(manifest_summaries)} 条 / 平台 {args.platform}")

    client = llm_mod.DeepSeekLLM(cfg)
    try:
        selection = client.select_modules(
            problem_text,
            manifest_summaries,
            (),
            {},
            {},
            (),
        )
    except Exception as exc:  # noqa: BLE001 - 探针就是要看真实异常
        print(f"\n[结果] 失败：{type(exc).__name__} kind={getattr(exc, 'kind', None)}"
              f"\n       message={str(exc)[:500]}")
        print("        ↑ 若上面有 [PROBE16] 行，其内容即真实拒绝理由"
              "（产品文案把它换成通用话术 = 可报告缺陷）")
        return 1
    slugs = [getattr(m, "slug", m) for m in selection.modules]
    print(f"\n[结果] 成功（未复现拒绝）：模块 {slugs}；"
          f"converged={getattr(selection, 'converged', None)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
