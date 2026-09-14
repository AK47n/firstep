"""完整包打包核心测试（工单 full-download/01）。

覆盖：完整包扫描与排除规则（第三方安装包 / SDK 打包件 / 缓存 / 备份目录 /
虚拟环境都不进包）、包内文件清单与 zip 内容一一对应、清单 SHA256 可复算、
分卷切分（含单文件超限单独成卷）、资料库基线清单与资料库扫描一致、删除
清单（有基线 / 无基线两态）、四件套落盘与 CLI 入口。
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from contest_generator.full_pack import (
    MATERIALS_MANIFEST_KEY,
    MAX_ENTRY_PATH_CHARS,
    TOP_LEVEL_ENTRIES,
    build_full_manifest,
    build_zip_volumes,
    derive_slug,
    excluded_paths,
    full_manifest_filename,
    main,
    materials_excluded,
    overlong_entries,
    prepare_full_package,
    register_materials_dirs,
    scan_tree,
    split_volumes,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_mini_repo(root: Path) -> Path:
    """迷你 firstep 仓库树：含中文目录、干扰件、备份目录、缓存。"""
    _write(root / "src" / "contest_generator" / "__init__.py", '__version__ = "9.9.9"\n')
    _write(root / "src" / "contest_generator" / "static" / "index.html", "<html>ok</html>")
    _write(root / "library" / "modules" / "oled" / "manifest.json", '{"slug": "oled"}')
    _write(root / "library" / "masters" / "stm32" / "main.c", "int main(void){return 0;}")
    _write(root / "sources" / "contest" / "2026C" / "题面.md", "# 2026C 题面\n")
    _write(root / "sources" / "materials" / "2026_08_MSPM0G3507与常用芯片手册" / "手册.md", "# 手册\n")
    _write(root / "sources" / "materials" / "K230-Cam-Example" / "例程" / "main.py", "print(1)\n")
    _write(root / "docs" / "agents" / "workflow.md", "# 工作流\n")
    _write(root / "tools" / "update-app.py", "print('updater')\n")
    _write(root / "README.md", "# firstep\n")
    _write(root / "pyproject.toml", "[project]\nname = 'contest-generator'\n")

    # 干扰件：一个都不该进包
    _write(root / "sources" / "materials" / "2026_04_配套资料" / "00_CH341SER.EXE", "MZ-binary")
    _write(
        root / "sources" / "materials" / "2026_04_配套资料" / "01_CCS_20.5.0.00028_win.zip",
        "CCS-installer",
    )
    _write(root / "sources" / "materials" / "2026_06_视觉资料" / "01_tsp-xbhdcc-v1.z01", "sdk-part")
    _write(root / "sources" / "materials" / "2026_06_视觉资料" / "dataset.zip", "dataset")
    _write(root / "sources" / "materials" / "2026_06_视觉资料" / "12_new_boot.img", "firmware")
    _write(root / "sources" / "materials" / "C7-3-4L 板资料" / "arduino-ide_2.2.1.rar", "installer")
    _write(root / "sources" / "materials" / "2026_04_配套资料" / "【云台】05_SPI屏幕驱动代码.zip", "spi")
    _write(root / "library" / "revise-backups" / "20260824" / "Debug" / "out.axf", "elf")
    _write(root / "library" / "fix-backups" / "20260824" / "main.c", "old")
    _write(root / "sources" / ".trash-pdf" / "old.pdf", "pdf")
    _write(root / "src" / "contest_generator" / "__pycache__" / "x.pyc", "bytecode")
    _write(root / "sources" / "materials" / "K230-Cam-Example" / "例程" / "__pycache__" / "m.pyc", "bytecode")
    _write(root / "node_modules" / "left-pad" / "index.js", "module.exports = 1")
    _write(root / ".venv" / "Scripts" / "python.exe", "exe")
    _write(root / ".scratch" / "full-download" / "notes.md", "# 工作区笔记")
    _write(root / ".git" / "config", "[core]")
    _write(root / "updates" / "updater.log", "log line")
    _write(root / "logs" / "server.log", "log line")
    _write(root / "tools" / "__pycache__" / "update-app.cpython-313.pyc", "bytecode")
    return root


# ---------------------------------------------------------------------------
# 扫描与排除规则
# ---------------------------------------------------------------------------


def test_scan_tree_includes_content_files(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    paths = [f.path for f in scan_tree(tree)]
    assert "src/contest_generator/__init__.py" in paths
    assert "library/modules/oled/manifest.json" in paths
    assert "sources/contest/2026C/题面.md" in paths
    assert "sources/materials/2026_08_MSPM0G3507与常用芯片手册/手册.md" in paths
    assert "sources/materials/K230-Cam-Example/例程/main.py" in paths
    assert "README.md" in paths
    assert "pyproject.toml" in paths
    # 确定性排序（diff 与分卷稳定）
    assert paths == sorted(paths)


def test_scan_tree_excludes_installers_and_sdk(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    paths = [f.path for f in scan_tree(tree)]
    for excluded in (
        "sources/materials/2026_04_配套资料/00_CH341SER.EXE",
        "sources/materials/2026_04_配套资料/01_CCS_20.5.0.00028_win.zip",
        "sources/materials/2026_06_视觉资料/01_tsp-xbhdcc-v1.z01",
        "sources/materials/2026_06_视觉资料/dataset.zip",
        "sources/materials/2026_06_视觉资料/12_new_boot.img",
        "sources/materials/C7-3-4L 板资料/arduino-ide_2.2.1.rar",
        "sources/materials/2026_04_配套资料/【云台】05_SPI屏幕驱动代码.zip",
    ):
        assert excluded not in paths, excluded


def test_scan_tree_excludes_caches_backups_and_workspace(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    paths = set(f.path for f in scan_tree(tree))
    for excluded in (
        "library/revise-backups/20260824/Debug/out.axf",
        "library/fix-backups/20260824/main.c",
        "sources/.trash-pdf/old.pdf",
        "src/contest_generator/__pycache__/x.pyc",
        "sources/materials/K230-Cam-Example/例程/__pycache__/m.pyc",
        "node_modules/left-pad/index.js",
        ".venv/Scripts/python.exe",
        ".scratch/full-download/notes.md",
        ".git/config",
        "updates/updater.log",
        "logs/server.log",
        "tools/__pycache__/update-app.cpython-313.pyc",
    ):
        assert excluded not in paths, excluded


def test_scan_tree_ignores_non_allowlisted_top_level(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    _write(tree / "random-notes.txt", "not part of the tool")
    _write(tree / "build" / "artifact.bin", "bin")
    paths = set(f.path for f in scan_tree(tree))
    assert "random-notes.txt" not in paths
    assert "build/artifact.bin" not in paths
    assert "README.md" in paths


def test_excluded_paths_reports_reason(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    excluded = excluded_paths(tree)
    assert excluded["sources/materials/2026_04_配套资料/00_CH341SER.EXE"] == "installer-glob"
    assert excluded["library/fix-backups/20260824/main.c"] == "dir-name"
    assert excluded["sources/materials/K230-Cam-Example/例程/__pycache__/m.pyc"] == "dir-name"
    assert "src/contest_generator/__init__.py" not in excluded


def test_top_level_entries_cover_tool_root() -> None:
    assert "src" in TOP_LEVEL_ENTRIES
    assert "library" in TOP_LEVEL_ENTRIES
    assert "sources" in TOP_LEVEL_ENTRIES
    assert "tools" in TOP_LEVEL_ENTRIES
    assert "README.md" in TOP_LEVEL_ENTRIES
    # 面向新用户的包内说明书（工单 newuser-download/02）：漏登记 = 它根本不进包，
    # 而「解压后没有任何说明」正是要根治的病。
    assert "00-START-HERE.txt" in TOP_LEVEL_ENTRIES


def test_repo_start_here_ships_in_package() -> None:
    """真仓库的 `00-START-HERE.txt` 必须真的进包（工单 newuser-download/02）。

    反向也验：`excluded_paths` 里不得出现它——两边都断言，防「清单有、包里没有」
    与「包里没有、没人发现」两种漏法。
    """
    repo = Path(__file__).resolve().parent.parent
    source = repo / "00-START-HERE.txt"
    assert source.is_file(), "仓库根缺少 00-START-HERE.txt（新用户解压后第一眼要看到的东西）"

    paths = {f.path for f in scan_tree(repo)}
    assert "00-START-HERE.txt" in paths, "00-START-HERE.txt 未进包（白名单漏登记？）"
    assert "00-START-HERE.txt" not in excluded_paths(repo), "00-START-HERE.txt 被判为排除项，进不了包"


def test_start_here_sorts_first_in_explorer() -> None:
    """`00-START-HERE.txt` 必须在解压目录里排**第一位**（工单 newuser-download/02）。

    为什么是硬要求：它排在中间就等于没有——实测裸叫 `START-HERE.txt` 时按名称排在
    README 之下（#11/14），隐藏扩展名时更靠后（#17/22）。新人只会点第一眼看到的东西。

    只拿**进包的那些根级条目**比（`TOP_LEVEL_ENTRIES` ∩ 仓库根实际内容），
    因为用户解压后看到的就是这些；排序口径近似资源管理器：先按「主名（去扩展名）不区分大小写」，
    同名再按全名。
    """
    repo = Path(__file__).resolve().parent.parent
    shipped = sorted(
        [p.name for p in repo.iterdir() if p.name in TOP_LEVEL_ENTRIES],
        key=lambda n: ((n.rsplit(".", 1)[0] if "." in n else n).lower(), n),
    )
    assert shipped, "仓库根没有任何进包条目——白名单与磁盘脱节了？"
    # 点开头的文件（`.gitattributes` / `.gitignore`）由资源管理器排在更前，且用户通常没开显示
    # 隐藏文件——拿「用户实际看得到的那批」比第一眼落点。
    visible = [n for n in shipped if not n.startswith(".")]
    assert visible[0] == "00-START-HERE.txt", (
        f"解压后第一个可见文件应是 00-START-HERE.txt，实际是 {visible[0]}；前 3 项：{visible[:3]}"
    )


def test_start_here_is_newcomer_facing_and_readable() -> None:
    """`00-START-HERE.txt` 面向新用户：UTF-8 无 BOM、一屏内读完、三步链路齐全。"""
    repo = Path(__file__).resolve().parent.parent
    raw = (repo / "00-START-HERE.txt").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "00-START-HERE.txt 不应带 UTF-8 BOM"
    text = raw.decode("utf-8")  # 解不开就是编码错了，直接红
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) <= 40, f"00-START-HERE.txt 太长（{len(lines)} 行），新人不会读完"
    for needle, why in (
        ("install.bat", "第一步该点哪个文件"),
        ("firstep", "桌面快捷方式的名字"),
        ("http://127.0.0.1:8000", "启动后浏览器会打开的地址"),
        ("DeepSeek API key", "要配的东西叫什么"),
        ("设置", "配 key 的入口在哪"),
        ("webapp.log", "出问题去哪看日志"),
    ):
        assert needle in text, f"00-START-HERE.txt 缺少关键信息：{why}（{needle}）"
    # 三条「预期行为」——消除「是不是坏了」的误解
    assert ".venv" in text, "00-START-HERE.txt 未说明『包里没有 .venv 是正常的』"
    assert "重复" in text, "00-START-HERE.txt 未说明 install.bat 可重复运行"


def test_readme_promised_package_files_exist_in_package() -> None:
    """README「获取方式」里点名「去包里看」的文件，必须真的在包里（工单 newuser-download/02）。

    这是把「文档不得指向不存在的东西」钉成跨文件不变量的最小一条：工单 01 曾短暂写过
    「解压后照包里的 `START-HERE.txt` 走」，而那时它还没进包——正是要根治的病。
    只检查「看起来像文件名」（含 `.`、无空格、长度合理）的 token，自然语言与下载资产名不算。
    """
    import re

    repo = Path(__file__).resolve().parent.parent
    readme = (repo / "README.md").read_text(encoding="utf-8")
    start = readme.find("## 获取方式")
    assert start >= 0, "README 缺少「获取方式」章节"
    rest = readme[start:]
    end = rest.find("\n## ", 3)
    section = rest if end < 0 else rest[:end]

    in_pack = {f.path for f in scan_tree(repo)}
    # 排除三类「不是包内文件名」的 token：发布资产名、版本号、资产名后缀（`.removed.txt` 这种
    # 只写了后缀的，不是用户要去包里找的文件）。
    not_package_file = re.compile(r"^(?:firstep-|v\d|\.)")
    promised = {
        token
        for token in re.findall(r"`([^`\n]+)`", section)
        if "." in token and " " not in token and 3 <= len(token) <= 40
        and not not_package_file.match(token)
    }
    assert "00-START-HERE.txt" in promised, (
        "「获取方式」应点名包内的 00-START-HERE.txt（新用户解压后的第一落点）"
    )
    missing = sorted(t for t in promised if t not in in_pack)
    assert not missing, f"「获取方式」点名了不在包内的文件：{missing}"


def test_excluded_file_count_stays_small_on_real_tree() -> None:
    """真仓库上排除集合必须是小集合（防排除模式过宽误伤内容文件）。

    只统计**白名单顶层之内**的排除项（`.git` / `.scratch` 这类整目录不进包
    属于预期，不该计入阈值）。
    """
    repo = Path(__file__).resolve().parent.parent
    excluded = excluded_paths(repo)
    inside = {
        path: reason
        for path, reason in excluded.items()
        if path.split("/", 1)[0] in TOP_LEVEL_ENTRIES
    }
    assert inside, "白名单内的排除集合不应为空——否则排除规则没生效"
    reasons = set(inside.values())
    assert reasons <= {"dir-name", "file-name", "installer-glob", "file-suffix"}
    # 量级守卫：排除项应远小于内容文件数（真仓库现状 ≈4.2k，绝大多数是
    # library 下两个本地备份目录；安装包类只有 33 个）
    assert len(inside) < 6000, f"白名单内排除集合异常大：{len(inside)} 项"
    installer_count = sum(1 for r in inside.values() if r == "installer-glob")
    assert 0 < installer_count <= 100, f"安装包类排除数异常：{installer_count}"
    # 内容文件绝不能被排除
    for must_keep in (
        "src/contest_generator/full_pack.py",
        "README.md",
        "pyproject.toml",
    ):
        assert must_keep not in excluded, must_keep


# ---------------------------------------------------------------------------
# 包内路径长度上限（工单 path-budget/01）
#
# 病灶与判据：Windows 资源管理器「全部解压缩」走老 API、硬卡 259 字符（含解压
# 根目录），超了报 `0x80010135: 路径太长`，点「跳过」**静默丢文件**——用户拿到
# 一个看似解压成功的残缺包。工具自身的解压（Python zipfile）与 `tar.exe` 走长
# 路径 API 不受影响，所以只有一条真判据：包内相对路径本身不能太长。
# ---------------------------------------------------------------------------


def _long_material_file(tree: Path, path_len: int) -> Path:
    """在资料库里造一个「包内相对路径恰好 path_len 字符」的文件。"""
    fixed = len("sources/materials/k230/") + len(".md")
    pad = "x" * (path_len - fixed)
    return _write(tree / "sources" / "materials" / "k230" / f"{pad}.md", "# 长路径\n")


def test_overlong_entry_is_rejected_by_packer(tmp_path: Path) -> None:
    """超上限的包内路径必须**拒绝发版**，并且错误信息要点名长度与修法。"""
    tree = make_mini_repo(tmp_path)
    bad = _long_material_file(tree, MAX_ENTRY_PATH_CHARS + 1)
    rel = bad.relative_to(tree).as_posix()
    assert len(rel) == MAX_ENTRY_PATH_CHARS + 1

    files = scan_tree(tree)
    assert [f.path for f in overlong_entries(files)] == [rel]

    with pytest.raises(ValueError) as excinfo:
        prepare_full_package(tree, version="v9.9.9", out_dir=tmp_path / "pack")
    message = str(excinfo.value)
    assert str(MAX_ENTRY_PATH_CHARS) in message
    assert rel in message
    assert "slim_materials_paths.py" in message


def test_path_at_ceiling_still_packs(tmp_path: Path) -> None:
    """恰好等于上限的路径必须放行（判据是「超过」才拒，不是「达到」就拒）。"""
    tree = make_mini_repo(tmp_path)
    edge = _long_material_file(tree, MAX_ENTRY_PATH_CHARS)
    rel = edge.relative_to(tree).as_posix()
    assert len(rel) == MAX_ENTRY_PATH_CHARS
    assert overlong_entries(scan_tree(tree)) == []

    manifest, written = prepare_full_package(tree, version="v9.9.9", out_dir=tmp_path / "pack")
    assert written, "边界路径不该阻断打包"
    with zipfile.ZipFile(written[0]) as archive:
        assert rel in archive.namelist()


def test_real_tree_paths_fit_windows_extractor_budget() -> None:
    """真仓库全量扫描：包内每条路径都不超上限（发版前的最后一道闸）。"""
    repo = Path(__file__).resolve().parent.parent
    files = scan_tree(repo)
    bad = overlong_entries(files)
    assert not bad, (
        "包内路径超上限（资源管理器解压会静默丢文件）：\n"
        + "\n".join(f"  {len(f.path):4d}  {f.path}" for f in bad[:10])
        + "\n修法见 .scratch/path-budget/slim_materials_paths.py"
    )
    longest = max(files, key=lambda f: len(f.path))
    # 余量守卫：最长路径必须比上限**明显**短，否则下一次资料增补就会顶破。
    assert len(longest.path) < MAX_ENTRY_PATH_CHARS, longest.path


def test_materials_paths_stay_under_ceiling() -> None:
    """资料库单独把一遍：新批次入库时最先撞上限的就是这里。"""
    repo = Path(__file__).resolve().parent.parent
    materials = repo / "sources" / "materials"
    if not materials.is_dir():
        pytest.skip("本地无资料库目录（git clone 用户）")
    longest_rel, longest_len, over = "", 0, []
    for path in materials.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        if len(rel) > longest_len:
            longest_rel, longest_len = rel, len(rel)
        if len(rel) > MAX_ENTRY_PATH_CHARS:
            over.append((len(rel), rel))
    assert not over, f"资料库路径超上限 {len(over)} 个：{sorted(over, reverse=True)[:5]}"
    assert longest_len <= MAX_ENTRY_PATH_CHARS, longest_rel


# ---------------------------------------------------------------------------
# 清单与分卷
# ---------------------------------------------------------------------------


def test_unregistered_cjk_dir_gets_deterministic_slug(tmp_path: Path) -> None:
    """未登记的中文资料目录不该阻断完整包：自动补登记为确定性派生 slug。"""
    tree = make_mini_repo(tmp_path)
    new_dir = tree / "sources" / "materials" / "2027_新赛题资料"
    _write(new_dir / "题面.md", "# 新赛题\n")

    manifest = build_full_manifest(
        version="v9.9.9", published_at="", files=scan_tree(tree), tree=tree
    )
    slugs = {b["slug"]: b["name"] for b in manifest[MATERIALS_MANIFEST_KEY]["batches"]}
    assert slugs[derive_slug("2027_新赛题资料")] == "2027_新赛题资料"

    # 幂等：同一目录名再扫一次得同一个 slug（跨版本基线稳定）
    again = build_full_manifest(
        version="v9.9.10", published_at="", files=scan_tree(tree), tree=tree
    )
    slugs_again = {b["slug"] for b in again[MATERIALS_MANIFEST_KEY]["batches"]}
    assert derive_slug("2027_新赛题资料") in slugs_again


def test_register_materials_dirs_keeps_registry_slug(tmp_path: Path) -> None:
    """已登记目录的 slug 绝不被派生值覆盖（发出去的 slug 是用户基线的一部分）。"""
    from contest_generator.materials_pack import slug_for_dir

    tree = make_mini_repo(tmp_path)
    register_materials_dirs(tree / "sources" / "materials")
    assert slug_for_dir("2026_08_MSPM0G3507与常用芯片手册") == "2026-08-mspm0-manuals"
    assert slug_for_dir("K230-Cam-Example") == "k230-cam-example"


def test_build_full_manifest_shape_and_materials_baseline(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    files = scan_tree(tree)
    manifest = build_full_manifest(
        version="v9.9.9", published_at="2026-09-13T00:00:00Z", files=files, tree=tree
    )
    assert manifest["version"] == "v9.9.9"
    assert manifest["published_at"] == "2026-09-13T00:00:00Z"
    assert manifest["total_bytes"] == sum(f.size for f in files)
    assert manifest["parts"] == []

    listed = {f["path"]: f for f in manifest["files"]}
    assert set(listed) == {f.path for f in files}
    assert listed["src/contest_generator/__init__.py"]["sha256"] == _sha256(
        tree / "src" / "contest_generator" / "__init__.py"
    )
    assert listed["src/contest_generator/__init__.py"]["size"] == (
        tree / "src" / "contest_generator" / "__init__.py"
    ).stat().st_size

    materials = manifest[MATERIALS_MANIFEST_KEY]
    assert materials["version"] == "v9.9.9"
    slugs = {b["slug"] for b in materials["batches"]}
    # 已登记目录用登记表的 slug；全 ASCII 目录走规范化 slug；
    # 只装安装包的目录被排除后不应出现在基线里（空批次）
    assert slugs == {"2026-08-mspm0-manuals", "k230-cam-example"}
    assert derive_slug("未登记目录") == derive_slug("未登记目录")
    assert derive_slug("未登记目录") != derive_slug("另一个目录")
    assert derive_slug("未登记目录").startswith("dir-")
    materials_paths = {
        f["path"] for b in materials["batches"] for f in b["files"]
    }
    assert materials_paths == {
        "2026_08_MSPM0G3507与常用芯片手册/手册.md",
        "K230-Cam-Example/例程/main.py",
    }
    for batch in materials["batches"]:
        assert batch["removed"] == []
        assert batch["parts"] == []


def test_materials_baseline_matches_materials_scan(tmp_path: Path) -> None:
    """完整包内的资料库基线必须与「同口径扫描」一致（落位后可直接转增量）。

    口径 = 资料库扫描 + 完整包排除规则：清单里出现的文件必须真的在包里。
    """
    from contest_generator.materials_pack import scan_as_manifest

    tree = make_mini_repo(tmp_path)
    manifest = build_full_manifest(
        version="v9.9.9", published_at="", files=scan_tree(tree), tree=tree
    )
    expected = scan_as_manifest(
        tree / "sources" / "materials", "v9.9.9", exclude=materials_excluded
    )
    assert manifest[MATERIALS_MANIFEST_KEY]["batches"] == expected["batches"]


def test_materials_baseline_never_lists_files_missing_from_package(tmp_path: Path) -> None:
    """基线清单里的每个资料库文件都必须在包内文件清单里（防虚报文件）。"""
    tree = make_mini_repo(tmp_path)
    files = scan_tree(tree)
    manifest = build_full_manifest(
        version="v9.9.9", published_at="", files=files, tree=tree
    )
    in_package = {f.path for f in files}
    listed = {
        f"sources/materials/{item['path']}"
        for batch in manifest[MATERIALS_MANIFEST_KEY]["batches"]
        for item in batch["files"]
    }
    assert listed, "基线不该为空"
    assert listed <= in_package, f"基线虚报：{sorted(listed - in_package)[:5]}"


def test_split_volumes_by_limit(tmp_path: Path) -> None:
    from contest_generator.materials_pack import PartFile

    files = [
        PartFile(path="a.bin", size=10, sha256="0" * 64),
        PartFile(path="b.bin", size=10, sha256="0" * 64),
        PartFile(path="c.bin", size=10, sha256="0" * 64),
    ]
    parts = split_volumes(files, limit=20)
    assert [[f.path for f in part] for part in parts] == [["a.bin", "b.bin"], ["c.bin"]]


def test_split_volumes_oversized_single_file_gets_own_part() -> None:
    from contest_generator.materials_pack import PartFile

    files = [
        PartFile(path="small.bin", size=5, sha256="0" * 64),
        PartFile(path="huge.bin", size=100, sha256="0" * 64),
        PartFile(path="tail.bin", size=5, sha256="0" * 64),
    ]
    parts = split_volumes(files, limit=20)
    assert [[f.path for f in part] for part in parts] == [["small.bin"], ["huge.bin"], ["tail.bin"]]


def test_build_zip_volumes_naming_and_checksums(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    files = scan_tree(tree)
    out = tmp_path / "pack"
    meta, written = build_zip_volumes(
        tree, "v9.9.9", files, out, limit=1024 * 1024
    )
    assert len(meta) == 1
    assert meta[0]["zip_name"] == "firstep-full-v9.9.9.zip"
    assert written[0].name == "firstep-full-v9.9.9.zip"
    assert meta[0]["size"] == written[0].stat().st_size
    assert meta[0]["sha256"] == _sha256(written[0])
    with zipfile.ZipFile(written[0]) as archive:
        names = sorted(n for n in archive.namelist() if not n.endswith("/"))
    assert names == sorted(f.path for f in files)
    assert not any(name.endswith(".exe") or name.endswith(".zip") for name in names)


def test_build_zip_volumes_multi_part_naming(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    files = scan_tree(tree)
    out = tmp_path / "pack"
    meta, written = build_zip_volumes(tree, "v9.9.9", files, out, limit=1)
    assert len(meta) > 1
    assert meta[0]["zip_name"] == "firstep-full-v9.9.9.part1.zip"
    assert meta[1]["zip_name"] == "firstep-full-v9.9.9.part2.zip"
    assert len(written) == len(meta)
    for item in meta:
        assert item["sha256"] == _sha256(out / item["zip_name"])


def test_build_zip_volumes_keeps_cjk_names(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    out = tmp_path / "pack"
    _, written = build_zip_volumes(tree, "v9.9.9", scan_tree(tree), out, limit=1024 * 1024)
    with zipfile.ZipFile(written[0]) as archive:
        names = archive.namelist()
    assert any("题面.md" in n for n in names)
    assert any("手册.md" in n for n in names)


# ---------------------------------------------------------------------------
# 编排：四件套
# ---------------------------------------------------------------------------


def test_prepare_full_package_writes_quartet(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    out = tmp_path / "pack"
    manifest, written = prepare_full_package(
        tree, version="v9.9.9", out_dir=out, published_at="2026-09-13T00:00:00Z"
    )
    manifest_file = out / full_manifest_filename("v9.9.9")
    assert manifest_file.is_file()
    assert written == [out / "firstep-full-v9.9.9.zip"]
    on_disk = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert on_disk == manifest
    assert on_disk["parts"][0]["sha256"] == _sha256(written[0])
    # total_bytes = 包内文件原始大小合计（下载前估算用），不是 zip 压缩后大小
    from contest_generator.full_pack import scan_tree

    expected_bytes = sum(f.size for f in scan_tree(tree))
    assert on_disk["total_bytes"] == expected_bytes


def test_prepare_full_package_removed_list_from_baseline(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    baseline = {
        "version": "v9.9.8",
        "files": [
            {"path": "src/contest_generator/__init__.py", "size": 1, "sha256": "0" * 64},
            {"path": "docs/old-page.md", "size": 1, "sha256": "0" * 64},
            {"path": "sources/materials/gone/old.md", "size": 1, "sha256": "0" * 64},
        ],
    }
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "pack"
    manifest, _ = prepare_full_package(
        tree,
        version="v9.9.9",
        out_dir=out,
        published_at="",
        baseline_path=baseline_path,
    )
    expected = ["docs/old-page.md", "sources/materials/gone/old.md"]
    removed = (out / "firstep-full-v9.9.9.removed.txt").read_text(encoding="utf-8").split()
    assert removed == expected
    # 删除清单必须同时进清单 JSON：更新器只读清单（按 URL 拉），不下载
    # .removed.txt —— 漏写会让「废弃文件清理」静默不执行（真实缺陷回归）。
    assert manifest["removed"] == expected
    on_disk = json.loads(
        (out / full_manifest_filename("v9.9.9")).read_text(encoding="utf-8")
    )
    assert on_disk["removed"] == expected


def test_prepare_full_package_without_baseline_writes_empty_removed(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    out = tmp_path / "pack"
    prepare_full_package(tree, version="v9.9.9", out_dir=out, published_at="")
    removed_file = out / "firstep-full-v9.9.9.removed.txt"
    assert removed_file.is_file()
    assert removed_file.read_text(encoding="utf-8").strip() == ""


def test_prepare_full_package_sha256_sidecar(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    out = tmp_path / "pack"
    _, written = prepare_full_package(tree, version="v9.9.9", out_dir=out, published_at="")
    sidecar = (out / "firstep-full-v9.9.9.sha256.txt").read_text(encoding="utf-8")
    assert written[0].name in sidecar
    assert _sha256(written[0]) in sidecar
    assert len(sidecar.strip().splitlines()) == len(written)


def test_prepare_full_package_rejects_bad_version(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path)
    out = tmp_path / "pack"
    import pytest

    with pytest.raises(ValueError):
        prepare_full_package(tree, version="../evil", out_dir=out, published_at="")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_writes_quartet(tmp_path: Path, capsys) -> None:
    tree = make_mini_repo(tmp_path)
    out = tmp_path / "pack"
    code = main(
        [
            "--tree",
            str(tree),
            "--version",
            "v9.9.9",
            "--out",
            str(out),
            "--published-at",
            "2026-09-13T00:00:00Z",
        ]
    )
    assert code == 0
    assert (out / "firstep-full-v9.9.9.zip").is_file()
    assert (out / "firstep-full-v9.9.9.manifest.json").is_file()
    assert (out / full_manifest_filename("v9.9.9")).is_file()
    printed = capsys.readouterr().out
    assert "完整包" in printed
    assert "firstep-full-v9.9.9.zip" in printed


def test_cli_rejects_missing_tree(tmp_path: Path) -> None:
    code = main(["--tree", str(tmp_path / "nope"), "--version", "v9.9.9", "--out", str(tmp_path)])
    assert code == 2
