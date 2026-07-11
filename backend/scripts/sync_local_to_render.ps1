# Copia PostgreSQL local (esquema gestorVentas) → Render.
#
# 1. copy .env.render.example .env.render
# 2. Editar .env.render con External Database URL de Render (+ ?sslmode=require)
# 3. .\scripts\sync_local_to_render.ps1

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

$py = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
& $py scripts/sync_local_to_render.py @args
exit $LASTEXITCODE
