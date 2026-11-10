@echo off
chcp 65001 >nul
schtasks /End /TN "LotteryAnalyzer\Bot" >nul 2>nul
schtasks /Delete /F /TN "LotteryAnalyzer\Bot"
if errorlevel 1 (echo Задача не найдена.) else (echo Бот убран из автозагрузки.)
pause
