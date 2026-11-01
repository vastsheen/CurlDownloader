# Build CurlDownloader.exe (onedir) and deploy it to the project root.
# Native tools (pip / PyInstaller) write progress to stderr, so this script
# deliberately avoids $ErrorActionPreference = "Stop" and checks $LASTEXITCODE
# after every native call instead.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$BinDir = Join-Path $Root "bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$YtdlpPath = Join-Path $BinDir "yt-dlp.exe"
if (-not (Test-Path $YtdlpPath)) {
    Write-Host "bin\yt-dlp.exe is missing; downloading it as a fallback..."
    Invoke-WebRequest -Uri "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" -OutFile $YtdlpPath
}

foreach ($binary in @("yt-dlp.exe", "ffmpeg.exe", "aria2c.exe")) {
    $path = Join-Path $BinDir $binary
    if (-not (Test-Path $path)) {
        throw "Missing $path. See the README 'Dependencies' section for a download link."
    }
}

Write-Host "Installing pyinstaller..."
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit code $LASTEXITCODE" }

Write-Host "Building exe..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "CurlDownloader" `
    --paths "." `
    --add-data "bin/yt-dlp.exe;bin" `
    --add-data "bin/ffmpeg.exe;bin" `
    --add-data "bin/aria2c.exe;bin" `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$DistDir = Join-Path $Root "dist\CurlDownloader"
if (-not (Test-Path (Join-Path $DistDir "CurlDownloader.exe"))) {
    throw "Build failed: $DistDir\CurlDownloader.exe not found"
}

# Deploy to the project root: <root>\CurlDownloader.exe
# While the app is running Windows locks the runtime DLLs, and a failed copy used
# to leave a mix of old and new files ("Failed to import encodings module").
$running = @(Get-Process -Name "CurlDownloader" -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    throw "CurlDownloader.exe is running (PID $($running.Id -join ', ')). Close it and build again."
}

$ExeTarget = Join-Path $Root "CurlDownloader.exe"
$InternalSrc = Join-Path $DistDir "_internal"
$InternalTarget = Join-Path $Root "_internal"

if (Test-Path $ExeTarget) { Remove-Item $ExeTarget -Force -ErrorAction Stop }

if (Test-Path $InternalTarget) {
    Remove-Item $InternalTarget -Recurse -Force -ErrorAction Stop
}
if (Test-Path $InternalTarget) {
    throw "Could not remove $InternalTarget. Close anything using it and build again."
}

Copy-Item (Join-Path $DistDir "CurlDownloader.exe") $ExeTarget -Force -ErrorAction Stop
Copy-Item $InternalSrc $InternalTarget -Recurse -Force -ErrorAction Stop

# Verify the deployed runtime instead of printing "Done" blindly.
foreach ($required in @(
    (Join-Path $InternalTarget "base_library.zip"),
    (Join-Path $InternalTarget "bin\yt-dlp.exe"),
    (Join-Path $InternalTarget "bin\ffmpeg.exe"),
    (Join-Path $InternalTarget "bin\aria2c.exe")
)) {
    if (-not (Test-Path $required)) { throw "Deploy check failed: missing $required" }
}
if (Test-Path (Join-Path $InternalTarget "_internal")) {
    throw "Deploy check failed: nested _internal folder under $InternalTarget. Remove it and build again."
}

$srcCount = (Get-ChildItem $InternalSrc -Recurse -File -Force).Count
$dstCount = (Get-ChildItem $InternalTarget -Recurse -File -Force).Count
if ($srcCount -ne $dstCount) {
    throw "Deploy check failed: copied $dstCount of $srcCount runtime files."
}

$srcHash = (Get-FileHash (Join-Path $DistDir "CurlDownloader.exe") -Algorithm SHA256).Hash
$dstHash = (Get-FileHash $ExeTarget -Algorithm SHA256).Hash
if ($srcHash -ne $dstHash) {
    throw "Deploy check failed: deployed exe does not match the build output."
}

Write-Host ""
Write-Host "Done:"
Write-Host "  EXE: $ExeTarget"
Write-Host "  Runtime: $InternalTarget"
Write-Host ""
Write-Host "Bundled yt-dlp: $YtdlpPath"
Write-Host "Bundled ffmpeg: $(Join-Path $BinDir 'ffmpeg.exe')"
Write-Host "Bundled aria2c: $(Join-Path $BinDir 'aria2c.exe')"

# Completion marker: build.bat trusts this file, not the process exit code.
New-Item -ItemType File -Force (Join-Path $DistDir ".build-ok") | Out-Null
exit 0
