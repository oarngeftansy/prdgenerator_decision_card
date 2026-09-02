param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000,
    [string]$LarkCliPath = $env:LARK_CLI_EXECUTABLE
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = "$root;$root\.runtime312;$root\runtime_packages"
$bundledNodeDir = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin"
if (Test-Path -LiteralPath $bundledNodeDir) {
    $env:PATH = "$bundledNodeDir;$env:PATH"
}
Set-Location $root

$bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$python = Get-Command python -ErrorAction SilentlyContinue
if (Test-Path -LiteralPath $bundledPython) {
    $pythonPath = $bundledPython
} elseif ($python) {
    $pythonPath = $python.Source
} else {
    $pythonPath = ""
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python runtime was not found."
}

if (-not $LarkCliPath) {
    $larkCommand = Get-Command lark-cli.cmd -ErrorAction SilentlyContinue
    if ($larkCommand) { $LarkCliPath = $larkCommand.Source }
}
if (-not $LarkCliPath) {
    $documents = [Environment]::GetFolderPath('MyDocuments')
    $commonLarkCli = Join-Path $documents '飞书机器人（jojo）\node_modules\.bin\lark-cli.CMD'
    if (Test-Path -LiteralPath $commonLarkCli) { $LarkCliPath = $commonLarkCli }
}
if ($LarkCliPath -and (Test-Path -LiteralPath $LarkCliPath)) {
    $env:LARK_CLI_EXECUTABLE = $LarkCliPath
}

# canonical_api_server is the sole production launcher. It composes the stable
# backend infrastructure with Gameplay Understanding v1.2, canonical planning,
# P7 snapshot rendering and canonical Feishu publication authority.
& $pythonPath -m uvicorn canonical_api_server:app --host $HostAddress --port $Port
