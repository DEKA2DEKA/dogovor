"""Монитор договоров организации.

Flask-приложение для отслеживания жизненного цикла договоров
по разделам: Заключение, Исполнение, Изменение, Хранение, Архив.

Версия программы: 1.0.0
Версия файла: 3.0.1
"""

import json
import os
import threading
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from models import (db, Contract, News, OrganizationCard, SECTIONS, SECTIONS_ORDER,
                     get_section, get_next_section_key, get_prev_section_key,
                     get_display_columns)

VERSION = "1.1.1"

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dogovor-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dogovor.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['ENVIRONMENT'] = os.environ.get('ENVIRONMENT', 'development')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

@app.context_processor
def inject_globals():
    return dict(VERSION=VERSION, ENVIRONMENT=app.config['ENVIRONMENT'])

SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), 'sample_data.json')
SAVED_REPORTS_PATH = os.path.join(os.path.dirname(__file__), 'saved_reports.json')

DEFAULT_REPORTS = [
    {
        "id": "report_active",
        "title": "Все активные",
        "description": "Договоры в Заключении и Исполнении",
        "icon": "bi-activity",
        "color": "#0d6efd",
        "filters": {"sections": ["conclusion", "execution"]}
    },
    {
        "id": "report_conclusion",
        "title": "Заключение",
        "description": "На этапе заключения",
        "icon": "bi-file-text",
        "color": "#4A90D9",
        "filters": {"sections": ["conclusion"]}
    },
    {
        "id": "report_modification",
        "title": "Изменения (ДС)",
        "description": "Допсоглашения в работе",
        "icon": "bi-pen",
        "color": "#E67E22",
        "filters": {"sections": ["modification"]}
    },
    {
        "id": "report_storage",
        "title": "На хранении",
        "description": "Договоры в архивохранилище",
        "icon": "bi-archive",
        "color": "#2A9D8F",
        "filters": {"sections": ["storage"]}
    },
    {
        "id": "report_large",
        "title": "Крупные (>1 млн)",
        "description": "Договоры от 1 000 000 ₽",
        "icon": "bi-cash-stack",
        "color": "#198754",
        "filters": {"amount_min": 1000000}
    },
]


@app.template_filter('format_date')
def format_date_filter(value):
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    now = datetime.now()
    return f'{now.day} {months[now.month]} {now.year} г.'


