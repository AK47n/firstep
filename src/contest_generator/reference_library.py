"""参考文件库核心：配套资料录入 + 提炼归档（磁盘目录即数据库）。

与模块库同风格：一个条目一个目录——reference.json（机器可读元数据：标题 /
类型 / 简介 / 锚定）+ 素材文件本体（内容自持——归档 = 复制入库，源工程删除
不丢）。条目字段 = 标题 / 类型 / 简介 / 锚定（赛题编号、套件型号或未锚定；套件必须
从模块库已有 kit 词表选——录入时从 list_modules 收集（module_kit_vocabulary）、
校验拒绝词表外值；赛题编号锚定与赛题库 key 同源校验（validate_topic_key，
放行集合一致），查库确认（查无此条拒绝）留待素材区接线；未锚定留给不属于
任何已登记赛题 / 套件的配套资料，锚定值恒为空）。

录入流程（复用模块库草稿→校验→入库模式）：AI 通读素材生成简介草稿
（llm.reference_summarize，/api/references/draft）→ 用户修改 / 补锚定 →
add_reference 结构校验（标题 / 类型 / 简介非空、锚定合法、文件路径安全）通过
才入库——任何失败都不留半成品（条目目录整体回滚）。归档（确认提炼报告时的
"归档为该题参考文件"动作）走 archive_reference：字节复制源工程文件入库、锚定
赛题编号、简介由确认流程在写盘前经 LLM 生成传入（本函数不调 LLM、只复制与
校验）。

浏览 / 搜索（按标题 / 类型 / 锚定值子串过滤）与删除即时生效。任何从条目 id
拼路径的操作（浏览 / 删除 / 写回）都先校验 id 合法性，杜绝借 id 逃出库目录的
路径穿越。库目录的物理位置由调用方传入（webapp 按模块库平级兄弟推导），测试
用 tmp_path。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .autocommit import commit_after_write
from .entry_store import (
    StoreError,
    StoreParseError,
    StoreReadError,
    StoreShapeError,
    delete_entry,
    entry_transaction,
    is_unsafe_path,
    iter_entry_dirs,
    read_json,
    require_str,
    validate_store_key,
    write_json,
)
from .library import file_label, list_modules
from .manifest import collect_kits
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32
from .topic_library import validate_topic_key

if TYPE_CHECKING:
    # 仅类型注解用（draft_description 签名；C1 归位后 llm → selection →
    # reference_library → llm 会成运行时环，library.py 同款先例）
    from .llm import LLM

REFERENCE_META_FILENAME = "reference.json"

# 素材清单.txt（素材工具脚本写入条目目录）：首行表头 + 空行，之后每行
# "相对路径  大小 bytes"（路径可含空格，锚尾解析）——PDF / zip 等只留痕
# 不入库的二进制素材由它索引，是文件名搜索与文件清单的素材来源。
# 写入侧契约 = build_material_manifest（唯一生成器），读端 = _MANIFEST_LINE
# （写读对偶同模块）；表头统一为 sources/materials 源目录说明（读端锚尾
# 正则天然跳过，仅人类可读）。
MANIFEST_FILENAME = "素材清单.txt"
_MANIFEST_HEADER = "素材目录（sources/materials）文件清单："
_MANIFEST_LINE = re.compile(r"^(.*?)\s+(\d+)\s+bytes$")

# 锚定类型：赛题编号（如 2026C）、套件型号（必须取自模块库已有 kit 词表）
# 或 未锚定（配套资料不属于任何已登记赛题 / 套件，如通用开发板资料）
ANCHOR_KIND_TOPIC = "topic"
ANCHOR_KIND_KIT = "kit"
ANCHOR_KIND_NONE = "none"
ANCHOR_KINDS = (ANCHOR_KIND_TOPIC, ANCHOR_KIND_KIT, ANCHOR_KIND_NONE)

# 条目平台属性（工单 01）：stm32 / mspm0 / any。词表复用 platforms.py 的两
# 个已知平台 + any（平台无关，缺省——旧条目缺字段 = any，向后兼容：任何生成
# 平台都注入；带平台 = 只注入对应平台工程，装配点统一过滤）。
PLATFORM_ANY = "any"
REFERENCE_PLATFORMS = (PLATFORM_STM32, PLATFORM_MSPM0, PLATFORM_ANY)

# 归档条目固定类型：被剔除的业务代码复制入库即为"例程代码"参考
ARCHIVE_ENTRY_TYPE = "例程代码"

_ENTRY_ID_PATTERN = re.compile(r"^[^.\s/\\][\w.\- ]*$")


class ReferenceError(ValueError):
    """参考文件库操作失败（条目不存在、锚定非法、文件非法、校验未通过等）。"""


@dataclass(frozen=True)
class ReferenceEntry:
    """一个参考文件条目：标题 / 类型 / 简介 / 锚定 + 素材文件清单。

    体量字段（file_count / size_bytes）是磁盘实况（磁盘目录即数据库），元数据
    解析（from_dict）不含——读盘返回前由 get_reference / add_reference 用
    entry_stats 补全，序列化出去的值恒为实况。
    """

    id: str  # 条目 id = 目录名（由标题生成，含中英文 / 数字 / 连字符）
    title: str  # 标题
    type: str  # 类型（例程工程 / 说明书等，自由文本）
    description: str  # 简介（AI 草稿由用户确认）
    anchor_kind: str  # ANCHOR_KIND_TOPIC / ANCHOR_KIND_KIT
    anchor_value: str  # 锚定值（赛题编号 或 模块库已有 kit 型号）
    files: tuple[str, ...]  # 素材文件路径（相对条目目录）
    platform: str = PLATFORM_ANY  # 平台属性：stm32 / mspm0 / any（缺省 any 向后兼容）
    file_count: int = 0  # 条目目录文件数（含 reference.json）
    size_bytes: int = 0  # 条目目录总体积（字节）

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict。"""
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "description": self.description,
            "anchor_kind": self.anchor_kind,
            "anchor_value": self.anchor_value,
            "platform": self.platform,
            "files": list(self.files),
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReferenceEntry":
        """从 dict 解析并校验，任何缺失 / 非法字段抛 ReferenceError。"""
        if not isinstance(data, dict):
            raise ReferenceError("参考文件条目必须是对象")
        entry_id = _require_str(data, "id")
        title = _require_str(data, "title")
        type_ = _require_str(data, "type")
        description = _require_str(data, "description")
        anchor_kind = _require_str(data, "anchor_kind")
        if anchor_kind not in ANCHOR_KINDS:
            # 词表外锚定类型 = 元数据损坏（与 FileDecision.from_dict 拒绝词表外
            # action 同款）：浏览时大声失败，不把坏数据带进列表
            raise ReferenceError(
                f"非法锚定类型：{anchor_kind!r}（应为 topic、kit 或 none）"
            )
        if anchor_kind == ANCHOR_KIND_NONE:
            # 未锚定：锚定值恒为空（非空 = 元数据损坏，拒绝）
            raw_value = data.get("anchor_value")
            if raw_value is not None and raw_value != "":
                raise ReferenceError("未锚定条目的锚定值必须为空")
            anchor_value = ""
        else:
            anchor_value = _require_str(data, "anchor_value")
        files = data.get("files")
        if not isinstance(files, list) or not all(
            isinstance(item, str) and item for item in files
        ):
            raise ReferenceError("files 必须是非空字符串列表")
        platform = data.get("platform", PLATFORM_ANY)
        if platform not in REFERENCE_PLATFORMS:
            # 词表外平台属性 = 元数据损坏（与锚定类型同款）：浏览时大声失败，
            # 不把坏数据带进列表
            raise ReferenceError(
                f"非法平台属性：{platform!r}（应为 stm32、mspm0 或 any）"
            )
        return cls(
            id=entry_id,
            title=title,
            type=type_,
            description=description,
            anchor_kind=anchor_kind,
            anchor_value=anchor_value,
            files=tuple(files),
            platform=platform,
        )


