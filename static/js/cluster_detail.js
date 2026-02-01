async function loadClusterDetail(clusterId) {
    try {
        const data = await apiFetch(`/api/cluster/${clusterId}`);
        const cluster = data.cluster;

        document.getElementById('breadcrumb-label').textContent =
            `Cluster #${cluster.cluster_id}: ${cluster.label}`;
        document.getElementById('detail-header').textContent =
            `Cluster #${cluster.cluster_id}: ${cluster.label}`;

        document.getElementById('cluster-info').innerHTML =
            `<span class="badge bg-primary">Steps: ${cluster.step_count}</span> ` +
            `<span class="badge bg-info">Cases: ${cluster.case_count}</span>`;

        const tbody = document.getElementById('detail-body');
        tbody.innerHTML = data.steps.map(s =>
            `<tr>
                <td>${s.operation}</td>
                <td><a href="javascript:void(0)" onclick="goToCase('${s.case_id}')"><code>${s.case_id}</code></a></td>
                <td>${s.case_title}</td>
                <td>${s.step_no}</td>
            </tr>`
        ).join('');

    } catch (e) {
        showAlert(e.message);
    }
}

function goToCase(caseId) {
    window.location.href = `/?case=${encodeURIComponent(caseId)}`;
}
