import os
import sys
import traceback

print("=== НАЧАЛО ДИАГНОСТИКИ ===", file=sys.stderr)

# 1. Проверяем структуру проекта
print("\n1. Содержимое корневой папки:", file=sys.stderr)
try:
    for item in os.listdir("/opt/render/project/src"):
        print(f"   - {item}", file=sys.stderr)
except Exception as e:
    print(f"   Ошибка: {e}", file=sys.stderr)

# 2. Проверяем папку app/
print("\n2. Содержимое папки 'app/':", file=sys.stderr)
try:
    app_path = "/opt/render/project/src/app"
    if os.path.exists(app_path):
        for item in os.listdir(app_path):
            print(f"   - {item}", file=sys.stderr)
    else:
        print("   Папка 'app/' не существует!", file=sys.stderr)
except Exception as e:
    print(f"   Ошибка: {e}", file=sys.stderr)

# 3. Проверяем наличие routes.py
print("\n3. Проверка файла routes.py:", file=sys.stderr)
routes_path = "/opt/render/project/src/app/routes.py"
if os.path.exists(routes_path):
    print(f"   Файл существует, размер: {os.path.getsize(routes_path)} байт", file=sys.stderr)
    
    # Читаем первые 3 строки
    with open(routes_path, 'r') as f:
        lines = [f.readline().strip() for _ in range(3)]
    print(f"   Первые строки: {lines}", file=sys.stderr)
else:
    print("   Файл routes.py НЕ НАЙДЕН!", file=sys.stderr)

print("\n=== КОНЕЦ ДИАГНОСТИКИ ===", file=sys.stderr)

# Пробуем импортировать
try:
    from app import create_app
    app = create_app()
    print("=== ПРИЛОЖЕНИЕ УСПЕШНО СОЗДАНО ===", file=sys.stderr)
except Exception as e:
    print(f"\n=== КРИТИЧЕСКАЯ ОШИБКА ===", file=sys.stderr)
    print(f"Тип ошибки: {type(e).__name__}", file=sys.stderr)
    print(f"Сообщение: {str(e)}", file=sys.stderr)
    print("\nТрассировка:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    # Создаём пустое приложение, чтобы Render не перезапускал постоянно
    from flask import Flask
    app = Flask(__name__)
    @app.route('/')
    def diagnostic():
        return "Диагностический режим: проверьте логи в панели Render"
