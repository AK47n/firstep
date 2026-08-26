"""赛题库核心：长 PDF 拆条 → 用户逐条校对 → 确认入库（事务）+ 编号解析。

流程（素材库 spec + ADR 0006）：用户导入历年真题长 PDF → 拆条（短全文走
LLM，协议在 llm 层；超长全文走确定性分块 split_topics_document——flash
输出预算有限会静默漏题，纯文本规则零 AI 改写）→ 用户逐条校对（改年份 /
题号 / 题面）→ 确认入库。磁盘目录即数据库（与模块库同风格）：一条目一
目录（目录名 = 赛题编号），题面全文落 topic.md，原 PDF 复制保留在条目
目录（AI 拆错可查原文），manifest.json 记录年份 / 编号 / 题面文件名 /
原 PDF 文件名 / 附带程序目录。附带程序用引用方式（字段存绝对路径，不
复制）——源工程还要继续编辑使用，复制会制造两份（2026C 钥匙/锁两套即
此形态）。

编号解析："2026C"（年份 + 题号）→ 题面全文，供生成入口与 AI 理解使用；
查无此条明确报错（不猜测编造）。

确认入库是事务（与提炼确认同风格）：全部校验（至少一道题 / 编号格式与不
重复 / 题面非空 / 原 PDF 存在 / 附带程序目录存在 / 编号未被占用）都在落盘
前完成，落盘中途失败清理全部已建条目目录——任何失败都不留半成品。赛题库
的物理位置由调用方传入（webapp 取模块库同级 topics/，配置字段后续工单加），
测试用 tmp_path。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .autocommit import commit_after_write
from .entry_store import (
    StoreError,
    StoreParseError,
    StoreReadError,
    StoreShapeError,
    delete_entry,
    entry_transaction,
    iter_entry_dirs,
    read_json,
    require_str,
    validate_store_key,
    write_json,
)
from .extraction import (
    locate_topic_pages,
    pdf_figure_annotations,
    pdf_image_notes,
    pdf_page_render_notes,
)
from .manifest import MANIFEST_FILENAME

# 视觉图注最小实质长度（工单 topic-vision-pages/02）：去壳（[示意图N：]）
# 后低于此值视为无实质内容（视觉对装饰图/空图返回「无实质内容」等短描述）
# → 不写回题面
MIN_FIGURE_NOTE_CHARS = 8


def _substantive_text(notes: str) -> str:
    """图注段去壳后的实质文本（去 [示意图N： / [图N 标注] / [图N 标注： 与空白）。

    渲染视觉段 `[图N 标注：<描述>]`（工单 topic-vision-render/01）与文字标注
    块 `[图N 标注]` 同前缀——冒号形态一并剥离，MIN_FIGURE_NOTE_CHARS 守卫
    对两种视觉产物（示意图 / 渲染段）都生效。
    """
    import re

    stripped = re.sub(r"\[示意图\d+：|\]|\[图\s*\d+\s*标注[：]?", "", notes)
    return "".join(stripped.split())

TOPIC_MD_FILENAME = "topic.md"  # 题面全文落盘文件名（条目目录内，唯一出处）


class TopicError(ValueError):
    """赛题库操作失败（条目不存在、编号冲突、题面 / 原 PDF 缺失等）。"""


# ---------------------------------------------------------------------------
# 赛题编号（key 的唯一出处）与拆条草稿模型：赛题库领域的模型层，llm 协议层
# 从这里取类型（拆条解析 / 编号提取消费），不反向定义。
# ---------------------------------------------------------------------------

# 赛题编号格式（key 的唯一出处）：4 位年份 + 单个大写字母题号（电赛官方
# 题号形态，如 2026C）；入库目录名与编号解析的查找键都按它校验（非法编号 =
# 路径穿越风险，入口拦截）。大小写收紧为单一大写字母：小写 / 多字母编号在
# 大小写不敏感的文件系统（Windows）上会与既有条目撞目录，跨平台行为不一致
# ——宁可拆条大声失败，也不让用户在校对页见到无法入库的编号。
TOPIC_KEY_PATTERN = re.compile(r"^(\d{4})([A-Z])$")


def validate_topic_key(key: str) -> str | None:
    """赛题编号格式校验（TOPIC_KEY_PATTERN 的配套文案，唯一出处）。

    合法返回 None，非法返回中文错误说明。拆条解析 / 编号提取 / 入库校验
    共用——文案只在此一处，改格式只动这里（与 TRUNCATION_NOTICE 同款
    单源约定，避免各层文案漂移）。执行走 entry_store 原语（validate_store_key），
    正则与文案仍归本模块。
    """
    try:
        validate_store_key(key, TOPIC_KEY_PATTERN, "赛题编号")
    except StoreError:
        return (
            f"赛题编号格式非法：{key!r}"
            "（须为 4 位年份 + 单个大写字母题号，如 2026C）"
        )
    return None


@dataclass(frozen=True)
class TopicDraft:
    """AI 拆条产物：一道赛题的年份 / 题号 / 题面全文（用户确认前的草稿）。

    key = 年份 + 题号（如 "2026C"），编号解析的查找键与入库目录名。
    """

    year: str
    number: str
    problem_text: str

    @property
    def key(self) -> str:
        return f"{self.year}{self.number}"

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "year": self.year,
            "number": self.number,
            "problem_text": self.problem_text,
        }


@dataclass(frozen=True)
class TopicEntry:
    """赛题条目（磁盘目录即数据库的加载形态：manifest + 题面 .md）。

    题面全文从条目目录的 topic.md 读（problem_md 字段记文件名）；原 PDF
    文件名与附带程序目录（绝对路径）记录在 manifest。
    """

    year: str
    number: str
    problem_text: str  # 题面全文
    problem_md: str = TOPIC_MD_FILENAME
    original_pdf: str = ""  # 原 PDF 文件名（保留在条目目录，AI 拆错可查原文）
    programs: tuple[str, ...] = ()  # 附带程序目录（绝对路径，引用方式）
    hint_module_groups: tuple[str, ...] = ()  # 功能组 hint（工单 recommend-
    # exclusive-groups/02）：赛题疑似需要但 AI 未命中时出兜底选择卡（组 id
    # 清单，缺省空；id 库内无对应组时推荐链路静默忽略）

    @property
    def key(self) -> str:
        """赛题编号（"2026C" = 年份 + 题号，编号解析的查找键）。"""
        return f"{self.year}{self.number}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "year": self.year,
            "number": self.number,
            "problem_text": self.problem_text,
            "problem_md": self.problem_md,
            "original_pdf": self.original_pdf,
            "programs": list(self.programs),
            "hint_module_groups": list(self.hint_module_groups),
        }


def confirm_topics(
    topic_library_root: Path,
    pdf_path: Path,
    entries: Sequence[TopicDraft],
    program_dirs: Sequence[Path | str] = (),
    pdf_filename: str = "",
) -> tuple[TopicEntry, ...]:
    """确认入库（事务）：全部校验通过后逐条落盘，中途失败清理不留半成品。

    一条目一目录（目录名 = 编号）：题面全文落 topic.md、原 PDF 复制进条目
    目录（AI 拆错可查原文）、manifest.json 记录字段与附带程序目录（引用
    方式——源工程还要编辑使用，复制会制造两份）。任何校验失败都在落盘前：
    目录都没建，绝无半成品。
    """
    _validate_entries(entries)
    if not pdf_path.is_file():
        raise TopicError(f"原 PDF 文件不存在：{pdf_path}")
    pdf_name = _resolve_pdf_name(pdf_filename)
    normalized_programs = tuple(_normalize_program_dir(program) for program in program_dirs)
    for program in normalized_programs:
        if not Path(program).is_dir():
            raise TopicError(f"附带程序目录不存在：{program}")
    for draft in entries:
        if (topic_library_root / draft.key).exists():
            raise TopicError(f"题库中已存在该编号的赛题：{draft.key}")

    with entry_transaction(topic_library_root, [draft.key for draft in entries]) as dirs:
        for draft, entry_dir in zip(entries, dirs):
            shutil.copy2(pdf_path, entry_dir / pdf_name)
            (entry_dir / TOPIC_MD_FILENAME).write_text(
                draft.problem_text, encoding="utf-8"
            )
            write_json(
                entry_dir,
                MANIFEST_FILENAME,
                {
                    "year": draft.year,
                    "number": draft.number,
                    "problem_md": TOPIC_MD_FILENAME,
                    "original_pdf": pdf_name,
                    "programs": list(normalized_programs),
                },
            )
    commit_after_write(topic_library_root, "lib: confirm topics")
    return tuple(resolve_number(topic_library_root, draft.key) for draft in entries)


def resolve_number(topic_library_root: Path, key: str) -> TopicEntry:
    """编号解析服务："2026C" → 题面全文（供生成入口与 AI 理解使用）。

    查无此条明确报错（不猜测编造）；编号格式非法先拒绝——目录名由编号
    决定，非法编号 = 路径穿越风险，入口拦截。
    """
    entry_dir = _entry_dir(topic_library_root, key)
    if not entry_dir.is_dir():
        raise TopicError(f"题库中没有该编号的赛题：{key}")
    return _load_entry(entry_dir)


def enrich_topic_image_notes(
    topic_library_root: Path,
    key: str,
    *,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
    observation_collector: object | None = None,
    detail_qa: bool = True,
) -> TopicEntry:
    """存量条目补图注（工单 topic-vision-notes/02/03）：题面引用图（"图N"）但
    无图注、且原 PDF 仍在条目目录内 → 生成图注段，追加题面文末（空行分隔，
    不破坏原文结构）并写回，返回补图注后的条目。

    三级生成（工单 topic-vision-render/01，视觉优先）：**渲染视觉优先**——
    矢量图（无栅格图对象，视觉提取不到）渲染成位图后走视觉通道
    （pdf_page_render_notes，DeepSeek 视觉模型，产出 `[图N 标注：<描述>]`
    ——2021F 图1 实测：文字标注只留碎片词、渲染视觉完整还原尺寸标注与
    红实线走向）；视觉失败（未配置 / 渲染不可用 / 网络）→ **文字标注兜底**
    （pdf_figure_annotations 按坐标重建布局，零额度）；文字层也为空 →
    **内嵌栅格图视觉**（pdf_image_notes）。

    共享 PDF（工单 topic-vision-pages/01）：真题汇总 PDF 被多个赛题条目共引
    ——全文档扫描会把**其它题**的图注追进当前题面（2024H 曾把约 280 行别的
    题的 [图N 标注] 追加进 2024H，污染推荐素材；取题面反复触发补图注 + 自动
    提交，清洗后又被追尾）。共享 PDF → locate_topic_pages 定位题面正文页，
    只在该页范围提取（别的题的图天然隔离）；定位失败（扫描件 / 不匹配）→
    跳过（宁可没有图注，也不污染题面）。单条目专属 PDF（如 2026C）全文档
    照常（单题 PDF 无跨题污染风险，最小回归面）。

    幂等：题面已含 `[示意图` 或 `[图N 标注` 标注 = 跳过不跑（重复取题面不
    重复消耗；渲染视觉段 `[图N 标注：…]` 同前缀命中）。任何不满足条件 /
    三级都失败 → 原样返回，绝不写回、绝不抛——图注是增强不是阻塞。
    """
    entry = resolve_number(topic_library_root, key)
    if "[示意图" in entry.problem_text or re.search(
        r"\[图\s*\d+\s*标注", entry.problem_text
    ):
        return entry  # 幂等：已补过图注 / 标注
    if not re.search(r"图\s*\d", entry.problem_text):
        return entry  # 题面没有引用图（无图可补）
    if not entry.original_pdf:
        return entry
    entry_dir = _entry_dir(topic_library_root, key)
    pdf_path = entry_dir / entry.original_pdf
    if not pdf_path.is_file():
        return entry
    shared_pdf = sum(
        1
        for other in list_topics(topic_library_root)
        if other.original_pdf == entry.original_pdf
    )
    page_range: Sequence[int] | None = None
    if shared_pdf > 1:
        # 共享 PDF（真题汇总）：定位题面正文页 → 限定页范围提取。定位失败 =
        # 扫描件无文本层 / 题面不匹配 → 跳过（宁可没有图注，也不冒险全文档）。
        page_range = locate_topic_pages(pdf_path, entry.problem_text)
        if page_range is None:
            return entry
    notes = _figure_notes(
        pdf_path,
        page_range=page_range,
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        vision_model=vision_model,
        observation_collector=observation_collector,
        detail_qa=detail_qa,
    )
    if not notes:
        return entry
    is_vision_note = "[示意图" in notes or re.search(
        r"\[图\s*\d+\s*标注：", notes
    )
    if is_vision_note and len(_substantive_text(notes)) < MIN_FIGURE_NOTE_CHARS:
        # 视觉条目无实质内容（如「无实质内容」等过短描述）→ 不写回：装饰图 /
        # 空图的识别结果入库会污染题面素材（2021F 曾把「无实质内容」追进题面）；
        # 覆盖内嵌图段（[示意图N：]）与渲染视觉段（[图N 标注：]，工单
        # topic-vision-render/01）；纯文字标注块（[图N 标注]）是坐标重建的
        # 可信内容，直接放行
        return entry
    new_text = entry.problem_text.rstrip("\n") + "\n\n" + notes
    (entry_dir / entry.problem_md).write_text(new_text, encoding="utf-8")
    commit_after_write(topic_library_root, "lib: 赛题条目补图注")
    return resolve_number(topic_library_root, key)


def _figure_notes(
    pdf_path: Path,
    *,
    page_range: Sequence[int] | None,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
    observation_collector: object | None,
    detail_qa: bool = True,
) -> str:
    """图注获取（三级降级链，工单 topic-vision-render/01，视觉优先）：

    1. pdf_page_render_notes——渲染页 → 视觉描述（矢量图路径，质量最高：
       2021F 图1 实测完整还原尺寸标注与红实线走向；文字标注只留碎片词）；
    2. pdf_figure_annotations——文字标注兜底（零额度，坐标重建布局）；
    3. pdf_image_notes——内嵌栅格图视觉兜底（现状保留）。

    各级异常 → 空串，逐级降级；三级都失败返回空串——图注是增强不是阻塞。
    page_range 非 None = 限定页提取（共享 PDF 定位结果 (start, end) **开区间**
    ——range 展开为页列表，直接 list() 会丢掉尾页前的页，2021F 图1 所在页曾
    因此被跳过），None = 全文档（单条目专属 PDF，现状）。"""
    pages = list(range(*page_range)) if page_range is not None else None
    try:
        notes = pdf_page_render_notes(
            pdf_path,
            pages=pages,
            vision_base_url=vision_base_url,
            vision_api_key=vision_api_key,
            vision_model=vision_model,
            observation_collector=observation_collector,
            detail_qa=detail_qa,
        )
    except Exception:
        notes = ""
    if notes:
        return notes
    try:
        notes = pdf_figure_annotations(pdf_path, pages=pages)  # 文字标注兜底
    except Exception:
        notes = ""
    if notes:
        return notes
    try:
        return pdf_image_notes(
            pdf_path,
            vision_base_url=vision_base_url,
            vision_api_key=vision_api_key,
            vision_model=vision_model,
            observation_collector=observation_collector,
            pages=pages,
            detail_qa=detail_qa,
        )
    except Exception:
        return ""


@dataclass(frozen=True)
class TopicHealth:
    """赛题条目浏览健康实况（工单 topic-library-ui/01，提示语义）。

    浏览列表每条带出：原 PDF 缺失（条目目录内文件不在，AI 拆错核对原文 /
    页图端点的能力丢失）+ 附带程序目录悬空（引用目录不存在，素材不可用）。
    只标记不改数据；判定在服务端（文件系统实况，前端无从判断）。
    original_pdf_size 供详情弹窗展示体量（缺失 = 0；随列表一次算好，
    前端不按条回查——对偶 PDF 轮列表带 mtime 先例）。
    """

    original_pdf_missing: bool
    programs_missing: tuple[str, ...]  # 悬空的附带程序绝对路径（按声明序）
    original_pdf_size: int = 0  # 原 PDF 字节数（文件缺失 = 0）

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_pdf_missing": self.original_pdf_missing,
            "programs_missing": list(self.programs_missing),
            "original_pdf_size": self.original_pdf_size,
        }


def topic_health(topic_library_root: Path, entry: TopicEntry) -> TopicHealth:
    """条目健康判定（浏览列表用）：原 PDF 缺失 = 有声明但文件不在条目目录
    （无声明不算缺失——没有就不查）；附带程序悬空 = 引用路径不是目录
    （Path.is_dir() 与确认入库同判据，引用指向文件 / 已删目录都算悬空）。"""
    entry_dir = _entry_dir(topic_library_root, entry.key)
    pdf_path = entry_dir / entry.original_pdf if entry.original_pdf else None
    original_pdf_missing = bool(pdf_path) and not pdf_path.is_file()
    programs_missing = tuple(
        program for program in entry.programs if not Path(program).is_dir()
    )
    return TopicHealth(
        original_pdf_missing=original_pdf_missing,
        programs_missing=programs_missing,
        original_pdf_size=pdf_path.stat().st_size if pdf_path and pdf_path.is_file() else 0,
    )


def list_topics(topic_library_root: Path) -> list[TopicEntry]:
    """浏览赛题库：全部条目按编号排序（磁盘目录即数据库，操作即时生效）。

    损坏的 manifest 大声失败（与模块库 / 参考库浏览同哲学，不静默跳过——
    浏览者不该面对缺条目的列表）；库根下的散文件与临时目录（点开头）不影响
    浏览（目录迭代走 entry_store 原语）。
    """
    entries: list[TopicEntry] = []
    for entry_dir in iter_entry_dirs(topic_library_root):
        entries.append(_load_entry(entry_dir))
    return sorted(entries, key=lambda entry: entry.key)


def update_topic(
    topic_library_root: Path,
    key: str,
    *,
    problem_text: str,
    programs: Sequence[str],
    hint_module_groups: Sequence[str],
) -> TopicEntry:
    """编辑赛题条目（工单 topic-library-ui/02）：题面全文 / 附带程序 / 功能组
    一次保存，全部校验在首次落盘前，成功自动 git 提交并返回更新后条目。

    身份不变量：year / number（目录名 = 编号身份）与 original_pdf /
    problem_md（文件引用）不可改——本函数只接收三个可编辑字段（题面 /
    附带程序 / 功能组），调用方提交的其余键一概忽略。校验与确认入库
    同口径：题面非空、程序目录必须存在（悬空引用要移除就在清单里删掉，
    不允许写入）、hint 组非空字符串。写题面文件（沿用条目 problem_md
    文件名）+ 更新 manifest（既有字段原样保留）。
    """
    entry = resolve_number(topic_library_root, key)  # 格式 + 查无此条（同文案）
    if not problem_text.strip():
        raise TopicError(f"赛题 {key} 的题面不能为空")
    for program in programs:
        if not isinstance(program, str):
            raise TopicError(
                f"赛题 {key} 的 programs 必须是非空字符串列表"
            )
    normalized_programs = tuple(_normalize_program_dir(program) for program in programs)
    for program in normalized_programs:
        if not Path(program).is_dir():
            raise TopicError(f"附带程序目录不存在：{program}")
    for group in hint_module_groups:
        if not isinstance(group, str) or not group.strip():
            raise TopicError(
                f"赛题 {key} 的 hint_module_groups 必须是非空字符串列表"
            )
    entry_dir = _entry_dir(topic_library_root, key)
    # 落盘：先写题面再写 manifest；写盘失败恢复题面旧值（manifest 保持原值）
    # ——对偶 update_reference「写入期失败清理已写内容」契约（本函数无新增
    # 文件，被改的就是题面与 manifest，恢复题面即尽清理职责）
    old_problem_text = entry.problem_text
    try:
        (entry_dir / entry.problem_md).write_text(problem_text, encoding="utf-8")
        data = read_json(entry_dir, MANIFEST_FILENAME)
        write_json(
            entry_dir,
            MANIFEST_FILENAME,
            {
                **data,
                "programs": list(normalized_programs),
                "hint_module_groups": list(hint_module_groups),
            },
        )
    except Exception:
        (entry_dir / entry.problem_md).write_text(old_problem_text, encoding="utf-8")
        raise
    commit_after_write(topic_library_root, f"lib: update topic {key}")
    return resolve_number(topic_library_root, key)


def delete_topic(topic_library_root: Path, key: str) -> None:
    """删除赛题条目：整个目录移除（含题面与原 PDF 副本）。

    编号先过格式校验（_entry_dir 拦截路径穿越）；查无此条明确报错（与
    resolve_number 同文案，不猜测编造，目录存在校验走 entry_store 原语）。
    """
    _entry_dir(topic_library_root, key)  # 编号先过格式校验（_entry_dir 拦截路径穿越）
    try:
        delete_entry(topic_library_root, key)
    except StoreError:
        raise TopicError(f"题库中没有该编号的赛题：{key}") from None
    commit_after_write(topic_library_root, f"lib: delete topic {key}")


def parse_confirm_entries(data: Mapping[str, Any]) -> tuple[TopicDraft, ...]:
    """把确认请求里的 entries 解析为 TopicDraft 列表（形状 + 全量校验）。

    用户校对后的提交值：形状问题（非列表 / 条目缺字段）与编号格式 / 重复 /
    题面为空（_validate_entries 全量校验）都在这里拦截——用户提交的畸形
    编号不必越过两层函数边界才报错。错误一律 TopicError（业务 400），与
    llm 层拆条解析（parse_topic_split，畸形输出抛 LLMError / 502）各管各的
    错误类型——刻意分工：那边模型输出不可信，这边用户提交。
    """
    raw = data.get("entries")
    if not isinstance(raw, list):
        raise TopicError("entries 必须是列表")
    drafts: list[TopicDraft] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise TopicError(f"entries[{index}] 必须是对象")
        year = item.get("year")
        number = item.get("number")
        problem_text = item.get("problem_text")
        if not isinstance(year, str) or not year.strip():
            raise TopicError(f"entries[{index}] 缺少必填字段：year")
        if not isinstance(number, str) or not number.strip():
            raise TopicError(f"entries[{index}] 缺少必填字段：number")
        if not isinstance(problem_text, str) or not problem_text.strip():
            raise TopicError(f"entries[{index}] 缺少必填字段：problem_text")
        drafts.append(
            TopicDraft(
                year=year.strip(),
                number=number.strip(),
                problem_text=problem_text,
            )
        )
    _validate_entries(drafts)
    return tuple(drafts)


# ---------------------------------------------------------------------------
# 确定性分块（工单 04）：长 PDF 按年份章节 + 题目标记切到单题（零 AI 改写）
# ---------------------------------------------------------------------------

# 规则经 .scratch/real-run/topic_split_by_year.py 真机验证（2017-2025 汇总
# PDF 163K 字符 69/69 全对）：年份章节按数字归组、取"到下一年距离最大"的
# 出现为起点（封面/页眉只有几百字符，章节跨度天然最大）；题目标记只认
# 括号式（X 题）与行首 X 题：，正文误匹配（"停止条件"类）全排除；题面 =
# 标题行起点到下一题标题行的原文段落（含评分标准表），零 AI 改写比 AI
# 抽取更忠实。
YEAR_RE = re.compile(r"(20(?:1[7-9]|2[0-5]))[ ]*年")  # group(1) = 4 位年份
TITLE_RE = re.compile(r"[（(]\s*([A-H])\s*题\s*[)）]|^([A-H])\s*题[：:]", re.M)

# 两种"拆不出来"共用同一句可操作提示（文案单源，与 validate_topic_key 同约定）
_SPLIT_FORMAT_HINT = (
    "长 PDF 的拆条分块要求标准格式（年份章节 + 题目标记（X 题）/行首 X 题：）；"
    "可尝试把 PDF 拆成单份赛题后逐份导入"
)


@dataclass(frozen=True)
class _Chapter:
    """年份章节（同一年变体归组后的一年）：起点 = 到下一年距离最大的出现。

    start/end 是全文切片边界（end 恒为下一章节起点或全文末尾），章节内容
    = text[start:end]。
    """

    year: str
    start: int
    end: int


def split_topics_document(text: str) -> tuple[TopicDraft, ...]:
    """多年真题长 PDF 全文 → 单题草稿（确定性分块，零 AI 改写）。

    LLM 一次拆 8 题会被 flash 模型输出预算截断（实测 max_tokens=8192 也断，
    静默漏题无感知），改为纯文本规则切分：年份章节（YEAR_RE，同一年变体
    按数字归组、取到下一年距离最大的出现为起点）→ 题目标记（TITLE_RE，
    括号式/行首式、正文误匹配排除、同字母去重取首次）→ 题面 = 标题行起点
    到下一题标题行的原文段落；每年最后一题含该年尾部杂项（评分汇总/页脚，
    校对阶段可修剪）。草稿形态与 LLM 拆条一致（TopicDraft：year/number/
    problem_text，confirm_topics 契约不变）。全文无年份章节或零赛题 = 格式
    不匹配，大声失败（宁可报错也不让用户面对空校对页，与"宁可大声失败"
    同哲学）。
    """
    chapters = _split_year_chapters(text)
    if not chapters:
        raise TopicError(
            f"未从 PDF 全文识别出任何年份章节（找不到 20XX 年）：{_SPLIT_FORMAT_HINT}"
        )
    drafts: list[TopicDraft] = []
    for chapter in chapters:
        seg = text[chapter.start : chapter.end]
        marks = _title_marks(seg)
        for index, (letter, pos) in enumerate(marks):
            nxt = marks[index + 1][1] if index + 1 < len(marks) else len(seg)
            drafts.append(
                TopicDraft(
                    year=chapter.year,
                    number=letter,
                    problem_text=seg[pos:nxt].strip(),
                )
            )
    if not drafts:
        raise TopicError(
            f"未从 PDF 全文识别出任何赛题（年份章节内找不到题目标记）："
            f"{_SPLIT_FORMAT_HINT}"
        )
    drafts.sort(key=lambda draft: draft.key)
    return tuple(drafts)


def _split_year_chapters(text: str) -> list[_Chapter]:
    """年份章节边界：同一年变体（'2017年'/'2017 年'）按数字归组，
    取'到下一年距离最大'的出现作为章节起点（封面/页眉只有几百字符，
    章节跨度天然最大）。"""
    occurrences: list[tuple[str, int]] = []
    for match in YEAR_RE.finditer(text):
        year = match.group(1)
        assert year is not None  # YEAR_RE 整式匹配，年份捕获组必命中
        occurrences.append((year, match.start()))
    best: dict[str, _Chapter] = {}
    for index, (year, pos) in enumerate(occurrences):
        nxt = len(text)
        for year2, pos2 in occurrences[index + 1 :]:
            if year2 != year:
                nxt = pos2
                break
        if year not in best or nxt - pos > best[year].end - best[year].start:
            best[year] = _Chapter(year=year, start=pos, end=nxt)
    return sorted(best.values(), key=lambda chapter: chapter.start)


def _title_marks(seg: str) -> list[tuple[str, int]]:
    """题目标记（含行首偏移）：同字母去重取首次；行首偏移 = 标题行起点
    （题面含标题文字）。"""
    marks: list[tuple[str, int]] = []
    for match in TITLE_RE.finditer(seg):
        letter = match.group(1) or match.group(2)
        line_start = seg.rfind("\n", 0, match.start()) + 1
        if not marks or marks[-1][0] != letter:
            marks.append((letter, line_start))
    return marks


# ---------------------------------------------------------------------------
# 校验与落盘辅助
# ---------------------------------------------------------------------------


def _validate_entries(entries: Sequence[TopicDraft]) -> None:
    """确认前校验（全部在落盘前）：至少一道题 / 编号格式与不重复 / 题面非空。

    编号格式校验用本模块的 validate_topic_key（文案唯一出处，模型回 owner
    后不再借道 llm 层）；这里是用户校对后的提交值，格式问题同样在落盘前
    拦截（与拆条解析同标准）。
    """
    if not entries:
        raise TopicError("至少拆出一道赛题才能入库")
    seen: set[str] = set()
    for draft in entries:
        message = validate_topic_key(draft.key)
        if message:
            raise TopicError(message)
        if not draft.problem_text.strip():
            raise TopicError(f"赛题 {draft.key} 的题面不能为空")
        if draft.key in seen:
            raise TopicError(f"同一批入库的赛题编号重复：{draft.key}")
        seen.add(draft.key)


def _resolve_pdf_name(pdf_filename: str) -> str:
    """原 PDF 在条目目录里的文件名：取传入文件名的 basename（客户端文件名
    可能是全路径 / 含分隔符），空名回退 topic.pdf；不得与题面 / manifest
    冲突（冲突会在落盘时覆盖条目元数据）。"""
    name = Path(pdf_filename).name or "topic.pdf"
    if name in (TOPIC_MD_FILENAME, MANIFEST_FILENAME):
        raise TopicError(f"原 PDF 文件名与 {name} 冲突，请重命名后重试")
    return name


def _normalize_program_dir(program_dir: Path | str) -> str:
    """附带程序目录规范化：空白即拒绝（Path("") 会变成 "."，落盘后查不到
    真实目录）；否则原样转字符串（引用方式，不解析不复制）。"""
    raw = str(program_dir)
    if not raw.strip():
        raise TopicError("附带程序目录不能为空")
    return raw


def _entry_dir(topic_library_root: Path, key: str) -> Path:
    """条目目录位置（库布局的唯一出处）：<root>/<编号>；编号先过格式校验，
    杜绝借编号拼路径逃出赛题库（编号由 4 位年份 + 单字母组成，无路径分隔符）。"""
    message = validate_topic_key(key)
    if message:
        raise TopicError(message)
    return topic_library_root / key


def _load_entry(entry_dir: Path) -> TopicEntry:
    """从条目目录加载：manifest.json + 题面 .md；缺失 / 损坏抛 TopicError。

    读盘 / 解析 / 形状校验走 entry_store 原语（read_json），错误类型与文案
    仍归本模块。
    """
    try:
        data = read_json(entry_dir, MANIFEST_FILENAME)
    except StoreReadError as exc:
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 manifest 无法读取：{exc.error}"
        ) from exc
    except StoreParseError as exc:
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 manifest 不是合法 JSON：{exc.error}"
        ) from exc
    except StoreShapeError:
        raise TopicError(f"赛题条目 {entry_dir.name} 的 manifest 必须是 JSON 对象") from None
    year = _require_str(data, "year", entry_dir)
    number = _require_str(data, "number", entry_dir)
    problem_md = _require_str(data, "problem_md", entry_dir)
    original_pdf = _require_str(data, "original_pdf", entry_dir)
    raw_programs = data.get("programs", [])
    if not isinstance(raw_programs, list) or not all(
        isinstance(item, str) and item for item in raw_programs
    ):
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 programs 必须是非空字符串列表"
        )
    raw_hint = data.get("hint_module_groups", [])
    if not isinstance(raw_hint, list) or not all(
        isinstance(item, str) and item for item in raw_hint
    ):
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 hint_module_groups 必须是非空字符串列表"
        )
    try:
        problem_text = (entry_dir / problem_md).read_text(encoding="utf-8")
    except OSError as exc:
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的题面文件无法读取：{problem_md}: {exc}"
        ) from exc
    return TopicEntry(
        year=year,
        number=number,
        problem_text=problem_text,
        problem_md=problem_md,
        original_pdf=original_pdf,
        programs=tuple(raw_programs),
        hint_module_groups=tuple(raw_hint),
    )


def _require_str(data: Mapping[str, Any], key: str, entry_dir: Path) -> str:
    try:
        return require_str(data, key)
    except StoreError:
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 manifest 缺少必填字段：{key}"
        ) from None
