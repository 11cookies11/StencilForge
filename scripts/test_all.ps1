param(
  [switch]$InstallBrowsers,
  [switch]$SkipPython,
  [switch]$SkipFrontend
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Run-Step {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][scriptblock]$Action
  )

  Write-Host ""
  Write-Host "==> $Name"
  & $Action
  if ($LASTEXITCODE -ne 0) {
    throw "Step failed: $Name (exit code $LASTEXITCODE)"
  }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
  if (-not $SkipPython) {
    Run-Step -Name "Python tests" -Action {
      python -m pytest -q
    }
  }

  if (-not $SkipFrontend) {
    Push-Location (Join-Path $repoRoot "ui-vue")
    try {
      if ($InstallBrowsers) {
        Run-Step -Name "Install Playwright browsers" -Action {
          npx playwright install
        }
      }

      Run-Step -Name "Frontend test:all" -Action {
        npm run test:all
      }
    }
    finally {
      Pop-Location
    }
  }

  Write-Host ""
  Write-Host "All requested tests passed."
}
finally {
  Pop-Location
}
