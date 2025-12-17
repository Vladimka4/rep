def save_to_database(self, dishes):
    """Сохраняет спарсенные блюда в базу данных"""
    try:
        category_map = {}
        added_count = 0
        skipped_count = 0
        
        for dish_data in dishes:
            section_name = dish_data['section_name']
            
            if section_name not in category_map:
                category = Category.query.filter_by(name=section_name).first()
                if not category:
                    category = Category(name=section_name)
                    db.session.add(category)
                    db.session.flush()
                category_map[section_name] = category
            else:
                category = category_map[section_name]
            
            # Проверяем существование блюда
            existing_dish = Dish.query.filter_by(
                name=dish_data['name'],
                category_id=category.id
            ).first()
            
            if not existing_dish:
                # Ограничиваем длину названия
                name = dish_data['name'][:100] if len(dish_data['name']) > 100 else dish_data['name']
                
                # Ограничиваем длину описания
                description = dish_data['description']
                if description and len(description) > 500:
                    description = description[:497] + '...'
                
                # НЕ загружаем изображения, чтобы ускорить процесс
                dish = Dish(
                    name=name,
                    description=description,
                    price=dish_data['price'],
                    category_id=category.id,
                    is_available=True,
                    image=None  # Изображения не загружаем для скорости
                )
                db.session.add(dish)
                added_count += 1
            else:
                skipped_count += 1
        
        db.session.commit()
        logger.info(f"Сохранено {added_count} блюд, пропущено {skipped_count} дубликатов")
        return True
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка сохранения в базу: {e}")
        return False
