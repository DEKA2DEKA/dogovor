"""Модели данных для монитора договоров.

Определяет модель Contract и константы статусов жизненного цикла
договора от получения до уничтожения.

Версия: 1.0.0
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

STATUSES = {
    'received': 'Получен',
    'processing': 'Оформление',
    'approval': 'Согласование',
    'revision': 'Корректировка',
    'signing': 'Подписание руководителем',
    'sent': 'Направление контрагенту',
    'archive': 'Архив',
    'destroyed': 'Уничтожен',
}

STATUS_ORDER = {
    'received': 0,
    'processing': 1,
    'approval': 2,
    'revision': 3,
    'signing': 4,
    'sent': 5,
    'archive': 6,
    'destroyed': 7,
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
    received_date = db.Column(db.DateTime, nullable=True)
    processing_date = db.Column(db.DateTime, nullable=True)
    approval_date = db.Column(db.DateTime, nullable=True)
    revision_date = db.Column(db.DateTime, nullable=True)
    signing_date = db.Column(db.DateTime, nullable=True)
    sent_date = db.Column(db.DateTime, nullable=True)
    archive_date = db.Column(db.DateTime, nullable=True)
    destroyed_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'number': self.number or '',
            'name': self.name or '',
            'counterparty': self.counterparty or '',
            'subject': self.subject or '',
            'amount': self.amount or 0,
            'status': self.status,
            'status_display': STATUSES.get(self.status, self.status),
            'responsible': self.responsible or '',
            'notes': self.notes or '',
            'received_date': self.received_date.isoformat() if self.received_date else '',
            'processing_date': self.processing_date.isoformat() if self.processing_date else '',
            'approval_date': self.approval_date.isoformat() if self.approval_date else '',
            'revision_date': self.revision_date.isoformat() if self.revision_date else '',
            'signing_date': self.signing_date.isoformat() if self.signing_date else '',
            'sent_date': self.sent_date.isoformat() if self.sent_date else '',
            'archive_date': self.archive_date.isoformat() if self.archive_date else '',
            'destroyed_date': self.destroyed_date.isoformat() if self.destroyed_date else '',
        }
