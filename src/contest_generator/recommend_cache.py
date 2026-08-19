"""推荐结果缓存：done 载荷落盘复用（工单 llm-cost-control/02，Web 端）。

机制照搬 CLI 验收脚本 generate_check.py 的 --reuse-recommend（键 / 指纹 /
载荷形状逐字兼容，双客户端对偶）：推荐段是回归大头（单题 ~10-15 min 真实
LLM 调用），同题重跑命中缓存直出 done 载荷。

缓存文件 = 用户配置目录下 cache/recommend_<key>.json：
    {"topic_key", "platform", "problem_sha256", "reference_ids",
     "clarify_sha256", "done": 推荐结果 dict}

- 键：topic_id 优先（历史赛题显式入口）；无 topic_id 用题面 sha256（题面变
  → 键变自然失效）。
- 校验：题面指纹 / 平台 / 键任一不符 = 失效（推荐层按平台过滤模块，跨平台
  复用会假绿）；reference_ids / clarify 指纹为参数指纹——只进真实请求体，
  复用路径不一致打警告不阻断（换参数迭代的用途）。
- 旁路：损坏文件 / 写失败静默（缓存是省钱优化，绝不阻塞生成与修复）。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

# Web 端缓存目录：用户配置目录（config.json 同级）下的 cache/
DEFAULT_CACHE_DIR = Path.home() / ".contest_generator" / "cache"

_REQUIRED_FIELDS = ("topic_key", "platform", "problem_sha256")


def problem_fingerprint(problem_text: str) -> str:
    """题面 sha256 指纹（无 topic_id 时兼作缓存键；复用时校验题面未变）。"""
    return hashlib.sha256(problem_text.encode("utf-8")).hexdigest()


def clarify_fingerprint(
    clarify_hist: Sequence[Mapping[str, str]],
) -> str:
    """clarify 历史指纹（参数指纹，复用警告比对用）。

    顺序不敏感（map 预置 + 补问追加的先后不影响内容语义）：逐条序列化后
    排序再哈希——同内容不同顺序 = 同指纹，避免"补问答案进 map 后重跑"误报。
    """
    items = sorted(
        json.dumps(
            {"question": h["question"], "answer": h["answer"]},
            ensure_ascii=False,
            sort_keys=True,
        )
        for h in clarify_hist
    )
    return hashlib.sha256(json.dumps(items, ensure_ascii=False).encode("utf-8")).hexdigest()


def cache_key(topic_id: str | None, problem_text: str) -> str:
    """缓存键：topic_id 优先；无 topic_id（手动准入）用题面 sha256。"""
    return topic_id or problem_fingerprint(problem_text)


def recommend_cache_path(key: str, cache_dir: Path | None = None) -> Path:
    """缓存键 → 缓存文件路径 recommend_<key>.json（目录覆盖：显式 > 环境
    变量 > 缺省用户配置目录）。"""
    base = cache_dir or Path(
        os.environ.get("FIRSTEP_RECOMMEND_CACHE_DIR") or DEFAULT_CACHE_DIR
    )
    return base / f"recommend_{key}.json"


def cache_recommend(
    path: Path,
    done: dict,
    *,
    topic_key: str,
    problem_text: str,
    platform: str,
    reference_ids: Sequence[str] = (),
    clarify_hist: Sequence[Mapping[str, str]] = (),
) -> None:
    """写缓存：done 载荷逐字 + 元数据（与 CLI generate_check 格式逐字兼容）。

    写失败静默（旁路）；done 必须含 modules 列表（下游消费契约）。
    """
    payload = {
        "topic_key": topic_key,
        "platform": platform,
        "problem_sha256": problem_fingerprint(problem_text),
        "reference_ids": list(reference_ids),
        "clarify_sha256": clarify_fingerprint(clarify_hist),
        "done": done,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass  # 旁路：写失败不阻塞主流程


def load_recommend(path: Path) -> dict:
    """读缓存：json 读回 + 形状校验；坏 json / 缺字段 → ValueError。

    与 CLI 同款校验（复用安全网——坏缓存宁可报错走真实推荐，不带假数据
    进下游）。
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"缓存不可读: {path}（{exc}）") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"缓存形状错误: {path}（顶层非对象）")
    for field in _REQUIRED_FIELDS:
        if not isinstance(raw.get(field), str) or not raw[field]:
            raise ValueError(f"缓存形状错误: {path}（缺 {field}）")
    done = raw.get("done")
    if not isinstance(done, dict) or not isinstance(done.get("modules"), list):
        raise ValueError(f"缓存形状错误: {path}（done 非对象或缺 modules 列表）")
    return raw


def validate_recommend(
    cached: Mapping[str, Any],
    *,
    topic_key: str,
    problem_text: str,
    platform: str,
) -> tuple[bool, str]:
    """缓存是否仍有效：题面 / 平台 / 键任一不符 → (False, 原因)。

    调用方拿 False 走真实推荐（Web 交互场景不报错退出——CLI 回归脚本的
    "缺失即报错"语义不适用）。
    """
    if cached.get("problem_sha256") != problem_fingerprint(problem_text):
        return False, "题面已变化"
    if cached.get("platform") != platform:
        return False, "平台与缓存时不同"
    if cached.get("topic_key") != topic_key:
        return False, "赛题键与缓存时不同"
    return True, ""


def parameter_warnings(
    cached: Mapping[str, Any],
    *,
    reference_ids: Sequence[str],
    clarify_hist: Sequence[Mapping[str, str]],
) -> list[str]:
    """参数指纹警告：reference_ids / clarify 内容只进真实请求体，复用路径
    否则不感知其变化——不一致打警告不阻断；旧格式缓存无元数据则跳过比对。"""
    warns: list[str] = []
    if "reference_ids" in cached and sorted(cached["reference_ids"]) != sorted(reference_ids):
        warns.append(
            f"reference_ids 与生成缓存时不同"
            f"（缓存 {sorted(cached['reference_ids'])}，本次 {sorted(reference_ids)}）"
        )
    if "clarify_sha256" in cached and cached["clarify_sha256"] != clarify_fingerprint(
        clarify_hist
    ):
        warns.append("clarifications 内容与生成缓存时不同")
    return warns
