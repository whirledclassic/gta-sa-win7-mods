@echo off
setlocal EnableExtensions EnableDelayedExpansion
title UPDATING GROVELINK TO LATEST
color 0B
cd /d "%~dp0"

echo.
echo ################################################
echo #                                              #
echo #     UPDATING GROVELINK TO LATEST             #
echo #     One-click patcher -- no Git needed       #
echo #                                              #
echo ################################################
echo.

REM Admin so INSTALL firewall / CLEO copy can finish without a second UAC dance
net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator so the update can refresh game files...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

REM ============================================================
REM Locate the real repo folder (Desktop stub OR zip folder)
REM ============================================================
set "REPO="
if exist "%~dp0INSTALL.bat" if exist "%~dp0grovelink\bridge\grovelink_server.py" (
  set "REPO=%~dp0"
)
if not defined REPO (
  if exist "%USERPROFILE%\Desktop\GroveLink_REPO.txt" (
    set /p REPO=<"%USERPROFILE%\Desktop\GroveLink_REPO.txt"
  )
)
if not defined REPO (
  if exist "%PUBLIC%\Desktop\GroveLink_REPO.txt" (
    set /p REPO=<"%PUBLIC%\Desktop\GroveLink_REPO.txt"
  )
)
if defined REPO (
  if "!REPO:~-1!"==" " set "REPO=!REPO:~0,-1!"
)
if not defined REPO goto :err_no_repo
if not exist "!REPO!\INSTALL.bat" goto :err_no_repo
if not exist "!REPO!\grovelink\bridge\grovelink_server.py" goto :err_no_repo

echo Repo folder:
echo   !REPO!
echo.

