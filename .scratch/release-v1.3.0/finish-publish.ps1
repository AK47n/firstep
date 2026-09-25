# 发版 v1.3.0 收尾（网络恢复后跑这一条）
#
# 背景：2026-09-25 打包与真编译闸门都过了，但 `github.com:443` 连不上
# （`api.github.com` 正常、`github.com:22` 探测通但本机 ssh.exe 不可用），
# 于是 `git push` 反复失败（12 次重试 / 约 12 分钟）。本脚本把剩下四步串起来：
#   ① 推 main + tag ② 建 Release ③ 传八件资产 ④ 联网自检
#
# 先决条件（都已就位）：包在 `%USERPROFILE%\Desktop\firstep-pack\`、本地 tag v1.3.0 已打好、
# Release 说明在 `release-notes-v1.3.0.md`、工作树干净。
#
# 用法：powershell -File .scratch\release-v1.3.0\finish-publish.ps1
# 注意：① 推送会跑 pre-push 闸门（整套 pytest + 前端门禁 + 浏览器门禁，约 8 分钟）；
#       ② **在推送成功之前不要建 Release**——`gh release create` 会按远端默认分支的 HEAD
#          建 tag，远端还没收到 main 的新提交时会把 tag 打到 v1.2.2 那个提交上。

$ErrorActionPreference = 'Stop'
$Repo = 'AK47n/firstep'
$Pack = Join-Path $env:USERPROFILE 'Desktop\firstep-pack'
$Root = 'C:\Users\luoji\Desktop\firstep'
Set-Location $Root

Write-Host '[1/4] 推 main + tag（会跑 pre-push 闸门）…'
git push origin main v1.3.0
if ($LASTEXITCODE -ne 0) { throw '推送失败——网络还没恢复？先别建 Release。' }

Write-Host '[2/4] 建 Release…'
gh release create v1.3.0 `
  --title 'firstep 电赛工程生成器 · v1.3.0（新增「硬件检测」：先验硬件再做题）' `
  --notes-file "$Pack\release-notes-v1.3.0.md" `
  --repo $Repo

Write-Host '[3/4] 传八件资产（小发版四件 + 完整包四件；ASCII 文件名）…'
gh release upload v1.3.0 `
  "$Pack\firstep-update-v1.3.0.zip" "$Pack\firstep-update-v1.3.0.files.txt" `
  "$Pack\firstep-update-v1.3.0.removed.txt" "$Pack\firstep-update-v1.3.0.sha256.txt" `
  --repo $Repo
gh release upload v1.3.0 `
  "$Pack\firstep-full-v1.3.0.zip" "$Pack\firstep-full-v1.3.0.manifest.json" `
  "$Pack\firstep-full-v1.3.0.removed.txt" "$Pack\firstep-full-v1.3.0.sha256.txt" `
  --repo $Repo
gh release view v1.3.0 --repo $Repo

Write-Host '[4/4] 联网自检（拿线上最新 Release 校 README 体积口径与 Release 说明前两行）…'
python tools\check-download-docs.py
if ($LASTEXITCODE -ne 0) { throw '联网自检非 0——照它的逐条原因修，别忽略。' }

Write-Host ''
Write-Host '发版完成。收尾还差一步（未自动做）：把 docs\agents\local-environment.md 第 0 节的'
Write-Host '落差表写成「已发布 v1.3.0 / 落差归零」，并落 .scratch\release-v1.3.0\issues\03 的账本。'
