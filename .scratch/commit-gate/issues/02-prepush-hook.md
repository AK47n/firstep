# A2 — `.githooks/pre-push` 接上选择器

**要做什么：** 真推一次代码时，如果改动破坏了既有守卫，push 被拦下并**点名失败的用例**；推 tag（发版）自动跑全套；钩子自己坏了不许卡住维护者。

**被谁阻塞：** A1。

**状态：** pending

- [ ] `.githooks/pre-push` 存在且可执行，调用 `tools/prepush.py` 并透传 stdin 的 refs
- [ ] 测试红 → 非 0 退出（push 被拒）+ 打印失败的用例名与「怎么绕过/怎么复跑」
- [ ] 推 tag（`refs/tags/*`）→ 自动全套，不看子集
- [ ] `FIRSTEP_PREPUSH=full` → 全套；`FIRSTEP_PREPUSH=off` → 跳过（明写警告：仅限确知自己在做什么时）
- [ ] 钩子自身故障（python 缺失 / 选择器抛错 / git 读不到）→ **打印原因并放行**（exit 0），绝不因闸门坏了卡人
- [ ] 真机验证一次：构造一个破坏守卫的改动 → push 被拒并点名；还原 → push 通过
