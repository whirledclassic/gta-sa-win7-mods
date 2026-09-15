@echo off
setlocal EnableExtensions
title GroveLink update
color 0A
cd /d "%~dp0"
echo Checking for Git...
where git >nul 2>&1
if errorlevel 1 (
  echo Git not installed. Using the files already in this folder.
  echo Download a fresh zip from GitHub if this folder is old:
  echo   https://github.com/whirledclassic/gta-sa-win7-mods
  echo.
) else (
  echo Pulling latest main...
  git pull origin main
  echo.
)
call "%~dp0INSTALL.bat" PATCH
endlocal
