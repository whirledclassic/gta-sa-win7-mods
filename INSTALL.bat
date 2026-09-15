@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink auto installer / patcher
color 0A
cd /d "%~dp0"

set "MODE=INSTALL"
if /I "%~1"=="PATCH" set "MODE=PATCH"
if /I "%~n0"=="PATCH" set "MODE=PATCH"

net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%MODE%' -Verb RunAs"
  exit /b
)

echo ==================================================
echo   GROVELINK  %MODE%
echo ==================================================
echo.

set "SRC=%~dp0"
set "VER=7"
if exist "%SRC%VERSION.txt" (
  set /p VER=<"%SRC%VERSION.txt"
)

call :FIND_GTA
if not defined GTA (
  echo ERROR: Could not find gta_sa.exe
  echo Put GTA San Andreas on C: D: or E: or edit this script.
  pause
  exit /b 1
)
echo Game     : %GTA%

if not exist "%GTA%\CLEO.asi" (
  echo WARNING: CLEO.asi not found. Install CLEO 4.3/4.4 from https://cleo.li
)

if not exist "%GTA%\CLEO" mkdir "%GTA%\CLEO"
if not exist "%GTA%\CLEO\GroveLink" mkdir "%GTA%\CLEO\GroveLink"

set "INSTVER="
if exist "%GTA%\CLEO\GroveLink\installed.txt" set /p INSTVER=<"%GTA%\CLEO\GroveLink\installed.txt"
if defined INSTVER echo Installed: v%INSTVER%
echo Pack     : v%VER%
echo.

echo Copying GroveLink files...
copy /Y "%SRC%grovelink\GroveLink.fxt" "%GTA%\CLEO\GroveLink.fxt" >nul
copy /Y "%SRC%grovelink\GroveLink\link.ini" "%GTA%\CLEO\GroveLink\link.ini" >nul
if exist "%SRC%VERSION.txt" copy /Y "%SRC%VERSION.txt" "%GTA%\CLEO\GroveLink\version.txt" >nul

if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
  for %%F in ("%GTA%\CLEO\GroveLinkPhone.cs") do (
    if %%~zF LSS 200 del /f /q "%GTA%\CLEO\GroveLinkPhone.cs"
  )
)

(
  echo [paths]
  echo gta_dir = %GTA%
  echo gallery_dir = %USERPROFILE%\Documents\GTA San Andreas User Files\Gallery
  echo gallery_dir_alt = %USERPROFILE%\My Documents\GTA San Andreas User Files\Gallery
  echo [server]
  echo host = 0.0.0.0
  echo port = 8088
) > "%SRC%grovelink\bridge\config.ini"

copy /Y "%SRC%grovelink\bridge\START_GROVELINK.bat" "%USERPROFILE%\Desktop\START_GROVELINK.bat" >nul
copy /Y "%SRC%PATCH.bat" "%USERPROFILE%\Desktop\PATCH_GROVELINK.bat" >nul 2>nul

call :FIND_SANNY
if defined SANNY (
  echo Sanny    : %SANNY%
  echo Compiling phone + switcher...
  "%SANNY%" --compile "%SRC%grovelink\GroveLinkPhone.txt" "%GTA%\CLEO\GroveLinkPhone.cs"
  "%SANNY%" --compile "%SRC%switcher\MissionSwitcher.txt" "%GTA%\CLEO\MissionSwitcher.cs"
) else (
  echo Sanny    : NOT FOUND
  echo Compile yourself: open grovelink\GroveLinkPhone.txt in Sanny, press F7
  echo then copy GroveLinkPhone.cs into:
  echo   %GTA%\CLEO\
)

if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
  echo Phone CS : OK
) else (
  echo Phone CS : MISSING - compile in Sanny or the in-game phone will not appear
)

echo Opening firewall port 8088...
netsh advfirewall firewall delete rule name="GroveLink 8088" >nul 2>&1
netsh advfirewall firewall add rule name="GroveLink 8088" dir=in action=allow protocol=tcp localport=8088 >nul 2>&1

echo %VER%> "%GTA%\CLEO\GroveLink\installed.txt"

echo.
echo ==================================================
echo   DONE  v%VER%
echo ==================================================
echo 1. Double-click Desktop START_GROVELINK.bat
echo 2. Launch GTA San Andreas
echo 3. Press K  - green phone on the right
echo 4. Browser: URL printed by the bat  http://LAN-IP:8088
echo.
echo Next update: run PATCH.bat or Desktop PATCH_GROVELINK.bat
echo.
pause
endlocal
exit /b 0

:FIND_GTA
set "GTA="
for %%P in (
  "E:\GTA San Andreas"
  "D:\GTA San Andreas"
  "C:\GTA San Andreas"
  "C:\Program Files (x86)\Rockstar Games\GTA San Andreas"
  "C:\Program Files\Rockstar Games\GTA San Andreas"
  "C:\Games\GTA San Andreas"
  "D:\Games\GTA San Andreas"
  "E:\Games\GTA San Andreas"
) do (
  if exist "%%~P\gta_sa.exe" if not defined GTA set "GTA=%%~P"
)
if defined GTA goto :eof
for %%R in (
  "HKLM\SOFTWARE\Rockstar Games\GTA San Andreas\GTA San Andreas"
  "HKLM\SOFTWARE\WOW6432Node\Rockstar Games\GTA San Andreas\GTA San Andreas"
) do (
  for /f "tokens=2*" %%A in ('reg query %%R /v InstallFolder 2^>nul') do (
    if exist "%%B\gta_sa.exe" if not defined GTA set "GTA=%%B"
  )
)
goto :eof

:FIND_SANNY
set "SANNY="
for %%P in (
  "%ProgramFiles%\Sanny Builder 4\sanny.exe"
  "%ProgramFiles%\Sanny Builder 3\sanny.exe"
  "%ProgramFiles(x86)%\Sanny Builder 4\sanny.exe"
  "%ProgramFiles(x86)%\Sanny Builder 3\sanny.exe"
  "%USERPROFILE%\Desktop\Sanny Builder 3\sanny.exe"
  "%USERPROFILE%\Desktop\Sanny Builder 4\sanny.exe"
  "C:\Sanny Builder 3\sanny.exe"
  "C:\Sanny Builder 4\sanny.exe"
) do (
  if exist "%%~P" if not defined SANNY set "SANNY=%%~P"
)
goto :eof
