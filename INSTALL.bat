@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink + Mission Switcher — one-click install
color 0A
cd /d "%~dp0"

echo.
echo ================================================
echo   GROVELINK + SWITCHER  -  ONE-CLICK INSTALL
echo   For beginners: just wait, then follow 3 steps
echo ================================================
echo.

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator so files can go into the game folder...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo [1/8] Looking for GTA San Andreas with CLEO...
set "GTA="

REM Prefer installs that already have CLEO.asi
for %%P in (
  "E:\GTA San Andreas"
  "D:\GTA San Andreas"
  "C:\GTA San Andreas"
  "E:\Games\GTA San Andreas"
  "D:\Games\GTA San Andreas"
  "C:\Games\GTA San Andreas"
  "%ProgramFiles(x86)%\Rockstar Games\GTA San Andreas"
  "%ProgramFiles%\Rockstar Games\GTA San Andreas"
) do (
  if exist "%%~P\gta_sa.exe" if exist "%%~P\CLEO.asi" if not defined GTA set "GTA=%%~P"
  if exist "%%~P\gta_sa.exe" if exist "%%~P\cleo.asi" if not defined GTA set "GTA=%%~P"
)

REM Registry InstallPath (Steam / Rockstar / common)
if not defined GTA (
  for %%K in (
    "HKLM\SOFTWARE\Rockstar Games\GTA San Andreas\Installation"
    "HKLM\SOFTWARE\WOW6432Node\Rockstar Games\GTA San Andreas\Installation"
    "HKCU\SOFTWARE\Rockstar Games\GTA San Andreas\Installation"
    "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 12120"
    "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 12120"
  ) do (
    for /f "tokens=2*" %%A in ('reg query %%K /v InstallPath 2^>nul ^| find /i "InstallPath"') do (
      if exist "%%~B\gta_sa.exe" if not defined GTA set "GTA=%%~B"
    )
    for /f "tokens=2*" %%A in ('reg query %%K /v InstallLocation 2^>nul ^| find /i "InstallLocation"') do (
      if exist "%%~B\gta_sa.exe" if not defined GTA set "GTA=%%~B"
    )
  )
)

REM Any gta_sa.exe without CLEO preference
if not defined GTA (
  for %%P in (
    "E:\GTA San Andreas"
    "D:\GTA San Andreas"
    "C:\GTA San Andreas"
    "%ProgramFiles(x86)%\Rockstar Games\GTA San Andreas"
    "%ProgramFiles%\Rockstar Games\GTA San Andreas"
    "C:\Games\GTA San Andreas"
    "D:\Games\GTA San Andreas"
    "E:\Games\GTA San Andreas"
  ) do (
    if exist "%%~P\gta_sa.exe" if not defined GTA set "GTA=%%~P"
  )
)

if not defined GTA (
  echo.
  echo Could not find gta_sa.exe automatically.
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
if exist "%GTA%\CLEO.asi" (
  echo    CLEO.asi: FOUND
) else if exist "%GTA%\cleo.asi" (
  echo    CLEO.asi: FOUND
) else (
  echo    WARNING: CLEO.asi missing — install CLEO 4.3/4.4 from https://cleo.li
  echo    Put IniFiles.cleo inside the CLEO folder too.
)

echo.
echo [2/8] Installing GroveLink support files (fxt + link.ini)...
if not exist "%GTA%\CLEO" mkdir "%GTA%\CLEO"
if not exist "%GTA%\CLEO\GroveLink" mkdir "%GTA%\CLEO\GroveLink"
copy /Y "%~dp0grovelink\GroveLink.fxt" "%GTA%\CLEO\GroveLink.fxt" >nul
copy /Y "%~dp0grovelink\GroveLink\link.ini" "%GTA%\CLEO\GroveLink\link.ini" >nul
echo    GroveLink.fxt + link.ini copied.

echo.
echo [3/8] Compiling GroveLinkPhone with Sanny Builder if available...
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
    "D:\Sanny Builder 3\sanny.exe"
    "D:\Sanny Builder 4\sanny.exe"
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
  echo    ================================================
  echo    PHONE SCRIPT NEEDS A ONE-TIME COMPILE
  echo    ================================================
  if "%HAD_OLD%"=="1" (
    echo    Keeping your existing GroveLinkPhone.cs ^(not deleted^).
    echo    Recompile when you can so you get the latest camera/inbox.
  ) else (
    echo    No GroveLinkPhone.cs yet — do this once:
  )
  echo.
  echo    1. Download Sanny Builder 3 or 4:
  echo       https://sannybuilder.com
  echo    2. Install it, then open:
  echo       %~dp0grovelink\GroveLinkPhone.txt
  echo    3. Press F7 ^(Compile^).
  echo    4. Copy the new GroveLinkPhone.cs into:
  echo       %GTA%\CLEO\
  echo.
  echo    NOTE: The tiny file in grovelink\prebuilt\ is an OLD test stub.
  echo    Do NOT use it for the camera phone — compile GroveLinkPhone.txt.
  echo    ================================================
)

