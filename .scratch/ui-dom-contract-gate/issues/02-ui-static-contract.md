# 02 — ui 层第一层缝：id 存在性 + 装载可达性（纯静态，进前端门禁）

**要做什么：** 给 `ui/` 层立起第一条**可测的 interface**：任何一个 `ui/*.js` 里写死的 id，都必须在
「页面真正会出现的声明集合」里找得到；任何一个 `ui/*.js` 模块，都必须真的被页面装载。
端到端行为：把 `$("output-dir")` 写成 `$("outpt-dir")`、或新加一个 `ui/` 模块而忘了在
`index.html` 里 import/调用，`node --test "tests/js/*.test.mjs"` 当场变红并点名文件与 id。

**被谁阻塞：** 无——可立即开始（与 01 互不阻塞）。

**状态：** claimed

- [ ] 判据落点 `tests/js/ui-dom-contract.mjs`（判据单源，可复用），断言落点
      `tests/js/ui-dom-contract.test.mjs`（照 `tests/js/import-usage.mjs` ↔
      `import-usage-guard.test.mjs` 的先例：判据与断言分文件）。
- [ ] **id 存在性**：从 `ui/*.js` 抠**静态 id 字面量**——`$("x")` / `getElementById("x")` /
      `querySelector("#x…")`；声明集合 = `index.html` 的静态 `id="…"` ∪ 全前端 JS 里内联的
      `id="…"` / `.id = "…"` / `id: "…"`（模板串拼出来的 id 与 `#rrggbb` 颜色字面量不进判据）。
      一条 id 两边都没有 = 红，报错点名 **id + 引用它的文件**。
      实测基线（本轮探针）：html 静态 541 + JS 内联 38 = 579 个声明；ui 静态引用 510 个；**缺 0**。
      所以这条守卫**落地即绿**——它防的是明天。
- [ ] **装载可达性**：逐个 `ui/*.js` 判——
      ① 有 `export function init*` 的模块：必须在 `index.html` 的 import 清单里被**具名导入**、
      且在该文件模块体里出现 `init…()` 调用；
      ② 没有 `init*` 导出的模块：必须以 `import "/js/ui/<file>"`（只为加载）出现。
      两条都不满足 = 红并点名模块（"写了却从没生效"）。
- [ ] **反向验证（红证，两条判据各一次）**：
      ① 把 `index.html` 一个被引用的 id 改名 → id 判据必须红且点名那个 id 与文件；
      ② 把某个 `ui/` 模块的 `$("x")` 改成一个不存在的 id → 同样红；
      ③ 从 `index.html` 的 import 清单里摘掉一个 `init*` 模块 → 装载判据必须红且点名模块。
      三次注入都**逐字节复原**，红/绿两次输出留 `## Comments`。
- [ ] 不引入任何新依赖（只吃 `node:` 内置模块），命令仍是
      `node --test "tests/js/*.test.mjs"`。
- [ ] 判据**不绑写法**：改名变量、两步取元素、`?.` 可选链都算通过——判的是事实（id 在不在、
      模块装没装），不是源码形状。
- [ ] `node --test "tests/js/*.test.mjs"` 全绿 + `python -m pytest` 全绿；提交信息中文。

## Comments
