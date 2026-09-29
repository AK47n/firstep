r"""收口体检（工单 03）：守卫文件的规模与表条数——**按脚本复算，不按记忆写**（纪律 3）。

只读，不改任何东西。
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"


def table_size(text: str, name: str) -> int:
    block = re.search(rf"const {name} = \[(.*?)\n\];", text, re.S).group(1)
    return len(re.findall(r"^\s*\[", block, re.M))


def main() -> None:
    raw = GUARD.read_bytes()
    text = raw.decode("utf-8")
    print(f"守卫：{GUARD.relative_to(ROOT).as_posix()}（LF 检出）")
    print(f"  行数 {text.count(chr(10))}  字节 {len(raw)}  CRLF 行尾 {raw.count(b'\r\n')}（应为 0）")
    print(f"  test() 用例数：{len(re.findall(r'^test[(]', text, re.M))}")
    for name in ("PAGE_SCOPES", "FONT_ROLES", "BORDER_KINDS", "BORDER_REGISTER", "JS_BORDER_REGISTER"):
        print(f"  {name}：{table_size(text, name)} 条")
    print(f"  注释里「腿⑥」{text.count('腿⑥')} 次、「腿⑦」{text.count('腿⑦')} 次")


if __name__ == "__main__":
    main()
