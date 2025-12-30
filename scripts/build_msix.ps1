param(
    [string]$Version = "0.1.8.0"
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

$Version = Normalize-Version $Version
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
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

Get-Content -Path $manifestTemplate -Raw |
    ForEach-Object { $_ -replace "__VERSION__", $Version } |
    Set-Content -Path $manifestTarget -Encoding utf8

@'
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:
    raise SystemExit("Pillow is required to generate MSIX assets.") from exc

assets = Path(r"__ASSETS__")
assets.mkdir(parents=True, exist_ok=True)

def make_square(size):
    img = Image.new("RGBA", (size, size), (37, 99, 235, 255))
    draw = ImageDraw.Draw(img)
    text = "SF"
    font = ImageFont.load_default()
    if hasattr(draw, "textbbox"):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = right - left, bottom - top
    else:
        text_w, text_h = draw.textsize(text, font=font)
    draw.text(((size - text_w) / 2, (size - text_h) / 2), text, fill=(255, 255, 255, 255), font=font)
    return img

def make_wide(width, height):
    img = Image.new("RGBA", (width, height), (37, 99, 235, 255))
    draw = ImageDraw.Draw(img)
    text = "StencilForge"
    font = ImageFont.load_default()
    if hasattr(draw, "textbbox"):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = right - left, bottom - top
    else:
        text_w, text_h = draw.textsize(text, font=font)
    draw.text(((width - text_w) / 2, (height - text_h) / 2), text, fill=(255, 255, 255, 255), font=font)
    return img

make_square(44).save(assets / "Square44x44Logo.png")
make_square(150).save(assets / "Square150x150Logo.png")
make_square(310).save(assets / "Square310x310Logo.png")
make_wide(310, 150).save(assets / "Wide310x150Logo.png")
make_square(50).save(assets / "StoreLogo.png")
'@ -replace "__ASSETS__", ($assetsRoot -replace "\\", "\\\\") | .\.venv\Scripts\python -

$makeappxPath = $null
$makeappxCmd = Get-Command makeappx.exe -ErrorAction SilentlyContinue
if ($makeappxCmd) {
    $makeappxPath = $makeappxCmd.Source
    if (-not $makeappxPath) {
        $makeappxPath = $makeappxCmd.Path
    }
    if (-not $makeappxPath) {
        $makeappxPath = $makeappxCmd.Definition
    }
}

$kitRoots = @(
    "C:\Program Files (x86)\Windows Kits\10\bin",
    "C:\Program Files\Windows Kits\10\bin"
)

if (-not $makeappxPath) {
    foreach ($root in $kitRoots) {
        if (-not (Test-Path $root)) {
            continue
        }
        $makeappx = Get-ChildItem $root -Recurse -Filter makeappx.exe |
            Where-Object { $_.FullName -match "\\x64\\makeappx.exe$" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($makeappx) {
            $makeappxPath = $makeappx.FullName
            break
        }
    }
}

if (-not $makeappxPath) {
    throw "makeappx.exe not found. Install Windows SDK (Windows 10/11) to build MSIX."
}

if (Test-Path $outputMsix) {
    Remove-Item $outputMsix -Force
}

& $makeappxPath pack /d $stageRoot /p $outputMsix /o | Out-Host
Write-Host "MSIX output: $outputMsix"
