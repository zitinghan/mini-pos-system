$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $projectRoot 'backend\data\windows-processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Write-Output 'No saved POS processes.'; return }
$records = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($record in $records) {
    $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $record.started) {
        & taskkill.exe /PID $record.id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not stop the POS $($record.role) process." }
    }
}
Remove-Item -LiteralPath $statePath
Write-Output 'POS stopped. Saved data has been kept.'
