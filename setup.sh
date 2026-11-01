#!/usr/bin/env bash
# Кроссплатформенный скрипт установки lottery-project для Linux/macOS

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

echo_step() {
    echo -e "\n${BLUE}▶${NC} $1"
}

# Проверка Python
check_python() {
    echo_step "Проверка Python..."

    if ! command -v python3 &> /dev/null; then
        echo_error "Python 3 не найден!"
        echo ""
        echo "Установите Python 3.10+ одним из способов:"
        echo "  • Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
        echo "  • macOS: brew install python@3.11"
        echo "  • Или скачайте с https://www.python.org/downloads/"
        echo ""
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
        echo_error "Требуется Python 3.10+, установлен $PYTHON_VERSION"
        exit 1
    fi

    echo_info "Python: $PYTHON_VERSION ✓"
}

# Проверка Node.js
check_node() {
    echo_step "Проверка Node.js..."

    if ! command -v node &> /dev/null; then
        echo_error "Node.js не найден!"
        echo ""
        echo "Установите Node.js 20+ одним из способов:"
        echo "  • Ubuntu/Debian: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs"
        echo "  • macOS: brew install node@20"
        echo "  • Или скачайте с https://nodejs.org/"
        echo ""
        exit 1
    fi

    NODE_VERSION=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)

    if [ "$NODE_MAJOR" -lt 20 ]; then
        echo_error "Требуется Node.js 20+, установлен v$NODE_VERSION"
        exit 1
    fi

    echo_info "Node.js: v$NODE_VERSION ✓"
}

# Создание виртуального окружения Python
setup_venv() {
    echo_step "Настройка виртуального окружения Python..."

    if [ -d "$VENV_DIR" ]; then
        echo_warn "Виртуальное окружение уже существует, пересоздаю..."
        rm -rf "$VENV_DIR"
    fi

    python3 -m venv "$VENV_DIR"

    if [ ! -f "$PYTHON" ]; then
        echo_error "Не удалось создать виртуальное окружение!"
        exit 1
    fi

    echo_info "Виртуальное окружение создано"
}

# Установка зависимостей Python
install_python_deps() {
    echo_step "Установка зависимостей Python..."

    "$PYTHON" -m pip install --upgrade pip setuptools wheel --quiet
    "$PYTHON" -m pip install -r python/requirements.txt --quiet

    echo_info "Зависимости Python установлены"
}

# Установка зависимостей Node.js
install_node_deps() {
    echo_step "Установка зависимостей Node.js..."

    if command -v npm &> /dev/null; then
        npm install --silent
    elif command -v bun &> /dev/null; then
        bun install
    else
        echo_error "Не найден npm или bun!"
        exit 1
    fi

    echo_info "Зависимости Node.js установлены"
}

# Создание файла .env если не существует
setup_env() {
    echo_step "Проверка файла конфигурации..."

    if [ ! -f ".env" ]; then
        echo_warn "Файл .env не найден, создаю из .env.example..."
        cp .env.example .env
        echo_info "Файл .env создан. Отредактируйте его при необходимости."
    else
        echo_info "Файл .env уже существует"
    fi
}

# Создание папок данных
setup_data_dirs() {
    echo_step "Создание папок данных..."

    mkdir -p data/{draws,results,journal,my_tickets,logs,api_samples,rules}
    mkdir -p backup

    echo_info "Папки данных созданы"
}

# Основная функция
main() {
    echo ""
    echo "╔════════════════════════════════════════════════╗"
    echo "║   Установка lottery-project v42.2.2           ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""

    check_python
    check_node
    setup_venv
    install_python_deps
    install_node_deps
    setup_env
    setup_data_dirs

    echo ""
    echo -e "${GREEN}✓ Установка завершена успешно!${NC}"
    echo ""
    echo "Для запуска приложения выполните:"
    echo "  ./start.sh"
    echo ""
    echo "Для CLI команд:"
    echo "  ./lp.sh fetch         # Загрузить тиражи"
    echo "  ./lp.sh scan          # Проверить на случайность"
    echo "  ./lp.sh analyze --game 6x45   # Анализ игры"
    echo ""
}

main "$@"
