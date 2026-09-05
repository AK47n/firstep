# pack-update.ps1 — firstep 小发版更新包打包脚本
# 用法（仓库根）：
#   powershell -File tools\pack-update.ps1 -Tag v1.1.0
#   可选：-Baseline <上次发布的 files.txt 路径> -OutDir <输出目录> -AllowDirty
# 产出（缺省 %USERPROFILE%\Desktop\firstep-pack）：
#   firstep-update-<Tag>.zip          仓库 tracked 快照（git archive，zip 内顶层 = 仓库根）
#   firstep-update-<Tag>.files.txt    zip 内文件清单（相对路径，每行一个）
#   firstep-update-<Tag>.removed.txt  自基线起被删除的文件（无基线 = 空清单）
#   firstep-update-<Tag>.sha256.txt   zip 的 SHA256（sha256sum 格式）
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Baseline,
    [string]$OutDir = (Join-Path $env:USERPROFILE 'Desktop\firstep-pack'),
    [switch]$AllowDirty
)

$ErrorActionPreference = 'Stop'

# ---------- 1. 定位仓库根（本脚本位于 tools\ 下） ----------
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

# 锁定控制台输出/输入编码为 UTF-8：否则 PowerShell 5.1 可能按 ANSI(GBK) 解码
# git 输出的中文路径，清单写盘后变成乱码（与 zip 内 UTF-8 文件名不一致）。
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)

# ---------- 2. Tag 校验（仅防路径注入，不约束版本文法） ----------
if ($Tag -notmatch '^[A-Za-z0-9._-]+$') {
    throw "Tag 含非法字符：$Tag（仅允许字母数字 . _ -）"
}

# ---------- 3. 工作树检查：tracked 变更必须已提交 ----------
if (-not $AllowDirty) {
    $dirty = git status --porcelain --untracked-files=no
    if ($LASTEXITCODE -ne 0) { throw "git status 执行失败：$LASTEXITCODE" }
    if ($dirty) {
        Write-Host "[错误] 工作树存在未提交的 tracked 变更，拒绝打包（-AllowDirty 可豁免）：" -ForegroundColor Red
        $dirty | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
}

# ---------- 4. 顶层白名单（新增顶层目录时在此登记） ----------
$TopLevels = @(
    'src', 'library', 'sources', 'tests', 'docs', 'assets', 'tools', '.githooks',
    '.gitattributes', '.gitignore', 'CLAUDE.md', 'README.md', 'CONTEXT.md',
    'CHANGELOG.md', 'VERSIONS.md', 'pyproject.toml', 'install.bat', 'start-app.bat',
    'start-app.vbs', 'stop-firstep.bat', 'stop-firstep.vbs'
)
$TopPattern = '^(' + (($TopLevels | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')(/|$)'

# ---------- 5. 文件清单（仅 tracked；.venv / sources\materials / .scratch 不进清单） ----------
# -c core.quotepath=false：显式要求真实 UTF-8 路径（默认配置会把中文转义成 \NNN，
# 与 zip 内 UTF-8 文件名不一致，删除清单将无法定位文件；不依赖本机 git 全局配置）。
$Files = @(git -c core.quotepath=false ls-files | Where-Object { $_ -match $TopPattern })
if ($Files.Count -eq 0) {
    throw 'git ls-files 无匹配文件，检查仓库状态'
}

# ---------- 6. 打 zip（git archive 只含 tracked、含子目录；排除项靠白名单） ----------
# 只传「清单中实际命中」的顶层作为 pathspec：git archive 的 pathspec 必须匹配
# 已跟踪路径，未跟踪目录（如新建未提交的 tools\）传进去会 fatal。
$HitTop = @($TopLevels | Where-Object {
    $p = [regex]::Escape($_)
    [bool]($Files | Where-Object { $_ -match "^$p(/|$)" })
})
if ($HitTop.Count -eq 0) { throw '无命中的顶层路径，无法打包' }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Zip     = Join-Path $OutDir "firstep-update-$Tag.zip"
$FilesTxt = Join-Path $OutDir "firstep-update-$Tag.files.txt"
$RemovedTxt = Join-Path $OutDir "firstep-update-$Tag.removed.txt"
$ShaTxt   = Join-Path $OutDir "firstep-update-$Tag.sha256.txt"

git archive --format=zip --output="$Zip" HEAD -- $HitTop
if ($LASTEXITCODE -ne 0) { throw "git archive 失败：$LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $Zip)) { throw "zip 未生成：$Zip" }

[System.IO.File]::WriteAllLines($FilesTxt, $Files, [System.Text.UTF8Encoding]::new($false))

# ---------- 7. 删除清单（自基线 diff；无基线 = 空） ----------
# 基线文件必须以 UTF-8 显式读取：PowerShell 5.1 的 Get-Content 默认 ANSI(GBK)，
# 会把 UTF-8 中文路径读成乱码，导致「基线有而当前无」误判为全部删除。
if ($Baseline) {
    if (-not (Test-Path -LiteralPath $Baseline)) { throw "基线文件不存在：$Baseline" }
    $BaseLines = @(Get-Content -LiteralPath $Baseline -Encoding UTF8 | Where-Object { $_ -and -not $_.StartsWith('#') })
    $Removed = @($BaseLines | Where-Object { $_ -notin $Files })
    [System.IO.File]::WriteAllLines($RemovedTxt, $Removed, [System.Text.UTF8Encoding]::new($false))
} else {
    [System.IO.File]::WriteAllLines($RemovedTxt, @(), [System.Text.UTF8Encoding]::new($false))
}

# ---------- 8. SHA256 ----------
$sha = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash
[System.IO.File]::WriteAllText($ShaTxt, "$sha  firstep-update-$Tag.zip`n", [System.Text.UTF8Encoding]::new($false))

# ---------- 9. 摘要 ----------
$sizeMB = [math]::Round((Get-Item -LiteralPath $Zip).Length / 1MB, 1)
$baselineNote = if ($Baseline) { "（基线 $Baseline）" } else { "（无基线，空清单）" }
Write-Host "更新包已生成：$Zip（$sizeMB MB，$($Files.Count) 个文件）"
Write-Host "  文件清单：$FilesTxt"
Write-Host "  删除清单：$RemovedTxt $baselineNote"
Write-Host "  SHA256：$ShaTxt"
