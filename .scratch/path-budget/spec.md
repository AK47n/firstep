# spec：完整包「路径太长」根治（工单 path-budget/01）

Status: ready-for-human（实现已完成，待人工验收）

## 现象（用户报障，2026-09-14）

用户在**另一台电脑**下载 `firstep-full-v1.2.0.zip` 后解压，Windows 报：

```
一个意外错误使你无法复制该文件。
错误 0x80010135: 路径太长
touch_screen_calibration.ino（类型: INO 文件, 10.8 KB）
```

对话框给「重试 / 跳过 / 取消」——**点「跳过」不会中止，只会静默丢掉这个文件**，
用户以为解压成功了。

## 根因（实测口径）

| 判据 | 实测 |
|---|---|
| 包内最深相对路径 | **223 字符**（`sources/materials/lckfb-地阔星移植手册/网盘下载/ili9488/…/touch_screen_calibration/touch_screen_calibration/touch_screen_calibration.ino`） |
| 资源管理器「全部解压缩」上限 | **259 字符**（含解压根目录；老 API，`0x80010135`） |
| 工具自身解压（Python `zipfile`） | 实测写到 **290+ 字符仍成功**（走长路径 API） |
| `tar.exe`（bsdtar 3.8.8） | 实测 267 字符完整落地，退出码 0 |
| 非资料库内容最长路径 | 137 字符（**病灶全在资料库**） |
| 超 200 字符的文件 | 22 个（原 26 个含 4 个在 `1-Demo` 下的计数口径差异），**100% 集中在两族 LCD 厂商例程** |

**一句话**：解压根目录吃掉 `C:\Users\<用户名>\Desktop\…`（20~40 字符），资料库再
贡献 223 字符，两者一加就顶破 259。同一份包「这台机器能解、那台不能」，差别只在
用户名长短与是否多套一层目录——这就是它必然复发的机理。

## 方案（两半，缺一不可）

**① 把路径压回安全区（治已有的病）**

外科手术式改目录名，落在 `lckfb-地阔星移植手册/网盘下载/{ili9341,ili9488}` 两族内：

| 规则 | 含义 | 依据 |
|---|---|---|
| A | 去掉纯序号外壳层 `…/<芯片包>/1-Demo/` → `…/<芯片包>/` | 厂商光盘的「第 1 个示例」目录，无信息量 |
| C | `Demo_Arduino/Install libraries/` → `Demo_Arduino/libs/` | 只是目录名；Arduino 库名是下一层 `LCDWIKI_*`，不受影响 |
| D | 仅在各示例/`Example/` 子树内折叠「相邻同名目录层」（`x/x/` → `x/`） | 厂商拷贝留下的冗余 |

- 效果：最长 **223 → 194 字符**，超上限文件 **22 → 0**；
- 代价：**零**——只改目录名，**不动任何文件名**（`.ino` 草图名与文件名一致是 Arduino
  硬要求）；受影响 2438 个文件，内容 (size, sha256) 多重集逐项不变；
- 全库实测无任何代码/清单引用这些路径（`library/modules/*/manifest.json` 里那两处
  `1-Demo` 命中是散文误报，非路径）。

**② 让以后发不出这种包（治病根）**

`full_pack.prepare_full_package` 扫完树立刻 `ensure_paths_fit(files)`：
任何包内相对路径 > `MAX_ENTRY_PATH_CHARS`(200) 就**拒绝发版**，错误信息给出
「长度 + 路径 + 修法脚本」。以后资料库再进新批次，撞线在发版这一步就被挡下——
用户侧不会再出现「解压悄悄丢文件」。

## 明确不做

- **不放宽判据到 259**：那是资源管理器的上限，不是我们的上限；留 59 字符余量给
  解压根目录（用户名 + 放哪）。
- **不动 `Demo_*` 目录名本身**：那是给人看的语义信息，改它收益小而可读性损失大。
- **不要求用户改注册表 / 装 7-Zip**：治产品，不治用户。
- **不做「解压器」**：多一个要维护的可执行文件；路径压短之后不需要它。

## 验收判据

1. `.scratch/path-budget/slim_materials_paths.py` dry-run → 超限 0、无路径冲突；
2. `--write` 后自校验：文件数不变、(size, sha256) 多重集逐项相等；
3. `pytest tests/test_full_pack.py -k "overlong or ceiling or real_tree or materials_paths"` 全绿；
4. 真仓库 `scan_tree` 最长路径 ≤ 200（实测 194）；
5. 用**同一台用户名偏长的机器**（`C:\Users\Admin…\Desktop\firstep` 口径）复算：
   最深总长 ≤ 233，资源管理器不再报 0x80010135。

## 即时解药（老包，用户手上已有）

老包（≤ v1.2.0）不变，那台机器这样解**不丢文件**：

```powershell
mkdir C:\firstep
tar -xf "$env:USERPROFILE\Downloads\firstep-full-v1.2.0.zip" -C C:\firstep
```

`tar.exe` 是 Windows 10/11 自带；长路径一步到位（实测 267 字符落地成功）。