echo.
echo [4/8] Mission Switcher ^(optional, SkinOnly = safer^)...
set "SW_COMPILED=0"
if defined SANNY (
  "%SANNY%" --game sa --no-splash --compile "%~dp0switcher\MissionSwitcher_SkinOnly.txt" "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs.new" 2>nul
  if not exist "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs.new" (
    "%SANNY%" --no-splash --compile "%~dp0switcher\MissionSwitcher_SkinOnly.txt" "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs.new" 2>nul
  )
  if exist "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs.new" (
    if exist "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs" del /f /q "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs" >nul 2>&1
    move /Y "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs.new" "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs" >nul
    set "SW_COMPILED=1"
    echo    MissionSwitcher_SkinOnly.cs installed.
    echo    In game: stand near companion, press H. J = back to CJ.
  ) else (
    echo    Switcher auto-compile skipped ^(Sanny could not compile^).
    echo    Manual: open switcher\MissionSwitcher_SkinOnly.txt in Sanny, F7.
  )
) else (
  echo    Skipped ^(needs Sanny^). Later: F7 on switcher\MissionSwitcher_SkinOnly.txt
  echo    then copy .cs into %GTA%\CLEO\
)

echo.
echo [5/8] Creating Gallery folders + bridge config.ini...
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
  echo open_browser = 1
  echo max_photos = 40
) > "%~dp0grovelink\bridge\config.ini"
echo    Gallery: %GAL1%
echo    config.ini written ^(port 8088, open_browser=1, max_photos=40^).

echo.
echo [6/8] Opening firewall for TCP 8088...
netsh advfirewall firewall delete rule name="GroveLink Phone" >nul 2>&1
netsh advfirewall firewall add rule name="GroveLink Phone" dir=in action=allow protocol=tcp localport=8088 profile=any >nul 2>&1
netsh firewall add portopening TCP 8088 "GroveLink Phone" >nul 2>&1
echo    Rule "GroveLink Phone" allowed on port 8088.

echo.
echo [7/8] Desktop starters + health check + phone URL note...
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%USERPROFILE%\Desktop\START_GROVELINK.bat" >nul
copy /Y "%~dp0grovelink\bridge\START_GROVELINK.bat" "%PUBLIC%\Desktop\START_GROVELINK.bat" >nul 2>&1
copy /Y "%~dp0VERIFY_GROVELINK.bat" "%USERPROFILE%\Desktop\VERIFY_GROVELINK.bat" >nul
copy /Y "%~dp0VERIFY_GROVELINK.bat" "%PUBLIC%\Desktop\VERIFY_GROVELINK.bat" >nul 2>&1
copy /Y "%~dp0UPDATE_GROVELINK.bat" "%USERPROFILE%\Desktop\UPDATE_GROVELINK.bat" >nul
copy /Y "%~dp0UPDATE_GROVELINK.bat" "%PUBLIC%\Desktop\UPDATE_GROVELINK.bat" >nul 2>&1
REM So Desktop VERIFY / UPDATE can find bridge files even when not run from the zip folder
> "%USERPROFILE%\Desktop\GroveLink_REPO.txt" echo %~dp0
if exist "%PUBLIC%\Desktop\" > "%PUBLIC%\Desktop\GroveLink_REPO.txt" echo %~dp0

REM Launcher that starts bridge (opens browser itself via open_browser=1)
(
  echo @echo off
  echo title GroveLink Phone
  echo start "GroveLink" "%~dp0grovelink\bridge\START_GROVELINK.bat"
  echo echo.
  echo echo Bridge starting... browser should open http://127.0.0.1:8088
  echo echo Phone URL is printed in the bridge window and in GroveLink_PHONE_URL.txt
  echo timeout /t 3 /nobreak ^>nul
) > "%USERPROFILE%\Desktop\GroveLink_Phone_LAUNCH.bat"

powershell -NoProfile -Command ^
  "$desk=[Environment]::GetFolderPath('Desktop');" ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut($desk+'\GroveLink Phone.lnk');" ^
  "$s.TargetPath=$desk+'\GroveLink_Phone_LAUNCH.bat';" ^
  "$s.WorkingDirectory='%~dp0grovelink\bridge';" ^
  "$s.WindowStyle=1;" ^
  "$s.Description='Start GroveLink phone bridge + open page';" ^
  "$s.Save()" >nul 2>&1

