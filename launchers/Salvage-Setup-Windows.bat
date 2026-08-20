@echo off
title Salvage Setup
echo.
echo   Salvage - Minecraft modpack setup
echo.
echo   Fetching the setup app...
echo.

set "PS=%TEMP%\salvage-setup.ps1"
set "URL=https://raw.githubusercontent.com/TheKingNate/high-seas-modpack/release/install/salvage-setup.ps1"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { Invoke-WebRequest '%URL%' -OutFile '%PS%' -UseBasicParsing } catch { exit 1 }"

if not exist "%PS%" (
    echo   Couldn't download the setup app.
    echo.
    echo   Check your internet connection and try again.
    echo   If that keeps failing, tell Josh.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS%"
del "%PS%" >nul 2>&1
