// ui/hwcheck.js — 硬件检测栏目的**入口**（工单 module-hwcheck/01 + 02；
// 工单 hwcheck-hygiene/11 起只剩"接线 + 两个导出"）。
//
// 对外契约（`boot.js` 的装载清单与既有用例指着的是**这两个名字**，一个字不许改）：
//   renderHwcheckPanel()  面板整体重绘（本件只转出，定义在 ui/hwcheck-core.js）
//   initHwcheck()         接线 + 首次渲染
//
// 四件的**依赖方向**见 ui/hwcheck-core.js 头部（单源，改那里就够）：不是一条链，而是
// 「入口 → 器件 / 动作 / 核心（三件并列）＋ 器件 → 动作 / 核心 ＋ 动作 → 核心 ＋ 核心 →
// 谁都不 import」。本件只留**接线的形状**（谁在什么事件上挂哪个处理函数）；处理分支住在
// 它们操作的那一件里——这样"点了会怎样"的代码与它改的状态在同一屏，入口不必再读懂全部业务。
//
// ⚠ 这一栏的接线有三条老规矩（下面各自带注释）：一律**容器级委托**（`innerHTML` 全量重绘
// 后仍有效）；重绘前用 `setPendingFocus` 登记焦点落点（工单 hwcheck-hygiene/06）；
// 说明按钮走既有捕获阶段委托（冒泡阶段拦不住"点说明 = 把器件去掉"）。

import { $ } from "/js/app.js";
import { HWCHECK_LAST_DIR_KEY, HWCHECK_PARENT_KEY } from "/js/fx/hwcheck-project.js";
import { bindModuleInfoEntry } from "/js/ui/generate-recommend.js";
import {
  generateHwcheck,
  handleChannelChange,
  handleChecklistChange,
  handleDeviceChipsClick,
  handleDeviceChipsKeydown,
  handleDeviceGridClick,
  handleDeviceGridKeydown,
  handleParentChange,
  handlePlatformClick,
  handleProjectClick,
  handoffToGenerate,
  loadHwcheckRecent,
  pickHwcheckParent,
  previewHwcheck,
  restoreHwcheckProject,
  submitHwcheckTriage,
} from "/js/ui/hwcheck-actions.js";
import {
  hwcheckUI,
  readStored,
  renderHwcheckAdvice,
  renderHwcheckDevices,
  renderHwcheckPanel,
  renderHwcheckUnverifiedNote,
} from "/js/ui/hwcheck-core.js";
import {
  handleMyDeviceChange,
  handleMyDeviceClick,
  handleMyDeviceInput,
  loadMyDevices,
  openMyDeviceForm,
  suggestMyDeviceId,
} from "/js/ui/hwcheck-devices.js";

// 面板重绘的定义在核心件——这里**转出**：入口正文也要调它（下面那句
// `renderHwcheckPanel()`），所以同时有一条 import 边与这条再导出边。
export { renderHwcheckPanel } from "/js/ui/hwcheck-core.js";

