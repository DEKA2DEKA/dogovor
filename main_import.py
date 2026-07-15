import os
import pandas as pd
import numpy as np
from datetime import datetime
from models import db, MainContract


MAIN_COLUMNS = [
    'sequence_number', 'customer', 'contract_number', 'object_work',
    'contract_deadline', 'work_start_date', 'work_end_date',
    'completed_volume', 'labor_plan', 'labor_fact', 'mastered_percent',
    'cost_no_vat', 'cost_with_vat', 'advance_plan', 'advance_fact',
    'zip_plan', 'zip_fact', 'tzr_plan', 'tzr_fact',
    'travel_plan', 'travel_fact', 'sub_plan', 'sub_fact',
    'total_protocol', 'balance_ds_total', 'balance_from_advance',
    'balance_from_contract', 'ds_transferred', 'ds_remaining',
    'correspondence', 'notes', 'bank', 'invoice_status', 'invoice',
    'igk', 'government_contract', 'nomenclature_1c',
]

MAIN_RUSSIAN = {
    'Номер п/п': 'sequence_number',
    'Закзчик': 'customer',
    'Номер договора_ДС': 'contract_number',
    'Объект, работа': 'object_work',
    'Срок по договору': 'contract_deadline',
    'Дата_начала_работ': 'work_start_date',
    'Дата_окончания_работ': 'work_end_date',
    'Выполненный объем': 'completed_volume',
    'Трудоемкость_план': 'labor_plan',
    'Трудоемкость факт': 'labor_fact',
    'Освоено в процентах': 'mastered_percent',
    'Стоимость без НДС': 'cost_no_vat',
    'Стоимость с НДС': 'cost_with_vat',
    'Аванс по договору': 'advance_plan',
    'Аванс факт': 'advance_fact',
    'Затраты ЗИП план': 'zip_plan',
    'Затраты ЗИП факт': 'zip_fact',
    'ТЗР план': 'tzr_plan',
    'ТЗР факт': 'tzr_fact',
    'Командировки_план': 'travel_plan',
    'Командировки факт': 'travel_fact',
    'Затраты на суб_план': 'sub_plan',
    'Затраты на суб факт': 'sub_fact',
    'Итого протокол': 'total_protocol',
    'Баланс_ДС_всего': 'balance_ds_total',
    'Баланс_от аванса': 'balance_from_advance',
    'Баланс от договора': 'balance_from_contract',
    'ДС переведено по окрасчету': 'ds_transferred',
    'Остаток ДС по окрасчету': 'ds_remaining',
    'Переписка': 'correspondence',
    'Примечания': 'notes',
    'Банк': 'bank',
    'Статус о_счета': 'invoice_status',
    'о_счет': 'invoice',
    'ИГК': 'igk',
    'Госконтракт': 'government_contract',
    'Номенклатура_1с': 'nomenclature_1c',
}

NUMERIC_FIELDS = {
    'completed_volume', 'labor_plan', 'labor_fact', 'mastered_percent',
    'cost_no_vat', 'cost_with_vat', 'advance_plan', 'advance_fact',
    'zip_plan', 'zip_fact', 'tzr_plan', 'tzr_fact',
    'travel_plan', 'travel_fact', 'sub_plan', 'sub_fact',
    'total_protocol', 'balance_ds_total', 'balance_from_advance',
    'balance_from_contract', 'ds_transferred', 'ds_remaining',
}

STATUS_MAP = {
    'Исполняемые': 'executing',
    'Закрытые': 'closed',
    'ЦТОСО': 'ctoso',
}

REGION_MAP = {
    'Мурманск': 'Мурманск',
    'ДВ': 'ДВ',
    'ЦТОСО': 'ЦТОСО',
}


