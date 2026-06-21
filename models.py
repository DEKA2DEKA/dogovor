"""Модели данных для монитора договоров.

Определяет модель Contract, а также структуру разделов и шагов
жизненного цикла договора.

Версия программы: 1.0.0
Версия файла: 2.0.1
"""

import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

SECTIONS_ORDER = ['conclusion', 'execution', 'modification', 'storage', 'archive']

NEXT_SECTION = {
    'conclusion': 'execution',
    'execution': 'modification',
    'modification': 'storage',
    'storage': 'archive',
    'archive': None,
}

PREV_SECTION = {
    'execution': 'conclusion',
    'modification': 'execution',
    'storage': 'modification',
    'archive': 'storage',
    'conclusion': None,
}

SECTIONS = {
    'conclusion': {
        'label': 'Заключение',
        'steps': ['received', 'processing', 'approval', 'revision', 'signing', 'sent'],
        'step_labels': {
            'received': 'Получен',
            'processing': 'Оформление',
            'approval': 'Согласование',
            'revision': 'Корректировка',
            'signing': 'Подписание руководителем',
            'sent': 'Направление контрагенту',
        },
        'step_colors': {
            'received': '#4A90D9',
            'processing': '#00B4D8',
            'approval': '#F4A261',
            'revision': '#E76F51',
            'signing': '#9B5DE5',
            'sent': '#6C63FF',
        },
    },
    'execution': {
        'label': 'Исполнение',
        'steps': ['contract_letter', 'in_progress', 'completed'],
        'step_labels': {
            'contract_letter': 'Договорное письмо',
            'in_progress': 'В процессе исполнения',
            'completed': 'Исполнение завершено',
        },
        'step_colors': {
            'contract_letter': '#20B2AA',
            'in_progress': '#3CB371',
            'completed': '#2E8B57',
        },
    },
    'modification': {
        'label': 'Изменение',
        'steps': ['received', 'processing', 'approval', 'revision', 'signing', 'sent'],
        'step_labels': {
            'received': 'ДС/письмо получено',
            'processing': 'Оформление ДС',
            'approval': 'Согласование',
            'revision': 'Корректировка',
            'signing': 'Подписание руководителем',
            'sent': 'Направление контрагенту',
        },
        'step_colors': {
            'received': '#E67E22',
            'processing': '#D35400',
            'approval': '#E74C3C',
            'revision': '#C0392B',
            'signing': '#8E44AD',
            'sent': '#6C63FF',
        },
    },
    'storage': {
        'label': 'Хранение',
        'steps': ['pending', 'stored'],
        'step_labels': {
            'pending': 'Ожидает сдачи',
            'stored': 'На хранении',
        },
        'step_colors': {
            'pending': '#95A5A6',
            'stored': '#7F8C8D',
        },
    },
    'archive': {
        'label': 'Архив',
        'steps': ['pending_destruction', 'destroyed'],
        'step_labels': {
            'pending_destruction': 'К уничтожению',
            'destroyed': 'Уничтожен',
        },
        'step_colors': {
            'pending_destruction': '#34495E',
            'destroyed': '#2C3B40',
        },
    },
}


def get_section(section_key):
    return SECTIONS.get(section_key)


def get_next_section_key(section_key):
    return NEXT_SECTION.get(section_key)


def get_prev_section_key(section_key):
    return PREV_SECTION.get(section_key)


def get_display_columns(section_key):
    """Return list of (step_key, label, color) for kanban columns including virtual ones."""
    sec = get_section(section_key)
    if not sec:
        return []
    columns = [('__incoming__', 'Входящие', '#6c757d')]
    for step in sec['steps']:
        columns.append((step, sec['step_labels'].get(step, step), sec['step_colors'].get(step, '#6c757d')))
    next_key = get_next_section_key(section_key)
    if next_key and next_key in SECTIONS:
        nsec = SECTIONS[next_key]
        first_step = nsec['steps'][0]
        label = f'→ {nsec["step_labels"].get(first_step, first_step)}'
        columns.append((f'__next__{first_step}', label, nsec['step_colors'].get(first_step, '#6c757d')))
    return columns


