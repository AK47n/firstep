# 02 — 包内 `START-HERE.txt`：解压后第一眼就看到「从这里开始」

**要做什么：** 一个新用户把完整包解压完，打开的文件夹里**第一个文件**就是 `START-HERE.txt`（记事本双击可读），
它只用一屏回答「现在双击哪个、装多久、装完干什么、怎么再启动」。
不需要他去读 `README.md`、更不会让他去猜 `install.bat` 和 `start-app.vbs` 有什么区别。

**被谁阻塞：** 无——可立即开始。

**状态：** ready-for-agent

- [ ] 根目录新增 `START-HERE.txt`，UTF-8 **无 BOM**、中文、≤30 行（一屏内读完）
- [ ] 内容只覆盖前 20 分钟，按顺序四段：
      ① 现在做什么（双击 `install.bat`；装什么：建虚拟环境 + 装依赖，**需要联网**，几分钟，可重复运行）
      ② 装完做什么（双击**桌面上的 `firstep` 快捷方式**；浏览器自动打开 `http://127.0.0.1:8000`）
      ③ 第一次用配一次 key（网页右上角「设置」→ 粘贴 DeepSeek API key → 「检查环境」）
      ④ 出问题怎么办（去哪个日志 / 哪份文档；`stop-firstep.bat` 是停服务）
- [ ] 含三条「预期行为」消除误解：**包里没有 `.venv` 是正常的**（脚本会建）/ 首次装依赖慢是正常的 / 重复运行 `install.bat` 不会出错
- [ ] 不重复 README 的合规声明与开发说明；面向的是**使用工具的人**，不是贡献者
- [ ] 登记进 `full_pack` 顶层白名单 `TOP_LEVEL_ENTRIES`（不登记则按现有规则根本不进包）
- [ ] 打包守卫扩 `tests/test_full_pack.py`：
      - [ ] `scan_tree(仓库根)` 结果**包含** `START-HERE.txt`
      - [ ] `excluded_paths(仓库根)` **不含** `START-HERE.txt`（防「清单有、包里没有」反例）
- [ ] 文档守卫扩 `tests/test_onboarding_docs.py`：`START-HERE.txt` 存在、无 BOM、三步链路 needle 齐全
      （`install.bat` / 桌面 `firstep` / API key / `http://127.0.0.1:8000`）
- [ ] **补上 README 的指向**（工单 01 评审留的尾巴）：`START-HERE.txt` 真进包后，「获取方式」表首行的
      「解压后照下面『三步装好』做」改回「解压后照包里的 `START-HERE.txt` 走」，
      并加一条守卫断言「README 提到的包内文件确实在 `scan_tree` 结果里」（防再次指向不存在的文件）
- [ ] `docs/agents/releasing.md` 的完整包一节已提到 `START-HERE.txt`（工单 01 顺手写了），核对无需再改
- [ ] 本机验证：对仓库根跑一次 `scan_tree` 与「清单 ↔ zip 内容一一对应」的既有断言，全绿

## 备注

- 本工单只产出「包内文件 + 白名单 + 守卫」，**不触发发版**；真实出现在用户手上要等下一次完整包（见 05）。
