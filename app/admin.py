from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm
from flask_login import login_required, current_user
from wtforms import PasswordField, TextAreaField, FloatField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange
from . import db
from .models import User, Category, Dish, Order, OrderItem, Favorite, ImageQueue
from .parsers.nsm_parser import NSMParser
import logging
from datetime import date, datetime, timedelta

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

@admin_parsing_bp.route('/process-image-queue', methods=['POST'])
@login_required
def process_image_queue():
    """Обработка очереди изображений"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    from .parsers.nsm_parser import process_image_queue, get_queue_stats
    
    limit = request.form.get('limit', 5, type=int)
    cleanup = request.form.get('cleanup', 'true') == 'true'
    
    try:
        # Сначала показываем статистику до обработки
        stats_before = get_queue_stats()
        
        # Обрабатываем очередь
        result = process_image_queue(limit=limit, cleanup=cleanup)
        
        # Получаем статистику после обработки
        stats_after = get_queue_stats()
        
        flash(
            f'✅ Обработано {result["total"]} задач: {result["downloaded"]} загружено, '
            f'{result["failed"]} ошибок, {result["skipped"]} пропущено. '
            f'В очереди осталось: {stats_after.get("pending", 0)}',
            'success'
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки очереди изображений: {e}")
        flash(f'Ошибка при обработке очереди: {e}', 'danger')
    
    return redirect(url_for('admin_parsing.parse_nsm'))

@admin_parsing_bp.route('/clear-image-queue', methods=['POST'])
@login_required
def clear_image_queue():
    """Очистка очереди изображений"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    from .parsers.nsm_parser import clear_image_queue
    
    try:
        deleted = clear_image_queue()
        flash(f'✅ Очередь изображений очищена: удалено {deleted} задач', 'success')
    except Exception as e:
        logger.error(f"Ошибка очистки очереди: {e}")
        flash(f'Ошибка при очистке очереди: {e}', 'danger')
    
    return redirect(url_for('admin_parsing.parse_nsm'))

@admin_parsing_bp.route('/queue-stats')
@login_required
def queue_stats():
    """Статистика очереди изображений"""
    if not current_user.is_admin:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    from .parsers.nsm_parser import get_queue_stats
    
    try:
        stats = get_queue_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Ошибка получения статистики очереди: {e}")
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
# 2. FLASK-ADMIN панель управления (остается как есть, только добавляем ImageQueueAdminView)
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

class ImageQueueAdminView(SecureModelView):
    """Админка для очереди изображений"""
    column_list = ['id', 'dish', 'image_url_short', 'status', 'priority', 'retry_count', 'created_at', 'updated_at']
    column_searchable_list = ['image_url', 'status']
    column_filters = ['status', 'priority', 'dish']
    column_sortable_list = ['id', 'priority', 'created_at', 'updated_at']
    column_default_sort = ('priority', True)
    
    form_columns = ['dish', 'image_url', 'status', 'priority', 'retry_count']
    
    column_labels = {
        'id': 'ID',
        'dish': 'Блюдо',
        'image_url_short': 'URL изображения',
        'status': 'Статус',
        'priority': 'Приоритет',
        'retry_count': 'Попыток',
        'created_at': 'Создано',
        'updated_at': 'Обновлено'
    }
    
    column_formatters = {
        'image_url_short': lambda v, c, m, p: m.image_url[:50] + '...' if len(m.image_url) > 50 else m.image_url,
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d.%m.%Y %H:%M'),
        'updated_at': lambda v, c, m, p: m.updated_at.strftime('%d.%m.%Y %H:%M'),
        'dish': lambda v, c, m, p: m.dish.name if m.dish else 'N/A'
    }
    
    def on_model_delete(self, model):
        # При удалении из админки логируем
        logger.info(f"Удалена задача очереди: {model.id} (блюдо: {model.dish_id})")

class UserAdminView(SecureModelView):
    """Админка для пользователей"""
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
        pass

