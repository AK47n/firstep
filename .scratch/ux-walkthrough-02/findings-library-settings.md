# 走查发现：库管理与设置（子代理 c032f83e 报告，只读）

范围：模块库 / 赛题库 / 参考文件库 / PDF 资料库 / 母版库 + 设置页（AI API、库目录、工具链、环境体检）+ 新手指引 + 更新记录。未改文件。

总体：管理页骨架高度一致（lib-toolbar + chips + lib-stats + empty-state）；痛点集中在录入/编辑绕路、设置首配信息架构、体检与表单言行不一、搜索覆盖、删除/恢复路径。

## 一、录入/编辑流程
1. 【P1】录入模块/参考条目跨 3 折叠区：模块「② 平台版本与源文件」「③ 进阶能力」默认折叠，提交按钮在 3 区外底部（index.html:2589 add-sec-basic 无 collapsed / 2604 add-sec-files collapsed / 2620 add-sec-adv collapsed / 2636 #btn-add-module-submit 区外 / 2631 #btn-draft-desc 在③内）。参考：入库按钮只在③（index.html:2732 #btn-ref-add），①标题②素材锚定简介在展开区；AI 草稿按钮(#btn-ref-draft-desc 2711)与简介框(#ref-desc 2701)不同区、反馈(#ref-draft-msg 2713)散在②。修法：草稿按钮挪到简介输入框同行；提交按钮贴近最后一区；参考 3 区默认全展开或顶部常驻 primary。
2. 【P1】参考条目「改文件内容」强制两步（先删再存）：ui/reference.js:245 弹窗提示原文「支持增，不支持改内容——替换请先勾删保存，再回来添加」；doSave 323-359（勾删 data-edit-rm + 新增 collectFiles(newfilesBox) 一次 PUT）无「同名覆盖」路径。修法：doSave 对「新增名与现有重名」自动视为覆盖，一次 PUT。
3. 【P2】模块编辑弹窗两套保存语义：ui/library.js:233-235 两个 primary 「保存身份」(299-323 doSaveIdentity → PUT /platform-identity)与「推送新文件」(324-350 doPushFiles → POST /platform-files)。修法：合并为一个「保存」或推送改次级+未推送红色计数角标。

## 二、设置页信息架构
4. 【P1】「保存设置」在页面最底部（index.html:3102 #btn-save-settings、3107 #settings-msg；ui/settings.js:336-372），成功提示仅在底部文本。修法：sticky 保存条 或 「AI API」卡内独立「保存并连接」；成功提示改 toast。
5. 【P2】库目录卡只有模块库 (#set-lib-dir) 与母版库 (#set-masters-dir)（index.html:2974-2981）；赛题/参考/PDF 目录从模块库目录派生（webapp.py:528-529 topic_library_dir/reference_library_dir、4290/4305 materials_dir），改模块库目录时静默联动，无提示无体检。修法：列出 5 个目录只读展示派生值+说明，或切换时确认弹窗；体检加 topic/ref/pdf 目录存在性检查。
6. 【P1】体检与工具链卡言行不一：fx/env.js:49-62 tcMeta 只 stm32=Keil UV4 / mspm0=gmake（miss 文案只 uv4_path/gmake_path）；设置卡 index.html:2990-3008 给 MSPM0 暴露 CCS 三件套（SDK/编译器/SysConfig）+ DSLite；webapp.py:1022-1023 /api/env/status 只 find_uv4+find_make。叫法混乱：体检「gmake（mspm0）」vs 设置卡「CCS 三件套」vs 新手指引 fx/guide.js:280,341,344「MSPM0 装 CCS（gmake 工具链）」。修法：体检补 CCS 编译器/SysConfig 检查并逐行列出 3 字段；统一叫法「Keil UV4（stm32）/ CCS+MSPM0 SDK（mspm0）」。
7. 【P2】体检失败行只有文字（fx/env.js:10-32 envRowHTML/envChannelHTML、50-51/60 miss 文案纯字符串），无跳转；ui/nav-jump.js gotoSettingsKey 只聚焦 #set-api-key。修法：envRowHTML detail 嵌 data-jump → gotoNavTab("settings") + expandSettingsCollapse("toolchain") + focus 对应输入框（ui/settings.js 已有 expandSettingsCollapse 可复用）。

## 三、检索与发现性
8. 【P2】参考库默认按标题升序（ui/reference.js:31 refUI.sortBy="title"；index.html:2653-2655），pdf 默认按名（ui/pdf.js:166 pdfUI.sortBy="name"）；154 条混大量未锚定/旧资料。修法：默认改「最近更新」降序（mtime）。

## 四、删除/恢复路径
9. 【P1】PDF 库只能删「疑似重复」文件：fx/pdf.js:166 行渲染 `${dup ? '<button … data-pdf-trash …>删除</button>' : ""}`；fx/pdf.js:202 详情 `${flags.dup ? '…data-pdf-delete…' : ""}`；ui/pdf.js:104 openPdfTrashConfirm 仅 dup 触发。普通健康 PDF 无删除入口，只能磁盘删。修法：非重复 PDF 也提供回收删除（复用 .trash-pdf 回收目录+git 忽略+可恢复）；被参考条目引用的在确认框说明。
10. 【P2】删除确认形态不统一：模块 ui/library.js:392 / 赛题 ui/topic.js:308 / 参考 ui/reference.js:200 用共享 confirmModal；PDF ui/pdf.js:104 openPdfTrashConfirm / 母版 ui/master.js:392 openMasterDeleteConfirm 用自建 overlay。修法：统一走 confirmModal。

## 五、加载态/错误态
11. 【P2】部分库读取失败残留「正在读取」占位：ui/topic.js:296-305 loadTopics catch 只设 topic-browse-msg，grid 仍加载 spinner；ui/pdf.js:248-256 loadPdfs catch 只设 pdf-msg 未清 pdf-rows 占位；对比 ui/library.js:141-144、ui/reference.js:193-197 失败清空占位。修法：对齐，失败清占位或渲染「读取失败，请刷新」。
12. 【P2】赛题库加载 spinner 整块网格（ui/topic.js:84-89 topicLoading、294-301 fetch 前渲染加载态），本地 API 极快导致闪烁。修法：延迟 ~150ms 再显示加载占位。

## 六、新手指引一致性
13. 【P2】指南与真实按钮基本一一对应（全部真实存在）；小出入：fx/guide.js:82「网页右上角『设置』」但设置按钮在顶部居中导航（index.html:1985 data-tab="settings"）；「MSPM0 装 CCS（gmake 工具链）」与设置卡「CCS 三件套」叫法不一致。修法：右上角→顶部导航；统一叫法。

## 七、跨库一致性
14. 【P3】母版库无搜索/排序/清空/chips/统计（index.html:2866-2878），仅「直接导入替换」；≤2 行故非大痛点。可选加刷新/健康说明。

## 只做 5 件事排序
1. 设置页保存设置 sticky/toast（痛点4）——新手指引第0步必经，改动小收益大。
2. 体检与工具链卡言行一致（6+7）——CCS 三件套入体检+统一叫法+未就绪项跳转。
3. 录入/编辑绕路（1+2）——AI 草稿按钮同行+提交贴末区；参考改文件一次 PUT 覆盖。
4. PDF 库删除任意单份（9）——复用 .trash-pdf 可恢复，几乎零成本。
5. 模块编辑弹窗合并保存语义（3）——避免「点了保存却没存文件」误解。

（共同点：都与首次使用/第一次做完一道题的关键路径相关；小改动、纯前端为主。）
