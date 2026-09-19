#requires -Version 5.1
# SPDX-License-Identifier: GPL-3.0-only
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))

function Pause-ForUser([string] $Message = 'Press Enter to close') {
    Write-Host ''
    [void](Read-Host $Message)
}

Write-Host ''
Write-Host 'End of the World Bot - Windows Setup Assistant'
Write-Host '----------------------------------------------'
Write-Host 'The full Bot runs in Windows Subsystem for Linux (WSL).'
Write-Host 'This assistant does not silently enable Windows features or use the network.'
Write-Host ''

$wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wsl) {
    Write-Host 'WSL is not available on this PC.' -ForegroundColor Yellow
    Write-Host 'Windows 10/11 users can install WSL and Ubuntu with:'
    Write-Host '  wsl --install -d Ubuntu'
    Write-Host ''
    $answer = Read-Host 'Open an Administrator window and start that installation now? [y/N]'
    if ($answer -match '^(?i:y|yes)$') {
        Start-Process -FilePath 'wsl.exe' -ArgumentList @('--install','-d','Ubuntu') -Verb RunAs -Wait
        Write-Host ''
        Write-Host 'If Windows asks you to restart, restart and then run "End of the World Bot Setup" again.'
    }
    Pause-ForUser
    exit 0
}

$probe = & wsl.exe -e sh -lc 'printf ready' 2>$null
if ($LASTEXITCODE -ne 0 -or ($probe -join '') -notmatch 'ready') {
    Write-Host 'WSL is present, but no ready Linux distribution was found.' -ForegroundColor Yellow
    Write-Host 'The recommended distribution is Ubuntu.'
    $answer = Read-Host 'Install Ubuntu now? This may require Administrator approval and a restart. [y/N]'
    if ($answer -match '^(?i:y|yes)$') {
        Start-Process -FilePath 'wsl.exe' -ArgumentList @('--install','-d','Ubuntu') -Verb RunAs -Wait
        Write-Host ''
        Write-Host 'Finish Ubuntu first-run setup (username/password), then run this assistant again.'
    }
    Pause-ForUser
    exit 0
}

$linuxRoot = (& wsl.exe -e wslpath -a $root 2>$null | Select-Object -First 1).Trim()
if (-not $linuxRoot) {
    throw 'Could not translate the installed Windows folder into a WSL path.'
}

Write-Host 'WSL is ready.'
Write-Host 'The next step checks Linux prerequisites and installs this release into your WSL home folder.'
Write-Host 'If packages are missing, the Linux script asks before using the Internet or sudo.'
Write-Host ''

& wsl.exe -e sh "$linuxRoot/windows/setup-wsl.sh" "$linuxRoot"
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host ''
    Write-Host 'Windows-side setup completed successfully.' -ForegroundColor Green
} elseif ($code -eq 2) {
    Write-Host ''
    Write-Host 'Setup was cancelled before Linux prerequisites were installed.' -ForegroundColor Yellow
} else {
    Write-Host ''
    Write-Host "Setup returned exit code $code." -ForegroundColor Red
}

Pause-ForUser
exit $code
