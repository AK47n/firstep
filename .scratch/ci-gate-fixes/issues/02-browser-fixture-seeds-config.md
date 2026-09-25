# 02 — 浏览器门禁在干净机器上能跑

**要做什么：** `browser-suite` job 在**空 HOME**（= CI runner 的真实形态）下真能起后端并答出端点哨兵，
不再依赖开发机上那份 `~/.contest_generator/config.json`；整支浏览器门禁 42 条用例在这种环境下通过。

**被谁阻塞：** 01（用它引入的 `FIRSTEP_CONFIG_PATH`；**不伪造 `HOME` / `USERPROFILE`**）。

**状态：** resolved

- [x] 夹具起后端前写一份**临时配置**，把 `module_library_dir` / `masters_dir` 指向**检出内**的 `library/`
- [x] 该配置还带**非空 `api_key`**（工单 01 收紧闸后库端点才放行）与**死端口 `base_url`**
      （漏拦的 LLM 路径不出网）——勾选项原只写了两个库目录，这两条是实现必须的补充，理由见 Comments
- [x] 用 01 的环境变量把子进程指到那份临时配置（不改夹具进程自身的环境语义）
- [x] 临时配置与临时目录随夹具收尾清掉（`exit` + `SIGINT`/`SIGTERM`；**`SIGKILL` 覆盖不到**，如实记）
- [x] **哨兵判据保持不变**：它这次报的是真话；不许改成「只看健康检查」
- [x] 种子目录先 `existsSync` 校验：布局改名时当场报「种子库不存在」，不产生误导性假红
- [x] 判据 = **空 `HOME` 下整支浏览器门禁（5 spec / 42 用例）通过**（本次红灯的现场口径）
- [x] 中文提交

## Comments

### 落地事实（2026-09-25）

`tests/browser/server.mjs` 新增 `seedConfig()`：`mkdtempSync` 写一份 `config.json`
（两个库目录指向 `<检出>/library/{modules,masters}`），`spawnServer` 把它经
**`FIRSTEP_CONFIG_PATH`** 交给子进程。三条附带决定，逐条说清为什么：

- **`api_key` = 夹具专用假值 `sk-browser-fixture`**（勾选项里没写，是实现的必要补充）：
  工单 01 把闸收紧成"非空 key 才放行"，而库端点与 AI 端点共用 `_require_config`——
  不给 key 则库端点仍 400，本单的目的就达不到。副作用要认下来：整支门禁从"未配置态"
  变成"已配置态"，所以**不能**再靠它验未配置态的界面行为。
- **`base_url` = `http://127.0.0.1:9/v1`（死端口）**：评审抓到的整改。不写它就落到
  `DEFAULT_BASE_URL = https://api.deepseek.com`，一条没被 spec 的 `page.route` 拦住的 LLM
  路径会**真出网**（假 key 换回 401）。**拦截不在夹具里**——那是各 spec 自己的
  `page.route`（`module-intro.spec.mjs:83`、`code-tree-click.spec.mjs:58`）；夹具没有
  "拦端点"这个职责。指到死端口后漏拦的路径立刻连接被拒：不出网、且大声失败。
- **两个种子目录先 `existsSync` 校验**：布局改名 / 检出里没有库时当场报"种子库不存在"，
  而不是后端起得来、库端点答 400、哨兵误报「端口上是旧后端」（夹具注释最怕的误导性假红）。

**临时目录清理**：`process.on("exit")`（正常结束）＋ `SIGINT` / `SIGTERM`（Ctrl-C / 被强杀，
排查时正是在反复 Ctrl-C）。**`SIGKILL` 收不到，会留残留**——这是范围外的已知限度，不假称已覆盖。

### 读数（本机实测，口径 = `HOME`/`USERPROFILE` 指向空目录）

| 场景 | 读数 |
|---|---|
| **改前**（旧夹具）+ 空 HOME | 哨兵判「端口上是旧后端」，**5 spec 全红** |
| **改后** + 空 HOME（**全新**临时目录）= CI runner 的形态 | **42 passed / 0 fail / 158 秒** ✅ |
| 改后 + 正常 HOME（本机那份真配置） | 42 passed / 0 fail |
| 改后 + 只把 HOME 换成另一目录（那份 HOME 里**没有**配置） | 42 passed / 0 fail |

第三、四行合起来说明：起作用的是**种子配置**，HOME 在哪、里面有没有配置都不影响。

> **这份读数不蕴含「CI 必绿」，如实说清限度**：① `n=1`——同一夹具在排查期间有过一整支红的
> 记录（见 `05`，签名与本次不同）；② 本机 158 秒对 `local-environment` 记的 pre-push 浏览器
> 预算（180 秒）仍是同一量级、贴着线，CI 那支 job 有 20 分钟预算故安全。
> 真正的判据是**推上去让 CI 自己跑一遍**（这条门自加上起就没在 CI 上真跑过，见 spec 底部）。

### ⚠ 副产物：`launcher-reload` 出现过一次整支红（已另开 `05`）

| 条件 | 读数 |
|---|---|
| 空 HOME，**复用过的**临时目录（同一目录跑第二轮） | `launcher-reload` 5 条全红（A = `page.reload` 30s 超时，B–E = `ERR_CONNECTION_REFUSED`） |
| 空 HOME，**全新**临时目录 | 5 条全绿 |
| 本机正常 HOME | 5 条全绿 |

**我不宣称这是"本单引入"或"不是本单引入"**——评审指出我先前那个对照（"旧夹具也红"）
其实是**同一个已知根因**（空 HOME 无配置 ⇒ 哨兵判旧后端），与这条新签名不是一回事；
而"`page.reload` 超时 + `ERR_CONNECTION_REFUSED`"这个签名在本仓
（`local-environment` 第 2 节那几条老偶发）里早有前科。故 `05` 只记现场与复现条件、
**不定性**，留给接手的人先把它稳定复现出来再谈。