def load_saved_reports():
    if os.path.exists(SAVED_REPORTS_PATH):
        with open(SAVED_REPORTS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_REPORTS


def save_saved_reports(reports):
    with open(SAVED_REPORTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)


def load_sample_data():
    if not os.path.exists(SAMPLE_DATA_PATH):
        return
    if Contract.query.count() > 0:
        return
    with open(SAMPLE_DATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    parent_map = {}
    for item in data:
        if item.get('parent_number'):
            parent_map[item['number']] = item['parent_number']

    for item in data:
        if item.get('parent_number'):
            continue
        _create_contract_from_dict(item)

    for item in data:
        if item.get('parent_number'):
            parent = Contract.query.filter_by(number=item['parent_number']).first()
            if parent:
                c = _create_contract_from_dict(item)
                c.parent_id = parent.id
                db.session.add(c)
    db.session.commit()


def _create_contract_from_dict(item):
    dates = {}
    for field in ('received_date', 'processing_date', 'approval_date',
                  'revision_date', 'signing_date', 'sent_date',
                  'archive_date', 'destroyed_date'):
        if item.get(field):
            try:
                dates[field] = datetime.fromisoformat(item[field])
            except (ValueError, TypeError):
                dates[field] = None
        else:
            dates[field] = None

    contract = Contract(
        number=item.get('number'),
        name=item.get('name'),
        counterparty=item.get('counterparty'),
        subject=item.get('subject'),
        amount=item.get('amount'),
        status=item.get('status', 'received'),
        responsible=item.get('responsible'),
        notes=item.get('notes'),
        sections=json.dumps(item.get('sections', ['conclusion'])),
        section_steps=json.dumps(item.get('section_steps', {'conclusion': 'received'})),
        contract_type=item.get('contract_type', 'main'),
        sort_order=item.get('sort_order', 0.0),
        received_date=dates['received_date'],
        processing_date=dates['processing_date'],
        approval_date=dates['approval_date'],
        revision_date=dates['revision_date'],
        signing_date=dates['signing_date'],
        sent_date=dates['sent_date'],
        archive_date=dates['archive_date'],
        destroyed_date=dates['destroyed_date'],
    )
    new_str_fields = (
        'registration_number', 'document_date', 'additional_number', 'additional_date',
        'service_section', 'service_subtype', 'brief_subject', 'place_conclusion',
        'place_service', 'initiator', 'government_id', 'payment_form', 'original_status',
        'outgoing_info', 'signatory', 'signatory_doc', 'counterparty_details',
        'electronic_copy', 'prolongation', 'planned_start', 'planned_end',
        'actual_start', 'actual_end', 'validity_period',
        'date_sent_to_sign', 'date_received_signed', 'termination_date',
    )
    for f in new_str_fields:
        if f in item:
            setattr(contract, f, item[f])
    new_num_fields = (
        'prolongation_days', 'monthly_amount', 'amount_no_tax', 'tax_rate',
        'amount_with_tax', 'amount_paid', 'amount_remaining',
    )
    for f in new_num_fields:
        if f in item:
            setattr(contract, f, item[f])
    if 'renewal_required' in item:
        contract.renewal_required = bool(item['renewal_required'])
    db.session.add(contract)
    return contract


def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val
    try:
        return pd.to_datetime(val)
    except Exception:
        return None


def parse_amount(val):
    if pd.isna(val):
        return None
    try:
        return float(str(val).replace(' ', '').replace(',', '.'))
    except Exception:
        return None


COLUMN_MAP = {
    'номер договора': 'number',
    'номер': 'number',
    'наименование': 'name',
    'контрагент': 'counterparty',
    'предмет': 'subject',
    'сумма': 'amount',
    'статус': 'status',
    'ответственный': 'responsible',
    'примечания': 'notes',
    'дата получения': 'received_date',
    'дата оформления': 'processing_date',
    'дата согласования': 'approval_date',
    'дата корректировки': 'revision_date',
    'дата подписания': 'signing_date',
    'дата направления': 'sent_date',
    'дата архивации': 'archive_date',
    'дата уничтожения': 'destroyed_date',
    'номер регистрации': 'registration_number',
    'дата документа': 'document_date',
    'номер дс': 'additional_number',
    'дата дс': 'additional_date',
    'раздел услуг': 'service_section',
    'объект': 'service_subtype',
    'вид работ': 'service_subtype',
    'кратко': 'brief_subject',
    'место заключения': 'place_conclusion',
    'место оказания': 'place_service',
    'инициатор': 'initiator',
    'игк': 'government_id',
    'форма расчета': 'payment_form',
    'статус оригинала': 'original_status',
    'исх': 'outgoing_info',
    'подписант': 'signatory',
    'полномочий': 'signatory_doc',
    'реквизиты': 'counterparty_details',
    'электронная копия': 'electronic_copy',
    'пролонгация': 'prolongation',
    'срок до пролонгации': 'prolongation_days',
    'продление требуется': 'renewal_required',
    'дог.начало': 'planned_start',
    'дог.оконч': 'planned_end',
    'факт.нач': 'actual_start',
    'факт.оконч': 'actual_end',
    'срок действия': 'validity_period',
    'стоимость в мес': 'monthly_amount',
    'без ндс': 'monthly_amount',
    'без налога': 'amount_no_tax',
    'налог %': 'tax_rate',
    'с налогом': 'amount_with_tax',
    'оплачено': 'amount_paid',
    'осталось': 'amount_remaining',
    'отправки оригинала': 'date_sent_to_sign',
    'получения оригинала': 'date_received_signed',
    'расторжения': 'termination_date',
}

STATUS_ALIASES = {
    'получен': 'received',
    'оформление': 'processing',
    'согласование': 'approval',
    'корректировка': 'revision',
    'подписание руководителем': 'signing',
    'подписание': 'signing',
    'направление контрагенту': 'sent',
    'направление': 'sent',
    'архив': 'archive',
    'уничтожен': 'destroyed',
}


def import_excel(filepath):
    df = pd.read_excel(filepath, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]

    col_map = {}
    for col in df.columns:
        for alias, field in COLUMN_MAP.items():
            if alias in col:
                col_map[col] = field
                break

    imported = 0
    numeric_fields = ('amount', 'prolongation_days', 'monthly_amount', 'amount_no_tax',
                      'tax_rate', 'amount_with_tax', 'amount_paid', 'amount_remaining')
    date_fields = ('received_date', 'processing_date', 'approval_date',
                   'revision_date', 'signing_date', 'sent_date',
                   'archive_date', 'destroyed_date')
    bool_fields = ('renewal_required',)

    for _, row in df.iterrows():
        data = {}
        for excel_col, field in col_map.items():
            val = row[excel_col]
            if field in numeric_fields:
                data[field] = parse_amount(val)
            elif field in date_fields:
                data[field] = parse_date(val)
            elif field == 'status' and val and not pd.isna(val):
                raw = str(val).strip().lower()
                data[field] = STATUS_ALIASES.get(raw, raw)
            elif field in bool_fields:
                if val and not pd.isna(val):
                    data[field] = str(val).strip().lower() in ('да', 'yes', 'true', '1', '+')
                else:
                    data[field] = False
            else:
                data[field] = str(val).strip() if val and not pd.isna(val) else None

        if not any([data.get('number'), data.get('name'), data.get('counterparty')]):
            continue

        data['sections'] = json.dumps(['conclusion'])
        data['section_steps'] = json.dumps({'conclusion': data.get('status', 'received')})

        contract = Contract(**data, sort_order=float(imported))
        db.session.add(contract)
        imported += 1

    db.session.commit()
    return imported


def apply_filters(query, filters):
    sections_filter = filters.get('sections')
    status = filters.get('status')
    search = filters.get('search', '').strip()
    date_from = filters.get('date_from')
    date_to = filters.get('date_to')
    amount_min = filters.get('amount_min')
    amount_max = filters.get('amount_max')
    period = filters.get('period')

    if sections_filter:
        parts = sections_filter.split(',')
        for sec in parts:
            sec = sec.strip()
            if sec in SECTIONS:
                like = f'%"{sec}"%'
                query = query.filter(Contract.sections.like(like))

    if status and status in [s for sec in SECTIONS for s in SECTIONS[sec]['steps']]:
        like = f'%"{status}"%'
        query = query.filter(Contract.section_steps.like(like))

    if search:
        like = f'%{search}%'
        query = query.filter(
            or_(
                Contract.number.like(like),
                Contract.name.like(like),
                Contract.counterparty.like(like),
                Contract.subject.like(like),
                Contract.responsible.like(like),
            )
        )

    if date_from:
        try:
            dt = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Contract.received_date >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Contract.received_date <= dt)
        except ValueError:
            pass

    if period == 'month':
        dt = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Contract.received_date >= dt)

    if amount_min:
        try:
            query = query.filter(Contract.amount >= float(amount_min))
        except ValueError:
            pass

    if amount_max:
        try:
            query = query.filter(Contract.amount <= float(amount_max))
        except ValueError:
            pass

    return query


