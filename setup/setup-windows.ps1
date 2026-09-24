# One-time setup on Windows. Run setup\setup-windows.bat (double-click), or let the AI agent run:
#     powershell -ExecutionPolicy Bypass -File setup\setup-windows.ps1
# Installs everything INTO this folder (.tools\, .pixi\, models\, engine\remotion\node_modules).
# Needs internet once (~2.5 GB of downloads). No admin rights, no API keys.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PIXI_HOME = Join-Path $Root ".tools\pixi-home"
$Pixi = Join-Path $Root ".tools\pixi.exe"

Write-Host "== 1/5 pixi (the folder's own package manager)"
New-Item -ItemType Directory -Force -Path (Join-Path $Root ".tools") | Out-Null
if (-not (Test-Path $Pixi)) {
  $zip = Join-Path $env:TEMP "pixi.zip"
  Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-pc-windows-msvc.zip" -OutFile $zip
  Expand-Archive -Force -Path $zip -DestinationPath (Join-Path $Root ".tools")
}

Write-Host "== 2/5 Python, Manim, ffmpeg, Node, VieNeu (from the lockfile)"
& $Pixi install
if ($LASTEXITCODE -ne 0) { throw "pixi install failed" }

Write-Host "== 3/5 Remotion"
Push-Location (Join-Path $Root "engine\remotion")
& $Pixi run --manifest-path (Join-Path $Root "pixi.toml") npm ci --no-audit --no-fund
& $Pixi run --manifest-path (Join-Path $Root "pixi.toml") npx remotion browser ensure
Pop-Location

Write-Host "== 4/5 Voice models (downloaded once into models\)"
& $Pixi run python run.py warmup

Write-Host "== 5/5 Check"
& (Join-Path $Root "os.cmd") doctor
