from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from config import Config

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    
    # Загрузчик пользователя ВНУТРИ функции
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User  # ← ТОЧКА вместо 'app'
        return User.query.get(int(user_id))
    
    # Регистрация Blueprints - ВАЖНО: относительные импорты
    from .routes import main      # ← ИЗМЕНИТЕ ЭТУ СТРОКУ
    from .auth import auth        # ← И ЭТУ
    from .user import user        # ← И ЭТУ
    
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(user, url_prefix='/user')
    
    # Создание таблиц БД
    with app.app_context():
        db.create_all()
    
    return app
