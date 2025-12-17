from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm
from flask_admin.form.upload import FileUploadField
from wtforms.fields import PasswordField, TextAreaField
from flask_login import login_required, current_user
from . import db
from .models import User, Category, Dish, Order, OrderItem, Favorite
from .parsers.nsm_parser import NSMParser
import logging
import os

logger = logging.getLogger(__name__)

# ============================================================================
# 1. BLUEPRINT для парсинга (старый функционал)
# ============================================================================

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

@admin_bp.route('/parse-nsm', methods=['GET'])
@login_required
def parse_nsm():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('admin/parse_nsm.html')

@admin_bp.route('/parse-nsm-action', methods=['POST'])
@login_required
def parse_nsm_action():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    base_url = request.form.get('base_url', 'https://nsm-22.ru/')
    specific_section = request.form.get('specific_section')
    
    parser = NSMParser(base_url)
    
    if specific_section:
        # Парсим конкретный раздел
        section_name = specific_section.split('/')[-2].replace('-', ' ').title()
        dishes = parser.parse_section(specific_section, section_name)
        
        if dishes:
            parser.save_to_database(dishes)
            flash(f'Успешно спарсено {len(dishes)} блюд из раздела "{section_name}"', 'success')
        else:
            flash('Не удалось получить блюда из указанного раздела', 'danger')
    else:
        # Парсим весь сайт
        dishes = parser.parse_all_menu()
        
        if dishes:
            parser.save_to_database(dishes)
            flash(f'Успешно спарсено {len(dishes)} блюд со всего сайта', 'success')
        else:
            flash('Не удалось получить меню', 'danger')
    
    return redirect(url_for('admin_bp.parse_nsm'))

# ============================================================================
# 2. FLASK-ADMIN панель управления
# ============================================================================

class SecureModelView(ModelView):
    """Безопасный ModelView с проверкой прав администратора"""
    form_base_class = SecureForm
    page_size = 50
    create_modal = True
    edit_modal = True
    can_export = True
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login', next=request.url))

class UserAdminView(SecureModelView):
    """Админка для пользователей"""
    column_list = ['id', 'username', 'is_admin', 'is_active', 'created_at', 'orders_count']
    column_searchable_list = ['username']
    column_filters = ['is_admin', 'is_active', 'created_at']
    column_sortable_list = ['id', 'username', 'created_at']
    form_columns = ['username', 'password', 'is_admin', 'is_active']
    column_labels = {
        'username': 'Имя пользователя',
        'is_admin': 'Администратор',
        'is_active': 'Активен',
        'created_at': 'Дата регистрации',
        'orders_count': 'Количество заказов'
    }
    
    def scaffold_form(self):
        form_class = super().scaffold_form()
        form_class.password = PasswordField('Новый пароль')
        return form_class
    
    def on_model_change(self, form, model, is_created):
        if form.password.data:
            from . import bcrypt
            model.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
    
    def orders_count_formatter(self, context, model, name):
        return len(model.orders)
    
    column_formatters = {
        'orders_count': orders_count_formatter
    }

class CategoryAdminView(SecureModelView):
    """Админка для категорий"""
    column_list = ['id', 'name', 'image', 'dishes_count']
    column_searchable_list = ['name']
    form_columns = ['name', 'image']
    column_labels = {
        'name': 'Название',
        'image': 'Изображение',
        'dishes_count': 'Количество блюд'
    }
    
    def scaffold_form(self):
        form_class = super().scaffold_form()
        # Для простоты делаем обычное текстовое поле для имени файла
        return form_class
    
    def dishes_count_formatter(self, context, model, name):
        return len(model.dishes)
    
    column_formatters = {
        'dishes_count': dishes_count_formatter
    }

