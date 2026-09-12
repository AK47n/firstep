# launcher-log.ps1 — start-app.bat 的启动留痕单源（工单 launcher-failure-reason/01）
#
# 为什么要这一支脚本：start-app.bat 的失败分支只弹中文弹窗，弹窗正文在进程侧读不到，
# 于是「这次失败到底是哪一条分支」只能靠退出码 + 计时猜（挂账单 E2 的第三态就因此
# 一直「留人工」）。本脚本把每次启动写成 launcher.log 里的一行机器可读记录。
#
# 用法（start-app.bat 各分支调用）：
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File "tools\launcher-log.ps1" -Reason port_busy port=8899
#
# 行形态（固定字段顺序，可选字段追加在后）：
#   [2026-09-12T01:30:00+08:00] reason=port_busy port=8899
#
# 现用字段：各分支传 `port=<端口>`；`:started` 另传 `tries=<第几次轮询就绪>`。
# （早期注释里举的 `http_status=` 例子从未被任何分支传过，已删——免得读者以为日志里有它。）
#
# 落盘纪律（测试 tests/test_launcher_log.py 钉住）：
#   * 行内容纯 ASCII，值里不得有空格（多词用 - 连接）——保证「按空白切词」的读法稳定；
#   * 文件按追加语义（保留每次启动的历史），UTF-8 **无 BOM**（Add-Content 首写会带 BOM，故用
#     .NET 的 UTF8Encoding($false)）；
#   * 目录不存在则自动创建（%USERPROFILE%\.contest_generator\ 正常由应用创建，但不能假定它在）；
#   * 中文只在弹窗里，日志不写中文。
#
# 注意：本文件必须存成 UTF-8 with BOM（仓库硬性约定，见 CLAUDE.md / docs/agents/workflow.md；
# tests/test_ps1_encoding.py 兜底）——Windows PowerShell 5.1 对无 BOM 的 .ps1 按系统 ANSI 解码。

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string] $Reason,

    # 可选细节，形如 key=value（值内不得有空格）
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Fields
)

$ErrorActionPreference = 'Stop'

function Get-LauncherLogPath {
    $home_ = $env:USERPROFILE
    if ([string]::IsNullOrWhiteSpace($home_)) {
        $home_ = [Environment]::GetFolderPath('UserProfile')
    }
    if ([string]::IsNullOrWhiteSpace($home_)) {
        throw 'launcher-log: 无法确定用户主目录（USERPROFILE 为空）'
    }
    return (Join-Path (Join-Path $home_ '.contest_generator') 'launcher.log')
}

# 去掉调用方可能带上的成对引号（cmd 转发参数时常见）
function Remove-WrappingQuotes {
    param([string] $Text)
    $t = $Text.Trim()
    if ($t.Length -ge 2) {
        $first = $t.Substring(0, 1)
        $last = $t.Substring($t.Length - 1, 1)
        if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
            return $t.Substring(1, $t.Length - 2)
        }
    }
    return $t
}

$reasonText = Remove-WrappingQuotes $Reason
if ($reasonText -notmatch '^[a-z][a-z0-9_]*$') {
    throw "launcher-log: reason 必须是码表里的小写下划线形态，收到：$Reason"
}
if ($reasonText -match '\s') {
    throw 'launcher-log: reason 不得含空白'
}

$parts = New-Object System.Collections.Generic.List[string]
foreach ($f in @($Fields)) {
    $pair = Remove-WrappingQuotes $f
    if ([string]::IsNullOrWhiteSpace($pair)) { continue }
    if ($pair -notmatch '^[A-Za-z][A-Za-z0-9_]*=(.+)$') {
        throw "launcher-log: 附加字段必须是 key=value 形态，收到：$f"
    }
    $value = $pair.Substring($pair.IndexOf('=') + 1)
    if ($value -match '\s') {
        throw "launcher-log: 字段值不得含空白（多词用 - 连接），收到：$f"
    }
    $parts.Add($pair)
}

$stamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
$line = '[' + $stamp + '] reason=' + $reasonText
foreach ($p in $parts) { $line = $line + ' ' + $p }

$logPath = Get-LauncherLogPath
$dir = Split-Path -Parent $logPath
if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

# UTF-8 无 BOM 追加：Add-Content -Encoding UTF8 在文件不存在时会先写 BOM，故走 .NET
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::AppendAllText($logPath, $line + [Environment]::NewLine, $utf8NoBom)
