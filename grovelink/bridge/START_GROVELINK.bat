@echo off
title GroveLink Phone Bridge
cd /d "%~dp0"

REM Pack version from repo-root VERSION (bridge is grovelink\bridge)
set "GL_VER=unknown"
if exist "%~dp0..\..\VERSION" (
  set /p GL_VER=<"%~dp0..\..\VERSION"
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
