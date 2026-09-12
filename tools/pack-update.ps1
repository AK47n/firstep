# pack-update.ps1 — firstep 小发版更新包打包脚本
# 用法（仓库根）：
#   powershell -File tools\pack-update.ps1 -Tag v1.1.0
#   可选：-Baseline <上次发布的 files.txt 路径> -OutDir <输出目录> -AllowDirty
#         -Python <python.exe>（缺省找 PATH 上的 python）
# 产出（缺省 %USERPROFILE%\Desktop\firstep-pack）：
#   firstep-update-<Tag>.zip          仓库 tracked 快照（zip 内顶层 = 仓库根）
#   firstep-update-<Tag>.files.txt    zip 内文件清单（相对路径，每行一个）
#   firstep-update-<Tag>.removed.txt  自基线起被删除的文件（无基线 = 空清单）
#   firstep-update-<Tag>.sha256.txt   zip 的 SHA256（sha256sum 格式）
# 依赖：python 在 PATH（或 -Python 指定）；核心逻辑在 src\contest_generator\pack_update.py。
# 口径（工单 full-download/08）：字节取源与完整包一致——核心里的 `git archive`
#   被钉成 `-c core.autocrlf=false`，故不受本机 autocrlf 影响，两个包对同一文件
#   逐字节相同（此前不钉 → 本机 autocrlf=true 转出 CRLF，两个包 926 个文件不一致）。
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [string]$Baseline,
    [string]$OutDir = (Join-Path $env:USERPROFILE 'Desktop\firstep-pack'),
    [string]$Python,
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

# ---------- 2. Tag 校验（仅防路径注入，不约束版本文法；核心侧再校验一次） ----------
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

# ---------- 6. 定位 python（显式 > PATH） ----------
if (-not $Python) {
    $Python = 'python'
}
& $Python --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "python 不可用（$Python），请安装或 -Python 指定路径"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Zip      = Join-Path $OutDir "firstep-update-$Tag.zip"
$FilesTxt = Join-Path $OutDir "firstep-update-$Tag.files.txt"
$RemovedTxt = Join-Path $OutDir "firstep-update-$Tag.removed.txt"
$ShaTxt   = Join-Path $OutDir "firstep-update-$Tag.sha256.txt"

# ---------- 7. 调核心打包（zip 与 .files.txt 由核心写出，两者必然一一对应） ----------
# 清单经临时文件传给核心：本机 tracked 快照约 3500 条、~150KB，直接上命令行
# 会逼近 Windows 命令行长度上限。
$ManifestTmp = Join-Path ([System.IO.Path]::GetTempPath()) "firstep-files-$Tag-$PID.txt"
[System.IO.File]::WriteAllLines($ManifestTmp, $Files, [System.Text.UTF8Encoding]::new($false))

try {
    $CorePath = Join-Path $RepoRoot 'src\contest_generator\pack_update.py'
    if (-not (Test-Path -LiteralPath $CorePath)) { throw "打包核心不存在：$CorePath" }
    # 以模块方式跑（PYTHONPATH=src + -m，与 pack-full.ps1 同款姿势）：直接
    # `python <脚本路径>` 会让核心里的相对导入 `from .full_pack import ...` 失败
    # （2026-09-13 真机演练踩到）。
    $env:PYTHONPATH = Join-Path $RepoRoot 'src'
    # 核心按 UTF-8 输出：否则中文摘要在已设为 UTF-8 的 PS 控制台上显示为乱码
    $env:PYTHONIOENCODING = 'utf-8'
    $CoreOut = & $Python -B -m contest_generator.pack_update --tree $RepoRoot --version $Tag --out $OutDir --files $ManifestTmp
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "更新包打包失败（退出码 $code）：见上方错误输出"
    }
    $CoreOut | ForEach-Object { Write-Host $_ }
} finally {
    Remove-Item -LiteralPath $ManifestTmp -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path -LiteralPath $Zip)) { throw "zip 未生成：$Zip" }

# ---------- 8. 删除清单（自基线 diff；无基线 = 空） ----------
# 基线文件必须以 UTF-8 显式读取：PowerShell 5.1 的 Get-Content 默认 ANSI(GBK)，
# 会把 UTF-8 中文路径读成乱码，导致「基线有而当前无」误判为全部删除。
if ($Baseline) {
    if (-not (Test-Path -LiteralPath $Baseline)) { throw "基线文件不存在：$Baseline" }
    $BaseLines = @(Get-Content -LiteralPath $Baseline -Encoding UTF8 | Where-Object { $_ -and -not $_.StartsWith('#') })
    $Removed = @($BaseLines | Where-Object { $_ -notin $Files })
    [System.IO.File]::WriteAllLines($RemovedTxt, $Removed, [System.Text.UTF8Encoding]::new($false))
} else {
    # 空清单写注释行：0 字节文件会被 `gh release upload` 以
    # `HTTP 400: Bad Content-Length` 拒收（工单 full-download/08 现场踩到；
    # 更新器跳过 `#` 行，语义不变）
    [System.IO.File]::WriteAllLines($RemovedTxt, @('# 无删除项（空清单占位：0 字节会被 gh 拒收）'), [System.Text.UTF8Encoding]::new($false))
}

# ---------- 9. SHA256（从核心输出里取，避免再算一遍） ----------
$shaMatch = [regex]::Match(($CoreOut -join "`n"), '(?m)^\s*SHA256：([0-9a-fA-F]{64})')
if (-not $shaMatch.Success) { throw "未能从核心输出解析 SHA256，拒绝写出校验和文件" }
$sha = $shaMatch.Groups[1].Value.ToLower()
[System.IO.File]::WriteAllText($ShaTxt, "$sha  firstep-update-$Tag.zip`n", [System.Text.UTF8Encoding]::new($false))
$verified = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLower()
if ($verified -ne $sha) { throw "校验和不一致：核心报告 $sha，实测 $verified" }

# ---------- 10. 摘要 ----------
$sizeMB = [math]::Round((Get-Item -LiteralPath $Zip).Length / 1MB, 1)
$baselineNote = if ($Baseline) { "（基线 $Baseline）" } else { "（无基线，空清单）" }
Write-Host "更新包已生成：$Zip（$sizeMB MB，$($Files.Count) 个文件）"
Write-Host "  文件清单：$FilesTxt"
Write-Host "  删除清单：$RemovedTxt $baselineNote"
Write-Host "  SHA256：$ShaTxt"
Write-Host "  字节口径：与完整包同源（核心内 git archive 已钉 core.autocrlf=false）"
