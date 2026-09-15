@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink install
color 0A
cd /d "%~dp0"

echo.
echo ================================================
echo   GROVELINK  -  ONE-CLICK INSTALL
echo ================================================
echo.

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator so files can go into the game folder...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo [1/7] Looking for GTA San Andreas with CLEO...
set "GTA="
for %%P in ("E:\GTA San Andreas" "D:\GTA San Andreas" "C:\GTA San Andreas") do (
  if exist "%%~P\gta_sa.exe" if exist "%%~P\CLEO.asi" if not defined GTA set "GTA=%%~P"
)
if not defined GTA (
  for %%P in (
    "%ProgramFiles(x86)%\Rockstar Games\GTA San Andreas"
    "%ProgramFiles%\Rockstar Games\GTA San Andreas"
    "C:\Games\GTA San Andreas"
    "D:\Games\GTA San Andreas"
    "E:\Games\GTA San Andreas"
    "C:\GTA San Andreas"
    "D:\GTA San Andreas"
    "E:\GTA San Andreas"
  ) do (
    if exist "%%~P\gta_sa.exe" if not defined GTA set "GTA=%%~P"
  )
)
if not defined GTA if exist "E:\GTA San Andreas\gta_sa.exe" set "GTA=E:\GTA San Andreas"
if not defined GTA (
  echo.
  echo Could not find gta_sa.exe.
  echo Type the FULL folder path that contains gta_sa.exe
  echo Example: E:\GTA San Andreas
  set /p GTA=Path: 
)
if not exist "%GTA%\gta_sa.exe" (
  echo.
  echo Still no gta_sa.exe in:
  echo   %GTA%
  echo Install stopped.
  pause
  exit /b 1
)
echo    Game: %GTA%

echo.
echo [2/7] Installing CLEO support files (fxt + link.ini)...
if not exist "%GTA%\CLEO" mkdir "%GTA%\CLEO"
if not exist "%GTA%\CLEO\GroveLink" mkdir "%GTA%\CLEO\GroveLink"
copy /Y "%~dp0grovelink\GroveLink.fxt" "%GTA%\CLEO\GroveLink.fxt" >nul
copy /Y "%~dp0grovelink\GroveLink\link.ini" "%GTA%\CLEO\GroveLink\link.ini" >nul
if not exist "%GTA%\cleo.asi" if not exist "%GTA%\CLEO.asi" (
  echo    WARNING: CLEO.asi was not found. Install CLEO 4.3/4.4 from https://cleo.li
  echo    IniFiles.cleo must be inside the CLEO folder.
)

echo.
echo [3/7] Compiling GroveLinkPhone with Sanny Builder if available...
set "SANNY="
where sanny.exe >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%S in ('where sanny.exe 2^>nul') do (
    if not defined SANNY set "SANNY=%%S"
  )
)
if not defined SANNY (
  for %%P in (
    "%ProgramFiles%\Sanny Builder 4\sanny.exe"
    "%ProgramFiles(x86)%\Sanny Builder 4\sanny.exe"
    "%ProgramFiles%\Sanny Builder 3\sanny.exe"
    "%ProgramFiles(x86)%\Sanny Builder 3\sanny.exe"
    "%USERPROFILE%\Desktop\Sanny Builder 3\sanny.exe"
    "%USERPROFILE%\Desktop\Sanny Builder 4\sanny.exe"
    "%USERPROFILE%\Documents\Sanny Builder 3\sanny.exe"
    "%USERPROFILE%\Documents\Sanny Builder 4\sanny.exe"
    "C:\Sanny Builder 3\sanny.exe"
    "C:\Sanny Builder 4\sanny.exe"
  ) do (
    if exist "%%~P" if not defined SANNY set "SANNY=%%~P"
  )
)

set "COMPILED=0"
set "HAD_OLD=0"
if exist "%GTA%\CLEO\GroveLinkPhone.cs" set "HAD_OLD=1"

if defined SANNY (
  echo    Sanny: %SANNY%
  "%SANNY%" --game sa --no-splash --compile "%~dp0grovelink\GroveLinkPhone.txt" "%GTA%\CLEO\GroveLinkPhone.cs.new" 2>nul
  if not exist "%GTA%\CLEO\GroveLinkPhone.cs.new" (
    "%SANNY%" --no-splash --compile "%~dp0grovelink\GroveLinkPhone.txt" "%GTA%\CLEO\GroveLinkPhone.cs.new" 2>nul
  )
  if exist "%GTA%\CLEO\GroveLinkPhone.cs.new" (
    if exist "%GTA%\CLEO\GroveLinkPhone.cs" del /f /q "%GTA%\CLEO\GroveLinkPhone.cs" >nul 2>&1
    move /Y "%GTA%\CLEO\GroveLinkPhone.cs.new" "%GTA%\CLEO\GroveLinkPhone.cs" >nul
    set "COMPILED=1"
    echo    GroveLinkPhone.cs installed (compiled from GroveLinkPhone.txt).
  ) else (
    echo    Auto-compile did not produce a .cs file.
  )
) else (
  echo    Sanny Builder not found on PATH or common install paths.
)

