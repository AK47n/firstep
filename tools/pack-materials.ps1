# pack-materials.ps1 — firstep 资料库增量打包脚本（工单 materials-update/02）
# 用法（仓库根）：
#   powershell -File tools\pack-materials.ps1 -Tag v1.1.0 -Mode diff -Baseline <上版清单.json|URL>
#   powershell -File tools\pack-materials.ps1 -Tag v1.1.0 -Mode init
#   powershell -File tools\pack-materials.ps1 -Tag v1.1.0 -Mode full
# 可选：-Tree <资料库目录>（缺省 仓库根\sources\materials） -OutDir <输出目录> -Python <python.exe>
# 产出（缺省 %USERPROFILE%\Desktop\firstep-pack-materials）：
#   firstep-materials-<Tag>.manifest.json          本版全量清单（下一版的 diff 基线）
#   firstep-materials-<Tag>-<slug>.zip[.part<N>]   批次增量 zip（init 模式不产出）
# 依赖：python 在 PATH（或 -Python 指定）；核心逻辑在 src\contest_generator\materials_pack.py。
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [ValidateSet('init', 'full', 'diff')][string]$Mode = 'diff',
    [string]$Baseline,
    [string]$Tree,
    [string]$OutDir = (Join-Path $env:USERPROFILE 'Desktop\firstep-pack-materials'),
    [string]$Python,
    [switch]$AllowDirty
)

$ErrorActionPreference = 'Stop'

# ---------- 1. 定位仓库根（本脚本位于 tools\ 下） ----------
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

# 锁定控制台编码 UTF-8（中文路径输出不乱码；PS 5.1 默认 ANSI(GBK)）
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)

# ---------- 2. Tag 校验（仅防路径注入，不约束版本文法；CLI 侧再校验一次） ----------
if ($Tag -notmatch '^[A-Za-z0-9._-]+$') {
    throw "Tag 含非法字符：$Tag（仅允许字母数字 . _ -）"
}

# ---------- 3. 资料库目录缺省 = 仓库根\sources\materials ----------
if (-not $Tree) {
    $Tree = Join-Path $RepoRoot 'sources\materials'
}
if (-not (Test-Path -LiteralPath $Tree -PathType Container)) {
    throw "资料库目录不存在：$Tree"
}

# ---------- 4. diff 模式必须有基线 ----------
if ($Mode -eq 'diff' -and -not $Baseline) {
    throw "diff 模式需要 -Baseline（上一版清单路径或 URL）：$Tag"
}

# ---------- 5. 定位 python（显式 > PATH） ----------
if (-not $Python) {
    $Python = 'python'
}
& $Python --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "python 不可用（$Python），请安装或 -Python 指定路径"
}

# ---------- 6. 调用核心 CLI（PYTHONPATH=src，import contest_generator.materials_pack） ----------
$env:PYTHONPATH = Join-Path $RepoRoot 'src'

$argsList = @(
    '-m', 'contest_generator.materials_pack',
    '--tree', $Tree,
    '--version', $Tag,
    '--out', $OutDir,
    '--mode', $Mode
)
if ($Baseline) {
    $argsList += @('--baseline', $Baseline)
}

Write-Host "[打包] 资料库：$Tree"
Write-Host "[打包] 模式：$Mode / 版本：$Tag / 输出：$OutDir"
& $Python @argsList
if ($LASTEXITCODE -ne 0) {
    throw "打包失败（退出码 $LASTEXITCODE）：见上方错误输出"
}

# ---------- 7. 确认清单 ----------
$ManifestPath = Join-Path $OutDir "firstep-materials-$Tag.manifest.json"
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "未生成清单：$ManifestPath"
}
Write-Host "清单确认：$ManifestPath"
