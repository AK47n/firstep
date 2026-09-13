# 02 — 包内 `00-START-HERE.txt`：解压后第一眼就看到「从这里开始」

**要做什么：** 一个新用户把完整包解压完，打开的文件夹里**第一个文件**就是 `00-START-HERE.txt`（记事本双击可读），
它只用一屏回答「现在双击哪个、装多久、装完干什么、怎么再启动」。
不需要他去读 `README.md`、更不会让他去猜 `install.bat` 和 `start-app.vbs` 有什么区别。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 根目录新增 `00-START-HERE.txt`，UTF-8 **无 BOM**、中文、≤30 行（一屏内读完）
- [x] 内容只覆盖前 20 分钟，按顺序四段：
      ① 现在做什么（双击 `install.bat`；装什么：建虚拟环境 + 装依赖，**需要联网**，几分钟，可重复运行）
      ② 装完做什么（双击**桌面上的 `firstep` 快捷方式**；浏览器自动打开 `http://127.0.0.1:8000`）
      ③ 第一次用配一次 key（网页右上角「设置」→ 粘贴 DeepSeek API key → 「检查环境」）
      ④ 出问题怎么办（去哪个日志 / 哪份文档；`stop-firstep.bat` 是停服务）
- [x] 含三条「预期行为」消除误解：**包里没有 `.venv` 是正常的**（脚本会建）/ 首次装依赖慢是正常的 / 重复运行 `install.bat` 不会出错
- [x] 不重复 README 的合规声明与开发说明；面向的是**使用工具的人**，不是贡献者
- [x] 登记进 `full_pack` 顶层白名单 `TOP_LEVEL_ENTRIES`
- [x] 打包守卫扩 `tests/test_full_pack.py`：
      - [x] `scan_tree(仓库根)` 结果**包含**它
      - [x] `excluded_paths(仓库根)` **不含**它
      - [x] 新增 `test_start_here_sorts_first_in_explorer`：解压后第一个**可见**文件必须是它
      - [x] 新增 `test_readme_promised_package_files_exist_in_package`：README 点名「去包里看」的文件必须真在包里
- [x] 文档守卫扩 `tests/test_onboarding_docs.py`：三步链路 needle 齐全
      （`install.bat` / 桌面 `firstep` / API key / `http://127.0.0.1:8000` / `webapp.log` / `.venv` / 「重复」）
- [x] **补上 README 的指向**（工单 01 评审留的尾巴）：已改为「解压完第一个文件就是 `00-START-HERE.txt`」
- [x] `docs/agents/releasing.md` 的完整包一节同步新名（工单 01 顺手写了，本次核对无需再改）
- [x] 本机验证：真打一次完整包（`v0.0.0-probe`，8,776 文件 / 770.2 MB zip）→ 它在 zip 里、在清单里、
      清单 SHA256 与盘上文件一致、包内第一个可见条目就是它
- [x] 真机 L2 演练：见 `E2E-8020.md` 与 `verify-02-L2.txt`（全链路 PASS）

## 验收记录（2026-09-13）

- **红证（守卫真会红）**：临时把它从白名单摘掉 → `test_top_level_entries_cover_tool_root` 与
  `test_repo_start_here_ships_in_package` **两条 FAIL**；还原后逐字节干净（`git diff` 只有预期的 3 行新增）。
- **真打包验证**：`python -m contest_generator.full_pack --tree . --version v0.0.0-probe` →
  zip 内含 `00-START-HERE.txt`；清单记 `size=2175 / sha256=b048d492…`，与盘上文件一致；
  包内根级第一个可见条目 = `00-START-HERE.txt`。
- **改名决策（与工单原文的偏离 + 两处自伤，都留痕）**：
  1. 工单原定名 `START-HERE.txt`；实测它在资源管理器里排到 README **之下**（名称序 #11/14；
     隐藏扩展名时 #17/22）——**排在中间就等于没有**。改名 `00-START-HERE.txt` 后为**第一位**。
     定名理由写进 `full_pack.py` 注释与守卫 docstring，防后人「顺手去掉那个奇怪的 00-」。
  2. 我用 `Set-Content -Encoding UTF8` 改内容时被 PS 5.1 **加了 BOM**，被新守卫当场抓住（已改回无 BOM）。
  3. 批量替换 `.scratch` 文档时套出 `00-00-` 双前缀（6 个文件、28 处），已全部修正并复查为 0。
     **教训**：批量文本替换必须幂等 + 断言替换条数——第一版没做，靠肉眼差点漏过。
- **L2 真机演练**（原始输出 `verify-02-L2.txt`）：从真实包解压（6.5 秒 / 8,776 文件）→
  `install.bat` 五步全过 → 桌面快捷方式三属性正确 → `http://127.0.0.1:8020/api/health` 返回本应用 →
  配置与日志全落演练用户目录、真身 `~\.contest_generator` mtime 未变 → 再跑一次 `install.bat` 幂等。
- **回归**：`tests/test_full_pack.py` 27 条 + `tests/test_onboarding_docs.py` 8 条全绿；全量见提交信息。

## 备注

- 本工单只产出「包内文件 + 白名单 + 守卫」，**不触发发版**；真实出现在用户手上要等下一次完整包（见 05）。
- 演练顺带发现两个小卡点：**K5**（`install.bat` 收尾没讲「以后不用再跑本脚本」）归工单 04；
  **K6**（`install.bat` 里写死的 8000 与多实例端口不一致）只登记不改。
