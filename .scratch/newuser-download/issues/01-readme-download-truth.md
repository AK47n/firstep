# 01 — README「获取方式」只说事实：一条主路径 + 哪个文件给谁

**要做什么：** 一个新用户打开 GitHub 仓库主页，第一屏就能得到完整答案：**下哪个文件、多大、要不要装解压软件、
下完第一步做什么**。README 里不再出现任何「线上已经不存在的下载形态」，并且把「已装用户走工具内更新、
不用来这里」写在同一处，免得新用户误下 296 MB 的小发版包。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 「获取方式」表不再出现 `firstep-full.7z` / 7-Zip / Bandizip / 「约 6 GB」这类**已下线形态**的口径
- [x] 主路径写死在第一行：**下 `firstep-full-<版本>.zip`（约 821 MB）+ Windows 自带解压**
- [x] 同处给出「哪个文件给谁下」的表（完整包 / `firstep-update-*` / `manifest`·`removed`·`sha256` / git clone 四行，每行写明给谁用）
- [x] 轻量路径（`git clone`）保留，但**明确其定位是「不要资料库、且自己会配 Python」的人**
- [x] README 顶部固定链接指向 `/releases/latest`（实测 HTTP 200 → `releases/tag/v1.1.1`；不写死 tag 深链）
- [x] 「三步装好」第 2 步改为「双击桌面 `firstep` 快捷方式」，并补一句**以后再启动只双击它、不用再跑 `install.bat`**（`start-app.vbs` 降为兜底）
- [x] 全文搜一遍：顺带清掉两处遗留的「6 GB」体积口径（原第 32、80 行），体积只在「获取方式」出现
- [x] 文档守卫扩 `tests/test_onboarding_docs.py`：
      - [x] 负向：`dead_channel_hits()`（工具名 + 否定式放行 / 7z 分卷名直接命中）
      - [x] 正向：获取方式章含资产名形态 + 「自带解压」口径 + 三行「给谁下」+ `/releases/latest`
      - [x] 章内禁用词（`7-zip` / `bandizip` / `winrar` / 好压 一个字都不许提）
      - [x] 既有正向断言（`install.bat` / `start-app` / 板子型号 / Python 版本）全部仍绿
- [x] 全量回归：pytest **4342 passed / 1 skipped**；`node --test tests/js/*.test.mjs` **1554 pass / 0 fail**

## 验收记录（2026-09-13）

- **守卫有效性探针** `.scratch/newuser-download/probe-01-guard-effectiveness.py` → 证据 `verify-01-guard-effectiveness.txt`：
  旧 README 原文回归样本 5 条原因全部命中；5 条违规写法逐条命中；9 条防坑提醒/边界写法逐条放行；
  当前 README 0 命中；章内禁用词 5 个全干净。
  探针过程中抓到两个真问题：① 守卫初版**误伤**「不用装 7-Zip」这句防坑提醒；② 「解压 `.001`」模式
  在样本里**从未被命中**（探针 A 段是空断言）——两处都已修，并把「守卫必须自己先红一次」写进做法。
- **L1 真机演练**（用线上真实资产，非本地副本）→ 证据 `verify-01-L1.txt` 与 `E2E-8020.md`：
  - 下载 `firstep-full-v1.1.1.zip` **821,352,026 字节**，59 秒、峰值 18.96 MB/s；
  - SHA256 `8c6541e3…afd88` 与线上 `sha256.txt` **一致**；
  - **Windows 自带解压**（`tar.exe` / bsdtar，与资源管理器同一 libarchive 血统）→ 5.9 秒出 8,777 文件 / 1,070.0 MB；
  - 解压后第一眼 = **13 个根级文件 + 8 个目录、没有任何「从这里开始」** → 卡点 K1，已由工单 02 承接。
- **顺带发现**（登记不修）：本机 `curl.exe` 直连 GitHub 报 `schannel: CRYPT_E_NO_REVOCATION_CHECK` 失败，
  而 `gh` 与 Python `urllib` 均正常（工具内下载走 Python，**不影响用户**）。
- **与工单原文的一处偏差**：工单原写「下 `firstep-完整包-<tag>.zip`（约 790 MB）」，实际写成
  **线上真实存在的** `firstep-full-<版本>.zip`（约 821 MB）——「人话资产名」是工单 03 的目标、当期还不存在，
  这里若照抄，就等于又让用户去找一个不存在的文件（本工单要根治的病）。等 03 落地并实测过中文资产名后，
  再由 03 统一改口径（两处已互指）。
- **越界说明**：`docs/agents/releasing.md` 按 spec 的「7z 渠道口径下线」一并改（它原本把 6.2 GB / 7z 分卷
  当作新装主渠道），并补了 Release 说明模板与「中文资产名必须先实测」的要求。评审见 `code-review.md`。

## 备注

- 本工单**不依赖任何发版**：README 是仓库主页，改完立刻对新用户生效。
- 「7z 渠道下线」在本工单只动**口径**；历史 release 资产不删（见 spec「范围外」）。
