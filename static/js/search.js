let visibleExtraColumns = new Set();

async function loadExtraColumns() {
    try {
        const data = await apiFetch('/api/cases/columns');
        const allColumns = [...new Set([...data.case_columns, ...data.step_columns])];

        if (allColumns.length > 0) {
            const container = document.getElementById('extra-columns-checkboxes');
            container.innerHTML = allColumns.map(col =>
                `<div class="form-check form-check-inline">
                    <input class="form-check-input extra-col-check" type="checkbox"
                           id="col-${col}" value="${col}" onchange="toggleColumn('${col}', this.checked)">
                    <label class="form-check-label" for="col-${col}">${col}</label>
                </div>`
            ).join('');
            document.getElementById('column-selector').classList.remove('d-none');
        }
    } catch (e) {
        // Ignore
    }
}

function toggleColumn(col, checked) {
    if (checked) {
        visibleExtraColumns.add(col);
    } else {
        visibleExtraColumns.delete(col);
    }
}

function toggleSelectAll(checkbox) {
    const checks = document.querySelectorAll('.case-select-check');
    checks.forEach(c => c.checked = checkbox.checked);
    updateBatchDeleteButton();
}

function updateBatchDeleteButton() {
    const checked = document.querySelectorAll('.case-select-check:checked');
    const btn = document.getElementById('btn-batch-delete');
    if (btn) {
        btn.classList.toggle('d-none', checked.length === 0);
    }
}

async function batchDeleteCases() {
    const checked = document.querySelectorAll('.case-select-check:checked');
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
        searchCases();
        loadImportStatus();
    } catch (e) {
        showAlert(e.message);
    }
}

async function deleteSingleCase(caseId) {
    if (!confirm(`确定要删除用例 ${caseId} 吗？\n\n此操作将同时删除关联的步骤和聚类结果。`)) return;

    try {
        await apiFetch(`/api/cases/${encodeURIComponent(caseId)}`, { method: 'DELETE' });
        showAlert(`已删除用例 ${caseId}`, 'success');
        searchCases();
        loadImportStatus();
    } catch (e) {
        showAlert(e.message);
    }
}

async function searchCases() {
    const q = document.getElementById('search-input').value.trim();
    if (!q) return;

    const mode = document.querySelector('input[name="search-mode"]:checked').value;

    try {
        const data = await apiFetch(`/api/cases/search?q=${encodeURIComponent(q)}&mode=${mode}`);

        document.getElementById('search-results').classList.remove('d-none');
        document.getElementById('case-detail-section').classList.add('d-none');

        if (data.cases.length === 0) {
            document.getElementById('case-list-section').classList.remove('d-none');
            document.getElementById('result-count').textContent = '0';
            document.getElementById('case-list-body').innerHTML =
                '<tr><td colspan="5" class="text-center text-muted">未找到匹配结果</td></tr>';
            return;
        }

        if (data.cases.length === 1) {
            loadCaseDetail(data.cases[0].id);
            document.getElementById('case-list-section').classList.add('d-none');
        } else {
            document.getElementById('result-count').textContent = data.total;
            const tbody = document.getElementById('case-list-body');
            tbody.innerHTML = data.cases.map(c =>
                `<tr>
                    <td><input type="checkbox" class="case-select-check" value="${c.id}" onchange="updateBatchDeleteButton()"></td>
                    <td><code>${c.id}</code></td>
                    <td>${c.title}</td>
                    <td>${c.step_count}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="loadCaseDetail('${c.id}')">查看</button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteSingleCase('${c.id}')">删除</button>
                    </td>
                </tr>`
            ).join('');
            document.getElementById('case-list-section').classList.remove('d-none');
            document.getElementById('btn-batch-delete').classList.remove('d-none');
        }
    } catch (e) {
        showAlert(e.message);
    }
}

async function loadCaseDetail(caseId) {
    try {
        const data = await apiFetch(`/api/cases/${encodeURIComponent(caseId)}`);
        const c = data.case;
        const steps = data.steps;

        let html = `
            <h5><code>${c.id}</code> ${c.title}</h5>
            <small class="text-muted">来源文件: ${c.source_file || 'N/A'} | 导入时间: ${c.import_time || 'N/A'}</small>
            <button class="btn btn-sm btn-outline-danger float-end" onclick="deleteSingleCase('${c.id}')">
                <i class="bi bi-trash"></i> 删除此用例
            </button>
        `;

        if (visibleExtraColumns.size > 0 && c.extra_fields) {
            html += '<div class="mt-2">';
            for (const col of visibleExtraColumns) {
                if (c.extra_fields[col]) {
                    html += `<span class="badge bg-light text-dark me-2">${col}: ${c.extra_fields[col]}</span>`;
                }
            }
            html += '</div>';
        }

        // Original steps
        html += '<h6 class="mt-3">原始步骤</h6>';
        html += '<table class="table table-sm table-bordered"><thead><tr><th style="width:60px">#</th><th>操作</th>';
        for (const col of visibleExtraColumns) {
            html += `<th>${col}</th>`;
        }
        html += '</tr></thead><tbody>';
        for (const step of steps) {
            html += `<tr><td>${step.step_no}</td><td>${step.operation}</td>`;
            for (const col of visibleExtraColumns) {
                html += `<td>${(step.extra_fields && step.extra_fields[col]) || ''}</td>`;
            }
            html += '</tr>';
        }
        html += '</tbody></table>';

        // Cluster-annotated view
        html += '<h6 class="mt-3">聚类视图</h6>';
        for (const step of steps) {
            html += '<div class="card mb-2">';
            html += '<div class="card-body py-2 px-3">';
            html += `<strong>步骤 ${step.step_no}</strong>: ${step.operation}`;

            if (step.cluster_id !== null && step.cluster_id >= 0) {
                html += ` <span class="badge bg-primary">簇 #${step.cluster_id}</span>`;
                html += ` <span class="badge bg-info">${step.cluster_label || ''}</span>`;

                if (step.siblings && step.siblings.length > 0) {
                    html += '<div class="mt-1 ms-3"><small class="text-muted">其他用例中的相似步骤:</small>';
                    html += '<ul class="list-unstyled mb-0">';
                    for (const sib of step.siblings) {
                        html += `<li><small><code>${sib.case_id}</code> 步骤 ${sib.step_no}: ${sib.operation}</small></li>`;
                    }
                    html += '</ul></div>';
                }
            } else {
                html += ' <span class="badge bg-secondary">独立步骤</span>';
            }

            html += '</div></div>';
        }

        document.getElementById('case-detail-content').innerHTML = html;
        document.getElementById('case-detail-section').classList.remove('d-none');
        document.getElementById('search-results').classList.remove('d-none');

    } catch (e) {
        showAlert(e.message);
    }
}

function hideCaseDetail() {
    document.getElementById('case-detail-section').classList.add('d-none');
}