def get_section_stats():
    stats = {}
    for key in SECTIONS_ORDER:
        like = f'%"{key}"%'
        count = Contract.query.filter(Contract.sections.like(like)).count()
        stats[key] = count
    return stats


# --- HTML routes ---

@app.route('/')
def info():
    total = Contract.query.count()
    section_stats = get_section_stats()
    active = section_stats.get('conclusion', 0) + section_stats.get('execution', 0)
    total_amount = db.session.query(db.func.sum(Contract.amount)).scalar() or 0
    in_storage = section_stats.get('storage', 0) + section_stats.get('archive', 0)

    news_items = News.query.filter_by(is_active=True).order_by(News.created_at.desc()).all()

    org_card = OrganizationCard.query.first()
    if not org_card:
        org_card = OrganizationCard(full_name='', short_name='')
        db.session.add(org_card)
        db.session.commit()

    return render_template(
        'info.html',
        total=total,
        active_count=active,
        total_amount=total_amount,
        in_storage=in_storage,
        section_stats=section_stats,
        sections=SECTIONS,
        sections_order=SECTIONS_ORDER,
        news_items=[n.to_dict() for n in news_items],
        org_card=org_card.to_dict(),
    )


@app.route('/board')
def board_view():
    section_stats = get_section_stats()
    return render_template('board.html', sections=SECTIONS,
                           sections_order=SECTIONS_ORDER, stats=section_stats)


