// Версия программы: 1.0.0 | Версия файла: 1.0.2

let currentContractId = null;

const SECTIONS = {
    conclusion: { label: 'Заключение', steps: ['received', 'processing', 'approval', 'revision', 'signing', 'sent'], step_labels: { received: 'Получен', processing: 'Оформление', approval: 'Согласование', revision: 'Корректировка', signing: 'Подписание руководителем', sent: 'Направление контрагенту' }, step_colors: { received: '#4A90D9', processing: '#00B4D8', approval: '#F4A261', revision: '#E76F51', signing: '#9B5DE5', sent: '#6C63FF' } },
    execution: { label: 'Исполнение', steps: ['contract_letter', 'in_progress', 'completed'], step_labels: { contract_letter: 'Договорное письмо', in_progress: 'В процессе исполнения', completed: 'Исполнение завершено' }, step_colors: { contract_letter: '#20B2AA', in_progress: '#3CB371', completed: '#2E8B57' } },
    modification: { label: 'Изменение', steps: ['received', 'processing', 'approval', 'revision', 'signing', 'sent'], step_labels: { received: 'ДС/письмо получено', processing: 'Оформление ДС', approval: 'Согласование', revision: 'Корректировка', signing: 'Подписание руководителем', sent: 'Направление контрагенту' }, step_colors: { received: '#E67E22', processing: '#D35400', approval: '#E74C3C', revision: '#C0392B', signing: '#8E44AD', sent: '#6C63FF' } },
    storage: { label: 'Хранение', steps: ['pending', 'stored'], step_labels: { pending: 'Ожидает сдачи', stored: 'На хранении' }, step_colors: { pending: '#95A5A6', stored: '#7F8C8D' } },
    archive: { label: 'Архив', steps: ['pending_destruction', 'destroyed'], step_labels: { pending_destruction: 'К уничтожению', destroyed: 'Уничтожен' }, step_colors: { pending_destruction: '#34495E', destroyed: '#2C3B40' } },
};

document.addEventListener('DOMContentLoaded', function () {
    initDragDrop();
    initFileInput();
});

function initDragDrop() {
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) return;
    dropZone.classList.add('active');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
        document.body.addEventListener(event, e => { e.preventDefault(); e.stopPropagation(); });
    });
    ['dragenter', 'dragover'].forEach(event => {
        document.body.addEventListener(event, () => { dropZone.classList.add('dragover'); });
    });
    ['dragleave', 'drop'].forEach(event => {
        document.body.addEventListener(event, () => { dropZone.classList.remove('dragover'); });
    });
    document.body.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFile(files[0]);
    });
}

function initFileInput() {
    const input = document.getElementById('fileInput');
    if (!input) return;
    input.addEventListener('change', e => {
        if (e.target.files.length > 0) handleFile(e.target.files[0]);
    });
}

function handleFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls'].includes(ext)) {
        showImportResult('error', 'Поддерживаются только файлы Excel (.xlsx, .xls)');
        return;
    }
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) return;
    const progressEl = dropZone.querySelector('.drop-zone-progress');
    const textEl = dropZone.querySelector('.drop-zone-text');
    textEl.classList.add('d-none');
    progressEl.classList.remove('d-none');
    const formData = new FormData();
    formData.append('file', file);
    fetch('/api/import', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            progressEl.classList.add('d-none');
            textEl.classList.remove('d-none');
            showImportResult(data.error ? 'error' : 'success', data.error || data.message);
        })
        .catch(() => {
            progressEl.classList.add('d-none');
            textEl.classList.remove('d-none');
            showImportResult('error', 'Ошибка при загрузке файла');
        });
}

function showImportResult(type, message) {
    const modal = new bootstrap.Modal(document.getElementById('importModal'));
    document.getElementById('importResult').innerHTML =
        `<div class="alert alert-${type === 'success' ? 'success' : 'danger'} mb-0">${message}</div>`;
    modal.show();
}

