@echo off
setlocal
title Vitro-CAD local MCP setup
powershell.exe -NoProfile -Sta -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
set "VITRO_INSTALL_EXIT=%ERRORLEVEL%"
if not "%VITRO_INSTALL_EXIT%"=="0" (
    echo.
    echo Setup stopped with code %VITRO_INSTALL_EXIT%.
    echo Please take a screenshot of this window. Do not share your password.
    echo Press any key to close this window.
    pause >nul
)
exit /b %VITRO_INSTALL_EXIT%
