"""Монитор договоров организации.

Flask-приложение для отслеживания жизненного цикла договоров:
получение, оформление, согласование, подписание, архивирование.

Версия: 1.1.0
"""

import json
import os
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from models import db, Contract, STATUSES, STATUS_ORDER

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dogovor-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dogovor.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

@app.template_filter('format_date')
def format_date_filter(value):
    from datetime import datetime as dt
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    now = dt.now()
    return f'{now.day} {months[now.month]} {now.year} г.'


STATUS_COLORS = {
    'received': '#4A90D9',
    'processing': '#00B4D8',
    'approval': '#F4A261',
    'revision': '#E76F51',
    'signing': '#9B5DE5',
    'sent': '#6C63FF',
    'archive': '#2A9D8F',
    'destroyed': '#6C757D',
}

SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), 'sample_data.json')

SAVED_REPORTS_PATH = os.path.join(os.path.dirname(__file__), 'saved_reports.json')

DEFAULT_REPORTS = [
    {
        "id": "report_active",
        "title": "Активные договоры",
        "description": "Все договоры в работе (кроме архивных и уничтоженных)",
        "icon": "bi-activity",
        "color": "#0d6efd",
        "filters": {"status_neg": ["archive", "destroyed"]}
    },
    {
        "id": "report_approval",
        "title": "На согласовании",
        "description": "Договоры, требующие согласования",
        "icon": "bi-clock-history",
        "color": "#F4A261",
        "filters": {"status": "approval"}
    },
    {
        "id": "report_signing",
        "title": "На подписание",
        "description": "Договоры ожидающие подписания руководителем",
        "icon": "bi-pen",
        "color": "#9B5DE5",
        "filters": {"status": "signing"}
    },
    {
        "id": "report_archive",
        "title": "Архив договоров",
        "description": "Завершённые договоры в архиве",
        "icon": "bi-archive",
        "color": "#2A9D8F",
        "filters": {"status": "archive"}
    },
    {
        "id": "report_large",
        "title": "Крупные договоры",
        "description": "Договоры на сумму свыше 1 000 000 ₽",
        "icon": "bi-cash-stack",
        "color": "#198754",
        "filters": {"amount_min": 1000000}
    },
    {
        "id": "report_month",
        "title": "Договоры за последний месяц",
        "description": "Поступившие за последние 30 дней",
        "icon": "bi-calendar-event",
        "color": "#E76F51",
        "filters": {"period": "month"}
    },
]


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
    for item in data:
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
            received_date=dates['received_date'],
            processing_date=dates['processing_date'],
            approval_date=dates['approval_date'],
            revision_date=dates['revision_date'],
            signing_date=dates['signing_date'],
            sent_date=dates['sent_date'],
            archive_date=dates['archive_date'],
            destroyed_date=dates['destroyed_date'],
        )
        db.session.add(contract)
    db.session.commit()


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
    for _, row in df.iterrows():
        data = {}
        for excel_col, field in col_map.items():
            val = row[excel_col]
            if field == 'amount':
                data[field] = parse_amount(val)
            elif field in ('received_date', 'processing_date', 'approval_date',
                           'revision_date', 'signing_date', 'sent_date',
                           'archive_date', 'destroyed_date'):
                data[field] = parse_date(val)
            elif field == 'status' and val and not pd.isna(val):
                raw = str(val).strip().lower()
                data[field] = STATUS_ALIASES.get(raw, raw)
            else:
                data[field] = str(val).strip() if val and not pd.isna(val) else None

        if not any([data.get('number'), data.get('name'), data.get('counterparty')]):
            continue

        contract = Contract(**data)
        db.session.add(contract)
        imported += 1

    db.session.commit()
    return imported


def apply_filters(query, filters):
    status = filters.get('status')
    status_neg = filters.get('status_neg')
    search = filters.get('search', '').strip()
    date_from = filters.get('date_from')
    date_to = filters.get('date_to')
    amount_min = filters.get('amount_min')
    amount_max = filters.get('amount_max')
    period = filters.get('period')

    if status and status in STATUSES:
        query = query.filter(Contract.status == status)

    if status_neg:
        for s in status_neg:
            query = query.filter(Contract.status != s)

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
        from datetime import timedelta
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