def validate_topic_anchor(anchor: str) -> None:
    """赛题编号锚定格式校验：年份 + 编号（如 2026C）。

    格式与赛题库 key 同源（validate_topic_key，唯一出处）——放行集合与赛题库
    合法编号完全一致（旧实现独立的 ^\d{4}[A-Za-z]{1,2}$ 会放行 2026c / 2026AB
    这类赛题库永远存不了的编号，导致锚定永远解析不中）。查库确认（查无此条
    拒绝）留待素材区接线。
    """
    message = validate_topic_key(anchor)
    if message:
        raise ReferenceError(message)


def module_kit_vocabulary(module_library_dir: Path) -> tuple[str, ...]:
    """模块库现有 kit 词表（参考文件套件锚定的合法取值，唯一出处）。

    收集走 manifest.collect_kits（保序去重的唯一实现）；manifest 损坏的模块
    由 list_modules 抛 LibraryError，透传给调用方（webapp 错误映射已登记）。
    """
    return tuple(collect_kits(list_modules(module_library_dir)))


# ---------------------------------------------------------------------------
# 浏览 / 搜索 / 删除（磁盘目录即数据库，操作即时生效）
# ---------------------------------------------------------------------------


def list_references(reference_root: Path) -> list[ReferenceEntry]:
    """返回库中全部条目（按 id 排序）；元数据损坏的条目目录抛 ReferenceError。

    库根不存在 = 空库、散文件与点开头目录不影响浏览（目录迭代走 entry_store
    原语，与模块库 / 赛题库浏览同哲学）。
    """
    entries: list[ReferenceEntry] = []
    for entry in iter_entry_dirs(reference_root):
        entries.append(get_reference(reference_root, entry.name))
    return entries