@app.route('/board/<section_key>')
def section_detail(section_key):
    if section_key not in SECTIONS:
        return render_template('board.html', sections=SECTIONS,
                               sections_order=SECTIONS_ORDER, stats=get_section_stats())

    sec = get_section(section_key)
    next_key = get_next_section_key(section_key)
    display_columns = get_display_columns(section_key)

    like = f'%"{section_key}"%'
    contracts = Contract.query.filter(Contract.sections.like(like)).order_by(Contract.sort_order).all()

    board_data = {}
    for col_key, _, _ in display_columns:
        board_data[col_key] = []

    for c in contracts:
        steps = c.get_section_steps_dict()
        step = steps.get(section_key, sec['steps'][0])
        if step in board_data:
            board_data[step].append(c.to_dict())
        else:
            board_data.get(sec['steps'][0], []).append(c.to_dict())

    if next_key:
        nsec = get_section(next_key)
        first_step = nsec['steps'][0]
        next_col = f'__next__{first_step}'
        next_like = f'%"{next_key}"%'
        next_contracts = Contract.query.filter(Contract.sections.like(next_like)).order_by(Contract.sort_order).all()
        for c in next_contracts:
            nsteps = c.get_section_steps_dict()
            if nsteps.get(next_key) == first_step:
                board_data.setdefault(next_col, []).append(c.to_dict())

    return render_template('section.html', section_key=section_key,
                           section=sec, board=board_data, all_sections=SECTIONS,
                           sections_order=SECTIONS_ORDER, display_columns=display_columns,
                           next_section_key=next_key,
                           prev_section_key=get_prev_section_key(section_key))


@app.route('/database')
def database():
    contracts = Contract.query.order_by(Contract.created_at.desc()).all()
    return render_template('database.html', contracts=[c.to_dict() for c in contracts],
                           sections=SECTIONS, sections_order=SECTIONS_ORDER)


@app.route('/reports')
def reports():
    saved = load_saved_reports()
    return render_template('reports.html', sections=SECTIONS,
                           sections_order=SECTIONS_ORDER, saved_reports=saved)


# --- API routes ---

@app.route('/api/contracts')
def api_contracts():
    query = Contract.query
    query = apply_filters(query, request.args)
    contracts = query.order_by(Contract.created_at.desc()).all()
    return jsonify([c.to_dict() for c in contracts])


@app.route('/api/contracts/<section_key>')
def api_contracts_by_section(section_key):
    if section_key not in SECTIONS:
        return jsonify([])
    sec = get_section(section_key)
    like = f'%"{section_key}"%'
    query = Contract.query.filter(Contract.sections.like(like))
    query = apply_filters(query, request.args)
    contracts = query.order_by(Contract.created_at.desc()).all()
    board_data = {step: [] for step in sec['steps']}
    for c in contracts:
        steps = c.get_section_steps_dict()
        step = steps.get(section_key, sec['steps'][0])
        if step in board_data:
            board_data[step].append(c.to_dict())
        else:
            board_data[sec['steps'][0]].append(c.to_dict())
    return jsonify(board_data)


@app.route('/api/import', methods=['POST'])
def api_import():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Файл не выбран'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.xlsx', '.xls'):
        return jsonify({'error': 'Поддерживаются только файлы Excel (.xlsx, .xls)'}), 400
    filename = secure_filename(f'import_{datetime.now().strftime("%Y%m%d_%H%M%S")}{ext}')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    try:
        count = import_excel(filepath)
        return jsonify({'message': f'Импортировано {count} договоров', 'count': count})
    except Exception as e:
        return jsonify({'error': f'Ошибка импорта: {str(e)}'}), 500


