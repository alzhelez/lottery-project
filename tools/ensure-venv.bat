@echo off
rem Проверяет окружение Python проекта (.venv) и при необходимости создаёт его и ставит библиотеки.
rem Вызывается из lp.bat, start.bat и schedule.bat — отдельно запускать не нужно.
setlocal
set "ROOT=%~dp0.."
set "VPY=%ROOT%\.venv\Scripts\python.exe"
set "RETRIED="

:check
if not exist "%VPY%" goto create
"%VPY%" -c "import numpy, scipy, sklearn, requests, openpyxl" >nul 2>nul
if not errorlevel 1 exit /b 0
echo Окружение Python есть, но библиотек не хватает — устанавливаю...
goto install

:create
echo Окружение Python (.venv) не найдено — создаю его. Это нужно один раз, займёт 1-3 минуты.
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY goto no_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 goto old_python
%PY% -m venv "%ROOT%\.venv"
if errorlevel 1 goto venv_failed

:install
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip >nul 2>nul
"%VPY%" -m pip install --disable-pip-version-check -q -r "%ROOT%\python\requirements.txt"
if not errorlevel 1 goto installed
if defined RETRIED goto pip_failed
rem окружение могло сломаться (например, после обновления или удаления Python) — пересоздаём
set "RETRIED=1"
echo Окружение повреждено — пересоздаю...
rmdir /s /q "%ROOT%\.venv"
goto create

:installed
echo Окружение Python готово.
exit /b 0

:no_python
echo [ОШИБКА] Python не найден. Запустите setup.bat — он предложит установить Python.
exit /b 1
:old_python
echo [ОШИБКА] Нужен Python 3.10 или новее. Запустите setup.bat.
exit /b 1
:venv_failed
echo [ОШИБКА] Не удалось создать окружение .venv в папке проекта. Проверьте права на запись в папку.
exit /b 1
:pip_failed
echo [ОШИБКА] Не удалось установить библиотеки Python. Проверьте подключение к интернету.
exit /b 1