def entry_stats(entry_dir: Path) -> tuple[int, int]:
    """条目目录磁盘实况：(文件数, 总体积字节)。

    磁盘目录即数据库——统计整目录（含 reference.json），即删除动作的真实
    影响面；素材清单（files 字段）之外的散文件也如实计入。
    """
    count = 0
    total = 0
    for path in entry_dir.rglob("*"):
        if path.is_file():
            count += 1
            total += path.stat().st_size
    return count, total


def get_reference(reference_root: Path, entry_id: str) -> ReferenceEntry:
    """读取单个条目；不存在或元数据损坏抛 ReferenceError。

    读盘 / 解析 / 形状校验走 entry_store 原语（read_json），错误类型与文案
    仍归本模块。返回时补全体量字段（磁盘实况，元数据不含）。
    """
    _validate_entry_id(entry_id)
    entry_dir = reference_root / entry_id
    if not entry_dir.is_dir():
        raise ReferenceError(f"参考文件条目 {entry_id!r} 不存在")
    try:
        data = read_json(entry_dir, REFERENCE_META_FILENAME)
    except StoreReadError as exc:
        raise ReferenceError(
            f"参考文件条目 {entry_id!r} 的元数据无法读取：{exc.error}"
        ) from exc
    except StoreParseError as exc:
        raise ReferenceError(
            f"参考文件条目 {entry_id!r} 的元数据不是合法 JSON：{exc.error}"
        ) from exc
    except StoreShapeError:
        raise ReferenceError(
            f"参考文件条目 {entry_id!r} 的元数据不合法：参考文件条目必须是对象"
        ) from None
    try:
        entry = ReferenceEntry.from_dict(data)
    except ReferenceError as exc:
        raise ReferenceError(f"参考文件条目 {entry_id!r} 的元数据不合法：{exc}") from exc
    file_count, size_bytes = entry_stats(entry_dir)
    return replace(entry, file_count=file_count, size_bytes=size_bytes)


