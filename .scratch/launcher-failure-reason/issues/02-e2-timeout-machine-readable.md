# 02 — E2 超时态真机复现收口（`start-app.bat :timeout`）

**要做什么：** 挂账单 `real-acceptance/01` 的 **E2 第三态**（启动超时弹窗）自第十六轮起就是
「留人工 / 需劣化环境」。工单 01 把失败原因变成可机读之后，本单在劣化环境里**真跑一次** `:timeout`
分支并把现场落盘——从此这一态的判读口径是「日志里的 `reason=timeout`」，不再是「退出耗时 ≈25s 所以
大概是超时」，E2 也就可以从留人工转成机器可判读。

**被谁阻塞：** 01（launcher 可机读失败原因）——没有 `reason=` 这一行，本单的判据仍然只能靠计时。

**状态：** resolved

- [x] 劣化环境配方落盘：**真 exe 形态的「慢 python」替身**（真 python 安装目录整目录拷贝 +
      `python._pth`（`Lib`/`DLLs`/`.`/`import site`）+ `sitecustomize.py` 钩子：命令行出现
      `-m contest_generator.webapp` 就挂住，其余调用原样放行）；`USERPROFILE` 重定向到临时目录。
- [x] 真跑 `cmd /c start-app.bat`，实测走 `:timeout`：`launcher.log` 出现 `reason=timeout port=8899`、
      退出码 1、服务侧 `webapp.log` 只有替身那行「holding service start」（服务从未就绪）。
- [x] 同场对照三态（同一脚本、同一台机器）：`already_running`（8899 上真起过服务）/ `port_busy`
      （8899 上占位服务身份不符）/ `no_python`（PATH 无 python）——四态 reason 各不相同且与期望一致；
      另加默认端口 8000 的只读观察 `already_running@8000`。
- [x] 现场落盘 `.scratch/launcher-failure-reason/verify-01-branch-matrix.txt`（逐态：前置、期望、
      退出码、耗时、`launcher.log` 原文、判读），**7/7 PASS**。
- [x] 回勾 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md` 的 E2 行
      （第三态从「留人工」改为「机器可判读」并给出证据路径）+ 来源工单
      `newcomer-onboarding/02-launcher-chinese-feedback.md` 对应项。
- [x] 如实记账：本单**不**声称在「真·慢机器/冷启动」上验过——只打通劣化环境下的可复现性与可判读性
      （spec「范围外」已写）；被强杀/等待的边界也在落盘里写明。

## 验收记录（2026-09-12）

`python .scratch/launcher-failure-reason/probe-01-branch-matrix.py` → `verify-01-branch-matrix.txt`：

- **`:timeout` 真机复现成功**（第十六轮起挂了三轮的「留人工/需劣化环境」到此收口）：
  退出码 1、耗时 47.4s（= 20 次轮询 + 收尾），`launcher.log` = `[2026-09-12T09:59:34+08:00] reason=timeout port=8899`，
  服务侧 `webapp.log` 尾行 `[slow-python] holding service start`（证明「服务起得来但没就绪」这个形态为真）。
- 同场 7 态全绿（见工单 01 的表格）。
- **不扰民证明**：`started` / `already_running` / `already_running@8000` 三态各自「新增浏览器进程=0、
  已复原=True」（临时改写 URL 关联后立即复原）；整轮前后浏览器进程数 8 → 8；结尾核对用户 8000 会话
  `{"app": "contest-generator", "ok": true}`。

## 配方与踩坑（供下一轮复用，也是本单的「怎么验」）

| 步 | 做法 | 坑（都实测过） |
|---|---|---|
| 让服务「起得来但不就绪」 | 真 python 目录整拷 + `sitecustomize.py`：`-m contest_generator.webapp` 就挂住 | ① PATH 前置 `python.cmd` 垫片会让 launcher 的批处理异常退出；② 只拷 `python.exe` 单体跑不起来（DLL 在安装目录里）；③ `._pth` 会接管 sys.path，必须写 `Lib`/`DLLs`/`.`/`import site`，否则 `encodings` 都 import 不了；④ **解释器启动阶段 `sys.argv` 只有 `['-m']`**，模块名要看 `sys.orig_argv`（本条是最后一块拼图） |
| 判读 | 读 `launcher.log` 的 `reason=` 行 | 被强杀/等待的进程退不出码 ⇒ 不要把退出码当唯一判据 |
| 不弹框 | 探针自带「firstep 标题窗口一出现就按 pid 杀」的清扫线程 | 清扫别用 `taskkill /IM powershell.exe`（会误伤别的东西）；判据别用「命令行含 Popup」（会命中测试执行器自己） |
| 不开浏览器 | 临时改写 `HKCU\…\Classes\<ProgId>\shell\open\command` → `cmd.exe /c exit`，跑完复原 | `start` 是 cmd 内建命令，PATH 垫片与「替换内建分派」都拦不住 |
| 收尾清端口 | 每个状态开始前 + 收尾都按**端口**清一次监听者（`clear_port`） | launcher 用 `start "" /b` 把服务**脱离进程树**起了，`taskkill /T` 打不到它；漏收一次就会留一个探针端口监听者，让下一次测量读到 `:already_running`/`:port_busy` 而不是它该有的形态（实测踩到过：`:started` 被判成 `port_busy`） |

## Comments

- 2026-09-12：立单。素材 = `newcomer-onboarding/verify-16-E2-timeout-state.txt` 的六版尝试
  （其中 v4/v5/v6 都栽在「宿主里跑 `.bat`」的工具链交互上，不是产品问题）。
- 2026-09-12：落地。第六版之后的第七种造法（真 exe + `sitecustomize`）才把第三态稳定造出来。
