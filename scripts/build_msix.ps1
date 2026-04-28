param(
    [string]$Version = "0.1.8.0",
    [string]$IdentityName = $env:MSIX_IDENTITY_NAME,
    [string]$IdentityPublisher = $env:MSIX_IDENTITY_PUBLISHER,
    [string]$PublisherDisplayName = $env:MSIX_PUBLISHER_DISPLAY_NAME,
    [string]$SignCertPath = $env:MSIX_SIGN_CERT_PATH,
    [string]$SignCertPassword = $env:MSIX_SIGN_CERT_PASSWORD,
    [string]$SignCertBase64 = $env:MSIX_SIGN_CERT_BASE64,
    [string]$SignTimestampUrl = $env:MSIX_SIGN_TIMESTAMP_URL
)

$ErrorActionPreference = "Stop"

function Normalize-Version([string]$Value) {
    $clean = $Value.Trim()
    if ($clean.StartsWith("v")) {
        $clean = $clean.Substring(1)
    }
    $parts = $clean.Split(".")
    if ($parts.Length -eq 3) {
        return "$clean.0"
    }
    return $clean
}

function Resolve-SdkToolPath([string]$ToolName) {
    $toolPath = $null
    $toolCmd = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($toolCmd) {
        $toolPath = $toolCmd.Source
        if (-not $toolPath) {
            $toolPath = $toolCmd.Path
        }
        if (-not $toolPath) {
            $toolPath = $toolCmd.Definition
        }
    }

    $kitRoots = @(
        "C:\Program Files (x86)\Windows Kits\10\bin",
        "C:\Program Files\Windows Kits\10\bin"
    )

    if (-not $toolPath) {
        foreach ($root in $kitRoots) {
            if (-not (Test-Path $root)) {
                continue
            }
            $candidate = Get-ChildItem $root -Recurse -Filter $ToolName |
                Where-Object { $_.FullName -match ("\\x64\\" + [regex]::Escape($ToolName) + "$") } |
                Sort-Object FullName -Descending |
                Select-Object -First 1
            if ($candidate) {
                $toolPath = $candidate.FullName
                break
            }
        }
    }

    return $toolPath
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$brandingPath = Join-Path $projectRoot "packaging\branding.json"
$branding = if (Test-Path $brandingPath) {
    Get-Content -Path $brandingPath -Raw | ConvertFrom-Json
} else {
    throw "Missing branding file: $brandingPath"
}

$Version = Normalize-Version $Version
$IdentityName = if ([string]::IsNullOrWhiteSpace($IdentityName)) {
    if ($branding.msix_identity_name) { [string]$branding.msix_identity_name } else { "AD7477BB.StencilForge" }
} else {
    $IdentityName
}
$IdentityPublisher = if ([string]::IsNullOrWhiteSpace($IdentityPublisher)) {
    if ($branding.msix_identity_publisher) { [string]$branding.msix_identity_publisher } else { "CN=7FE71472-71A6-4A5E-8C37-0123AD823583" }
} else {
    $IdentityPublisher
}
$AppName = if ($branding.app_name) { [string]$branding.app_name } else { "StencilForge" }
$AppDescription = if ($branding.app_description) { [string]$branding.app_description } else { "PCB stencil and fixture generator" }
$PublisherDisplayName = if ([string]::IsNullOrWhiteSpace($PublisherDisplayName)) {
    if ($branding.publisher_display_name) { [string]$branding.publisher_display_name } else { $AppName }
} else {
    $PublisherDisplayName
}
$distRoot = Join-Path $projectRoot "dist\StencilForge"
if (-not (Test-Path $distRoot)) {
    throw "Missing dist output: $distRoot. Run scripts/build_windows.ps1 first."
}

$msixRoot = Join-Path $projectRoot "dist-msix"
$stageRoot = Join-Path $msixRoot "stage"
$outputMsix = Join-Path $msixRoot ("StencilForge_" + $Version + "_x64.msix")
$assetsRoot = Join-Path $stageRoot "Assets"

if (Test-Path $stageRoot) {
    Remove-Item $stageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $assetsRoot -Force | Out-Null

Copy-Item -Path (Join-Path $distRoot "*") -Destination $stageRoot -Recurse -Force

$manifestTemplate = Join-Path $projectRoot "packaging\msix\AppxManifest.xml"
$manifestTarget = Join-Path $stageRoot "AppxManifest.xml"
if (-not (Test-Path $manifestTemplate)) {
    throw "Missing manifest template: $manifestTemplate"
}

$manifestContent = Get-Content -Path $manifestTemplate -Raw
$manifestContent = $manifestContent.Replace("__VERSION__", $Version)
$manifestContent = $manifestContent.Replace("__IDENTITY_NAME__", $IdentityName)
$manifestContent = $manifestContent.Replace("__IDENTITY_PUBLISHER__", $IdentityPublisher)
$manifestContent = $manifestContent.Replace("__APP_NAME__", $AppName)
$manifestContent = $manifestContent.Replace("__APP_DESCRIPTION__", $AppDescription)
$manifestContent = $manifestContent.Replace("__PUBLISHER_DISPLAY_NAME__", $PublisherDisplayName)
Set-Content -Path $manifestTarget -Value $manifestContent -Encoding utf8

@'
from pathlib import Path

try:
    from PIL import Image, ImageOps
except Exception as exc:
    raise SystemExit("Pillow is required to generate MSIX assets.") from exc

assets = Path(r"__ASSETS__")
assets.mkdir(parents=True, exist_ok=True)
source_dir = Path(r"__SOURCE__")

def load_source(name):
    path = source_dir / name
    if not path.exists():
        raise SystemExit(f"Missing source asset: {path}")
    return Image.open(path).convert("RGBA")

def fit_to_canvas(source, size):
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    fitted = ImageOps.contain(source, size, Image.Resampling.LANCZOS)
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (x, y), fitted)
    return canvas

square_source = load_source("logo_1080x1080.png")
wide_source = load_source("logo_1920x1080.png")
store_source = load_source("logo_300x300.png")

fit_to_canvas(square_source, (44, 44)).save(assets / "Square44x44Logo.png")
fit_to_canvas(square_source, (150, 150)).save(assets / "Square150x150Logo.png")
fit_to_canvas(square_source, (310, 310)).save(assets / "Square310x310Logo.png")
fit_to_canvas(wide_source, (310, 150)).save(assets / "Wide310x150Logo.png")
fit_to_canvas(store_source, (50, 50)).save(assets / "StoreLogo.png")
'@ -replace "__ASSETS__", ($assetsRoot -replace "\\", "\\\\") -replace "__SOURCE__", ((Join-Path $projectRoot "assets\store") -replace "\\", "\\\\") | python -

$makeappxPath = Resolve-SdkToolPath "makeappx.exe"

if (-not $makeappxPath) {
    throw "makeappx.exe not found. Install Windows SDK (Windows 10/11) to build MSIX."
}

if (Test-Path $outputMsix) {
    Remove-Item $outputMsix -Force
}

& $makeappxPath pack /d $stageRoot /p $outputMsix /o | Out-Host
Write-Host "MSIX output: $outputMsix"

$tempPfxPath = $null
$signingEnabled = -not [string]::IsNullOrWhiteSpace($SignCertPath) -or -not [string]::IsNullOrWhiteSpace($SignCertBase64)

if ($signingEnabled) {
    if ([string]::IsNullOrWhiteSpace($SignCertPath) -and -not [string]::IsNullOrWhiteSpace($SignCertBase64)) {
        $tempPfxPath = Join-Path $env:TEMP ("stencilforge-msix-signing-" + [Guid]::NewGuid().ToString() + ".pfx")
        [IO.File]::WriteAllBytes($tempPfxPath, [Convert]::FromBase64String($SignCertBase64))
        $SignCertPath = $tempPfxPath
    }

    if ([string]::IsNullOrWhiteSpace($SignCertPassword)) {
        throw "MSIX signing requested but MSIX_SIGN_CERT_PASSWORD is empty."
    }

    if (-not (Test-Path $SignCertPath)) {
        throw "MSIX signing certificate not found: $SignCertPath"
    }

    $signtoolPath = Resolve-SdkToolPath "signtool.exe"
    if (-not $signtoolPath) {
        throw "signtool.exe not found. Install Windows SDK (Windows 10/11) to sign MSIX."
    }

    $signArgs = @("sign", "/fd", "SHA256", "/f", $SignCertPath, "/p", $SignCertPassword)
    if (-not [string]::IsNullOrWhiteSpace($SignTimestampUrl)) {
        $signArgs += @("/tr", $SignTimestampUrl, "/td", "SHA256")
    }
    $signArgs += $outputMsix

    try {
        & $signtoolPath @signArgs | Out-Host
    }
    finally {
        if ($tempPfxPath -and (Test-Path $tempPfxPath)) {
            Remove-Item $tempPfxPath -Force
        }
    }

    Write-Host "MSIX signing: enabled"
}
else {
    Write-Host "MSIX signing: disabled (unsigned package)"
}
