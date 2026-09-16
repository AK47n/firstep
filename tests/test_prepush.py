# -*- coding: utf-8 -*-
"""提交闸门的选择器守卫（工单 commit-gate/01）。

**为什么值得单独立一套用例**：闸门这东西失效的方式是**静默**的——选择器算错一个分支，
大概率不会报错，只会「少跑了一批用例」，而"少跑"正好长得像"全绿"。所以这里既测
每类规则的**正例**，也测**反例**（认不出来的路径必须倒向整套），并用真实仓库的事实
兜底（`wide_modules()` 读的是测试文件里真实的 import 行）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO / "tools" / "prepush.py"


def load_prepush():
    spec = importlib.util.spec_from_file_location("prepush_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["prepush_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prepush():
    return load_prepush()


@pytest.fixture()
def selection(prepush):
    """用**真实仓库**的测试文件表与真实 import 分布做判据（不喂假数据）。"""

    def _select(*changed: str):
        return prepush.select_tests(list(changed))

    return _select


@pytest.fixture(autouse=True)
def _restore_repo_root(prepush):
    """`make_git_repo` 会把 prepush.REPO_ROOT 改指临时仓库——用完必须还原。"""
    original = prepush.REPO_ROOT
    yield
    prepush.REPO_ROOT = original


# ---------------------------------------------------------------------------
# 正例：每类规则各一条
# ---------------------------------------------------------------------------


def test_test_file_change_runs_only_itself(selection):
    """改测试文件 → 只跑它自己（别拖上半仓）。"""
    result = selection("tests/test_manifest.py")
    assert result.full is False
    assert result.paths == ("tests/test_manifest.py",)


def test_narrow_module_change_runs_its_namesake_test(selection):
    """窄面模块（有同名测试、不在公共面）→ 只跑同名测试。"""
    result = selection("src/contest_generator/changelog.py")
    assert result.full is False
    assert result.paths == ("tests/test_changelog.py",)


def test_wide_module_change_runs_everything(selection):
    """公共面模块（被 ≥ 阈值个测试文件 import）→ 整套。"""
    result = selection("src/contest_generator/manifest.py")
    assert result.full is True
    assert "公共面" in result.reasons["src/contest_generator/manifest.py"]


def test_library_change_runs_library_family(selection):
    """库内容改动 → 库与母版守卫族（不是整套，也不能漏母版同步守卫）。"""
    result = selection("library/modules/oled/manifest.json")
    assert result.full is False
    assert "tests/test_library_invariants.py" in result.paths
    assert "tests/test_master_template_config.py" in result.paths
    assert "tests/test_readme.py" in result.paths


def test_doc_change_runs_doc_family_only(selection):
    """纯文档改动 → 文档守卫族，且不跑产品测试。"""
    result = selection("docs/agents/releasing.md")
    assert result.full is False
    assert set(result.paths) == {
        "tests/test_readme.py",
        "tests/test_changelog.py",
        "tests/test_repo_language.py",
        "tests/test_onboarding_docs.py",
        "tests/test_ps1_encoding.py",
    }


def test_mixed_changes_union(selection):
    """多类混合 → 取并集（文档 + 库 + 一个窄模块）。"""
    result = selection(
        "docs/agents/workflow.md",
        "library/masters/mspm0/main.c",
        "src/contest_generator/changelog.py",
    )
    assert result.full is False
    assert "tests/test_changelog.py" in result.paths
    assert "tests/test_library_invariants.py" in result.paths
    assert "tests/test_readme.py" in result.paths


def test_empty_change_runs_nothing(selection):
    """空改动 → 不跑（例如只推一个空合并）。"""
    result = selection()
    assert result.full is False
    assert result.paths == ()


# ---------------------------------------------------------------------------
# 反例：认不出来的一律倒向整套（闸门不许被一个没想到的文件类型绕过）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "src/contest_generator/static/js/fx/module.js",   # 前端资产
        "src/contest_generator/templates/index.html",     # 模板
        "src/contest_generator/boards/board_g3507.json",  # 包内数据子目录
        "tools/pack-update.ps1",                          # 仓库工具
        ".githooks/commit-msg",                           # 闸门自身
        ".github/workflows/ci.yml",                       # CI 配置
        "pyproject.toml",                                 # 投影配置
        ".gitignore",                                     # 投影配置
        "Makefile",                                       # 完全认不出来
        "tests/_byte_server.py",                          # tests 下的非 test_*.py
    ],
)
def test_unrecognized_paths_fall_back_to_full(selection, path):
    """倒向更严：认不出来的落点必须整套跑，理由里点名是哪个文件。"""
    result = selection(path)
    assert result.full is True, f"{path} 应当倒向整套，实际 {result.paths}"
    assert path.replace("\\", "/") in result.reasons


def test_module_without_namesake_test_falls_back_to_full(prepush):
    """源码模块没有同名测试 → 整套（用合成表测，不依赖仓库当前恰好缺哪个）。"""
    result = prepush.select_tests(
        ["src/contest_generator/nonexistent_module.py"],
        tests=frozenset({"tests/test_manifest.py"}),
        wide=frozenset(),
    )
    assert result.full is True
    assert "没有同名测试" in result.reasons["src/contest_generator/nonexistent_module.py"]


def test_package_init_falls_back_to_full(prepush):
    """改包入口 → 整套（版本号是发版判据的输入）。"""
    result = prepush.select_tests(
        ["src/contest_generator/__init__.py"],
        tests=frozenset({"tests/test_manifest.py"}),
        wide=frozenset(),
    )
    assert result.full is True


# ---------------------------------------------------------------------------
# 事实兜底：判据必须与仓库现状对得上（否则闸门在悄悄失效）
# ---------------------------------------------------------------------------


def test_wide_modules_are_derived_from_real_imports(prepush):
    """公共面名单是**实测推导**的：清单里的每个模块都必须真被 ≥ 阈值个测试文件 import。"""
    import re

    pattern = re.compile(
        r"^\s*(?:from|import)\s+contest_generator\.([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE
    )
    counts: dict[str, int] = {}
    for test_file in sorted((REPO / "tests").glob("test_*.py")):
        text = test_file.read_text(encoding="utf-8", errors="replace")
        for name in sorted(set(pattern.findall(text))):
            counts[name] = counts.get(name, 0) + 1

    prepush.reset_cache()
    wide = prepush.wide_modules()
    assert wide, "一个公共面模块都没推出来——判据本身失效了"
    for module in wide:
        assert counts.get(module, 0) >= prepush.WIDE_IMPORT_THRESHOLD, (
            f"{module} 被算成公共面，实际只有 {counts.get(module, 0)} 个测试文件 import 它"
        )


def test_every_family_file_exists(prepush):
    """守卫族清单必须只含真实存在的测试文件（改名后不会静默跳过）。"""
    for path in (*prepush.LIBRARY_FAMILY, *prepush.DOCUMENT_FAMILY):
        assert (REPO / path).is_file(), f"{path} 不存在——守卫族清单过期了"


def test_guard_families_are_not_the_whole_suite(prepush):
    """两个族都必须显著小于整套（否则「子集」是假的）。"""
    total = len(list((REPO / "tests").glob("test_*.py")))
    assert len(prepush.DOCUMENT_FAMILY) < total / 4
    assert len(prepush.LIBRARY_FAMILY) < total / 4


def test_unknown_extension_in_src_package_falls_back(prepush):
    """包内非 .py 落点（例如 static/ 下的 .js）不许被当成窄面。"""
    result = prepush.select_tests(
        ["src/contest_generator/static/js/ui/generate.js"],
        tests=frozenset({"tests/test_webapp.py"}),
        wide=frozenset(),
    )
    assert result.full is True


# ---------------------------------------------------------------------------
# 闸门自身故障 → 放行（不许把维护者堵在门外）
# ---------------------------------------------------------------------------


def test_safe_main_passes_through_when_selector_blows_up(prepush, monkeypatch, capsys):
    """选择器抛错 → 打印原因 + 返回 0（放行），绝不因闸门坏了卡人。"""

    def boom(argv=None):
        raise RuntimeError("模拟选择器崩溃")

    monkeypatch.setattr(prepush, "main", boom)
    code = prepush.safe_main([])
    assert code == 0
    assert "闸门自身故障" in capsys.readouterr().out


def test_safe_main_propagates_test_failure(prepush, monkeypatch):
    """测试真红 → 退出码原样传出（这是闸门存在的意义，不能被吞）。"""
    monkeypatch.setattr(prepush, "main", lambda argv=None: 1)
    assert prepush.safe_main([]) == 1


def test_off_mode_skips_gate(prepush, monkeypatch, capsys):
    """FIRSTEP_PREPUSH=off → 跳过并明写警告。"""
    monkeypatch.setenv("FIRSTEP_PREPUSH", "off")
    assert prepush.main([]) == 0
    out = capsys.readouterr().out
    assert "跳过闸门" in out
    assert "不鼓励" not in out or "仅限" in out


def test_dry_run_does_not_execute_pytest(prepush, monkeypatch, capsys):
    """--dry-run 只说不跑（不许真调 pytest）。"""

    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run 不该执行 pytest")

    monkeypatch.setattr(prepush, "run_pytest", forbidden)
    code = prepush.main(["--changed", "src/contest_generator/changelog.py", "--dry-run"])
    assert code == 0
    assert "tests/test_changelog.py" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 端到端判据（选择器侧）：真实 refs → 真实选择结果
# ---------------------------------------------------------------------------


def test_real_refs_to_selection_end_to_end(prepush):
    """从**真实 git diff** 算改动 → 选出对应的测试（把钩子那条链的判据也钉住）。

    用**自建的小仓库**而不是本仓库的 `HEAD~1..HEAD`：CI 的 checkout 上那条区间
    可能是空的（合并提交 / CHANGELOG 自动提交），用例会变成假红——2026-09-16 CI
    实测就是 `assert []`。小仓库里改动是自己造的，任何 checkout 都成立。
    """
    repo, first, second = make_git_repo(prepush, files=("src/contest_generator/changelog.py",))
    changed, has_tag = prepush.changed_from_refs(
        f"refs/heads/main {second} refs/heads/main {first}\n"
    )
    assert has_tag is False
    assert changed == ["src/contest_generator/changelog.py"], changed

    selection = prepush.select_tests(changed)
    assert selection.paths == ("tests/test_changelog.py",)
    assert selection.reasons


def test_core_file_in_real_diff_forces_full_suite(prepush):
    """真正的端到端杀器用例：diff 里只要有一个公共面文件，就必须整套。"""
    repo, _, second = make_git_repo(prepush, files=("notes.md",))
    changed, _ = prepush.changed_from_refs(
        f"refs/heads/main {second} refs/heads/main {second}\n"
    )
    core = "src/contest_generator/manifest.py"
    selection = prepush.select_tests([*changed, core])
    assert selection.full is True
    assert "公共面" in selection.reasons[core]

    # 真仓库里这个模块也确实存在（判据不是凭空写的）
    assert (REPO / core).is_file()


# ---------------------------------------------------------------------------
# 两个真缺陷的回归（2026-09-16 端到端演练里被真 push 放过去的）
# ---------------------------------------------------------------------------


def test_new_branch_push_does_not_degenerate_to_empty(prepush):
    """**回归（真缺陷①）**：推新分支（远端 sha 全零）不许算出「零改动放行」。

    当时的写法拿 `origin/main` 当基点，而本机克隆里 `origin/main` 正好 = 本地 HEAD，
    于是 diff 恒空 → 闸门报「没有守卫要跑」→ 一笔删掉母版守卫的提交被真 push 放过去了。
    现在的契约是二选一，**绝不许是「零改动 + 不要整套」**：
      · 基点可解析 → 给出那批提交的真实改动；
      · 否则 → 倒向整套（第二个返回值在钩子侧就是「整套」的意思）。
    """
    repo, _, second = make_git_repo(prepush, files=("src/contest_generator/changelog.py",))
    changed, force_full = prepush.changed_from_refs(
        f"HEAD {second} refs/heads/main {'0' * 40}\n"
    )
    assert changed or force_full, (
        "推新分支既没算出改动、也没要求整套——这正是当时被真 push 放过去的那条路"
    )
    if force_full:
        assert changed == [], "倒向整套时不该再带一份可能不全的改动清单"


def test_new_branch_without_usable_base_falls_back_to_head_parent(prepush, monkeypatch):
    """基点拿不到时退到 HEAD~1（新分支通常只有一个新提交），仍要给出真实改动。"""
    monkeypatch.setattr(prepush, "base_ref", lambda: "")
    repo, _, second = make_git_repo(prepush, files=("src/contest_generator/changelog.py",))
    changed, force_full = prepush.changed_from_refs(
        f"HEAD {second} refs/heads/main {'0' * 40}\n"
    )
    assert force_full is False
    assert changed == ["src/contest_generator/changelog.py"], changed


def test_remote_branch_update_reports_pushed_commits(prepush):
    """远端已有分支：`remote_sha..local_sha` 就是本次推的改动（这条一直是好的）。"""
    repo, first, second = make_git_repo(prepush, files=("src/contest_generator/changelog.py",))
    changed, force_full = prepush.changed_from_refs(
        f"refs/heads/main {second} refs/heads/main {first}\n"
    )
    assert force_full is False
    assert changed == ["src/contest_generator/changelog.py"], changed


def test_base_ref_returns_readable_reference(prepush):
    """基点引用必须真实可解析（不能返回一个 git 不认识的字符串）。"""
    base = prepush.base_ref()
    assert base, "拿不到基点引用"
    import subprocess as sp

    result = sp.run(["git", "rev-parse", "--verify", f"{base}^{{commit}}"],
                    cwd=str(REPO), capture_output=True, text=True)
    assert result.returncode == 0, f"基点 {base!r} 解析不了：{result.stderr}"


def test_no_duplicate_test_function_names():
    """本文件里不许出现重名用例。

    **为什么值得一条守卫**（2026-09-16 踩到）：我重写「远端已有分支」那条用例时，
    新版本加在前面、旧的留在后面——Python 取**后一个**定义，于是 CI 上跑的一直是
    旧的非确定性版本，改了三次都没生效。pytest 对重名**不报错**（静默覆盖），
    这类错误只能靠机械判据挡。
    """
    import re

    source = (REPO / "tests" / "test_prepush.py").read_text(encoding="utf-8")
    names = re.findall(r"^def (test_[A-Za-z0-9_]+)\(", source, re.MULTILINE)
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert not duplicates, f"重名用例（pytest 只会跑最后一个）：{duplicates}"


def make_git_repo(prepush, *, files: tuple[str, ...], tmp_root=None):
    """造一个**两提交的小仓库**并让 prepush 在它里面跑 → (repo, first, second)。

    为什么要自建：`changed_from_refs` 读的是**当前仓库**的 git 状态，而 CI 的 checkout
    上「上一笔提交改了什么」完全不受控（合并提交 / 只有 CHANGELOG 的自动提交），
    拿它当夹具的用例会变成假红或假绿。小仓库里改动是自己造的，任何 checkout 都成立。
    """
    import subprocess as sp
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="prepush-fixture-", dir=tmp_root))
    (root / "src" / "contest_generator").mkdir(parents=True)
    (root / "src" / "contest_generator" / "changelog.py").write_text("x = 1\n", encoding="utf-8")
    (root / "notes.md").write_text("n\n", encoding="utf-8")
    sp.run(["git", "init", "-q", "-b", "main"], cwd=str(root), capture_output=True)
    sp.run(["git", "config", "user.email", "t@t"], cwd=str(root), capture_output=True)
    sp.run(["git", "config", "user.name", "t"], cwd=str(root), capture_output=True)
    sp.run(["git", "add", "-A"], cwd=str(root), capture_output=True)
    sp.run(["git", "commit", "-qm", "first"], cwd=str(root), capture_output=True)
    first = sp.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                   capture_output=True, text=True).stdout.strip()

    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed\n", encoding="utf-8")
    sp.run(["git", "add", "-A"], cwd=str(root), capture_output=True)
    sp.run(["git", "commit", "-qm", "second"], cwd=str(root), capture_output=True)
    second = sp.run(["git", "rev-parse", "HEAD"], cwd=str(root),
                    capture_output=True, text=True).stdout.strip()

    original = prepush.REPO_ROOT
    prepush.REPO_ROOT = root
    return root, first, second



