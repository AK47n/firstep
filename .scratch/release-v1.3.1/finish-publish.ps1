# 发版 v1.3.1 收尾（推送 → Release → 八件资产 → 联网自检）
#
# 先决条件（都已就位）：两个包在 `%USERPROFILE%\Desktop\firstep-pack\`、本地 tag v1.3.1 已打好、
# Release 说明在 `release-notes-v1.3.1.md`、工作树干净。
#
# 用法：powershell -File .scratch\release-v1.3.1\finish-publish.ps1
#
# ⚠ 两条本机事实（2026-09-27 本轮实测，**与 v1.3.0 那份脚本不同**）：
#   ① 钉 IP 的 git config 键**不是** `http.https://github.com/.resolve`——
#      git 2.54.0.windows.1 上那个键**不生效**（`ls-remote` 仍按 hosts 解析到 127.0.0.1、
#      21 秒后 `Failed to connect to github.com port 443`）。**有效的键是 `http.curloptResolve`**：
#        git -c http.curloptResolve=github.com:443:140.82.113.3 ls-remote origin main   # 通
#   ② 候选 IP 要**按内容**验，不是按 HTTP 码：本机中间人会对任意域名答 200。
#      判据 = 拿回来的真是 git 智能 HTTP 广告（`001e# service=git-upload-pack…` + 真 ref）。
#
# 注意：① 推送会跑 pre-push 闸门（推 tag ⇒ 整套 pytest + 前端门禁 + 浏览器门禁，约 8 分钟）；
#       ② **在推送成功之前不要建 Release**——`gh release create` 会在服务端按远端默认分支的
#          HEAD 建 tag，远端还没收到 main 的新提交时会把 tag 打到旧提交上。

$ErrorActionPreference = 'Stop'
$Repo = 'AK47n/firstep'
$Tag = 'v1.3.1'
$Pack = Join-Path $env:USERPROFILE 'Desktop\firstep-pack'
$Root = 'C:\Users\luoji\Desktop\firstep'
$Resolve = 'http.curloptResolve=github.com:443:140.82.113.3'
Set-Location $Root

Write-Host '[1/4] 推 main + tag（钉 IP；会跑 pre-push 闸门）…'
git -c $Resolve push origin main $Tag
if ($LASTEXITCODE -ne 0) { throw '推送失败——先别建 Release。' }

Write-Host '[2/4] 建 Release…'
gh release create $Tag `
  --title 'firstep 电赛工程生成器 · v1.3.1（页面文字与可达性小修）' `
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
Write-Host '发版完成。收尾还差一步（未自动做）：把 docs\agents\local-environment.md 第 0 节的'
Write-Host '落差表写成「已发布 v1.3.1 / 落差归零」，并落本目录 issues\03 的账本。'
