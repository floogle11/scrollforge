param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cacheRoot = Join-Path $repoRoot '.cache\local-agent'
$checkout = Join-Path $cacheRoot 'checkout'
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$logPath = Join-Path $cacheRoot 'run.log'
$git = 'C:\Program Files\Git\cmd\git.exe'
$gh = 'C:\Program Files\GitHub CLI\gh.exe'
$codex = Join-Path $env:APPDATA 'npm\codex.cmd'

function Invoke-Git {
    param([string[]]$GitArgs)
    $savedAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $gitOutput = & $git @GitArgs 2>&1
        $gitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedAction
    }
    if ($gitCode -ne 0) { throw "Git failed (exit $gitCode) while running '$($GitArgs[-1])'." }
    return (($gitOutput | Out-String).Trim())
}

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Repository virtualenv Python is missing.' }
if (-not (Test-Path -LiteralPath $git -PathType Leaf)) { throw 'Git CLI is missing.' }
if (-not (Test-Path -LiteralPath $gh -PathType Leaf)) { throw 'GitHub CLI is missing.' }
if (-not (Test-Path -LiteralPath $codex -PathType Leaf)) { throw 'Codex CLI is missing.' }

$env:GIT_BIN = $git
$env:GH_BIN = $gh
$env:CODEX_BIN = $codex
$env:PATH = "C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI;C:\Program Files\nodejs;$env:PATH"

if ($DryRun) {
    if (-not (Test-Path -LiteralPath $checkout -PathType Container)) {
        throw 'The isolated checkout does not exist; dry-run will not clone or fetch it.'
    }
    $arguments = @('-m', 'worker.local_loop', '--dry-run')
} else {
    New-Item -ItemType Directory -Force -Path $cacheRoot | Out-Null
    if (-not (Test-Path -LiteralPath $checkout -PathType Container)) {
        $remote = Invoke-Git -GitArgs @('-C', $repoRoot, 'config', '--get', 'remote.origin.url')
        if ([string]::IsNullOrWhiteSpace($remote)) { throw 'Could not read the repository origin URL.' }
        Invoke-Git -GitArgs @('clone', '--', $remote, $checkout) | Out-Null
    }
    $checkoutItem = Get-Item -LiteralPath $checkout -Force
    if (($checkoutItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The isolated checkout path cannot be a junction or symbolic link.'
    }
    $checkoutFull = [IO.Path]::GetFullPath($checkout)
    $cacheFull = [IO.Path]::GetFullPath($cacheRoot)
    if (-not $checkoutFull.StartsWith($cacheFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Resolved isolated checkout is outside the local-agent cache.'
    }
    $origin = Invoke-Git -GitArgs @('-C', $repoRoot, 'config', '--get', 'remote.origin.url')
    $cloneOrigin = Invoke-Git -GitArgs @('-C', $checkout, 'config', '--get', 'remote.origin.url')
    if ($cloneOrigin -ne $origin) { throw 'The isolated checkout remote does not match this repository.' }
    $userName = Invoke-Git -GitArgs @('-C', $repoRoot, 'config', '--get', 'user.name')
    $userEmail = Invoke-Git -GitArgs @('-C', $repoRoot, 'config', '--get', 'user.email')
    if ([string]::IsNullOrWhiteSpace($userName) -or [string]::IsNullOrWhiteSpace($userEmail)) {
        throw 'Configure Git user.name and user.email in this repository before installing the loop.'
    }
    Invoke-Git -GitArgs @('-C', $checkout, 'config', '--local', 'user.name', $userName) | Out-Null
    Invoke-Git -GitArgs @('-C', $checkout, 'config', '--local', 'user.email', $userEmail) | Out-Null
    Invoke-Git -GitArgs @('-C', $checkout, 'config', '--local', 'credential.helper', '!gh auth git-credential') | Out-Null
    Invoke-Git -GitArgs @('-C', $checkout, 'fetch', '--prune') | Out-Null
    # Python handles only-fast-forward updates and recovery of cached feed commits.
    $arguments = @('-m', 'worker.local_loop', '--once', '--publish')
}

Push-Location $checkout
try {
    & $python @arguments 2>&1 | Out-File -FilePath $logPath -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Local loop exited with code $LASTEXITCODE." }
} finally {
    Pop-Location
}
