# 04 — 声明补全 + 测试防回潮

**要做什么：** 仓库 README 第三方素材段补塔克版权归属与下架说明；真库不变量测试
翻转——参考库不得出现塔克条目（防回潮：以后再录入即红）。

**被谁阻塞：** 01（真库删除后才能让「不得存在」断言为真）。

**状态：** resolved

- [ ] README.md 第三方素材段：加「塔克创新（烟台塔克电子科技）」条目——
      版权归属、官网 www.xtark.cn、本工具已下架全部塔克文件（参考库已删 /
      资料包已下架）、学习资料请自行官网获取
- [ ] `tests/test_reference_library.py` 真库塔克不变量段：从「6 条目必须存在」
      翻转为「库内不得存在 塔克R3*/xtark 条目」（防回潮）
- [ ] 全量回归 + JS 测试通过

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：
  ① README 声明——`README.md:104-116`「## 塔克创新（TARKBOT）资料——已下架说明」：
  版权归属（烟台塔克电子科技有限公司）+ 官网 <https://www.xtark.cn> + 本工具不再收录
  分发 + 已安装用户删除提示 + 指向 `docs/third-party-summaries/塔克R3底盘控制知识总结.md`；
  ② 测试翻转——`tests/test_reference_library.py:2211-2245`「真库数据不变量：塔克
  塔克R3 条目必须不存在（工单 tark-removal/04）」段：`TARKBOT_MARKERS = ("塔克",
  "TARKBOT", "xtark", "DB20", "塔克创新")`（:2221）、
  `test_tarkbot_entries_absent_from_reference_library`（:2226，list_references 全库
  零命中否则断言红）、`test_tarkbot_entries_absent_from_web_facing_search`（:2242，
  按塔克词搜索零命中）；原「6 条必须存在」不变量已删（注释 :2219 记录）。
  ③ 回归：基线 `python -m pytest -q` = **3892 passed**（含上述两个不变量测试）；
  前端 `node --test` 相关文件全绿。
  验收逐条对照：① README 段 ✓ ② 真库不变量翻转（含防回潮 + 搜索面）✓
  ③ 全量回归通过 ✓。
