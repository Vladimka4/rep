import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin
from app import db
from app.models import Category, Dish
import hashlib
import re
from decimal import Decimal
import logging
import tempfile
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class NSMParser:
    """Парсер для ресторана На Старом Месте (nsm-22.ru)"""
    
    def __init__(self, base_url="https://nsm-22.ru/"):
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.timeout = 10
    
    def safe_float(self, price_str):
        """Безопасное преобразование строки в float"""
        try:
            if not price_str:
                return 0.0
            
            # Убираем все символы кроме цифр, точки и запятой
            clean_price = re.sub(r'[^\d.,]', '', price_str)
            
            # Заменяем запятую на точку, если это десятичный разделитель
            if ',' in clean_price and '.' in clean_price:
                # Если есть и точка и запятая, запятая - разделитель тысяч
                clean_price = clean_price.replace(',', '')
            else:
                # Если только запятая, заменяем на точку
                clean_price = clean_price.replace(',', '.')
            
            # Удаляем лишние точки (оставляем только первую)
            parts = clean_price.split('.')
            if len(parts) > 2:
                clean_price = parts[0] + '.' + ''.join(parts[1:])
            
            return float(Decimal(clean_price))
        except (ValueError, TypeError) as e:
            logger.warning(f"Ошибка преобразования цены '{price_str}': {e}")
            return 0.0
    
    def clean_text(self, text):
        """Очистка текста от лишних пробелов и символов"""
        if not text:
            return ""
        
        # Убираем лишние пробелы и переносы строк
        cleaned = ' '.join(text.split())
        
        # Убираем нежелательные символы
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
        
        return cleaned.strip()
    
    def get_menu_sections(self):
        """Получает список всех разделов меню"""
        try:
            response = requests.get(self.base_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            menu_sections = []
            
            # Вариант 1: Ищем в мобильном меню
            mobile_menu = soup.find('div', class_='mobile-nav')
            if mobile_menu:
                links = mobile_menu.find_all('a', class_='woodmart-nav-link')
                for link in links:
                    href = link.get('href', '')
                    if href and '/wp-admin' not in href:
                        menu_sections.append({
                            'name': self.clean_text(link.get_text(strip=True)),
                            'url': urljoin(self.base_url, href)
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
            
            # Фильтруем пустые значения
            menu_sections = [s for s in menu_sections if s['name'] and s['url']]
            
            return menu_sections
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при получении разделов меню: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении разделов меню: {e}")
            return []
    
    def parse_section(self, section_url, section_name):
        """Парсит конкретный раздел меню"""
        try:
            response = requests.get(section_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            dishes = []
            
            # Находим все элементы с блюдами
            prodline_sections = soup.find_all('section', class_='prodline')
            
            for prodline in prodline_sections:
                columns = prodline.find_all('div', class_='elementor-column')
                
                for column in columns:
                    dish = self._parse_dish_from_column(column, section_name)
                    if dish:
                        dishes.append(dish)
            
            # Также ищем отдельные блюда вне структуры prodline
            dish_elements = soup.find_all('div', class_=['prodimg', 'prodhead'])
            if dish_elements and not dishes:
                dishes = self._alternative_parse(soup, section_name)
            
            return dishes
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при парсинге раздела {section_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при парсинге раздела {section_name}: {e}")
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
            
            name = self.clean_text(name_elem.get_text(strip=True))
            if not name or name == 'Нет названия' or len(name) < 2:
                return None
            
            # Цена
            price = 0.0
            prodprice = column.find('div', class_='prodprice')
            if prodprice:
                price_elem = prodprice.find('p')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = self.safe_float(price_text)
            
            # Вес/описание
            description = ""
            weighttext = column.find('div', class_='weighttext')
            if weighttext:
                weight_elem = weighttext.find('p')
                if weight_elem:
                    description = self.clean_text(weight_elem.get_text(strip=True))
            
            # Изображение - сохраняем URL для последующей загрузки
            image_url = None
            prodimg = column.find('div', class_='prodimg')
            if prodimg:
                img_elem = prodimg.find('img')
                if img_elem and img_elem.get('src'):
                    image_url = urljoin(self.base_url, img_elem['src'])
            
            return {
                'name': name,
                'price': price,
                'description': description,
                'image_url': image_url,
                'section_name': section_name
            }
            
        except Exception as e:
            logger.warning(f"Ошибка при парсинге блюда: {e}")
            return None
    
    def _alternative_parse(self, soup, section_name):
        """Альтернативный метод парсинга для сложных структур"""
        dishes = []
        
        img_elements = soup.find_all('div', class_='prodimg')
        
        for img_div in img_elements:
            try:
                parent = img_div.parent
                
                name_elem = parent.find_next('div', class_='prodhead')
                if not name_elem:
                    continue
                
                name = name_elem.find('h2', class_='elementor-heading-title')
                if not name:
                    continue
                
                name = self.clean_text(name.get_text(strip=True))
                if not name:
                    continue
                
                # Цена
                price = 0.0
                price_elem = parent.find_next('div', class_='prodprice')
                if price_elem:
                    price_text = price_elem.find('p')
                    if price_text:
                        price = self.safe_float(price_text.get_text(strip=True))
                
                # Вес
                description = ""
                weight_elem = parent.find_next('div', class_='weighttext')
                if weight_elem:
                    weight_text = weight_elem.find('p')
                    if weight_text:
                        description = self.clean_text(weight_text.get_text(strip=True))
                
                # Изображение
                img_elem = img_div.find('img')
                image_url = None
                if img_elem and img_elem.get('src'):
                    image_url = urljoin(self.base_url, img_elem['src'])
                
                dishes.append({
                    'name': name,
                    'price': price,
                    'description': description,
                    'image_url': image_url,
                    'section_name': section_name
                })
                
            except Exception as e:
                logger.warning(f"Ошибка в альтернативном парсинге: {e}")
                continue
        
        return dishes
    
    def _download_image(self, url):
        """Скачивает изображение и сохраняет локально"""
        try:
            if not url:
                logger.debug("Пустой URL изображения")
                return None
            
            # Пропускаем placeholder изображения
            if 'placeholder' in url or 'nophoto' in url:
                logger.debug(f"Пропускаем placeholder: {url}")
                return None
            
            # Ограничиваем размер загружаемых изображений
            response = requests.get(url, headers=self.headers, timeout=5, stream=True)
            response.raise_for_status()
            
            # Проверяем Content-Type
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                logger.warning(f"URL не является изображением: {content_type}")
                return None
            
            # Ограничиваем размер файла (макс 500KB)
            content_length = int(response.headers.get('content-length', 0))
            if content_length > 500 * 1024:  # 500KB
                logger.warning(f"Изображение слишком большое: {content_length} bytes")
                return None
            
            # Генерируем безопасное имя файла
            file_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            file_name = f"nsm_{file_hash}.jpg"
            
            # Определяем путь для сохранения
            static_path = Path('app/static/images')
            
            # Проверяем существование директории, создаем если нужно
            if not static_path.exists():
                try:
                    static_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Создана директория: {static_path}")
                except Exception as e:
                    logger.warning(f"Не удалось создать директорию {static_path}: {e}")
                    return None
            else:
                # Проверяем, не существует ли уже файл
                file_path = static_path / file_name
                if file_path.exists():
                    logger.debug(f"Файл уже существует: {file_name}")
                    return file_name
            
            file_path = static_path / file_name
            
            # Сохраняем файл частями
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Проверяем размер файла
            if file_path.stat().st_size == 0:
                logger.warning(f"Пустой файл изображения: {file_name}")
                try:
                    file_path.unlink()
                except:
                    pass
                return None
            
            logger.info(f"Изображение сохранено: {file_name} ({file_path.stat().st_size} bytes)")
            return file_name
            
        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут при загрузке изображения: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка загрузки изображения {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Ошибка сохранения изображения {url}: {e}")
            return None
    
    def parse_all_menu(self):
        """Парсит все меню ресторана (только текст, без загрузки изображений)"""
        try:
            sections = self.get_menu_sections()
            logger.info(f"Найдено разделов меню: {len(sections)}")
            
            all_dishes = []
            
            for section in sections:
                logger.info(f"Парсинг раздела: {section['name']}")
                dishes = self.parse_section(section['url'], section['name'])
                logger.info(f"  Найдено блюд: {len(dishes)}")
                
                for dish in dishes:
                    dish['section_url'] = section['url']
                    all_dishes.append(dish)
                
                time.sleep(0.2)  # Уменьшенная задержка
            
            # Удаляем дубликаты
            unique_dishes = []
            seen_names = set()
            
            for dish in all_dishes:
                if dish['name'] not in seen_names:
                    seen_names.add(dish['name'])
                    unique_dishes.append(dish)
            
            logger.info(f"Уникальных блюд после фильтрации: {len(unique_dishes)}")
            return unique_dishes
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге всего меню: {e}")
            return []
    
    def save_to_database(self, dishes):
        """Сохраняет спарсенные блюда в базу данных (только текст)"""
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
                    
                    # Сохраняем блюдо БЕЗ изображения (оно будет загружено позже)
                    dish = Dish(
                        name=name,
                        description=description,
                        price=dish_data['price'],
                        category_id=category.id,
                        is_available=True,
                        image=None  # Изображение будет загружено отдельно
                    )
                    db.session.add(dish)
                    added_count += 1
                else:
                    skipped_count += 1
            
            db.session.commit()
            logger.info(f"Сохранено {added_count} блюд (без изображений), пропущено {skipped_count} дубликатов")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Ошибка сохранения в базу: {e}")
            return False
    
    def download_images(self, limit=None):
        """Загружает изображения для блюд, у которых их нет"""
        try:
            # Получаем блюда без изображений
            query = Dish.query.filter(Dish.image.is_(None))
            if limit:
                query = query.limit(limit)
            
            dishes_without_images = query.all()
            
            logger.info(f"Найдено {len(dishes_without_images)} блюд без изображений")
            
            if not dishes_without_images:
                return 0
            
            downloaded_count = 0
            
            for dish in dishes_without_images:
                # Для каждого блюда нужно получить URL изображения из базы
                # Но у нас нет поля image_url в модели, поэтому нам нужно как-то хранить URL
                # Или нужно парсить заново с сохранением URL
                
                # Вместо этого, создадим временный парсер для поиска изображения
                # Это не оптимально, но для демонстрации сойдет
                
                # Для каждого блюда получим категорию и попробуем найти изображение
                category = Category.query.get(dish.category_id)
                if not category:
                    continue
                
                # Парсим раздел для поиска изображения
                logger.info(f"Поиск изображения для: {dish.name}")
                
                # Получаем URL раздела из статичного списка
                section_url = self._get_section_url_by_name(category.name)
                if not section_url:
                    continue
                
                # Парсим раздел и ищем изображение для этого блюда
                image_url = self._find_image_url_for_dish(section_url, dish.name)
                if image_url:
                    # Загружаем изображение
                    image_filename = self._download_image(image_url)
                    if image_filename:
                        dish.image = image_filename
                        downloaded_count += 1
                        logger.info(f"  Загружено изображение для: {dish.name}")
                        
                        # Коммитим после каждого успешного сохранения
                        db.session.commit()
                        
                        # Пауза между загрузками
                        time.sleep(1)
            
            return downloaded_count
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Ошибка при загрузке изображений: {e}")
            return 0
    
    def _get_section_url_by_name(self, section_name):
        """Получает URL раздела по его имени"""
        sections_mapping = {
            'Салаты': 'https://nsm-22.ru/salaty/',
            'Закуски': 'https://nsm-22.ru/zakuski/',
            'Горячие закуски': 'https://nsm-22.ru/goryachie-zakuski/',
            'Супы': 'https://nsm-22.ru/supy/',
            'Паста': 'https://nsm-22.ru/pasta/',
            'Лепка': 'https://nsm-22.ru/lepka/',
            'Рыба': 'https://nsm-22.ru/ryba/',
            'Мясо и птица': 'https://nsm-22.ru/myaso-i-ptitsa/',
            'Гарниры': 'https://nsm-22.ru/garniry/',
            'Десерты': 'https://nsm-22.ru/deserty/',
            'Детское меню': 'https://nsm-22.ru/detskoe-menyu/',
        }
        return sections_mapping.get(section_name)
    
    def _find_image_url_for_dish(self, section_url, dish_name):
        """Находит URL изображения для конкретного блюда"""
        try:
            response = requests.get(section_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем все блюда в разделе
            prodline_sections = soup.find_all('section', class_='prodline')
            
            for prodline in prodline_sections:
                columns = prodline.find_all('div', class_='elementor-column')
                
                for column in columns:
                    # Ищем название блюда
                    prodhead = column.find('div', class_='prodhead')
                    if not prodhead:
                        continue
                    
                    name_elem = prodhead.find('h2', class_='elementor-heading-title')
                    if not name_elem:
                        continue
                    
                    name = self.clean_text(name_elem.get_text(strip=True))
                    
                    # Если нашли нужное блюдо
                    if name == dish_name:
                        # Ищем изображение
                        prodimg = column.find('div', class_='prodimg')
                        if prodimg:
                            img_elem = prodimg.find('img')
                            if img_elem and img_elem.get('src'):
                                return urljoin(self.base_url, img_elem['src'])
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка при поиске изображения для {dish_name}: {e}")
            return None

def parse_nsm_menu():
    """Основная функция для парсинга меню (только текст)"""
    parser = NSMParser()
    dishes = parser.parse_all_menu()
    
    if dishes:
        logger.info(f"Всего спарсено блюд: {len(dishes)}")
        
        # Выводим статистику по ценам
        prices = [d['price'] for d in dishes if d['price'] > 0]
        if prices:
            logger.info(f"Средняя цена: {sum(prices)/len(prices):.2f} руб.")
            logger.info(f"Минимальная цена: {min(prices):.2f} руб.")
            logger.info(f"Максимальная цена: {max(prices):.2f} руб.")
        
        return dishes
    else:
        logger.warning("Не удалось получить меню")
        return []

def save_nsm_menu_to_db():
    """Парсит и сохраняет меню в БД (только текст)"""
    parser = NSMParser()
    dishes = parser.parse_all_menu()
    
    if dishes:
        success = parser.save_to_database(dishes)
        if success:
            logger.info(f"✅ Текст меню успешно сохранено в базу данных ({len(dishes)} блюд)")
            return True
        else:
            logger.error("❌ Ошибка при сохранении в базу данных")
            return False
    else:
        logger.error("❌ Не удалось получить меню для сохранения")
        return False

def download_nsm_images(limit=5):
    """Загружает изображения для блюд"""
    parser = NSMParser()
    
    logger.info(f"Начинаю загрузку изображений (максимум {limit})...")
    downloaded = parser.download_images(limit=limit)
    
    if downloaded > 0:
        logger.info(f"✅ Загружено {downloaded} изображений")
        return True
    else:
        logger.info("❌ Не удалось загрузить изображения")
        return False
