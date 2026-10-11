#!/bin/sh
# При первом запуске с пустым томом данных кладём в него тиражи из образа.
set -e
if [ ! -d "$LOTTERY_DATA_DIR/draws" ] || [ -z "$(ls -A "$LOTTERY_DATA_DIR/draws" 2>/dev/null)" ]; then
  mkdir -p "$LOTTERY_DATA_DIR"
  cp -r /app/data-seed/. "$LOTTERY_DATA_DIR"/
  echo "Данные инициализированы в $LOTTERY_DATA_DIR"
fi
exec "$@"
