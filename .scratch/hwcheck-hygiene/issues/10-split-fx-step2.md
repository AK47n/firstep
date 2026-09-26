# 10 — 拆 fx 第二步：迁移消费者、删掉旧文件与再导出

**要做什么：** 把纯函数层的全部消费者改指到新的六个模块，然后**删掉旧文件与那段过渡性的再导出**
——`static/js/fx/hwcheck.js` 这个路径从此不存在。

**被谁阻塞：** **09**（六件新模块 + 搬迁完整性自检先绿）。

**状态：** ready-for-agent

## 现状（实测：旧文件的 fan-in 很小）

| 消费者 | 引用数 | 引的是什么 |
|---|---|---|
| `static/js/ui/hwcheck.js` | 1 条大 import 块（约 90 个名字） | 大部分导出 |
| `tests/js/hwcheck.test.mjs` | 13 处 | 纯函数与渲染产物断言 |
| `static/js/ui/generate-recommend.js` | 2 处 | 衔接相关的名字 |
| `tests/browser/hwcheck.spec.mjs` | 1 处 | 直接引用（若为字符串/注释也要一并改） |

## 验收标准

- [ ] 四个消费者全部改指新模块（`ui/hwcheck.js` 那条大 import 块按新模块拆成若干条，
      并保留既有的行尾注释体裁）。
- [ ] 旧文件与其再导出**删除**；`grep -r "fx/hwcheck.js" static tests` **零命中**
      （`boot.js` 的模块清单若列了它也要一并改）。
- [ ] `window` 桥名字并集在删除前后**完全相等**（每件新模块各自发布自己那一段）——
      页面内联脚本与浏览器探针仍能取到同样的全局名。
- [ ] 搬迁完整性自检切到"搬前快照"那一侧（见 09），仍然绿；**自检不许随旧文件一起删掉**。
- [ ] **反证**：故意漏迁一个消费者的一个名字 → `static-import-guard` 判据④或 `import-usage-guard`
      必须红；复原后逐字节相同（`.scratch/hwcheck-hygiene/probe-10-red.py` / `probe-10-red.txt`）。
- [ ] 读数：全套 pytest + 前端门禁 + 浏览器门禁，三个读数落盘。
- [ ] 本单收口后本文件**没有留下任何过渡态**（barrel、临时快照脚本的去留：快照留档在本目录，
      脚本若只服务 09/10 则移进本目录而不是留在 `tests/js/`）。