export function initHwcheck() {
  hwcheckUI.parentDir = readStored(HWCHECK_PARENT_KEY);
  const parentInput = $("hwcheck-parent");
  if (parentInput) parentInput.value = hwcheckUI.parentDir;

  const platforms = $("hwcheck-platforms");
  if (platforms) {
    // 事件委托（innerHTML 全量重绘后仍有效）：点平台卡 → 换平台并清掉旧产物
    // （旧产物是另一块板子的 main.c，留着会误导）。
    platforms.addEventListener("click", handlePlatformClick);
    platforms.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const card = e.target.closest("[data-hwcheck-platform]");
      if (!card) return;
      e.preventDefault();
      card.click();
    });
  }
  const channels = $("hwcheck-channels");
  if (channels) {
    // 通道勾选走委托（工单 02 起通道清单可能变长，逐个绑定会漏）；
    // 通道是渲染输入 → 改了就把旧预览清掉（旧文本是另一种形态的 main.c），
    // 并重取板侧视图（通道模块自己也会占脚、也会撞脚）。
    channels.addEventListener("change", handleChannelChange);
  }

  // —— 器件挑选（工单 03）：搜索框 / 卡片网格（点卡片 = 加一件）/ chips（点 = 去掉）——
  const deviceSearch = $("hwcheck-device-search");
  if (deviceSearch) {
    deviceSearch.addEventListener("input", () => {
      hwcheckUI.deviceQuery = deviceSearch.value || "";
      renderHwcheckDevices();
    });
  }
  const deviceGrid = $("hwcheck-device-grid");
  if (deviceGrid) {
    // 与生成页模块网格同一套委托语义：详情按钮优先（开说明弹窗），
    // 卡片本体 = 加一件器件。平台用**本栏目自己的**（生成页的平台可能不同）。
    deviceGrid.addEventListener("click", handleDeviceGridClick);
    // 键盘同等可达（工单 06）：卡片是 role="button" tabindex="0"。
    // 详情按钮是真 <button>（浏览器自己把 Enter/Space 变成 click），排掉免得开两次。
    deviceGrid.addEventListener("keydown", handleDeviceGridKeydown);
  }
  const deviceChips = $("hwcheck-device-chips");
  if (deviceChips) {
    // 说明按钮走既有委托（捕获阶段拦，否则会连带把 chip 从工程里移除）
    bindModuleInfoEntry(deviceChips, () => hwcheckUI.platform);
    deviceChips.addEventListener("click", handleDeviceChipsClick);
    // chip 是 role="button" tabindex="0"（工单 hwcheck-hygiene/06）：Enter / Space 同义
    deviceChips.addEventListener("keydown", handleDeviceChipsKeydown);
  }
  const preview = $("btn-hwcheck-preview");
  if (preview) preview.addEventListener("click", previewHwcheck);
  const generate = $("btn-hwcheck-generate");
  if (generate) generate.addEventListener("click", generateHwcheck);
  // 带入生成页（工单 hwcheck-acceptance/04）：容器级委托（innerHTML 全量重绘后
  // 仍有效，与器件网格 / chips 同一套纪律）。按钮置灰时不触发（浏览器不发 click）。
  const handoff = $("hwcheck-handoff");
  if (handoff) {
    handoff.addEventListener("click", (e) => {
      if (e.target.closest("[data-hwcheck-handoff]")) handoffToGenerate();
    });
  }

  if (parentInput) {
    parentInput.addEventListener("change", () => handleParentChange(parentInput));
  }
  const pick = $("btn-hwcheck-pick-parent");
  if (pick) {
    pick.addEventListener("click", () => pickHwcheckParent(parentInput));
  }

  // —— 「我的器件」（库外件，工单 02）：新建 / 编辑 / 删除 / 保存 / 取消 ——
  // 全部走容器级委托（innerHTML 全量重绘后仍有效，与器件网格同一套纪律）。
  const myNew = $("btn-my-device-new");
  if (myNew) myNew.addEventListener("click", () => openMyDeviceForm(null));
  const myBox = $("my-devices");
  if (myBox) {
    myBox.addEventListener("click", handleMyDeviceClick);
    // 表单输入：`input` 覆盖打字（地址预览与校验理由实时跟上），`change` 单独
    // 接一次是为了 `<select>`（总线下拉在部分浏览器上不触发 input）。
    // 资料文本框（工单 07）只同步 state —— **不许重绘**（正在打字，同表单纪律）。
    myBox.addEventListener("input", handleMyDeviceInput);
    myBox.addEventListener("change", handleMyDeviceChange);
    // 名称 → id 建议：只在 id 还是空 / 还是上一次自动填的那值时补一下，
    // 用户手填过 id 就不动它（不覆盖用户输入）。
    // ⚠ 只改 id 那个输入框的 value 再 syncMyDeviceForm —— **不许整块重绘**：
    // 用户正在表单里往下填（或刚填完其它字段），整块重绘会把它们一起清掉
    // （与 syncMyDeviceForm 那条同一个坑：真正在编辑的表单不能被替换）。
    myBox.addEventListener("blur", (e) => suggestMyDeviceId(myBox, e), true);
  }

  const project = $("hwcheck-project");
  if (project) {
    project.addEventListener("click", handleProjectClick);
  }
  const checklist = $("hwcheck-checklist");
  if (checklist) {
    checklist.addEventListener("change", handleChecklistChange);
  }
  // —— 现象回填 + AI 排障（工单 08）：唯一的 LLM 入口 ——
  const symptom = $("hwcheck-symptom");
  if (symptom) {
    symptom.addEventListener("input", () => {
      hwcheckUI.symptom = symptom.value;
      renderHwcheckAdvice();   // 按钮的可用性跟着"填没填"变
    });
  }
  const triage = $("btn-hwcheck-triage");
  if (triage) triage.addEventListener("click", submitHwcheckTriage);
  const recent = $("hwcheck-recent");
  if (recent) {
    recent.addEventListener("click", (e) => {
      const row = e.target.closest("[data-hwcheck-open-project]");
      if (row) restoreHwcheckProject(row.dataset.hwcheckOpenProject);
    });
  }

  renderHwcheckUnverifiedNote();
  renderHwcheckPanel();
  // 「我的器件」拉一次（与平台无关，所以不随换平台重取）；刷新回显：上次看的那个
  // 检测工程按服务端真源读回来（清单内容与勾选态都回来）
  loadMyDevices();
  const last = readStored(HWCHECK_LAST_DIR_KEY);
  if (last) restoreHwcheckProject(last);
  loadHwcheckRecent();
}