function showContractDetail(id) {
    currentContractId = id;
    const modal = new bootstrap.Modal(document.getElementById('contractModal'));
    document.getElementById('modalTitle').textContent = 'Загрузка...';
    document.getElementById('modalBody').innerHTML =
        '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div></div>';
    modal.show();

    fetch('/api/contracts')
        .then(r => r.json())
        .then(all => {
            const c = all.find(x => x.id === id);
            if (c) renderContractDetail(c);
            else document.getElementById('modalBody').innerHTML = '<div class="alert alert-danger">Договор не найден</div>';
        })
        .catch(() => {
            document.getElementById('modalBody').innerHTML = '<div class="alert alert-danger">Ошибка загрузки</div>';
        });
}

function getPrevStep(sectionKey, currentStep) {
    const sec = SECTIONS[sectionKey];
    if (!sec) return null;
    if (currentStep === '__incoming__') return null;
    const idx = sec.steps.indexOf(currentStep);
    if (idx > 0) return sec.steps[idx - 1];
    return '__incoming__';
}

function getNextStep(sectionKey, currentStep) {
    const sec = SECTIONS[sectionKey];
    if (!sec) return null;
    if (currentStep === '__incoming__') return sec.steps[0];
    const idx = sec.steps.indexOf(currentStep);
    if (idx < sec.steps.length - 1) return sec.steps[idx + 1];
    return '__next_section__';
}

const NEXT_SECTION_MAP = { conclusion: 'execution', execution: 'modification', modification: 'storage', storage: 'archive', archive: null };

