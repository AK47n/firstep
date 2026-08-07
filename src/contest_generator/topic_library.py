"""赛题库核心：长 PDF 拆条 → 用户逐条校对 → 确认入库（事务）+ 编号解析。

流程（素材库 spec + ADR 0006）：用户导入历年真题长 PDF → AI 拆条（年份 /
编号 / 题面全文，拆条协议在 llm 层）→ 用户逐条校对（改年份 / 题号 / 题面）
→ 确认入库。磁盘目录即数据库（与模块库同风格）：一条目一目录（目录名 =
赛题编号），题面全文落 topic.md，原 PDF 复制保留在条目目录（AI 拆错可查
原文），manifest.json 记录年份 / 编号 / 题面文件名 / 原 PDF 文件名 / 附带
程序目录。附带程序用引用方式（字段存绝对路径，不复制）——源工程还要继续
编辑使用，复制会制造两份（2026C 钥匙/锁两套即此形态）。

编号解析："2026C"（年份 + 题号）→ 题面全文，供生成入口与 AI 理解使用；
查无此条明确报错（不猜测编造）。关联模块复用模块简介"XX 题专用"标注自动
发现（如"2026C 数字钥匙题专用"），不新造链接字段——发现是读时计算，模块
库更新后关联随之更新。

确认入库是事务（与提炼确认同风格）：全部校验（至少一道题 / 编号格式与不
重复 / 题面非空 / 原 PDF 存在 / 附带程序目录存在 / 编号未被占用）都在落盘
前完成，落盘中途失败清理全部已建条目目录——任何失败都不留半成品。赛题库
的物理位置由调用方传入（webapp 取模块库同级 topics/，配置字段后续工单加），
测试用 tmp_path。
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .llm import LLM, TopicDraft, validate_topic_key
from .library import list_modules
from .manifest import MANIFEST_FILENAME

TOPIC_MD_FILENAME = "topic.md"  # 题面全文落盘文件名（条目目录内，唯一出处）


class TopicError(ValueError):
    """赛题库操作失败（条目不存在、编号冲突、题面 / 原 PDF 缺失等）。"""


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

    created: list[Path] = []
    topic_library_root.mkdir(parents=True, exist_ok=True)
    try:
        for draft in entries:
            entry_dir = topic_library_root / draft.key
            entry_dir.mkdir()
            created.append(entry_dir)
            shutil.copy2(pdf_path, entry_dir / pdf_name)
            (entry_dir / TOPIC_MD_FILENAME).write_text(
                draft.problem_text, encoding="utf-8"
            )
            _write_manifest(
                entry_dir,
                {
                    "year": draft.year,
                    "number": draft.number,
                    "problem_md": TOPIC_MD_FILENAME,
                    "original_pdf": pdf_name,
                    "programs": list(normalized_programs),
                },
            )
    except Exception:
        for entry_dir in created:
            shutil.rmtree(entry_dir, ignore_errors=True)  # 入库中途失败不留半成品
        raise
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


def parse_confirm_entries(data: Mapping[str, Any]) -> tuple[TopicDraft, ...]:
    """把确认请求里的 entries 解析为 TopicDraft 列表（形状校验）。

    用户校对后的提交值：形状问题（非列表 / 条目缺字段） = 业务 400
    （TopicError）；编号格式与重复等进一步校验在 confirm_topics（核心
    唯一来源）。llm 层拆条解析（parse_topic_split）各管各的错误类型——
    那边畸形输出抛 LLMError（502），这边用户提交问题抛 TopicError（400）。
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
    return tuple(drafts)


def discover_related_modules(module_library_dir: Path, key: str) -> tuple[str, ...]:
    """自动发现关联模块：复用模块简介的"XX 题专用"标注，不新造链接字段。

    匹配规则：简介含该题编号（如 2026C）且含"专用"（如"2026C 数字钥匙题
    专用"）。模块清单走 library.list_modules（唯一浏览入口）——损坏的
    manifest 大声失败（与模块库浏览同哲学），不静默跳过。发现是读时计算，
    模块库更新后关联随之更新；模块库不存在返回空。
    """
    if not module_library_dir.is_dir():
        return ()
    return tuple(
        manifest.slug
        for manifest in list_modules(module_library_dir)
        if key in manifest.description and "专用" in manifest.description
    )


# ---------------------------------------------------------------------------
# 校验与落盘辅助
# ---------------------------------------------------------------------------


def _validate_entries(entries: Sequence[TopicDraft]) -> None:
    """确认前校验（全部在落盘前）：至少一道题 / 编号格式与不重复 / 题面非空。

    编号格式校验用 llm 层的 validate_topic_key（文案唯一出处）；这里是
    用户校对后的提交值，格式问题同样在落盘前拦截（与拆条解析同标准）。
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
    """从条目目录加载：manifest.json + 题面 .md；缺失 / 损坏抛 TopicError。"""
    try:
        text = (entry_dir / MANIFEST_FILENAME).read_text(encoding="utf-8")
    except OSError as exc:
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 manifest 无法读取：{exc}"
        ) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 manifest 不是合法 JSON：{exc}"
        ) from exc
    if not isinstance(data, dict):
        raise TopicError(f"赛题条目 {entry_dir.name} 的 manifest 必须是 JSON 对象")
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
    )


def _write_manifest(entry_dir: Path, data: dict[str, Any]) -> None:
    (entry_dir / MANIFEST_FILENAME).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _require_str(data: Mapping[str, Any], key: str, entry_dir: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TopicError(f"赛题条目 {entry_dir.name} 的 manifest 缺少必填字段：{key}")
    return value
