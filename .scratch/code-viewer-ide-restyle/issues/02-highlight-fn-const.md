# 02 — C 高亮补函数名与宏常量细类（.tok-fn / .tok-const）

**要做什么：** C 源码高亮从 5 类扩到 7 类：标识符后跟 `(`（非关键字）→
.tok-fn（函数名，Dark+ 式淡黄）；全大写标识符 → .tok-const（宏常量，Dark+ 式
紫）；`#define NAME …` 行内 NAME 段拆出 tok-const（其余预处理行 #include /
#pragma / 条件编译仍整行 tok-pre）。函数名/宏常量在生成工程（TI 风格，大量
GPIO_PORT_x、#define）里极常见，这是与 CCS 视觉拉齐的关键一环；新 class 经
highlightCodeLines 跨行 stack 机制天然兼容，无需改查看器渲染件。

**被谁阻塞：** 无——可立即开始（与 01 独立；建议 01 后做便于整屏验收）。

**状态：** resolved

- [x] cHighlight：`foo(` / `int foo(void)` → tok-fn；关键字后 `(` 仍 tok-kw；
      `foo (`（空白容忍）仍 tok-fn，非函数标识符（空格后非 `(`）不着色
- [x] cHighlight：`GPIO_PIN_0`、`LED_GPIO` 全大写 → tok-const（含下划线判定）；
      无下划线的全大写短词（如 `A`）不误染
- [x] `#define LED_GPIO 2` → NAME tok-const、其余 tok-pre；`#include` 行仍整行
      tok-pre（既有用例不破）
- [x] :root / light 各加 --tok-fn（#dcdcaa / #953800）、--tok-const（#c586c0 /
      #6639ba），挂 --tok-* 族
- [x] tests/js 新用例全绿（现 code-highlight.test.mjs 既有用例零改动通过）
- [x] 全量 node --test 绿；深/亮截图确认新颜色可读、不冲突既有 tok 色
      （计算色已验证：深 rgb(220,220,170)/rgb(197,134,192)，亮
      rgb(149,56,0)/rgb(102,57,186)）
