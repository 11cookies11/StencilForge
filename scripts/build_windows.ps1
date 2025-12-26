$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Resolve-Path "$root\..")

Write-Host "== Build UI ==" -ForegroundColor Cyan
Push-Location ui-vue
if (!(Test-Path node_modules)) {
  npm install
}
npm run build
Pop-Location

Write-Host "== Build PyInstaller ==" -ForegroundColor Cyan
pyinstaller .\packaging\StencilForge.spec

Write-Host "Done. Output: .\dist\StencilForge" -ForegroundColor Green