function moveStep(contractId, sectionKey, direction) {
    fetch(`/api/contract/${contractId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section: sectionKey, direction: direction })
    })
    .then(r => r.json())
    .then(() => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('contractModal'));
        if (modal) modal.hide();
        location.reload();
    })
    .catch(err => alert('Ошибка: ' + err.message));
}

function renderContractDetail(c) {
    document.getElementById('modalTitle').textContent = `Договор ${c.number || 'б/н'}`;

    const sectionsHtml = c.sections.map(sk => {
        const sec = SECTIONS[sk];
        if (!sec) return '';
        const steps = c.section_steps || {};
        const curStep = steps[sk] || sec.steps[0];
        const curIdx = sec.steps.indexOf(curStep);
        const hasPrev = curStep !== '__incoming__' && (curIdx > 0 || curStep === sec.steps[0]);
        const hasNext = curStep === '__incoming__' || curIdx < sec.steps.length - 1 || NEXT_SECTION_MAP[sk];

        const timelineHtml = sec.steps.map((s, i) => {
            let cls = '';
            if (i < curIdx) cls = 'completed';
            else if (i === curIdx) cls = 'active';
            return `<div class="timeline-item ${cls}">
                <strong>${sec.step_labels[s] || s}</strong>
            </div>`;
        }).join('');

        return `<div class="card mb-2">
            <div class="card-body py-2">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0" style="color:${sec.step_colors[curStep] || '#6c757d'}">
                        <i class="bi bi-circle-fill" style="font-size:0.6rem"></i> ${sec.label}
                    </h6>
                    <div class="d-flex gap-1">
                        ${hasPrev ? `<button class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="event.stopPropagation(); moveStep(${c.id}, '${sk}', 'backward')" title="Предыдущий шаг"><i class="bi bi-chevron-left"></i></button>` : ''}
                        <span class="badge" style="background:${sec.step_colors[curStep] || '#6c757d'}">
                            ${sec.step_labels[curStep] || (curStep === '__incoming__' ? 'Входящие' : curStep)}
                        </span>
                        ${hasNext ? `<button class="btn btn-sm btn-outline-primary py-0 px-1" onclick="event.stopPropagation(); moveStep(${c.id}, '${sk}', 'forward')" title="Следующий шаг"><i class="bi bi-chevron-right"></i></button>` : ''}
                    </div>
                </div>
                <div class="timeline" style="padding-left:20px">
                    ${timelineHtml}
                </div>
            </div>
        </div>`;
    }).join('');

    const childrenHtml = (c.children || []).map(ch => {
        return `<div class="d-flex justify-content-between align-items-center py-1 border-bottom">
            <a href="#" onclick="showContractDetail(${ch.id}); return false">${ch.number || 'б/н'}</a>
            <small class="text-muted">${ch.name}</small>
        </div>`;
    }).join('');

    const parentLink = c.parent_id
        ? `<div class="mb-2"><small class="text-muted">ДС к договору:</small>
            <a href="#" onclick="showContractDetail(${c.parent_id}); return false">
                (открыть основной договор)</a></div>`
        : '';

    const fieldRow = (label, val) =>
        `<div class="modal-detail-label">${label}</div><div class="modal-detail-value">${val || '—'}</div>`;

    const fieldRow6 = (label, val) =>
        `<div class="col-6">${fieldRow(label, val)}</div>`;

    document.getElementById('modalBody').innerHTML = `
        <div class="row">
            <div class="col-md-7">
                <div class="card mb-3">
                    <div class="card-body">
                        ${parentLink}
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <span class="badge ${c.contract_type === 'additional' ? 'bg-warning text-dark' : 'bg-secondary'}">
                                ${c.contract_type === 'additional' ? 'Дополнительное соглашение' : 'Основной договор'}
                            </span>
                        </div>

                        ${fieldRow('Номер договора', c.number)}
                        ${fieldRow('Наименование', c.name)}
                        ${fieldRow('Контрагент', c.counterparty)}
                        ${fieldRow('Предмет договора', c.subject)}

                        <div class="row">
                            ${fieldRow6('Сумма', c.amount ? c.amount.toFixed(2) + ' ₽' : '—')}
                            ${fieldRow6('Ответственный', c.responsible)}
                        </div>

                        ${c.brief_subject ? fieldRow('Краткая тема', c.brief_subject) : ''}
                        ${c.service_section ? fieldRow('Раздел услуг', c.service_section) : ''}
                        ${c.service_subtype ? fieldRow('Объект, вид работ', c.service_subtype) : ''}
                        ${c.place_conclusion || c.place_service ? `<div class="row">
                            ${c.place_conclusion ? fieldRow6('Место заключения', c.place_conclusion) : ''}
                            ${c.place_service ? fieldRow6('Место оказания', c.place_service) : ''}
                        </div>` : ''}

                        <details class="mt-3"${c.registration_number || c.document_date || c.additional_number || c.additional_date || c.initiator || c.government_id || c.payment_form || c.prolongation || c.renewal_required || c.prolongation_days || c.validity_period ? ' open' : ''}>
                            <summary class="fw-bold small text-muted">Дополнительные реквизиты</summary>
                            <div class="mt-2">
                                ${c.registration_number ? fieldRow('Номер регистрации БРД', c.registration_number) : ''}
                                ${c.document_date ? fieldRow('Дата документа', c.document_date) : ''}
                                ${c.additional_number ? fieldRow('Номер ДС', c.additional_number) : ''}
                                ${c.additional_date ? fieldRow('Дата ДС', c.additional_date) : ''}
                                ${c.initiator ? fieldRow('Инициатор договора', c.initiator) : ''}
                                ${c.government_id ? fieldRow('ИГК', c.government_id) : ''}
                                ${c.payment_form ? fieldRow('Форма расчета', c.payment_form) : ''}
                                ${c.prolongation ? fieldRow('Пролонгация', c.prolongation) : ''}
                                ${c.renewal_required ? fieldRow('Продление требуется', c.renewal_required ? 'Да' : 'Нет') : ''}
                                ${c.prolongation_days ? fieldRow('Срок до пролонгации, дн', c.prolongation_days) : ''}
                                ${c.validity_period ? fieldRow('Срок действия', c.validity_period) : ''}
                            </div>
                        </details>

                        <details class="mt-2"${c.planned_start || c.planned_end || c.actual_start || c.actual_end ? ' open' : ''}>
                            <summary class="fw-bold small text-muted">Плановые и фактические даты</summary>
                            <div class="mt-2">
                                <div class="row">
                                    ${c.planned_start ? fieldRow6('План. начало', c.planned_start) : ''}
                                    ${c.planned_end ? fieldRow6('План. окончание', c.planned_end) : ''}
                                    ${c.actual_start ? fieldRow6('Факт. начало', c.actual_start) : ''}
                                    ${c.actual_end ? fieldRow6('Факт. окончание', c.actual_end) : ''}
                                </div>
                            </div>
                        </details>

                        <details class="mt-2"${c.monthly_amount || c.amount_no_tax || c.tax_rate || c.amount_with_tax || c.amount_paid || c.amount_remaining ? ' open' : ''}>
                            <summary class="fw-bold small text-muted">Финансовая информация</summary>
                            <div class="mt-2">
                                <div class="row">
                                    ${c.monthly_amount ? fieldRow6('В мес. без НДС', c.monthly_amount.toFixed(2) + ' ₽') : ''}
                                    ${c.amount_no_tax ? fieldRow6('Стоимость без налога', c.amount_no_tax.toFixed(2) + ' ₽') : ''}
                                    ${c.tax_rate ? fieldRow6('Налог, %', c.tax_rate) : ''}
                                    ${c.amount_with_tax ? fieldRow6('Стоимость с налогом', c.amount_with_tax.toFixed(2) + ' ₽') : ''}
                                    ${c.amount_paid ? fieldRow6('Оплачено', c.amount_paid.toFixed(2) + ' ₽') : ''}
                                    ${c.amount_remaining ? fieldRow6('Осталось', c.amount_remaining.toFixed(2) + ' ₽') : ''}
                                </div>
                            </div>
                        </details>

                        <details class="mt-2"${c.original_status || c.date_sent_to_sign || c.date_received_signed || c.outgoing_info || c.signatory || c.signatory_doc || c.counterparty_details || c.electronic_copy || c.termination_date ? ' open' : ''}>
                            <summary class="fw-bold small text-muted">Статус и документооборот</summary>
                            <div class="mt-2">
                                ${c.original_status ? fieldRow('Статус оригинала', c.original_status) : ''}
                                ${c.date_sent_to_sign ? fieldRow('Отправлен на подпись', c.date_sent_to_sign) : ''}
                                ${c.date_received_signed ? fieldRow('Получен подписанным', c.date_received_signed) : ''}
                                ${c.outgoing_info ? fieldRow('Исх. и дата направления', c.outgoing_info) : ''}
                                ${c.signatory ? fieldRow('Подписант', c.signatory) : ''}
                                ${c.signatory_doc ? fieldRow('Документ полномочий', c.signatory_doc) : ''}
                                ${c.counterparty_details ? fieldRow('Реквизиты контрагента', c.counterparty_details) : ''}
                                ${c.electronic_copy ? fieldRow('Электронная копия', c.electronic_copy) : ''}
                                ${c.termination_date ? fieldRow('Дата расторжения', c.termination_date) : ''}
                            </div>
                        </details>

                        ${fieldRow('Примечания', c.notes)}

                        ${childrenHtml ? `<div class="mt-3"><div class="modal-detail-label">Дополнительные соглашения</div>${childrenHtml}</div>` : ''}
                    </div>
                </div>
            </div>
            <div class="col-md-5">
                <h6 class="mb-2">Разделы и шаги</h6>
                ${sectionsHtml || '<p class="text-muted">Нет данных</p>'}
            </div>
        </div>`;
}

function deleteContract(id) {
    document.getElementById('confirmBody').textContent = 'Вы уверены, что хотите удалить этот договор?';
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    const btn = document.getElementById('confirmBtn');
    btn.className = 'btn btn-danger';
    const handler = () => {
        fetch(`/api/contract/${id}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(() => location.reload())
            .catch(() => alert('Ошибка при удалении'));
        btn.removeEventListener('click', handler);
    };
    btn.addEventListener('click', handler);
    modal.show();
}