@app.route('/api/contract/<int:contract_id>/move', methods=['POST'])
def api_move_contract(contract_id):
    contract = db.session.get(Contract, contract_id)
    if not contract:
        return jsonify({'error': 'Договор не найден'}), 404

    data = request.get_json()
    section_key = data.get('section')
    direction = data.get('direction', 'forward')

    if not section_key or section_key not in SECTIONS:
        return jsonify({'error': 'Некорректный раздел'}), 400
    sec = get_section(section_key)

    steps = contract.get_section_steps_dict()
    current_step = steps.get(section_key, sec['steps'][0])

    if direction == 'backward':
        if current_step == '__incoming__':
            return jsonify({'error': 'Это начальная позиция'}), 400
        steps_list = sec['steps']
        if current_step in steps_list:
            idx = steps_list.index(current_step)
            if idx > 0:
                steps[section_key] = steps_list[idx - 1]
            else:
                steps[section_key] = '__incoming__'
        contract.section_steps = json.dumps(steps)
        contract.status = steps.get(section_key, sec['steps'][0])
        new_step = steps.get(section_key)
        if new_step and new_step not in ('__incoming__',) and not new_step.startswith('__next__'):
            like_sec = f'%"{section_key}"%'
            exist = Contract.query.filter(
                Contract.id != contract.id,
                Contract.sections.like(like_sec),
                Contract.section_steps.like(f'%"{new_step}"%'),
            ).count()
            contract.sort_order = float(exist)
        db.session.commit()
        return jsonify(contract.to_dict())

    steps_list = sec['steps']
    next_key = get_next_section_key(section_key)

    # Determine new step
    if current_step == '__incoming__':
        new_step = steps_list[0]
        steps[section_key] = new_step
    elif current_step in steps_list:
        idx = steps_list.index(current_step)
        if idx < len(steps_list) - 1:
            new_step = steps_list[idx + 1]
            steps[section_key] = new_step
        elif next_key:
            nsec = get_section(next_key)
            if next_key not in steps:
                steps[next_key] = '__incoming__'
                contract.sections = json.dumps(
                    list(dict.fromkeys(contract.get_sections_list() + [next_key]))
                )
            new_step = steps.get(section_key)
        else:
            return jsonify({'error': 'Это финальный шаг'}), 400
    else:
        return jsonify({'error': 'Некорректный шаг'}), 400

    contract.section_steps = json.dumps(steps)
    if new_step not in ('__incoming__',) and not new_step.startswith('__next__'):
        like_sec = f'%"{section_key}"%'
        exist = Contract.query.filter(
            Contract.id != contract.id,
            Contract.sections.like(like_sec),
            Contract.section_steps.like(f'%"{new_step}"%'),
        ).count()
        contract.sort_order = float(exist)
    sections = contract.get_sections_list()
    if section_key not in sections:
        sections.append(section_key)
        contract.sections = json.dumps(sections)

    date_now = datetime.utcnow()
    date_map = {
        'conclusion': {'received': 'received_date', 'processing': 'processing_date',
                       'approval': 'approval_date', 'revision': 'revision_date',
                       'signing': 'signing_date', 'sent': 'sent_date'},
        'execution': {},
        'modification': {'received': 'received_date', 'processing': 'processing_date',
                         'approval': 'approval_date', 'revision': 'revision_date',
                         'signing': 'signing_date', 'sent': 'sent_date'},
        'storage': {},
        'archive': {'pending_destruction': None, 'destroyed': 'destroyed_date'},
    }
    field_map = date_map.get(section_key, {})
    date_field = field_map.get(new_step)
    if date_field and not getattr(contract, date_field):
        setattr(contract, date_field, date_now)

    contract.status = steps.get(section_key, sec['steps'][0])
    db.session.commit()
    return jsonify(contract.to_dict())


@app.route('/api/reorder', methods=['POST'])
def api_reorder():
    data = request.get_json()
    section_key = data.get('section')
    step_key = data.get('step')
    contract_ids = data.get('contract_ids', [])

    if not section_key or not step_key:
        return jsonify({'error': 'Некорректные параметры'}), 400

    for i, cid in enumerate(contract_ids):
        contract = db.session.get(Contract, cid)
        if contract:
            contract.sort_order = float(i)
    db.session.commit()
    return jsonify({'message': 'Порядок обновлён'})


@app.route('/api/contract/<int:contract_id>', methods=['DELETE'])
def api_delete_contract(contract_id):
    contract = db.session.get(Contract, contract_id)
    if not contract:
        return jsonify({'error': 'Договор не найден'}), 404
    db.session.delete(contract)
    db.session.commit()
    return jsonify({'message': 'Договор удалён'})


