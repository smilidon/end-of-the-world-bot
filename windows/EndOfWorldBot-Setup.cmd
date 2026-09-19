@echo off
setlocal
title End of the World Bot Setup
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-windows.ps1"
exit /b %ERRORLEVEL%
