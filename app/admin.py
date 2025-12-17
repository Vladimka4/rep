from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm
from flask_login import login_required, current_user
from wtforms import PasswordField, TextAreaField, FloatField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange
from . import db
from .models import User, Category, Dish, Order, OrderItem, Favorite
from .parsers.nsm_parser import NSMParser
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

# ============================================================================
# 1. BLUEPRINT для парсинга
# ============================================================================

admin_parsing_bp = Blueprint('admin_parsing', __name__, url_prefix='/admin-parsing')

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
    can_view_details = True
    column_display_pk = True
    column_hide_backrefs = False
    column_list = ['id']
    
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        flash('У вас нет прав для доступа к этой странице.', 'danger')
        return redirect(url_for('main.index'))

class UserAdminView(SecureModelView):
    """Админка для пользователей"""
    # Используем 'admin_user' как endpoint для User
    column_list = ['id', 'username', 'is_admin', 'is_active', 'created_at', 'orders']
    column_searchable_list = ['username']
    column_filters = ['is_admin', 'is_active', 'created_at']
    column_sortable_list = ['id', 'username', 'created_at']
    column_default_sort = ('id', True)
    
    form_columns = ['username', 'is_admin', 'is_active']
    
    form_extra_fields = {
        'password': PasswordField('Новый пароль (оставьте пустым, чтобы не менять)')
    }
    
    column_labels = {
        'id': 'ID',
        'username': 'Имя пользователя',
        'is_admin': 'Администратор',
        'is_active': 'Активен',
        'created_at': 'Дата регистрации',
        'orders': 'Количество заказов'
    }
    
    column_formatters = {
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d.%m.%Y %H:%M'),
        'orders': lambda v, c, m, p: len(m.orders) if m.orders else 0
    }
    
    def on_model_change(self, form, model, is_created):
        if form.password.data:
            from . import bcrypt
            model.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

class CategoryAdminView(SecureModelView):
    """Админка для категорий"""
    # Используем 'admin_category' как endpoint для Category
    column_list = ['id', 'name', 'image', 'dishes']
    column_searchable_list = ['name']
    column_filters = ['name']
    column_sortable_list = ['id', 'name']
    column_default_sort = ('id', True)
    
    form_columns = ['name', 'image']
    
    column_labels = {
        'id': 'ID',
        'name': 'Название',
        'image': 'Изображение',
        'dishes': 'Количество блюд'
    }
    
    column_formatters = {
        'dishes': lambda v, c, m, p: len(m.dishes) if m.dishes else 0
    }
    
    def after_model_change(self, form, model, is_created):
        # Обновляем кэш или что-то еще при изменении категории
        pass

class DishAdminView(SecureModelView):
    """Админка для блюд"""
    # Используем 'admin_dish' как endpoint для Dish
    column_list = ['id', 'name', 'category', 'price', 'is_available', 'image']
    column_searchable_list = ['name', 'description']
    column_filters = ['is_available', 'category', 'price']
    column_sortable_list = ['id', 'name', 'price']
    column_default_sort = ('id', True)
    
    # Создаем кастомное поле для выбора категории
    form_columns = ['name', 'description', 'price', 'category', 'is_available', 'image']
    
    column_labels = {
        'id': 'ID',
        'name': 'Название',
        'description': 'Описание',
        'price': 'Цена',
        'category': 'Категория',
        'is_available': 'Доступно',
        'image': 'Изображение'
    }
    
    form_extra_fields = {
        'price': FloatField('Цена', validators=[DataRequired(), NumberRange(min=0)]),
        'description': TextAreaField('Описание', validators=[Length(max=500)])
    }
    
    def on_model_change(self, form, model, is_created):
        # Очистка описания от лишних пробелов
        if model.description:
            model.description = model.description.strip()
        # Округление цены до 2 знаков
        model.price = round(model.price, 2)
        
        # Если изображение пустое, ставим placeholder
        if not model.image:
            model.image = 'default.jpg'

