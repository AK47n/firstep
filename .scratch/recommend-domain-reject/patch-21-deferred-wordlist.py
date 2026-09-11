# -*- coding: utf-8 -*-
"""工单 real-acceptance/10 数据补丁：顺延批 27 条方案裸名入 models（纯数据，零代码）。

**落点不手抄**——与工单 08 先例同款：本脚本机械反查每条顺延名的归属行
（判据 = name 命中某行 `solutions[].name`，或该方案名的**去括号裸名**），
要求每条**恰好命中一行**（0 = 需人工裁，>1 = 歧义），否则大声失败。

**幂等**：一律从基线副本（`.scratch/recommend-domain-reject/wordlist-before-21.json`，
= 单 08 落盘后的 git HEAD 版）重新生成，不叠加在现状之上——否则重跑会把同一批
名字再加一遍而自检只测「这一条」的增量。

**双重守卫**（工单验收标准）：
- 词表段实发**未被截断**（`WORDLIST_PROMPT_BYTES` 内，全量送达——截断 = 模型看不到
  合法名 = 本工单要治的病）；
- 词表段增量 ≤ 权威口径的现有余量扣掉活动余量（余量来源 = 单 05 全文段 25600→23400
  后的实测 3548B；本批实测只需 ≈2529B，**不动任何段预算常量**）。

跑法（仓库根）：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/recommend-domain-reject/patch-21-deferred-wordlist.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "src" / "contest_generator" / "wordlist.json"
DIR = ROOT / ".scratch" / "recommend-domain-reject"
BASELINE = DIR / "wordlist-before-21.json"
DEFERRED = DIR / "deferred-18.txt"
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.budget import wire_size  # noqa: E402
from contest_generator.llm import (  # noqa: E402
    WORDLIST_PROMPT_BYTES,
    _wordlist_prompt_segment,
)
from contest_generator.wordlist import (  # noqa: E402
    format_wordlist_prompt,
    load_wordlist,
)

# 权威口径（单 05 段级重分配后的实测）：mspm0 最坏形态距断言边界 129024 的余量。
# 本批为纯数据改动，只需确认增量在这笔余量内——**不改任何段预算常量**。
HEADROOM_BYTES = 3548
# 活动余量（自设，非契约；与 measure-20-deferred-headroom.py 同值）：留呼吸位
ACTIVITY_MARGIN = 512


def deferred_names() -> list[str]:
    """deferred-18.txt 里的顺延名（首行是说明，名字按「、」分隔）。"""
    text = DEFERRED.read_text(encoding="utf-8")
    body = text.split("：", 1)[-1] if "：" in text else text
    return [p.strip() for p in body.replace("\n", "").split("、") if p.strip()]


def bare(name: str) -> str:
    """方案名的去括号裸名（判据单源写法，与 probe-21 / patch-18 同款）。"""
    return re.sub(r"（[^）]*）", "", name).strip()


def landing_points(data: list, names: list[str]) -> dict[str, str]:
    """机械反查：顺延名 → 归属行 category（每条必须恰好一行）。"""
    found: dict[str, set[str]] = {name: set() for name in names}
    for item in data:
        for option in item.get("solutions") or []:
            for candidate in (option["name"], bare(option["name"])):
                if candidate in found:
                    found[candidate].add(item["category"])
    empty = [n for n, cats in found.items() if not cats]
    ambiguous = [n for n, cats in found.items() if len(cats) > 1]
    if empty:
        raise SystemExit(f"反查无落点（需人工裁）：{'、'.join(empty)}")
    if ambiguous:
        raise SystemExit(
            "反查歧义（命中多行）："
            + "；".join(f"{n} → {'/'.join(sorted(found[n]))}" for n in ambiguous)
        )
    return {name: next(iter(found[name])) for name in names}


def _groups_of(data: list) -> tuple:
    """把 JSON 数据投影成词表组（走真加载路径，口径与 DEFAULT_WORDLIST 一致）。

    lib_slugs=None：本脚本只关心 models/solutions 文本形态，lib_modules 引用
    校验归 tests/test_wordlist.py 的既有用例（不在此重复）。
    """
    import tempfile

    handle = tempfile.NamedTemporaryFile(
        "wb", suffix="-wordlist-trial.json", delete=False
    )
    try:
        handle.write((json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8"))
        handle.close()
        return load_wordlist(Path(handle.name), lib_slugs=None)
    finally:
        Path(handle.name).unlink(missing_ok=True)


def segment_wire(data: list) -> int:
    """词表段**实发**字节（截断感知，生产路径 format_wordlist_prompt + fit）。"""
    return wire_size(_wordlist_prompt_segment(_groups_of(data)))


def main() -> int:
    if not BASELINE.exists():
        raise SystemExit(
            f"基线副本不存在：{BASELINE}（用 git show HEAD:src/contest_generator/"
            "wordlist.json 落一份）"
        )
    data = json.loads(BASELINE.read_bytes().decode("utf-8"))
    names = deferred_names()
    home = landing_points(data, names)

    # 落点分布（保序打印，作证据留档）
    by_category: dict[str, list[str]] = {}
    for name in names:
        by_category.setdefault(home[name], []).append(name)
    print(f"顺延批 {len(names)} 条，机械反查落点跨 {len(by_category)} 行：")
    for category, group_names in sorted(
        by_category.items(), key=lambda item: -len(item[1])
    ):
        print(f"  [{category}] +{len(group_names)}：{'、'.join(group_names)}")

    # 去重保序写入（已在 models 的不重复加）
    added: dict[str, list[str]] = {}
    skipped: list[str] = []
    for item in data:
        wanted = by_category.get(item["category"], [])
        if not wanted:
            continue
        models = item.setdefault("models", [])
        for name in wanted:
            if name in models:
                skipped.append(name)
                continue
            models.append(name)
            added.setdefault(item["category"], []).append(name)

    base_wire = segment_wire(json.loads(BASELINE.read_bytes().decode("utf-8")))
    after_wire = segment_wire(data)
    delta = after_wire - base_wire
    print(f"\n词表段实发 {base_wire} → {after_wire}B（+{delta}）"
          f"  预算={WORDLIST_PROMPT_BYTES}B")
    if skipped:
        print(f"已在 models、未重复加：{'、'.join(skipped)}")

    # 守卫一：段未截断（全量送达）
    groups = _groups_of(data)
    if _wordlist_prompt_segment(groups) != format_wordlist_prompt(groups):
        raise SystemExit("词表段被 WORDLIST_PROMPT_BYTES 截断——全量送达契约破了")
    print(f"截断守卫：未截断（全量送达，余 {WORDLIST_PROMPT_BYTES - after_wire}B）")

    # 守卫二：增量在权威口径余量内（不动任何段预算常量）
    budget = HEADROOM_BYTES - ACTIVITY_MARGIN
    if delta > budget:
        raise SystemExit(
            f"词表段增量 {delta}B 超出可用余量 {budget}B"
            f"（权威余量 {HEADROOM_BYTES} − 活动余量 {ACTIVITY_MARGIN}）"
            "——须停下来记决策点，别顺手改段预算常量"
        )
    print(f"预算守卫：增量 {delta}B ≤ {budget}B"
          f"（权威余量 {HEADROOM_BYTES} − 活动余量 {ACTIVITY_MARGIN}）")

    PATH.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(f"\n已落盘 {PATH.relative_to(ROOT)}（+{sum(len(v) for v in added.values())} 条裸名）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
