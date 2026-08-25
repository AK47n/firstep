# 01 步骤 7 完成判定修正：默认布线 / 无需配置也显示完成

> 归属 spec：`.scratch/step7-done/spec.md`

Status: resolved

## 背景

步骤 7 从未显示完成（用户报告）。根因：`syncStep7()` 判定过窄且只在 bind/unbind 时被调用。

## 任务

- 新增纯函数 `step7DoneState(state)`：里程碑判定（见 spec 方案四态 + 两前提）。
- `syncStep7()` 改为薄壳：组装 state（chosenPlatform / expanded.length / pinRoles() / 当前角色键绑定 / instances 带 pin / stepDoneSet.has(9)）。
- `renderPinCard()` 三个出口各补 `syncStep7()`（未选平台 / 板定义未就绪 / 正常末尾）。
- 生成成功处理器 `markStepDone(9)` 后补 `syncStep7()`。

## 验收标准

- [x] `tests/js/step7-done.test.mjs` 8 用例全绿（先红后绿）
- [x] `node --test "tests/js/*.test.mjs"` 全绿
- [x] headless 实测：默认布线生成后导航/总览 7 变 ✓；无角色即 ✓；未选平台不勾；已绑定 ✓
- [x] 主 script 块 `new Function` 语法检查通过
- [x] pytest 语言/编码套件通过
