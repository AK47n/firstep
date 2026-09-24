# -*- coding: utf-8 -*-
"""工单 hwcheck-acceptance/03 的量具：**被拦下时学生读到的那段字**（两分支逐条）。

要证明的是同一句话：出路里点名的动作，在这一页上真做得到。所以探针不只打印
400 原文，还逐条核对（每条都对着真页面 / 真判据，不靠自述）：

* **控件名在页面上**：出路里出现的栏位标题与勾选框文字，都能在
  `src/contest_generator/static/index.html` 里找到（单源常量由
  `tests/test_hwcheck.py::test_exit_copy_names_controls_that_exist_on_the_page`
  盯着，这里再从**读数**这一侧看一眼）；
* **实例名只在括号里**：把出路里所有 `（…）` 段摘掉之后，不该再剩下任何 SysConfig
  实例名（`OLED_SPI` / `AHT10` 这种）——门口那个反例正是拿实例名当唯一线索；
* **照着做能走通**：按出路里那条动作重跑一遍（取消勾选「OLED 屏」），必须真能生成
  （`hwcheck_view` 不再抛 400）——同脚那一支就在真母版上验这条。

两个分支各一幕（工单要求"两分支的 400 原文逐条打出来"）：

1. **重名那一支（注入现场）**：地猛星 + 默认 OLED 通道 + aht10——就是
   `.scratch/hwcheck-acceptance/exit-aht10.txt` 那一幕。工单 02 已把母版 14 组同名
   符号改名，真母版今天这组**能生成**了，所以现场由注入造出：把 AHT10 / OLED_SPI
   的符号名改回裸名（去掉 02 加的 `<实例名>_` 前缀——与 `tests/conftest.py` 的
   `_revert_pin_names` 同一手法：按「实例 + 当前符号名」定位，不手抄符号名清单）。
2. **同脚那一支（真库真母版）**：地猛星 + 默认双通道 + xunji + rc522——浏览器验收
   （`tests/browser/hwcheck.spec.mjs`）用的同一组；撞脚的既有通道带进来的 oled，
   也有器件 rc522，还有被 xunji 带进来的依赖 motor。

用法：`python .scratch/hwcheck-acceptance/probe-03-exit-copy.py [--out FILE]`
先落盘再打印（本机控制台 GBK）。
"""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.hwcheck import (  # noqa: E402
    HWCHECK_CHANNEL_LABELS,
    HWCHECK_CHANNEL_SECTION,
    HWCHECK_DEVICE_SECTION,
    HwCheckConfig,
    HwCheckError,
)
from contest_generator.hwcheck_board import (  # noqa: E402
    HWCHECK_PIN_EXIT_MARKER,
    hwcheck_view,
)
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS  # noqa: E402

LIBRARY = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"
INDEX_HTML = REPO / "src" / "contest_generator" / "static" / "index.html"
EXIT_AHT10 = REPO / ".scratch" / "hwcheck-acceptance" / "exit-aht10.txt"


def _revert_pin_names(text: str, instance: str) -> str:
    """把一个实例的引脚符号名改回裸名（去掉 02 加的 `<实例名>_` 前缀）。

    "撤回改名" = 去掉前缀，所以不手抄任何符号名清单（母版重排 / 改缩进也不会碎）；
    一处都找不到 = 母版漂移，当场大声失败（不静默造一个"不撞"的假现场）。
    """
    pattern = re.compile(
        r'(?m)^(?P<head>\s*' + re.escape(instance)
        + r'\.associatedPins\[\d+\]\.\$name\s*=\s*)"'
        + re.escape(instance) + r'_(?P<symbol>[A-Za-z0-9_]+)";'
    )
    text, count = pattern.subn(r'\g<head>"\g<symbol>";', text)
    assert count, f"母版里找不到 {instance} 的 `<实例名>_<符号>` 落点"
    return text


def _injected_masters(tmp: Path) -> Path:
    """母版库的临时副本，其中 AHT10 / OLED_SPI 的符号名被撤回成裸名（重名现场）。"""
    target = tmp / "masters"
    shutil.copytree(MASTERS, target)
    syscfg = target / "mspm0" / "mspm0.syscfg"
    text = syscfg.read_text(encoding="utf-8")
    for instance in ("AHT10", "OLED_SPI"):
        text = _revert_pin_names(text, instance)
    syscfg.write_text(text, encoding="utf-8")
    return target


def _message(config: HwCheckConfig, masters: Path) -> str:
    """走产品那条路取 400 原文（`hwcheck_view` 装不下时抛 HwCheckError = 页面读到的字）。"""
    try:
        hwcheck_view(
            config, module_library_dir=LIBRARY, masters_dir=masters,
        )
    except HwCheckError as exc:
        return str(exc)
    return ""


