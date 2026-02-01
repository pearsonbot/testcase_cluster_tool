let clusterPollingTimer = null;

async function loadModelInfo() {
    try {
        const data = await apiFetch('/api/settings/');
        const modelType = data.settings.model_type || 'builtin';
        const el = document.getElementById('model-name');
        if (modelType === 'builtin') {
            el.textContent = 'text2vec-base-chinese (built-in)';
            el.className = 'badge bg-info';
        } else if (modelType === 'local') {
            el.textContent = `Local: ${data.settings.model_path || 'not set'}`;
            el.className = 'badge bg-success';
        } else if (modelType === 'api') {
            el.textContent = `API: ${data.settings.api_model_name || 'not set'}`;
            el.className = 'badge bg-warning text-dark';
        }
    } catch (e) {
        document.getElementById('model-name').textContent = 'Not configured';
    }
}

async function loadClusterStatus() {
    try {
        const data = await apiFetch('/api/cluster/status');
        const el = document.getElementById('cluster-status');

        if (data.status === 'completed' && data.result) {
            el.innerHTML = `<span class="badge bg-success">Clustering completed</span> ` +
                `${data.result.total_clusters} clusters, ${data.result.noise_count} independent steps ` +
                `(threshold: ${data.result.threshold})`;
        } else if (data.status === 'running') {
            el.innerHTML = '<span class="badge bg-warning text-dark">Running...</span>';
            startPolling();
        } else if (data.status === 'error') {
            el.innerHTML = `<span class="badge bg-danger">Error</span> ${data.error}`;
        } else {
            // Check if there are saved results
            const listData = await apiFetch('/api/cluster/list');
            if (listData.clusters && listData.clusters.length > 0) {
                const totalSteps = listData.clusters.reduce((sum, c) => sum + c.step_count, 0);
                el.innerHTML = `<span class="badge bg-success">Clustering available</span> ` +
                    `${listData.clusters.length} clusters`;
            } else {
                el.innerHTML = '<span class="text-muted">Not yet run</span>';
            }
        }
    } catch (e) {
        document.getElementById('cluster-status').textContent = 'Failed to load status';
    }
}

async function runClustering() {
    const threshold = parseFloat(document.getElementById('threshold-slider').value);

    document.getElementById('btn-cluster').disabled = true;
    document.getElementById('cluster-progress').classList.remove('d-none');
    document.getElementById('cluster-progress-text').textContent = 'Starting...';
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
    clusterPollingTimer = setInterval(pollClusterStatus, 2000);
}

async function pollClusterStatus() {
    try {
        const data = await apiFetch('/api/cluster/status');

        if (data.status === 'running') {
            document.getElementById('cluster-progress').classList.remove('d-none');
            document.getElementById('cluster-progress-text').textContent = data.progress || 'Processing...';
        } else if (data.status === 'completed') {
            clearInterval(clusterPollingTimer);
            clusterPollingTimer = null;
            document.getElementById('cluster-progress').classList.add('d-none');
            document.getElementById('btn-cluster').disabled = false;

            const r = data.result;
            document.getElementById('cluster-status').innerHTML =
                `<span class="badge bg-success">Clustering completed</span> ` +
                `${r.total_clusters} clusters, ${r.noise_count} independent steps ` +
                `(threshold: ${r.threshold})`;

            showAlert(`Clustering completed: ${r.total_clusters} clusters found`, 'success');
        } else if (data.status === 'error') {
            clearInterval(clusterPollingTimer);
            clusterPollingTimer = null;
            document.getElementById('cluster-progress').classList.add('d-none');
            document.getElementById('btn-cluster').disabled = false;
            showAlert(`Clustering error: ${data.error}`);
        }
    } catch (e) {
        // Network error, keep polling
    }
}
