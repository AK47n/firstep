#!/bin/sh
# 从**每个历史提交**里删掉"工具生成的产物"（照 scripts/purge-generated.list）。
#
# 用法（仓库根目录）：
#   FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f \
#     --index-filter 'sh /绝对/路径/scripts/purge-generated.sh' --prune-empty -- --all
#
# ⚠ 两个"必须"（都踩过）：
#   ① 调用时**必须用绝对路径**。index-filter 是在临时目录里跑的（GIT_DIR 指过去），
#      写相对路径 `sh scripts/…` 会报 "No such file or directory" ——
#      而那个报错看起来像"脚本不存在"，会让人去改文件名。
#   ② 脚本里**不能靠 cwd 找文件**，要用脚本自己的位置推。
#      否则又会找不到 purge-generated.list，报错看着像"清单没生成"。
#
# ── 为什么用 index-filter 而不是 tree-filter ──
# tree-filter 会把每个提交 checkout 到磁盘再改（这里 2830 个提交、300MB，几小时）；
# index-filter 只在**索引**上操作，不碰工作区，快一个数量级。
#
# ── 为什么读清单而不是在脚本里写正则 ──
# ① 这个脚本对每个提交跑一次，在里面再"列文件 + 正则筛"会慢一个数量级；
# ② 那种写法要用 sh 的 tr/egrep，而这台机器上只有 git 自带的那套 Unix 工具，
#    PowerShell 里跑不了 —— 没法先干跑一遍看看会删什么；
# ③ 最要紧的是：**清单必须先被人看过**。删错一个文件不可逆。
# 清单由 scripts/make-purge-list.mjs 生成，它带一道"命中里有真源码就报警"的闸。
#
# ── 为什么必须 -f ──
# 后面那些提交里本来就没有这些文件，不加 -f 会因为"没有匹配"而报错退出。

# 从脚本位置推仓库根（脚本在 <repo>/scripts/ 下）
SELF_DIR=$(cd "$(dirname "$0")" && pwd)
LIST="$SELF_DIR/purge-generated.list"

[ -f "$LIST" ] || { echo "找不到 $LIST —— 先跑 node scripts/make-purge-list.mjs ." >&2; exit 1; }

# 路径里有空格和中文：
#   按行读用 sed 去 CR（Windows 上生成的文件可能是 CRLF）
#   交给 git 时用 xargs -d '\n'，别用默认的按空白切分
sed -e 's/\r$//' -e '/^#/d' -e '/^$/d' "$LIST" | xargs -d '\n' -r git rm --cached -f -q --ignore-unmatch

exit 0
