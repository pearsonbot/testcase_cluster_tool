let currentSort = 'id';
let currentOrder = 'asc';
let currentPage = 1;

async function loadBrowseStats() {
    try {
        const data = await apiFetch('/api/import/status');
        document.getElementById('stat-cases').textContent = data.case_count || 0;
        document.getElementById('stat-steps').textContent = data.step_count || 0;
        document.getElementById('stat-last-import').textContent = data.last_import_time || '-';

        const srcData = await apiFetch('/api/import/sources');
        document.getElementById('stat-sources').textContent =
            (srcData.sources ? srcData.sources.length : 0) + ' 个';
    } catch (e) {
        // Ignore
    }
}

async function loadSourceFilters() {
    try {
        const data = await apiFetch('/api/import/sources');
        const select = document.getElementById('filter-source');
        if (data.sources) {
            data.sources.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.filename;
                opt.textContent = `${s.filename} (${s.case_count})`;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        // Ignore
    }
}

function toggleSort(field) {
    if (currentSort === field) {
        currentOrder = currentOrder === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort = field;
        currentOrder = 'asc';
    }
    loadBrowseData(currentPage);
}

async function loadBrowseData(page) {
    currentPage = page;
    const source = document.getElementById('filter-source').value;
    const keyword = document.getElementById('filter-keyword').value.trim();
    const perPage = 20;

    const params = new URLSearchParams({
        page, per_page: perPage,
        sort: currentSort, order: currentOrder,
    });
    if (source) params.set('source', source);
    if (keyword) params.set('keyword', keyword);

    try {
        const data = await apiFetch(`/api/cases/browse?${params}`);

        const tbody = document.getElementById('browse-body');
        const emptyEl = document.getElementById('browse-empty');
        const tableEl = document.getElementById('browse-table');
        const pagination = document.getElementById('browse-pagination');

        if (!data.cases || data.cases.length === 0) {
            tbody.innerHTML = '';
            tableEl.classList.add('d-none');
            emptyEl.classList.remove('d-none');
            pagination.classList.add('d-none');
            return;
        }

        tableEl.classList.remove('d-none');
        emptyEl.classList.add('d-none');

        tbody.innerHTML = data.cases.map(c =>
            `<tr class="browse-row" data-case-id="${c.id}">
                <td><input type="checkbox" class="browse-select-check" value="${c.id}" onchange="browseUpdateBatchDelete()"></td>
                <td><code>${c.id}</code></td>
                <td>
                    <span class="browse-title" style="cursor:pointer" onclick="browseToggleSteps(this, '${c.id}')">${c.title}</span>
                    <div class="browse-steps-preview d-none mt-1" id="steps-${c.id}"></div>
                </td>
                <td><span class="badge bg-secondary">${c.step_count}</span></td>
                <td><small>${c.source_file || '-'}</small></td>
                <td><small>${c.import_time || '-'}</small></td>
                <td>
                    <a href="/?case=${encodeURIComponent(c.id)}" class="btn btn-sm btn-outline-primary">查看</a>
                    <button class="btn btn-sm btn-outline-danger" onclick="browseDeleteCase('${c.id}')">删除</button>
                </td>
            </tr>`
        ).join('');

        // Pagination
        const totalPages = Math.ceil(data.total / perPage);
        pagination.classList.remove('d-none');
        document.getElementById('browse-page-info').textContent =
            `共 ${data.total} 条  第 ${page}/${totalPages} 页`;

        const btns = document.getElementById('browse-page-buttons');
        let paginationHtml = '';
        if (page > 1) {
            paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:loadBrowseData(${page - 1})">上一页</a></li>`;
        }
        const start = Math.max(1, page - 2);
        const end = Math.min(totalPages, page + 2);
        for (let i = start; i <= end; i++) {
            paginationHtml += `<li class="page-item ${i === page ? 'active' : ''}">
                <a class="page-link" href="javascript:loadBrowseData(${i})">${i}</a></li>`;
        }
        if (page < totalPages) {
            paginationHtml += `<li class="page-item"><a class="page-link" href="javascript:loadBrowseData(${page + 1})">下一页</a></li>`;
        }
        btns.innerHTML = paginationHtml;

        // Update batch delete button
        browseUpdateBatchDelete();

    } catch (e) {
        showAlert(e.message);
    }
}

async function browseToggleSteps(el, caseId) {
    const preview = document.getElementById(`steps-${caseId}`);
    if (!preview.classList.contains('d-none')) {
        preview.classList.add('d-none');
        return;
    }

    if (preview.innerHTML === '') {
        try {
            const data = await apiFetch(`/api/cases/${encodeURIComponent(caseId)}`);
            const steps = data.steps;
            preview.innerHTML = steps.map(s =>
                `<small class="d-block text-muted ms-2">├ ${s.step_no}. ${s.operation}</small>`
            ).join('');
        } catch (e) {
            preview.innerHTML = '<small class="text-danger">加载失败</small>';
        }
    }
    preview.classList.remove('d-none');
}

function browseToggleSelectAll(checkbox) {
    const checks = document.querySelectorAll('.browse-select-check');
    checks.forEach(c => c.checked = checkbox.checked);
    browseUpdateBatchDelete();
}

function browseUpdateBatchDelete() {
    const checked = document.querySelectorAll('.browse-select-check:checked');
    const btn = document.getElementById('btn-browse-batch-delete');
    if (btn) {
        btn.classList.toggle('d-none', checked.length === 0);
    }
}

async function browseBatchDelete() {
    const checked = document.querySelectorAll('.browse-select-check:checked');
    if (checked.length === 0) return;

    const caseIds = Array.from(checked).map(c => c.value);
    if (!confirm(`确定要删除选中的 ${caseIds.length} 条用例吗？\n\n此操作将同时删除关联的步骤和聚类结果。`)) return;

    try {
        await apiFetch('/api/cases/batch-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_ids: caseIds })
        });
        showAlert(`已删除 ${caseIds.length} 条用例`, 'success');
        loadBrowseData(currentPage);
        loadBrowseStats();
    } catch (e) {
        showAlert(e.message);
    }
}

async function browseDeleteCase(caseId) {
    if (!confirm(`确定要删除用例 ${caseId} 吗？\n\n此操作将同时删除关联的步骤和聚类结果。`)) return;

    try {
        await apiFetch(`/api/cases/${encodeURIComponent(caseId)}`, { method: 'DELETE' });
        showAlert(`已删除用例 ${caseId}`, 'success');
        loadBrowseData(currentPage);
        loadBrowseStats();
    } catch (e) {
        showAlert(e.message);
    }
}
