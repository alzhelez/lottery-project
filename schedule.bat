@echo off
rem Автозапуск по расписанию через Планировщик Windows.
rem   schedule.bat        — каждый час
rem   schedule.bat 3      — каждые 3 часа
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "HOURS=%~1"
if "%HOURS%"=="" set "HOURS=1"
call "%ROOT%tools\ensure-venv.bat"
if errorlevel 1 goto no_venv
schtasks /Create /F /SC HOURLY /MO %HOURS% /TN "LotteryAnalyzer\Auto" /TR "\"%ROOT%.venv\Scripts\pythonw.exe\" \"%ROOT%python\lp.py\" auto"
if errorlevel 1 goto failed
echo.
echo Готово: цикл «загрузка - анализ - прогноз в журнал» будет запускаться каждые %HOURS% ч.
echo Окно не появляется; журнал работы — data\logs\auto.log, статус — на главной странице приложения.
echo Задача работает, пока вы вошли в Windows. Отключить: unschedule.bat
pause
exit /b 0
:no_venv
echo Окружение Python не найдено: сначала запустите setup.bat
pause
exit /b 1
:failed
echo [ОШИБКА] Не удалось создать задачу в Планировщике.
pause
exit /b 1
