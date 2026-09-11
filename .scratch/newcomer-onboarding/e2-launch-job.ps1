# E2 超时态实测：真正执行 launcher 的那一层（跑在 Start-Job 的子进程里）
# 为什么单独一层：Start-Process 跑批处理不可靠（v4/v5 两次静默不执行），而作业里用
# & cmd /c 调用批处理 + $LASTEXITCODE 是稳的。
# 用法：由 run-E2-timeout-v6.ps1 通过 Start-Job -FilePath 调用，参数 = 仓库根 + 结果文件路径。
# 说明：被测对象 = .scratch/newcomer-onboarding/diag-trace-start-app.bat —— 它是 start-app.bat 的
# **同流程 ASCII trace 副本**（逐分支写 trace），用来在读不到弹窗正文时确证走了哪个分支。
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$ResultFile
)
Set-Location $Repo
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$out = & cmd /c ".scratch\newcomer-onboarding\diag-trace-start-app.bat" 2>&1
$rc = $LASTEXITCODE
$sw.Stop()
$tracePath = Join-Path $env:TEMP 'e2v6-trace.txt'
$trace = if (Test-Path $tracePath) { Get-Content $tracePath -Raw } else { '(无 trace 文件)' }
@(
    "exit_code=$rc",
    ("elapsed_seconds=" + [math]::Round($sw.Elapsed.TotalSeconds, 1)),
    ("stdout=" + (($out | Out-String).Trim())),
    "trace:",
    $trace
) | Set-Content -Path $ResultFile -Encoding UTF8
exit $rc
