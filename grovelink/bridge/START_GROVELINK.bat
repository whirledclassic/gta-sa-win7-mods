@echo off
title GroveLink Phone Bridge
cd /d "%~dp0"

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
echo Python was not found.
echo Install Python 2.7.18 or 3.8.10 for Windows 7, then run this bat again.
echo https://www.python.org/downloads/release/python-3810/
echo.
pause
:end
pause
