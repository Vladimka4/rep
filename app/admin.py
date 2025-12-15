from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from .parsers.nsm_parser import NSMParser  # Добавьте эту строку

admin = Blueprint('admin', __name__, url_prefix='/admin')

@admin.route('/parse-nsm', methods=['GET'])
@login_required
def parse_nsm():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    return render_template('admin/parse_nsm.html')

@admin.route('/parse-nsm-action', methods=['POST'])
@login_required
def parse_nsm_action():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('main.index'))
    
    base_url = request.form.get('base_url', 'https://nsm-22.ru/')
    specific_section = request.form.get('specific_section')
    
    parser = NSMParser(base_url)
    
    if specific_section:
        # Парсим конкретный раздел
        section_name = specific_section.split('/')[-2].replace('-', ' ').title()
        dishes = parser.parse_section(specific_section, section_name)
        
        if dishes:
            parser.save_to_database(dishes)
            flash(f'Успешно спарсено {len(dishes)} блюд из раздела "{section_name}"', 'success')
        else:
            flash('Не удалось получить блюда из указанного раздела', 'danger')
    else:
        # Парсим весь сайт
        dishes = parser.parse_all_menu()
        
        if dishes:
            parser.save_to_database(dishes)
            flash(f'Успешно спарсено {len(dishes)} блюд со всего сайта', 'success')
        else:
            flash('Не удалось получить меню', 'danger')
    
    return redirect(url_for('admin.parse_nsm'))