@echo off
rem Telegram-бот в автозагрузке: задача Планировщика Windows запускает его при входе в систему,
rem без окна. Бот работает отдельно от сайта и отвечает, даже когда приложение закрыто.
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
call "%ROOT%tools\ensure-venv.bat"
if errorlevel 1 goto no_venv
schtasks /Create /F /SC ONLOGON /TN "LotteryAnalyzer\Bot" /TR "\"%ROOT%.venv\Scripts\pythonw.exe\" \"%ROOT%python\lp.py\" bot"
if errorlevel 1 goto failed
schtasks /Run /TN "LotteryAnalyzer\Bot" >nul
echo.
echo Готово: бот запущен и будет запускаться сам при входе в Windows.
echo Напишите боту /menu. Отключить: bot-uninstall.bat
pause
exit /b 0
:no_venv
echo Окружение Python не найдено: сначала запустите setup.bat
pause
exit /b 1
:failed
echo [ОШИБКА] Не удалось создать задачу в Планировщике. Запустите этот файл от имени администратора
echo или пользуйтесь bot.bat (бот работает, пока открыто окно).
pause
exit /b 1
