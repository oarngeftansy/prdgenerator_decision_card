param(
    [string]$GitRemote = 'origin',
    [string]$GitBranch = 'codex/planner-decision-card',
    [Parameter(Mandatory = $true)]
    [string]$SvnUrl,
    [Parameter(Mandatory = $true)]
    [string]$SvnUsername,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = 'python'
$packageRelative = 'artifacts/svn-release-staging/ai_gamedesigntool'
$packagePath = Join-Path $repoRoot $packageRelative

$steps = @(
    'python -m pytest -q',
    "git push $GitRemote $GitBranch",
    'verify GitHub remote SHA equals local HEAD',
    'build_svn_release_package.ps1',
    'svn update/add/delete',
    'svn commit'
)
if ($DryRun) {
    [ordered]@{ dryRun = $true; orderedSteps = $steps; svnUrl = $SvnUrl; svnUsername = $SvnUsername } | ConvertTo-Json -Depth 5
    exit 0
}

if ((& git -C $repoRoot status --porcelain)) {
    throw 'Working tree is not clean; commit or intentionally exclude local changes before triple sync.'
}
& $python -m pytest -q -p no:cacheprovider --basetemp .test-tmp/triple-sync
if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }

$localSha = (& git -C $repoRoot rev-parse HEAD).Trim()
& git -C $repoRoot push $GitRemote $GitBranch
if ($LASTEXITCODE -ne 0) { throw 'git push failed; SVN write is blocked' }
$remoteSha = (& git -C $repoRoot ls-remote $GitRemote "refs/heads/$GitBranch").Split("`t")[0]
if ($remoteSha -ne $localSha) { throw 'GitHub remote SHA does not match local HEAD' }

if (Test-Path -LiteralPath $packagePath) {
    throw "Release staging already exists: $packagePath"
}
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'build_svn_release_package.ps1') -OutputPath $packageRelative
if ($LASTEXITCODE -ne 0) { throw 'release packaging failed' }

$svnCommand = Get-Command svn.exe -ErrorAction SilentlyContinue
if (-not $svnCommand) { throw 'svn.exe is required for guarded non-interactive synchronization' }
$secureCredential = Read-Host -AsSecureString 'SVN password'
$credentialPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureCredential)
try {
    $plainCredential = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($credentialPointer)
    $auth = @('--username', $SvnUsername, '--password', $plainCredential, '--non-interactive', '--trust-server-cert-failures', 'unknown-ca,cn-mismatch,expired,not-yet-valid,other')
    $rootEntries = & $svnCommand.Source ls $SvnUrl @auth
    if ($LASTEXITCODE -ne 0) { throw 'SVN read verification failed' }
    $baseUrl = $SvnUrl.TrimEnd('/')
    if ($rootEntries -contains 'trunk/') { $baseUrl += '/trunk' }
    $targetUrl = "$baseUrl/ai_gamedesigntool"
    $existing = & $svnCommand.Source info $targetUrl @auth 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $svnCommand.Source import $packagePath $targetUrl -m "Publish ai_gamedesigntool from Git $localSha" @auth
    }
    else {
        throw 'Existing SVN target requires a reviewed checkout/update workflow; no overwrite was attempted.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'svn commit/import failed' }
    [ordered]@{ localSha = $localSha; remoteSha = $remoteSha; svnUrl = $targetUrl; status = 'published' } | ConvertTo-Json -Depth 5
}
finally {
    if ($credentialPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($credentialPointer) }
    $plainCredential = $null
}
