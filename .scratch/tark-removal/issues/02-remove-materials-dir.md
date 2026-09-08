# 02 — sources/materials 塔克目录下架（分发面收口）

**要做什么：** 删除 `sources/materials/塔克R3两驱小车底盘资料/` 目录——完整包 next 版
自然不含；下一次 materials 增量包（diff 基线机制）自动产生该批次的 removed 清单，
已安装用户侧一键更新即自动删除塔克文件。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 删除目录（不在 git 内，直接文件系统删除）
- [ ] 确认下次打包 diff 机制覆盖整批删除（materials_pack L242-250 整批消失路径）——
      跑一次 diff 模式对当前基线做 dry 验证（若基线不可得则说明并跳过）
