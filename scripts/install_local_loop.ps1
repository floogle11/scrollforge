$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repoRoot 'scripts\run_local_loop.ps1'
$git = 'C:\Program Files\Git\cmd\git.exe'
$cacheRoot = Join-Path $repoRoot '.cache\local-agent'
$checkout = Join-Path $cacheRoot 'checkout'
$taskName = 'ScrollForge Local Codex Loop'

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

if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) { throw 'Local loop launcher is missing.' }
if (-not (Test-Path -LiteralPath $git -PathType Leaf)) { throw 'Git CLI is missing.' }
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
$rootOrigin = Invoke-Git -GitArgs @('-C', $repoRoot, 'config', '--get', 'remote.origin.url')
$cloneOrigin = Invoke-Git -GitArgs @('-C', $checkout, 'config', '--get', 'remote.origin.url')
if ($cloneOrigin -ne $rootOrigin) { throw 'The isolated checkout remote does not match this repository.' }

$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$actionArgs = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $runner + '"'
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument $actionArgs
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $identity
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($atLogon, $repeat) -Principal $principal -Settings $settings -Description 'Runs ScrollForge from an isolated clone using the signed-in local Codex CLI.' -Force | Out-Null
Write-Output "Registered '$taskName' for $identity. It runs only while this user is logged in."
