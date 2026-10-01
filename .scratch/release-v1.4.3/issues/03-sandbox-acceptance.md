# 03 — 沙箱「模拟用户机」真机验收 + 当场回写第 1 节

**要做什么：** 从**要发的那棵树**重造一份干净沙箱，按 `docs/agents/local-environment.md` 第 1 节的四个落点
（工具根 / 数据目录 / 端口 / 入口）真进程 ＋ 真 Chromium 走一遍：看的是"用户打开工具会看到什么"，
并核对本轮那两条可见变化真的出现在页面上。结论**当场回写**第 1 节与第 2 节。

**被谁阻塞：** 01（沙箱要从要发的那棵树造出来）。

**状态：** ready-for-agent

- [ ] **先收 8020**（重建会整树删工具根，带进程删会 `WinError 32`）
- [ ] `python .scratch\full-download\make_sim_sandbox.py`（工具根 `Desktop\firstep-sim`、
      数据目录 `~\.contest_generator_sim` 一起重造）
- [ ] 补回 `sim-run.py`（构建脚本不带它；恢复副本 `.scratch/update-restart-stale-service/sandbox-entry-sim-run.py`）
- [ ] `FIRSTEP_LAUNCHER_PORT=8020` 起沙箱 → `GET /api/health` 版本 = **1.4.3**
- [ ] 真浏览器验收（探针从 `.scratch/release-v1.4.0/probe-sandbox-accept.mjs` 复制一支到本目录并**加本轮检查**）：
      ① 十二页签「有文字的元素」字号 ⊆ 六档角色、正文基准 14px（老口径照旧）；
      ② **三条文字**（`.res-soft` / `.sugg-count` / `.chip.rec.unsel .reason`）的计算色 = 实色 `--muted`、
      **不再有 `opacity`**，且对比度 ≥ 4.5；
      ③ **浅色主题**板图「固定/电源」焊盘取值 = `rgb(175,184,193)`（与「空闲 IO」同一支）；
      ④ 设置页版本 = v1.4.3、版本更新记录页首块 = v1.4.3
- [ ] 真身数据目录**零触碰**：`~\.contest_generator\config.json` mtime 仍是 **2026-09-10 23:28:07**
- [ ] 收尾：收 8020、查无残留 `contest_generator.webapp` / `sim-run` 进程
- [ ] **当场回写** `local-environment.md` 第 1 节（沙箱当前状态 = v1.4.3）与第 2 节（端口实况：
      8000 真身没在跑、8020 已释放）
- [ ] 提交信息中文

## Comments

### 落地事实

（做完填：沙箱文件数 / 体积、`/api/health` 读数、验收通过条数、收尾状态）
