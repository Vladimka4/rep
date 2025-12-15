from flask import Blueprint, render_template, request, flash, session, redirect, url_for, jsonify
from flask_login import current_user
from . import db  # Вместо from app import db
from .models import Category, Dish, Order, OrderItem

main = Blueprint('main', __name__)

@main.route('/')
def index():
    categories = Category.query.all()
    return render_template('index.html', categories=categories)

@main.route('/menu/<int:category_id>')
def menu(category_id):
    category = Category.query.get_or_404(category_id)
    dishes = Dish.query.filter_by(category_id=category_id, is_available=True).all()
    return render_template('menu.html', category=category, dishes=dishes)

@main.route('/cart')
def cart():
    cart = session.get('cart', {})
    cart_items = []
    total_price = 0
    total_items = 0
    
    for dish_id, item in cart.items():
        cart_items.append({
            'id': dish_id,
            'name': item['name'],
            'price': item['price'],
            'quantity': item['quantity'],
            'image': item.get('image', 'default.jpg'),
            'subtotal': item['price'] * item['quantity']
        })
        total_price += item['price'] * item['quantity']
        total_items += item['quantity']
    
    return render_template('cart.html', 
                         cart_items=cart_items,
                         total_price=total_price,
                         total_items=total_items)

@main.route('/add_to_cart/<int:dish_id>', methods=['POST'])
def add_to_cart(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    cart = session.get('cart', {})
    
    if str(dish_id) in cart:
        cart[str(dish_id)]['quantity'] += 1
    else:
        cart[str(dish_id)] = {
            'name': dish.name,
            'price': float(dish.price),
            'quantity': 1,
            'image': dish.image or 'default.jpg'
        }
    
    session['cart'] = cart
    
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
    return jsonify({'success': True})

@main.route('/remove_from_cart/<int:dish_id>', methods=['POST'])
def remove_from_cart(dish_id):
    cart = session.get('cart', {})
    
    if str(dish_id) in cart:
        del cart[str(dish_id)]
        session['cart'] = cart
        return jsonify({'success': True})
    
    return jsonify({'success': False}), 404

@main.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = session.get('cart', {})
    
    if not cart:
        flash('Корзина пуста', 'error')
        return redirect(url_for('main.cart'))
    
    if request.method == 'POST':
        # Считаем итог
        total = sum(item['price'] * item['quantity'] for item in cart.values())
        
        # Создаём заказ
        if current_user.is_authenticated:
            order = Order(
                user_id=current_user.id,
                customer_name=current_user.username,
                address=request.form['address'],
                total=total
            )
        else:
            order = Order(
                customer_name=request.form['name'],
                address=request.form['address'],
                total=total
            )
        
        db.session.add(order)
        db.session.commit()
        
        # Добавляем товары в заказ
        for dish_id, item in cart.items():
            order_item = OrderItem(
                order_id=order.id,
                dish_id=int(dish_id),
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)
        
        db.session.commit()
        
        # Очищаем корзину
        session.pop('cart', None)
        
        flash(f'Заказ #{order.id} успешно оформлен!', 'success')
        return redirect(url_for('main.index'))
    
    # Подсчёт для показа в форме
    total_price = sum(item['price'] * item['quantity'] for item in cart.values())
    total_items = sum(item['quantity'] for item in cart.values())
    
    return render_template('checkout.html',
                         total_price=total_price,

                         total_items=total_items)
