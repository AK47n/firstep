# 01 — PDF 内嵌图自动转码：BMP / JPEG2000 → PNG（Pillow）

**Status:** resolved

**What to build:** `pdf_image_notes` 对 DeepSeek 不支持的嵌入图格式（BMP / JPEG2000 / 未知后缀）在发送前用 Pillow 转 PNG，替换 vision-deepseek-native/01 的「BMP 发送前跳过」行为；`pyproject.toml` 加 `pillow>=11`；PIL lazy import + 全异常兜底（未装 pillow 老环境退化为跳过，不崩启动）。spec：`.scratch/vision-format-transcode/spec.md`（用户已确认根治方案）。

**Definition of done:**
- [x] 红证先行：改 BMP 测试（跳过→转码发送）+ 新增 JPEG2000 转码测试 + 新增转码失败降级测试 → 前两个跑红
- [x] pyproject.toml dependencies 加 pillow
- [x] extraction.py 新增 `_transcode_to_png(data) -> bytes | None`（lazy import PIL，异常 → None）
- [x] pdf_image_notes 接线：后缀 ∉ {.jpg,.jpeg,.png,.gif,.webp} → 转码成功用 PNG 字节 + image/png 发送，失败 skipped；mime 与相关注释同步更新
- [x] 全量 pytest（2123+ 绿）+ `mypy src` 干净
- [x] code-review 双轴评审通过；Comments 写证据；Status 改 resolved

## 背景

- 赛题库实测（pdf_image_scan.py）：长 PDF 472 图 = JPEG 230 + PNG 230 + **JPEG2000 12**（约 2.5%，DeepSeek 不支持）；用户可上传任意 PDF（BMP 可能出现）。
- 现状：`extraction.py:162-166` BMP 发送前跳过；`.jp2` 走 `_image_mime` 未知后缀兜底 `image/png` 直发 → 服务端按 PNG 解码必失败 → 单张静默跳过。切智谱 GLM 救不了 JPEG2000（格式转换问题，非服务商问题）——用户确认根治方案：自动转格式。
- `_join_notes` 已有 skipped 尾部标注（「另有 N 张图跳过：超大或描述失败」），转码失败复用，不新增文案。
- 测试体系：假件 `_FakeImage(data, name)` / `_FakePage(images)` / `_FakeReader(pages)` + monkeypatch（tests/test_extraction.py:149-179）；BMP 测试现为 `testpdf_image_notes_skips_bmp_embedded_images`（L244-260，断言 BMP 未发出）。

## 测试决策

红证先行（BMP 行为变更 + JPEG2000 新路径），假件体系无需真实 PDF；JPEG2000 生成用 PIL（环境无 OpenJPEG 时 pytest.skip 防脆）；全量 pytest + `mypy src` 收尾。

## Comments

**2026-08-21 实施**

### 红证闭环

- 改 BMP 测试（跳过→转码发送）：旧实现 BMP 直接跳过 → calls 少一条 → **红**
- 新增 JPEG2000 转码测试：旧实现兜底直发原 JP2 字节 + image/png → PIL 还原 `format == 'JPEG2000'` ≠ 'PNG' → **红**
- 降级测试（垃圾字节 + .bmp → 跳过计尾部标注）：旧实现即绿（保护新路径）

### 改动（3 文件）

- `pyproject.toml`：dependencies 加 `pillow>=11`（注释标注工单归属）。
- `extraction.py`：
  - 新增 `_VISION_PASSTHROUGH_SUFFIXES = frozenset({".jpg",".jpeg",".png",".gif",".webp"})`（DeepSeek 直发集）+ 注释更新（.bmp 条目保留原因 = PDF 结构兼容 + 转码语义）。
  - 新增 `_needs_transcode(name) -> bool`：后缀 ∉ 直发集 → 需转码。
  - 新增 `_transcode_to_png(data) -> bytes | None`：`Image.open(io.BytesIO(data))` → `convert("RGB")` → PNG 字节；**PIL lazy import**（函数内），任何异常 → None（老环境未装 pillow 退化为跳过，不崩启动）。
  - `pdf_image_notes` 接线：替换「.bmp 发送前跳过」（vision-deepseek-native/01 行为）→ `_needs_transcode` 时转码，成功以 PNG 字节 + `image/png` 发送，失败 `skipped += 1`（复用 `_join_notes` 尾部标注，不新增文案）。
- `tests/test_extraction.py`：改 1（`testpdf_image_notes_transcodes_bmp_embedded_images`）+ 新增 2（JPEG2000 转码 / 解码失败降级）；`_pil_image_bytes(fmt)` helper（PIL 现场生成）；JPEG2000 生成失败 → pytest.skip 防脆。

### 测试与静态检查

- 全量 pytest：**2125 passed**（105.47s；原 2123 − 1 改 + 2 新 = 2125；3 个既有 SyntaxWarning 与本次无关）
- `mypy src`：Success，57 文件无问题

### 评审（双轴 code-review）

- **Standards 轴：无硬违规**（语言规范 / 中文注释全过）。判断项 4 项全落实：① `Path(name or "").suffix.lower()` 两处重复 → 抽 `_image_suffix` helper；② `import io` 懒加载无谓 → 移模块顶层（PIL 仍 lazy）；③ 注释失真（未知后缀「png 兜底」在 pdf_image_notes 路径不可达）→ 注释改写说明 .bmp 条目保留原因与直发/转码判定关系；④ BMP/JPEG2000 两测试脚手架重复 → `pytest.mark.parametrize` 合并。
- **Spec 轴：主体正确、DoD 代码项全满足**。建议项全落实：① JPEG2000 skip 判定过宽（捕获生成异常=假绿）→ 改用 `"JPEG2000" in Image.registered_extensions().values()` 精确预判；② 全跳过边界未覆盖 → 新增 `testpdf_image_notes_all_images_undecodable_returns_empty`（`_join_notes` 空 notes → "" 的既有语义文档化）；③ 评审范围外文档（revise-deepen/04、05）提交时排除。

### 真机验证（真实赛题长 PDF，用户授权）

- **离线转码**（verify_transcode_real_pdf.py，零额度）：261 页长 PDF 全部 472 图格式分布复现（jpg 230 + png 230 + jp2 12）；**12/12 JPEG2000 转 PNG 成功**（p37-p159，450KB→220KB 等，PIL 逐一验证 format=PNG）。
- **真实视觉**（verify_vision_real_jp2.py，DeepSeek 官方端点 + 用户主 key，12 次调用 ≈ 5K token 几分钱）：**12/12 识别成功 0 失败**——p37 功率放大电路、p39 场地 500×400cm、p141 场地 80×70cm 圆角 R10、p145 CC3200 WiFi 双终端、p148 尺寸标注 125/150cm 等，描述质量正常。主 key 只读不打印、未改任何配置。
- **真实流程边界**：p142 图 4.82MB > MAX_IMAGE_BYTES（4MB）→ pdf_image_notes 既有守卫会「超大跳过」（验证脚本绕过守卫直调，故也识别成功）；其余 11 张均进图注。

### 最终回归

- 评审落实后：`tests/test_extraction.py` 31 passed（parametrize 2 用例 + 降级 + 全跳过边界）；`mypy src` 57 文件干净；全量 pytest（待收尾确认）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
