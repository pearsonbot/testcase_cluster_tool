let uploadedMapping = null;

async function loadImportStatus() {
    try {
        const data = await apiFetch('/api/import/status');
        const el = document.getElementById('import-status');
        if (data.case_count > 0) {
            el.innerHTML = `<span class="badge bg-success">Database: ${data.case_count} cases, ${data.step_count} steps</span>`;
            if (data.last_import_time) {
                el.innerHTML += ` <small class="text-muted">Last import: ${data.last_import_time}</small>`;
            }
        } else {
            el.innerHTML = '<span class="badge bg-secondary">No data imported yet</span>';
        }
    } catch (e) {
        document.getElementById('import-status').textContent = 'Failed to load status';
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('xlsx-file');
    if (!fileInput.files.length) {
        showAlert('Please select an xlsx file first');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    document.getElementById('btn-upload').disabled = true;
    document.getElementById('import-progress').classList.remove('d-none');
    hideAlert();

    try {
        const resp = await fetch('/api/import/upload', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();

        if (!data.success) {
            throw new Error(data.error);
        }

        uploadedMapping = data.mapping;

        // Show column mapping
        const mappingDiv = document.getElementById('mapping-content');
        let html = '<table class="table table-sm table-bordered"><thead><tr><th>Field</th><th>Mapped Column</th></tr></thead><tbody>';

        const fieldNames = {
            'id': 'Identifier (标识)',
            'title': 'Title (标题)',
            'step_no': 'Step No (TC步骤)',
            'operation': 'Operation (TC操作)'
        };

        for (const [field, name] of Object.entries(fieldNames)) {
            const colIdx = data.mapping[field];
            const colName = colIdx !== undefined ? data.headers[colIdx] : '<span class="text-danger">Not Mapped</span>';
            html += `<tr><td>${name}</td><td>`;

            if (data.unmatched.includes(field)) {
                // Show dropdown for manual mapping
                html += `<select class="form-select form-select-sm" id="manual-${field}">`;
                html += '<option value="">-- Select Column --</option>';
                data.headers.forEach((h, i) => {
                    html += `<option value="${i}">${h}</option>`;
                });
                html += '</select>';
            } else {
                html += colName;
            }

            html += '</td></tr>';
        }
        html += '</tbody></table>';

        if (data.extra_columns && Object.keys(data.extra_columns).length > 0) {
            html += `<small class="text-muted">Extra columns: ${Object.keys(data.extra_columns).join(', ')}</small>`;
        }

        mappingDiv.innerHTML = html;
        document.getElementById('column-mapping').classList.remove('d-none');
        document.getElementById('import-progress').classList.add('d-none');

        if (data.auto_confirmed) {
            // Auto-confirmed, but still show for review
        }

    } catch (e) {
        showAlert(e.message);
        document.getElementById('import-progress').classList.add('d-none');
    } finally {
        document.getElementById('btn-upload').disabled = false;
    }
}

async function confirmImport() {
    // Check for manual mappings
    const mapping = { ...uploadedMapping };
    for (const field of ['id', 'title', 'step_no', 'operation']) {
        const select = document.getElementById(`manual-${field}`);
        if (select && select.value) {
            mapping[field] = parseInt(select.value);
        }
    }

    // Validate all required fields are mapped
    for (const field of ['id', 'title', 'step_no', 'operation']) {
        if (mapping[field] === undefined || mapping[field] === null) {
            showAlert(`Field "${field}" is not mapped. Please select a column.`);
            return;
        }
    }

    document.getElementById('import-progress').classList.remove('d-none');
    document.getElementById('column-mapping').classList.add('d-none');

    try {
        const data = await apiFetch('/api/import/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mapping })
        });

        let resultHtml = `<div class="alert alert-success">
            Successfully imported ${data.cases_imported} cases with ${data.steps_imported} steps.
        </div>`;

        if (data.warnings && data.warnings.length > 0) {
            resultHtml += '<div class="alert alert-warning"><strong>Warnings:</strong><ul>';
            data.warnings.forEach(w => { resultHtml += `<li>${w}</li>`; });
            resultHtml += '</ul></div>';
        }

        document.getElementById('import-result').innerHTML = resultHtml;
        document.getElementById('import-result').classList.remove('d-none');
        document.getElementById('import-progress').classList.add('d-none');

        loadImportStatus();
        loadExtraColumns();

    } catch (e) {
        showAlert(e.message);
        document.getElementById('import-progress').classList.add('d-none');
    }
}

function cancelImport() {
    document.getElementById('column-mapping').classList.add('d-none');
    uploadedMapping = null;
}
