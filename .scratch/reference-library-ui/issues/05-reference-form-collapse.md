# 05 — 录入表单分区折叠 + 视觉收尾

**要做什么：** 参考文件录入表单按「基本信息（标题 / 类型）/ 素材与锚定
（简介草稿 / 文件 / 锚定三态）/ 平台属性」分区折叠，默认只展开第一步；
空态 / 加载态 / 按钮 / 徽章视觉与全站（生成页、模块库页）对齐。

**被谁阻塞：** 工单 02（表格令牌与检索已完成，收尾在一致风格上）。

**状态：** resolved

- [x] 录入表单分区折叠（默认展开「基本信息」；锚定三态切换与套件下拉、
      平台 radio 保持在所属区内；折叠样式沿模块库 add-section collapsed
      先例，aria-expanded 语义正确）——三段 .add-section（add-sec-ref-basic /
      add-sec-ref-material / add-sec-ref-platform）复用模块库全局
      initAddSections()（选择器 .add-section 遍历，零新 JS），默认
      aria-expanded true/false/false，DOM 不销毁（收起不丢已填状态）
- [x] AI 简介草稿按钮、入库按钮与各提示文案位置随分区调整，交互不变——
      AI 草稿按钮留 ②（就近素材文件）；入库按钮移 ③（最后动作）；
      评审修订：草稿 / 文件载入反馈从 ref-add-msg（③默认收起，用户不可见）
      拆到新 ref-draft-msg（②内就近）；入库反馈仍 ref-add-msg（③）
- [x] 按钮统一（主 / 普通 / danger 全站一致）——经全局按钮样式 + .primary /
      .danger 兑现（工单 02 起）；聚焦态全局 :focus-visible（L170 + L696
      checkbox/radio）
- [x] 空态 / 加载态 / 错误态视觉打磨——empty-state（📚/🔍 空态区分「暂无
      条目」vs「没有匹配」）与 ⏳ 加载占位为工单 02 实现；错误 ref-msg /
      ref-add-msg / ref-draft-msg 走全局 .error/.ok；本轮与模块库同风格核对
- [x] 补充规则视觉（选中 / 悬停 / 键盘焦点）与既有表格体系一致（tr:hover
      高亮、chips on 态、:focus-visible）——无回归：录入 / 校验 / 删除 /
      搜索全流程冒烟通过（02 段检索、03/04 段录入-编辑-删除临时条目全链路、
      05 段折叠交互，48 项 PASS）

**实现备注（评审双轴修订后）：**

- Spec 轴 C1（行为回归，实锤）：draft 成功 / 失败消息与文件载入消息写
  ref-add-msg（③默认收起）→ 在 ② 点「AI 生成简介草稿」后反馈被藏进折叠区，
  与「交互不变」冲突。修：新增 ref-draft-msg（② body 底部），draft handler
  与 bindFilePicker 两处 msgEl 迁移；入库反馈仍 ref-add-msg（③内，点入库处
  就近）。冒烟增「草稿反馈在②区、入库反馈在③区」回归检查。
- Spec 轴 A1（工单 3/4/5 项在 diff 无增量）：视觉收尾三勾在 02/03/04 轮已
  兑现（表格令牌 .lib-table、空态 / 加载占比、按钮 / 聚焦全局样式、tr:hover /
  chips on），本轮为核对 + 整体一致性确认——工单注明归属，不重复实现。
- Spec 轴 A2（勾 5 全流程无回归未在 t05 增断言）：录入（03/04 临时条目
  POST）、校验（后端 400 中文）、删除（cleanupTmp/cleanupD DELETE + 服务器
  直查零残留）、搜索（02 段即时过滤）全由既有冒烟段覆盖，t05 不重复。
- Standards 轴（判断级）：①三段 .add-section 与模块库逐字结构重复——有界、
  先例一致（共享 CSS + initAddSections 已去重行为），不修；②add-sec-ref-
  material 命名（模块库 add-sec-files 更窄）——分区内容不同（素材 + 锚定 +
  简介），名称如实，不修；③冒烟状态卫生——t05c 清理后补 addFileRow 恢复
  表单预置基线 1 行（与初始态一致，不污染复跑）。
- 冒烟新增 6 项（工单 05 段）：三分区默认态 + aria 序列、②点击展开、
  收起不丢已填状态（行数不变；预置基线 1 行为既有设计，模块库同款）、
  ③展开后入库按钮 offsetParent 可见、草稿 / 入库反馈分区归属。
- 验证：tests/js 336 绿（HTML 结构改动零纯函数影响）、pytest 2393 绿
  （无后端改动）、冒烟 48 项 PASS；截图证据 05-form-collapsed.png（默认只
  展开①）/ 05-form-expanded.png（展开①+②）。
