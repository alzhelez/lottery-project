@echo off
rem Выкладывает проект в репозиторий GitHub (по умолчанию github.com/alzhelez/lottery-project).
rem   publish.bat                       обычная публикация новой версии
rem   publish.bat https://github.com/<вы>/<репозиторий>.git   другой репозиторий
rem История репозитория сохраняется: новая версия ложится обычным коммитом поверх неё,
rem без принудительной перезаписи. Ваши данные (.env, .venv, результаты, журнал) не выкладываются.
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "REPO=%~1"
if "%REPO%"=="" set "REPO=https://github.com/alzhelez/lottery-project.git"

where git >nul 2>nul
if errorlevel 1 (
  echo Git не установлен. Установите: winget install Git.Git  ^(или https://git-scm.com^),
  echo затем откройте новое окно консоли и запустите publish.bat ещё раз.
  exit /b 1
)

rem Версия из config\version.json: { "version": "40.3.0_11102026" }
set "VER="
for /f "tokens=2 delims=:}" %%v in (config\version.json) do set "VER=%%~v"
set "VER=%VER: =%"
set "VER=%VER:"=%"
if "%VER%"=="" set "VER=без номера"

rem Имя и почта автора коммитов — если git ещё не настроен, спросим один раз.
git config user.name >nul 2>nul || (
  set /p "GNAME=Ваше имя для коммитов: "
  git config --global user.name "!GNAME!"
)
git config user.email >nul 2>nul || (
  set /p "GMAIL=Почта для коммитов (как на GitHub): "
  git config --global user.email "!GMAIL!"
)

set "FRESH="
if not exist ".git" (
  echo Создаю локальный репозиторий...
  git init -q
  set "FRESH=1"
)
git remote get-url origin >nul 2>nul && (git remote set-url origin "%REPO%") || (git remote add origin "%REPO%")

echo Получаю историю из %REPO% ...
git fetch -q origin
if errorlevel 1 (
  echo Не удалось связаться с GitHub. Проверьте адрес репозитория и интернет.
  echo При первом обращении Git откроет окно входа в GitHub — войдите в свой аккаунт.
  exit /b 1
)

rem Основная ветка репозитория на GitHub: main или master.
set "BRANCH="
for /f "tokens=2" %%r in ('git ls-remote --symref origin HEAD 2^>nul ^| findstr /b "ref:"') do set "BRANCH=%%r"
set "BRANCH=%BRANCH:refs/heads/=%"
if "%BRANCH%"=="" set "BRANCH=main"

if defined FRESH (
  git symbolic-ref HEAD refs/heads/%BRANCH%
  git ls-remote --exit-code --heads origin %BRANCH% >nul 2>nul
  if not errorlevel 1 (
    rem Репозиторий не пустой: встаём на его историю, файлы на диске не меняются.
    git reset -q --soft origin/%BRANCH%
  )
)

git add -A
git diff --cached --quiet
if not errorlevel 1 (
  echo Изменений нет — выкладывать нечего.
  goto push
)
echo.
echo Будут выложены изменения:
git diff --cached --stat | more
echo.
choice /m "Выложить версию %VER% на GitHub"
if errorlevel 2 (
  git reset -q
  echo Отменено.
  exit /b 1
)
git commit -q -m "Версия %VER%" -m "Изменения — в CHANGELOG.md."

:push
git push -u origin %BRANCH%
if errorlevel 1 (
  echo.
  echo Не удалось выложить. Если на GitHub есть изменения, которых нет здесь,
  echo сначала заберите их: git pull --rebase origin %BRANCH% — и запустите publish.bat снова.
  exit /b 1
)
echo.
echo Готово: %REPO:.git=%
echo Проверки CI: %REPO:.git=%/actions
exit /b 0