// --- Drag and Drop ---

let dragSrcId = null;

document.addEventListener('DOMContentLoaded', function () {
    const board = document.getElementById('kanbanBoard');
    if (!board) return;

    board.addEventListener('dragstart', function (e) {
        const card = e.target.closest('.contract-card');
        if (!card) return;
        dragSrcId = card.dataset.id;
        card.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', dragSrcId);
    });

    board.addEventListener('dragend', function (e) {
        const card = e.target.closest('.contract-card');
        if (card) card.classList.remove('dragging');
        document.querySelectorAll('.column-body.drag-over').forEach(el => el.classList.remove('drag-over'));
    });

    board.addEventListener('dragover', function (e) {
        e.preventDefault();
        const column = e.target.closest('.column-body');
        if (!column || column.dataset.step.startsWith('__')) return;
        e.dataTransfer.dropEffect = 'move';
        column.classList.add('drag-over');

        const afterCard = getDragAfterElement(column, e.clientY);
        const dragging = document.querySelector('.contract-card.dragging');
        if (dragging && afterCard) {
            column.insertBefore(dragging, afterCard);
        } else if (dragging) {
            column.appendChild(dragging);
        }
    });

    board.addEventListener('dragleave', function (e) {
        const column = e.target.closest('.column-body');
        if (column) column.classList.remove('drag-over');
    });

    board.addEventListener('drop', function (e) {
        e.preventDefault();
        const column = e.target.closest('.column-body');
        if (!column) return;
        column.classList.remove('drag-over');
        const step = column.dataset.step;
        if (step.startsWith('__')) return;

        const section = column.dataset.section;
        const ids = Array.from(column.querySelectorAll('.contract-card')).map(el => parseInt(el.dataset.id));
        if (ids.length === 0) return;

        fetch('/api/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ section, step, contract_ids: ids }),
        }).catch(err => console.error('Reorder error:', err));
    });
});

