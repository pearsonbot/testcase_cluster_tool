let uploadedMapping = null;

async function loadImportStatus() {
    try {
        const data = await apiFetch('/api/import/status');
        const el = document.getElementById('import-status');
        if (data.case_count > 0) {
            el.innerHTML = `<span class="badge bg-success">数据库: ${data.case_count} 条用例, ${data.step_count} 条步骤</span>`;
            if (data.last_import_time) {
                el.innerHTML += ` <small class="text-muted">上次导入: ${data.last_import_time}</small>`;
            }
        } else {
            el.innerHTML = '<span class="badge bg-secondary">暂无导入数据</span>';
        }
        // Update data stats
        const statsEl = document.getElementById('data-stats');
        if (statsEl) {
            if (data.case_count > 0) {
                statsEl.innerHTML = `<span class="badge bg-info">数据库状态:</span> ${data.case_count} 条用例, ${data.step_count} 条步骤`;
            } else {
                statsEl.innerHTML = '<span class="text-muted">数据库为空</span>';
            }
        }
    } catch (e) {
        document.getElementById('import-status').textContent = '加载状态失败';
    }
}

async function loadSourceFiles() {
    try {
        const data = await apiFetch('/api/import/sources');
        const container = document.getElementById('source-files-container');
        const section = document.getElementById('source-file-list');

        if (data.sources && data.sources.length > 0) {
            container.innerHTML = data.sources.map(s =>
                `<div class="form-check">
                    <input class="form-check-input source-check" type="checkbox" value="${s.filename}" id="src-${s.filename}">
                    <label class="form-check-label" for="src-${s.filename}">
                        ${s.filename} (${s.case_count} 条用例)
                    </label>
                </div>`
            ).join('');
            section.classList.remove('d-none');
        } else {
            section.classList.add('d-none');
        }
    } catch (e) {
        // Ignore
    }
}

async function deleteBySource() {
    const checked = document.querySelectorAll('.source-check:checked');
    if (checked.length === 0) {
        showAlert('请先选择要删除的来源文件');
        return;
    }

    const filenames = Array.from(checked).map(c => c.value);
    const msg = `确定要删除以下文件导入的所有数据吗？\n\n${filenames.join('\n')}\n\n此操作不可恢复！`;
    if (!confirm(msg)) return;

    try {
        for (const fn of filenames) {
            await apiFetch(`/api/import/by-source/${encodeURIComponent(fn)}`, { method: 'DELETE' });
        }
        showAlert(`已删除 ${filenames.length} 个来源文件的数据`, 'success');
        loadImportStatus();
        loadSourceFiles();
    } catch (e) {
        showAlert(e.message);
    }
}

async function clearAllData() {
    if (!confirm('确定要清空全部数据吗？\n\n将删除所有用例、步骤及聚类结果。\n此操作不可恢复！')) return;
    if (!confirm('再次确认：真的要清空全部数据吗？')) return;

    try {
        await apiFetch('/api/cases/all', { method: 'DELETE' });
        showAlert('已清空全部数据', 'success');
        loadImportStatus();
        loadSourceFiles();
    } catch (e) {
        showAlert(e.message);
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('xlsx-file');
    if (!fileInput.files.length) {
        showAlert('请先选择 xlsx 文件');
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.endsWith('.xlsx')) {
        showAlert('请上传 xlsx 格式文件');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

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
        let html = '<table class="table table-sm table-bordered"><thead><tr><th>字段</th><th>映射列</th></tr></thead><tbody>';

        const fieldNames = {
            'id': '标识 (ID)',
            'title': '标题 (Title)',
            'step_no': '步骤号 (Step No)',
            'operation': '操作 (Operation)'
        };

        for (const [field, name] of Object.entries(fieldNames)) {
            const colIdx = data.mapping[field];
            const colName = colIdx !== undefined ? data.headers[colIdx] : '<span class="text-danger">未映射</span>';
            html += `<tr><td>${name}</td><td>`;

            if (data.unmatched.includes(field)) {
                html += `<select class="form-select form-select-sm" id="manual-${field}">`;
                html += '<option value="">-- 请选择列 --</option>';
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
            html += `<small class="text-muted">附加列: ${Object.keys(data.extra_columns).join(', ')}</small>`;
        }

        mappingDiv.innerHTML = html;
        document.getElementById('column-mapping').classList.remove('d-none');
        document.getElementById('import-progress').classList.add('d-none');

    } catch (e) {
        showAlert(e.message);
        document.getElementById('import-progress').classList.add('d-none');
    } finally {
        document.getElementById('btn-upload').disabled = false;
    }
}

async function confirmImport() {
    const mapping = { ...uploadedMapping };
    for (const field of ['id', 'title', 'step_no', 'operation']) {
        const select = document.getElementById(`manual-${field}`);
        if (select && select.value) {
            mapping[field] = parseInt(select.value);
        }
    }

    for (const field of ['id', 'title', 'step_no', 'operation']) {
        if (mapping[field] === undefined || mapping[field] === null) {
            showAlert(`字段"${field}"未映射，请选择对应列。`);
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
            成功导入 ${data.cases_imported} 条用例, ${data.steps_imported} 条步骤。
        </div>`;

        if (data.warnings && data.warnings.length > 0) {
            resultHtml += '<div class="alert alert-warning"><strong>警告:</strong><ul>';
            data.warnings.forEach(w => { resultHtml += `<li>${w}</li>`; });
            resultHtml += '</ul></div>';
        }

        document.getElementById('import-result').innerHTML = resultHtml;
        document.getElementById('import-result').classList.remove('d-none');
        document.getElementById('import-progress').classList.add('d-none');

        loadImportStatus();
        loadExtraColumns();
        loadSourceFiles();

    } catch (e) {
        showAlert(e.message);
        document.getElementById('import-progress').classList.add('d-none');
    }
}

function cancelImport() {
    document.getElementById('column-mapping').classList.add('d-none');
    uploadedMapping = null;
}
