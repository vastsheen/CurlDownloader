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
$ExeTarget = Join-Path $Root "CurlDownloader.exe"
Copy-Item (Join-Path $DistDir "CurlDownloader.exe") $ExeTarget -Force

$InternalSrc = Join-Path $DistDir "_internal"
$InternalTarget = Join-Path $Root "_internal"
if (Test-Path $InternalTarget) {
    Remove-Item $InternalTarget -Recurse -Force -ErrorAction SilentlyContinue
}
try {
    Copy-Item $InternalSrc $InternalTarget -Recurse -Force -ErrorAction Stop
} catch {
    Write-Host "Warning: failed to copy _internal. CurlDownloader.exe may still be running."
    Write-Host "Please close CurlDownloader.exe and run build again."
    Write-Host "New build output: $DistDir"
    exit 1
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
