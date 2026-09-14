@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink + Switcher - one-click install
color 0A
cd /d "%~dp0"

echo.
echo ================================================
echo   GTA SA WIN7 MODS  -  AUTO INSTALL
echo ================================================
echo.

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator so files can go into the game folder...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo [1/7] Looking for GTA San Andreas...
set "GTA="
for %%P in (
  "%ProgramFiles(x86)%\Rockstar Games\GTA San Andreas"
  "%ProgramFiles%\Rockstar Games\GTA San Andreas"
  "C:\Games\GTA San Andreas"
  "D:\Games\GTA San Andreas"
  "E:\Games\GTA San Andreas"
  "C:\GTA San Andreas"
  "D:\GTA San Andreas"
  "E:\GTA San Andreas"
  "%USERPROFILE%\Desktop\GTA San Andreas"
  "%USERPROFILE%\Games\GTA San Andreas"
) do (
  if exist "%%~P\gta_sa.exe" if not defined GTA set "GTA=%%~P"
)

if not defined GTA (
  echo    Scanning fixed drives for gta_sa.exe...
  for %%D in (C D E F G H) do (
    if exist "%%D:\" (
      for /f "delims=" %%F in ('dir /s /b "%%D:\gta_sa.exe" 2^>nul') do (
        if not defined GTA (
          set "GTA=%%~dpF"
          set "GTA=!GTA:~0,-1!"
        )
      )
    )
  )
)

if not defined GTA (
  echo.
  echo Could not find gta_sa.exe.
  echo Type the FULL folder path that contains gta_sa.exe
  echo Example: D:\Games\GTA San Andreas
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
echo    Found: %GTA%

echo.
echo [2/7] Checking the game folder can be written...
set "WRITABLE=0"
echo grovelink-write-test> "%GTA%\._gl_write.tmp" 2>nul
if exist "%GTA%\._gl_write.tmp" (
  del /f /q "%GTA%\._gl_write.tmp" >nul 2>&1
  set "WRITABLE=1"
)

if "%WRITABLE%"=="0" (
  echo    Folder blocked. Taking ownership...
  takeown /f "%GTA%" /r /d y >nul 2>&1
  icacls "%GTA%" /grant "%USERNAME%":F /t /c /q >nul 2>&1
  attrib -r "%GTA%\*.*" /s /d >nul 2>&1
  echo grovelink-write-test> "%GTA%\._gl_write.tmp" 2>nul
  if exist "%GTA%\._gl_write.tmp" (
    del /f /q "%GTA%\._gl_write.tmp" >nul 2>&1
    set "WRITABLE=1"
  )
)

if "%WRITABLE%"=="0" (
  echo.
  echo ============================================================
  echo  This drive is locked or dirty (error 0x80071AC3).
  echo  Windows must repair it before ANY mod can install.
  echo ============================================================
  for %%I in ("%GTA%") do set "DRV=%%~dI"
  echo.
  echo Run this now?  chkdsk %DRV% /f
  echo The PC will ask to reboot. After reboot, run INSTALL.bat again.
  echo.
  set /p FIX=Type YES to schedule chkdsk: 
  if /I "%FIX%"=="YES" (
    echo Y| chkdsk %DRV% /f
    echo.
    echo Reboot now, then double-click INSTALL.bat again.
  )
  echo.
  echo Meanwhile a READY folder will be built on your Desktop.
  set "READY=%USERPROFILE%\Desktop\GroveLink_READY"
  mkdir "%READY%" >nul 2>&1
  mkdir "%READY%\GroveLink" >nul 2>&1
  copy /Y "%~dp0grovelink\GroveLink.fxt" "%READY%\" >nul
  copy /Y "%~dp0grovelink\GroveLink\link.ini" "%READY%\GroveLink\" >nul
  copy /Y "%~dp0grovelink\GroveLinkPhone.txt" "%READY%\" >nul
  echo Files waiting in:
  echo   %READY%
  echo After chkdsk, copy them into:
  echo   %GTA%\CLEO\
  pause
)

echo.
echo [3/7] Installing CLEO files...
if not exist "%GTA%\CLEO" mkdir "%GTA%\CLEO"
if not exist "%GTA%\CLEO\GroveLink" mkdir "%GTA%\CLEO\GroveLink"

if exist "%~dp0grovelink\GroveLink.fxt" copy /Y "%~dp0grovelink\GroveLink.fxt" "%GTA%\CLEO\GroveLink.fxt" >nul
if exist "%~dp0grovelink\GroveLink\link.ini" copy /Y "%~dp0grovelink\GroveLink\link.ini" "%GTA%\CLEO\GroveLink\link.ini" >nul

if not exist "%GTA%\cleo.asi" if not exist "%GTA%\CLEO.asi" (
  echo.
  echo    WARNING: cleo.asi was not found in the game folder.
  echo    Install CLEO 4.3/4.4 from https://cleo.li then rerun this.
  echo    IniFiles.cleo must be inside the CLEO folder.
)

echo.
echo [4/7] Compiling scripts if Sanny Builder is installed...
set "SANNY="
for %%P in (
  "%ProgramFiles%\Sanny Builder 4\sanny.exe"
  "%ProgramFiles(x86)%\Sanny Builder 4\sanny.exe"
  "%ProgramFiles%\Sanny Builder 3\sanny.exe"
  "%ProgramFiles(x86)%\Sanny Builder 3\sanny.exe"
  "%USERPROFILE%\Desktop\Sanny Builder 3\sanny.exe"
  "%USERPROFILE%\Desktop\Sanny Builder 4\sanny.exe"
) do (
  if exist "%%~P" if not defined SANNY set "SANNY=%%~P"
)

if defined SANNY (
  echo    Sanny: %SANNY%
  "%SANNY%" --game sa --no-splash --compile "%~dp0grovelink\GroveLinkPhone.txt" "%GTA%\CLEO\GroveLinkPhone.cs"
  if not exist "%GTA%\CLEO\GroveLinkPhone.cs" (
    "%SANNY%" --no-splash --compile "%~dp0grovelink\GroveLinkPhone.txt" "%GTA%\CLEO\GroveLinkPhone.cs"
  )
  "%SANNY%" --game sa --no-splash --compile "%~dp0switcher\MissionSwitcher_SkinOnly.txt" "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs"
  if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
    echo    GroveLinkPhone.cs installed.
  ) else (
    echo    Auto-compile failed. Open GroveLinkPhone.txt in Sanny and press F7.
  )
) else (
  echo    Sanny Builder not found.
  echo    Install it from https://sannybuilder.com
  echo    Then either rerun INSTALL.bat or compile GroveLinkPhone.txt with F7
  echo    and copy the .cs into:
  echo      %GTA%\CLEO\
)

