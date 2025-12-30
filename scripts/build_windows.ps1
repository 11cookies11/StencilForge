$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Resolve-Path "$root\.." | ForEach-Object { Join-Path $_ "build-logs" }
if (!(Test-Path $logDir)) {
  New-Item -ItemType Directory -Path $logDir | Out-Null
}
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logPath = Join-Path $logDir "build-$stamp.log"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

function Write-LogHeading([string]$text) {
  Write-Host $text -ForegroundColor Cyan
  Add-Content -Path $logPath -Value $text -Encoding utf8
}

function Invoke-Logged([scriptblock]$command, [string]$label) {
  Write-LogHeading $label
  $prevPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $output = & $command 2>&1 | Out-String
    if ($output) {
      Add-Content -Path $logPath -Value $output -Encoding utf8
      $output | Write-Host
    }
  }
  finally {
    $ErrorActionPreference = $prevPreference
  }
  if ($LASTEXITCODE -ne 0) {
    throw "$label failed with exit code $LASTEXITCODE"
  }
}

try {
  Set-Location (Resolve-Path "$root\..")

$venvPath = Resolve-Path ".\.venv" -ErrorAction SilentlyContinue
if (-not $venvPath) {
  python -m venv .venv
  $venvPath = Resolve-Path ".\.venv"
}
$python = Join-Path $venvPath "Scripts\python.exe"

Push-Location ui-vue
if (!(Test-Path node_modules)) {
  Invoke-Logged { npm install } "== Build UI: npm install =="
}
Invoke-Logged { npm run build } "== Build UI: npm run build =="
Pop-Location

Invoke-Logged { & $python -m pip install --upgrade pip } "== Build PyInstaller: pip upgrade =="
Invoke-Logged { & $python -m pip install -r requirements.txt pyinstaller } "== Build PyInstaller: pip install =="
Invoke-Logged { & $python -c "import shapely" } "== Build PyInstaller: check shapely =="
Invoke-Logged { & $python -c "import cadquery, OCP" } "== Build PyInstaller: check cadquery =="
Invoke-Logged { & $python -c "import casadi" } "== Build PyInstaller: check casadi =="
Invoke-Logged { & $python -m PyInstaller .\packaging\StencilForge.spec } "== Build PyInstaller: build =="

Write-Host "Done. Output: .\dist\StencilForge" -ForegroundColor Green
}
finally {
  Write-Host "Build log saved to: $logPath" -ForegroundColor Yellow
}
