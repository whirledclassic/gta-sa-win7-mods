@echo off
setlocal EnableExtensions EnableDelayedExpansion
title GroveLink Phone Bridge

REM Find the real bridge folder (Desktop copy of this bat has no .py next to it).
REM 1) grovelink_server.py next to this bat  -> run from bridge folder
REM 2) Desktop GroveLink_REPO.txt            -> REPO\grovelink\bridge
REM 3) %~dp0grovelink\bridge                 -> bat somehow at repo root
REM Else: plain English help, pause, exit.

set "BRIDGE_DIR="

if exist "%~dp0grovelink_server.py" (
  set "BRIDGE_DIR=%~dp0"
  goto have_bridge
)

REM Strip trailing CR from set /p (Win7 quirk) so paths resolve.
if exist "%USERPROFILE%\Desktop\GroveLink_REPO.txt" (
  set /p REPO_FROM_FILE=<"%USERPROFILE%\Desktop\GroveLink_REPO.txt"
  if defined REPO_FROM_FILE (
    for /f "delims=" %%A in ("!REPO_FROM_FILE!") do set "REPO_FROM_FILE=%%A"
    if exist "!REPO_FROM_FILE!\grovelink\bridge\grovelink_server.py" (
      set "BRIDGE_DIR=!REPO_FROM_FILE!\grovelink\bridge"
      goto have_bridge
    )
  )
)
if exist "%PUBLIC%\Desktop\GroveLink_REPO.txt" (
  set /p REPO_FROM_FILE2=<"%PUBLIC%\Desktop\GroveLink_REPO.txt"
  if defined REPO_FROM_FILE2 (
    for /f "delims=" %%A in ("!REPO_FROM_FILE2!") do set "REPO_FROM_FILE2=%%A"
    if exist "!REPO_FROM_FILE2!\grovelink\bridge\grovelink_server.py" (
      set "BRIDGE_DIR=!REPO_FROM_FILE2!\grovelink\bridge"
      goto have_bridge
    )
  )
)
if exist "%~dp0GroveLink_REPO.txt" (
  set /p REPO_FROM_FILE3=<"%~dp0GroveLink_REPO.txt"
  if defined REPO_FROM_FILE3 (
    for /f "delims=" %%A in ("!REPO_FROM_FILE3!") do set "REPO_FROM_FILE3=%%A"
    if exist "!REPO_FROM_FILE3!\grovelink\bridge\grovelink_server.py" (
      set "BRIDGE_DIR=!REPO_FROM_FILE3!\grovelink\bridge"
      goto have_bridge
    )
  )
)

if exist "%~dp0grovelink\bridge\grovelink_server.py" (
  set "BRIDGE_DIR=%~dp0grovelink\bridge"
  goto have_bridge
)

echo.
echo ================================================================
echo  GroveLink bridge files were not found.
echo.
echo  This usually means you double-clicked START_GROVELINK on the
echo  Desktop, but the phone bridge scripts live in the zip folder.
echo.
echo  Try one of these:
echo    1. Double-click the Desktop shortcut  "GroveLink Phone"
echo       ^(that launches the bridge from the install folder^)
echo    2. Open your extracted zip folder, then:
echo         grovelink\bridge\START_GROVELINK.bat
echo       ^(nested zip path may look like:
echo         gta-sa-win7-mods-main\gta-sa-win7-mods-main\grovelink\bridge^)
echo    3. Re-run INSTALL.bat as administrator from the zip folder
echo       ^(writes GroveLink_REPO.txt so Desktop START works^)
echo ================================================================
echo.
pause
exit /b 1

:have_bridge
cd /d "!BRIDGE_DIR!"
if not exist "grovelink_server.py" (
  echo.
  echo  Still cannot find grovelink_server.py in:
  echo    !BRIDGE_DIR!
  echo  Re-run INSTALL.bat from the extracted zip folder.
  echo.
  pause
  exit /b 1
)

REM Pack version from repo-root VERSION (bridge is grovelink\bridge)
set "GL_VER=unknown"
if exist "..\..\VERSION" (
  set /p GL_VER=<"..\..\VERSION"
)
REM Strip quotes + trailing CR (Win7 set /p quirk)
if defined GL_VER set "GL_VER=%GL_VER:"=%"
for /f "delims=" %%A in ("%GL_VER%") do set "GL_VER=%%A"
echo.
echo ================================================================
echo  GROVELINK PHONE BRIDGE
echo  Pack VERSION : %GL_VER%
echo ================================================================
echo.

where python >nul 2>nul
if %errorlevel%==0 (
  python grovelink_server.py
  goto end
)

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 grovelink_server.py
  if errorlevel 1 py -2 grovelink_server.py
  goto end
)

if exist "%LOCALAPPDATA%\Programs\Python\Python38\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python38\python.exe" grovelink_server.py
  goto end
)

if exist "C:\Python27\python.exe" (
  C:\Python27\python.exe grovelink_server.py
  goto end
)

echo.
echo ================================================================
echo  Python was NOT found on this PC.
echo.
echo  GroveLink needs Python to run the phone bridge.
echo  On Windows 7 install Python 3.8.10 (recommended) or 2.7.18.
echo.
echo  Download Python 3.8.10 here:
echo    https://www.python.org/downloads/release/python-3810/
echo.
echo  On that page scroll to Files and pick:
echo    - Windows x86-64 executable installer  (most 64-bit PCs)
echo    - Windows x86 executable installer     (32-bit)
echo  During setup, CHECK "Add Python to PATH", then re-run this bat.
echo.
echo  Opening the download page in your browser now...
echo ================================================================
echo.
start "" "https://www.python.org/downloads/release/python-3810/"
pause
goto end
:end
pause