def search_references(
    reference_root: Path,
    *,
    title: str = "",
    type: str = "",
    anchor: str = "",
    filename: str = "",
) -> list[ReferenceEntry]:
    """浏览 / 搜索：按标题 / 类型 / 锚定值 / 文件名子串过滤（大小写不敏感，可组合）。

    文件名过滤（文件名搜索工单）：逐路径子串匹配该条目可服务文件全集
    （_entry_file_records：素材清单记录 + 条目目录实际文件，唯一出处）——
    PDF 等只留痕不入库的二进制素材以清单路径命中（磁盘实况），文本文件
    同时可经实际路径命中；素材清单缺失 = 该项为空（旧条目兼容）。逐路径
    判据不跨路径拼接（含 \n 的 needle 不再伪命中）。全部过滤参数为空时
    返回全量（与 list_references 同形状）。
    """
    entries = list_references(reference_root)
    needle_title = title.strip().lower()
    needle_type = type.strip().lower()
    needle_anchor = anchor.strip().lower()
    needle_filename = filename.strip().lower()
    if not (needle_title or needle_type or needle_anchor or needle_filename):
        return entries
    return [
        entry
        for entry in entries
        if (not needle_title or needle_title in entry.title.lower())
        and (not needle_type or needle_type in entry.type.lower())
        and (not needle_anchor or needle_anchor in entry.anchor_value.lower())
        and (
            not needle_filename
            or any(
                needle_filename in rel.lower()
                for rel in _entry_file_records(reference_root, entry.id)
            )
        )
    ]


def delete_reference(reference_root: Path, entry_id: str) -> None:
    """删除条目：整个目录移除（目录存在校验走 entry_store 原语）。"""
    _validate_entry_id(entry_id)
    try:
        delete_entry(reference_root, entry_id)
    except StoreError:
        raise ReferenceError(f"参考文件条目 {entry_id!r} 不存在") from None
    commit_after_write(reference_root, f"lib: delete reference {entry_id}")


# ---------------------------------------------------------------------------
# 文件名搜索 / 文件清单与定位（文件名搜索 + 文件打开工单）：素材清单.txt 是
# 二进制素材（PDF / zip 等本体在 sources/materials 镜像）的索引，清单记录
# + 条目目录实际文件 = 可服务文件全集；写读对偶同模块（build_material_manifest
# 生成 ↔ _read_manifest_records 解析），三形状（清单 / 搜索 / 匹配）共用
# _entry_file_records 一个出处
# ---------------------------------------------------------------------------


def build_material_manifest(src_dir: Path) -> str:
    """《素材清单》文本生成器（素材工具脚本写入侧契约）：源目录全部文件留痕。

    首行表头 + 空行，之后每行 "相对路径  大小 bytes"（路径可含空格，锚尾
    解析）——与读取侧 _read_manifest_records 的 _MANIFEST_LINE 对偶：表头 /
    空行天然跳过；stat 失败的文件记 size=-1（读端锚尾正则只吃数字，-1 行
    仅留痕不索引）。行格式是写入侧契约，勿改（磁盘存量清单按旧格式，读端不变）。
    """
    lines = [_MANIFEST_HEADER, ""]
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        lines.append(f"{path.relative_to(src_dir).as_posix()}  {size} bytes")
    return "\n".join(lines)


def list_entry_files(reference_root: Path, entry_id: str) -> list[dict[str, str | int]]:
    """条目可服务文件清单 [{path, size_bytes}]（按路径排序）。

    数据源 = _entry_file_records（素材清单记录 + 条目目录实际文件，同路径
    磁盘实况优先——唯一出处）；条目不存在抛 ReferenceError（既有映射）。
    """
    return [
        {"path": rel, "size_bytes": size}
        for rel, size in sorted(_entry_file_records(reference_root, entry_id).items())
    ]


def match_entry_files(
    reference_root: Path, entry_id: str, needle: str
) -> list[str]:
    """条目内文件名子串匹配（大小写不敏感）：逐路径判据（不跨路径拼接）。

    命中路径按 _entry_file_records 插入序（清单顺序优先，磁盘新增殿后）返回
    ——用于文件名搜索时直接带出命中文件，省去"查看 → 清单 → 翻找"两跳。
    needle 空串返回空列表（调用方仅在文件名过滤时启用）。
    """
    needle = needle.strip().lower()
    if not needle:
        return []
    return [
        rel for rel in _entry_file_records(reference_root, entry_id)
        if needle in rel.lower()
    ]


