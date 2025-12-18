import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
from app import db
from app.models import Category, Dish, ImageQueue
import hashlib
import re
from decimal import Decimal
import logging
from pathlib import Path
import time
from sqlalchemy import or_, and_

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
        self.timeout = 15
        self.downloaded_urls = set()  # Кэш уже скачанных URL
        self.failed_urls = set()  # Кэш неудачных URL
    
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
                    if href and '/wp-admin' not in href and '#' not in href:
                        menu_sections.append({
                            'name': self.clean_text(link.get_text(strip=True)),
                            'url': urljoin(self.base_url, href)
                        })
            
            # Вариант 2: Если не нашли в мобильном меню, используем статичный список
            if not menu_sections or len(menu_sections) < 5:
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
            
            # Удаляем дубликаты по URL
            seen_urls = set()
            unique_sections = []
            for section in menu_sections:
                if section['url'] not in seen_urls:
                    seen_urls.add(section['url'])
                    unique_sections.append(section)
            
            return unique_sections
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при получении разделов меню: {e}")
            return self.get_static_sections()
        except Exception as e:
            logger.error(f"Ошибка при получении разделов меню: {e}")
            return self.get_static_sections()
    
    def get_static_sections(self):
        """Возвращает статичный список разделов при ошибке"""
        return [
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
    
    def parse_section(self, section_url, section_name):
        """Парсит конкретный раздел меню"""
        try:
            response = requests.get(section_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            dishes = []
            
            # Находим все элементы с блюдами - несколько возможных структур
            # Вариант 1: Современная структура
            prodline_sections = soup.find_all('section', class_='prodline')
            
            for prodline in prodline_sections:
                columns = prodline.find_all('div', class_='elementor-column')
                
                for column in columns:
                    dish = self._parse_dish_from_column(column, section_name)
                    if dish and dish['price'] > 0:  # Фильтруем блюда без цены
                        dishes.append(dish)
            
            # Вариант 2: Альтернативная структура
            if not dishes:
                dish_wrappers = soup.find_all('div', class_=['prodimg-wrapper', 'dish-item', 'menu-item'])
                for wrapper in dish_wrappers:
                    dish = self._parse_dish_from_wrapper(wrapper, section_name)
                    if dish and dish['price'] > 0:  # Фильтруем блюда без цены
                        dishes.append(dish)
            
            # Вариант 3: Поиск по общей структуре
            if not dishes:
                dish_elements = soup.find_all(['div', 'article'], class_=lambda x: x and any(
                    cls in str(x).lower() for cls in ['dish', 'prod', 'menu', 'food', 'item']
                ))
                for element in dish_elements:
                    dish = self._parse_dish_generic(element, section_name)
                    if dish and dish['price'] > 0:  # Фильтруем блюда без цены
                        dishes.append(dish)
            
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
            name = None
            prodhead = column.find('div', class_='prodhead')
            if prodhead:
                name_elem = prodhead.find(['h2', 'h3', 'h4', 'p'], class_=lambda x: x and 'title' in str(x).lower())
                if not name_elem:
                    name_elem = prodhead.find(['h2', 'h3', 'h4', 'p'])
                if name_elem:
                    name = self.clean_text(name_elem.get_text(strip=True))
            
            if not name:
                # Попробуем найти название в других местах
                name_elem = column.find(['h2', 'h3', 'h4'], class_=lambda x: x and 'title' in str(x).lower())
                if name_elem:
                    name = self.clean_text(name_elem.get_text(strip=True))
            
            if not name or name == 'Нет названия' or len(name) < 2:
                return None
            
            # Цена
            price = 0.0
            prodprice = column.find('div', class_='prodprice')
            if prodprice:
                price_elem = prodprice.find(['p', 'span', 'div'])
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = self.safe_float(price_text)
            
            if price <= 0:
                # Ищем цену в других местах
                price_elements = column.find_all(['span', 'div'], class_=lambda x: x and any(
                    word in str(x).lower() for word in ['price', 'cost', 'руб', '₽']
                ))
                for elem in price_elements:
                    price_text = elem.get_text(strip=True)
                    found_price = self.safe_float(price_text)
                    if found_price > 0:
                        price = found_price
                        break
            
            # Удаляем блюдо, если цена <= 0
            if price <= 0:
                logger.debug(f"Блюдо '{name}' удалено - цена отсутствует или равна 0")
                return None
            
            # Вес/описание
            description = ""
            weighttext = column.find('div', class_='weighttext')
            if weighttext:
                desc_elem = weighttext.find(['p', 'span', 'div'])
                if desc_elem:
                    description = self.clean_text(desc_elem.get_text(strip=True))
            
            if not description:
                # Ищем описание в других местах
                desc_elements = column.find_all(['p', 'div'], class_=lambda x: x and any(
                    word in str(x).lower() for word in ['desc', 'text', 'weight', 'вес', 'состав']
                ))
                for elem in desc_elements[:2]:  # Берем первые 2 элемента
                    text = self.clean_text(elem.get_text(strip=True))
                    if text and text != name and not any(word in text.lower() for word in ['руб', '₽', 'цена']):
                        description = text
                        break
            
            # Изображение
            image_url = None
            prodimg = column.find('div', class_='prodimg')
            if prodimg:
                img_elem = prodimg.find('img')
                if img_elem and img_elem.get('src'):
                    image_url = urljoin(self.base_url, img_elem['src'])
            
            if not image_url:
                # Ищем изображение в других местах
                img_elem = column.find('img')
                if img_elem and img_elem.get('src'):
                    src = img_elem['src']
                    if not src.startswith(('data:', 'javascript:')):
                        image_url = urljoin(self.base_url, src)
            
            return {
                'name': name[:100],  # Ограничиваем длину
                'price': price,
                'description': description[:500] if description else "",  # Ограничиваем длину
                'image_url': image_url,
                'section_name': section_name
            }
            
        except Exception as e:
            logger.debug(f"Ошибка при парсинге блюда из колонки: {e}")
            return None
    
    def _parse_dish_from_wrapper(self, wrapper, section_name):
        """Альтернативный метод парсинга блюда"""
        try:
            # Название
            name_elem = wrapper.find(['h2', 'h3', 'h4', 'p'], class_=lambda x: x and any(
                word in str(x).lower() for word in ['title', 'name', 'dish-name']
            ))
            if not name_elem:
                name_elem = wrapper.find(['h2', 'h3', 'h4'])
            
            if not name_elem:
                return None
            
            name = self.clean_text(name_elem.get_text(strip=True))
            if not name or len(name) < 2:
                return None
            
            # Цена
            price = 0.0
            price_elem = wrapper.find(['span', 'div', 'p'], class_=lambda x: x and any(
                word in str(x).lower() for word in ['price', 'cost', 'руб', '₽']
            ))
            if price_elem:
                price = self.safe_float(price_elem.get_text(strip=True))
            
            # Удаляем блюдо, если цена <= 0
            if price <= 0:
                logger.debug(f"Блюдо '{name}' удалено - цена отсутствует или равна 0")
                return None
            
            # Описание
            description = ""
            desc_elem = wrapper.find(['p', 'div'], class_=lambda x: x and any(
                word in str(x).lower() for word in ['desc', 'text', 'weight', 'вес', 'состав']
            ))
            if desc_elem:
                description = self.clean_text(desc_elem.get_text(strip=True))
            
            # Изображение
            image_url = None
            img_elem = wrapper.find('img')
            if img_elem and img_elem.get('src'):
                src = img_elem['src']
                if not src.startswith(('data:', 'javascript:')):
                    image_url = urljoin(self.base_url, src)
            
            return {
                'name': name[:100],
                'price': price,
                'description': description[:500] if description else "",
                'image_url': image_url,
                'section_name': section_name
            }
            
        except Exception as e:
            logger.debug(f"Ошибка в альтернативном парсинге: {e}")
            return None
    
    def _parse_dish_generic(self, element, section_name):
        """Универсальный метод парсинга блюда"""
        try:
            # Получаем весь текст элемента
            full_text = element.get_text(' ', strip=True)
            if len(full_text) < 10:  # Слишком мало текста
                return None
            
            # Пытаемся выделить название и цену
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            if len(lines) < 2:
                return None
            
            # Первая строка - предположительно название
            name = lines[0][:100]
            
            # Ищем цену в тексте
            price = 0.0
            for line in lines:
                found_price = self.safe_float(line)
                if found_price > 0:
                    price = found_price
                    break
            
            # Удаляем блюдо, если цена <= 0
            if price <= 0:
                logger.debug(f"Блюдо '{name}' удалено - цена отсутствует или равна 0")
                return None
            
            # Описание - остальной текст
            description_parts = []
            for line in lines[1:]:  # Пропускаем первую строку (название)
                if not any(word in line.lower() for word in ['руб', '₽', 'цена']) and line != name:
                    description_parts.append(line)
            
            description = ' '.join(description_parts)[:500]
            
            # Изображение
            image_url = None
            img_elem = element.find('img')
            if img_elem and img_elem.get('src'):
                src = img_elem['src']
                if not src.startswith(('data:', 'javascript:')):
                    image_url = urljoin(self.base_url, src)
            
            return {
                'name': name,
                'price': price,
                'description': description,
                'image_url': image_url,
                'section_name': section_name
            }
            
        except Exception as e:
            logger.debug(f"Ошибка в универсальном парсинге: {e}")
            return None
    
    def _get_image_filename_from_url(self, url):
        """Генерирует имя файла из URL"""
        if not url:
            return None
        
        # Пропускаем placeholder изображения
        if any(x in url.lower() for x in ['placeholder', 'nophoto', 'default', 'no-image', 'noimage']):
            return None
        
        # Извлекаем имя файла из URL
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Извлекаем расширение файла
        if '.' in path:
            ext = path.split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                # Генерируем хеш от URL для уникальности
                url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
                return f"nsm_{url_hash}.{ext}"
            else:
                # Неизвестное расширение, используем jpg по умолчанию
                url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
                return f"nsm_{url_hash}.jpg"
        else:
            # Нет расширения, используем jpg
            url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
            return f"nsm_{url_hash}.jpg"
    
    def _is_image_downloaded(self, image_filename):
        """Проверяет, скачано ли уже изображение"""
        if not image_filename:
            return False
        
        # Проверяем в кэше
        if image_filename in self.downloaded_urls:
            return True
        
        # Проверяем в базе данных
        existing_dish = Dish.query.filter_by(image=image_filename).first()
        if existing_dish:
            self.downloaded_urls.add(image_filename)
            return True
        
        # Проверяем файловую систему
        static_path = Path('app/static/images')
        file_path = static_path / image_filename
        
        if file_path.exists() and file_path.stat().st_size > 0:
            self.downloaded_urls.add(image_filename)
            return True
        
        return False
    
    def _is_url_downloaded(self, url):
        """Проверяет, скачан ли уже этот URL"""
        if not url:
            return False
        
        # Проверяем в кэше неудачных URL
        if url in self.failed_urls:
            return True
        
        # Генерируем имя файла и проверяем, скачан ли он
        image_filename = self._get_image_filename_from_url(url)
        if not image_filename:
            return True  # Считаем, что placeholder уже "скачан"
        
        return self._is_image_downloaded(image_filename)
    
    def _add_to_image_queue(self, dish_id, image_url):
        """Добавляет URL изображения в очередь для загрузки"""
        try:
            # Проверяем, нет ли уже этого URL в очереди
            existing_queue = ImageQueue.query.filter_by(
                dish_id=dish_id,
                image_url=image_url
            ).first()
            
            if existing_queue:
                # Обновляем статус, если задача была неудачной
                if existing_queue.status == 'failed' and existing_queue.retry_count < 3:
                    existing_queue.status = 'pending'
                    existing_queue.retry_count += 1
                    existing_queue.updated_at = datetime.utcnow()
                    db.session.commit()
                    logger.debug(f"URL обновлен в очереди для повторной попытки: {image_url}")
                return existing_queue.id
            
            # Создаем новую запись в очереди
            image_queue = ImageQueue(
                dish_id=dish_id,
                image_url=image_url,
                status='pending',
                priority=1
            )
            db.session.add(image_queue)
            db.session.commit()
            
            logger.info(f"URL добавлен в очередь загрузки: {image_url}")
            return image_queue.id
            
        except Exception as e:
            logger.error(f"Ошибка добавления в очередь: {e}")
            db.session.rollback()
            return None
    
    def _process_image_queue(self, limit=None):
        """Обрабатывает очередь изображений"""
        try:
            # Получаем задачи из очереди с высоким приоритетом
            query = ImageQueue.query.filter(
                ImageQueue.status.in_(['pending', 'failed'])
            ).order_by(ImageQueue.priority, ImageQueue.created_at)
            
            if limit:
                query = query.limit(limit)
            
            queue_items = query.all()
            
            logger.info(f"Найдено {len(queue_items)} задач в очереди")
            
            if not queue_items:
                return 0, 0, 0  # downloaded, failed, skipped
            
            downloaded = 0
            failed = 0
            skipped = 0
            
            for item in queue_items:
                try:
                    # Обновляем статус на "загружается"
                    item.status = 'downloading'
                    item.updated_at = datetime.utcnow()
                    db.session.commit()
                    
                    # Получаем блюдо
                    dish = Dish.query.get(item.dish_id)
                    if not dish:
                        item.status = 'failed'
                        item.updated_at = datetime.utcnow()
                        db.session.commit()
                        failed += 1
                        continue
                    
                    # Проверяем, не скачан ли уже URL
                    if self._is_url_downloaded(item.image_url):
                        item.status = 'skipped'
                        item.updated_at = datetime.utcnow()
                        db.session.commit()
                        skipped += 1
                        logger.debug(f"URL уже скачан, пропускаем: {item.image_url}")
                        continue
                    
                    logger.info(f"Загружаем изображение из очереди: {item.image_url}")
                    
                    # Загружаем изображение
                    image_filename = self._download_image(item.image_url, dish.name)
                    
                    if image_filename:
                        # Обновляем блюдо
                        dish.image = image_filename
                        item.status = 'completed'
                        item.updated_at = datetime.utcnow()
                        db.session.commit()
                        downloaded += 1
                        logger.info(f"Изображение успешно загружено: {image_filename}")
                    else:
                        item.status = 'failed'
                        item.retry_count += 1
                        item.updated_at = datetime.utcnow()
                        db.session.commit()
                        failed += 1
                        logger.warning(f"Не удалось загрузить изображение: {item.image_url}")
                    
                    # Пауза между загрузками
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки задачи очереди {item.id}: {e}")
                    try:
                        item.status = 'failed'
                        item.retry_count += 1
                        item.updated_at = datetime.utcnow()
                        db.session.commit()
                    except:
                        pass
                    failed += 1
            
            return downloaded, failed, skipped
            
        except Exception as e:
            logger.error(f"Ошибка обработки очереди: {e}")
            return 0, 0, 0
    
    def _cleanup_image_queue(self):
        """Очищает очередь от старых и завершенных задач"""
        try:
            # Удаляем задачи, которые успешно завершены более 1 дня назад
            from datetime import datetime, timedelta
            day_ago = datetime.utcnow() - timedelta(days=1)
            
            completed_items = ImageQueue.query.filter(
                ImageQueue.status == 'completed',
                ImageQueue.updated_at < day_ago
            ).all()
            
            deleted_count = 0
            for item in completed_items:
                db.session.delete(item)
                deleted_count += 1
            
            # Удаляем задачи, которые неудачны и уже превысили лимит попыток
            failed_items = ImageQueue.query.filter(
                ImageQueue.status == 'failed',
                ImageQueue.retry_count >= 3,
                ImageQueue.updated_at < day_ago
            ).all()
            
            for item in failed_items:
                db.session.delete(item)
                deleted_count += 1
            
            db.session.commit()
            
            if deleted_count > 0:
                logger.info(f"Очищено {deleted_count} старых задач из очереди")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки очереди: {e}")
            db.session.rollback()
            return 0
    
    def _download_image(self, url, dish_name=None):
        """Скачивает изображение и сохраняет локально"""
        try:
            if not url:
                logger.debug(f"Пустой URL изображения для блюда: {dish_name}")
                return None
            
            # Проверяем, не скачивали ли уже этот URL
            if self._is_url_downloaded(url):
                logger.debug(f"URL уже был скачан или помечен как ошибочный: {url}")
                return self._get_image_filename_from_url(url)
            
            # Пропускаем placeholder изображения
            if any(x in url.lower() for x in ['placeholder', 'nophoto', 'default', 'no-image', 'noimage']):
                logger.debug(f"Пропускаем placeholder: {url}")
                self.failed_urls.add(url)
                return None
            
            logger.info(f"Загружаем изображение: {url}")
            
            # Ограничиваем размер загружаемых изображений и время загрузки
            response = requests.get(url, headers=self.headers, timeout=10, stream=True)
            response.raise_for_status()
            
            # Проверяем Content-Type
            content_type = response.headers.get('content-type', '').lower()
            if not any(img_type in content_type for img_type in ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']):
                logger.warning(f"URL не является изображением или неверный тип: {content_type}")
                self.failed_urls.add(url)
                return None
            
            # Ограничиваем размер файла (макс 500KB для Render)
            content_length = int(response.headers.get('content-length', 0))
            if content_length > 500 * 1024:  # 500KB
                logger.warning(f"Изображение слишком большое: {content_length} bytes")
                self.failed_urls.add(url)
                return None
            
            # Генерируем имя файла
            image_filename = self._get_image_filename_from_url(url)
            if not image_filename:
                self.failed_urls.add(url)
                return None
            
            # Определяем путь для сохранения
            static_path = Path('app/static/images')
            
            # Проверяем существование директории, создаем если нужно
            try:
                static_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Не удалось создать директорию {static_path}: {e}")
                self.failed_urls.add(url)
                return None
            
            file_path = static_path / image_filename
            
            # Сохраняем файл
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Проверяем размер файла
            if not file_path.exists() or file_path.stat().st_size == 0:
                logger.warning(f"Пустой файл изображения: {image_filename}")
                try:
                    if file_path.exists():
                        file_path.unlink()
                except:
                    pass
                self.failed_urls.add(url)
                return None
            
            # Проверяем, является ли файл валидным изображением
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    img.verify()  # Проверяем целостность файла
            except Exception as e:
                logger.warning(f"Некорректный файл изображения {image_filename}: {e}")
                try:
                    file_path.unlink()
                except:
                    pass
                self.failed_urls.add(url)
                return None
            
            # Добавляем в кэш скачанных изображений
            self.downloaded_urls.add(image_filename)
            
            logger.info(f"Изображение сохранено: {image_filename} ({file_path.stat().st_size} bytes)")
            return image_filename
            
        except requests.exceptions.Timeout:
            logger.warning(f"Таймаут при загрузке изображения: {url}")
            self.failed_urls.add(url)
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка загрузки изображения {url}: {e}")
            self.failed_urls.add(url)
            return None
        except Exception as e:
            logger.warning(f"Ошибка сохранения изображения {url}: {e}")
            if url not in self.failed_urls:
                self.failed_urls.add(url)
            return None
    
    def parse_all_menu(self):
        """Парсит все меню ресторана"""
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
                
                # Задержка между запросами
                time.sleep(0.5)
            
            # Удаляем дубликаты по названию и цене
            unique_dishes = []
            seen_combinations = set()
            
            for dish in all_dishes:
                key = f"{dish['name'].lower()}_{dish['price']}"
                if key not in seen_combinations:
                    seen_combinations.add(key)
                    unique_dishes.append(dish)
            
            # Фильтруем блюда с ценой > 0 (дополнительная проверка)
            filtered_dishes = [d for d in unique_dishes if d['price'] > 0]
            
            if len(filtered_dishes) < len(unique_dishes):
                logger.info(f"Отфильтровано {len(unique_dishes) - len(filtered_dishes)} блюд с нулевой ценой")
            
            logger.info(f"Уникальных блюд после фильтрации: {len(filtered_dishes)}")
            return filtered_dishes
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге всего меню: {e}")
            return []
    
    def save_to_database(self, dishes):
        """Сохраняет спарсенные блюда в базу данных и добавляет URL в очередь"""
        try:
            category_map = {}
            added_count = 0
            skipped_count = 0
            price_zero_count = 0
            queue_added = 0
            
            for dish_data in dishes:
                # Проверяем цену еще раз перед сохранением
                if dish_data['price'] <= 0:
                    price_zero_count += 1
                    continue
                
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
                    dish = Dish(
                        name=dish_data['name'],
                        description=dish_data['description'],
                        price=dish_data['price'],
                        category_id=category.id,
                        is_available=True,
                        image=None  # Изображение будет загружено отдельно
                    )
                    db.session.add(dish)
                    db.session.flush()  # Получаем ID блюда
                    added_count += 1
                    
                    # Если есть URL изображения, добавляем в очередь
                    if dish_data.get('image_url'):
                        self._add_to_image_queue(dish.id, dish_data['image_url'])
                        queue_added += 1
                else:
                    # Если блюдо уже существует, но нет изображения и есть URL, добавляем в очередь
                    if not existing_dish.image and dish_data.get('image_url'):
                        # Проверяем, нет ли уже этого URL в очереди
                        existing_queue = ImageQueue.query.filter_by(
                            dish_id=existing_dish.id,
                            image_url=dish_data['image_url']
                        ).first()
                        
                        if not existing_queue:
                            self._add_to_image_queue(existing_dish.id, dish_data['image_url'])
                            queue_added += 1
                    
                    skipped_count += 1
            
            db.session.commit()
            
            if price_zero_count > 0:
                logger.info(f"Пропущено {price_zero_count} блюд с нулевой ценой при сохранении в БД")
            
            logger.info(f"Сохранено {added_count} блюд, пропущено {skipped_count} дубликатов, добавлено {queue_added} URL в очередь")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Ошибка сохранения в базу: {e}")
            return False
    
    def process_image_queue(self, limit=None, cleanup=True):
        """Обрабатывает очередь изображений"""
        try:
            # Сначала очищаем старые задачи, если нужно
            if cleanup:
                self._cleanup_image_queue()
            
            # Обрабатываем очередь
            downloaded, failed, skipped = self._process_image_queue(limit)
            
            return {
                'downloaded': downloaded,
                'failed': failed,
                'skipped': skipped,
                'total': downloaded + failed + skipped
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки очереди изображений: {e}")
            return {
                'downloaded': 0,
                'failed': 0,
                'skipped': 0,
                'total': 0
            }
    
    def get_queue_stats(self):
        """Получает статистику очереди"""
        try:
            total = ImageQueue.query.count()
            pending = ImageQueue.query.filter_by(status='pending').count()
            downloading = ImageQueue.query.filter_by(status='downloading').count()
            completed = ImageQueue.query.filter_by(status='completed').count()
            failed = ImageQueue.query.filter_by(status='failed').count()
            skipped = ImageQueue.query.filter_by(status='skipped').count()
            
            return {
                'total': total,
                'pending': pending,
                'downloading': downloading,
                'completed': completed,
                'failed': failed,
                'skipped': skipped
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики очереди: {e}")
            return {}

def parse_nsm_menu():
    """Основная функция для парсинга меню"""
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
    """Парсит и сохраняет меню в БД"""
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

def process_image_queue(limit=5, cleanup=True):
    """Обрабатывает очередь изображений"""
    parser = NSMParser()
    
    logger.info(f"Начинаю обработку очереди изображений (максимум {limit})...")
    result = parser.process_image_queue(limit=limit, cleanup=cleanup)
    
    if result['total'] > 0:
        logger.info(f"✅ Обработано {result['total']} задач: {result['downloaded']} загружено, {result['failed']} ошибок, {result['skipped']} пропущено")
        return result
    else:
        logger.info("❌ В очереди нет задач для обработки")
        return result

def get_queue_stats():
    """Получает статистику очереди"""
    parser = NSMParser()
    return parser.get_queue_stats()

def clear_image_queue():
    """Очищает всю очередь изображений"""
    try:
        deleted_count = ImageQueue.query.delete()
        db.session.commit()
        logger.info(f"✅ Очередь изображений очищена: удалено {deleted_count} задач")
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка очистки очереди: {e}")
        db.session.rollback()
        return 0

def update_category_images_from_dishes():
    """Обновляет изображения категорий на основе первого блюда в категории"""
    try:
        categories = Category.query.all()
        updated_count = 0
        
        for category in categories:
            # Находим первое блюдо в категории с изображением
            first_dish_with_image = Dish.query.filter_by(
                category_id=category.id
            ).filter(
                Dish.image.isnot(None),
                Dish.image != '',
                Dish.image != 'default.jpg'
            ).first()
            
            if first_dish_with_image and first_dish_with_image.image:
                # Обновляем изображение категории
                if category.image != first_dish_with_image.image:
                    category.image = first_dish_with_image.image
                    updated_count += 1
                    logger.info(f"Обновлено изображение для категории {category.name}: {first_dish_with_image.image}")
        
        db.session.commit()
        logger.info(f"✅ Обновлено {updated_count} изображений категорий")
        return updated_count
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Ошибка обновления изображений категорий: {e}")
        return 0

def update_all_category_images():
    """Основная функция для обновления всех изображений категорий"""
    updated = update_category_images_from_dishes()
    return updated