class DishAdminView(SecureModelView):
    """Админка для блюд"""
    column_list = ['id', 'name', 'category', 'price', 'is_available', 'image']
    column_searchable_list = ['name', 'description']
    column_filters = ['is_available', 'category', 'price']
    column_sortable_list = ['id', 'name', 'price']
    column_default_sort = ('id', True)
    
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
        if model.description:
            model.description = model.description.strip()
        model.price = round(model.price, 2)
        
        if not model.image:
            model.image = 'default.jpg'

class OrderAdminView(SecureModelView):
    """Админка для заказов"""
    column_list = ['id', 'customer_name', 'address', 'phone', 'total', 'status', 'created_at', 'customer']
    column_searchable_list = ['customer_name', 'address', 'phone']
    column_filters = ['status', 'created_at', 'total']
    column_sortable_list = ['id', 'total', 'created_at']
    column_default_sort = ('created_at', True)
    
    form_columns = ['customer_name', 'address', 'phone', 'total', 'status', 'customer']
    can_create = False
    
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
        'customer': 'Пользователь'
    }
    
    column_formatters = {
        'created_at': lambda v, c, m, p: m.created_at.strftime('%d.%m.%Y %H:%M'),
        'total': lambda v, c, m, p: f"{m.total} ₽",
        'customer': lambda v, c, m, p: m.customer.username if m.customer else 'Гость'
    }

class OrderItemAdminView(SecureModelView):
    """Админка для позиций заказа"""
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
        order = model.order
        if order:
            total = sum(item.quantity * item.price for item in order.items)
            order.total = total
            db.session.commit()

class FavoriteAdminView(SecureModelView):
    """Админка для избранного"""
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
        from .models import User, Order, Dish, Category, ImageQueue
        
        users_count = User.query.count()
        orders_count = Order.query.count()
        dishes_count = Dish.query.count()
        categories_count = Category.query.count()
        
        # Статистика очереди изображений
        queue_total = ImageQueue.query.count()
        queue_pending = ImageQueue.query.filter_by(status='pending').count()
        queue_failed = ImageQueue.query.filter_by(status='failed').count()
        
        today = datetime.now().date()
        today_orders = Order.query.filter(
            db.func.date(Order.created_at) == today
        ).count()
        
        # Заказы за последнюю неделю
        week_ago = datetime.now().date() - timedelta(days=7)
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
            'queue_total': queue_total,
            'queue_pending': queue_pending,
            'queue_failed': queue_failed,
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
    
    # Добавляем представления моделей
    flask_admin.add_view(UserAdminView(User, db.session, name='Пользователи', category='Основные', endpoint='user'))
    flask_admin.add_view(CategoryAdminView(Category, db.session, name='Категории', category='Основные', endpoint='category'))
    flask_admin.add_view(DishAdminView(Dish, db.session, name='Блюда', category='Основные', endpoint='dish'))
    flask_admin.add_view(OrderAdminView(Order, db.session, name='Заказы', category='Основные', endpoint='order'))
    flask_admin.add_view(ImageQueueAdminView(ImageQueue, db.session, name='Очередь изображений', category='Дополнительно', endpoint='imagequeue'))
    
    # Дополнительные модели
    flask_admin.add_view(OrderItemAdminView(OrderItem, db.session, name='Позиции заказа', category='Дополнительно', endpoint='orderitem'))
    flask_admin.add_view(FavoriteAdminView(Favorite, db.session, name='Избранное', category='Дополнительно', endpoint='favorite'))
    
    # Создаем кастомные страницы статистики
    @app.route('/admin/user-stats')
    @login_required
    def user_stats():
        if not current_user.is_admin:
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('main.index'))
        
        from .models import User
        
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        admin_users = User.query.filter_by(is_admin=True).count()
        
        week_ago = datetime.now() - timedelta(days=7)
        new_users = User.query.filter(User.created_at >= week_ago).count()
        
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
        
        total_orders = Order.query.count()
        total_revenue = db.session.query(db.func.sum(Order.total)).scalar() or 0
        
        status_stats = db.session.query(
            Order.status,
            db.func.count(Order.id).label('count'),
            db.func.sum(Order.total).label('revenue')
        ).group_by(Order.status).all()
        
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