class DishAdminView(SecureModelView):
    """Админка для блюд"""
    column_list = ['id', 'name', 'category', 'price', 'is_available', 'image']
    column_searchable_list = ['name', 'description']
    column_filters = ['is_available', 'category.name', 'price']
    column_sortable_list = ['name', 'price']
    form_columns = ['name', 'description', 'price', 'category', 'image', 'is_available']
    column_labels = {
        'name': 'Название',
        'description': 'Описание',
        'price': 'Цена',
        'category': 'Категория',
        'image': 'Изображение',
        'is_available': 'Доступно'
    }
    
    def scaffold_form(self):
        form_class = super().scaffold_form()
        form_class.description = TextAreaField('Описание')
        return form_class
    
    def on_model_change(self, form, model, is_created):
        # Очистка описания от лишних пробелов
        if model.description:
            model.description = model.description.strip()
        # Округление цены до 2 знаков
        model.price = round(model.price, 2)

class OrderAdminView(SecureModelView):
    """Админка для заказов"""
    column_list = ['id', 'customer_name', 'address', 'phone', 'total', 'status', 'created_at', 'user']
    column_searchable_list = ['customer_name', 'address', 'phone']
    column_filters = ['status', 'created_at']
    column_sortable_list = ['id', 'total', 'created_at']
    form_columns = ['customer_name', 'address', 'phone', 'total', 'status', 'user']
    can_create = False  # Заказы создаются только через сайт
    column_labels = {
        'customer_name': 'Имя клиента',
        'address': 'Адрес',
        'phone': 'Телефон',
        'total': 'Сумма',
        'status': 'Статус',
        'created_at': 'Дата создания',
        'user': 'Пользователь'
    }
    
    form_choices = {
        'status': [
            ('Новый', 'Новый'),
            ('В обработке', 'В обработке'),
            ('Готовится', 'Готовится'),
            ('В пути', 'В пути'),
            ('Доставлен', 'Доставлен'),
            ('Отменен', 'Отменен')
        ]
    }

class CustomAdminIndexView(AdminIndexView):
    """Кастомная главная страница админ-панели Flask-Admin"""
    @expose('/')
    def index(self):
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('auth.login', next=request.url))
        
        # Статистика для админ-панели
        stats = {
            'users_count': User.query.count(),
            'orders_count': Order.query.count(),
            'dishes_count': Dish.query.count(),
            'categories_count': Category.query.count(),
            'today_orders': Order.query.filter(
                db.func.date(Order.created_at) == db.func.current_date()
            ).count()
        }
        
        # Последние 5 заказов
        latest_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
        
        return self.render('admin/index.html', stats=stats, orders=latest_orders)
    
    @expose('/parse-nsm-page')
    def parse_nsm_page(self):
        """Страница парсинга (альтернатива Blueprint)"""
        if not current_user.is_authenticated or not current_user.is_admin:
            return redirect(url_for('auth.login', next=request.url))
        
        return render_template('admin/parse_nsm.html')

# Инициализация Flask-Admin
flask_admin = Admin(name='Food Delivery Admin', 
                   template_mode='bootstrap4',
                   index_view=CustomAdminIndexView(),
                   base_template='admin/master.html',
                   url='/admin-panel')  # Разный URL чтобы не конфликтовать с Blueprint

def init_admin_panel(app):
    """Инициализация админ-панели Flask-Admin"""
    flask_admin.init_app(app)
    
    # Добавляем представления моделей
    flask_admin.add_view(UserAdminView(User, db.session, name='Пользователи', category='Основные'))
    flask_admin.add_view(CategoryAdminView(Category, db.session, name='Категории', category='Основные'))
    flask_admin.add_view(DishAdminView(Dish, db.session, name='Блюда', category='Основные'))
    flask_admin.add_view(OrderAdminView(Order, db.session, name='Заказы', category='Основные'))
    
    # Отключаем некоторые вьюшки или добавляем в категорию "Дополнительно"
    flask_admin.add_view(SecureModelView(OrderItem, db.session, name='Позиции заказа', category='Дополнительно'))
    flask_admin.add_view(SecureModelView(Favorite, db.session, name='Избранное', category='Дополнительно'))

# ============================================================================
# 3. Функция для подключения всего админ-функционала
# ============================================================================

def init_admin(app):
    """Инициализация всего админ-функционала"""
    # 1. Регистрируем Blueprint для парсинга (доступно по /admin/parse-nsm)
    app.register_blueprint(admin_bp)
    
    # 2. Инициализируем Flask-Admin панель (доступно по /admin-panel)
    init_admin_panel(app)