def resolve_entry_file(
    reference_root: Path,
    materials_root: Path,
    entry_id: str,
    rel_path: str,
) -> tuple[Path, str | None]:
    """条目文件物理定位：(文件路径, 响应 media_type 覆写或 None)。

    路径安全（is_unsafe_path）不通过抛 ReferenceError（映射 400）；先试条目
    目录（文本副本，命中即服务、media_type 留空按扩展名自动猜）；不存在再试
    sources/materials 镜像（PDF 带 application/pdf 供浏览器预览，其余按扩展
    名自动转下载）；materials 根缺失 / 两处都找不到抛 ReferenceError（映射
    400，与条目不存在同通道）。条目不存在抛 ReferenceError（既有映射）。
    """
    entry = get_reference(reference_root, entry_id)
    if is_unsafe_path(rel_path):
        raise ReferenceError(f"非法文件路径：{rel_path!r}")
    entry_file = reference_root / entry.id / rel_path
    if entry_file.is_file():
        return entry_file, None
    materials_file = materials_root / entry.title / rel_path
    if materials_file.is_file():
        media_type = (
            "application/pdf" if materials_file.suffix.lower() == ".pdf" else None
        )
        return materials_file, media_type
    raise ReferenceError(f"参考文件条目 {entry_id!r} 中不存在文件：{rel_path}")


def _entry_file_records(reference_root: Path, entry_id: str) -> dict[str, int]:
    """条目可服务文件全集 {相对路径: 大小字节}（清单 / 搜索 / 匹配的唯一出处）。

    素材清单.txt 记录（二进制素材索引，size 取记录值）+ 条目目录实际文件
    （rglob 排除 reference.json，size 取真实 stat）；同路径磁盘实况优先。
    插入序 = 清单记录序 + 磁盘新增殿后（match_entry_files 保序依赖）。素材
    清单缺失 / 不可读 = 只剩实际文件（旧条目兼容）。条目不存在抛
    ReferenceError（既有映射）。
    """
    entry = get_reference(reference_root, entry_id)
    entry_dir = reference_root / entry.id
    records: dict[str, int] = {}
    for rel, size in _read_manifest_records(entry_dir):
        records[rel] = size
    for path in entry_dir.rglob("*"):
        if path.is_file() and path.name != REFERENCE_META_FILENAME:
            records[path.relative_to(entry_dir).as_posix()] = path.stat().st_size
    return records


def _read_manifest_records(entry_dir: Path) -> list[tuple[str, int]]:
    """素材清单.txt 记录 [(相对路径, 大小字节)]；缺失 / 不可读 = 空（旧条目兼容）。

    行格式每行 "相对路径  大小 bytes"（路径可含空格，锚尾解析）；表头行 /
    空行被正则锚尾天然跳过。
    """
    manifest = entry_dir / MANIFEST_FILENAME
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    return [
        (match.group(1), int(match.group(2)))
        for line in lines
        if (match := _MANIFEST_LINE.match(line))
    ]


# ---------------------------------------------------------------------------
# 全文回读（两级注入第二级）：store 自持读取——路径安全 + 二进制跳过 + 标签单源
# ---------------------------------------------------------------------------


def read_fulltext(reference_root: Path, entry: ReferenceEntry) -> str:
    """参考文件条目全文（两级注入第二级的素材）：素材文件拼成带文件名标注的文本。

    二进制素材（说明书 PDF 等）读不了文本——跳过并标注（不让生成流程因个别
    不可读素材整体失败）；条目文件缺失 / 相对路径非法 = 库损坏，大声失败
    （ReferenceError，宁可大声失败也不把坏数据带进上下文）。
    """
    chunks: list[str] = []
    for rel in entry.files:
        if is_unsafe_path(rel):
            raise ReferenceError(
                f"参考文件条目 {entry.id!r} 的文件路径非法：{rel!r}"
            )
        path = reference_root / entry.id / rel
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReferenceError(
                f"参考文件条目 {entry.id!r} 的素材文件无法读取：{rel}: {exc}"
            ) from exc
        except UnicodeDecodeError:
            chunks.append(file_label(rel, "（二进制素材，未嵌入全文）"))
            continue
        chunks.append(file_label(rel) + content)
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# AI 录入流程：草稿 → 用户修改 / 补锚定 → 结构校验 → 入库
# ---------------------------------------------------------------------------


