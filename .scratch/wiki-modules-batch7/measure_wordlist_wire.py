# -*- coding: utf-8 -*-
"""批次 7 词表预算实测：默认词表完整 wire 尺寸 + 与 WORDLIST_PROMPT_BYTES 余量。

结论写入 llm.py 注释（照批次 5/6 先例）。"""
import sys

sys.path.insert(0, "src")

from contest_generator.budget import wire_size
from contest_generator.llm import (
    WORDLIST_PROMPT_BYTES,
    WORDLIST_TRUNCATION_NOTICE,
    _wordlist_prompt_segment,
)
from contest_generator.wordlist import WORDLIST_PATH, format_wordlist_prompt, load_wordlist

groups = load_wordlist(WORDLIST_PATH)
segment = format_wordlist_prompt(groups)
fitted = _wordlist_prompt_segment(groups)
print("词表分组数:", len(groups))
print("完整 wire:", wire_size(segment))
print("截断 wire:", wire_size(fitted))
print("fit 上限（预算-标注）:", WORDLIST_PROMPT_BYTES - wire_size(WORDLIST_TRUNCATION_NOTICE))
print("余量:", WORDLIST_PROMPT_BYTES - wire_size(WORDLIST_TRUNCATION_NOTICE) - wire_size(segment))
print("截断发生:", fitted != segment)
