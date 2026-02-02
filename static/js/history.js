async function loadHistory() {
    try {
        const data = await apiFetch('/api/cluster/history');
        const tbody = document.getElementById('history-body');
        const emptyEl = document.getElementById('no-history');
        const tableEl = document.getElementById('history-table');

        if (!data.records || data.records.length === 0) {
            tableEl.classList.add('d-none');
            emptyEl.classList.remove('d-none');
            document.getElementById('compare-btn').disabled = true;
            return;
        }

        tableEl.classList.remove('d-none');
        emptyEl.classList.add('d-none');

        tbody.innerHTML = data.records.map(r => {
            const elapsed = formatHistoryElapsed(r.elapsed_seconds);
            const isCurrent = r.is_current ? '<span class="badge bg-success">当前</span>' : '';
            return `<tr>
                <td><input type="checkbox" class="history-checkbox" value="${r.id}" onchange="updateCompareButton()"></td>
                <td>${r.id}</td>
                <td>${r.run_time || '-'}</td>
                <td>${r.model_name || r.model_type || '-'}</td>
                <td>${r.similarity_threshold || '-'}</td>
                <td>${r.total_clusters || 0}</td>
                <td>${r.noise_count || 0}</td>
                <td>${r.total_steps || 0}</td>
                <td>${elapsed}</td>
                <td>${isCurrent}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="viewHistory(${r.id})">查看</button>
                    ${!r.is_current ? `<button class="btn btn-sm btn-outline-success" onclick="activateHistory(${r.id})">设为当前</button>` : ''}
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteHistory(${r.id})">删除</button>
                </td>
            </tr>`;
        }).join('');

    } catch (e) {
        showAlert(e.message);
    }
}

function formatHistoryElapsed(seconds) {
    if (!seconds || seconds < 0) return '-';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    if (m > 0) return `${m}分${s}秒`;
    return `${s}秒`;
}

function toggleHistorySelectAll(el) {
    document.querySelectorAll('.history-checkbox').forEach(cb => cb.checked = el.checked);
    updateCompareButton();
}

function updateCompareButton() {
    const checked = document.querySelectorAll('.history-checkbox:checked');
    const btn = document.getElementById('compare-btn');
    btn.disabled = checked.length !== 2;
}

async function viewHistory(historyId) {
    window.location.href = `/clusters?history_id=${historyId}`;
}

async function activateHistory(historyId) {
    if (!confirm('确定要将此记录设为当前活跃结果吗？')) return;

    try {
        await apiFetch(`/api/cluster/history/${historyId}/activate`, { method: 'POST' });
        showAlert('已设为当前活跃结果', 'success');
        loadHistory();
    } catch (e) {
        showAlert(e.message);
    }
}

async function deleteHistory(historyId) {
    if (!confirm('确定要删除此历史记录吗？\n\n关联的聚类结果也将被删除。')) return;

    try {
        await apiFetch(`/api/cluster/history/${historyId}`, { method: 'DELETE' });
        showAlert('已删除历史记录', 'success');
        loadHistory();
    } catch (e) {
        showAlert(e.message);
    }
}

async function compareSelected() {
    const checked = document.querySelectorAll('.history-checkbox:checked');
    if (checked.length !== 2) {
        showAlert('请选择恰好两条历史记录进行对比');
        return;
    }

    const id1 = checked[0].value;
    const id2 = checked[1].value;

    try {
        const data = await apiFetch(`/api/cluster/history/compare?id1=${id1}&id2=${id2}`);
        renderComparison(data);
    } catch (e) {
        showAlert(e.message);
    }
}

function renderComparison(data) {
    const card = document.getElementById('compare-card');
    const content = document.getElementById('compare-content');
    card.classList.remove('d-none');

    const r1 = data.record1;
    const r2 = data.record2;

    const clusterDiff = r2.total_clusters - r1.total_clusters;
    const noiseDiff = r2.noise_count - r1.noise_count;
    const diffSign = n => n > 0 ? `+${n}` : `${n}`;
    const diffClass = n => n > 0 ? 'text-success' : (n < 0 ? 'text-danger' : 'text-muted');

    let html = `
    <div class="row mb-3">
        <div class="col-md-6">
            <h6>记录 #${r1.id}</h6>
            <small class="text-muted">${r1.run_time}</small><br>
            <small>模型: ${r1.model_name || r1.model_type} | 阈值: ${r1.similarity_threshold}</small><br>
            <span class="badge bg-primary">${r1.total_clusters} 个簇</span>
            <span class="badge bg-secondary">${r1.noise_count} 噪声</span>
            <span class="badge bg-info">${r1.total_steps} 总步骤</span>
        </div>
        <div class="col-md-6">
            <h6>记录 #${r2.id}</h6>
            <small class="text-muted">${r2.run_time}</small><br>
            <small>模型: ${r2.model_name || r2.model_type} | 阈值: ${r2.similarity_threshold}</small><br>
            <span class="badge bg-primary">${r2.total_clusters} 个簇</span>
            <span class="badge bg-secondary">${r2.noise_count} 噪声</span>
            <span class="badge bg-info">${r2.total_steps} 总步骤</span>
        </div>
    </div>
    <div class="row mb-3">
        <div class="col">
            <strong>变化：</strong>
            簇数量 <span class="${diffClass(clusterDiff)}">${diffSign(clusterDiff)}</span> |
            噪声步骤 <span class="${diffClass(-noiseDiff)}">${diffSign(noiseDiff)}</span>
        </div>
    </div>`;

    if (data.new_labels.length > 0) {
        html += `<div class="mb-2"><strong class="text-success">新增簇标签 (${data.new_labels.length}):</strong><br>`;
        html += data.new_labels.map(l => `<span class="badge bg-success me-1 mb-1">${l}</span>`).join('');
        html += `</div>`;
    }

    if (data.disappeared_labels.length > 0) {
        html += `<div class="mb-2"><strong class="text-danger">消失簇标签 (${data.disappeared_labels.length}):</strong><br>`;
        html += data.disappeared_labels.map(l => `<span class="badge bg-danger me-1 mb-1">${l}</span>`).join('');
        html += `</div>`;
    }

    if (data.common_labels.length > 0) {
        html += `<div class="mb-2"><strong class="text-muted">共同簇标签 (${data.common_labels.length}):</strong><br>`;
        html += data.common_labels.map(l => `<span class="badge bg-light text-dark border me-1 mb-1">${l}</span>`).join('');
        html += `</div>`;
    }

    if (data.new_labels.length === 0 && data.disappeared_labels.length === 0 && data.common_labels.length === 0) {
        html += `<div class="text-muted">两次聚类均无标签数据可对比。</div>`;
    }

    content.innerHTML = html;
    card.scrollIntoView({ behavior: 'smooth' });
}
