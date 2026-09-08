# 01 — 模块源码 .c/.h 头部注入来源注释 + 判据单源

**要做什么：** 全库 56 个 wiki 派生模块的 .c/.h 文件顶部带标准来源注释块（原页 URL + 页面标题 + 改写说明），
任何人拿到 `library/modules/<slug>/code/` 下的模块源码即知来源与链接；且该行为被结构测试永久兜底。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `manifest.py` 新增 `is_wiki_source_url(url)` 判据（`startswith("https://wiki.lckfb.com/")`，单源）
- [x] 注入脚本 `.scratch/lckfb-attribution/inject_source_notes.py`：遍历 manifest，对 wiki 平台条目的
      files 逐文件注入标准注释块（.h 在 `#ifndef` 前、.c 在首个 `#include` 前）；幂等；
      页面标题从 `sources/materials/lckfb-地猛星移植手册/<cat>--<slug>.md` 首行取，缺失降级
- [x] 对 56 个 wiki 模块全量注入（115 文件），幂等验证重跑 0 变更
- [x] 新增 `tests/test_lckfb_attribution.py`：真实库遍历断言（wiki 模块每 .c/.h 顶部 600 字符含 source_url；
      注入函数纯函数化可测幂等）；非 wiki 模块不要求；含「注释块闭合」防回潮断言
      （曾漏闭合 `*/` 吞 include 行，self include 门禁抓出——测试钉死）
- [x] 全量 pytest 通过（448 个模块测试零破坏）