echo.
echo [5/7] Writing bridge config...
if not exist "%~dp0grovelink\bridge" mkdir "%~dp0grovelink\bridge"
(
  echo [paths]
  echo gta_dir = %GTA%
  echo gallery_dir = %USERPROFILE%\Documents\GTA San Andreas User Files\Gallery
  echo gallery_dir_alt = %PUBLIC%\Documents\GTA San Andreas User Files\Gallery
  echo.
  echo [server]
  echo host = 0.0.0.0
  echo port = 8088
) > "%~dp0grovelink\bridge\config.ini"

echo.
echo [6/7] Opening firewall port 8088...
netsh advfirewall firewall delete rule name="GroveLink Phone" >nul 2>&1
netsh advfirewall firewall add rule name="GroveLink Phone" dir=in action=allow protocol=tcp localport=8088 >nul 2>&1
netsh firewall add portopening TCP 8088 "GroveLink Phone" >nul 2>&1

echo.
echo [7/7] Desktop shortcut...
powershell -NoProfile -Command ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\GroveLink Phone.lnk');" ^
  "$s.TargetPath='%~dp0grovelink\bridge\START_GROVELINK.bat';" ^
  "$s.WorkingDirectory='%~dp0grovelink\bridge';" ^
  "$s.WindowStyle=1;" ^
  "$s.Description='Start GroveLink phone bridge';" ^
  "$s.Save()"

echo.
echo ================================================
echo   DONE
echo ================================================
echo Game folder : %GTA%
echo Phone script: %GTA%\CLEO\GroveLinkPhone.cs
echo Labels file : %GTA%\CLEO\GroveLink.fxt
echo Inbox file  : %GTA%\CLEO\GroveLink\link.ini
echo.
echo NEXT:
echo   1. Double-click  "GroveLink Phone"  on the Desktop
echo      (keep that window open)
echo   2. Launch GTA SA
echo   3. Press K
echo.
echo If GroveLinkPhone.cs is missing, compile with Sanny F7 once.
echo.
set /p RUN=Start the phone bridge now? (Y/N): 
if /I "%RUN%"=="Y" (
  start "GroveLink" "%~dp0grovelink\bridge\START_GROVELINK.bat"
)
echo.
pause
endlocal
