# 03 — 完整包资产改叫「人话名」，让新用户一眼知道该下哪一个

**要做什么：** 发布出去的完整包 zip，文件名本身就是说明书——GitHub Releases 页上新用户看到的是
`firstep-完整包-vX.Y.Z.zip`，而不是要靠猜的 `firstep-full-vX.Y.Z.zip`；
同页的 `firstep-update-*` 与 `manifest/removed/sha256` 都带「给谁用」的说明，
新用户不会再误下 296 MB 的已装用户包。

**被谁阻塞：** 01（README 得先把资产名写成同一个口径，否则又造出第 4 处不一致）。

**状态：** ready-for-agent

- [ ] `pack-full` 产出后增加一步「发布侧改名」：zip → `firstep-完整包-<tag>.zip`（多卷时 `<tag>.part<N>`）
- [ ] **同步改写清单**：`manifest.parts[].zip_name` 改成新名并重新落盘 `manifest.json`，
      `sha256.txt` 同步（它列的是同一批名字）——**产出的四件套必须自洽**
- [ ] **不改用户侧任何代码**：下载器按清单里的名字去 Release 上找同名资产，改名 + 改清单 = 链路不断
      （核对 `full_update._parse_parts` / `resolve_part_url` 的取名路径后再动手，并在工单里留一行核对结论）
- [ ] 契约写进 `docs/agents/releasing.md`：完整包 zip 用「人话名」，**同 release 内不得同时出现新旧两种 zip 名**
      （否则新用户又面对二选一；且用户侧的「任一资产缺失 = 整体判不可下」保护会因旧名残留而失效）
- [ ] 守卫：`tests/test_full_pack.py` 断言改名步骤产出「清单 `parts[].zip_name` == 新资产名」且 `sha256.txt` 对应可复算
- [ ] 守卫：`tests/test_onboarding_docs.py` 断言 `releasing.md` 里完整包资产名形态与 README 一致（防两处再次分叉）
- [ ] 上线前置说明写进工单：本改动**下次发版才生效**，且**旧版本用户不受影响**（他们看的是已发布的旧 release）

## 备注

- `firstep-update-*`（小发版四件套）资产名**绝对不动**：工具内更新按前缀发现资产，改名即断已装用户的更新链路。
- 若评估后发现「改名 + 重写清单」会牵动打包器的确定性测试基线，宁可把本单降级为「仅 Releases 说明书写清楚」，
  也不要在发版夜里动打包器（在工单 Comments 里记结论）。
