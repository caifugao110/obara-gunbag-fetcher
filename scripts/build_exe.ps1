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

# Locate a working Python interpreter
$PythonExes = @(
    (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    (Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "C:\Python313\python.exe",
    "C:\Python312\python.exe",
    "C:\Python311\python.exe"
)
$SystemPython = $null
foreach ($py in $PythonExes) {
    if ($py -and (Test-Path $py)) {
        Write-Info "Found Python: $py"
        $SystemPython = $py
        break
    }
}
if (-not $SystemPython) {
    throw "Python interpreter not found. Please install Python 3.9+ and ensure it's in PATH."
}

# Step 1: Create virtual environment
if (Test-Path $VenvDir) {
    Write-Warn "Removing existing .venv..."
    Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
    if (Test-Path $VenvDir) {
        Remove-Item -Recurse -Force $VenvDir
    }
}
Write-Info "Creating virtual environment..."
& $SystemPython -m venv $VenvDir
if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment" }

# Step 2: Install dependencies
$pythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) { throw "venv python.exe not found: $pythonExe" }

Write-Info "Upgrading pip..."
& $pythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip" }

Write-Info "Installing project dependencies..."
& $pythonExe -m pip install -r (Join-Path $ProjectDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Failed to install project dependencies" }

Write-Info "Installing PyInstaller..."
& $pythonExe -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Failed to install PyInstaller" }

Write-Info "Verifying PyInstaller installation..."
& $pythonExe -c "import PyInstaller; print(f'PyInstaller {PyInstaller.__version__} ready')"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller verification failed" }

Write-Success "Dependencies installed"

# Step 3: Build with PyInstaller (using python -m PyInstaller for reliability)
$SpecFile = Join-Path $ProjectDir "obara-gunbag-fetcher.spec"

$assetsDir = Join-Path $ProjectDir "assets"
$pyprojectToml = Join-Path $ProjectDir "pyproject.toml"
$configIni = Join-Path $ProjectDir "config.ini"
$originalListFile = Join-Path $ProjectDir "Original file list.txt"

# Step 3a: Auto-generate Windows version info from pyproject.toml
$versionFile = Join-Path $env:TEMP "obara_version_info.py"
Write-Info "Generating Windows version info from pyproject.toml..."

$pyprojectContent = Get-Content $pyprojectToml -Raw -ErrorAction Stop
$verMatch = [regex]::Match($pyprojectContent, '(?m)^version\s*=\s*"([^"]+)"')
$nameMatch = [regex]::Match($pyprojectContent, '(?m)^name\s*=\s*"([^"]+)"')
$authorMatch = [regex]::Match($pyprojectContent, '(?m)^authors\s*=\s*\[\{\s*name\s*=\s*"([^"]+)"')
$homepageMatch = [regex]::Match($pyprojectContent, '(?m)^Homepage\s*=\s*"([^"]+)"')

$version = if ($verMatch.Success) { $verMatch.Groups[1].Value } else { "1.0.0" }
$name = if ($nameMatch.Success) { $nameMatch.Groups[1].Value } else { "obara-gunbag-fetcher" }
$author = if ($authorMatch.Success) { $authorMatch.Groups[1].Value } else { "Unknown" }
$homepage = if ($homepageMatch.Success) { $homepageMatch.Groups[1].Value } else { "" }

$verParts = $version -split '\.'
$verMajor = [int]($verParts[0])
$verMinor = [int]($verParts[1])
$verPatch = if ($verParts.Count -gt 2) { [int]($verParts[2]) } else { 0 }

Write-Info "  Name: $name | Version: $version | Author: $author"

$versionInfoContent = @"
# Auto-generated from pyproject.toml - do not edit manually

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($verMajor, $verMinor, $verPatch, 0),
    prodvers=($verMajor, $verMinor, $verPatch, 0),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '0409B0',
          [
            StringStruct('CompanyName', '$author'),
            StringStruct('FileDescription', '$name'),
            StringStruct('FileVersion', '$version.0'),
            StringStruct('InternalName', '$name'),
            StringStruct('LegalCopyright', 'Copyright (C) 2026 $author. All rights reserved.'),
            StringStruct('OriginalFilename', '$name.exe'),
            StringStruct('ProductName', '$name'),
            StringStruct('ProductVersion', '$version.0')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@

$versionInfoContent | Set-Content -Path $versionFile -Encoding UTF8 -ErrorAction Stop
Write-Info "Version info written to: $versionFile"

$PyInstallerArgs = @(
    "-m", "PyInstaller",
    "--name", $name,
    "--onefile",
    "--windowed",
    "--noupx",
    "--clean",
    "--noconfirm",
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--specpath", $ProjectDir,
    "--add-data", "$assetsDir;assets",
    "--add-data", "$pyprojectToml;.",
    "--add-data", "$configIni;.",
    "--collect-data", "ttkbootstrap",
    "--collect-all", "requests",
    "--collect-all", "urllib3",
    "--hidden-import", "requests",
    "--hidden-import", "urllib3",
    "--hidden-import", "charset_normalizer",
    "--hidden-import", "idna",
    "--hidden-import", "certifi",
    "--version-file", $versionFile
)

$iconPath = Join-Path (Join-Path $ProjectDir "assets") "app.ico"
if (Test-Path $iconPath) {
    $PyInstallerArgs += "--icon"
    $PyInstallerArgs += $iconPath
}

$PyInstallerArgs += (Join-Path $ProjectDir "app.py")

Write-Info "Running PyInstaller..."
& $pythonExe @PyInstallerArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

# Cleanup temp version file
Remove-Item $versionFile -Force -ErrorAction SilentlyContinue

# Step 4: Copy additional files to dist and clean up leftover assets folder
if (Test-Path $configIni) { Copy-Item $configIni $DistDir -Force }
if (Test-Path $originalListFile) { Copy-Item $originalListFile $DistDir -Force }
$assetsDist = Join-Path $DistDir "assets"
if (Test-Path $assetsDist) {
    Write-Info "Removing leftover dist/assets folder..."
    Remove-Item -Recurse -Force $assetsDist
}

Write-Success "Build completed: $DistDir\$name.exe"

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
