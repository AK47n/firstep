# -*- coding: utf-8 -*-
# A 级探针（只读原库，全部动作在硬链接克隆里做）
# 目的：给出「只从历史删 sources/materials/」到底省多少 MB 的真实数字。
# 全部 git 调用带 -C 绝对路径，不依赖 cwd。

$ErrorActionPreference = 'Continue'
$REPO  = 'C:\Users\luoji\Desktop\firstep'
$WORK  = Join-Path $env:TEMP 'sm-probeA'
$OUT   = 'C:\Users\luoji\Desktop\firstep\.scratch\materials-history-purge'

function Step($m) { Write-Host "=== $m ===" }

if (Test-Path $WORK) { Remove-Item $WORK -Recurse -Force -ErrorAction SilentlyContinue }

Step "① 硬链接克隆原库到 $WORK"
& git clone --quiet $REPO $WORK 2>&1 | Select-Object -Last 2
if (-not (Test-Path (Join-Path $WORK '.git'))) { throw "clone 失败" }
& git -C $WORK config core.longpaths true
$c1 = (Get-ChildItem (Join-Path $WORK '.git') -Recurse -Force -File | Measure-Object Length -Sum)
Write-Host ("基线(未repack) .git = {0:N1} MB / {1} 文件" -f ($c1.Sum/1MB), $c1.Count)

Step "② 基线 repack（不删任何历史）"
& git -C $WORK gc --prune=now --quiet 2>&1 | Select-Object -Last 2
$c2 = (Get-ChildItem (Join-Path $WORK '.git') -Recurse -Force -File | Measure-Object Length -Sum)
Write-Host ("基线(repack后) .git = {0:N1} MB" -f ($c2.Sum/1MB))
$baseOdb = (git -C $WORK cat-file --batch-check='%(objectname)' --batch-all-objects | Measure-Object).Count
$baseCommits = git -C $WORK rev-list --all --count
$baseSrc   = (git -C $WORK ls-tree -r HEAD --name-only -- src   | Measure-Object).Count
$baseTests = (git -C $WORK ls-tree -r HEAD --name-only -- tests | Measure-Object).Count
Write-Host "基线: commits=$baseCommits odb=$baseOdb src=$baseSrc tests=$baseTests"

Step "③ A 级：filter-branch --index-filter 删 sources/materials/"
$env:FILTER_BRANCH_SQUELCH_WARNING = '1'
$t0 = Get-Date
& git -C $WORK filter-branch --force --index-filter "git rm -r --cached --ignore-unmatch -- sources/materials/" --prune-empty --tag-name-filter cat -- --all 2>&1 | Select-Object -Last 4
Write-Host ("filter-branch 耗时 {0:N0} 秒" -f ((Get-Date)-$t0).TotalSeconds)

Step "④ 清 refs/original + reflog，然后 repack"
& git -C $WORK for-each-ref --format='%(refname)' refs/original/ | ForEach-Object { & git -C $WORK update-ref -d $_ }
& git -C $WORK reflog expire --expire=now --all 2>&1 | Select-Object -Last 2
& git -C $WORK gc --prune=now --aggressive --quiet 2>&1 | Select-Object -Last 2

$c3 = (Get-ChildItem (Join-Path $WORK '.git') -Recurse -Force -File | Measure-Object Length -Sum)
$afterOdb = (git -C $WORK cat-file --batch-check='%(objectname)' --batch-all-objects | Measure-Object).Count
$afterCommits = git -C $WORK rev-list --all --count
$afterSrc   = (git -C $WORK ls-tree -r HEAD --name-only -- src   | Measure-Object).Count
$afterTests = (git -C $WORK ls-tree -r HEAD --name-only -- tests | Measure-Object).Count

Write-Host ""
Write-Host "########## A 级结果 ##########"
Write-Host ("基线 .git (repack 后)   : {0,8:N1} MB   odb={1}  commits={2}" -f ($c2.Sum/1MB), $baseOdb, $baseCommits)
Write-Host ("A 级 .git               : {0,8:N1} MB   odb={1}  commits={2}" -f ($c3.Sum/1MB), $afterOdb, $afterCommits)
Write-Host ("A 级净省（vs repack）   : {0,8:N1} MB" -f (($c2.Sum-$c3.Sum)/1MB))
Write-Host ("A 级净省（vs 现状 .git）: {0,8:N1} MB" -f (($c1.Sum-$c3.Sum)/1MB))
Write-Host ("src  {0} -> {1}   tests {2} -> {3}   (必须相等)" -f $baseSrc,$afterSrc,$baseTests,$afterTests)
Get-ChildItem (Join-Path $WORK '.git\objects\pack') -File -Filter *.pack | ForEach-Object { Write-Host ("   pack {0} {1:N1} MB" -f $_.Name.Substring(5,8), ($_.Length/1MB)) }
& git -C $WORK rev-list --objects --all > (Join-Path $OUT 'probe-A-after-revlist.txt')
Write-Host "A 级后 rev-list 已导出"
