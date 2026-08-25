# verify capsule nav states via CDP: mark done 1-3, scroll to step 6, shot + computed styles
param([int]$Port = 9250)
$ErrorActionPreference = "Stop"
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$outDir = "C:\Users\luoji\Desktop\firstep\.scratch\ui-polish-2"
$profile = Join-Path $env:TEMP "edge-cdp-nav-$Port"
if (Test-Path $profile) { Remove-Item $profile -Recurse -Force }
$p = Start-Process -FilePath $edge -ArgumentList @(
  "--headless=new", "--disable-gpu", "--hide-scrollbars",
  "--remote-debugging-port=$Port", "--remote-allow-origins=*",
  "--no-first-run", "--user-data-dir=$profile",
  "--window-size=1440,1000", "http://127.0.0.1:8000/") -PassThru
try {
  $deadline = (Get-Date).AddSeconds(15)
  $targets = $null
  do {
    Start-Sleep -Milliseconds 300
    try { $targets = Invoke-RestMethod "http://127.0.0.1:$Port/json/list" -TimeoutSec 2 } catch { }
  } while (-not $targets -and (Get-Date) -lt $deadline)
  $page = $targets | Where-Object { $_.url -like "*8000*" } | Select-Object -First 1
  $cts = [System.Threading.CancellationTokenSource]::new()
  $cts.CancelAfter(30000)
  $ws = [System.Net.WebSockets.ClientWebSocket]::new()
  $ws.ConnectAsync([Uri]$page.webSocketDebuggerUrl, $cts.Token).GetAwaiter().GetResult() | Out-Null
  $script:msgId = 0
  function Send-Cdp($method, $params) {
    $script:msgId++
    $o = @{ id = $script:msgId; method = $method }
    if ($params) { $o.params = $params }
    $json = $o | ConvertTo-Json -Compress -Depth 8
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $ws.SendAsync([ArraySegment[byte]]::new($bytes), [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token).GetAwaiter().GetResult() | Out-Null
    return $script:msgId
  }
  function Receive-Cdp($id) {
    $buf = New-Object byte[] 4194304
    for (;;) {
      $ms = New-Object IO.MemoryStream
      do {
        $r = $ws.ReceiveAsync([ArraySegment[byte]]::new($buf), $cts.Token).GetAwaiter().GetResult()
        $ms.Write($buf, 0, $r.Count)
      } while (-not $r.EndOfMessage)
      $text = [Text.Encoding]::UTF8.GetString($ms.ToArray())
      $m = $text | ConvertFrom-Json
      if ($m.id -eq $id) { return $m }
    }
  }
  function Eval-Js($expr) {
    $id = Send-Cdp "Runtime.evaluate" @{ expression = $expr; returnByValue = $true }
    $r = Receive-Cdp $id
    if ($r.result.exceptionDetails) { throw "eval error: $($r.result.exceptionDetails.text)" }
    return $r.result.result.value
  }
  function Shot($name) {
    $id = Send-Cdp "Page.captureScreenshot" @{ format = "png" }
    $r = Receive-Cdp $id
    [IO.File]::WriteAllBytes((Join-Path $outDir $name), [Convert]::FromBase64String($r.result.data))
    Write-Host "saved $name"
  }
  Send-Cdp "Page.enable" $null | Out-Null
  Receive-Cdp $script:msgId | Out-Null
  $deadline = (Get-Date).AddSeconds(20)
  $ready = $false
  do {
    Start-Sleep -Milliseconds 300
    $ready = Eval-Js "document.readyState === 'complete' && document.querySelectorAll('.step-nav .step-dot').length === 12"
  } while (-not $ready -and (Get-Date) -lt $deadline)
  if (-not $ready) { throw "page not ready" }

  # simulate progress: steps 1-3 done
  Eval-Js "markStepDone(1); markStepDone(2); markStepDone(3); true" | Out-Null
  # scroll so step 6 card top sits ~100px below viewport top -> current = 6
  Eval-Js "(function(){var c=stepCard(6); window.scrollTo(0, c.getBoundingClientRect().top + window.scrollY - 100); return true;})()" | Out-Null
  Start-Sleep -Milliseconds 600
  Shot "nav-states.png"

  # computed-style + state assertions
  $probe = @"
(function(){
  var items = document.querySelectorAll('.step-nav .step-dot');
  var nav = document.querySelector('.step-nav');
  var s1 = items[0], s3 = items[2], s6 = items[5];
  var c6 = stepCard(6).getBoundingClientRect();
  return JSON.stringify({
    navWidth: Math.round(nav.getBoundingClientRect().width),
    itemCount: items.length,
    done1: s1.classList.contains('done') && s1.querySelector('.dot').textContent === '\u2713',
    done3: s3.classList.contains('done') && s3.querySelector('.dot').textContent === '\u2713',
    undone4: !items[3].classList.contains('done') && items[3].querySelector('.dot').textContent === '4',
    current6: s6.classList.contains('current'),
    label1: s1.querySelector('.label').textContent,
    label10: items[9].querySelector('.label').textContent,
    label10Full: items[9].title,
    scrollY: Math.round(window.scrollY),
    card6Top: Math.round(c6.top),
    docHeight: document.documentElement.scrollHeight,
    viewH: window.innerHeight,
    anyCurrent: Array.from(items).filter(function(i){return i.classList.contains('current')}).map(function(i){return i.dataset.step}).join(',')
  });
})()
"@
  Write-Host "PROBE: " + (Eval-Js $probe)
  $ws.Dispose()
} finally {
  Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}
