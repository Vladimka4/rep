from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from . import db  # Относительный импорт
from .models import Order
from .forms import UpdateProfileForm

user = Blueprint('user', __name__)

@user.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm()
    
    if form.validate_on_submit():
        current_user.username = form.username.data
        db.session.commit()
        flash('Ваш профиль успешно обновлен!', 'success')
        return redirect(url_for('user.profile'))
    
    form.username.data = current_user.username
    return render_template('user/profile.html', form=form)

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
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id and not current_user.is_admin:
        flash('У вас нет доступа к этому заказу.', 'danger')
        return redirect(url_for('user.orders'))
    

    return render_template('user/order_detail.html', order=order)
