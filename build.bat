@echo off
rem ===========================================================================
rem  CurlDownloader build launcher
rem
rem  Stage 1: run build.ps1 with the execution policy bypassed for this process.
rem  Stage 2: if PowerShell is missing, or the .ps1 is blocked by group policy,
rem           build directly here in cmd so no script file has to be executed.
rem
rem  Usage: double-click build.bat, or run "build.bat" in a terminal.
rem ===========================================================================
setlocal EnableExtensions
cd /d "%~dp0"

rem ---------------------------------------------------------------- stage 1 --
set "PS="
where pwsh >nul 2>nul
if not errorlevel 1 set "PS=pwsh"
if not defined PS (
    where powershell >nul 2>nul
    if not errorlevel 1 set "PS=powershell"
)

if defined PS (
    if exist "dist\CurlDownloader\.build-ok" del /q "dist\CurlDownloader\.build-ok" >nul 2>nul
    echo [1/2] Trying "%PS% -NoProfile -ExecutionPolicy Bypass -File build.ps1" ...
    %PS% -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0build.ps1"
    if exist "dist\CurlDownloader\.build-ok" goto :done
    echo.
    echo [WARN] build.ps1 did not complete. Falling back to a direct build.
    echo.
) else (
    echo [WARN] PowerShell not found. Falling back to a direct build.
    echo.
)

rem ---------------------------------------------------------------- stage 2 --
echo [2/2] Building without PowerShell ...

if not exist "bin" mkdir "bin"

if exist "bin\yt-dlp.exe" goto :have_ytdlp

where curl >nul 2>nul
if errorlevel 1 goto :no_curl

echo Downloading yt-dlp ...
curl -L --fail --silent --show-error -o "bin\yt-dlp.exe" "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
if errorlevel 1 goto :ytdlp_failed

:have_ytdlp
if not exist "bin\ffmpeg.exe" goto :missing_ffmpeg
if not exist "bin\aria2c.exe" goto :missing_aria2c

echo Installing pyinstaller ...
python -m pip install -r requirements.txt
if errorlevel 1 goto :pip_failed

echo Building exe ...
python -m PyInstaller --noconfirm --clean --windowed --name CurlDownloader --paths "." --add-data "bin/yt-dlp.exe;bin" --add-data "bin/ffmpeg.exe;bin" --add-data "bin/aria2c.exe;bin" main.py
if errorlevel 1 goto :build_failed

copy /Y "dist\CurlDownloader\CurlDownloader.exe" "CurlDownloader.exe" >nul
if errorlevel 1 goto :copy_failed

if exist "_internal" rmdir /S /Q "_internal"
xcopy /E /I /Y "dist\CurlDownloader\_internal" "_internal" >nul
if errorlevel 1 goto :copy_failed

echo.
echo Done:
echo   EXE:     %CD%\CurlDownloader.exe
echo   Runtime: %CD%\_internal
goto :done

rem ------------------------------------------------------------------ errors --
:no_curl
echo [ERROR] curl.exe not found, cannot download yt-dlp automatically.
echo         Download it manually from:
echo         https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
echo         and save it as bin\yt-dlp.exe
goto :fail

:ytdlp_failed
echo [ERROR] Failed to download yt-dlp.exe.
echo         Download it manually from:
echo         https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
echo         and save it as bin\yt-dlp.exe
goto :fail

:missing_ffmpeg
echo [ERROR] Missing bin\ffmpeg.exe
echo         Download an essentials build from https://www.gyan.dev/ffmpeg/builds/
echo         and copy ffmpeg.exe into the bin folder.
goto :fail

:missing_aria2c
echo [ERROR] Missing bin\aria2c.exe
echo         Download from https://github.com/aria2/aria2/releases/tag/release-1.37.0
echo         (aria2-1.37.0-win-64bit-build1.zip) and copy aria2c.exe into bin\.
goto :fail

:pip_failed
echo [ERROR] "python -m pip install -r requirements.txt" failed.
echo         Check that python is on PATH and run: python --version
goto :fail

:build_failed
echo [ERROR] PyInstaller failed.
echo         Fix the error printed above, then run build.bat again.
goto :fail

:copy_failed
echo [ERROR] Could not copy the build output.
echo         Close CurlDownloader.exe if it is running, then run build.bat again.
goto :fail

:fail
echo.
echo Build FAILED.
exit /b 1

:done
exit /b 0
