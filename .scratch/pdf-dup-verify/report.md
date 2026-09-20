# PDF 资料库真重复复核与回收（2026-09-20）

**请求**：「PDF资料库里面看看是否真的重复如果是真的重复就删掉」。

**结论先说**：应用标出的 **15 组「疑似重复」全部是真重复**——全量 SHA256 复算**逐字节相同，
0 组假阳性**；已按应用自身的回收语义删掉每组冗余的一份 → **回收 15 个文件 / 10.85 MiB**，
库内 PDF **97 → 82**，且**内容层面零重复**（82 个文件 = 82 种唯一内容）。

## 一、为什么应用说「疑似」、这里能说「真」

| | 判据 | 读了内容吗 |
|---|---|---|
| 应用（`static/js/fx/pdf.js:pdfDupGroups`） | 同名（大小写不敏感）+ 同大小 + 大小 > 0 + 组内 ≥ 2 | **否**（自标「疑似」） |
| 本轮复核（`probe-01-verify.py`） | 对每个疑似组全量 SHA256 + 另做全库内容分组 | 是 |

复算结果：

| 项 | 实测 |
|---|---|
| 疑似组 | 15 |
| **真重复（组内哈希全同）** | **15** |
| 假重复（同名同大小但内容不同） | **0** |
| 全库内容重复组（含「改名重复」） | 15 |
| 应用判据抓不到的改名重复 | **0** |

即：在这份真实库上，应用判据**零漏报、零误报**（与 2026-09-13 那次实测结论一致，
见 `.scratch/library-dedup-audit/report.md` 第七节）。

## 二、这 15 组是什么

两个 lcdwiki 模块包**各自随包带一份同名通用文档**——是原厂打包形态，不是抓取失误：

| 侧 | 路径根 |
|---|---|
| 保留 | `lckfb-地阔星移植手册/网盘下载/ili9341/2.8inch_SPI_Module_ILI9341_MSP2807_V1.1/` |
| 回收 | `lckfb-地阔星移植手册/网盘下载/ili9488/3.5inch_SPI_Module_ILI9488_MSP3520_V1.1/` |

内容 = 通用工具上手图文 **10 份**（Keil / PCtoLCD2002 / C51_Keil&stc-isp / Arduino_IDE /
Image2Lcd，各 CN + EN）+ LCDWIKI Arduino 库文档 **5 份**（GUI / SPI / TOUCH 手册 +
SPI 支持型号表 + Requirements）。**保留 ili9341 侧**的理由：工单
`.scratch/wiki-stm32-batch10/issues/06-module-ili9341.md` 按名记录了该侧
`6-User_Manual/STM32_Keil_Use_Illustration_CN.pdf`；两侧逐字节相同，保留哪侧都不影响可读性。

## 三、删前核查（逐项都跑了）

| 核查 | 结果 |
|---|---|
| 代码引用 | grep `src/` 全部 `*.py` 对 15 个文件名 → **零命中** |
| 参考库引用 | grep `library/`（`*.json` / `*.md`）→ **零命中**（应用中 `pdf_referenced_by` 查的就是这个字段） |
| 文档引用 | 只有工单 06（按名记录**保留侧**，未动）与 `.materials-manifest.json`（发布侧基线，见「遗留」） |
| 「检查资料库更新」会不会误报 | 不会：`materials_update` 只比「本地基线 JSON vs 线上清单」，**不扫盘** |
| 测试 | `python -m pytest tests/test_pdf_library.py tests/test_materials_update.py tests/test_full_pack.py tests/test_lckfb_attribution.py -q` → **89 passed**（资料库相关用例全走 `tmp_path` 夹具，不吃真身状态） |
| 回收目录会不会进包 | 不会：`.trash-pdf` 已在 `full_pack.SKIP_DIR_NAMES` 与 `.gitignore` |

## 四、做法与恢复

- **落点** `sources/.trash-pdf/2026-09-20/<rel_path 镜像>`——与应用「删除」按钮**同一条回收语义**
  （`pdf_library.trash_pdf` 同款：保留批次层级、同日重名加 `_N` 后缀）。`sources/materials`
  **未被 git 跟踪**，真删不可回滚，故不真删。
- **脚本**（可复跑）：`probe-01-verify.py`（只读复核）/ `probe-02-apply.py`
  （**白名单式** 15 组，逐组 SHA256 相同才动手，`--check` 只校验）。已按 `--check` → 执行两步跑完。
- **恢复**：把 `sources/.trash-pdf/2026-09-20/lckfb-地阔星移植手册/` 整段挪回
  `sources/materials/` 即原位（两侧路径镜像）。

## 五、账目

| 项 | 前 | 后 |
|---|---|---|
| PDF 数 | 97 | **82** |
| PDF 合计 | 218.07 MB | **206.70 MB**（十进制 MB；回收 10.85 MiB） |
| 疑似重复组 | 15 | **0** |
| 内容重复组（含改名重复） | 15 | **0** |
| 0 字节损坏件 | 0 | 0 |

## 六、遗留

- **发布侧基线没跟着改**：`.materials-manifest.json` 仍是 12 批次 / 5081 文件（用的是**盘扫描**
  之外的声明清单），所以本机盘自此与线上基线差这 15 条。将来拿**本机盘**扫基线 / 打完整包时，
  `full_pack.scan_as_manifest` / `materials_pack` 会把这 15 条算成 `removed` —— 也就是**下一版
  会把它们从用户库里一并删掉**。想让删除进下一版就这么发；不想就先把回收目录那 15 件挪回原位。
  已记账到 `docs/agents/local-environment.md` 第 6 节。
- **判据仍不建议升级成内容哈希**：本轮再次实测它在真实库上零漏报零误报（内容重复总组数 =
  疑似组数 = 15）；升级只有维护成本、增量 0（成本实测 1.4 s / 208 MB，2026-09-13 测）。
