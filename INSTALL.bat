@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink + Switcher - one-click install
color 0A
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo [1/6] Find GTA with CLEO...
set "GTA="
for %%P in ("E:\GTA San Andreas" "D:\GTA San Andreas" "C:\GTA San Andreas") do (
  if exist "%%~P\gta_sa.exe" if exist "%%~P\CLEO.asi" if not defined GTA set "GTA=%%~P"
)
if not defined GTA if exist "E:\GTA San Andreas\gta_sa.exe" set "GTA=E:\GTA San Andreas"
if not defined GTA (
  echo Type the game folder (example E:\GTA San Andreas)
  set /p GTA=Path: 
)
echo    Found: %GTA%

echo [2/6] Make CLEO folders...
if not exist "%GTA%\CLEO" mkdir "%GTA%\CLEO"
if not exist "%GTA%\CLEO\GroveLink" mkdir "%GTA%\CLEO\GroveLink"
copy /Y "%~dp0grovelink\GroveLink.fxt" "%GTA%\CLEO\GroveLink.fxt" >nul
copy /Y "%~dp0grovelink\GroveLink\link.ini" "%GTA%\CLEO\GroveLink\link.ini" >nul

echo [3/6] Install prebuilt phone script (no Sanny needed)...
if exist "%~dp0grovelink\prebuilt\GroveLinkPhone.cs.b64" (
  certutil -decode -f "%~dp0grovelink\prebuilt\GroveLinkPhone.cs.b64" "%GTA%\CLEO\GroveLinkPhone.cs" >nul
)
if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
  echo    GroveLinkPhone.cs installed.
) else (
  echo    ERROR: phone script did not install. Is E: writable?
)

echo [4/6] Write config.ini...
(
  echo [paths]
  echo gta_dir = %GTA%
  echo gallery_dir = %USERPROFILE%\Documents\GTA San Andreas User Files\Gallery
  echo gallery_dir_alt = %USERPROFILE%\My Documents\GTA San Andreas User Files\Gallery
  echo [server]
  echo host = 0.0.0.0
  echo port = 8088
) > "%~dp0grovelink\bridge\config.ini"

echo [5/6] Firewall...
netsh advfirewall firewall add rule name="GroveLink Phone" dir=in action=allow protocol=tcp localport=8088 profile=any >nul 2>&1

echo [6/6] Desktop starter...
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%USERPROFILE%\Desktop\START_GROVELINK.bat" >nul
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%PUBLIC%\Desktop\START_GROVELINK.bat" >nul 2>&1

echo.
echo DONE
echo Game: %GTA%
echo Script: %GTA%\CLEO\GroveLinkPhone.cs
echo Launch THAT gta_sa.exe, press K. You should see GROVELINK OK.
echo.
set /p RUN=Start bridge now? (Y/N): 
if /I "%RUN%"=="Y" start "GroveLink" "%~dp0grovelink\bridge\START_GROVELINK.bat"
pause
endlocal