REM ============================================================
REM Read branch / release from update.ini or env UPDATE_BRANCH
REM ============================================================
set "BRANCH=fix/grovelink-camera-snapshots"
set "RELEASE="
set "INI=!REPO!\update.ini"
if not exist "!INI!" if exist "%~dp0update.ini" set "INI=%~dp0update.ini"
if exist "!INI!" (
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /b /c:"branch=" "!INI!" 2^>nul`) do (
    set "BRANCH=%%B"
  )
  for /f "usebackq tokens=1,* delims==" %%A in (`findstr /i /b /c:"release=" "!INI!" 2^>nul`) do (
    set "RELEASE=%%B"
  )
)
if defined UPDATE_BRANCH set "BRANCH=%UPDATE_BRANCH%"
for /f "tokens=* delims= " %%T in ("!BRANCH!") do set "BRANCH=%%T"
for /f "tokens=* delims= " %%T in ("!RELEASE!") do set "RELEASE=%%T"

echo Download source:
echo   branch = !BRANCH!
if defined RELEASE if not "!RELEASE!"=="" echo   release= !RELEASE!
echo.

set "OWNER=whirledclassic"
set "PROJ=gta-sa-win7-mods"
set "TMPROOT=%TEMP%\GroveLinkUpdate"
set "ZIPFILE=%TMPROOT%\pack.zip"
set "EXTRACT=%TMPROOT%\extract"
set "MANUAL_URL=https://github.com/!OWNER!/!PROJ!/archive/refs/heads/!BRANCH!.zip"

if exist "%TMPROOT%" rd /s /q "%TMPROOT%" >nul 2>&1
mkdir "%TMPROOT%" >nul 2>&1
mkdir "%EXTRACT%" >nul 2>&1
if not exist "%TMPROOT%" goto :err_temp

REM ============================================================
REM Optionally try GitHub latest release zipball (PS 2.0 safe)
REM ============================================================
set "DL_URL="
set "FETCHED_AS="
if /I "!RELEASE!"=="latest" (
  echo Trying GitHub latest release zipball...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $wc=New-Object System.Net.WebClient; $wc.Headers.Add('User-Agent','GroveLinkUpdater'); $wc.DownloadFile('https://api.github.com/repos/!OWNER!/!PROJ!/releases/latest','!TMPROOT!\release.json'); exit 0 } catch { exit 1 }"
  if exist "!TMPROOT!\release.json" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$t=[IO.File]::ReadAllText('!TMPROOT!\release.json'); $k='\"zipball_url\":\"'; $i=$t.IndexOf($k); if($i -lt 0){ exit 1 }; $i=$i+$k.Length; $j=$t.IndexOf('\"',$i); if($j -lt 0){ exit 1 }; $u=$t.Substring($i,$j-$i); [IO.File]::WriteAllText('!TMPROOT!\release_url.txt',$u); exit 0"
  )
  if exist "!TMPROOT!\release_url.txt" (
    set /p DL_URL=<"!TMPROOT!\release_url.txt"
  )
  if defined DL_URL if not "!DL_URL!"=="" (
    set "FETCHED_AS=release:latest"
    echo   Found release zipball.
  ) else (
    echo   No release found -- falling back to branch zip.
    set "DL_URL="
  )
)

if not defined DL_URL (
  set "DL_URL=https://github.com/!OWNER!/!PROJ!/archive/refs/heads/!BRANCH!.zip"
  set "FETCHED_AS=branch:!BRANCH!"
)

echo.
echo [1/4] Downloading pack zip...
echo   !DL_URL!
echo   (Win7-safe WebClient -- no Git required)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $wc=New-Object System.Net.WebClient; $wc.Headers.Add('User-Agent','GroveLinkUpdater'); $wc.DownloadFile('!DL_URL!','!ZIPFILE!'); if(-not (Test-Path '!ZIPFILE!')){ exit 1 }; $len=(Get-Item '!ZIPFILE!').Length; if($len -lt 1000){ exit 2 }; Write-Host ('   Downloaded ' + $len + ' bytes'); exit 0 } catch { Write-Host ('   Download failed: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
  echo.
  echo WebClient download failed -- trying bitsadmin...
  bitsadmin /transfer GroveLinkUpdate /download /priority foreground "!DL_URL!" "!ZIPFILE!" >nul 2>&1
)
if not exist "!ZIPFILE!" goto :err_network
for %%Z in ("!ZIPFILE!") do if %%~zZ LSS 1000 goto :err_network
echo    OK -- zip saved.
echo.

REM ============================================================
REM Unzip with Shell.Application COM (works on Win7)
REM ============================================================
echo [2/4] Extracting to temp...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $zip='!ZIPFILE!'; $dest='!EXTRACT!'; if(-not (Test-Path $dest)){ New-Item -ItemType Directory -Path $dest | Out-Null }; $shell=New-Object -ComObject Shell.Application; $zipNs=$shell.NameSpace($zip); $destNs=$shell.NameSpace($dest); if($zipNs -eq $null -or $destNs -eq $null){ Write-Host '   COM unzip unavailable'; exit 1 }; $destNs.CopyHere($zipNs.Items(), 20); $deadline=(Get-Date).AddSeconds(180); while((Get-Date) -lt $deadline){ Start-Sleep -Milliseconds 500; $dirs=@(Get-ChildItem -Path $dest -ErrorAction SilentlyContinue | Where-Object { $_.PSIsContainer }); foreach($d in $dirs){ if(Test-Path (Join-Path $d.FullName 'INSTALL.bat')){ Write-Host ('   Extracted: ' + $d.Name); exit 0 } } }; Write-Host '   Unzip timed out waiting for INSTALL.bat'; exit 2 } catch { Write-Host ('   Unzip failed: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 goto :err_unzip

set "SRC="
for /d %%D in ("!EXTRACT!\*") do (
  if exist "%%~D\INSTALL.bat" if exist "%%~D\grovelink\bridge\grovelink_server.py" set "SRC=%%~D"
)
if not defined SRC goto :err_unzip
echo    Source pack:
echo      !SRC!
echo.

REM ============================================================
REM Copy / replace pack files over the repo
REM ============================================================
echo [3/4] Copying new files into your install...
xcopy /E /Y /I /Q "!SRC!\*" "!REPO!\" >nul
if errorlevel 1 (
  echo    xcopy reported a problem -- trying robocopy...
  robocopy "!SRC!" "!REPO!" /E /NFL /NDL /NJH /NJS /nc /ns /np >nul
  if errorlevel 8 goto :err_copy
)
echo    Files updated.
echo.

set "NEWVER=unknown"
if exist "!REPO!\VERSION" (
  set /p NEWVER=<"!REPO!\VERSION"
)
for /f "tokens=* delims= " %%T in ("!NEWVER!") do set "NEWVER=%%T"

echo Fetched as: !FETCHED_AS!
echo Version   : !NEWVER!
echo.

REM ============================================================
REM Re-run INSTALL so CLEO / bridge / Desktop shortcuts refresh
REM ============================================================
echo [4/4] Running INSTALL.bat so game files + Desktop shortcuts refresh...
echo        (Already elevated -- INSTALL should continue without another UAC)
echo.
call "!REPO!\INSTALL.bat"

if exist "!REPO!\UPDATE_GROVELINK.bat" (
  copy /Y "!REPO!\UPDATE_GROVELINK.bat" "%USERPROFILE%\Desktop\UPDATE_GROVELINK.bat" >nul 2>&1
  copy /Y "!REPO!\UPDATE_GROVELINK.bat" "%PUBLIC%\Desktop\UPDATE_GROVELINK.bat" >nul 2>&1
)

echo.
color 0A
echo ################################################
echo #                                              #
echo #     SUCCESS -- Updated to version !NEWVER!
echo #                                              #
echo ################################################
echo.
echo   Branch/source : !FETCHED_AS!
echo   Version       : !NEWVER!
echo.
echo   Do these 3 steps:
echo.
echo   1. Start GroveLink  (Desktop "GroveLink Phone")
echo      (keep the black bridge window open)
echo.
echo   2. Launch GTA San Andreas
echo.
echo   3. Press K  Camera  Enter (or Space)
echo.
echo   Tip: Desktop UPDATE_GROVELINK.bat patches again anytime.
echo   Stuck? See grovelink\TROUBLESHOOTING.md
echo.
rd /s /q "%TMPROOT%" >nul 2>&1
pause
endlocal
exit /b 0

:err_no_repo
color 0C
echo.
echo Could not find your GroveLink install folder.
echo.
echo This updater needs either:
echo   - to live inside the extracted zip (next to INSTALL.bat), OR
echo   - Desktop file GroveLink_REPO.txt (created by INSTALL)
echo.
echo Fix: run INSTALL.bat once from the zip, OR open the zip folder
echo and double-click UPDATE_GROVELINK.bat there.
echo.
echo Manual zip (no updater):
echo   https://github.com/whirledclassic/gta-sa-win7-mods/archive/refs/heads/fix/grovelink-camera-snapshots.zip
echo Then extract and run INSTALL.bat.
echo See: grovelink\TROUBLESHOOTING.md
echo.
pause
exit /b 1

:err_temp
color 0C
echo.
echo Could not create temp folder:
echo   %TEMP%\GroveLinkUpdate
echo Free some disk space and try again.
echo.
echo Manual zip:
echo   !MANUAL_URL!
echo See: grovelink\TROUBLESHOOTING.md
echo.
pause
exit /b 1

:err_network
color 0C
echo.
echo DOWNLOAD FAILED -- no network, or GitHub blocked the download.
echo.
echo Plain English: this PC could not download the update zip.
echo.
echo What to try:
echo   1. Check Wi-Fi / internet, then run this updater again.
echo   2. Or download the zip yourself in a browser:
echo        !MANUAL_URL!
echo      Extract it, then run INSTALL.bat inside the new folder.
echo   3. Read: grovelink\TROUBLESHOOTING.md  (section: Updating)
echo.
pause
exit /b 1

:err_unzip
color 0C
echo.
echo UNZIP FAILED -- the downloaded file could not be extracted.
echo.
echo Plain English: Windows could not open the update zip.
echo.
echo What to try:
echo   1. Delete %%TEMP%%\GroveLinkUpdate and run this again.
echo   2. Or manual zip download:
echo        !MANUAL_URL!
echo      Extract with Windows Explorer, then run INSTALL.bat.
echo   3. Read: grovelink\TROUBLESHOOTING.md
echo.
pause
exit /b 1

:err_copy
color 0C
echo.
echo COPY FAILED -- could not write into your install folder.
echo.
echo Plain English: files were downloaded but not copied over.
echo Close GTA / GroveLink bridge, then try again.
echo Or copy the extracted folder over your install by hand and run INSTALL.bat.
echo.
echo Manual zip: !MANUAL_URL!
echo See: grovelink\TROUBLESHOOTING.md
echo.
pause
exit /b 1
