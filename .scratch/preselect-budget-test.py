def test_recommend_real_library_budget():
    """真实库预算回归（工单 module-preselect/02）：扫仓库真实模块库
    （library/modules）构造 mspm0 / stm32 两平台最坏形态 select 载荷——
    题面 4000 中文（零命中形态 = 预筛退化 slug 序截断，覆盖最坏截断面）+
    预筛后真实摘要 + 真实词表 + 20 条长澄清历史 + 15 条相关候选 + 满额参考
    全文——完整 payload json.dumps 序列化 ≤ MAX_REQUEST_BYTES 且余量 ≥ 2KB。

    模块库每增一个模块（摘要行变长 / 条数变多）此测试即红——照词表段
    test_wordlist_segment 的红证先例，防「固定 14 条假摘要样例」假绿掩盖
    真实库增长（预算推导按 14 条 ≈ 7.6KB 记账，批次 13 后 mspm0 84 条
    ≈ 73KB wire，未修复形态实测 195000B > 131072）。改 MODULE_SUMMARY_BYTES /
    REFERENCE_FULLTEXT_BYTES 必须先红证校准再改断言（照 budget.py 词表段
    先例：每涨必红、保 2KB 边界余量）。
    """
    from contest_generator.budget import MODULE_SUMMARY_BYTES
    from contest_generator.library import list_modules
    from contest_generator.selection import (
        filter_manifests_by_platform,
        preselect_module_summaries,
    )
    from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

    lib = Path(__file__).resolve().parents[1] / "library" / "modules"
    modules = list_modules(lib)
    problem = "设" * EMBEDDED_CONTENT_CAP  # 题面截断上限（零命中最坏形态）
    clarifications = tuple((f"第{i}问：" + "疑" * 200, "答" * 5000) for i in range(20))
    references = [
        _suggestion(
            f"关联例程{i:02d}", f"TI 外设例程 {i:02d}", "TI MSPM0 SDK 官方例程" * 8,
            source=REFERENCE_SOURCE_RELATED,
        )
        for i in range(15)
    ] + [_suggestion("big-ref", "大参考文件", "巨型参考")]
    for platform in (PLATFORM_MSPM0, PLATFORM_STM32):
        filtered = filter_manifests_by_platform(modules, platform)
        summaries = build_manifest_summaries(filtered)
        presel = preselect_module_summaries(
            summaries, problem, DEFAULT_WORDLIST, MODULE_SUMMARY_BYTES
        )
        prompt = _selection_user_prompt(
            problem,
            presel.summaries,
            references=references,
            reference_fulltexts={"big-ref": "中" * REFERENCE_FULLTEXT_BYTES},
            clarifications=clarifications,
            hardware_words=DEFAULT_WORDLIST,
        )
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SELECT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        total = len(json.dumps(payload).encode("utf-8"))
        assert total <= MAX_REQUEST_BYTES - 2 * 1024, (
            f"{platform} 真实库最坏形态 {total}B > "
            f"{MAX_REQUEST_BYTES - 2 * 1024}（预算 {MODULE_SUMMARY_BYTES}，"
            f"摘要 {presel.total} 条预筛后 {len(presel.summaries)} 条）"
        )
