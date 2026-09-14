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

echo [1/7] Looking for GTA San Andreas (CLEO copy first)...
set "GTA="
for %%P in (
  "E:\GTA San Andreas"
  "D:\GTA San Andreas"
  "C:\GTA San Andreas"
  "E:\Games\GTA San Andreas"
  "D:\Games\GTA San Andreas"
  "C:\Games\GTA San Andreas"
  "%USERPROFILE%\Desktop\GTA San Andreas"
) do (
  if exist "%%~P\gta_sa.exe" if exist "%%~P\CLEO.asi" if not defined GTA set "GTA=%%~P"
)
if not defined GTA (
  for %%P in (
    "E:\GTA San Andreas"
    "D:\GTA San Andreas"
    "C:\GTA San Andreas"
    "%ProgramFiles(x86)%\Rockstar Games\GTA San Andreas"
    "%ProgramFiles%\Rockstar Games\GTA San Andreas"
  ) do (
    if exist "%%~P\gta_sa.exe" if not defined GTA set "GTA=%%~P"
  )
)

if not defined GTA (
  echo    Scanning E: then D: then C: for CLEO.asi...
  for %%D in (E D C F G H) do (
    if exist "%%D:\" if not defined GTA (
      for /f "delims=" %%F in ('dir /s /b "%%D:\CLEO.asi" 2^>nul') do (
        if exist "%%~dpFgta_sa.exe" if not defined GTA (
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
  echo Type: E:\GTA San Andreas
  set /p GTA=Path: 
)

if not exist "%GTA%\gta_sa.exe" (
  echo Still no gta_sa.exe in %GTA%
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
  echo grovelink-write-test> "%GTA%\._gl_write.tmp" 2>nul
  if exist "%GTA%\._gl_write.tmp" (
    del /f /q "%GTA%\._gl_write.tmp" >nul 2>&1
    set "WRITABLE=1"
  )
)

if "%WRITABLE%"=="0" (
  echo Drive locked or dirty. Type YES to schedule chkdsk.
  for %%I in ("%GTA%") do set "DRV=%%~dI"
  set /p FIX=YES to chkdsk %DRV%: 
  if /I "%FIX%"=="YES" echo Y| chkdsk %DRV% /f
  set "READY=%USERPROFILE%\Desktop\GroveLink_READY"
  mkdir "%READY%\GroveLink" >nul 2>&1
  copy /Y "%~dp0grovelink\GroveLink.fxt" "%READY%\" >nul
  copy /Y "%~dp0grovelink\GroveLink\link.ini" "%READY%\GroveLink\" >nul
  echo Ready files: %READY%
  pause
)

echo.
echo [3/7] Installing CLEO files into %GTA%\CLEO ...
if not exist "%GTA%\CLEO" mkdir "%GTA%\CLEO"
if not exist "%GTA%\CLEO\GroveLink" mkdir "%GTA%\CLEO\GroveLink"
copy /Y "%~dp0grovelink\GroveLink.fxt" "%GTA%\CLEO\GroveLink.fxt" >nul
copy /Y "%~dp0grovelink\GroveLink\link.ini" "%GTA%\CLEO\GroveLink\link.ini" >nul

echo.
echo [4/7] Compile if Sanny exists...
set "SANNY="
for %%P in (
  "%ProgramFiles%\Sanny Builder 4\sanny.exe"
  "%ProgramFiles(x86)%\Sanny Builder 4\sanny.exe"
  "%ProgramFiles%\Sanny Builder 3\sanny.exe"
  "%ProgramFiles(x86)%\Sanny Builder 3\sanny.exe"
) do (
  if exist "%%~P" if not defined SANNY set "SANNY=%%~P"
)
if defined SANNY (
  "%SANNY%" --game sa --no-splash --compile "%~dp0grovelink\GroveLinkPhone.txt" "%GTA%\CLEO\GroveLinkPhone.cs"
)

echo.
echo [5/7] Writing bridge config to E: path...
(
  echo [paths]
  echo gta_dir = %GTA%
  echo gallery_dir = %USERPROFILE%\Documents\GTA San Andreas User Files\Gallery
  echo gallery_dir_alt = %USERPROFILE%\My Documents\GTA San Andreas User Files\Gallery
  echo.
  echo [server]
  echo host = 0.0.0.0
  echo port = 8088
) > "%~dp0grovelink\bridge\config.ini"

echo.
echo [6/7] Firewall 8088...
netsh advfirewall firewall add rule name="GroveLink Phone" dir=in action=allow protocol=tcp localport=8088 >nul 2>&1

echo.
echo [7/7] Shortcuts on YOUR desktop and Public desktop...
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%USERPROFILE%\Desktop\START_GROVELINK.bat" >nul
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%PUBLIC%\Desktop\START_GROVELINK.bat" >nul 2>&1

echo.
echo DONE. Game folder: %GTA%
echo Launch GTA from that folder. Press K in-game.
echo Desktop now has START_GROVELINK.bat
echo.
set /p RUN=Start bridge now? (Y/N): 
if /I "%RUN%"=="Y" start "GroveLink" "%~dp0grovelink\bridge\START_GROVELINK.bat"
pause
endlocal
