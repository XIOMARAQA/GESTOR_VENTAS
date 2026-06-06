param(
    [switch]$CreateOwner,
    [switch]$SkipBootstrap
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not $env:DATABASE_URL) {
    Write-Host "ERROR: Defina DATABASE_URL (External Database URL de Render)." -ForegroundColor Red
    exit 1
}

$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$args = @("scripts\setup_render_db.py")
if ($CreateOwner) { $args += "--create-owner" }
if ($SkipBootstrap) { $args += "--skip-bootstrap" }

& $py @args
exit $LASTEXITCODE
