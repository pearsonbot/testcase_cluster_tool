async function loadClusters() {
    try {
        const data = await apiFetch('/api/cluster/list');

        if (!data.clusters || data.clusters.length === 0) {
            document.getElementById('clusters-table').classList.add('d-none');
            document.getElementById('no-clusters').classList.remove('d-none');
            document.getElementById('cluster-summary').innerHTML =
                '<span class="text-muted">No clustering results available</span>';
            return;
        }

        const totalSteps = data.clusters.reduce((sum, c) => sum + c.step_count, 0);
        const totalCases = new Set(data.clusters.flatMap(c => [c.case_count])).size;
        document.getElementById('cluster-summary').innerHTML =
            `<span class="badge bg-primary">${data.clusters.length} clusters</span> ` +
            `covering ${totalSteps} steps`;

        const tbody = document.getElementById('clusters-body');
        tbody.innerHTML = data.clusters.map(c =>
            `<tr>
                <td>${c.cluster_id}</td>
                <td>${c.label}</td>
                <td><span class="badge bg-secondary">${c.step_count}</span></td>
                <td><span class="badge bg-info">${c.case_count}</span></td>
                <td><a href="/clusters/${c.cluster_id}" class="btn btn-sm btn-outline-primary">View Detail</a></td>
            </tr>`
        ).join('');

    } catch (e) {
        showAlert(e.message);
    }
}