@app.route('/api/contract/<int:contract_id>', methods=['PUT'])
def api_update_contract(contract_id):
    contract = db.session.get(Contract, contract_id)
    if not contract:
        return jsonify({'error': 'Договор не найден'}), 404
    data = request.get_json()
    for field in ('number', 'name', 'counterparty', 'subject', 'amount',
                  'responsible', 'notes'):
        if field in data:
            setattr(contract, field, data[field])
    for date_field in ('received_date', 'processing_date', 'approval_date',
                       'revision_date', 'signing_date', 'sent_date',
                       'archive_date', 'destroyed_date'):
        if date_field in data and data[date_field]:
            try:
                setattr(contract, date_field, datetime.fromisoformat(data[date_field]))
            except (ValueError, TypeError):
                pass
    new_str_fields = (
        'registration_number', 'document_date', 'additional_number', 'additional_date',
        'service_section', 'service_subtype', 'brief_subject', 'place_conclusion',
        'place_service', 'initiator', 'government_id', 'payment_form', 'original_status',
        'outgoing_info', 'signatory', 'signatory_doc', 'counterparty_details',
        'electronic_copy', 'prolongation', 'planned_start', 'planned_end',
        'actual_start', 'actual_end', 'validity_period',
        'date_sent_to_sign', 'date_received_signed', 'termination_date',
    )
    for f in new_str_fields:
        if f in data:
            setattr(contract, f, data[f])
    for num_field in ('prolongation_days', 'monthly_amount', 'amount_no_tax',
                      'tax_rate', 'amount_with_tax', 'amount_paid', 'amount_remaining'):
        if num_field in data:
            try:
                setattr(contract, num_field, float(data[num_field]) if data[num_field] else None)
            except (ValueError, TypeError):
                pass
    if 'renewal_required' in data:
        contract.renewal_required = bool(data['renewal_required'])
    db.session.commit()
    return jsonify(contract.to_dict())


@app.route('/api/stats')
def api_stats():
    total = Contract.query.count()
    section_stats = get_section_stats()
    by_section = {}
    for key in SECTIONS_ORDER:
        like = f'%"{key}"%'
        by_section[key] = Contract.query.filter(Contract.sections.like(like)).count()
    total_amount = db.session.query(db.func.sum(Contract.amount)).scalar() or 0
    return jsonify({
        'total': total,
        'total_amount': total_amount,
        'by_section': section_stats,
    })


@app.route('/api/clear', methods=['POST'])
def api_clear():
    Contract.query.delete()
    db.session.commit()
    return jsonify({'message': 'Все договоры удалены'})


@app.route('/api/reports', methods=['GET'])
def api_get_reports():
    return jsonify(load_saved_reports())


@app.route('/api/reports', methods=['POST'])
def api_save_report():
    data = request.get_json()
    reports = load_saved_reports()
    new_report = {
        "id": f"report_{len(reports) + 1}",
        "title": data.get('title', 'Новый отчёт'),
        "description": data.get('description', ''),
        "icon": "bi-funnel",
        "color": "#6C63FF",
        "filters": data.get('filters', {}),
    }
    reports.append(new_report)
    save_saved_reports(reports)
    return jsonify(new_report)


@app.route('/api/reports/<report_id>', methods=['DELETE'])
def api_delete_report(report_id):
    reports = load_saved_reports()
    reports = [r for r in reports if r['id'] != report_id]
    save_saved_reports(reports)
    return jsonify({'message': 'Отчёт удалён'})


@app.route('/api/contract/<int:contract_id>/additional', methods=['POST'])
def api_add_additional(contract_id):
    parent = db.session.get(Contract, contract_id)
    if not parent:
        return jsonify({'error': 'Договор не найден'}), 404
    data = request.get_json()
    child = Contract(
        number=data.get('number', f'{parent.number}/ДС'),
        name=data.get('name', 'Дополнительное соглашение'),
        counterparty=parent.counterparty,
        subject=data.get('subject', ''),
        amount=data.get('amount', 0),
        status='received',
        sections=json.dumps(['modification']),
        section_steps=json.dumps({'modification': 'received'}),
        contract_type='additional',
        parent_id=parent.id,
        responsible=parent.responsible,
        notes=data.get('notes', ''),
        received_date=datetime.utcnow(),
    )
    db.session.add(child)
    db.session.commit()
    return jsonify(child.to_dict()), 201


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    if app.config['ENVIRONMENT'] == 'production':
        return jsonify({'error': 'Forbidden'}), 403
    threading.Timer(0.5, os._exit, args=[0]).start()
    return jsonify({'message': 'Сервер остановлен'})


