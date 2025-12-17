from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm
from flask_login import login_required, current_user
from wtforms import PasswordField
from . import db
from .models import User, Category, Dish, Order, OrderItem, Favorite
from .parsers.nsm_parser import NSMParser
import logging
from datetime import date

logger = logging.getLogger(__name__)

# ============================================================================
# 1. BLUEPRINT для парсинга
# ============================================================================

# Изменяем имя Blueprint, чтобы избежать конфликта с Flask-Admin
admin_parsing_bp = Blueprint('admin_parsing', __name__, url_prefix='/admin')

@admin_parsing_bp.route('/parse-nsm', methods=['GET'])
@login_required
def parse_nsm():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('admin/parse_nsm.html')

@admin_parsing_bp.route('/parse-nsm-action', methods=['POST'])
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
    
    return redirect(url_for('admin_parsing.parse_nsm'))

@admin_parsing_bp.route('/download-images', methods=['POST'])
@login_required
def download_images():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    from .parsers.nsm_parser import download_nsm_images
    
    limit = request.form.get('limit', 5, type=int)
    
    try:
        success = download_nsm_images(limit=limit)
        if success:
            flash(f'Изображения успешно загружены (максимум {limit})', 'success')
        else:
            flash('Не удалось загрузить изображения', 'warning')
    except Exception as e:
        logger.error(f"Ошибка загрузки изображений: {e}")
        flash(f'Ошибка при загрузке изображений: {e}', 'danger')
    
    return redirect(url_for('admin_parsing.parse_nsm'))

@admin_parsing_bp.route('/image-stats')
@login_required
def image_stats():
    """Статистика по изображениям"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    from .models import Category, Dish
    
    try:
        # Статистика по блюдам
        total_dishes = Dish.query.count()
        dishes_with_images = Dish.query.filter(
            Dish.image.isnot(None),
            Dish.image != ''
        ).count()
        
        # Статистика по категориям
        total_categories = Category.query.count()
        categories_with_images = Category.query.filter(
            Category.image.isnot(None),
            Category.image != ''
        ).count()
        
        stats = {
            'total_dishes': total_dishes,
            'dishes_with_images': dishes_with_images,
            'total_categories': total_categories,
            'categories_with_images': categories_with_images,
            'dish_image_percentage': round((dishes_with_images / total_dishes * 100) if total_dishes > 0 else 0, 1),
            'category_image_percentage': round((categories_with_images / total_categories * 100) if total_categories > 0 else 0, 1)
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return jsonify({'error': str(e)}), 500

@admin_parsing_bp.route('/update-category-images', methods=['POST'])
@login_required
def update_category_images():
    """Обновление изображений категорий из блюд"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    try:
        from .parsers.nsm_parser import update_all_category_images
        
        logger.info("Начинаю обновление изображений категорий...")
        updated = update_all_category_images()
        
        if updated > 0:
            flash(f'✅ Обновлено {updated} изображений категорий', 'success')
        else:
            flash('⚠️ Не удалось обновить изображения категорий или нечего обновлять', 'warning')
            
    except Exception as e:
        logger.error(f"Ошибка обновления изображений категорий: {e}")
        flash(f'❌ Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('admin_parsing.parse_nsm'))

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
    column_list = ['id', 'username', 'is_admin', 'is_active', 'created_at']
    column_searchable_list = ['username']
    column_filters = ['is_admin', 'is_active', 'created_at']
    column_sortable_list = ['id', 'username', 'created_at']
    
    # УДАЛЕНО: 'password' из form_columns
    form_columns = ['username', 'is_admin', 'is_active']
    
    # ДОБАВЛЕНО: кастомное поле для пароля
    form_extra_fields = {
        'password': PasswordField('Новый пароль (оставьте пустым, чтобы не менять)')
    }
    
    column_labels = {
        'username': 'Имя пользователя',
        'is_admin': 'Администратор',
        'is_active': 'Активен',
        'created_at': 'Дата регистрации'
    }
    
    def on_model_change(self, form, model, is_created):
        # Если введен новый пароль, хешируем его
        if form.password.data:
            from . import bcrypt
            model.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

class CategoryAdminView(SecureModelView):
    """Админка для категорий"""
    column_list = ['id', 'name', 'image']
    column_searchable_list = ['name']
    form_columns = ['name', 'image']
    column_labels = {
        'name': 'Название',
        'image': 'Изображение'
    }

class DishAdminView(SecureModelView):
    """Админка для блюд"""
    # Используем 'category_id' вместо 'category' для избежания конфликта
    column_list = ['id', 'name', 'category_id', 'price', 'is_available']
    column_searchable_list = ['name', 'description']
    column_filters = ['is_available', 'category_id', 'price']
    column_sortable_list = ['name', 'price']
    form_columns = ['name', 'description', 'price', 'category_id', 'is_available']
    column_labels = {
        'name': 'Название',
        'description': 'Описание',
        'price': 'Цена',
        'category_id': 'Категория',
        'is_available': 'Доступно'
    }
    
    def on_model_change(self, form, model, is_created):
        # Очистка описания от лишних пробелов
        if model.description:
            model.description = model.description.strip()
        # Округление цены до 2 знаков
        model.price = round(model.price, 2)

class OrderAdminView(SecureModelView):
    """Админка для заказов"""
    column_list = ['id', 'customer_name', 'address', 'phone', 'total', 'status', 'created_at']
    column_searchable_list = ['customer_name', 'address', 'phone']
    column_filters = ['status', 'created_at']
    column_sortable_list = ['id', 'total', 'created_at']
    form_columns = ['customer_name', 'address', 'phone', 'total', 'status']
    can_create = False  # Заказы создаются только через сайт
    column_labels = {
        'customer_name': 'Имя клиента',
        'address': 'Адрес',
        'phone': 'Телефон',
        'total': 'Сумма',
        'status': 'Статус',
        'created_at': 'Дата создания'
    }

class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        from .models import User, Order, Dish, Category
        from datetime import datetime
        
        # Получаем статистику
        users_count = User.query.count()
        orders_count = Order.query.count()
        dishes_count = Dish.query.count()
        
        # Заказы за сегодня
        today = datetime.now().date()
        today_orders = Order.query.filter(
            db.func.date(Order.created_at) == today
        ).count()
        
        # Получаем последние заказы
        orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        
        stats = {
            'users_count': users_count,
            'orders_count': orders_count,
            'dishes_count': dishes_count,
            'today_orders': today_orders
        }
        
        return self.render('admin/index.html', stats=stats, orders=orders)

# Инициализация Flask-Admin
flask_admin = Admin(name='Food Delivery Admin', 
                   template_mode='bootstrap4',
                   url='/admin-panel',
                   index_view=MyAdminIndexView())

def init_admin(app):
    """Инициализация админ-панели"""
    # Инициализируем Flask-Admin
    flask_admin.init_app(app)
    
    # Добавляем представления моделей
    flask_admin.add_view(UserAdminView(User, db.session, name='Пользователи', category='Основные'))
    flask_admin.add_view(CategoryAdminView(Category, db.session, name='Категории', category='Основные'))
    flask_admin.add_view(DishAdminView(Dish, db.session, name='Блюда', category='Основные'))
    flask_admin.add_view(OrderAdminView(Order, db.session, name='Заказы', category='Основные'))
    
    # Отключаем некоторые вьюшки или добавляем в категорию "Дополнительно"
    flask_admin.add_view(SecureModelView(OrderItem, db.session, name='Позиции заказа', category='Дополнительно'))
    flask_admin.add_view(SecureModelView(Favorite, db.session, name='Избранное', category='Дополнительно'))
