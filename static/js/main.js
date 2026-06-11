let currentContractId = null;

document.addEventListener('DOMContentLoaded', function () {
    initDragDrop();
    initFileInput();
});

function initDragDrop() {
    const dropZone = document.getElementById('dropZone');
    if (!dropZone) return;

    dropZone.classList.add('active');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
        document.body.addEventListener(event, e => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    ['dragenter', 'dragover'].forEach(event => {
        document.body.addEventListener(event, () => {
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(event => {
        document.body.addEventListener(event, e => {
            dropZone.classList.remove('dragover');
        });
    });

    document.body.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
}

function initFileInput() {
    const input = document.getElementById('fileInput');
    if (!input) return;
    input.addEventListener('change', e => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });
}

function handleFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['xlsx', 'xls'].includes(ext)) {
        showImportResult('error', 'Поддерживаются только файлы Excel (.xlsx, .xls)');
        return;
    }

    const dropZone = document.getElementById('dropZone');
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
            if (data.error) {
                showImportResult('error', data.error);
            } else {
                showImportResult('success', data.message);
            }
        })
        .catch(err => {
            progressEl.classList.add('d-none');
            textEl.classList.remove('d-none');
            showImportResult('error', 'Ошибка при загрузке файла');
        });
}

function showImportResult(type, message) {
    const modal = new bootstrap.Modal(document.getElementById('importModal'));
    const result = document.getElementById('importResult');
    result.innerHTML = `<div class="alert alert-${type === 'success' ? 'success' : 'danger'} mb-0">${message}</div>`;
    modal.show();
}

function showContractDetail(id) {
    currentContractId = id;
    const modal = new bootstrap.Modal(document.getElementById('contractModal'));
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');

    title.textContent = 'Загрузка...';
    body.innerHTML = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div></div>';
    modal.show();

    fetch(`/api/contracts`)
        .then(r => r.json())
        .then(allContracts => {
            const contract = allContracts.find(c => c.id === id);
            if (!contract) {
                body.innerHTML = '<div class="alert alert-danger">Договор не найден</div>';
                return;
            }
            renderContractDetail(contract);
        })
        .catch(() => {
            body.innerHTML = '<div class="alert alert-danger">Ошибка загрузки данных</div>';
        });
}

function renderContractDetail(c) {
    const title = document.getElementById('modalTitle');
    const body = document.getElementById('modalBody');

    const statusList = [
        { key: 'received', label: 'Получен', date: c.received_date },
        { key: 'processing', label: 'Оформление', date: c.processing_date },
        { key: 'approval', label: 'Согласование', date: c.approval_date },
        { key: 'revision', label: 'Корректировка', date: c.revision_date },
        { key: 'signing', label: 'Подписание руководителем', date: c.signing_date },
        { key: 'sent', label: 'Направление контрагенту', date: c.sent_date },
        { key: 'archive', label: 'Архив', date: c.archive_date },
        { key: 'destroyed', label: 'Уничтожен', date: c.destroyed_date },
    ];

    const statusOrder = ['received', 'processing', 'approval', 'revision', 'signing', 'sent', 'archive', 'destroyed'];
    const currentIdx = statusOrder.indexOf(c.status);
    let foundActive = false;

    const timelineHtml = statusList.map((s, i) => {
        let cls = '';
        if (i < currentIdx) cls = 'completed';
        else if (i === currentIdx) { cls = 'active'; foundActive = true; }
        const dateStr = s.date ? new Date(s.date).toLocaleDateString('ru-RU') : '—';
        return `
            <div class="timeline-item ${cls}">
                <strong>${s.label}</strong>
                <br><small class="text-muted">${dateStr}</small>
            </div>
        `;
    }).join('');

    const statusColors = {
        received: '#4A90D9', processing: '#00B4D8', approval: '#F4A261',
        revision: '#E76F51', signing: '#9B5DE5', sent: '#6C63FF',
        archive: '#2A9D8F', destroyed: '#6C757D'
    };

    const statusLabel = {
        received: 'Получен', processing: 'Оформление', approval: 'Согласование',
        revision: 'Корректировка', signing: 'Подписание руководителем',
        sent: 'Направление контрагенту', archive: 'Архив', destroyed: 'Уничтожен'
    };

    title.textContent = `Договор ${c.number || 'б/н'}`;

    body.innerHTML = `
        <div class="row">
            <div class="col-md-7">
                <div class="card mb-3">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <span class="badge fs-6" style="background:${statusColors[c.status] || '#6c757d'}">${statusLabel[c.status] || c.status}</span>
                            <div>
                                <button class="btn btn-sm btn-outline-primary" onclick="moveContract(${c.id})">
                                    <i class="bi bi-arrow-right"></i> На следующий этап
                                </button>
                            </div>
                        </div>

                        <div class="modal-detail-label">Номер договора</div>
                        <div class="modal-detail-value">${c.number || '—'}</div>

                        <div class="modal-detail-label">Наименование</div>
                        <div class="modal-detail-value">${c.name || '—'}</div>

                        <div class="modal-detail-label">Контрагент</div>
                        <div class="modal-detail-value">${c.counterparty || '—'}</div>

                        <div class="modal-detail-label">Предмет договора</div>
                        <div class="modal-detail-value">${c.subject || '—'}</div>

                        <div class="row">
                            <div class="col-6">
                                <div class="modal-detail-label">Сумма</div>
                                <div class="modal-detail-value">${c.amount ? c.amount.toFixed(2) + ' ₽' : '—'}</div>
                            </div>
                            <div class="col-6">
                                <div class="modal-detail-label">Ответственный</div>
                                <div class="modal-detail-value">${c.responsible || '—'}</div>
                            </div>
                        </div>

                        <div class="modal-detail-label">Примечания</div>
                        <div class="modal-detail-value">${c.notes || '—'}</div>
                    </div>
                </div>
            </div>
            <div class="col-md-5">
                <div class="card">
                    <div class="card-body">
                        <h6 class="card-title">Ход выполнения</h6>
                        <div class="timeline">
                            ${timelineHtml}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function moveContract(id) {
    fetch(`/api/contracts`)
        .then(r => r.json())
        .then(all => {
            const c = all.find(x => x.id === id);
            if (!c) return;
            const order = ['received', 'processing', 'approval', 'revision', 'signing', 'sent', 'archive', 'destroyed'];
            const idx = order.indexOf(c.status);
            if (idx < order.length - 1) {
                const nextStatus = order[idx + 1];
                fetch(`/api/contract/${id}/move`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: nextStatus })
                })
                .then(r => r.json())
                .then(() => {
                    const modal = bootstrap.Modal.getInstance(document.getElementById('contractModal'));
                    if (modal) modal.hide();
                    location.reload();
                });
            }
        });
}

function deleteContract(id) {
    const body = document.getElementById('confirmBody');
    body.textContent = 'Вы уверены, что хотите удалить этот договор?';
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    const btn = document.getElementById('confirmBtn');

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

function clearAll() {
    const body = document.getElementById('confirmBody');
    body.textContent = 'Вы уверены, что хотите удалить ВСЕ договоры? Это действие необратимо.';
    const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
    const btn = document.getElementById('confirmBtn');

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
