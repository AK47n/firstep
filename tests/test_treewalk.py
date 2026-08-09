"""项目树遍历原语（工单 E 深化）：统一噪音跳过规则的专属测试。

六处遍历（master ×3 / keil / ccs / generator ×2）此前各自实现、三种互相
矛盾的跳过规则——本文件直接测原语本身，消费方的等价性由各自测试覆盖。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.treewalk import (
    iter_project_files,
    skip_project_noise,
)


def _write(project: Path, rel: str, content: str = "x") -> None:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_skip_project_noise_rules():
    # 顶层：.git + 构建产物目录
    assert skip_project_noise(".git/config")
    assert skip_project_noise("Debug/main.o")
    assert skip_project_noise("Release/x.hex")
    assert skip_project_noise("Listings/p.lst")
    assert skip_project_noise("Objects/p.crf")
    # 任意层级组件：Listings / Objects（USER/ 工程时产物在 USER/ 下）
    assert skip_project_noise("USER/Listings/p.lst")
    assert skip_project_noise("USER/Objects/p.dep")
    assert skip_project_noise("deep/nested/Objects/x.o")
    # 普通路径不误伤
    assert not skip_project_noise("src/main.c")
    assert not skip_project_noise("USER/project.uvprojx")
    assert not skip_project_noise("deep/nested/ObjectsDir/x.c")  # 不是完整组件


def test_iter_project_files_skips_noise_and_sorts(tmp_path):
    project = tmp_path / "proj"
    _write(project, "src/main.c")
    _write(project, "USER/project.uvprojx")
    _write(project, "Listings/proj.uvprojx")  # 判例：keil 旧实现找得到，master 忽略
    _write(project, "Objects/proj.o")
    _write(project, ".git/objects/x")

    files = iter_project_files(project)
    # WindowsPath 排序大小写不敏感：src 在 user 之前
    assert [p.relative_to(project).as_posix() for p in files] == [
        "src/main.c",
        "USER/project.uvprojx",
    ]


def test_iter_project_files_pattern_and_dirs_only():
    project = Path("proj")
    (project / "sub").mkdir(parents=True)
    (project / "a.c").write_text("", encoding="utf-8")
    (project / "a.h").write_text("", encoding="utf-8")
    try:
        headers = iter_project_files(project, pattern="*.h")
        assert [p.relative_to(project).as_posix() for p in headers] == ["a.h"]
    finally:
        import shutil

        shutil.rmtree(project)
