@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink — health check
color 0B
cd /d "%~dp0"

echo.
echo ================================================
echo   GROVELINK HEALTH CHECK  (beginner-friendly)
echo ================================================
echo.
echo This checks whether GroveLink is ready. OK = good.
echo MISSING = something to fix. See notes at the end.
echo.

set "GTA="
set "OK=0"
set "BAD=0"
set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"

REM If this bat was copied to Desktop, INSTALL wrote GroveLink_REPO.txt with the zip/repo path
REM Strip trailing CR from set /p (Win7 quirk) so paths resolve.
if exist "%USERPROFILE%\Desktop\GroveLink_REPO.txt" (
  set /p REPO_FROM_FILE=<"%USERPROFILE%\Desktop\GroveLink_REPO.txt"
  if defined REPO_FROM_FILE (
    for /f "delims=" %%A in ("!REPO_FROM_FILE!") do set "REPO_FROM_FILE=%%A"
    if exist "!REPO_FROM_FILE!\grovelink\bridge\grovelink_server.py" set "REPO=!REPO_FROM_FILE!"
  )
)
if exist "%PUBLIC%\Desktop\GroveLink_REPO.txt" (
  set /p REPO_FROM_FILE2=<"%PUBLIC%\Desktop\GroveLink_REPO.txt"
  if defined REPO_FROM_FILE2 (
    for /f "delims=" %%A in ("!REPO_FROM_FILE2!") do set "REPO_FROM_FILE2=%%A"
    if exist "!REPO_FROM_FILE2!\grovelink\bridge\grovelink_server.py" set "REPO=!REPO_FROM_FILE2!"
  )
)
REM Also accept running from Desktop next to a REPO pointer in same folder
if exist "%~dp0GroveLink_REPO.txt" (
  set /p REPO_FROM_FILE3=<"%~dp0GroveLink_REPO.txt"
  if defined REPO_FROM_FILE3 (
    for /f "delims=" %%A in ("!REPO_FROM_FILE3!") do set "REPO_FROM_FILE3=%%A"
    if exist "!REPO_FROM_FILE3!\grovelink\bridge\grovelink_server.py" set "REPO=!REPO_FROM_FILE3!"
  )
)

REM --- Find GTA (same idea as INSTALL) ---
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
  if exist "%%~P\gta_sa.exe" if not defined GTA set "GTA=%%~P"
)

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

REM Prefer config.ini gta_dir if present
set "CFG=%REPO%\grovelink\bridge\config.ini"
if not exist "%CFG%" set "CFG=%~dp0grovelink\bridge\config.ini"
if exist "%CFG%" (
  for /f "usebackq tokens=1,* delims==" %%A in ("%CFG%") do (
    set "K=%%A"
    set "V=%%B"
    set "K=!K: =!"
    if /I "!K!"=="gta_dir" (
      REM Trim leading/trailing spaces only — do NOT strip spaces inside path
      for /f "tokens=* delims= " %%T in ("!V!") do set "V=%%T"
      if exist "!V!\gta_sa.exe" set "GTA=!V!"
    )
  )
)

echo --- Pack version ---
set "GL_VER=unknown"
if exist "%REPO%\VERSION" (
  set /p GL_VER=<"%REPO%\VERSION"
  if defined GL_VER (
    for /f "delims=" %%A in ("!GL_VER!") do set "GL_VER=%%A"
  )
  echo   [OK]      VERSION file
  echo            %REPO%\VERSION
  echo            Pack version: !GL_VER!
  set /a OK+=1
) else if exist "%~dp0VERSION" (
  set /p GL_VER=<"%~dp0VERSION"
  if defined GL_VER (
    for /f "delims=" %%A in ("!GL_VER!") do set "GL_VER=%%A"
  )
  echo   [OK]      VERSION file
  echo            %~dp0VERSION
  echo            Pack version: !GL_VER!
  set /a OK+=1
) else (
  echo   [MISSING] VERSION file  — keep the pack root VERSION next to INSTALL.bat
  set /a BAD+=1
)
echo.

echo --- Game ---
if defined GTA (
  if exist "%GTA%\gta_sa.exe" (
    echo   [OK]      gta_sa.exe
    echo            %GTA%\gta_sa.exe
    set /a OK+=1
  ) else (
    echo   [MISSING] gta_sa.exe  ^(path set but file gone^)
    set /a BAD+=1
  )
) else (
  echo   [MISSING] gta_sa.exe  — run INSTALL.bat first, or put GTA on C/D/E
  set /a BAD+=1
  set "GTA="
)

echo.
echo --- CLEO ---
if defined GTA (
  if exist "%GTA%\CLEO.asi" (
    echo   [OK]      CLEO.asi
    set /a OK+=1
  ) else if exist "%GTA%\cleo.asi" (
    echo   [OK]      CLEO.asi
    set /a OK+=1
  ) else (
    echo   [MISSING] CLEO.asi  — install CLEO 4.3/4.4 from https://cleo.li
    set /a BAD+=1
  )

  if exist "%GTA%\CLEO\GroveLinkPhone.cs" (
    echo   [OK]      GroveLinkPhone.cs
    echo            %GTA%\CLEO\GroveLinkPhone.cs
    set /a OK+=1
  ) else (
    echo   [MISSING] GroveLinkPhone.cs  — compile GroveLinkPhone.txt in Sanny ^(F7^)
    set /a BAD+=1
  )

  if exist "%GTA%\CLEO\GroveLink\link.ini" (
    echo   [OK]      link.ini
    echo            %GTA%\CLEO\GroveLink\link.ini
    set /a OK+=1
  ) else (
    echo   [MISSING] link.ini  — run INSTALL.bat to copy it
    set /a BAD+=1
  )
) else (
  echo   [SKIP]    CLEO / phone script / link.ini  ^(need game folder first^)
)

