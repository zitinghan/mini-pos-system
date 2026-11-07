param([switch]$CurrentNetwork, [string]$InterfaceAlias = 'Wi-Fi')
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
    $displayName = 'KOKO Mini POS - phones on private LAN'
    $settings = @{
        Enabled = 'True'; Direction = 'Inbound'; Action = 'Allow'; Profile = 'Private'
        Protocol = 'TCP'; LocalPort = 8080; RemoteAddress = 'LocalSubnet'
        Program = $networkProgram; EdgeTraversalPolicy = 'Block'
    }
    if ($CurrentNetwork) {
        $network = Get-NetIPConfiguration -InterfaceAlias $InterfaceAlias -ErrorAction Stop
        $address = Get-NetIPAddress -InterfaceIndex $network.InterfaceIndex -AddressFamily IPv4 |
            Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '169.254.*' } |
            Select-Object -First 1
        if (-not $address -or -not $network.IPv4DefaultGateway) { throw 'This network has no usable IPv4 address and gateway.' }
        $cidr = & $pythonPath -c 'import ipaddress,sys; print(ipaddress.ip_network(sys.argv[1], strict=False))' "$($address.IPAddress)/$($address.PrefixLength)"
        if ($LASTEXITCODE -ne 0) { throw 'Could not determine the current local subnet.' }
        $profile = Get-NetConnectionProfile -InterfaceIndex $network.InterfaceIndex -ErrorAction Stop
        $settings.Profile = if ($profile.NetworkCategory -eq 'DomainAuthenticated') { 'Domain' } else { $profile.NetworkCategory.ToString() }
        $settings.RemoteAddress = $cidr.Trim()
        $settings.InterfaceAlias = $InterfaceAlias
        $ruleName = 'KOKO-Mini-POS-Current-Network-8080'
        $displayName = 'KOKO Mini POS - phones on configured local subnet'
    }
    $rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    if ($rule) {
        Set-NetFirewallRule -Name $ruleName @settings | Out-Null
    } else {
        New-NetFirewallRule -Name $ruleName -DisplayName $displayName @settings | Out-Null
    }
    @{ success = $true; rule = $ruleName; port = 8080; profile = $settings.Profile; remote_address = $settings.RemoteAddress } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
} catch {
    @{ success = $false; error = $_.Exception.Message } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
    throw
}
