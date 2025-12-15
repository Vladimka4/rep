import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'временный-ключ-для-разработки'
    
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///food_delivery.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки логирования
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')
    
    # Настройки парсера
    PARSER_TIMEOUT = 15
    PARSER_DELAY = 0.5  # Задержка между запросами