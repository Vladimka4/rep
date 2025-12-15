from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect  # Добавили
from config import Config

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'
csrf = CSRFProtect()  # Добавили

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)  # Инициализировали
    
    # Загрузчик пользователя
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))
    
    # Регистрация Blueprints
    from .routes import main
    from .auth import auth
    from .user import user
    
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(user, url_prefix='/user')
    
    # Создание таблиц БД
    with app.app_context():
        db.create_all()
    from .models import User
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            is_admin=True
        )
        admin.set_password('25102510')
        db.session.add(admin)
        db.session.commit()
    return app