def to_num(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s == '-':
        return None
    try:
        return float(s.replace(',', '.').replace(' ', ''))
    except (ValueError, TypeError):
        return None


def to_str(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    s = str(val).strip()
    if not s or s == '-':
        return None
    return s


def fix_quotes(val):
    if not val or not isinstance(val, str):
        return val
    return val.replace('«', '"').replace('»', '"').replace('"', '"').replace('"', '"')


def read_main_sheet(filepath, sheet_name, header_skip=8):
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=None, dtype=str)
    if df.empty:
        return None
    df = df.iloc[header_skip:]
    ncols = len(df.columns)
    names = MAIN_COLUMNS[:ncols] if ncols <= len(MAIN_COLUMNS) else MAIN_COLUMNS + [f'extra_{i}' for i in range(ncols - len(MAIN_COLUMNS))]
    df.columns = names
    existing = [c for c in MAIN_COLUMNS if c in df.columns]
    for c in MAIN_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[MAIN_COLUMNS].copy()
    df = df.dropna(how='all')
    return df


def validate_sheet(df, sheet_name, file_name):
    errors = []
    for idx, row in df.iterrows():
        row_num = idx + 9
        for col in NUMERIC_FIELDS:
            val = row.get(col)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                continue
            s = str(val).strip()
            if not s or s == '-':
                continue
            try:
                float(s.replace(',', '.').replace(' ', ''))
            except (ValueError, TypeError):
                errors.append({
                    'file': file_name,
                    'sheet': sheet_name,
                    'row': row_num,
                    'column': col,
                    'value': str(val)[:50],
                    'message': f'Невозможно преобразовать в число: "{str(val)[:50]}"',
                })
    return errors


def import_main_contracts(filepath, region, batch_id, skip_validation=False):
    xl = pd.ExcelFile(filepath)
    sheet_map = {}
    for name in xl.sheet_names:
        lower = name.lower().strip()
        if 'исполн' in lower:
            sheet_map['executing'] = name
        elif 'закрыт' in lower:
            sheet_map['closed'] = name
        elif 'цтосо' in lower:
            sheet_map['ctoso'] = name

    all_rows = []
    all_errors = []

    def parse_row_record(row):
        record = {}
        for col in MAIN_COLUMNS:
            record[col] = row.get(col)
        for nf in NUMERIC_FIELDS:
            record[nf] = to_num(record.get(nf))
        for sf in ('sequence_number', 'customer', 'contract_number', 'object_work',
                   'correspondence', 'notes', 'bank', 'invoice_status', 'invoice',
                   'igk', 'government_contract', 'nomenclature_1c'):
            record[sf] = fix_quotes(to_str(record.get(sf)))
        for dfld in ('contract_deadline', 'work_start_date', 'work_end_date'):
            record[dfld] = to_str(record.get(dfld))
        return record

    def is_contract_start(row):
        seq = to_str(row.get('sequence_number'))
        cust = to_str(row.get('customer'))
        return bool(seq or cust)

    for status_key, sheet_name in sheet_map.items():
        df = read_main_sheet(filepath, sheet_name)
        if df is None or df.empty:
            continue
        if not skip_validation:
            errs = validate_sheet(df, sheet_name, os.path.basename(filepath))
            all_errors.extend(errs)

        current_contract_idx = len(all_rows)
        for _, row in df.iterrows():
            record = parse_row_record(row)
            record['status'] = status_key
            record['region'] = region
            record['import_batch'] = batch_id

            if is_contract_start(row):
                record['parent_id'] = None
                all_rows.append(record)
                current_contract_idx = len(all_rows) - 1
            else:
                record['parent_id'] = current_contract_idx
                for cp in ('sequence_number', 'customer', 'igk',
                           'government_contract', 'nomenclature_1c',
                           'correspondence', 'bank', 'invoice_status', 'invoice'):
                    if cp not in record or not record.get(cp):
                        record.pop(cp, None)
                all_rows.append(record)

    return all_rows, all_errors


def import_main_file(filepath, region_label, batch_id, skip_validation=False):
    region = REGION_MAP.get(region_label, region_label)
    return import_main_contracts(filepath, region, batch_id, skip_validation=skip_validation)


def merge_and_save(rows, batch_id):
    id_map = {}
    saved = []
    for i, r in enumerate(rows):
        r['_idx'] = i
        parent_idx = r.pop('parent_id', None)
        mc = MainContract(**{k: v for k, v in r.items() if k != '_idx'})
        db.session.add(mc)
        db.session.flush()
        id_map[i] = mc.id
        if parent_idx is not None and parent_idx in id_map:
            mc.parent_id = id_map[parent_idx]
        saved.append(mc)
    db.session.commit()
    return len(saved)
