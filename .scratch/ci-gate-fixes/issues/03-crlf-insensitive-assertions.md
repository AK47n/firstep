# 03 — 两处 CRLF 敏感断言改为换行无关

**要做什么：** CRLF 检出（CI windows 腿的真实形态）下前端门禁全绿；本工作树 LF 检出同样全绿。
现在有两条断言拿 `\n` 当锚点，遇到 CRLF 就不匹配。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] `tests/js/ai-action-refs.test.mjs` 那条（生成骨架 / 生成工程收尾路径含 `aiActionStop`）改成换行无关
- [ ] `tests/js/module-intro-detail.test.mjs` 那条（点掉 chip 后的时序）改成换行无关
- [ ] 改法照本仓**既有口径**：`tests/js/tab-register-guard.test.mjs:276` 的原话——
      锚点用**不含缩进与换行**的子串（带 `\n` 的锚点会静默不落上，第一版就是这么假红的）
- [ ] **反向验证**（先红后绿）：干净 clone（`core.autocrlf=true`）改前 **1794 passed / 2 fail**，
      改后 **1796 passed / 0 fail**
- [ ] LF 检出（本工作树）同样 **1796 passed / 0 fail**——两个方向都要跑
- [ ] 断言强度不缩水：两条用例判的仍是「这两处调用是成对的 start/stop」这件事本身，
      不是退化成「文件里有某个词」
- [ ] 中文提交