(
  echo GroveLink — phone page URL
  echo ==========================
  echo.
  echo The LIVE address is printed by the bridge window when it starts.
  echo.
  echo On this PC try:   http://127.0.0.1:8088
  echo On your phone:    http://YOUR-PC-LAN-IP:8088
  echo                   ^(same Wi-Fi; IP shown in the bridge window^)
  echo.
  echo Also see: grovelink\bridge\OPEN_ON_PHONE.txt after the bridge runs once.
  echo Health check:     http://127.0.0.1:8088/health
  echo.
  echo In GTA: K → Camera / Inbox / Contacts / Status / Help / Close
  echo         Camera: Enter or Space to snap
  echo.
  echo Stuck? Double-click VERIFY_GROVELINK.bat on the Desktop.
  echo Outdated? Double-click UPDATE_GROVELINK.bat on the Desktop.
) > "%USERPROFILE%\Desktop\GroveLink_PHONE_URL.txt"

(
  echo GroveLink — quick start
  echo ======================
  echo.
  echo Do these 3 steps:
  echo.
  echo   1. Double-click Desktop shortcut  "GroveLink Phone"
  echo      ^(keep the black bridge window open^)
  echo.
  echo   2. Launch GTA San Andreas
  echo.
  echo   3. Press K → Camera → Enter ^(or Space^)
  echo      Shot appears on the phone page in a couple seconds.
  echo.
  echo In-game menu: CAMERA / INBOX / CONTACTS / STATUS / HELP / CLOSE
  echo HELP reminds you: OPEN START GROVELINK ON PC
  echo.
  echo Stuck? See TROUBLESHOOTING in the repo folder:
  echo   %~dp0grovelink\TROUBLESHOOTING.md
  echo.
  echo Or run Desktop VERIFY_GROVELINK.bat for an OK/MISSING checklist.
  echo.
  echo Already installed / outdated?
  echo   Double-click Desktop UPDATE_GROVELINK.bat for a one-click patch.
) > "%USERPROFILE%\Desktop\GroveLink_README.txt"
if exist "%PUBLIC%\Desktop\" copy /Y "%USERPROFILE%\Desktop\GroveLink_README.txt" "%PUBLIC%\Desktop\GroveLink_README.txt" >nul 2>&1

echo    Desktop: GroveLink Phone, START_GROVELINK, VERIFY_GROVELINK, UPDATE_GROVELINK, README, PHONE_URL + REPO pointer

echo.
echo [8/8] Done
echo.
color 0A
echo ################################################
echo #                                              #
echo #           SUCCESS — YOU ARE READY            #
echo #                                              #
echo ################################################
echo.
echo   Do these 3 steps:
echo.
echo   1. Double-click Desktop shortcut  "GroveLink Phone"
echo      ^(keep the black bridge window open^)
echo.
echo   2. Launch GTA San Andreas
echo.
echo   3. Press K → Camera → Enter ^(or Space^)
echo      Shot appears on the phone page in a couple seconds.
echo.
echo   Optional: VERIFY_GROVELINK.bat checks everything; UPDATE_GROVELINK.bat patches to latest.
echo   Readme   : Desktop GroveLink_README.txt  ^(same 3 steps + TROUBLESHOOTING^)
echo.
echo ------------------------------------------------
echo Game folder : %GTA%
if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
  echo Phone script: PRESENT  %GTA%\CLEO\GroveLinkPhone.cs
) else (
  echo Phone script: MISSING — follow Sanny F7 steps printed above
)
if "%SW_COMPILED%"=="1" (
  echo Switcher    : INSTALLED  MissionSwitcher_SkinOnly.cs  ^(H near companion / J = CJ^)
) else if exist "%GTA%\CLEO\MissionSwitcher_SkinOnly.cs" (
  echo Switcher    : PRESENT  MissionSwitcher_SkinOnly.cs  ^(H / J^)
)
echo Gallery     : %GAL1%
echo PC page     : http://127.0.0.1:8088
echo Health check: Desktop VERIFY_GROVELINK.bat
echo ------------------------------------------------
echo.
set /p RUN=Start GroveLink Phone bridge now? (Y/N): 
if /I "%RUN%"=="Y" (
  start "GroveLink" "%USERPROFILE%\Desktop\GroveLink_Phone_LAUNCH.bat"
)
echo.
pause
endlocal
