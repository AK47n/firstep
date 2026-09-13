# 06 — Releases 页说明改写 + 下载链路一致性自检（工单 01 的另一半）

**要做什么：** 新用户不会只读 README——他从 README 的 `/releases/latest` 链接点进来，
**第一眼看的是 Release 说明正文**，而那里当时还挂着 v1.0.0 的「完整包 = 约 6.2 GB / 4 个 7z 分卷」。
本工单把 Releases 页本身修好，并留一个**发版前自检**，防止文档与线上再次分叉。

**被谁阻塞：** 01（README 口径先定，两处要讲同一个故事）。

**状态：** resolved

- [x] 三个 Release 的说明正文改写（**服务端 notes，不动资产、不动 tag**）：
      - `v1.1.1`（最新版）：标题后插入固定的前两行——新用户只下 `firstep-full-v1.1.1.zip`（约 821 MB，
        系统自带解压，包内 `00-START-HERE.txt` 三步）/ 已装用户走工具内更新；
      - `v1.1.0`：加「已被 v1.1.1 取代」警示 + 同样的前两行；
      - `v1.0.0`：标注「历史归档，不要照这一页做」，说明为什么（4 个 7z 分卷 / 约 6.2 GB / 需 7-Zip /
        不含 v1.1.0 起的增量能力），并指向最新版。**历史内容一律保留不改。**
- [x] 说明里的下载直链实测可用：`releases/latest/download/firstep-full-v1.1.1.zip` → HTTP 200 / 821,352,026 字节
- [x] `docs/agents/releasing.md` 的「Release 说明模板」与「快速发版（给 Agent）」互相指路
- [x] 新增发版前自检 `tools/check-download-docs.py`（README / 线上 Release / 包内文件三处一致性），
      并挂进 `releasing.md` 的「发版前必做」与「快速发版」两步
- [x] 自检的正反两向都验过：当前口径 PASS；把旧口径（6 GB + 7z 分卷 + 需 7-Zip）塞进去 → 命中 4 条

## 验收记录（2026-09-13）

- 改写脚本 `patch-releases.py` **幂等**（已改过的 release 跳过），改完逐条复核首几行；
  原始输出 `verify-06-releases.txt`。
- 自检脚本原始输出 `verify-06-consistency.txt`（完整版 PASS / 离线版 PASS 且在结论里点明线上那半没查）。
- **两处踩坑留痕**（都是"自己先红一次"抓出来的）：
  1. 自检初版拿「章内第一条 约 N MB」去比完整包——实际那条是 `git clone` 的 270 MB，
     **探针自己误报**。改成逐行按资产名绑定，并把 clone 那行改用 `git count-objects -vH` 的
     `size-pack`（实测 271.95 MiB，与 README 写的「约 270 MB」相符）校验。
  2. 初版只查体积与资产名，**抓不住 7z 旧口径**；反向验证时发现这个盲区，补齐了已下线形态判据
     （与 `tests/test_onboarding_docs.py` 的守卫同口径，含否定式放行），再做红/绿两向验证。
- 为什么不写进 pytest：本仓库测试**刻意不联网**（`tests/fakes.py` 明写「网络不进测试」），
  联网门禁会引入 flaky；故做成发版前手动跑的自检。

## 备注

- 本工单**不改任何代码路径**，只改服务端 Release 正文与加一个发布侧脚本。
- Release 正文是服务端状态、不在 git 里；`verify-06-releases.txt` 是它的**唯一在库证据**，
  改文案前先看那份文件。
