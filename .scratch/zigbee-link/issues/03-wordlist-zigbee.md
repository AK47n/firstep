# 03 — 词表「无线通信模块」补 Zigbee 方案 + lib_modules

**要做什么：** 买件指引（库外建议选型参考）的「无线通信模块」组出现「Zigbee 模块（DL-20 串口透传）」方案，带「库内已有：zigbee_link」徽标（不重复标 recommended，该组已有 2 个）；词表加载机械校验（lib_modules 引用 slug 存在）通过；方案形状/徽标规则单测绿。用户看到 Zigbee 买件方案时知道库内已有驱动，无需重复采购。

**被谁阻塞：** 01（slug 存在性是词表加载校验前提）

**状态：** resolved

**评审整改（2026-09-05）：** 双轴评审通过；补强——① 新测试改精确 name 匹配 + 字段级断言（interface/price/note 含 zigbee_link 与 115200/suitable/lib_modules/recommended）；② test_wordlist docstring 修正（解析用例自足 + 末尾真实词表回归）。

- [x] `src/contest_generator/wordlist.json` 无线通信模块组新增 `Zigbee 模块（DL-20 串口透传）` 方案（interface/price/note/suitable，recommended=false，lib_modules=["zigbee_link"]）
- [x] 词表加载校验通过（slug 存在于源码树模块库）
- [x] `tests/test_wordlist.py` 新增用例：新方案形状、lib_modules 引用、组内 recommended 数 ≤2
- [x] 词表相关测试全绿
