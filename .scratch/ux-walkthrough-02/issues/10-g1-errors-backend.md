# 10 — G1 后端错误人话化（文件系统分派 / 500 去类型名 / backup_id 文案）

**要做什么：** 后端面向用户的错误消息不再透黑话：①文件系统 OSError 按 errno/winerror 分派中文与修复步骤（WinError 32 → 文件正被占用提示关闭 Keil；Errno 28 → 磁盘空间不足；PermissionError → 只读/权限）；②500 兜底去掉 `type(exc).__name__`，保留「服务器内部错误」+ 反馈引导（类型名进日志）；③backup_id 相关报错（非法/不存在）改人话并给下一步（自动回滚备份已失效、可重新生成或手动保留副本）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 文件系统错误分派：winerror 32 / errno 28 / PermissionError 各有中文文案与修复步骤；其它 OSError 保持「文件操作失败」前缀但不再裸 str(exc)（无映射时给一般性说明）
- [x] 500 兜底串不含异常类型名（类型名仅日志）
- [x] backup_id 相关错误消息人话化含下一步
- [x] pytest 覆盖上述分派分支（含未映射 OSError 兜底）
- [x] pytest 全量通过；受影响的既有 message 断言同步更新
