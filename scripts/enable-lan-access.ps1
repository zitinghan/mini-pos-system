$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $projectRoot 'artifacts\windows\lan-firewall-result.json'
New-Item -ItemType Directory -Path (Split-Path -Parent $resultPath) -Force | Out-Null
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this script as administrator to allow phone access through Windows Firewall.'
    }
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    $networkProgram = & $pythonPath -c 'import sys; print(sys._base_executable)'
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $networkProgram)) { throw 'Could not locate the installed Python runtime.' }
    $ruleName = 'KOKO-Mini-POS-LAN-8080'
    $rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    if ($rule) {
        Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound -Action Allow -Profile Private -Protocol TCP -LocalPort 8080 -RemoteAddress LocalSubnet -Program $networkProgram -EdgeTraversalPolicy Block | Out-Null
    } else {
        New-NetFirewallRule -Name $ruleName -DisplayName 'KOKO Mini POS - phones on private LAN' -Enabled True -Direction Inbound -Action Allow -Profile Private -Protocol TCP -LocalPort 8080 -RemoteAddress LocalSubnet -Program $networkProgram -EdgeTraversalPolicy Block | Out-Null
    }
    @{ success = $true; rule = $ruleName; port = 8080; profile = 'Private'; remote_address = 'LocalSubnet' } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    @{ success = $false; error = $_.Exception.Message } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    throw
}
