let clusterPollingTimer = null;

async function loadModelInfo() {
    try {
        const data = await apiFetch('/api/settings/');
        const modelType = data.settings.model_type || 'builtin';
        const el = document.getElementById('model-name');
        if (modelType === 'builtin') {
            el.textContent = 'text2vec-base-chinese (内置)';
            el.className = 'badge bg-info';
        } else if (modelType === 'local') {
            el.textContent = `本地: ${data.settings.model_path || '未设置'}`;
            el.className = 'badge bg-success';
        } else if (modelType === 'api') {
            el.textContent = `API: ${data.settings.api_model_name || '未设置'}`;
            el.className = 'badge bg-warning text-dark';
        } else if (modelType === 'tfidf') {
            el.textContent = 'TF-IDF (轻量)';
            el.className = 'badge bg-secondary';
        }
    } catch (e) {
        document.getElementById('model-name').textContent = '未配置';
    }
}

async function loadClusterStatus() {
    try {
        const data = await apiFetch('/api/cluster/status');
        const el = document.getElementById('cluster-status');

        if (data.status === 'completed' && data.result) {
            el.innerHTML = `<span class="badge bg-success">聚类完成</span> ` +
                `${data.result.total_clusters} 个簇, ${data.result.noise_count} 个独立步骤 ` +
                `(阈值: ${data.result.threshold})`;
        } else if (data.status === 'running') {
            el.innerHTML = '<span class="badge bg-warning text-dark">执行中...</span>';
            startPolling();
        } else if (data.status === 'error') {
            el.innerHTML = `<span class="badge bg-danger">错误</span> ${data.error}`;
        } else {
            const listData = await apiFetch('/api/cluster/list');
            if (listData.clusters && listData.clusters.length > 0) {
                el.innerHTML = `<span class="badge bg-success">聚类可用</span> ` +
                    `${listData.clusters.length} 个簇`;
            } else {
                el.innerHTML = '<span class="text-muted">未执行</span>';
            }
        }
    } catch (e) {
        document.getElementById('cluster-status').textContent = '加载状态失败';
    }
}

async function runClustering() {
    const threshold = parseFloat(document.getElementById('threshold-slider').value);

    document.getElementById('btn-cluster').disabled = true;
    document.getElementById('cluster-progress').classList.remove('d-none');
    document.getElementById('cluster-progress-text').textContent = '启动中...';
    document.getElementById('cluster-progress-bar').style.width = '0%';
    document.getElementById('cluster-progress-bar').textContent = '0%';
    hideAlert();

    try {
        await apiFetch('/api/cluster/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ similarity_threshold: threshold })
        });
        startPolling();
    } catch (e) {
        showAlert(e.message);
        document.getElementById('btn-cluster').disabled = false;
        document.getElementById('cluster-progress').classList.add('d-none');
    }
}

function startPolling() {
    if (clusterPollingTimer) clearInterval(clusterPollingTimer);
    clusterPollingTimer = setInterval(pollClusterStatus, 1000);
}

function formatElapsed(seconds) {
    if (!seconds || seconds < 0) return '';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    if (m > 0) {
        return `已用时: ${m}分${s}秒`;
    }
    return `已用时: ${s}秒`;
}

async function pollClusterStatus() {
    try {
        const data = await apiFetch('/api/cluster/status');

        if (data.status === 'running') {
            document.getElementById('cluster-progress').classList.remove('d-none');

            // Update phase text
            const phaseText = document.getElementById('cluster-phase-text');
            if (data.phase_name) {
                phaseText.textContent = `${data.phase_name} (${data.phase_index || 0}/${data.total_phases || 5})`;
            }

            // Update elapsed time
            const elapsedEl = document.getElementById('cluster-elapsed');
            if (data.elapsed_seconds !== undefined) {
                elapsedEl.textContent = formatElapsed(data.elapsed_seconds);
            }

            // Update progress bar
            const bar = document.getElementById('cluster-progress-bar');
            const pct = data.overall_progress || 0;
            bar.style.width = `${pct}%`;
            bar.textContent = `${pct}%`;

            // Update detail text
            document.getElementById('cluster-progress-text').textContent = data.detail || data.progress || '处理中...';

        } else if (data.status === 'completed') {
            clearInterval(clusterPollingTimer);
            clusterPollingTimer = null;
            document.getElementById('cluster-progress').classList.add('d-none');
            document.getElementById('btn-cluster').disabled = false;

            const r = data.result;
            document.getElementById('cluster-status').innerHTML =
                `<span class="badge bg-success">聚类完成</span> ` +
                `${r.total_clusters} 个簇, ${r.noise_count} 个独立步骤 ` +
                `(阈值: ${r.threshold})`;

            showAlert(`聚类完成: 共 ${r.total_clusters} 个簇`, 'success');

            // Reload results panel
            if (typeof loadClusterResultsPanel === 'function') {
                loadClusterResultsPanel();
            }

        } else if (data.status === 'error') {
            clearInterval(clusterPollingTimer);
            clusterPollingTimer = null;
            document.getElementById('cluster-progress').classList.add('d-none');
            document.getElementById('btn-cluster').disabled = false;
            showAlert(`聚类错误: ${data.error}`);
        }
    } catch (e) {
        // Network error, keep polling
    }
}

async function loadClusterResultsPanel() {
    try {
        const data = await apiFetch('/api/cluster/current-summary');
        const panel = document.getElementById('cluster-results-panel');

        if (!data.summary || data.summary.total_clusters === 0) {
            panel.classList.add('d-none');
            return;
        }

        const s = data.summary;
        panel.classList.remove('d-none');

        document.getElementById('cluster-result-date').textContent = s.run_time || '';
        document.getElementById('cluster-result-summary').innerHTML =
            `模型: <strong>${s.model_name || '-'}</strong> | ` +
            `阈值: <strong>${s.similarity_threshold || '-'}</strong> | ` +
            `耗时: <strong>${formatElapsed(s.elapsed_seconds)}</strong><br>` +
            `簇数量: <strong>${s.total_clusters}</strong> | ` +
            `噪声步骤: <strong>${s.noise_count}</strong> | ` +
            `总步骤: <strong>${s.total_steps}</strong>`;

        // Load top 10 clusters
        const tbody = document.getElementById('cluster-top10-body');
        if (data.top_clusters && data.top_clusters.length > 0) {
            tbody.innerHTML = data.top_clusters.map((c, i) =>
                `<tr>
                    <td>${i + 1}</td>
                    <td>${c.label}</td>
                    <td><span class="badge bg-secondary">${c.step_count}</span></td>
                    <td><span class="badge bg-info">${c.case_count}</span></td>
                </tr>`
            ).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="4" class="text-muted text-center">暂无数据</td></tr>';
        }
    } catch (e) {
        // No results panel to show
        const panel = document.getElementById('cluster-results-panel');
        if (panel) panel.classList.add('d-none');
    }
}
