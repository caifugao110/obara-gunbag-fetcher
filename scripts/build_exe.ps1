#Requires -Version 5.1
param(
    [string]$ProjectDir = (Split-Path $PSScriptRoot),
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
$pythonExe = Join-Path $VenvDir "Scripts\python.exe"
& $pythonExe -m pip install --upgrade pip | Out-Null
& $pythonExe -m pip install -r (Join-Path $ProjectDir "requirements.txt") | Out-Null
& $pythonExe -m pip install pyinstaller | Out-Null
Write-Success "Dependencies installed"

# Step 3: Build with PyInstaller
$pyi = Join-Path $VenvDir "Scripts\pyinstaller.exe"
$SpecFile = Join-Path $ProjectDir "obara-gunbag-fetcher.spec"

$assetsDir = Join-Path $ProjectDir "assets"
$pyprojectToml = Join-Path $ProjectDir "pyproject.toml"
$configIni = Join-Path $ProjectDir "config.ini"
$originalListFile = Join-Path $ProjectDir "Original file list.txt"
$PyInstallerArgs = @(
    "--name", "obara-gunbag-fetcher",
    "--onefile",
    "--windowed",
    "--clean",
    "--noconfirm",
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--specpath", $ProjectDir,
    "--add-data", "$assetsDir;assets",
    "--add-data", "$pyprojectToml;.",
    "--add-data", "$configIni;.",
    "--collect-data", "ttkbootstrap"
)

$iconPath = Join-Path (Join-Path $ProjectDir "assets") "app.ico"
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
$iconSrc = Join-Path (Join-Path $ProjectDir "assets") "app.ico"
if (Test-Path $iconSrc) { Copy-Item $iconSrc $assetsDest -Force }
if (Test-Path $configIni) { Copy-Item $configIni $DistDir -Force }
if (Test-Path $originalListFile) { Copy-Item $originalListFile $DistDir -Force }

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
