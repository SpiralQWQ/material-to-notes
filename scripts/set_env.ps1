# Load the local .env into the current PowerShell session (PowerShell 5.1).
#
#   . .\scripts\set_env.ps1      # dot-source so the variables survive
#
# Values are never printed, so the script is safe to run in a shared terminal.

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot '.env'

if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Warning ".env not found at $envFile - copy .env.example and fill it in"
    return
}

$loaded = 0
Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq '' -or $line.StartsWith('#')) { return }
    $sep = $line.IndexOf('=')
    if ($sep -lt 1) { return }
    $name = $line.Substring(0, $sep).Trim()
    $value = $line.Substring($sep + 1).Trim()
    Set-Item -LiteralPath "Env:$name" -Value $value
    $loaded = $loaded + 1
    Write-Host "set $name"
}

Write-Host "loaded $loaded variable(s) from $envFile"
