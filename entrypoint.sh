#!/bin/sh
set -e

echo "[entrypoint] Запуск Car Expenses приложения..."

# Инициализация базы данных
echo "[entrypoint] Проверка и инициализация базы данных..."
python /app/init_db.py

if [ $? -eq 0 ]; then
    echo "[entrypoint] База данных готова к работе"
else
    echo "[entrypoint] Ошибка инициализации базы данных!" >&2
    exit 1
fi

# Запуск приложения через gunicorn
echo "[entrypoint] Запуск Flask приложения на порту 8000..."
exec gunicorn -w 4 -b 0.0.0.0:8000 app:app
