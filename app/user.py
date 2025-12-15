from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Order, Favorite, Dish, User
from .forms import UpdateProfileForm
from sqlalchemy.orm import joinedload

user = Blueprint('user', __name__)

@user.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm()
    
    if form.validate_on_submit():
        # Проверяем, не занято ли имя другим пользователем
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
            return redirect(url_for('user.profile'))
    
    elif request.method == 'GET':
        form.username.data = current_user.username
    
    # Получаем статистику пользователя
    orders_count = Order.query.filter_by(user_id=current_user.id).count()
    favorites_count = Favorite.query.filter_by(user_id=current_user.id).count()
    
    return render_template('user/profile.html', 
                         form=form,
                         orders_count=orders_count,
                         favorites_count=favorites_count)

@user.route('/orders')
@login_required
def orders():
    page = request.args.get('page', 1, type=int)
    orders = Order.query.filter_by(user_id=current_user.id)\
        .order_by(Order.created_at.desc())\
        .paginate(page=page, per_page=10)
    return render_template('user/orders.html', orders=orders)

@user.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.options(joinedload(Order.items).joinedload(OrderItem.dish))\
        .get_or_404(order_id)
    
    if order.user_id != current_user.id and not current_user.is_admin:
        flash('У вас нет доступа к этому заказу.', 'danger')
        return redirect(url_for('user.orders'))
    
    return render_template('user/order_detail.html', order=order)

@user.route('/favorites')
@login_required
def favorites():
    # Получаем избранные блюда пользователя
    favorites = Favorite.query.filter_by(user_id=current_user.id)\
        .join(Dish)\
        .filter(Dish.is_available == True)\
        .order_by(Favorite.added_at.desc())\
        .all()
    
    return render_template('user/favorites.html', favorites=favorites)

@user.route('/remove_favorite/<int:favorite_id>', methods=['POST'])
@login_required
def remove_favorite(favorite_id):
    favorite = Favorite.query.get_or_404(favorite_id)
    
    if favorite.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Доступ запрещен'}), 403
    
    db.session.delete(favorite)
    db.session.commit()
    
    flash('Удалено из избранного', 'success')
    return redirect(url_for('user.favorites'))
