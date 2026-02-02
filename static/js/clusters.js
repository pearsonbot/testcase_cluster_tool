async function loadClusters() {
    try {
        const params = new URLSearchParams(window.location.search);
        const historyId = params.get('history_id');
        let url = '/api/cluster/list';
        if (historyId) {
            url += `?history_id=${historyId}`;
        }

        const data = await apiFetch(url);

        if (!data.clusters || data.clusters.length === 0) {
            document.getElementById('clusters-table').classList.add('d-none');
            document.getElementById('no-clusters').classList.remove('d-none');
            document.getElementById('cluster-summary').innerHTML =
                '<span class="text-muted">暂无聚类结果</span>';
            return;
        }

        const totalSteps = data.clusters.reduce((sum, c) => sum + c.step_count, 0);
        const historyLabel = historyId ? ` <span class="badge bg-warning text-dark">历史记录 #${historyId}</span>` : '';
        document.getElementById('cluster-summary').innerHTML =
            `<span class="badge bg-primary">${data.clusters.length} 个簇</span> ` +
            `覆盖 ${totalSteps} 条步骤` + historyLabel;

        const detailSuffix = historyId ? `?history_id=${historyId}` : '';
        const tbody = document.getElementById('clusters-body');
        tbody.innerHTML = data.clusters.map(c =>
            `<tr>
                <td>${c.cluster_id}</td>
                <td>${c.label}</td>
                <td><span class="badge bg-secondary">${c.step_count}</span></td>
                <td><span class="badge bg-info">${c.case_count}</span></td>
                <td><a href="/clusters/${c.cluster_id}${detailSuffix}" class="btn btn-sm btn-outline-primary">查看详情</a></td>
            </tr>`
        ).join('');

    } catch (e) {
        showAlert(e.message);
    }
}
