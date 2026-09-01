param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$manifestPath = Join-Path $repoRoot 'config\svn-release-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Get-CompatibleRelativePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\', '/'))
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    $prefix = $rootFull + [System.IO.Path]::DirectorySeparatorChar
    if (-not $pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escaped expected root: $pathFull"
    }
    return $pathFull.Substring($prefix.Length)
}

function Copy-FilteredTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Get-ChildItem -LiteralPath $Source -Recurse -Force | ForEach-Object {
        $relative = Get-CompatibleRelativePath -Root $Source -Path $_.FullName
        $parts = $relative -split '[\\/]'
        $excluded = $false
        foreach ($part in $parts) {
            if ($manifest.excludeNames -contains $part) {
                $excluded = $true
                break
            }
        }
        if ($excluded) { return }

        $destinationPath = Join-Path $Destination $relative
        if ($_.PSIsContainer) {
            New-Item -ItemType Directory -Path $destinationPath -Force | Out-Null
        }
        else {
            $parent = Split-Path -Parent $destinationPath
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $_.FullName -Destination $destinationPath
        }
    }
}
$target = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputPath))
$artifactsRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'artifacts'))
if (-not $target.StartsWith($artifactsRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutputPath must resolve under the repository artifacts directory.'
}
if (Test-Path -LiteralPath $target) {
    throw "OutputPath already exists; choose a new empty staging path: $target"
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ai-gamedesigntool-" + [guid]::NewGuid().ToString('N'))
$archivePath = Join-Path $tempRoot 'head.zip'
New-Item -ItemType Directory -Path $tempRoot | Out-Null
New-Item -ItemType Directory -Path $target -Force | Out-Null
try {
    & git -C $repoRoot archive --format=zip --output=$archivePath HEAD
    if ($LASTEXITCODE -ne 0) { throw 'git archive HEAD failed' }
    Expand-Archive -LiteralPath $archivePath -DestinationPath $target

    foreach ($dependencyRoot in $manifest.dependencyRoots) {
        $source = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $dependencyRoot))
        if (-not $source.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Dependency path escaped repository: $dependencyRoot"
        }
        if (-not (Test-Path -LiteralPath $source -PathType Container)) {
            throw "Missing dependency root: $dependencyRoot"
        }
        Copy-FilteredTree -Source $source -Destination (Join-Path $target $dependencyRoot)
    }

    $forbidden = @()
    Get-ChildItem -LiteralPath $target -Recurse -Force | ForEach-Object {
        if ($manifest.excludeNames -contains $_.Name) { $forbidden += $_.FullName }
        if ($manifest.allowedSecretTemplateNames -notcontains $_.Name) {
            foreach ($pattern in $manifest.secretPatterns) {
                if ($_.Name -like $pattern) { $forbidden += $_.FullName }
            }
        }
    }
    if ($forbidden.Count -gt 0) {
        throw ("Release package contains excluded or sensitive paths:`n" + ($forbidden -join "`n"))
    }
    foreach ($entryPoint in $manifest.requiredEntryPoints) {
        if (-not (Test-Path -LiteralPath (Join-Path $target $entryPoint) -PathType Leaf)) {
            throw "Missing required entry point: $entryPoint"
        }
    }

    $commit = (& git -C $repoRoot rev-parse HEAD).Trim()
    $releaseManifest = [ordered]@{
        schemaVersion = 'svn-release-package-v1'
        sourceCommit = $commit
        generatedAtUtc = [DateTime]::UtcNow.ToString('o')
        sourceMode = $manifest.sourceMode
        dependencyRoots = @($manifest.dependencyRoots)
        secretFindingCount = 0
        excludedPathCount = 0
    }
    $releaseManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $target 'release-manifest.json') -Encoding UTF8

    $hashes = [ordered]@{}
    Get-ChildItem -LiteralPath $target -Recurse -File | Sort-Object FullName | ForEach-Object {
        $relative = (Get-CompatibleRelativePath -Root $target -Path $_.FullName).Replace('\', '/')
        if ($relative -ne 'sha256sums.json') {
            $hashes[$relative] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $hashes | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $target 'sha256sums.json') -Encoding UTF8
    [ordered]@{ outputPath = $target; sourceCommit = $commit; fileCount = $hashes.Count; dependencyRoots = @($manifest.dependencyRoots) } | ConvertTo-Json -Depth 5
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
