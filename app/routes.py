from flask import Blueprint, render_template, request, flash, session, redirect, url_for, jsonify
from flask_login import current_user, login_required
from . import db
from .models import Category, Dish, Order, OrderItem, Favorite
import json
import logging

logger = logging.getLogger(__name__)

# ЭТА СТРОКА ОБЯЗАТЕЛЬНО ДОЛЖНА БЫТЬ:
main = Blueprint('main', __name__)

@main.route('/')
def index():
    try:
        categories = Category.query.all()
        return render_template('index.html', categories=categories)
    except Exception as e:
        logger.error(f"Ошибка загрузки главной страницы: {str(e)}")
        flash('Ошибка загрузки главной страницы', 'danger')
        return render_template('index.html', categories=[])

@main.route('/menu/<int:category_id>')
def menu(category_id):
    try:
        category = Category.query.get_or_404(category_id)
        dishes = Dish.query.filter_by(category_id=category_id, is_available=True).all()
        
        favorite_ids = []
        if current_user.is_authenticated:
            favorites = Favorite.query.filter_by(user_id=current_user.id).all()
            favorite_ids = [f.dish_id for f in favorites]
        
        return render_template('menu.html', 
                            category=category, 
                            dishes=dishes,
                            favorite_ids=favorite_ids)
    except Exception as e:
        logger.error(f"Ошибка загрузки меню категории {category_id}: {str(e)}")
        flash('Ошибка загрузки меню', 'danger')
        return redirect(url_for('main.index'))

@main.route('/cart')
def cart():
    try:
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
            else:
                logger.warning(f"Блюдо с ID {dish_id} не найдено в корзине")
        
        return render_template('cart.html', 
                            cart_items=cart_items,
                            total_price=total_price,
                            total_items=total_items)
    except Exception as e:
        logger.error(f"Ошибка загрузки корзины: {str(e)}")
        flash('Ошибка загрузки корзины', 'danger')
        return render_template('cart.html', 
                            cart_items=[],
                            total_price=0,
                            total_items=0)

@main.route('/add_to_cart/<int:dish_id>', methods=['POST'])
def add_to_cart(dish_id):
    try:
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
        
        total_items = sum(item['quantity'] for item in cart.values())
        
        return jsonify({
            'success': True,
            'cart_total': total_items,
            'message': f'{dish.name} добавлен в корзину'
        })
    except Exception as e:
        logger.error(f"Ошибка добавления в корзину {dish_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@main.route('/update_cart/<int:dish_id>', methods=['POST'])
def update_cart(dish_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Нет данных'}), 400
            
        quantity = data.get('quantity', 1)
        
        if not isinstance(quantity, int) or quantity < 0:
            return jsonify({'success': False, 'message': 'Некорректное количество'}), 400
        
        cart = session.get('cart', {})
        
        if str(dish_id) in cart:
            if quantity <= 0:
                del cart[str(dish_id)]
            else:
                cart[str(dish_id)]['quantity'] = quantity
        
        session['cart'] = cart
        session.modified = True
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Ошибка обновления корзины {dish_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@main.route('/remove_from_cart/<int:dish_id>', methods=['POST'])
def remove_from_cart(dish_id):
    try:
        cart = session.get('cart', {})
        
        if str(dish_id) in cart:
            del cart[str(dish_id)]
            session['cart'] = cart
            session.modified = True
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': 'Товар не найден'}), 404
    except Exception as e:
        logger.error(f"Ошибка удаления из корзины {dish_id}: {str(e)}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@main.route('/add_to_favorites/<int:dish_id>', methods=['POST'])
@login_required
def add_to_favorites(dish_id):
    try:
        dish = Dish.query.get_or_404(dish_id)
        
        favorite = Favorite.query.filter_by(
            user_id=current_user.id, 
            dish_id=dish_id
        ).first()
        
        if favorite:
            db.session.delete(favorite)
            action = 'removed'
            message = 'Удалено из избранного'
        else:
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
    except Exception as e:
        logger.error(f"Ошибка добавления в избранное {dish_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Ошибка сервера'}), 500

@main.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    try:
        cart = session.get('cart', {})
        
        if not cart:
            flash('Корзина пуста', 'error')
            return redirect(url_for('main.cart'))
        
        if request.method == 'POST':
            # Валидация данных
            address = request.form.get('address', '').strip()
            phone = request.form.get('phone', '').strip()
            
            if not address or len(address) < 10:
                flash('Пожалуйста, укажите корректный адрес доставки', 'danger')
                return redirect(url_for('main.checkout'))
            
            # Считаем итог
            total = 0
            order_items = []
            
            for dish_id, item in cart.items():
                dish = Dish.query.get(int(dish_id))
                if dish:
                    if not dish.is_available:
                        flash(f'Блюдо "{dish.name}" временно недоступно', 'warning')
                        return redirect(url_for('main.cart'))
                    
                    total += dish.price * item['quantity']
                    order_items.append({
                        'dish': dish,
                        'quantity': item['quantity'],
                        'price': dish.price
                    })
                else:
                    logger.warning(f"Блюдо с ID {dish_id} не найдено при оформлении заказа")
            
            if total <= 0:
                flash('Ошибка расчета суммы заказа', 'danger')
                return redirect(url_for('main.cart'))
            
            # Создаём заказ
            order = Order(
                user_id=current_user.id,
                customer_name=current_user.username,
                address=address,
                phone=phone,
                total=total
            )
            
            db.session.add(order)
            db.session.flush()  # Получаем ID заказа
            
            # Добавляем товары в заказ
            for item in order_items:
                order_item = OrderItem(
                    order_id=order.id,
                    dish_id=item['dish'].id,
                    quantity=item['quantity'],
                    price=item['price']
                )
                db.session.add(order_item)
            
            db.session.commit()
            
            # Очищаем корзину
            session.pop('cart', None)
            
            flash(f'Заказ #{order.id} успешно оформлен!', 'success')
            return redirect(url_for('user_bp.orders'))
        
        # GET запрос - показываем корзину
        cart_items = []
        total_price = 0
        total_items = 0
        
        for dish_id, item in cart.items():
            dish = Dish.query.get(dish_id)
            if dish:
                if not dish.is_available:
                    flash(f'Блюдо "{dish.name}" временно недоступно и было удалено из корзины', 'warning')
                    continue
                    
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
                            
    except Exception as e:
        logger.error(f"Ошибка оформления заказа: {str(e)}")
        db.session.rollback()
        flash('Ошибка оформления заказа. Пожалуйста, попробуйте позже', 'danger')
        return redirect(url_for('main.cart'))

