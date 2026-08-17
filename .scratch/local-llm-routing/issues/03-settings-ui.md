# 03 — 设置页 UI：本地模型端点可填写 / 清空

**What to build:** 设置页可填写 / 清空本地模型端点（base_url + 模型名），保存后
立即生效；清空 = 恢复纯 DeepSeek。手改 config.json 不再是必需路径——配置入口
收进既有设置页。

**Blocked by:** 01（依赖字段定义与持久化）

**Status:** ready-for-agent

## 验收

- [ ] `/api/settings` GET 返回 `local_llm_base_url` / `local_llm_model`
      （未配置为空串，前端显示为空输入框）。
- [ ] `/api/settings` PUT 接受两字段（缺省 / 空串 = 关闭本地路由）；非字符串
      → 400 中文报错（与既有字段同严格度）。
- [ ] 前端设置表单加两个输入框（本地 base_url / 本地模型），加载时回填、
      保存时提交；保存提示「已保存，立即生效。」（与既有风格一致）。
- [ ] 清空两字段保存 = 关闭本地路由（等价于从 config.json 移除）。
- [ ] test_webapp.py 增 GET / PUT 覆盖（含空串清空、非字符串 400）；
      前端改动手动验证。全量 pytest 绿。

## 文件边界

- webapp 的 /api/settings GET / PUT。
- 前端 index.html（设置表单 + loadSettings / saveSettings 接线）。
- 测试：test_webapp.py；前端 settings JS 属既有 inline 现状（node:test 未覆盖
  该段，本工单不新增前端测试缝）。
- 不动路由层（02 已定）、不动 config 字段语义（01 已定）。
