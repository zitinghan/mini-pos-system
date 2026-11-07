$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$startupDirectory = [Environment]::GetFolderPath('Startup')
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $startupDirectory 'KOKO Mini POS (Auto Start).lnk'))
$shortcut.TargetPath = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'start-windows.ps1') + '" -NoBrowser'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Start the POS server and print worker when signing in to Windows'
$shortcut.WindowStyle = 7
$shortcut.Save()
Write-Output 'Mini POS will start automatically when this Windows user signs in.'
