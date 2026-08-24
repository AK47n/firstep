# 03 — 真机验证：2024H 生成到英文目录并编译

**要做什么：** 用修复后的真实生成链路（非 fake）把 2024H 重新生成到
`C:\Users\luoji\Desktop\2024H_Auto_Car`，确认目录名是英文、`gmake -C
Debug -f makefile -B all` exit=0、`mspm0_project.out` 产出。

**被谁阻塞：** 01、02

**状态：** resolved

- [x] 真实生成 2024H → 桌面 `2024H_Auto_Car`
- [x] 目录内无中文路径残留（makefile 集 recipe 全 ASCII）
- [x] gmake 全量编译 exit=0、`.out` 存在

**验收记录（2026-08-24）：** 用真实 generate_project（复用 .contest_context.json
载荷：slugs 7 模块 / main_c / 题面 / instances）生成 `C:\Users\luoji\Desktop\
2024H_Auto_Car`；makefile 集 0 中文；`gmake -C Debug -f makefile -B all`
exit=0，`2024H_Auto_Car.out` 83508 字节；要点：CCS 22:56 打开新工程时用
.cproject 重建了 makefile 集（build-1404002600、-O2、绝对路径），纯 ASCII
路径下转码无损 → 编译通过——与中文路径乱码失败的对照证实根因即路径编码；
工程内容与中文目录版基本一致（.out 83508 vs 83584 字节差异 = 产物名不同）。
