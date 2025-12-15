from flask import Blueprint, render_template, request, flash, session, redirect, url_for, jsonify
from flask_login import current_user, login_required  # Добавили login_required
from . import db
from .models import Category, Dish, Order, OrderItem, Favorite  # Добавили Favorite
import json

main = Blueprint('main', __name__)

@main.route('/')
def index():
    categories = Category.query.all()
    return render_template('index.html', categories=categories)

@main.route('/menu/<int:category_id>')
def menu(category_id):
    category = Category.query.get_or_404(category_id)
    dishes = Dish.query.filter_by(category_id=category_id, is_available=True).all()
    
    # Получаем избранные блюда пользователя
    favorite_ids = []
    if current_user.is_authenticated:
        favorites = Favorite.query.filter_by(user_id=current_user.id).all()
        favorite_ids = [f.dish_id for f in favorites]
    
    return render_template('menu.html', 
                         category=category, 
                         dishes=dishes,
                         favorite_ids=favorite_ids)

@main.route('/cart')
def cart():
    cart = session.get('cart', {})
    cart_items = []
    total_price = 0
    total_items = 0
    
    for dish_id, item in cart.items():
        dish = Dish.query.get(dish_id)
        if dish:
            cart_items.append({
                'id': dish_id,
                'name': dish.name,
                'price': dish.price,
                'quantity': item['quantity'],
                'image': dish.image or 'default.jpg',
                'subtotal': dish.price * item['quantity']
            })
            total_price += dish.price * item['quantity']
            total_items += item['quantity']
    
    return render_template('cart.html', 
                         cart_items=cart_items,
                         total_price=total_price,
                         total_items=total_items)

@main.route('/add_to_cart/<int:dish_id>', methods=['POST'])
def add_to_cart(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    cart = session.get('cart', {})
    
    if not dish.is_available:
        return jsonify({'success': False, 'message': 'Товар недоступен'})
    
    dish_id_str = str(dish_id)
    if dish_id_str in cart:
        cart[dish_id_str]['quantity'] += 1
    else:
        cart[dish_id_str] = {
            'name': dish.name,
            'price': float(dish.price),
            'quantity': 1
        }
    
    session['cart'] = cart
    session.modified = True
    
    # Подсчитываем общее количество
    total_items = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'success': True,
        'cart_total': total_items,
        'message': f'{dish.name} добавлен в корзину'
    })

@main.route('/update_cart/<int:dish_id>', methods=['POST'])
def update_cart(dish_id):
    data = request.get_json()
    quantity = data.get('quantity', 1)
    
    cart = session.get('cart', {})
    
    if str(dish_id) in cart:
        if quantity <= 0:
            del cart[str(dish_id)]
        else:
            cart[str(dish_id)]['quantity'] = quantity
    
    session['cart'] = cart
    session.modified = True
    return jsonify({'success': True})

@main.route('/remove_from_cart/<int:dish_id>', methods=['POST'])
def remove_from_cart(dish_id):
    cart = session.get('cart', {})
    
    if str(dish_id) in cart:
        del cart[str(dish_id)]
        session['cart'] = cart
        session.modified = True
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 404

@main.route('/add_to_favorites/<int:dish_id>', methods=['POST'])
@login_required
def add_to_favorites(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    
    # Проверяем, есть ли уже в избранном
    favorite = Favorite.query.filter_by(
        user_id=current_user.id, 
        dish_id=dish_id
    ).first()
    
    if favorite:
        # Удаляем из избранного
        db.session.delete(favorite)
        action = 'removed'
        message = 'Удалено из избранного'
    else:
        # Добавляем в избранное
        favorite = Favorite(user_id=current_user.id, dish_id=dish_id)
        db.session.add(favorite)
        action = 'added'
        message = 'Добавлено в избранное'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'action': action,
        'message': message
    })

@main.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = session.get('cart', {})
    
    if not cart:
        flash('Корзина пуста', 'error')
        return redirect(url_for('main.cart'))
    
    if request.method == 'POST':
        # Считаем итог
        total = sum(
            Dish.query.get(int(dish_id)).price * item['quantity'] 
            for dish_id, item in cart.items()
            if Dish.query.get(int(dish_id))
        )
        
        # Создаём заказ
        order = Order(
            user_id=current_user.id,
            customer_name=current_user.username,
            address=request.form['address'],
            phone=request.form.get('phone', ''),
            total=total
        )
        
        db.session.add(order)
        db.session.commit()
        
        # Добавляем товары в заказ
        for dish_id, item in cart.items():
            dish = Dish.query.get(int(dish_id))
            if dish:
                order_item = OrderItem(
                    order_id=order.id,
                    dish_id=int(dish_id),
                    quantity=item['quantity'],
                    price=dish.price
                )
                db.session.add(order_item)
        
        db.session.commit()
        
        # Очищаем корзину
        session.pop('cart', None)
        
        flash(f'Заказ #{order.id} успешно оформлен!', 'success')
        return redirect(url_for('user.orders'))
    
    # Подсчёт для показа в форме
    cart_items = []
    total_price = 0
    total_items = 0
    
    for dish_id, item in cart.items():
        dish = Dish.query.get(dish_id)
        if dish:
            total_price += dish.price * item['quantity']
            total_items += item['quantity']
            cart_items.append({
                'name': dish.name,
                'quantity': item['quantity'],
                'price': dish.price
            })
    
    return render_template('checkout.html',
                         cart_items=cart_items,
                         total_price=total_price,
                         total_items=total_items)
