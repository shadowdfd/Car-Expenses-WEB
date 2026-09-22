#!/usr/bin/env python3
"""
Скрипт автоматической инициализации базы данных.
Создаёт таблицы, если они ещё не существуют.
"""

import os
import sys

def init_database():
    """Инициализирует базу данных, если она не существует."""
    try:
        from app import app, db

        with app.app_context():
            # Проверяем, существует ли база данных
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')

            if os.path.exists(db_path):
                print(f"[INFO] База данных уже существует: {db_path}")

                # Проверяем, есть ли таблицы
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()

                if tables:
                    print(f"[INFO] Найдены таблицы: {', '.join(tables)}")
                    print("[INFO] Инициализация не требуется")
                    return True
                else:
                    print("[INFO] База данных существует, но таблиц нет. Создаём таблицы...")
            else:
                print(f"[INFO] База данных не найдена. Создаём: {db_path}")

            # Создаём все таблицы
            db.create_all()
            print("[SUCCESS] База данных успешно инициализирована!")

            # Выводим список созданных таблиц
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            if tables:
                print(f"[INFO] Созданы таблицы: {', '.join(tables)}")

            return True

    except Exception as e:
        print(f"[ERROR] Ошибка при инициализации базы данных: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
