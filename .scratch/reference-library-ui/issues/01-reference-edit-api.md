# 01 — 后端：条目编辑端点（元数据 + 文件增删一次事务）

**要做什么：** 让参考文件条目入库后可以被编辑：一次保存同时更新元数据
（标题 / 类型 / 简介 / 锚定 / 平台）与文件集合（增删），校验与录入同源、
失败磁盘零变化、成功后自动 git 提交；curl 即可端到端验证，暂不涉及 UI。

**被谁阻塞：** 无——可立即开始（纯后端竖切）。

**状态：** resolved

- [ ] `PUT /api/references/{entry_id}` 存在，body 契约 = `{title, type,
      description, anchor_kind, anchor_value, platform, add_files?, remove_files?}`，
      成功返回 `to_dict()`（含 file_count / size_bytes 实况）
- [ ] 元数据校验与 add_reference 同源：非空、锚定三态（topic 格式 / kit 词表
      / none 空值）、平台词表；标题 / 锚定值等变化正确写回元数据
- [ ] add_files 路径安全、不与 reference.json 冲突，内容按 UTF-8 写入；
      remove_files 必须实际存在于条目目录（清单外散文件也允许删除），
      删除实体并更新元数据 files 清单（保序去重）
- [ ] 任何校验失败：ReferenceError 中文文案 → HTTP 400，磁盘零变化
      （含「删除清单外路径」「删除 reference.json」「删不存在的文件」各例）
- [ ] 标题编辑不影响条目 id / 目录名（位置不变，引用稳定）
- [ ] 成功一次 commit_after_write 自动 git 提交（提交信息 `lib: update
      reference {id}`）
- [ ] pytest 新增用例全绿（成功 / 各校验失败 / 不存在条目 / 组合增删 /
      files 清单更新 / autocommit 触发），全量 pytest 保持绿

**实现备注（评审修订后）：**

- code-review 双轴（Standards + Spec）一致指出原实现的原子性承诺过头：
  write_json 失败时已写新增文件会残留。修订 = 元数据写入并入 cleanup 范围
  （写失败清理已写文件并保持元数据原值），新增测试
  test_update_reference_cleans_added_files_on_meta_write_failure 锁定。
- Spec 轴：platform 由「缺省兜底 any」改为「必填」——PUT 是元数据替换语义，
  兜底会把存量条目平台静默降级；测试补缺 platform → 400 断言。
- 形状校验（add_files / remove_files）沿用既有路由先例直接 HTTPException(400)
  （同 module_platform_files），非域语义错误（域错误仍走 ReferenceError 表）。
- 评审修订时修复自查发现：remove_files 缺省给 `()` 会误判非 list → 400，
  改为 `[]` 缺省（测试含「显式空容器合法」断言锁定）。
- 删除实体失败仅留清单外散文件：与浏览 / 统计「磁盘目录即数据库」容忍
  语义一致（先例 remove_platform_files 同款）。
