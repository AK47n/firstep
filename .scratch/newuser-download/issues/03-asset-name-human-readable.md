# 03 — 完整包资产改「人话名」，让新用户一眼知道该下哪一个

**要做什么：** 发布出去的完整包 zip，文件名本身就是说明书——GitHub Releases 页上新用户看到的是
`firstep-完整包-vX.Y.Z.zip`，而不是要靠猜的 `firstep-full-vX.Y.Z.zip`；
同页的 `firstep-update-*` 与 `manifest/removed/sha256` 都带「给谁用」的说明，
新用户不会再误下 296 MB 的已装用户包。

**被谁阻塞：** 01（README 先把资产名口径写成同一个说法）。

**状态：** resolved（**决策：不改名**，见下）

## 决策与理由（2026-09-13 定案）

**不做改名。** 完整包资产名继续是 `firstep-full-<tag>.zip`；新用户的可发现性改由
「Release 说明正文前两行 + README 获取方式 + 包内 `00-START-HERE.txt`」三处承担。

三条理由（细节与重新评估条件见 `docs/adr/0015-full-package-asset-name-ascii.md`）：

1. **改名必然连带手改机器清单**：工具内「检查完整包」按清单里的 `zip_name` 在 Release 上
   找**同名**资产（`full_update._parse_parts` → `resolve_part_url` 逐字匹配）；
   名字不一致 → 分卷表为空 → **整条链路判「不可下」**。这不是改文件名，是「改名 + 手改 3.7 MB
   的 `manifest.json` + 重算校验和」。
2. **上传侧对非 ASCII 名没有可靠证据，且有反向证据**：`releasing.md` 记着「gh 上传中文名会被
   换成 `default.txt`」；要推翻只能真上传实测，而**在同一 tag 上传第二个 zip 会让所有已装用户
   的检查更新判「不可下」**——测试动作本身有破坏性，除非另开一次性 tag，成本收益不成比例。
3. **收益已被更便宜的手段拿走**：新用户要的是「一眼知道下哪个」，不是「文件名带中文」。
   Release 说明前两行 + README + 包内第一个文件（`00-START-HERE.txt`）已落地并有守卫钉住。

## 验收项（按「不改名」口径勾）

- [x] 决策与理由写成 ADR（`docs/adr/0015-full-package-asset-name-ascii.md`），含**重新评估条件**
      与「不允许在已发布 tag 上原地改名」的红线
- [x] `firstep-update-*` 资产名不动的约束一并写进 ADR（工具内更新按前缀发现资产）
- [x] 「同一 release 内不得同时存在新旧两种 zip 名」的约束保留在 `releasing.md`「附件命名注意」
- [x] 新用户可发现性用替代手段落地并验证：
      - Release 说明前两行固定（三个 release 都已改写，`verify-06-releases.txt`）
      - README「获取方式」只指一个文件（工单 01）
      - 包内 `00-START-HERE.txt` 排序第一（工单 02）
- [x] 不新建 `tests` 断言（**没有代码改动就没有可断言的契约**——避免为「不做的事」写空守卫）
- [ ] ~~`pack-full` 产出后改名并重写清单~~（**不做**，理由见上）

## 备注

- 本工单原计划的 `pack-full` 改名步骤**全部取消**；工单保留为「决策记录」，不再有待办。
- 若将来满足 ADR 里的重新评估条件，按 ADR 第 4 条流程实施，届时另开工单，
  **不要在本工单上复活**。