class OrderAdminView(SecureModelView):
    """Админка для заказов"""
    # Используем 'admin_order' как endpoint для Order
    column_list = ['id', 'customer_name', 'address', 'phone', 'total', 'status', 'created_at', 'user']
    column_searchable_list = ['customer_name', 'address', 'phone']
    column_filters = ['status', 'created_at', 'total']
    column_sortable_list = ['id', 'total', 'created_at']
    column_default_sort = ('created_at', True)
    
    form_columns = ['customer_name', 'address', 'phone', 'total', 'status', 'user']
    can_create = False  # Заказы создаются только через сайт
    
    # Добавляем возможность изменения статуса
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
    
    column_labels = {
        'id': 'ID заказа',
        'customer_name': 'Имя клиента',
        'address': 'Адрес',
        'phone': 'Телефон',
        'total': 'Сумма',
        'status': 'Статус',
        'created_at': 'Дата создания',
        'user': 'Пользователь'
    }
    
    column_formatters = {
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d.%m.%Y %H:%M'),
        'total': lambda v, c, m, p: f"{m.total} ₽",
        'user': lambda v, c, m, p: m.user.username if m.user else 'Гость'
    }
    
    def on_model_change(self, form, model, is_created):
        # Если заказ доставлен или отменен, нельзя менять статус на другие
        if model.status in ['Доставлен', 'Отменен']:
            # Можно добавить логику блокировки изменения
            pass

class OrderItemAdminView(SecureModelView):
    """Админка для позиций заказа"""
    # Используем 'admin_orderitem' как endpoint для OrderItem
    column_list = ['id', 'order', 'dish', 'quantity', 'price', 'total']
    column_filters = ['order', 'dish']
    column_sortable_list = ['id', 'quantity', 'price']
    
    form_columns = ['order', 'dish', 'quantity', 'price']
    
    column_labels = {
        'id': 'ID',
        'order': 'Заказ',
        'dish': 'Блюдо',
        'quantity': 'Количество',
        'price': 'Цена за шт.',
        'total': 'Сумма'
    }
    
    column_formatters = {
        'total': lambda v, c, m, p: f"{m.quantity * m.price} ₽",
        'price': lambda v, c, m, p: f"{m.price} ₽"
    }
    
    def on_model_change(self, form, model, is_created):
        # Автоматически обновляем общую сумму заказа
        order = model.order
        if order:
            # Пересчитываем общую сумму заказа
            total = sum(item.quantity * item.price for item in order.items)
            order.total = total
            db.session.commit()

class FavoriteAdminView(SecureModelView):
    """Админка для избранного"""
    # Используем 'admin_favorite' как endpoint для Favorite
    column_list = ['id', 'user', 'dish', 'added_at']
    column_filters = ['user', 'dish', 'added_at']
    column_sortable_list = ['id', 'added_at']
    
    form_columns = ['user', 'dish']
    
    column_labels = {
        'id': 'ID',
        'user': 'Пользователь',
        'dish': 'Блюдо',
        'added_at': 'Дата добавления'
    }
    
    column_formatters = {
        'added_at': lambda v, c, m, p: m.added_at.strftime('%d.%m.%Y %H:%M')
    }

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    
    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next='/admin'))
        flash('У вас нет прав для доступа к этой странице.', 'danger')
        return redirect(url_for('main.index'))
    
    @expose('/')
    def index(self):
        from .models import User, Order, Dish, Category
        from datetime import datetime
        
        users_count = User.query.count()
        orders_count = Order.query.count()
        dishes_count = Dish.query.count()
        categories_count = Category.query.count()
        
        today = datetime.now().date()
        today_orders = Order.query.filter(
            db.func.date(Order.created_at) == today
        ).count()
        
        # Заказы за последнюю неделю
        week_ago = datetime.now().date() - datetime.timedelta(days=7)
        recent_orders = Order.query.filter(
            Order.created_at >= week_ago
        ).count()
        
        # Общая выручка
        total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
        
        # Получаем последние заказы
        orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
        
        # Получаем популярные блюда
        from sqlalchemy import func
        popular_dishes = db.session.query(
            Dish.name,
            db.func.count(OrderItem.dish_id).label('count')
        ).join(OrderItem).group_by(Dish.id).order_by(db.func.count(OrderItem.dish_id).desc()).limit(5).all()
        
        stats = {
            'users_count': users_count,
            'orders_count': orders_count,
            'dishes_count': dishes_count,
            'categories_count': categories_count,
            'today_orders': today_orders,
            'recent_orders': recent_orders,
            'total_revenue': total_revenue,
            'popular_dishes': popular_dishes
        }
        
        return self.render('admin/index.html', stats=stats, orders=orders)

