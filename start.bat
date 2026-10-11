@echo off
chcp 65001 >nul
cd /d "%~dp0"
call tools\ensure-venv.bat
if errorlevel 1 goto failed
if exist "node_modules" goto run
echo Зависимости интерфейса не установлены — запускаю setup.bat
call setup.bat
if not exist "node_modules" goto failed
:run
echo Запуск: откройте http://localhost:3000 (остановить — Ctrl+C)
where bun >nul 2>nul && (call bun run dev & exit /b)
call npm run dev
exit /b
:failed
pause