def _check_exit_block(label: str, message: str, lines: list[str]) -> None:
    """出路那一段的逐条核对（控件在页面上 / 实例名只在括号里）。"""
    block = message.split(HWCHECK_PIN_EXIT_MARKER, 1)[1]
    html = INDEX_HTML.read_text(encoding="utf-8")
    controls = [HWCHECK_CHANNEL_SECTION, HWCHECK_DEVICE_SECTION,
                *HWCHECK_CHANNEL_LABELS.values()]
    for control in controls:
        if control in block:
            assert control in html, f"{label}：出路点名了页面上没有的控件「{control}」"
            lines.append(f"  ✓ 点名的控件在页面上：{control}")
    # 先摘掉括号段与**控件名本身**（勾选框文字「OLED 屏」与栏位标题——它们是这一页
    # 真有的东西，不是实例名），剩下的才该干净：实例名 = `INSTANCE_CONSUMERS` 的键
    # （单源）+ 带下划线的大写 token（母版里没登记归属的新实例也兜住）。
    # 两种括号都要摘：中文句子用「（…）」，`instance_label` 的标签用「(…)」。
    stripped = block
    for pattern in (r"（[^）]*）", r"\([^)]*\)"):
        stripped = re.sub(pattern, "", stripped)
    for control in controls:
        stripped = stripped.replace(control, "")
    leftover = sorted(
        {name for name in INSTANCE_CONSUMERS if name in stripped}
        | set(re.findall(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b", stripped))
    )
    assert not leftover, f"{label}：实例名跑到括号外面了：{leftover}\n{block}"
    lines.append("  ✓ 实例名只作括号里的补充信息（摘掉括号后不剩实例名）")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8，先落盘再打印）")
    args = parser.parse_args()

    report: list[str] = [
        "=== 工单 hwcheck-acceptance/03：被拦下时的出路（两分支 400 原文）===",
        "",
    ]

    # ① 重名那一支：地猛星 + 默认 OLED 通道 + aht10（注入现场）
    with tempfile.TemporaryDirectory() as tmp:
        masters = _injected_masters(Path(tmp))
        config = HwCheckConfig(
            platform=PLATFORM_MSPM0, debug_uart=True, oled=True,
            devices=("aht10",),
        )
        message = _message(config, masters)
        assert message, "注入现场应当被拦下（真母版今天不拦——那正是 02 的成果）"
        report.append("【分支一·重名】地猛星 + 默认 OLED 通道 + aht10（注入现场）")
        report.append(message)
        report.append("")
        report.append("  核对：")
        _check_exit_block("分支一", message, report)
        # 照它做能走通：取消勾选「OLED 屏」
        after = _message(
            HwCheckConfig(
                platform=PLATFORM_MSPM0, debug_uart=True, oled=False,
                devices=("aht10",),
            ),
            masters,
        )
        assert not after, f"取消勾选 OLED 屏之后仍被拦下：\n{after}"
        report.append("  ✓ 照着做能走通：取消勾选「OLED 屏」后不再被拦下")
        # 出路第 2 条也要**照着做一遍**（评审指出：只走通第 1 条 = 读数缺一半）
        after_device = _message(
            HwCheckConfig(
                platform=PLATFORM_MSPM0, debug_uart=True, oled=True,
                devices=(),
            ),
            masters,
        )
        assert not after_device, (
            f"去掉器件 aht10 之后仍被拦下：\n{after_device}"
        )
        report.append("  ✓ 照着做能走通：去掉「3. 要测的器件」里的 aht10 后不再被拦下")
        # 旧文案**必须消失**（票面点名的现状反例，原文见 exit-aht10.txt 的 git 历史）
        for forbidden in (
            "回到上面的器件选择，把上面点名的那几件里",
            "换一件同类替代",
        ):
            assert forbidden not in message, (
                f"旧出路文案又回来了：「{forbidden}」\n{message}"
            )
        report.append("  ✓ 票面点名的那两条旧出路（指向不存在的控件）已不再出现")
        # 这一支是**注入现场**：真母版今天不拦（02 的成果），所以现场来源要写清
        report.append(
            "  · 现场说明：本支是注入现场（真母版 + 撤回一处改名），真母版上这组今天"
            "能生成——`exit-aht10.txt` 是改之前的 HEAD 实测（立项依据），"
            "改之后的同一幕就是本节读数"
        )
        report.append("")

    # ② 同脚那一支：地猛星 + 默认双通道 + xunji + rc522（真库真母版）
    config = HwCheckConfig(
        platform=PLATFORM_MSPM0, debug_uart=True, oled=True,
        devices=("xunji", "rc522"),
    )
    message = _message(config, MASTERS)
    assert message, "真母版上这一组应当被拦下（浏览器验收用的就是它）"
    report.append("【分支二·同脚】地猛星 + 默认双通道 + xunji + rc522（真库真母版）")
    report.append(message)
    report.append("")
    report.append("  核对：")
    _check_exit_block("分支二", message, report)
    after = _message(
        HwCheckConfig(
            platform=PLATFORM_MSPM0, debug_uart=True, oled=False,
            devices=("xunji", "rc522"),
        ),
        MASTERS,
    )
    assert not after, f"取消勾选 OLED 屏之后仍被拦下：\n{after}"
    report.append("  ✓ 照着做能走通：取消勾选「OLED 屏」后不再被拦下（浏览器用例同一步）")
    report.append("")

    text = "\n".join(report) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")     # 先落盘
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
