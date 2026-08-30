# firstep · 电赛工程生成器

贴一段赛题原文，自动生成一个**打开就能编译、直接开写**的完整工程（MSPM0G3507 / CCS 与 STM32F103C8T6 / Keil5 双平台）。

## 获取方式（二选一）

| 方式 | 内容包括 | 备注 |
| --- | --- | --- |
| **GitHub 克隆**（轻量，约 270 MB） | 生成器代码 + 模块库/母版库（`library/`）、文档 | `git clone https://github.com/AK47n/firstep.git` |
| **完整包**（开箱即用，约 6 GB） | 上述全部 + `sources/materials` 电赛参考资料库（CCS 安装包、开发板手册、K230/视觉资料、真题、参考例程） | 从 [GitHub Releases](https://github.com/AK47n/firstep/releases) 下载 `firstep-full.7z.001~004` 四个分卷，全部下载后解压 `.001` 即可；需 [7-Zip](https://www.7-zip.org/) 或 Bandizip |

> `sources/materials` 资料库内有大量超过 100 MB 的第三方安装包/固件镜像（GitHub 单文件上限 100 MB），**不入 git 仓库**，随完整包（Releases 附件）分发。只想跑工具本身（不用资料库）的话，克隆 GitHub 仓库即可。

## 这是什么

- 一个**本地网页工具**：双击启动，浏览器里操作，数据全部留在本机（`%USERPROFILE%\.contest_generator\`）。
- 生成的内容是**完整工程**：主程序 + 外设驱动 + 引脚映射 + IDE 工程文件（`.uvprojx` / `.cproject`）——用对应 IDE 打开就能编译，改一改就能上板。
- 两条硬件线（先备一款即可，两款同时备也不冲突）：

| 平台 | 板子 | IDE |
| --- | --- | --- |
| stm32 | STM32F103C8T6 最小系统板 | Keil5（MDK-ARM） |
| mspm0 | 地猛星 MSPM0G3507 开发板 | TI CCS（Code Composer Studio） |

- 只有「生成 / 修改工程」这一步需要调用 DeepSeek API（联网），其余操作全部本地完成。

## 开始之前：四样东西

1. **Windows 10/11 电脑**（本工具只支持 Windows）。
2. **Python 3.13 或更新版本**：去 https://www.python.org/downloads/ 下载安装；安装时务必勾选 **Add python.exe to PATH**。
3. **DeepSeek API key**：打开 https://platform.deepseek.com → 注册 / 登录 → 左侧「API keys」→ 创建；生成一次消耗几分钱，建议先充值少量。key 只保存在本机。
4. **至少一套板子 + 对应 IDE**（见上表；首次可只买一块最小系统板 + 装一个 IDE）。

## 三步装好

1. **双击 `install.bat`**：自动创建虚拟环境并安装依赖（需要联网，约几分钟；脚本可重复运行，重复安装不会出错）。
2. **双击 `start-app.vbs`**：后台启动服务，浏览器自动打开 http://127.0.0.1:8000 。
3. **配 key**：网页右上角「设置」→ 粘贴 DeepSeek API key → 点「检查环境」（体检会逐一列出还有什么没就绪；顺便可点「一键补齐」——它按顺序带你补齐缺失步骤，**只带路、不下载文件**）。模块库 / 母版库在首次运行 `install.bat` 时已自动指向工具包里的 `library` 文件夹，正常不用手动设置。

## 然后呢：30 秒上手

首页就是完整流程（12 步向导）：**粘贴赛题 → 选平台 → 生成 → 修改 → 编译 → 上板**。

- 第一次打开可先点顶部「指南 / 新手指引」——从准备、做题主线到编译上板、交付收尾的四章完整教程，随时可回看。
- 主路径看**「任务推进」**页签（按任务卡逐步走，卡上有「和 AI 商量」可以直接问）。
- 改参数用**「参数速调」**；交报告/演示用**「交付」**页签，会给你一份补充在报告里的草稿。
- 生成的工程在**桌面**（目录名形如 `2024H_Auto_Car_STM32`，平台后缀区分）。

## 常见问题

- **双击 `start-app.vbs` 没反应 / 没开浏览器**：先运行 `install.bat` 装依赖；再不行看日志 `%USERPROFILE%\.contest_generator\webapp.log`。
- **提示端口 8000 被占用**：关闭占用该端口的程序后重新双击 `start-app.vbs`（本工具不会自动换端口）。
- **提示未配置 AI**：右上角「设置」填写 API key（key 存在 `%USERPROFILE%\.contest_generator\config.json`）。
- **没装编译工具链 / 想自动编译**：「设置」页填 Keil 的 `uv4_path` 或 `gmake` 工具链路径（「检查环境」会直接提示缺哪一项）。
- **体检提示「模块库 / 母版未就绪」**：「设置」→「库目录」，把两项分别填到工具包根目录（含 `install.bat` 的文件夹，如 `C:\...\firstep`）下的 `library\modules` 与 `library\masters`；赛题库 / 参考文件库自动跟随（`library\topics`、`library\references`，与模块库同级）。
- **想停掉服务**：双击 `stop-firstep.bat`。
