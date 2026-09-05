// nav-tabs-shared.mjs — 顶部导航 tab 键单源（工单 version-changelog/05）：
// guide.test.mjs / guide-refs.test.mjs 只做成员校验（includes），顺序无断言
// 意义——键清单在此单源，免一次导航调整波及多个测试文件。
// 结构契约（分组 / 组内顺序 / 与 index.html 静态标记一致）的 canonical 是
// nav-tabs-guard.test.mjs（读 HTML 断言 GROUPS），并在其中锁定本清单与之相等。
export const NAV_TAB_KEYS = [
  "generate", "topic", "code", "settings",
  "library", "reference", "pdf", "md", "master",
  "guide", "changelog",
];
