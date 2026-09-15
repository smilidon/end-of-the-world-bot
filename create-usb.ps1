#requires -Version 5.1
# SPDX-License-Identifier: GPL-3.0-only
<#
.SYNOPSIS
Copy verified source/package files to a NEW folder on an already mounted drive.
.DESCRIPTION
Non-bootable data copy only. Never formats, partitions, writes raw devices,
downloads content, or installs a runtime. Bot execution/indexing requires Linux.
An optional, previously generated ReferenceHtml is copied as reference.html.
.EXAMPLE
.\create-usb.ps1 -Destination 'E:\EndOfWorldBot' -WhatIf
.EXAMPLE
.\create-usb.ps1 -Destination 'E:\EndOfWorldBot' -ReferenceHtml 'C:\Prepared\reference.html'
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string] $Destination,
    [string] $Source = $PSScriptRoot,
    [string] $ReferenceHtml
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-PortableName([string] $Name) {
    # Windows aliases, devices, ADS and case collisions must also be rejected
    # by the Linux fixture runner, not just by the Windows filesystem.
    foreach ($part in $Name.Split('/')) {
        if (-not $part -or $part -in '.', '..' -or
            $part -match '[\x00-\x1f<>:"\\|?*]' -or $part -match '[. ]$' -or
            $part -match '^(?i:CON|PRN|AUX|NUL|CLOCK\$|CONIN\$|CONOUT\$|COM[0-9\u00b9\u00b2\u00b3]|LPT[0-9\u00b9\u00b2\u00b3])(?:\.|$)') {
            throw "Unsafe Windows file name: $Name"
        }
    }
}

function Get-LocalPath([string] $Value) {
    if ([IO.Path]::DirectorySeparatorChar -eq '\') {
        if ($Value -notmatch '^[A-Za-z]:[\\/]') {
            throw 'Use an absolute local drive path, for example E:\EndOfWorldBot; no UNC or device paths.'
        }
        Assert-PortableName ($Value.Substring(3).Replace('\', '/').TrimEnd('/'))
    } elseif (-not $Value.StartsWith('/') -or $Value.StartsWith('//')) {
        throw 'Use an absolute local filesystem path.'
    }
    return [IO.Path]::GetFullPath($Value)
}

function Assert-NoLinks([string] $Path) {
    $current = $Path
    while ($current) {
        $item = Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
        if ($null -ne $item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Symlinks/junctions/reparse points are not supported: $current"
        }
        $current = [IO.Path]::GetDirectoryName($current)
    }
}

function Get-PackageFile([string] $Name) {
    Assert-PortableName $Name
    $path = [IO.Path]::Combine($sourcePath, $Name)
    Assert-NoLinks $path
    if (-not [IO.File]::Exists($path)) { throw "Package file missing: $Name" }
    return $path
}

$staging = $null
try {
    $sourcePath = Get-LocalPath $Source
    $target = Get-LocalPath $Destination
    Assert-NoLinks $sourcePath
    Assert-NoLinks $target
    if (-not [IO.Directory]::Exists($sourcePath)) { throw 'Source must be an extracted package or source folder.' }
    if (Test-Path -LiteralPath $target) { throw 'Destination already exists; choose a NEW folder. Nothing overwritten.' }
    $parent = [IO.Path]::GetDirectoryName($target)
    if (-not $parent -or -not [IO.Directory]::Exists($parent)) {
        throw 'Destination parent must already exist on a mounted drive.'
    }
    $sourcePrefix = $sourcePath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if ($target.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Destination must be outside the source folder.'
    }

    $names = [IO.File]::ReadAllLines((Get-PackageFile 'RELEASE_FILES.txt'))
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($name in $names) {
        Assert-PortableName $name
        if (-not $seen.Add($name)) { throw "Duplicate/case-colliding package path: $name" }
    }
    if (-not $seen.Contains('FILE_MANIFEST.sha256') -or -not $seen.Contains('RELEASE_FILES.txt')) {
        throw 'Invalid package allowlist: missing manifests.'
    }
    $hashes = @{}
    foreach ($line in [IO.File]::ReadAllLines((Get-PackageFile 'FILE_MANIFEST.sha256'))) {
        if ($line -cnotmatch '^([0-9a-f]{64})  (.+)$') { throw 'Invalid checksum manifest.' }
        $digest, $name = $Matches[1], $Matches[2]
        if ($hashes.ContainsKey($name) -or -not $seen.Contains($name) -or $name -eq 'FILE_MANIFEST.sha256') {
            throw 'Checksum manifest does not match allowlist.'
        }
        $hashes[$name] = $digest
    }
    if ($hashes.Count -ne $names.Count - 1) { throw 'Checksum manifest does not match allowlist.' }

    $files = @()
    foreach ($name in $names) {
        $path = Get-PackageFile $name
        $digest = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($name -ne 'FILE_MANIFEST.sha256' -and $digest -ne $hashes[$name]) {
            throw "Package checksum mismatch: $name"
        }
        $files += [pscustomobject]@{ Name = $name; Path = $path; Hash = $digest }
    }
    if ($ReferenceHtml) {
        if ($seen.Contains('reference.html')) { throw 'Package already contains reference.html.' }
        $page = Get-LocalPath $ReferenceHtml
        Assert-NoLinks $page
        if (-not [IO.File]::Exists($page) -or [IO.Path]::GetExtension($page) -ne '.html') {
            throw 'ReferenceHtml must be an existing, trusted Linux-generated HTML export.'
        }
        $files += [pscustomobject]@{ Name = 'reference.html'; Path = $page; Hash = (Get-FileHash -LiteralPath $page -Algorithm SHA256).Hash }
    }

    Write-Output "Source: $sourcePath"
    Write-Output "Destination: $target"
    Write-Output "Verified package; copying $($files.Count) files. Non-bootable. Bot runtime: Linux only."
    if (-not $ReferenceHtml) { Write-Output 'No reference.html selected: this copy will have no Windows reference reader/content.' }
    if (-not $PSCmdlet.ShouldProcess($target, 'Copy into a NEW data folder (no formatting or boot setup)')) { return }

    # Stage alongside the target; Directory.Move refuses an existing destination.
    # No recursive source copy, overwrite option, deletion, or raw device access.
    $staging = [IO.Path]::Combine($parent, '.end-of-world-copy-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $staging -ErrorAction Stop | Out-Null
    foreach ($file in $files) {
        Assert-NoLinks $file.Path
        Assert-NoLinks $staging
        $output = [IO.Path]::Combine($staging, $file.Name)
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($output)) | Out-Null
        [IO.File]::Copy($file.Path, $output, $false)
        if ((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash -ne $file.Hash) {
            throw "Copied checksum mismatch (source may have changed): $($file.Name)"
        }
    }
    Assert-NoLinks $target
    [IO.Directory]::Move($staging, $target)
    $staging = $null
    Write-Output "Copy complete: $target"
    if ($ReferenceHtml) { Write-Output 'Windows: open reference.html in a browser for static excerpts/search/printing only.' }
    Write-Output 'Linux: see START_HERE.md for runtime prerequisites and launch.sh. Safely eject the drive when finished.'
} catch {
    if ($staging) { Write-Warning "Copy incomplete. Partial files retained at: $staging. Inspect/remove that folder manually, fix the cause, then retry with a NEW destination." }
    Write-Error $_
    exit 1
}
