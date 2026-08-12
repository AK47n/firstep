"""工单 03 生成接线的测试假件：赛题库 / 参考文件库 / 该题专用模块。

fakes.py 属既有测试只读件（工单 01/02 约定，只读不碰），新增假件独立成
文件。素材区用真实入库函数构造（confirm_topics / add_reference）——接线
测试断言的是真实磁盘形状下的编号解析与关联发现。
"""

from __future__ import annotations

import json
from pathlib import Path

from contest_generator.topic_library import TopicDraft
from contest_generator.reference_library import add_reference
from contest_generator.topic_library import confirm_topics
from tests.fakes import make_sample_pdf

TOPIC_PROBLEM_TEXT = "2026C 数字钥匙题面全文（长 PDF 拆条入库）"

KIT_KEY = "2026C 钥匙套件"  # 锁控制模块的套件（参考文件 kit 锚定的合法取值）
UWB_KIT = "地猛星 UWB 套件"  # 普通候选模块的套件（非该题专用）

# 参考文件条目 id 由标题生成（add_reference 的 _next_entry_id 逻辑）
TOPIC_REFERENCE_ID = "2026C-数字钥匙参考例程"  # 锚定赛题 2026C
KIT_REFERENCE_ID = "钥匙套件说明书"  # 锚定套件 KIT_KEY
UWB_REFERENCE_ID = "UWB-套件例程"  # 锚定普通候选模块的套件 UWB_KIT
OTHER_REFERENCE_ID = "无关套件资料"  # 锚定无关套件（任何模块都没有该 kit，不该被关联）


def make_fake_topic_library(
    topic_root: Path, *, problem_text: str = TOPIC_PROBLEM_TEXT
) -> Path:
    """赛题库：2026C 一条目（真实 confirm_topics 入库，题面全文可注入）。"""
    pdf_path = topic_root.parent / "2026C.pdf"
    make_sample_pdf(pdf_path, "2026C contest problems")
    confirm_topics(
        topic_root,
        pdf_path,
        (TopicDraft(year="2026", number="C", problem_text=problem_text),),
    )
    return topic_root


def make_fake_reference_library(reference_root: Path) -> Path:
    """参考文件库：锚定 2026C / 该题套件 / 普通候选套件 各一条 + 无关套件一条。"""
    add_reference(
        reference_root,
        title="2026C 数字钥匙参考例程",
        type="例程工程",
        description="2026C 钥匙题配套例程",
        anchor_kind="topic",
        anchor_value="2026C",
        files={"key_example.c": "/* 数字钥匙例程 */\nvoid key_check(void);\n"},
        kit_vocabulary=(KIT_KEY, UWB_KIT, "无关套件"),
    )
    add_reference(
        reference_root,
        title="钥匙套件说明书",
        type="说明书",
        description="钥匙套件使用说明",
        anchor_kind="kit",
        anchor_value=KIT_KEY,
        files={"manual.txt": "套件接线与使用说明全文\n"},
        kit_vocabulary=(KIT_KEY, UWB_KIT, "无关套件"),
    )
    add_reference(
        reference_root,
        title="UWB 套件例程",
        type="例程工程",
        description="UWB 测距套件配套例程",
        anchor_kind="kit",
        anchor_value=UWB_KIT,
        files={"uwb_example.c": "/* UWB 例程 */\nvoid uwb_start(void);\n"},
        kit_vocabulary=(KIT_KEY, UWB_KIT, "无关套件"),
    )
    add_reference(
        reference_root,
        title="无关套件资料",
        type="例程工程",
        description="别的套件的例程",
        anchor_kind="kit",
        anchor_value="无关套件",
        files={"other.c": "/* 别的套件 */\n"},
        kit_vocabulary=(KIT_KEY, UWB_KIT, "无关套件"),
    )
    return reference_root


def make_topic_specific_module(module_library_dir: Path) -> Path:
    """假模块：stm32-only 候选（平台过滤判据）+ 带 kit。"""
    return _add_module(
        module_library_dir,
        "lock_control",
        "钥匙校验与锁控制驱动",
        KIT_KEY,
    )


def make_kit_candidate_module(module_library_dir: Path) -> Path:
    """普通候选模块（无题绑定），stm32 版本带 UWB 套件 kit。

    候选清单的套件关联靠它：套件锚定的参考文件仍能经候选模块的 kit 进清单
    （评审 c2 修复的回归锚点）。
    """
    return _add_module(
        module_library_dir,
        "uwb",
        "UWB 测距模块驱动",
        UWB_KIT,
    )


def _add_module(module_library_dir: Path, slug: str, description: str, kit: str) -> Path:
    module_dir = module_library_dir / slug
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "description": description,
                "dependencies": [],
                "platforms": {
                    "stm32": {
                        "files": [f"{slug}.c", f"{slug}.h"],
                        "verified": True,
                        "hardware_bound": False,
                        "kit": kit,
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (module_dir / f"{slug}.c").write_text(
        f"#include \"{slug}.h\"\n/* {slug} */\nvoid {slug}_init(void);\n",
        encoding="utf-8",
    )
    (module_dir / f"{slug}.h").write_text(
        f"#pragma once\nvoid {slug}_init(void);\n", encoding="utf-8"
    )
    return module_dir
