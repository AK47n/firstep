# 发版 v1.4.0 收尾（推送 → Release → 八件资产 → 联网自检）
#
# 先决条件（都已就位）：两个包在 `%USERPROFILE%\Desktop\firstep-pack\`、本地 tag v1.4.0 已打好、
# Release 说明在 `release-notes-v1.4.0.md`、工作树干净。
#
# 用法：powershell -File .scratch\release-v1.4.0\finish-publish.ps1 -ResolveIp <验过的 IP>
#
# ⚠ 两条本机事实（2026-09-27 实测，v1.3.1 那一轮定的）：
#   ① 钉 IP 的 git config 键**不是** `http.https://github.com/.resolve`（git 2.54 上不生效）
#      ——**有效的键是 `http.curloptResolve`**；
#   ② 候选 IP 要**按内容**验（拿回来的得是 `001e# service=git-upload-pack…` + 真 ref），
#      本机中间人对任意域名都可能答 200。
#   另：第一次推常被掐（`Recv failure: Connection was reset`）——换验过的 IP **并加
#   `http.postBuffer=524288000`**（默认 1 MiB 之上走 chunked，中间人更容易掐）。
#
# 编码（硬性约定）：本文件必须存成 UTF-8 with BOM —— 见 CLAUDE.md「PowerShell 编码」。
# v1.3.1 那一轮新写的 .ps1 无 BOM，pre-push 闸门当场红两条、白等一整轮（≈5 分钟）。

param(
    [string]$ResolveIp = '140.82.114.3'
)

$ErrorActionPreference = 'Stop'
$Repo = 'AK47n/firstep'
$Tag = 'v1.4.0'
$Pack = Join-Path $env:USERPROFILE 'Desktop\firstep-pack'
$Root = 'C:\Users\luoji\Desktop\firstep'
$Resolve = "http.curloptResolve=github.com:443:$ResolveIp"
Set-Location $Root

Write-Host "[0/4] 先按内容验一次 IP（$ResolveIp）…"
$probe = git -c $Resolve ls-remote origin main 2>&1
if ($LASTEXITCODE -ne 0 -or "$probe" -notmatch 'refs/heads/main') {
    throw "IP $ResolveIp 不可用（读数：$probe）——换一个候选重试。"
}
Write-Host "      OK：$probe"

Write-Host '[1/4] 推 main + tag（钉 IP；会跑 pre-push 闸门，约 8 分钟）…'
git -c $Resolve -c http.postBuffer=524288000 push origin main $Tag
if ($LASTEXITCODE -ne 0) { throw '推送失败——先别建 Release。' }

Write-Host '[2/4] 建 Release…'
gh release create $Tag `
  --title 'firstep 电赛工程生成器 · v1.4.0（全站观感统一）' `
  --notes-file "$Pack\release-notes-$Tag.md" `
  --repo $Repo

Write-Host '[3/4] 传八件资产（小发版四件 + 完整包四件；ASCII 文件名）…'
gh release upload $Tag `
  "$Pack\firstep-update-$Tag.zip" "$Pack\firstep-update-$Tag.files.txt" `
  "$Pack\firstep-update-$Tag.removed.txt" "$Pack\firstep-update-$Tag.sha256.txt" `
  --repo $Repo
gh release upload $Tag `
  "$Pack\firstep-full-$Tag.zip" "$Pack\firstep-full-$Tag.manifest.json" `
  "$Pack\firstep-full-$Tag.removed.txt" "$Pack\firstep-full-$Tag.sha256.txt" `
  --repo $Repo
gh release view $Tag --repo $Repo

Write-Host '[4/4] 联网自检（拿线上最新 Release 校 README 体积口径与 Release 说明前两行）…'
python tools\check-download-docs.py
if ($LASTEXITCODE -ne 0) { throw '联网自检非 0——照它的逐条原因修，别忽略。' }

Write-Host ''
Write-Host '发版完成。收尾还差一步（未自动做）：把 docs\agents\local-environment.md 第 0 节写成'
Write-Host '「已发布 v1.4.0 / 落差归零」、第 3 节加一行发布状态，并落本目录 issues\04 的账。'
