param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$dataDir = Join-Path $projectRoot 'backend\data'
$logDir = Join-Path $projectRoot 'artifacts\windows'
$appUrl = 'http://127.0.0.1:8080'
function Show-PhoneAccess {
    try {
        $addresses = @(Get-NetIPConfiguration -ErrorAction Stop | Where-Object { $_.IPv4DefaultGateway } | ForEach-Object { $_.IPv4Address.IPAddress })
        foreach ($address in $addresses) { Write-Output "Phone on the same Wi-Fi: http://${address}:8080" }
    } catch { Write-Output 'Phone access: use this PC Wi-Fi IPv4 address on port 8080.' }
}
New-Item -ItemType Directory -Path $dataDir,$logDir -Force | Out-Null
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Install the Python environment first; see README.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) { throw 'Build the frontend first: cd frontend; npm ci; npm run build' }
$running = $false
try { $health = Invoke-RestMethod "$appUrl/api/health" -TimeoutSec 3; $running = $health.service -eq 'keke-pos' } catch { }
if ($running) {
    if (-not $NoBrowser) { Start-Process $appUrl }
    Write-Output "POS is running at $appUrl"
    Show-PhoneAccess
    return
}
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8080)
try { $listener.Start() } catch { throw 'Port 8080 is already in use by another application.' } finally { $listener.Stop() }
$configPath = Join-Path $dataDir 'windows-config.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    $setupToken = & $pythonPath -c 'import secrets; print(secrets.token_urlsafe(32))'
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate the setup token.' }
    @{ setup_token = $setupToken } | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
}
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$env:SETUP_TOKEN = $config.setup_token
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $dataDir 'pos.db') -replace '\\','/')
$env:PRINT_OUTPUT_DIR = Join-Path $dataDir 'tickets'
$env:FONT_PATH = Join-Path $env:WINDIR 'Fonts\msyh.ttc'
$env:CORS_ORIGINS = $appUrl
$env:PYTHONUTF8 = '1'
if (-not (Test-Path -LiteralPath $env:FONT_PATH)) { throw 'Microsoft YaHei CJK font is missing.' }
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $pythonPath -m app.database.initialize
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
} finally { Pop-Location }
$processRecords = @()
try {
    $serverPath = Join-Path $PSScriptRoot 'windows_server.py'
    $server = Start-Process -FilePath $pythonPath -ArgumentList ('"' + $serverPath + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'server.out.log') -RedirectStandardError (Join-Path $logDir 'server.err.log') -PassThru
    $processRecords += @{ id = $server.Id; started = $server.StartTime.ToUniversalTime().Ticks.ToString(); role = 'server' }
    $worker = Start-Process -FilePath $pythonPath -ArgumentList '-m','app.printing.worker' -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'worker.out.log') -RedirectStandardError (Join-Path $logDir 'worker.err.log') -PassThru
    $processRecords += @{ id = $worker.Id; started = $worker.StartTime.ToUniversalTime().Ticks.ToString(); role = 'worker' }
    ConvertTo-Json -InputObject $processRecords | Set-Content -LiteralPath (Join-Path $dataDir 'windows-processes.json') -Encoding UTF8
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $server.Refresh(); $worker.Refresh()
        if ($server.HasExited -or $worker.HasExited) { throw "A POS process stopped. Check $logDir" }
        try { $health = Invoke-RestMethod "$appUrl/api/health" -TimeoutSec 2; $ready = $health.service -eq 'keke-pos' } catch { }
        if ($ready) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw "POS did not become ready. Check $logDir" }
} catch {
    foreach ($record in $processRecords) {
        $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
        if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $record.started) { & taskkill.exe /PID $record.id /T /F | Out-Null }
    }
    throw
}
$setup = Invoke-RestMethod "$appUrl/api/auth/setup-status" -TimeoutSec 5
if ($setup.setup_required) {
    $instructionsPath = Join-Path $dataDir 'FIRST-RUN.txt'
    @("KEKE Mini POS - first administrator setup", "", "Open $appUrl", 'Enter your preferred administrator name and a new 6-12 digit PIN.', 'The third field asks for this setup token:', '', $config.setup_token, '', 'Keep this file private. Your database is backend\data\pos.db.') | Set-Content -LiteralPath $instructionsPath -Encoding UTF8
    if (-not $NoBrowser) { Start-Process notepad.exe -ArgumentList ('"' + $instructionsPath + '"') }
}
if (-not $NoBrowser) { Start-Process $appUrl }
Write-Output "POS is running at $appUrl"
Show-PhoneAccess