def draft_description(llm: LLM, files: Mapping[str, str]) -> str:
    """AI 通读素材生成简介草稿（与模块录入的草稿同款：草稿不校验、由用户确认）。"""
    return llm.reference_summarize(_assemble_material(files))


def add_reference(
    reference_root: Path,
    *,
    title: str,
    type: str,
    description: str,
    anchor_kind: str,
    anchor_value: str,
    files: Mapping[str, str],
    kit_vocabulary: Sequence[str],
    platform: str = PLATFORM_ANY,
) -> ReferenceEntry:
    """完整录入流程：结构校验通过才入库；失败不留半成品（与模块录入同款）。

    校验全部在落盘前：标题 / 类型 / 简介非空；锚定合法——套件型号必须在
    模块库已有 kit 词表内（词表外值拒绝，spec「不新打字」）、赛题编号通过
    格式校验（查库确认待赛题库工单 01 落地后接入）；平台属性必须取自词表
    （stm32 / mspm0 / any，词表外值大声失败）；素材文件至少一个、路径安全。
    简介由用户先经 /api/references/draft 生成草稿并确认，本函数不做
    AI 一致性校验（配套资料可能是说明书等非代码素材，简介正确性由人确认）。
    条目目录名由标题生成（重复标题自动加 -2 / -3 后缀）。
    """
    title = title.strip()
    type_ = type.strip()
    description = description.strip()
    anchor_value = anchor_value.strip()
    platform = platform.strip()
    if not title:
        raise ReferenceError("条目标题不能为空")
    if not type_:
        raise ReferenceError("条目类型不能为空")
    if not description:
        raise ReferenceError("条目简介不能为空")
    _validate_anchor(anchor_kind, anchor_value, kit_vocabulary)
    if platform not in REFERENCE_PLATFORMS:
        raise ReferenceError(
            f"非法平台属性：{platform!r}（应为 stm32、mspm0 或 any）"
        )
    _validate_files(files)

    reference_root.mkdir(parents=True, exist_ok=True)
    entry_id = _next_entry_id(reference_root, title)
    entry = ReferenceEntry(
        id=entry_id,
        title=title,
        type=type_,
        description=description,
        anchor_kind=anchor_kind,
        anchor_value=anchor_value,
        files=tuple(files),
        platform=platform,
    )
    with entry_transaction(reference_root, [entry_id]) as (entry_dir,):
        _write_files(entry_dir, files)
        write_json(entry_dir, REFERENCE_META_FILENAME, entry.to_dict())
    file_count, size_bytes = entry_stats(reference_root / entry_id)
    entry = replace(entry, file_count=file_count, size_bytes=size_bytes)
    commit_after_write(reference_root, f"lib: add reference {entry_id}")
    return entry


# ---------------------------------------------------------------------------
# 归档（确认提炼报告时的"归档为该题参考文件"动作）：复制入库、内容自持
# ---------------------------------------------------------------------------


def archive_reference(
    reference_root: Path,
    *,
    source: Path,
    rel_path: str,
    title: str,
    description: str,
    anchor_topic: str,
) -> ReferenceEntry:
    """归档：源工程文件字节复制入库、锚定赛题编号（内容自持，源删除不丢）。

    归档条目字段自动生成：类型固定 ARCHIVE_ENTRY_TYPE、简介由确认流程在写盘
    前经 LLM 生成传入（本函数不调 LLM，只负责复制与校验）。单个动作原子：
    复制 / 元数据任何一步失败都删除条目目录，不留半成品。
    """
    validate_topic_anchor(anchor_topic)
    title = title.strip()
    description = description.strip()
    if not title:
        raise ReferenceError("归档条目标题不能为空")
    if not description:
        raise ReferenceError("归档条目简介不能为空")
    if is_unsafe_path(rel_path):
        raise ReferenceError(f"归档文件路径非法：{rel_path!r}")
    if rel_path == REFERENCE_META_FILENAME:
        # 源工程里恰好叫 reference.json 的文件不能归档：复制后会被元数据覆盖
        # （内容静默丢失、meta 的 files 字段说谎）——与录入流程同一拦截
        raise ReferenceError(f"文件名不能与 {REFERENCE_META_FILENAME} 冲突")

    reference_root.mkdir(parents=True, exist_ok=True)
    entry_id = _next_entry_id(reference_root, title)
    entry = ReferenceEntry(
        id=entry_id,
        title=title,
        type=ARCHIVE_ENTRY_TYPE,
        description=description,
        anchor_kind=ANCHOR_KIND_TOPIC,
        anchor_value=anchor_topic,
        files=(rel_path,),
    )
    with entry_transaction(reference_root, [entry_id]) as (entry_dir,):
        dst = entry_dir / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dst)
        write_json(entry_dir, REFERENCE_META_FILENAME, entry.to_dict())
    file_count, size_bytes = entry_stats(reference_root / entry_id)
    return replace(entry, file_count=file_count, size_bytes=size_bytes)


