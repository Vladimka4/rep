import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin
from app import db
from app.models import Category, Dish
import hashlib

class NSMParser:
    """Парсер для ресторана На Старом Месте (nsm-22.ru)"""
    
    def __init__(self, base_url="https://nsm-22.ru/"):
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    
    def get_menu_sections(self):
        """Получает список всех разделов меню"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем меню в навигации
            menu_sections = []
            
            # Вариант 1: Ищем в мобильном меню
            mobile_menu = soup.find('div', class_='mobile-nav')
            if mobile_menu:
                links = mobile_menu.find_all('a', class_='woodmart-nav-link')
                for link in links:
                    if '/wp-admin' not in link.get('href', ''):
                        menu_sections.append({
                            'name': link.get_text(strip=True),
                            'url': urljoin(self.base_url, link.get('href'))
                        })
            
            # Вариант 2: Если не нашли в мобильном меню, используем статичный список
            if not menu_sections:
                menu_sections = [
                    {'name': 'Салаты', 'url': 'https://nsm-22.ru/salaty/'},
                    {'name': 'Закуски', 'url': 'https://nsm-22.ru/zakuski/'},
                    {'name': 'Горячие закуски', 'url': 'https://nsm-22.ru/goryachie-zakuski/'},
                    {'name': 'Супы', 'url': 'https://nsm-22.ru/supy/'},
                    {'name': 'Паста', 'url': 'https://nsm-22.ru/pasta/'},
                    {'name': 'Лепка', 'url': 'https://nsm-22.ru/lepka/'},
                    {'name': 'Рыба', 'url': 'https://nsm-22.ru/ryba/'},
                    {'name': 'Мясо и птица', 'url': 'https://nsm-22.ru/myaso-i-ptitsa/'},
                    {'name': 'Гарниры', 'url': 'https://nsm-22.ru/garniry/'},
                    {'name': 'Десерты', 'url': 'https://nsm-22.ru/deserty/'},
                    {'name': 'Детское меню', 'url': 'https://nsm-22.ru/detskoe-menyu/'},
                ]
            
            return menu_sections
            
        except Exception as e:
            print(f"Ошибка при получении разделов меню: {e}")
            return []
    
    def parse_section(self, section_url, section_name):
        """Парсит конкретный раздел меню"""
        try:
            response = requests.get(section_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            dishes = []
            
            # Находим все элементы с блюдами
            # Структура: section с классом prodline содержит 2 блюда (левое и правое)
            prodline_sections = soup.find_all('section', class_='prodline')
            
            for prodline in prodline_sections:
                # В каждой секции prodline есть две колонки с блюдами
                columns = prodline.find_all('div', class_='elementor-column')
                
                for column in columns:
                    dish = self._parse_dish_from_column(column, section_name)
                    if dish:
                        dishes.append(dish)
            
            # Также ищем отдельные блюда вне структуры prodline
            # Проверяем наличие отдельных элементов с классами блюд
            dish_elements = soup.find_all('div', class_=['prodimg', 'prodhead'])
            if dish_elements and not dishes:
                # Альтернативный метод парсинга
                dishes = self._alternative_parse(soup, section_name)
            
            return dishes
            
        except Exception as e:
            print(f"Ошибка при парсинге раздела {section_name}: {e}")
            return []
    
    def _parse_dish_from_column(self, column, section_name):
        """Парсит блюдо из колонки"""
        try:
            # Название блюда
            prodhead = column.find('div', class_='prodhead')
            if not prodhead:
                return None
            
            name_elem = prodhead.find('h2', class_='elementor-heading-title')
            if not name_elem:
                return None
            
            name = name_elem.get_text(strip=True)
            if not name or name == 'Нет названия':
                return None
            
            # Цена
            price = "0"
            prodprice = column.find('div', class_='prodprice')
            if prodprice:
                price_elem = prodprice.find('p')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Извлекаем только числа
                    import re
                    price_match = re.search(r'(\d+[.,]?\d*)', price_text.replace(' ', ''))
                    if price_match:
                        price = str(float(price_match.group(1).replace(',', '.')))
            
            # Вес/описание
            description = ""
            weighttext = column.find('div', class_='weighttext')
            if weighttext:
                weight_elem = weighttext.find('p')
                if weight_elem:
                    description = weight_elem.get_text(strip=True)
            
            # Изображение
            image_url = None
            prodimg = column.find('div', class_='prodimg')
            if prodimg:
                img_elem = prodimg.find('img')
                if img_elem and img_elem.get('src'):
                    image_url = urljoin(self.base_url, img_elem['src'])
            
            return {
                'name': name,
                'price': float(price) if price != "0" else 0.0,
                'description': description,
                'image_url': image_url,
                'section_name': section_name
            }
            
        except Exception as e:
            print(f"Ошибка при парсинге блюда: {e}")
            return None
    
    def _alternative_parse(self, soup, section_name):
        """Альтернативный метод парсинга для сложных структур"""
        dishes = []
        
        # Ищем все изображения блюд
        img_elements = soup.find_all('div', class_='prodimg')
        
        for img_div in img_elements:
            try:
                # Находим связанное название и цену
                parent = img_div.parent
                
                # Ищем название в ближайших элементах
                name_elem = parent.find_next('div', class_='prodhead')
                if not name_elem:
                    continue
                
                name = name_elem.find('h2', class_='elementor-heading-title')
                if not name:
                    continue
                
                name = name.get_text(strip=True)
                
                # Ищем цену
                price = "0"
                price_elem = parent.find_next('div', class_='prodprice')
                if price_elem:
                    price_text = price_elem.find('p')
                    if price_text:
                        import re
                        price_match = re.search(r'(\d+[.,]?\d*)', price_text.get_text(strip=True).replace(' ', ''))
                        if price_match:
                            price = str(float(price_match.group(1).replace(',', '.')))
                
                # Ищем вес
                description = ""
                weight_elem = parent.find_next('div', class_='weighttext')
                if weight_elem:
                    weight_text = weight_elem.find('p')
                    if weight_text:
                        description = weight_text.get_text(strip=True)
                
                # Изображение
                img_elem = img_div.find('img')
                image_url = None
                if img_elem and img_elem.get('src'):
                    image_url = urljoin(self.base_url, img_elem['src'])
                
                dishes.append({
                    'name': name,
                    'price': float(price) if price != "0" else 0.0,
                    'description': description,
                    'image_url': image_url,
                    'section_name': section_name
                })
                
            except Exception as e:
                print(f"Ошибка в альтернативном парсинге: {e}")
                continue
        
        return dishes
    
    def _download_image(self, url):
        """Скачивает изображение и сохраняет локально"""
        try:
            if not url:
                return None
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # Генерируем имя файла
            file_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            file_name = f"nsm_{file_hash}.jpg"
            file_path = os.path.join('app', 'static', 'images', file_name)
            
            # Проверяем существует ли директория
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Сохраняем файл
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            return file_name
            
        except Exception as e:
            print(f"Ошибка загрузки изображения: {e}")
            return None
    
    def parse_all_menu(self):
        """Парсит все меню ресторана"""
        try:
            # Получаем все разделы меню
            sections = self.get_menu_sections()
            print(f"Найдено разделов меню: {len(sections)}")
            
            all_dishes = []
            
            for section in sections:
                print(f"Парсинг раздела: {section['name']}")
                dishes = self.parse_section(section['url'], section['name'])
                print(f"  Найдено блюд: {len(dishes)}")
                
                # Добавляем информацию о разделе к каждому блюду
                for dish in dishes:
                    dish['section_url'] = section['url']
                    all_dishes.append(dish)
                
                # Небольшая задержка между запросами
                import time
                time.sleep(1)
            
            return all_dishes
            
        except Exception as e:
            print(f"Ошибка при парсинге всего меню: {e}")
            return []
    
    def save_to_database(self, dishes):
        """Сохраняет спарсенные блюда в базу данных"""
        try:
            category_map = {}
            
            for dish_data in dishes:
                section_name = dish_data['section_name']
                
                # Создаем или находим категорию
                if section_name not in category_map:
                    category = Category.query.filter_by(name=section_name).first()
                    if not category:
                        category = Category(name=section_name)
                        db.session.add(category)
                        db.session.flush()
                    category_map[section_name] = category
                else:
                    category = category_map[section_name]
                
                # Проверяем, существует ли уже такое блюдо
                existing_dish = Dish.query.filter_by(
                    name=dish_data['name'],
                    category_id=category.id
                ).first()
                
                if not existing_dish:
                    # Создаем новое блюдо
                    dish = Dish(
                        name=dish_data['name'],
                        description=dish_data['description'],
                        price=dish_data['price'],
                        category_id=category.id,
                        is_available=True,
                        image=self._download_image(dish_data['image_url']) if dish_data.get('image_url') else None
                    )
                    db.session.add(dish)
            
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Ошибка сохранения в базу: {e}")
            return False

# Утилитарные функции для использования в проекте
def parse_nsm_menu():
    """Основная функция для парсинга меню"""
    parser = NSMParser()
    dishes = parser.parse_all_menu()
    
    if dishes:
        print(f"Всего спарсено блюд: {len(dishes)}")
        
        # Пример вывода первых 3 блюд
        for i, dish in enumerate(dishes[:3]):
            print(f"  {i+1}. {dish['name']} - {dish['price']} руб. ({dish['section_name']})")
        
        return dishes
    else:
        print("Не удалось получить меню")
        return []

def save_nsm_menu_to_db():
    """Парсит и сохраняет меню в БД"""
    parser = NSMParser()
    dishes = parser.parse_all_menu()
    
    if dishes:
        success = parser.save_to_database(dishes)
        if success:
            print(f"✅ Меню успешно сохранено в базу данных ({len(dishes)} блюд)")
            return True
        else:
            print("❌ Ошибка при сохранении в базу данных")
            return False
    else:
        print("❌ Не удалось получить меню для сохранения")
        return False