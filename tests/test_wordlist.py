"""硬件词表（wordlist.py）测试：solutions 解析（工单 buy-guide/01）。

词表解析耦合到包内默认词表（DEFAULT_WORDLIST=load_wordlist() 模块级），
这里全部用临时词表文件 + 显式路径，测试自足不依赖库内容。
"""

from __future__ import annotations

import pytest

from contest_generator.wordlist import (
    HardwareWordGroup,
    SolutionOption,
    WordlistError,
    category_names,
    format_wordlist_prompt,
    load_wordlist,
    model_names,
)


def _write(tmp_path, content):
    path = tmp_path / "wordlist.json"
    path.write_text(content, encoding="utf-8")
    return path  # noqa: RET504 路径显式传 load_wordlist


def test_load_wordlist_without_solutions_ok(tmp_path):
    """旧词表（无 solutions 键）向后兼容：解析成功、solutions 空。"""
    path = _write(
        tmp_path, '[{"category": "视觉模块", "models": ["K230", "OpenMV"]}]'
    )
    groups = load_wordlist(path)
    assert len(groups) == 1
    assert groups[0].solutions == ()


def test_load_wordlist_solutions_parsed(tmp_path):
    """solutions 解析：字段映射 + recommended 默认 False + 可空字符串。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "models": ["超声波传感器"], '
        '"solutions": ['
        '{"name": "HC-SR04", "interface": "GPIO", "price": "￥3-8/个", '
        '"note": "测2cm-4m", "suitable": "避障", "recommended": true},'
        '{"name": "JSN-SR04T"}]}]',
    )
    groups = load_wordlist(path)
    solutions = groups[0].solutions
    assert len(solutions) == 2
    assert solutions[0] == SolutionOption(
        name="HC-SR04",
        interface="GPIO",
        price="￥3-8/个",
        note="测2cm-4m",
        suitable="避障",
        recommended=True,
    )
    assert solutions[1].recommended is False
    assert solutions[1].interface == ""


def test_load_wordlist_solutions_missing_name_rejected(tmp_path):
    """solutions 条目缺 name → WordlistError（确定性知识宁缺毋编）。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": [{"price": "￥3"}]}]',
    )
    with pytest.raises(WordlistError, match="缺 name"):
        load_wordlist(path)


def test_load_wordlist_solutions_not_array_rejected(tmp_path):
    """solutions 非数组 → WordlistError。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": {"name": "HC-SR04"}}]',
    )
    with pytest.raises(WordlistError, match="solutions 必须是数组"):
        load_wordlist(path)


def test_load_wordlist_solutions_recommended_not_bool_rejected(tmp_path):
    """recommended 非布尔 → WordlistError（形状硬约束）。"""
    path = _write(
        tmp_path,
        '[{"category": "感知传感器", "solutions": '
        '[{"name": "HC-SR04", "recommended": "yes"}]}]',
    )
    with pytest.raises(WordlistError, match="recommended 必须是布尔"):
        load_wordlist(path)


def test_format_wordlist_prompt_shows_solution_names(tmp_path):
    """科普段带方案名（紧凑）：名称 + 推荐标记，详情不进 prompt。"""
    groups = (
        HardwareWordGroup(
            category="感知传感器",
            models=("超声波传感器",),
            solutions=(
                SolutionOption(name="HC-SR04", recommended=True),
                SolutionOption(name="JSN-SR04T"),
            ),
        ),
    )
    prompt = format_wordlist_prompt(groups)
    assert "选购方案" in prompt
    assert "HC-SR04（推荐）" in prompt
    assert "JSN-SR04T" in prompt


def test_wordlist_static_helpers():
    """category_names / model_names 仍正确（覆盖 models 跨组收集）。"""
    groups = (
        HardwareWordGroup(category="视觉模块", models=("K230", "OpenMV")),
        HardwareWordGroup(category="声光提示器件", models=("LED",)),
    )
    assert category_names(groups) == {"视觉模块", "声光提示器件"}
    assert model_names(groups) == {"K230", "OpenMV", "LED"}
