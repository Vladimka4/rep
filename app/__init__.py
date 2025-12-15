from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from config import Config
import logging
from logging.handlers import RotatingFileHandler
import os

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'
csrf = CSRFProtect()

def setup_logging(app):
    """Настройка логирования"""
    if not app.debug:
        # Создаем директорию для логов
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Файловый обработчик
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Food Delivery запущен')
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчик к корневому логгеру
    logging.getLogger().addHandler(console_handler)
    logging.getLogger().setLevel(logging.DEBUG)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Настройка логирования
    setup_logging(app)
    
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Загрузчик пользователя
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))
    
    # Регистрация Blueprints
    from .routes import main
    from .auth import auth
    from .user import user
    from .admin import admin
    
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(user, url_prefix='/user')
    app.register_blueprint(admin, url_prefix='/admin')
    
    # Регистрация CLI команд
    from .commands import init_app as commands_init
    commands_init(app)
    
    # Создание таблиц БД и администратора в контексте приложения
    with app.app_context():
        try:
            # Создаем таблицы
            db.create_all()
            app.logger.info("Таблицы БД созданы/проверены")
            
            # Создание администратора (как было)
            from .models import User
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin_user = User(
                    username='admin',
                    is_admin=True
                )
                admin_user.set_password('25102510')
                db.session.add(admin_user)
                db.session.commit()
                app.logger.info("Администратор создан")
                
        except Exception as e:
            app.logger.error(f"Ошибка инициализации БД: {e}")
    return app