param(
    [Parameter(Mandatory = $true)][string]$Configuration,
    [ValidateSet('source', 'packaged')][string]$Mode = 'source',
    [ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Run = ('code-ui-' + (Get-Date -Format 'yyyyMMdd-HHmmss')),
    [ValidatePattern('^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')][string]$QueryId,
    [ValidatePattern('^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')][string]$ExpectedKnowledgeRevision
)
$ErrorActionPreference = 'Stop'
$workspacePath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$nodeExecutable = 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
$playwrightModule = 'C:/Users/DaydreamBlend/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$configurationPath = (Resolve-Path -LiteralPath $Configuration).Path
foreach ($requiredPath in @($nodeExecutable, $playwrightModule)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) { throw "Prepared runtime missing: $requiredPath" }
}
$env:PALIMPSEST_WORKSPACE = $workspacePath
$env:PALIMPSEST_DESKTOP_CONFIG = $configurationPath
$env:PALIMPSEST_PLAYWRIGHT_MODULE = $playwrightModule
$env:PALIMPSEST_UI_RUN = $Run
[Environment]::SetEnvironmentVariable('PALIMPSEST_UI_QUERY_ID', $QueryId, 'Process')
[Environment]::SetEnvironmentVariable('PALIMPSEST_UI_K_REVISION', $ExpectedKnowledgeRevision, 'Process')
if ($Mode -eq 'packaged') {
    $packageExecutable = Join-Path $workspacePath 'output/t13-code-review-ui/app/Palimpsest-win32-x64/Palimpsest.exe'
    if (-not (Test-Path -LiteralPath $packageExecutable)) { throw 'The 0.2.0 package has not been prepared.' }
    $env:PALIMPSEST_ELECTRON_EXECUTABLE = $packageExecutable
} else {
    [Environment]::SetEnvironmentVariable('PALIMPSEST_ELECTRON_EXECUTABLE', $null, 'Process')
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $dockerDirectory = 'C:/Program Files/Docker/Docker/resources/bin'
    if (-not (Test-Path -LiteralPath (Join-Path $dockerDirectory 'docker.exe'))) { throw 'Docker CLI is not available.' }
    $env:PATH = $dockerDirectory + [System.IO.Path]::PathSeparator + $env:PATH
}
Push-Location $workspacePath
try {
    & $nodeExecutable (Join-Path $workspacePath 'desktop/test/electron-knowledge-ui.cjs')
    if ($LASTEXITCODE -ne 0) { throw "Electron UI check failed with exit $LASTEXITCODE" }
} finally {
    Pop-Location
}
