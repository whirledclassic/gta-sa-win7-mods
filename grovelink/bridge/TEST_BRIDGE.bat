@echo off
title GroveLink — smoke test bridge
cd /d "%~dp0"
echo Running tests\smoke_bridge.py (stdlib only)...
echo.

where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0..\..\tests\smoke_bridge.py"
  goto done
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0..\..\tests\smoke_bridge.py"
  if errorlevel 1 py -2 "%~dp0..\..\tests\smoke_bridge.py"
  goto done
)
if exist "%LOCALAPPDATA%\Programs\Python\Python38\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python38\python.exe" "%~dp0..\..\tests\smoke_bridge.py"
  goto done
)
if exist "C:\Python27\python.exe" (
  C:\Python27\python.exe "%~dp0..\..\tests\smoke_bridge.py"
  goto done
)
echo Python not found — install 3.8.10 for Win7 then retry.
echo https://www.python.org/downloads/release/python-3810/
pause
exit /b 1
:done
echo.
pause
