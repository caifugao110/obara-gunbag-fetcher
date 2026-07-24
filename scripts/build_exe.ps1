#Requires -Version 5.1
param(
    [string]$ProjectDir = $PSScriptRoot,
    [switch]$SkipCleanup
)

$ErrorActionPreference = "Stop"

$ProjectDir = Resolve-Path $ProjectDir
$VenvDir = Join-Path $ProjectDir ".venv"
$DistDir = Join-Path $ProjectDir "dist"
$BuildDir = Join-Path $ProjectDir "build"

function Write-Info ($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success ($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn ($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

Write-Info "Project directory: $ProjectDir"

# Step 1: Create virtual environment
if (Test-Path $VenvDir) {
    Write-Warn "Removing existing .venv..."
    Remove-Item -Recurse -Force $VenvDir
}
Write-Info "Creating virtual environment..."
python -m venv $VenvDir

# Step 2: Install dependencies
$pip = Join-Path $VenvDir "Scripts\pip.exe"
& $pip install --upgrade pip | Out-Null
& $pip install -r (Join-Path $ProjectDir "requirements.txt") | Out-Null
& $pip install pyinstaller | Out-Null
Write-Success "Dependencies installed"

# Step 3: Build with PyInstaller
$pyi = Join-Path $VenvDir "Scripts\pyinstaller.exe"
$SpecFile = Join-Path $ProjectDir "obara-gunbag-fetcher.spec"

$PyInstallerArgs = @(
    "--name", "obara-gunbag-fetcher",
    "--onefile",
    "--windowed",
    "--clean",
    "--noconfirm",
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--specpath", $ProjectDir,
    "--add-data", "config.ini;."
)

$iconPath = Join-Path $ProjectDir "assets" "app.ico"
if (Test-Path $iconPath) {
    $PyInstallerArgs += "--icon"
    $PyInstallerArgs += $iconPath
}

$PyInstallerArgs += (Join-Path $ProjectDir "app.py")

Write-Info "Running PyInstaller..."
& $pyi @PyInstallerArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# Step 4: Copy additional files to dist
$assetsDest = Join-Path $DistDir "assets"
if (-not (Test-Path $assetsDest)) { New-Item -ItemType Directory -Path $assetsDest | Out-Null }
$iconSrc = Join-Path $ProjectDir "assets" "app.ico"
if (Test-Path $iconSrc) { Copy-Item $iconSrc $assetsDest -Force }

Write-Success "Build completed: $DistDir\obara-gunbag-fetcher.exe"

# Step 5: Cleanup
if (-not $SkipCleanup) {
    Write-Info "Cleaning up..."
    $itemsToRemove = @($VenvDir, $BuildDir, $SpecFile)
    foreach ($item in $itemsToRemove) {
        if (Test-Path $item) {
            Remove-Item -Recurse -Force $item
        }
    }
    Write-Success "Cleanup done"
}

Write-Success "All done!"
