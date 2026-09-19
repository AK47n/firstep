# pack-full.ps1 — firstep 完整包打包脚本（工单 full-download/01）
# 用法（仓库根）：
#   powershell -File tools\pack-full.ps1 -Tag v1.1.0
#   powershell -File tools\pack-full.ps1 -Tag v1.1.0 -Baseline <上版完整包清单.json>
# 可选：-Tree <仓库根>（缺省 = 本脚本上级目录） -OutDir <输出目录> -Python <python.exe>
#       -LimitMB <单卷上限 MB，缺省 1900> -AllowDirty
#       -AllowMissingBaselineParts（允许基线旁边的 .removed.txt 缺失：首次发布等）
# 产出（缺省 %USERPROFILE%\Desktop\firstep-pack）：
#   firstep-full-<Tag>.zip[.part<N>]          完整包 zip 分卷（超单卷上限自动拆卷）
#   firstep-full-<Tag>.manifest.json          完整包清单（含包内全部文件 + 资料库基线清单）
#   firstep-full-<Tag>.removed.txt            **累计**删除清单（历史发过、本版不发；无基线 = 空）
#   firstep-full-<Tag>.sha256.txt             各分卷 SHA256
# 依赖：python 在 PATH（或 -Python 指定）；核心逻辑在 src\contest_generator\full_pack.py。
# 说明：包内只收「会变的内容」——工具本体 / 五个库 / 资料库内容文件；第三方安装包与
#       视觉 SDK 打包件、缓存、本地备份目录、虚拟环境一律不进包（约省 5.4 GB）。
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Baseline,
    [string]$Tree,
    [string]$OutDir = (Join-Path $env:USERPROFILE 'Desktop\firstep-pack'),
    [string]$Python,
    [double]$LimitMB = 1900,
    [switch]$AllowDirty,
    [switch]$AllowMissingBaselineParts
)
$ErrorActionPreference = 'Stop'

# ---------- 1. 定位仓库根（本脚本位于 tools\ 下） ----------
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

# 锁定控制台编码 UTF-8（中文路径与文件名输出不乱码；PS 5.1 默认 ANSI(GBK)）
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)

# ---------- 2. Tag 校验（仅防路径注入，不约束版本文法；CLI 侧再校验一次） ----------
if ($Tag -notmatch '^[A-Za-z0-9._-]+$') {
    throw "Tag 含非法字符：$Tag（仅允许字母数字 . _ -）"
}

# ---------- 3. 仓库根与单卷上限 ----------
if (-not $Tree) {
    $Tree = $RepoRoot
}
if (-not (Test-Path -LiteralPath $Tree -PathType Container)) {
    throw "仓库根目录不存在：$Tree"
}
if ($LimitMB -le 0) {
    throw "单卷上限必须是正数：$LimitMB"
}

# ---------- 4. 工作树检查：tracked 变更必须已提交（完整包是发版产物） ----------
if (-not $AllowDirty) {
    $dirty = git status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) { throw "git status 执行失败：$LASTEXITCODE" }
    if ($dirty) {
        Write-Host "[错误] 工作树存在未提交的 tracked 变更，拒绝打包（-AllowDirty 可豁免）：" -ForegroundColor Red
        $dirty | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
}

# ---------- 5. 定位 python（显式 > PATH） ----------
if (-not $Python) {
    $Python = 'python'
}
& $Python --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "python 不可用（$Python），请安装或 -Python 指定路径"
}

# ---------- 6. 调用核心 CLI（PYTHONPATH=src，import contest_generator.full_pack） ----------
$env:PYTHONPATH = Join-Path $RepoRoot 'src'

$argsList = @(
    '-m', 'contest_generator.full_pack',
    '--tree', $Tree,
    '--version', $Tag,
    '--out', $OutDir,
    '--limit-mb', $LimitMB
)
if ($Baseline) {
    if (-not (Test-Path -LiteralPath $Baseline)) { throw "基线清单不存在：$Baseline" }
    $argsList += @('--baseline', $Baseline, '--baseline-search-dir', $OutDir)
    # 累计删除清单的第二个输入：上一版**小发版**清单（工单 update-orphan-files/02）。
    # 小发版包发的东西与完整包不一样（本机库备份那类完整包收不到、而小发版照发），
    # 只按完整包清单做差那部分就永远清不掉。**按 tag 找齐在 Python 侧做**
    # （full_pack.find_update_files_for，有单测；PS 的 GetFileNameWithoutExtension
    # 只削一层扩展名，tag 里的点会咬人——离线演练实测踩到过）。
}
if ($AllowMissingBaselineParts) {
    $argsList += '--allow-missing-baseline-parts'
}

Write-Host "[打包] 仓库根：$Tree"
Write-Host "[打包] 版本：$Tag / 输出：$OutDir / 单卷上限：$LimitMB MB"
# Python 子进程按 UTF-8 输出：否则中文摘要按控制台 ANSI(GBK) 编码，在已设为
# UTF-8 的 PS 控制台上显示为乱码（文件本体编码一直是对的）。
$env:PYTHONIOENCODING = 'utf-8'
& $Python @argsList
$code = $LASTEXITCODE
if ($code -ne 0) {
    throw "完整包打包失败（退出码 $code）：见上方错误输出"
}

# ---------- 7. 确认四件套 ----------
$ManifestPath = Join-Path $OutDir "firstep-full-$Tag.manifest.json"
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "未生成完整包清单：$ManifestPath"
}
$ZipCount = @(Get-ChildItem -LiteralPath $OutDir -Filter "firstep-full-$Tag*.zip").Count
if ($ZipCount -lt 1) {
    throw "未生成 zip 分卷：$OutDir\firstep-full-$Tag*.zip"
}
Write-Host "清单确认：$ManifestPath（zip 分卷 $ZipCount 卷）"
Write-Host "下一步：按 docs\agents\releasing.md「完整包（zip 分卷）」上传四件套资产"
