"""模块库真机迁移（工单 05）：存量 6 模块简介按三要素重写 + 身份字段补填。

用法：python module_migrate.py <命令> <slug> [...]
  draft    <slug>                        AI 通读代码出简介草稿（真实 DeepSeek）
  validate <slug> <desc-file>            真实 AI 一致性校验（只校验，不落盘）
  save     <slug> <desc-file>            一致性校验通过后写回简介（失败不落盘）
  identity <slug> <platform> <kit> <source_url>   身份字段补填（kit / source_url，
                                         由人填写，走 update_platform_identity）

与真机录入先例 module_import.py 同一模式：走真实 DeepSeek + 真实库目录。
"""
import json
import sys
from pathlib import Path

from contest_generator.config import load_config
from contest_generator.llm import DeepSeekLLM
from contest_generator.library import (
    draft_description,
    update_module_description,
    update_platform_identity,
    validate_description,
)


def module_files(slug: str) -> dict[str, str]:
    """读模块全部平台版本引用的源文件（与 update_module_description 同视角）。"""
    from contest_generator.library import get_module

    root = Path(load_config().module_library_dir)
    manifest = get_module(root, slug)
    module_dir = root / slug
    files: dict[str, str] = {}
    for entry in manifest.platforms.values():
        for name in entry.files:
            if name in files:
                continue
            files[name] = (module_dir / name).read_text(encoding="utf-8")
    return files


def cmd_draft(slug: str) -> None:
    llm = DeepSeekLLM(load_config())
    draft = draft_description(llm, module_files(slug))
    print(draft)


def cmd_validate(slug: str, desc_file: str) -> None:
    llm = DeepSeekLLM(load_config())
    description = Path(desc_file).read_text(encoding="utf-8").strip()
    result = validate_description(llm, description, module_files(slug))
    print(f"consistent={result.consistent}")
    if not result.consistent:
        print("issues:", result.issues)


def cmd_save(slug: str, desc_file: str) -> None:
    llm = DeepSeekLLM(load_config())
    description = Path(desc_file).read_text(encoding="utf-8").strip()
    root = Path(load_config().module_library_dir)
    manifest = update_module_description(llm, root, slug, description)
    print(f"已写回 {slug}：{manifest.description}")


def cmd_identity(slug: str, platform: str, kit: str, source_url: str) -> None:
    root = Path(load_config().module_library_dir)
    manifest = update_platform_identity(
        root, slug, platform, kit=kit, source_url=source_url
    )
    entry = manifest.platforms[platform]
    print(f"已补填 {slug}/{platform}：kit={entry.kit} source_url={entry.source_url}")


def main() -> None:
    command = sys.argv[1]
    if command == "draft":
        cmd_draft(sys.argv[2])
    elif command == "validate":
        cmd_validate(sys.argv[2], sys.argv[3])
    elif command == "save":
        cmd_save(sys.argv[2], sys.argv[3])
    elif command == "identity":
        cmd_identity(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
