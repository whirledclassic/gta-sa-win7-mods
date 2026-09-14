@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink install
color 0A
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

set "GTA="
for %%P in ("E:\GTA San Andreas" "D:\GTA San Andreas" "C:\GTA San Andreas") do (
  if exist "%%~P\gta_sa.exe" if exist "%%~P\CLEO.asi" if not defined GTA set "GTA=%%~P"
)
if not defined GTA if exist "E:\GTA San Andreas\gta_sa.exe" set "GTA=E:\GTA San Andreas"
echo Game: %GTA%

if not exist "%GTA%\CLEO" mkdir "%GTA%\CLEO"
if not exist "%GTA%\CLEO\GroveLink" mkdir "%GTA%\CLEO\GroveLink"
copy /Y "%~dp0grovelink\GroveLink.fxt" "%GTA%\CLEO\GroveLink.fxt" >nul
copy /Y "%~dp0grovelink\GroveLink\link.ini" "%GTA%\CLEO\GroveLink\link.ini" >nul

:: Remove the crashy test script if it was installed
if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
  echo Removing bad GroveLinkPhone.cs so the game can start...
  del /f /q "%GTA%\CLEO\GroveLinkPhone.cs"
)

(
  echo [paths]
  echo gta_dir = %GTA%
  echo gallery_dir = %USERPROFILE%\Documents\GTA San Andreas User Files\Gallery
  echo gallery_dir_alt = %USERPROFILE%\My Documents\GTA San Andreas User Files\Gallery
  echo [server]
  echo host = 0.0.0.0
  echo port = 8088
) > "%~dp0grovelink\bridge\config.ini"

copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%USERPROFILE%\Desktop\START_GROVELINK.bat" >nul

echo.
echo DONE. The crashing script was removed.
echo Game should start again from: %GTA%\gta_sa.exe
echo Phone .cs must be compiled in Sanny Builder (F7) from GroveLinkPhone.txt
echo then copy GroveLinkPhone.cs into %GTA%\CLEO\
pause
endlocal
