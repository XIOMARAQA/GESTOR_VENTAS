# Aplica migraciones Django a la BD de Render (después de makemigrations + migrate local).
#
# Opción A — archivo .env.render (recomendado):
#   copy .env.render.example .env.render
#   # editar DATABASE_URL con External Database URL de Render
#   .\scripts\migrate_render.ps1
#
# Opción B — variable en la sesión:
#   $env:DATABASE_URL = "postgresql://...@dpg-....oregon-postgres.render.com/gestor_ventas_db?sslmode=require"
#   .\scripts\migrate_render.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$envRender = Join-Path $PWD ".env.render"
if (Test-Path $envRender) {
    Get-Content $envRender | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
        $name, $value = $_ -split '=', 2
        [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
    }
    Write-Host "Cargado: .env.render" -ForegroundColor DarkGray
}

if (-not $env:DATABASE_URL) {
    Write-Host "ERROR: Defina DATABASE_URL en .env.render o en la sesión." -ForegroundColor Red
    exit 1
}

$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
Write-Host "Aplicando migraciones a Render..." -ForegroundColor Cyan
& $py manage.py migrate --noinput
exit $LASTEXITCODE