def default_section_steps():
    return json.dumps({'conclusion': 'received'})


def default_sections():
    return json.dumps(['conclusion'])


class News(db.Model):
    __tablename__ = 'news'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    body = db.Column(db.Text, nullable=True)
    tag = db.Column(db.String(100), nullable=True)
    tag_color = db.Column(db.String(20), default='#6c757d')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date or '',
            'title': self.title,
            'body': self.body or '',
            'tag': self.tag or '',
            'tag_color': self.tag_color or '#6c757d',
            'is_active': self.is_active,
        }


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(100), nullable=True)
    name = db.Column(db.String(300), nullable=True)
    counterparty = db.Column(db.String(300), nullable=True)
    subject = db.Column(db.String(500), nullable=True)
    amount = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), default='received')
    responsible = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    sections = db.Column(db.Text, default=default_sections)
    section_steps = db.Column(db.Text, default=default_section_steps)
    contract_type = db.Column(db.String(20), default='main')
    parent_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True)

    children = db.relationship(
        'Contract', backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic', foreign_keys=[parent_id]
    )

    received_date = db.Column(db.DateTime, nullable=True)
    processing_date = db.Column(db.DateTime, nullable=True)
    approval_date = db.Column(db.DateTime, nullable=True)
    revision_date = db.Column(db.DateTime, nullable=True)
    signing_date = db.Column(db.DateTime, nullable=True)
    sent_date = db.Column(db.DateTime, nullable=True)
    archive_date = db.Column(db.DateTime, nullable=True)
    destroyed_date = db.Column(db.DateTime, nullable=True)
    sort_order = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_sections_list(self):
        try:
            return json.loads(self.sections) if self.sections else ['conclusion']
        except (json.JSONDecodeError, TypeError):
            return ['conclusion']

    def get_section_steps_dict(self):
        try:
            return json.loads(self.section_steps) if self.section_steps else {'conclusion': 'received'}
        except (json.JSONDecodeError, TypeError):
            return {'conclusion': 'received'}

    def get_step_label(self, section_key):
        steps = self.get_section_steps_dict()
        step = steps.get(section_key)
        sec = get_section(section_key)
        if sec and step:
            return sec['step_labels'].get(step, step)
        return '—'

    def to_dict(self):
        secs = self.get_sections_list()
        steps = self.get_section_steps_dict()
        children_list = [c.to_dict_brief() for c in self.children.all()]

        return {
            'id': self.id,
            'number': self.number or '',
            'name': self.name or '',
            'counterparty': self.counterparty or '',
            'subject': self.subject or '',
            'amount': self.amount or 0,
            'status': self.status,
            'status_display': self.get_step_label(secs[0]) if secs else '—',
            'responsible': self.responsible or '',
            'notes': self.notes or '',
            'sections': secs,
            'section_steps': steps,
            'sort_order': self.sort_order or 0,
            'contract_type': self.contract_type or 'main',
            'parent_id': self.parent_id,
            'children': children_list,
            'received_date': self.received_date.isoformat() if self.received_date else '',
            'processing_date': self.processing_date.isoformat() if self.processing_date else '',
            'approval_date': self.approval_date.isoformat() if self.approval_date else '',
            'revision_date': self.revision_date.isoformat() if self.revision_date else '',
            'signing_date': self.signing_date.isoformat() if self.signing_date else '',
            'sent_date': self.sent_date.isoformat() if self.sent_date else '',
            'archive_date': self.archive_date.isoformat() if self.archive_date else '',
            'destroyed_date': self.destroyed_date.isoformat() if self.destroyed_date else '',
        }

    def to_dict_brief(self):
        secs = self.get_sections_list()
        steps = self.get_section_steps_dict()
        return {
            'id': self.id,
            'number': self.number or '',
            'name': self.name or '',
            'counterparty': self.counterparty or '',
            'amount': self.amount or 0,
            'sections': secs,
            'section_steps': steps,
            'contract_type': self.contract_type or 'main',
            'sort_order': self.sort_order or 0,
        }
