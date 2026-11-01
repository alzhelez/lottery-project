#!/usr/bin/env bash
# CLI обертка для lp.py (Linux/macOS)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

VENV_DIR=".venv"
PYTHON="$VENV_DIR/bin/python"

# Проверка виртуального окружения
if [ ! -d "$VENV_DIR" ] || [ ! -f "$PYTHON" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "Запустите: ./setup.sh"
    exit 1
fi

# Передать все аргументы в lp.py
"$PYTHON" python/lp.py "$@"
