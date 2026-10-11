@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo === Лотерейный анализатор: установка ===
echo.

rem --- 1. Python 3.10+ ---
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY goto install_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto old_python
for /f "delims=" %%v in ('%PY% --version') do echo Найден %%v

rem --- 2. Окружение Python в папке проекта ---
if exist ".venv\Scripts\python.exe" goto venv_ready
echo Создаю окружение .venv ...
%PY% -m venv .venv
if errorlevel 1 goto venv_failed
:venv_ready
echo Устанавливаю библиотеки Python ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r python\requirements-dev.txt
if errorlevel 1 goto pip_failed

rem --- 3. Зависимости интерфейса ---
where bun >nul 2>nul && goto use_bun
where npm >nul 2>nul || goto install_node
echo Устанавливаю зависимости интерфейса: npm install ...
call npm install --no-audit --no-fund
if errorlevel 1 goto node_failed
goto done
:use_bun
echo Устанавливаю зависимости интерфейса: bun install ...
call bun install
if errorlevel 1 goto node_failed

:done
echo.
echo Готово. Запуск приложения: start.bat, затем откройте http://localhost:3000
echo Командная строка: lp.bat fetch, lp.bat analyze --game 4x20 и т. д.
echo Автозапуск по расписанию: schedule.bat
pause
exit /b 0

:install_python
where winget >nul 2>nul || goto no_python
echo Python не найден. Установить Python 3.12 через winget?
choice /C YN /M "Y - установить, N - отмена"
if errorlevel 2 goto no_python
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto no_python
echo.
echo Python установлен. Закройте это окно и запустите setup.bat ещё раз, чтобы Windows увидела новый путь.
pause
exit /b 0
:install_node
where winget >nul 2>nul || goto no_node
echo Node.js не найден. Установить Node.js LTS через winget?
choice /C YN /M "Y - установить, N - отмена"
if errorlevel 2 goto no_node
winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto no_node
echo.
echo Node.js установлен. Закройте это окно и запустите setup.bat ещё раз.
pause
exit /b 0
:no_python
echo [ОШИБКА] Python не найден.
echo Установите Python 3.10 или новее с https://www.python.org/downloads/
echo и при установке отметьте пункт "Add python.exe to PATH". Затем запустите setup.bat снова.
pause
exit /b 1
:old_python
echo [ОШИБКА] Нужен Python 3.10 или новее, найден:
%PY% --version
pause
exit /b 1
:venv_failed
echo [ОШИБКА] Не удалось создать окружение .venv
pause
exit /b 1
:pip_failed
echo [ОШИБКА] Не удалось установить библиотеки Python. Проверьте подключение к интернету.
pause
exit /b 1
:no_node
echo [ОШИБКА] Не найдены ни Node.js, ни Bun. Установите Node.js 20+ с https://nodejs.org
pause
exit /b 1
:node_failed
echo [ОШИБКА] Не удалось установить зависимости интерфейса.
pause
exit /b 1
