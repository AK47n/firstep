"""按需视觉问答（工单 recommend-vision-qa/02）：推荐澄清阶段的「图内信息
问题」自动消化——条目 PDF 渲染题面页 → 视觉模型针对性作答。

薄传输层：不 import 生成流程（照 vision.py 先例，装配由调用方注入）；
渲染 / 视觉调用均为模块级函数引用 = 测试 monkeypatch 接缝（照 extraction
先例）。任何失败 / 否定回答 → None（调用方转用户——视觉是增强不是阻塞，
绝不抛出，绝不让推荐流程崩溃）。
"""

from __future__ import annotations

from pathlib import Path

from .extraction import _render_page_png, locate_topic_pages
from .vision import (
    DEFAULT_VISION_BASE_URL,
    DEFAULT_VISION_MODEL,
    describe_image_cached,
)

# 视觉回答否定词（命中任一 → 判「图中无此信息」，返回 None 转用户）。
# 宁缺毋滥：误判的代价只是问题转回用户，而错误的答案会污染澄清历史
# （澄清历史原样喂给收敛模型，比「问用户」危害大得多）
VISION_NEGATIVE_PATTERNS = (
    "没有",
    "未找到",
    "图上无",
    "图中无",
    "无法",
    "不确定",
    "无相关信息",
)


def _qa_prompt(question: str) -> str:
    """问题 → 视觉提示词：只回答该问题；图里没有就明说（否定词判定依赖）。"""
    return (
        "这是电子设计竞赛题面中的一页，页内有示意图。"
        f"请只回答下面这个问题：\n{question}\n"
        "如果图中没有相关信息，只回复「图中没有相关信息」。"
    )


def answer_figure_question(
    pdf_path: Path,
    problem_text: str,
    question: str,
    *,
    vision_base_url: str = DEFAULT_VISION_BASE_URL,
    vision_api_key: str = "",
    vision_model: str = DEFAULT_VISION_MODEL,
    observation_collector: object | None = None,
) -> str | None:
    """条目 PDF + 题面 + 问题 → 视觉答案；无答案 → None（调用方转用户）。

    链路：locate_topic_pages 文本层定位题面页（(start, end) 开区间，与
    enrich 图注同款——共享汇总 PDF 与单条目专属 PDF 统一走定位）→ 逐页
    _render_page_png → describe_image_cached(png, "image/png", prompt=问题
    引导)（同页同问题缓存命中不重发请求/花钱，键已含 prompt 互不串答）。

    降级（全部静默，绝不抛出）：定位失败 / 定位抛错（坏 PDF、无 PyMuPDF）
    → None，不冒险全文档渲染（共享汇总 PDF 渲染全文档成本不可接受）；单页
    渲染失败 / 视觉失败 → 跳过该页；回答命中否定词（图中没有相关信息等）
    → 跳过；多页实质答案换行拼接；全部落空 → None。
    """
    try:
        page_range = locate_topic_pages(pdf_path, problem_text)
    except Exception:
        return None  # 定位抛错（坏 PDF 等）：判无，绝不阻塞推荐流程
    if page_range is None:
        return None
    prompt = _qa_prompt(question)
    answers: list[str] = []
    for page_no in range(*page_range):
        try:
            png = _render_page_png(pdf_path, page_no)
            if png is None:
                continue
            text = describe_image_cached(
                png,
                "image/png",
                prompt,
                base_url=vision_base_url,
                api_key=vision_api_key,
                model=vision_model,
                observation_collector=observation_collector,
            ).strip()
        except Exception:
            continue  # 渲染 / 视觉失败（含未配置 / 网络 / 限流）：跳过该页
        if not text or any(pattern in text for pattern in VISION_NEGATIVE_PATTERNS):
            continue
        answers.append(text)
    return "\n".join(answers) if answers else None
