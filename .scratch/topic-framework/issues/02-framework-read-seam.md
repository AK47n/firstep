# 02 — 题型框架读取缝（build_topic_framework）

**要做什么：** 新增纯函数 `reference_library.build_topic_framework(reference_root: Path, entry: ReferenceEntry) -> str | None`：读条目目录下约定文件 `framework/main.c`（**控制文件**——与 `reference.json` 同阶：不入 `files` 清单、`read_fulltext` 不读它，避免与断言注入段重复；`entry_stats` / `list_entry_files` 磁盘实况口径照旧统计）；`topic_type` 空 → None；文件缺失 / 不可读（OSError / UnicodeDecodeError）→ None（降级不抛——框架是增强不是闸门）；成功 = 返回文件全文（utf-8）。另加常量 `REFERENCE_FRAMEWORK_FILENAME = "framework/main.c"`。

**被谁阻塞：** 01（依赖 topic_type 字段定义）。

**状态：** resolved

**验收：** 全部 ✓（`REFERENCE_FRAMEWORK_FILENAME = "framework/main.c"` 常量 + `build_topic_framework` 四态测试：topic_type 空 / 文件缺失 / 正常 / 非 UTF-8；读全文隔离断言 + entry_stats 计 framework 目录）。

- [x] `REFERENCE_FRAMEWORK_FILENAME` 常量（单源：`"framework/main.c"`）
- [x] `build_topic_framework(reference_root, entry)`：topic_type 空 → None；`reference_root / entry.id / framework/main.c` 缺失 → None；read_text utf-8 失败（OSError / UnicodeDecodeError）→ None；成功 → 全文
- [x] 文档化：`framework/main.c` 语义 = 该条目的题型确定性框架段（prompt 注入用），非普通素材（不进 reference.json files、不进 read_fulltext）
- [x] 测试：topic_type 空 / 文件缺失 / 正常读取 / 非 UTF-8（None）四态；`read_fulltext` 不包含 framework 内容（控制文件隔离断言）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
