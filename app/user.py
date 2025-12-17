from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Order, Favorite, Dish, User, OrderItem
from .forms import UpdateProfileForm
from sqlalchemy.orm import joinedload
import logging

logger = logging.getLogger(__name__)


user_bp = Blueprint('user_bp', __name__)  

@user_bp.route('/profile', methods=['GET', 'POST'])  
@login_required
def profile():
    try:
        form = UpdateProfileForm()
        
        if form.validate_on_submit():
            existing_user = User.query.filter(
                User.username == form.username.data,
                User.id != current_user.id
            ).first()
            
            if existing_user:
                flash('Это имя пользователя уже занято', 'danger')
            else:
                current_user.username = form.username.data
                db.session.commit()
                flash('Ваш профиль успешно обновлен!', 'success')
                return redirect(url_for('user_bp.profile'))  
        
        elif request.method == 'GET':
            form.username.data = current_user.username
        
        orders_count = Order.query.filter_by(user_id=current_user.id).count()
        favorites_count = Favorite.query.filter_by(user_id=current_user.id).count()
        
        return render_template('user/profile.html', 
                             form=form,
                             orders_count=orders_count,
                             favorites_count=favorites_count)
    except Exception as e:
        logger.error(f"Ошибка в профиле пользователя {current_user.id}: {str(e)}")
        flash('Ошибка загрузки профиля', 'danger')
        return redirect(url_for('main.index'))

@user_bp.route('/orders')  
@login_required
def orders():
    try:
        page = request.args.get('page', 1, type=int)
        orders = Order.query.filter_by(user_id=current_user.id)\
            .order_by(Order.created_at.desc())\
            .paginate(page=page, per_page=10)
        return render_template('user/orders.html', orders=orders)
    except Exception as e:
        logger.error(f"Ошибка загрузки заказов пользователя {current_user.id}: {str(e)}")
        flash('Ошибка загрузки заказов', 'danger')
        return redirect(url_for('user_bp.profile')) 

@user_bp.route('/order/<int:order_id>')  
@login_required
def order_detail(order_id):
    try:
        order = Order.query.options(
            joinedload(Order.items).joinedload(OrderItem.dish)
        ).get_or_404(order_id)
        
        if order.user_id != current_user.id and not current_user.is_admin:
            flash('У вас нет доступа к этому заказу.', 'danger')
            return redirect(url_for('user_bp.orders'))  
        
        return render_template('user/order_detail.html', order=order)
    except Exception as e:
        logger.error(f"Ошибка загрузки заказа {order_id}: {str(e)}")
        flash('Ошибка загрузки деталей заказа', 'danger')
        return redirect(url_for('user_bp.orders')) 

@user_bp.route('/favorites')
@login_required
def favorites():
    try:
        favorites = Favorite.query.filter_by(user_id=current_user.id)\
            .join(Dish)\
            .filter(Dish.is_available == True)\
            .order_by(Favorite.added_at.desc())\
            .all()
        
        return render_template('user/favorites.html', favorites=favorites)
    except Exception as e:
        logger.error(f"Ошибка загрузки избранного пользователя {current_user.id}: {str(e)}")
        flash('Ошибка загрузки избранного', 'danger')
        return redirect(url_for('main.index'))

@user_bp.route('/remove_favorite/<int:favorite_id>', methods=['POST']) 
@login_required
def remove_favorite(favorite_id):
    try:
        favorite = Favorite.query.get_or_404(favorite_id)
        
        if favorite.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
        
        db.session.delete(favorite)
        db.session.commit()
        
        flash('Удалено из избранного', 'success')
        return redirect(url_for('user_bp.favorites')) 
    except Exception as e:
        logger.error(f"Ошибка удаления избранного {favorite_id}: {str(e)}")
        flash('Ошибка удаления из избранного', 'danger')
        return redirect(url_for('user_bp.favorites'))  
