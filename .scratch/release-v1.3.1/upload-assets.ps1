# 上传 v1.3.1 八件资产（小发版四件 + 完整包四件；ASCII 文件名）
#
# 用法：powershell -File .scratch\release-v1.3.1\upload-assets.ps1
#
# 编码（硬性约定）：本文件必须存成 UTF-8 with BOM —— 见 CLAUDE.md「PowerShell 编码」。
# 踩过一次：第一版由编辑工具写出来是**无 BOM**，pre-push 闸门的
# `tests/test_ps1_encoding.py` 当场红（两条），推送被拒。

$ErrorActionPreference = 'Stop'
$Repo = 'AK47n/firstep'
$Tag = 'v1.3.1'
$Pack = Join-Path $env:USERPROFILE 'Desktop\firstep-pack'

Write-Host '[1/2] 小发版四件套…'
gh release upload $Tag `
  "$Pack\firstep-update-$Tag.zip" "$Pack\firstep-update-$Tag.files.txt" `
  "$Pack\firstep-update-$Tag.removed.txt" "$Pack\firstep-update-$Tag.sha256.txt" `
  --repo $Repo

Write-Host '[2/2] 完整包四件套（约 755 MB，慢）…'
gh release upload $Tag `
  "$Pack\firstep-full-$Tag.zip" "$Pack\firstep-full-$Tag.manifest.json" `
  "$Pack\firstep-full-$Tag.removed.txt" "$Pack\firstep-full-$Tag.sha256.txt" `
  --repo $Repo

Write-Host '资产清单：'
gh release view $Tag --repo $Repo