# --- Organization Card API ---

@app.route('/api/organization-card', methods=['GET'])
def api_get_organization_card():
    card = OrganizationCard.query.first()
    if not card:
        card = OrganizationCard(full_name='', short_name='')
        db.session.add(card)
        db.session.commit()
    return jsonify(card.to_dict())


@app.route('/api/organization-card', methods=['PUT'])
def api_update_organization_card():
    card = OrganizationCard.query.first()
    if not card:
        card = OrganizationCard()
        db.session.add(card)
    data = request.get_json()
    fields = ('full_name', 'short_name', 'inn', 'kpp', 'ogrn',
              'legal_address', 'actual_address', 'phone', 'email',
              'bank_name', 'bik', 'corr_account', 'current_account', 'director')
    for field in fields:
        if field in data:
            setattr(card, field, data[field])
    db.session.commit()
    return jsonify(card.to_dict())


# --- News API ---

@app.route('/api/news', methods=['GET'])
def api_get_news():
    all_news = News.query.order_by(News.created_at.desc()).all()
    return jsonify([n.to_dict() for n in all_news])


@app.route('/api/news', methods=['POST'])
def api_create_news():
    data = request.get_json()
    item = News(
        date=data.get('date', ''),
        title=data.get('title', 'Без названия'),
        body=data.get('body', ''),
        tag=data.get('tag', ''),
        tag_color=data.get('tag_color', '#6c757d'),
        is_active=data.get('is_active', True),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.route('/api/news/<int:news_id>', methods=['PUT'])
def api_update_news(news_id):
    item = db.session.get(News, news_id)
    if not item:
        return jsonify({'error': 'Новость не найдена'}), 404
    data = request.get_json()
    for field in ('date', 'title', 'body', 'tag', 'tag_color'):
        if field in data:
            setattr(item, field, data[field])
    if 'is_active' in data:
        item.is_active = bool(data['is_active'])
    db.session.commit()
    return jsonify(item.to_dict())


@app.route('/api/news/<int:news_id>', methods=['DELETE'])
def api_delete_news(news_id):
    item = db.session.get(News, news_id)
    if not item:
        return jsonify({'error': 'Новость не найдена'}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Новость удалена'})


def seed_news():
    if News.query.count() > 0:
        return
    samples = [
        {"date": "10.06.2026", "title": "Введена новая форма доверенности руководителя", "body": "С 1 июля 2026 года вводится обновлённая форма доверенности на подписание договоров. Старые бланки действительны до 01.08.2026.", "tag": "Важно", "tag_color": "#dc3545"},
        {"date": "08.06.2026", "title": "Новая редакция типового договора поставки", "body": "Утверждена редакция №5 типового договора поставки. Изменены пункты об ответственности сторон и форс-мажоре.", "tag": "Обновление", "tag_color": "#0d6efd"},
        {"date": "05.06.2026", "title": "День архива — сшей архивный документ!", "body": "Проверьте, все ли исполненные договоры сданы в архив. Срок хранения — 5 лет.", "tag": "Событие", "tag_color": "#198754"},
        {"date": "01.06.2026", "title": "Мотивация дня: порядок в договорах — порядок в делах", "body": "Каждый оформленный договор приближает нас к порядку в документообороте. Спасибо за вашу работу!", "tag": "Мотивация", "tag_color": "#6f42c1"},
        {"date": "28.05.2026", "title": "Изменение реквизитов организации", "body": "Обратите внимание: с 01.06.2026 изменились банковские реквизиты организации. Новые данные внесены в шаблоны договоров.", "tag": "Важно", "tag_color": "#dc3545"},
        {"date": "25.05.2026", "title": "Семинар по договорной работе", "body": "20 июня состоится семинар «Актуальные вопросы договорной работы». Приглашаются все сотрудники бюро.", "tag": "Анонс", "tag_color": "#F4A261"},
    ]
    for s in samples:
        item = News(**s)
        db.session.add(item)
    db.session.commit()


with app.app_context():
    db.create_all()
    load_sample_data()
    seed_news()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