# Инициализация Flask-Admin
flask_admin = Admin(name='Food Delivery Admin', 
                   template_mode='bootstrap4',
                   url='/admin',
                   index_view=MyAdminIndexView())

def init_admin(app):
    """Инициализация админ-панели"""
    flask_admin.init_app(app)
    
    # Добавляем представления моделей с явными endpoint
    flask_admin.add_view(UserAdminView(User, db.session, name='Пользователи', category='Основные', endpoint='user'))
    flask_admin.add_view(CategoryAdminView(Category, db.session, name='Категории', category='Основные', endpoint='category'))
    flask_admin.add_view(DishAdminView(Dish, db.session, name='Блюда', category='Основные', endpoint='dish'))
    flask_admin.add_view(OrderAdminView(Order, db.session, name='Заказы', category='Основные', endpoint='order'))
    
    # Дополнительные модели
    flask_admin.add_view(OrderItemAdminView(OrderItem, db.session, name='Позиции заказа', category='Дополнительно', endpoint='orderitem'))
    flask_admin.add_view(FavoriteAdminView(Favorite, db.session, name='Избранное', category='Дополнительно', endpoint='favorite'))
    
    # Создаем кастомные страницы
    @app.route('/admin/user-stats')
    @login_required
    def user_stats():
        if not current_user.is_admin:
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('main.index'))
        
        from .models import User
        from datetime import datetime, timedelta
        
        # Статистика по пользователям
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        admin_users = User.query.filter_by(is_admin=True).count()
        
        # Новые пользователи за последние 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        new_users = User.query.filter(User.created_at >= week_ago).count()
        
        # Пользователи по дате регистрации
        users_by_date = db.session.query(
            db.func.date(User.created_at).label('date'),
            db.func.count(User.id).label('count')
        ).group_by(db.func.date(User.created_at)).order_by(db.func.date(User.created_at).desc()).limit(30).all()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'admin_users': admin_users,
            'new_users': new_users,
            'users_by_date': users_by_date
        }
        
        return render_template('admin/user_stats.html', stats=stats)
    
    @app.route('/admin/order-stats')
    @login_required
    def order_stats():
        if not current_user.is_admin:
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('main.index'))
        
        from .models import Order
        from datetime import datetime, timedelta
        
        # Общая статистика
        total_orders = Order.query.count()
        total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
        
        # Статистика по статусам
        status_stats = db.session.query(
            Order.status,
            db.func.count(Order.id).label('count'),
            db.func.sum(Order.total).label('revenue')
        ).group_by(Order.status).all()
        
        # Статистика по дням
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        orders_today = Order.query.filter(db.func.date(Order.created_at) == today).count()
        orders_week = Order.query.filter(db.func.date(Order.created_at) >= week_ago).count()
        orders_month = Order.query.filter(db.func.date(Order.created_at) >= month_ago).count()
        
        revenue_today = db.session.query(db.func.sum(Order.total)).filter(
            db.func.date(Order.created_at) == today
        ).scalar() or 0
        
        revenue_week = db.session.query(db.func.sum(Order.total)).filter(
            db.func.date(Order.created_at) >= week_ago
        ).scalar() or 0
        
        revenue_month = db.session.query(db.func.sum(Order.total)).filter(
            db.func.date(Order.created_at) >= month_ago
        ).scalar() or 0
        
        # Заказы по дням
        orders_by_date = db.session.query(
            db.func.date(Order.created_at).label('date'),
            db.func.count(Order.id).label('count'),
            db.func.sum(Order.total).label('revenue')
        ).group_by(db.func.date(Order.created_at)).order_by(db.func.date(Order.created_at).desc()).limit(30).all()
        
        stats = {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'status_stats': status_stats,
            'orders_today': orders_today,
            'orders_week': orders_week,
            'orders_month': orders_month,
            'revenue_today': revenue_today,
            'revenue_week': revenue_week,
            'revenue_month': revenue_month,
            'orders_by_date': orders_by_date
        }
        
        return render_template('admin/order_stats.html', stats=stats)