function getDragAfterElement(container, y) {
    const cards = container.querySelectorAll('.contract-card:not(.dragging)');
    let closest = null;
    let closestOffset = Number.NEGATIVE_INFINITY;
    cards.forEach(card => {
        const box = card.getBoundingClientRect();
        const offset = y - card.offsetHeight / 2;
        if (offset < 0 && offset > closestOffset) {
            closestOffset = offset;
            closest = card;
        }
    });
    return closest;
}

function clearAll() {
    document.getElementById('confirmBody').textContent = 'Удалить ВСЕ договоры? Это необратимо.';
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    const btn = document.getElementById('confirmBtn');
    btn.className = 'btn btn-danger';
    const handler = () => {
        fetch('/api/clear', { method: 'POST' })
            .then(r => r.json())
            .then(() => location.reload())
            .catch(() => alert('Ошибка'));
        btn.removeEventListener('click', handler);
    };
    btn.addEventListener('click', handler);
    modal.show();
}

function stopServer() {
    document.getElementById('confirmBody').textContent = 'Остановить сервер? Данные сохранятся в БД.';
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    const btn = document.getElementById('confirmBtn');
    btn.className = 'btn btn-danger';
    const handler = () => {
        fetch('/api/shutdown', { method: 'POST' })
            .then(r => r.json())
            .then(data => alert(data.message || 'Сервер остановлен'))
            .catch(() => alert('Сервер остановлен'));
        btn.removeEventListener('click', handler);
    };
    btn.addEventListener('click', handler);
    modal.show();
}
