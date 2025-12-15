import click
from . import db  # Относительный импорт
from .models import User, Category, Dish
import json
import os

def init_app(app):
    @app.cli.command('create-admin')
    @click.argument('username')
    @click.argument('password')
    def create_admin(username, password):
        """Создание администратора"""
        admin = User.query.filter_by(username=username).first()
        if admin:
            click.echo(f'Пользователь {username} уже существует')
            return
        
        admin = User(
            username=username,
            is_admin=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f'Администратор {username} успешно создан')
    
    @app.cli.command('init-db')
    def init_database():
        """Инициализация базы данных с тестовыми данными"""
        # Создаём категории
        categories_data = [
            {'name': 'Пицца', 'image': 'pizza.jpg'},
            {'name': 'Бургеры', 'image': 'burger.jpg'},
            {'name': 'Суши', 'image': 'sushi.jpg'},
            {'name': 'Напитки', 'image': 'drinks.jpg'},
        ]
        
        for cat_data in categories_data:
            category = Category.query.filter_by(name=cat_data['name']).first()
            if not category:
                category = Category(name=cat_data['name'], image=cat_data['image'])
                db.session.add(category)
        
        db.session.commit()
        
        # Создаём блюда
        dishes_data = [
            {'name': 'Пепперони', 'category': 'Пицца', 'price': 450, 'description': 'Пицца с пепперони и сыром'},
            {'name': 'Маргарита', 'category': 'Пицца', 'price': 380, 'description': 'Классическая пицца с томатами и сыром'},
            {'name': 'Чизбургер', 'category': 'Бургеры', 'price': 250, 'description': 'Бургер с говяжьей котлетой и сыром'},
            {'name': 'Филадельфия', 'category': 'Суши', 'price': 320, 'description': 'Ролл с лососем и сливочным сыром'},
            {'name': 'Кола', 'category': 'Напитки', 'price': 100, 'description': 'Газированный напиток'},
        ]
        
        for dish_data in dishes_data:
            category = Category.query.filter_by(name=dish_data['category']).first()
            if category:
                dish = Dish.query.filter_by(name=dish_data['name']).first()
                if not dish:
                    dish = Dish(
                        name=dish_data['name'],
                        category_id=category.id,
                        price=dish_data['price'],
                        description=dish_data['description'],
                        image=f"{dish_data['name'].lower()}.jpg"
                    )
                    db.session.add(dish)
        
        db.session.commit()

        click.echo('База данных инициализирована с тестовыми данными')
