"""错误映射结构测试（工单 C6）：表住 errors.py + 结构防漏登。

- 结构测试：反射枚举 contest_generator 包下全部异常类（pkgutil 模块树扫 +
  inspect.getmembers + __subclasses__ 收敛），断言均已登记（自身或基类在
  error_to_http 表内）——登记遗漏从此测试红，不是线上 500。
- 白名单：刻意按 500 暴露（从不直达 web 层）的类，逐条注释理由。
- 行为抽查：error_entry 对 UnknownPlatformError 给 400 中文（原漏登记的
  实证 bug）；既有映射状态码 / 文案逐字不变（表平移不改变行为）。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import contest_generator
from contest_generator.entry_store import (
    StoreError,
    StoreParseError,
    StoreReadError,
    StoreShapeError,
)
from contest_generator.errors import _ERROR_TABLE, error_entry
from contest_generator.generator import DuplicateFilePathError
from contest_generator.llm import LLMError
from contest_generator.boards import BoardError
from contest_generator.manifest import ManifestError
from contest_generator.patchers import UnknownPlatformError
from contest_generator.report import ReportError
from contest_generator.selection import ManualReferenceError, SelectionError
from contest_generator.syscfg_model import SyscfgModelError
from contest_generator.wordlist import WordlistError

# 刻意按 500 暴露的类（不登记）：这些类从不直达 web 层，泄漏必是真 bug，
# 500 大声失败正是政策本意——结构测试不强制它们入表，逐条注释理由：
_UNREGISTERED_WHITELIST: tuple[type[Exception], ...] = (
    # 条目库原语失败（entry_store.py：读盘 / 解析 / 形状 / 键非法 / 查无
    # 此条 / 字段缺失）：四库全部捕获重包装为各自域错误（已登记）；能漏到
    # 路由层 = 调用方漏包装 → 500 正确
    StoreError,
    StoreReadError,
    StoreParseError,
    StoreShapeError,
    # 模块清单内部校验（manifest.py）：所有出厂路径都被 library.py 捕获
    # 重包装为 LibraryError（已登记）；能漏到路由层 = 调用方 bug → 500 正确
    ManifestError,
    # 板定义文件内部校验（boards.py，工单 pin-board-config/01）：板 JSON 是
    # 包内静态数据（随包分发），损坏 = 安装/发布坏 → 500 大声失败正确；
    # 与 ManifestError 同政策
    BoardError,
    # 提炼报告 / 判定条目内部校验（report.py）：llm.py / master.py 捕获
    # 重包装为 LLMError / MasterError（已登记）；同上
    ReportError,
    # 硬件词表加载（wordlist.py）：只发生在模块导入期（DEFAULT_WORDLIST =
    # load_wordlist() 模块级），词表损坏直接导入失败，不可能到 web 层
    WordlistError,
    # syscfg 文件模型内部失败（syscfg_model.py，架构评审 ②）：prune / rewrite
    # 的母版漂移 / 数据漂移防御路径。迁移期（工单 03）由 pinwriter 捕获重包装
    # 为 PinBindingError（已登记）——能漏到路由层 = 调用方漏包装 → 500 正确
    SyscfgModelError,
)


def _registered_types() -> tuple[type[Exception], ...]:
    """error_to_http 表里出现过的类型（含内置 OSError——子类也经 isinstance 命中）。"""
    return tuple(t for entry in _ERROR_TABLE for t in entry.exc_types)


def _all_package_error_classes() -> set[type[Exception]]:
    """反射枚举包内全部异常类：pkgutil 模块树扫 + inspect.getmembers + __subclasses__ 收敛。

    模块树扫收集包内各模块定义的异常类（排除从别的模块 import 进来的类）；
    __subclasses__ 收敛把包外（如测试内临时定义）继承包内异常的新类也算
    进来——漏登检查连"测试内造的新异常"都不放过。
    """
    package = contest_generator
    classes: set[type[Exception]] = set()
    mod_names = [
        info.name
        for info in pkgutil.walk_packages(package.__path__, package.__name__ + ".")
    ]
    for mod_name in mod_names:
        mod = importlib.import_module(mod_name)
        for _, obj in inspect.getmembers(mod):
            if (
                inspect.isclass(obj)
                and issubclass(obj, Exception)
                and obj.__module__ == mod_name
            ):
                classes.add(obj)
    # __subclasses__ 收敛：包内类的直接/间接子类（无论定义在哪个模块）
    queue = list(classes)
    while queue:
        for sub in queue.pop().__subclasses__():
            if issubclass(sub, Exception) and sub not in classes:
                classes.add(sub)
                queue.append(sub)
    return classes


def test_every_package_exception_is_registered_or_whitelisted() -> None:
    """结构防漏登：包内每个异常类必须命中 error_to_http 表（自身或其基类
    在表内，isinstance 语义），否则必须在白名单——漏登从此是测试红。
    """
    registered = _registered_types()
    missing = [
        cls
        for cls in sorted(
            _all_package_error_classes(),
            key=lambda c: f"{c.__module__}.{c.__qualname__}",
        )
        if cls not in _UNREGISTERED_WHITELIST
        and not any(issubclass(cls, r) for r in registered)
    ]
    assert missing == [], (
        "以下异常类未在 errors.py 登记（若故意按 500 暴露请加进白名单）：\n"
        + "\n".join(f"  {c.__module__}.{c.__qualname__}" for c in missing)
    )


def test_unknown_platform_error_is_registered_as_400() -> None:
    """实证 bug 修复：UnknownPlatformError（原漏登记 500）→ 400 中文带平台清单。"""
    status, message = error_entry(
        UnknownPlatformError("未知平台 'foo'，已注册的平台：mspm0, stm32")
    )
    assert status == 400
    assert "未知平台" in message
    assert "stm32" in message  # 带已注册平台清单，用户可直接修正重试


def test_manual_reference_error_registered_as_400() -> None:
    """手动选参考资料校验失败（工单 01）：显式登记 error_to_http 表 → 400 中文。"""
    status, message = error_entry(
        ManualReferenceError("手动选择的参考文件不存在：幻觉 id")
    )
    assert status == 400
    assert "不存在" in message


def test_duplicate_file_path_error_registered_as_400() -> None:
    """跨模块同名文件冲突（生成侧查重兜底，工单 gen-file-collision-gate/01）：
    显式登记 error_to_http 表 → 400 中文。"""
    status, message = error_entry(
        DuplicateFilePathError(
            "所选模块存在同名文件冲突（生成工程链接期会报 UV4 L6200E "
            "multiply defined）：\n- 模块 zigbee_uart 与模块 zigbee_uart_key "
            "都声明文件 code/zigbee_uart.c"
        )
    )
    assert status == 400
    assert "同名文件冲突" in message
    assert "code/zigbee_uart.c" in message


def test_error_entry_contract_unchanged() -> None:
    """行为契约抽查：既有映射的状态码 / 文案逐字不变（表平移不改变行为）。"""
    assert error_entry(LLMError("boom")) == (502, "AI 服务调用失败：boom")
    assert error_entry(OSError("磁盘满")) == (400, "文件操作失败：磁盘满")
    assert error_entry(SelectionError("缺依赖")) == (400, "缺依赖")
    assert error_entry(RuntimeError("内部损坏")) == (
        500,
        "服务器内部错误（RuntimeError）：内部损坏",
    )
