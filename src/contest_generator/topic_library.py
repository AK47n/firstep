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
from .library import list_modules
from .manifest import MANIFEST_FILENAME, ModuleManifest

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


def related_module_slugs(
    manifests: Sequence[ModuleManifest], key: str
) -> tuple[str, ...]:
    """从 manifest 清单筛出该题专用模块（简介含该题编号且含"专用"）。

    匹配规则与 discover_related_modules 同一处实现——生成上下文已扫过库时
    直接复用候选清单，不二次扫盘（复用"XX 题专用"标注，不新造链接字段）。
    """
    return tuple(
        manifest.slug
        for manifest in manifests
        if key in manifest.description and "专用" in manifest.description
    )


def discover_related_modules(module_library_dir: Path, key: str) -> tuple[str, ...]:
    """自动发现关联模块：复用模块简介的"XX 题专用"标注，不新造链接字段。

    模块清单走 library.list_modules（唯一浏览入口）——损坏的 manifest 大声
    失败（与模块库浏览同哲学），不静默跳过。发现是读时计算，模块库更新后
    关联随之更新；模块库不存在返回空。
    """
    if not module_library_dir.is_dir():
        return ()
    return related_module_slugs(list_modules(module_library_dir), key)


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


def _require_str(data: Mapping[str, Any], key: str, entry_dir: Path) -> str:
    try:
        return require_str(data, key)
    except StoreError:
        raise TopicError(
            f"赛题条目 {entry_dir.name} 的 manifest 缺少必填字段：{key}"
        ) from None
