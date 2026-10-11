@echo off
rem Обновляет программу до последней версии из GitHub.
rem   update.bat          скачать изменения, обновить библиотеки Python и интерфейса
rem Ваши данные (data\, .env, .venv) не трогаются. Если папка ещё не связана с GitHub
rem (программа распакована из архива), update.bat один раз свяжет её — см. docs\INSTALL.md.
chcp 65001 >nul
rem Обновление может заменить и сам update.bat, а cmd читает .bat по ходу выполнения —
rem поэтому работаем из копии во временной папке.
if /i not "%~1"=="--run" (
  copy /y "%~f0" "%TEMP%\lottery-update.bat" >nul
  "%TEMP%\lottery-update.bat" --run "%~dp0."
)
setlocal
cd /d "%~2"

set "REPO=https://github.com/alzhelez/lottery-project.git"

where git >nul 2>nul
if errorlevel 1 (
  echo Git не установлен. Установите: winget install Git.Git  ^(или https://git-scm.com^),
  echo затем откройте новое окно консоли и запустите update.bat ещё раз.
  goto failed
)

call :version OLD

if exist ".git" goto pull

echo Папка ещё не связана с GitHub — связываю ^(один раз^).
echo Файлы программы будут заменены версией из репозитория; данные и .env останутся.
choice /m "Продолжить"
if errorlevel 2 goto failed
git init -q
git remote add origin "%REPO%"
git fetch -q origin
if errorlevel 1 goto no_network
set "BRANCH="
for /f "tokens=2" %%r in ('git ls-remote --symref origin HEAD 2^>nul ^| findstr /b "ref:"') do set "BRANCH=%%r"
set "BRANCH=%BRANCH:refs/heads/=%"
if "%BRANCH%"=="" set "BRANCH=master"
git symbolic-ref HEAD refs/heads/%BRANCH%
git reset -q origin/%BRANCH%
git checkout -q -- .
git branch -q --set-upstream-to=origin/%BRANCH%
goto deps

:pull
echo Скачиваю изменения...
git pull --ff-only
if errorlevel 1 (
  echo.
  echo Не удалось обновить: в папке изменены файлы программы, или нет связи с GitHub.
  echo Посмотреть изменённые файлы: git status
  echo Отложить свои изменения и обновиться: git stash, затем update.bat
  goto failed
)

:deps
echo Обновляю библиотеки Python...
call tools\ensure-venv.bat
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r python\requirements.txt
if errorlevel 1 goto failed

echo Обновляю зависимости интерфейса...
where bun >nul 2>nul && (call bun install) || (call npm install --no-audit --no-fund)
if errorlevel 1 goto failed

call :version NEW
echo.
echo Готово. Версия %NEW% ^(была %OLD%^)
echo Что нового — CHANGELOG.md. Запуск: start.bat
pause
exit /b 0

:version
rem Номер версии из config\version.json: { "version": "40.3.0_11102026" }
set "_V="
for /f "tokens=2 delims=:}" %%v in (config\version.json) do set "_V=%%v"
set "_V=%_V: =%"
set "%1=%_V:"=%"
exit /b 0

:no_network
echo Не удалось связаться с GitHub. Проверьте интернет.
:failed
pause
exit /b 1
