# 配方撰写说明（工单 module-hwcheck/09 用；给写配方的人/代理读）

> 这份是**工作说明**，不是交付物。目标是给 pilot 清单里还没有配方的模块写出
> `library/hwcheck_recipes.json` 的一条条目，并通过校验器。

## 这是什么

检测程序（学生烧进板子上的 `main.c`）由两半拼成：**框架**（LED 心跳 / 输出通道 /
逐件小节的位置 / 结尾汇总）由 `src/contest_generator/hwcheck.py` 确定性渲染；
**「每一件怎么测」**来自库根的数据文件 `library/hwcheck_recipes.json`
（键 = `slug → platform → 配方`）。配方是**数据**，不是 C 代码；里面的调用写成
C 表达式字符串，渲染器把它们摆进小节函数并做转义。

配方的段（都能缺省，缺 = 这一件不做这项）：

| 段 | 形状 | 含义 |
|---|---|---|
| `include` | `{"headers": ["x.h"]}` | 这一节的调用要 include 的头（**器件模块的头必须写**，框架只 include 通道与心跳那几个） |
| `locals` | `{"declarations": ["float pitch = 0"]}` | 这一节自己要声明的局部变量（只认 `类型 名字 [= 数字]` 形） |
| `prereq` | `{"calls": ["I2C_Init()"]}` | 前置调用（跨模块的头也走 `include`） |
| `init` | `{"calls": [...], "expect": "0"}` | 初始化调用；`expect` 非空 = 板上判 OK/FAIL（拿最后一次调用的返回值比） |
| `probe` | `{"calls": [...], "expect": "0x68"}` | **自证通信**的探头：不信 `init` 的返回值，自己读一次寄存器/ID 再比 |
| `read` | `{"expressions": [{"expression": "MPU6050_GetData()", "unit": "°"}]}` | 要回显的**整数**读数（渲染成 `hwcheck_report_int`） |
| `console` | `{"command": "k", "description": "…"}` | 串口命令台的**单字符**命令 + 一句中文说明 |
| `note` | `{"lines": ["…"]}` | 平台差异说明（直接印到检测页，也进 prompt 语境） |

`init` / `probe` / `read` 的字符串里可以写中文，渲染器会把非 ASCII 转义成八进制
（ARMCC 按本地代码页解析源文件，直接写中文会吞引号——这是既有的真机判例）。

## 硬规则（违反 = 构建期大声失败，进程会点名 slug / 平台 / 段 / 名字）

1. **每一个被引用的函数名必须真的存在于「该模块该平台的头文件」或「母版工程树的
   头文件」里**（两者的函数联集就是白名单）。判据与生成门禁同一套
   （`skeleton.format_interface_blocks`）；写错一个字母就不会通过。
2. `console.command` 必须是**单字符**，且不能是 `r` / `y` / `g` / `o` / `b` / `?`
   （库内既有命令与帮助字符，既有行为一个字节都不许动），也不能与其他配方的命令
   重复。**本期分配**（别改别的件已用的字符）：
   - `debug_uart` = `u`，`key` = `k`，`beep` = `p`，`sr04` = `s`，
     `jy61p` = `j`，`xunji` = `x`，`adc` = `a`
   - 已占用：`led` = `l`、`oled` = `d`、`ml_mpu6050` = `m`
3. `read.expressions` 的表达式必须是**整数**（常量或返回 `int` 的调用）：读数经
   `hwcheck_report_int` 回显，浮点/字符串过不了。想显示小数（如角度）要像
   `ml_mpu6050` 那条一样**拆整数位**（见既有配方）。
4. **不猜读函数**：如果这件没有"能读回来的东西"，就不要 `read` 段，也不要编造
   一个函数（编造 = 校验器当场红）。
5. 板端判定**只有两层能给结论**：`init.expect` 与 `probe.expect`（比返回值）。
   读数只回显 + 给正常范围参考，**不在板上做阈值判决**。
6. `note.lines` 写清**平台差异**与**这一趟到底证明了什么、没证明什么**（例：
   `led_init()` 是 `void` → 没有可读状态 → 板上判不了通断，只能靠眼睛看）。

## 写法参考（照既有三件的样子写）

先读 `library/hwcheck_recipes.json` 里 `led` / `oled` / `ml_mpu6050` 三条
（它们是本期的样板：说明怎么写、探头怎么设、平台差异怎么讲），再读你要写的那个
模块的双平台头文件（`library/modules/<slug>/`）：**只写头文件里真实存在的函数**。

## 怎么自检

1. 把你写的那一条（只含你负责的 slug）存成临时文件，例如
   `.scratch/module-hwcheck/drafts/<slug>.json`，形状 = 顶层就是 `{"<slug>": {"stm32": {...}, "mspm0": {...}}}`；
2. 跑校验器（在仓库根）：

```powershell
python .scratch\module-hwcheck\validate-recipes.py --recipe .scratch\module-hwcheck\drafts\<slug>.json --cell <slug>:stm32 --cell <slug>:mspm0
```

   - `OK …` 一行 = 这一格过了（会印出命令字符 / 有没有探头 / 读数条数）；
   - 抛 `HwCheckError` = 引用校验没过（**读那句中文报错，它会点名哪一段哪个名字**）；
   - `判红：` 列表 = 空格子或渲染不出小节。
3. 单平台件（`sr04` / `jy61p` / `xunji` 只有 mspm0 条目）只校验有条目的那一格。

## 交付

1. 通过校验的 **JSON 片段**（顶层 `{"<slug>": {...}}`，UTF-8，缩进 1 空格或 2 空格都行）；
2. JSON 片段里每个 `expect` / 命令字符的**依据一行**（例如"WHO_AM_I 是 0x68，见
   `<头文件>` 第 N 行"或"这个函数返回 0 = 成功，见驱动实现"）；
3. 你**没写**什么、为什么（例：这件没有可读状态 → 无 `read`；本平台没有条目 →
   只有一格）。**不确定就别写**——宁可少一段，也不要编一个函数名。
