@echo off
rem Telegram-бот с кнопками: слушает бота, пока это окно открыто (остановить — Ctrl+C).
rem Чтобы бот работал сам, без окна, после входа в Windows: bot-install.bat
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
call "%ROOT%tools\ensure-venv.bat"
if errorlevel 1 exit /b 1
"%ROOT%.venv\Scripts\python.exe" "%ROOT%python\lp.py" bot
pause
