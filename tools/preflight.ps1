# tools/preflight.ps1 —— 发版前自检的 PowerShell 入口（工单 commit-gate/03）
#
# 为什么是薄壳：判据（三处版本号一致 / 母版 .settings 编码钉 / 下载文档一致性）
# 全部在 tools/preflight.py 里，而它复用产品自己的解析器（contest_generator.changelog）
# ——两份判据漂移过一次就很难查，所以这里**不重复实现任何判据**，只负责把仓库根的
# Python 找出来并转发退出码。
#
# 用法（仓库根，或任意位置——脚本自己定位仓库根）：
#     powershell -File tools\preflight.ps1
#     pwsh -File tools\preflight.ps1 -Quiet
#
# 退出码：0 = 可以发版；1 = 有红项（逐条原因由 python 侧打印）；2 = 环境问题。
#
# 编码（硬性约定）：本文件必须存成 UTF-8 with BOM —— 见 CLAUDE.md「PowerShell 编码」，
# 无 BOM 时 Windows PowerShell 5.1 按 GBK 解码，UTF-8 中文注释会吞掉行尾换行、
# 把下一行代码注释掉（tests/test_ps1_encoding.py 兜底）。

[CmdletBinding()]
param(
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

# 仓库根 = 本脚本所在目录的上一级
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PreflightPy = Join-Path $RepoRoot 'tools\preflight.py'

if (-not (Test-Path $PreflightPy)) {
    Write-Error "找不到 $PreflightPy —— 请在仓库内运行本脚本"
    exit 2
}

# 解释器：优先仓库 .venv（装机方式装的），否则系统 python / py
$candidates = @()
$venvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (Test-Path $venvPython) { $candidates += $venvPython }
foreach ($name in @('python', 'py')) {
    $found = Get-Command $name -ErrorAction SilentlyContinue
    if ($found) { $candidates += $found.Source }
}

if ($candidates.Count -eq 0) {
    Write-Error '找不到 python 解释器（python / py 都不在 PATH）—— 发版自检需要它'
    exit 2
}

$python = $candidates[0]
if (-not $Quiet) { Write-Host "[preflight] 解释器：$python" }

# 钉 PYTHONPATH 到仓库 src：本机全局 site-packages 里可能有一份 editable 安装指向
# **另一个**源码路径（见 docs/agents/local-environment.md 2.5），不钉就会检查错对象。
$env:PYTHONPATH = (Join-Path $RepoRoot 'src')
if ($env:PYTHONIOENCODING -eq $null -or $env:PYTHONIOENCODING -eq '') {
    $env:PYTHONIOENCODING = 'utf-8'
}

& $python $PreflightPy
exit $LASTEXITCODE
