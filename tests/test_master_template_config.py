"""mspm0 母版里「不是构建产物、但不能丢」的工程配置（回归守卫）。

**这条用例是被一次真实事故逼出来的**（2026-09-16 发现）：2026-09-15 的
「编译产物不入库」清理用一条 `(^|/)\\.settings/` 正则把 `library/masters/mspm0/.settings/`
整个扫掉了，其中 `org.eclipse.core.resources.prefs` 里钉着 **CCS 工程编码 UTF-8**
（`encoding/<project>=UTF-8`）——它不是可再生的构建产物，是工程配置：丢了以后生成的
CCS 工程在默认 GBK 的工作区里打开，中文注释有乱码风险。

当时的清理器**没有拦住**：它有「命中里像源码的要人工确认」这道闸，但判据是扩展名白名单，
而 `.prefs` 既不是源码也不是它认识的那几种配置后缀 → 静默照删。半天后是被
`tests/test_readme.py::test_directory_structure_syncs_with_master_templates`
（README 目录结构章 ↔ 母版实况双向同步）抓出来的——那条红在 main 上挂了整整一天没人发现，
因为**没人跑全套**（同一轮测试提速的工单 `test-speedup/02` 正是为了这件事）。

所以这里钉的不是「有个文件」，而是「这个文件里那个值」——下一个人再清一次时，
不许把工程配置当 IDE 状态顺手删掉。
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MSPM0_SETTINGS = ROOT / "library" / "masters" / "mspm0" / ".settings"

# 判据 = 内容里有这一行（不是「文件存在就行」：空文件或写坏的同名文件同样致命）
UTF8_ENCODING_PIN = "encoding/<project>=UTF-8"


def test_mspm0_master_pins_project_encoding_to_utf8() -> None:
    """母版必须把 CCS 工程编码钉成 UTF-8——中文注释的乱码防线。"""
    prefs = MSPM0_SETTINGS / "org.eclipse.core.resources.prefs"
    assert prefs.is_file(), (
        f"{prefs.relative_to(ROOT)} 不在母版里——CCS 工程编码钉丢了，"
        "生成的工程在 GBK 工作区里中文注释会乱码（判据与来由见本文件顶部）"
    )
    text = prefs.read_text(encoding="utf-8", errors="replace")
    assert UTF8_ENCODING_PIN in text, (
        f"{prefs.relative_to(ROOT)} 里没有 {UTF8_ENCODING_PIN}（实际内容：{text!r}）"
    )


def test_mspm0_master_ships_the_codan_prefs_that_purge_once_removed() -> None:
    """同一批被误删的另一件：codan 静态检查设置。

    它本身不影响编译，但它与编码钉同处 `.settings/`——**两者一起在场**才说明
    「母版 .settings/ 是工程配置、不是 IDE 状态」这条口径没被再次推翻。
    只钉一个文件的话，下次清理完全可以只删掉另一个而不被发现。
    """
    assert (MSPM0_SETTINGS / "org.eclipse.cdt.codan.core.prefs").is_file(), (
        "母版 .settings/ 里的 codan 设置不见了——它和编码钉是同一批工程配置"
    )
