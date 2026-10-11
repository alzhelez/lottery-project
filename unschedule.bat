@echo off
chcp 65001 >nul
schtasks /Delete /F /TN "LotteryAnalyzer\Auto"
if errorlevel 1 (echo Задача не найдена.) else (echo Автозапуск отключён.)
pause
