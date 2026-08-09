# 模块库迁入软件仓库（随软件走）

模块库（modules + masters + topics + references）原住用户主目录 `~/.contest_generator/`，不在任何版本控制下——用户明确担心未来删掉会丢失，且计划把生成器做成（小范围发布的）软件。决策：**整个库迁入 firstep 仓库的 `library/` 目录，git 版本化，随软件分发**；`config.json` 的 `module_library_dir` 键改指向仓库内路径（`topic_library_dir` / `reference_library_dir` 按 config.py 约定跟随同级 `topics/` / `references/`，masters 单独键跟随）。`config.json` 本身（含 DeepSeek API key）留在用户主目录不进 git，仓库内放无 key 示例。

考虑过的替代方案：独立 git 仓库（库与软件版本脱节，发布要跨仓库打包）、原位保留 + 发布时打包（库本身不版本化，防丢目标落空）。git 对 topics 下重复的真题 PDF（7 份同 blob）自动去重，仓库增量约 40M。

**Consequences**: 库生命周期与软件一致（改库 = 改软件提交）；发布时库自然随软件走；工作区体积增大（235M，多数为重复 PDF 的工作区占用）。赛题素材（官方真题 PDF）随软件分发的版权边界未定，留到真正发布时决定。