# ---------------------------------------------------------------------------
# 校验与落盘辅助
# ---------------------------------------------------------------------------


def _validate_anchor(
    anchor_kind: str, anchor_value: str, kit_vocabulary: Sequence[str]
) -> None:
    """锚定校验：套件型号必须取自模块库已有 kit 词表，赛题编号过格式校验，
    未锚定要求锚定值为空。"""
    if anchor_kind == ANCHOR_KIND_TOPIC:
        validate_topic_anchor(anchor_value)
    elif anchor_kind == ANCHOR_KIND_KIT:
        if anchor_value not in kit_vocabulary:
            raise ReferenceError(
                f"套件型号 {anchor_value!r} 不在模块库已有 kit 词表中"
                f"（现有：{'、'.join(kit_vocabulary) or '无'}）"
            )
    elif anchor_kind == ANCHOR_KIND_NONE:
        if anchor_value:
            raise ReferenceError("未锚定条目的锚定值必须为空")
    else:
        raise ReferenceError(
            f"非法锚定类型：{anchor_kind!r}（应为 topic、kit 或 none）"
        )


def _validate_files(files: Mapping[str, str]) -> None:
    if not files:
        raise ReferenceError("至少需要一个素材文件")
    for name in files:
        if is_unsafe_path(name):
            raise ReferenceError(f"文件路径必须是相对且无 .. 的：{name!r}")
        if name == REFERENCE_META_FILENAME:
            raise ReferenceError(f"文件名不能与 {REFERENCE_META_FILENAME} 冲突")


def _validate_entry_id(entry_id: str) -> None:
    """条目 id 合法性：杜绝借 id 拼路径逃出库目录的路径穿越。"""
    try:
        validate_store_key(entry_id, _ENTRY_ID_PATTERN, "条目 id")
    except StoreError:
        raise ReferenceError(f"非法条目 id：{entry_id!r}") from None


def _next_entry_id(reference_root: Path, title: str) -> str:
    """由标题生成安全的条目目录名；重名自动加 -2 / -3 后缀（目录名唯一）。"""
    base = _sanitize_id(title)
    existing = {p.name for p in reference_root.iterdir()}
    entry_id = base
    counter = 2
    while entry_id in existing:
        entry_id = f"{base}-{counter}"
        counter += 1
    return entry_id


def _sanitize_id(title: str) -> str:
    """把标题转成安全的条目目录名：保留中英文 / 数字 / 下划线，其余换连字符。"""
    cleaned = re.sub(r"[^\w\-]+", "-", title).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned[:60] or "reference"


def _write_files(entry_dir: Path, files: Mapping[str, str]) -> None:
    for name, content in files.items():
        path = entry_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _assemble_material(files: Mapping[str, str]) -> str:
    """把素材文件拼成一份带文件名标注的文本（简介草稿的 AI 视角）。"""
    return "\n".join(
        file_label(name) + content for name, content in files.items()
    )


def _require_str(data: dict[str, Any], key: str) -> str:
    try:
        return require_str(data, key)
    except StoreError:
        raise ReferenceError(f"缺少必填字段：{key}") from None