@app.route('/')
def info():
    total = Contract.query.count()
    by_status = {}
    for key in STATUSES:
        by_status[key] = Contract.query.filter(Contract.status == key).count()
    active_count = total - by_status.get('archive', 0) - by_status.get('destroyed', 0)
    total_amount = db.session.query(db.func.sum(Contract.amount)).scalar() or 0
    signing_count = by_status.get('signing', 0) + by_status.get('sent', 0)

    news_items = [
        {
            "date": "10.06.2026",
            "title": "Введена новая форма доверенности руководителя",
            "body": "С 1 июля 2026 года вводится обновлённая форма доверенности "
                    "на подписание договоров. Старые бланки действительны до 01.08.2026.",
            "tag": "Важно",
            "tag_color": "#dc3545"
        },
        {
            "date": "08.06.2026",
            "title": "Новая редакция типового договора поставки",
            "body": "Утверждена редакция №5 типового договора поставки. "
                    "Изменены пункты об ответственности сторон и форс-мажоре.",
            "tag": "Обновление",
            "tag_color": "#0d6efd"
        },
        {
            "date": "05.06.2026",
            "title": "День архива — сшей архивный документ!",
            "body": "Сегодня день архивного работника. Проверьте, все ли "
                    "исполненные договоры сданы в архив. Срок хранения — 5 лет.",
            "tag": "Событие",
            "tag_color": "#198754"
        },
        {
            "date": "01.06.2026",
            "title": "Мотивация дня: порядок в договорах — порядок в делах",
            "body": "Каждый оформленный договор приближает нас к порядку "
                    "в документообороте. Спасибо за вашу работу!",
            "tag": "Мотивация",
            "tag_color": "#6f42c1"
        },
        {
            "date": "28.05.2026",
            "title": "Изменение реквизитов организации",
            "body": "Обратите внимание: с 01.06.2026 изменились банковские "
                    "реквизиты организации. Новые данные внесены в шаблоны договоров.",
            "tag": "Важно",
            "tag_color": "#dc3545"
        },
        {
            "date": "25.05.2026",
            "title": "Скоро: семинар по договорной работе",
            "body": "20 июня состоится семинар «Актуальные вопросы договорной "
                    "работы». Приглашаются все сотрудники бюро.",
            "tag": "Анонс",
            "tag_color": "#F4A261"
        },
    ]

    return render_template(
        'info.html',
        total=total,
        active_count=active_count,
        total_amount=total_amount,
        signing_count=signing_count,
        by_status=by_status,
        news_items=news_items,
        statuses=STATUSES,
        status_colors=STATUS_COLORS,
    )


@app.route('/board')
def board():
    contracts = Contract.query.order_by(Contract.created_at.desc()).all()
    board_data = {key: [] for key in STATUSES}
    for c in contracts:
        board_data[c.status].append(c.to_dict())
    return render_template('index.html', board=board_data, statuses=STATUSES,
                           status_colors=STATUS_COLORS)


@app.route('/database')
def database():
    contracts = Contract.query.order_by(Contract.created_at.desc()).all()
    return render_template('database.html', contracts=[c.to_dict() for c in contracts],
                           statuses=STATUSES)


@app.route('/reports')
def reports():
    saved = load_saved_reports()
    return render_template('reports.html', statuses=STATUSES, saved_reports=saved)


@app.route('/api/contracts')
def api_contracts():
    query = Contract.query
    query = apply_filters(query, request.args)
    contracts = query.order_by(Contract.created_at.desc()).all()
    return jsonify([c.to_dict() for c in contracts])


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
    new_status = data.get('status')
    if new_status not in STATUSES:
        return jsonify({'error': 'Некорректный статус'}), 400

    contract.status = new_status
    date_now = datetime.utcnow()
    date_map = {
        'received': 'received_date',
        'processing': 'processing_date',
        'approval': 'approval_date',
        'revision': 'revision_date',
        'signing': 'signing_date',
        'sent': 'sent_date',
        'archive': 'archive_date',
        'destroyed': 'destroyed_date',
    }
    date_field = date_map.get(new_status)
    if date_field:
        setattr(contract, date_field, date_now)

    db.session.commit()
    return jsonify(contract.to_dict())


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

    db.session.commit()
    return jsonify(contract.to_dict())


@app.route('/api/stats')
def api_stats():
    total = Contract.query.count()
    by_status = {}
    for key in STATUSES:
        by_status[key] = Contract.query.filter(Contract.status == key).count()
    return jsonify({'total': total, 'by_status': by_status})


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


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
        return jsonify({'message': 'Сервер остановлен'})
    return jsonify({'error': 'Не удалось остановить сервер'}), 500


with app.app_context():
    db.create_all()
    load_sample_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