if "%COMPILED%"=="0" (
  echo.
  echo    Phone script was NOT auto-installed.
  echo    Open grovelink\GroveLinkPhone.txt in Sanny Builder, press F7,
  echo    then copy GroveLinkPhone.cs into:
  echo      %GTA%\CLEO\
  if "%HAD_OLD%"=="1" (
    echo.
    echo    NOTE: An existing GroveLinkPhone.cs was LEFT in place
    echo    so the phone is not deleted after install. Recompile when you can.
  )
)

echo.
echo [4/7] Creating Gallery folders + bridge config.ini...
set "GAL1=%USERPROFILE%\Documents\GTA San Andreas User Files\Gallery"
set "GAL2=%USERPROFILE%\My Documents\GTA San Andreas User Files\Gallery"
if not exist "%USERPROFILE%\Documents\GTA San Andreas User Files" mkdir "%USERPROFILE%\Documents\GTA San Andreas User Files" >nul 2>&1
if not exist "%GAL1%" mkdir "%GAL1%" >nul 2>&1
if not exist "%USERPROFILE%\My Documents\GTA San Andreas User Files" mkdir "%USERPROFILE%\My Documents\GTA San Andreas User Files" >nul 2>&1
if not exist "%GAL2%" mkdir "%GAL2%" >nul 2>&1
(
  echo [paths]
  echo gta_dir = %GTA%
  echo gallery_dir = %GAL1%
  echo gallery_dir_alt = %GAL2%
  echo [server]
  echo host = 0.0.0.0
  echo port = 8088
) > "%~dp0grovelink\bridge\config.ini"
echo    Gallery: %GAL1%
echo    config.ini written for port 8088.

echo.
echo [5/7] Opening firewall for TCP 8088...
netsh advfirewall firewall delete rule name="GroveLink Phone" >nul 2>&1
netsh advfirewall firewall add rule name="GroveLink Phone" dir=in action=allow protocol=tcp localport=8088 profile=any >nul 2>&1
netsh firewall add portopening TCP 8088 "GroveLink Phone" >nul 2>&1
echo    Rule "GroveLink Phone" allowed on port 8088.

echo.
echo [6/7] Desktop starter...
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%USERPROFILE%\Desktop\START_GROVELINK.bat" >nul
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%PUBLIC%\Desktop\START_GROVELINK.bat" >nul 2>&1
powershell -NoProfile -Command ^
  "$desk=[Environment]::GetFolderPath('Desktop');" ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut($desk+'\GroveLink Phone.lnk');" ^
  "$s.TargetPath='%~dp0grovelink\bridge\START_GROVELINK.bat';" ^
  "$s.WorkingDirectory='%~dp0grovelink\bridge';" ^
  "$s.WindowStyle=1;" ^
  "$s.Description='Start GroveLink phone bridge';" ^
  "$s.Save()" >nul 2>&1
echo    Desktop: START_GROVELINK.bat (+ GroveLink Phone shortcut if PowerShell ok)

echo.
echo [7/7] Summary
echo ================================================
echo   DONE
echo ================================================
echo Game folder : %GTA%
if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
  echo Phone script: %GTA%\CLEO\GroveLinkPhone.cs  [PRESENT]
) else (
  echo Phone script: MISSING — compile GroveLinkPhone.txt in Sanny ^(F7^)
)
echo Labels file : %GTA%\CLEO\GroveLink.fxt
echo Inbox file  : %GTA%\CLEO\GroveLink\link.ini
echo Gallery     : %GAL1%
echo.
echo VERIFY:
echo   1. Double-click START_GROVELINK on the Desktop ^(keep window open^)
echo   2. On PC open http://127.0.0.1:8088
echo   3. On phone open http://LAN-IP:8088 ^(printed by the bridge^)
echo   4. Launch GTA, press K, Camera, Enter or Space — shot appears in a couple seconds
echo.
set /p RUN=Start the phone bridge now? (Y/N): 
if /I "%RUN%"=="Y" (
  start "GroveLink" "%~dp0grovelink\bridge\START_GROVELINK.bat"
)
echo.
pause
endlocal
