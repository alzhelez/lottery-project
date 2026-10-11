@echo off
rem Командная строка движка. Примеры:
rem   lp.bat fetch            lp.bat analyze --game 4x20      lp.bat diagnose --api
rem   lp.bat journal          lp.bat godmode --game 4x20 --budget 60
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
call "%ROOT%tools\ensure-venv.bat"
if errorlevel 1 exit /b 1
"%ROOT%.venv\Scripts\python.exe" "%ROOT%python\lp.py" %*
exit /b %errorlevel%
