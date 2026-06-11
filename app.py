"""Монитор договоров организации.

Flask-приложение для отслеживания жизненного цикла договоров:
получение, оформление, согласование, подписание, архивирование.

Версия: 1.0.0
"""

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


@app.route('/')
def index():
    contracts = Contract.query.order_by(Contract.created_at.desc()).all()
    board = {key: [] for key in STATUSES}
    for c in contracts:
        board[c.status].append(c.to_dict())
    return render_template('index.html', board=board, statuses=STATUSES,
                           status_colors=STATUS_COLORS)


@app.route('/database')
def database():
    contracts = Contract.query.order_by(Contract.created_at.desc()).all()
    return render_template('database.html', contracts=[c.to_dict() for c in contracts],
                           statuses=STATUSES)


@app.route('/api/contracts')
def api_contracts():
    status = request.args.get('status')
    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    amount_min = request.args.get('amount_min')
    amount_max = request.args.get('amount_max')

    query = Contract.query

    if status and status in STATUSES:
        query = query.filter(Contract.status == status)

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


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
