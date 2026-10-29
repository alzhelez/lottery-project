#!/usr/bin/env bash
# Кроссплатформенный скрипт запуска lottery-project для Linux/macOS

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"
NODE_BIN="node"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка виртуального окружения
check_venv() {
    if [ ! -d "$VENV_DIR" ] || [ ! -f "$PYTHON" ]; then
        echo_warn "Виртуальное окружение не найдено или повреждено"
        echo_info "Запускаю setup.sh для инициализации..."
        ./setup.sh
    fi
}

# Проверка зависимостей Node.js
check_node_modules() {
    if [ ! -d "node_modules" ]; then
        echo_warn "Зависимости Node.js не установлены"
        echo_info "Устанавливаю зависимости..."
        if command -v npm &> /dev/null; then
            npm install --silent
        elif command -v bun &> /dev/null; then
            bun install
        else
            echo_error "Не найден npm или bun!"
            exit 1
        fi
    fi
}

# Основная функция
main() {
    echo ""
    echo "╔════════════════════════════════════════════════╗"
    echo "║   Lottery Project - Запуск                    ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""

    # Проверка и настройка окружения
    check_venv
    check_node_modules

    echo_info "Запуск Next.js сервера..."
    echo_info "Приложение будет доступно на http://localhost:3000"
    echo ""
    echo -e "${YELLOW}Нажмите Ctrl+C для остановки${NC}"
    echo ""

    # Запуск Next.js dev-сервера
    if command -v npm &> /dev/null; then
        npm run dev
    elif command -v bun &> /dev/null; then
        bun run dev
    else
        echo_error "Не найден npm или bun!"
        exit 1
    fi
}

# Обработка сигналов для корректного завершения
trap "echo ''; echo_info 'Остановка сервера...'; exit 0" SIGINT SIGTERM

main "$@"
