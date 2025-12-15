import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # СТРОКА 1: Использовать переменную окружения или временный ключ для разработки
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # СТРОКИ 2-5: Обработка DATABASE_URL для Render
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # СТРОКА 6: Использовать PostgreSQL или SQLite
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///food_delivery.db'
    
    # СТРОКА 7: Оптимизация
    SQLALCHEMY_TRACK_MODIFICATIONS = False