echo.
echo --- Bridge (Python + config) ---
set "PYOK=0"
where python >nul 2>nul
if not errorlevel 1 (
  echo   [OK]      Python  ^(python on PATH^)
  set "PYOK=1"
  set /a OK+=1
)
if "%PYOK%"=="0" (
  where py >nul 2>nul
  if not errorlevel 1 (
    echo   [OK]      Python  ^(py launcher^)
    set "PYOK=1"
    set /a OK+=1
  )
)
if "%PYOK%"=="0" (
  if exist "%LOCALAPPDATA%\Programs\Python\Python38\python.exe" (
    echo   [OK]      Python  3.8 at LocalAppData
    set "PYOK=1"
    set /a OK+=1
  )
)
if "%PYOK%"=="0" (
  if exist "C:\Python27\python.exe" (
    echo   [OK]      Python  2.7 at C:\Python27
    set "PYOK=1"
    set /a OK+=1
  )
)
if "%PYOK%"=="0" (
  echo   [MISSING] Python  — install 2.7.18 or 3.8.10 for Windows 7
  echo            https://www.python.org/downloads/release/python-3810/
  set /a BAD+=1
)

if exist "%REPO%\grovelink\bridge\config.ini" (
  echo   [OK]      config.ini
  echo            %REPO%\grovelink\bridge\config.ini
  set /a OK+=1
) else if exist "%~dp0grovelink\bridge\config.ini" (
  echo   [OK]      config.ini
  set /a OK+=1
) else if exist "%~dp0config.ini" (
  echo   [OK]      config.ini  ^(next to this bat^)
  set /a OK+=1
) else (
  echo   [MISSING] config.ini  — run INSTALL.bat ^(writes port 8088^)
  set /a BAD+=1
)

if exist "%REPO%\grovelink\bridge\grovelink_server.py" (
  echo   [OK]      grovelink_server.py
  set /a OK+=1
) else if exist "%~dp0grovelink_server.py" (
  echo   [OK]      grovelink_server.py
  set /a OK+=1
) else (
  echo   [MISSING] grovelink_server.py  — keep files from the zip / repo
  set /a BAD+=1
)

echo.
echo --- Source + photos folder ---
if exist "%REPO%\grovelink\GroveLinkPhone.txt" (
  echo   [OK]      GroveLinkPhone.txt  ^(CLEO source in repo^)
  echo            %REPO%\grovelink\GroveLinkPhone.txt
  set /a OK+=1
) else if exist "%~dp0grovelink\GroveLinkPhone.txt" (
  echo   [OK]      GroveLinkPhone.txt
  set /a OK+=1
) else (
  echo   [MISSING] GroveLinkPhone.txt  — needed to compile the phone with Sanny F7
  set /a BAD+=1
)

set "PHOTOS=%REPO%\grovelink\bridge\photos"
if not exist "%PHOTOS%" (
  mkdir "%PHOTOS%" >nul 2>&1
)
if exist "%PHOTOS%" (
  echo writable > "%PHOTOS%\.grovelink_write_test" 2>nul
  if exist "%PHOTOS%\.grovelink_write_test" (
    del /f /q "%PHOTOS%\.grovelink_write_test" >nul 2>&1
    echo   [OK]      bridge\photos writable
    echo            %PHOTOS%
    set /a OK+=1
  ) else (
    echo   [MISSING] bridge\photos not writable — check folder permissions
    echo            %PHOTOS%
    set /a BAD+=1
  )
) else (
  echo   [MISSING] bridge\photos  — could not create under repo bridge folder
  set /a BAD+=1
)

echo.
echo --- Firewall note ---
echo   [NOTE]    INSTALL adds rule "GroveLink Phone" for TCP port 8088.
echo            If the phone cannot connect, allow Python / port 8088 in
echo            Windows Firewall, and use the same Wi-Fi ^(not guest/VPN^).

echo.
echo --- URLs to try ---
echo   On this PC:     http://127.0.0.1:8088
echo   Health JSON:    http://127.0.0.1:8088/health
echo   Export zip:     http://127.0.0.1:8088/export.zip
echo   Share page:     http://127.0.0.1:8088/qr
echo   Smoke test:     grovelink\bridge\TEST_BRIDGE.bat  ^(or tests\smoke_bridge.py^)
echo   On your phone:  http://YOUR-PC-LAN-IP:8088
echo                   ^(LAN IP is printed when you start the bridge^)
echo.
echo   Start bridge:   Desktop "GroveLink Phone" or START_GROVELINK.bat
echo   Update pack:    Desktop UPDATE_GROVELINK.bat
echo   In GTA:         K → Camera / STATUS / HELP → Enter or Space
echo.

echo ================================================
if %BAD%==0 (
  color 0A
  echo   RESULT: looks good  ^(%OK% checks OK, 0 missing^)
  echo   Next: start GroveLink Phone, launch GTA, press K.
) else (
  color 0E
  echo   RESULT: %BAD% thing^(s^) missing  ^(%OK% OK^)
  echo   Tip: run INSTALL.bat as Administrator, then check again.
  echo   More help: grovelink\TROUBLESHOOTING.md
)
echo ================================================
echo.
pause
endlocal
