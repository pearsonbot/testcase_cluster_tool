async function exportResults() {
    try {
        const resp = await fetch('/api/export/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        if (!resp.ok) {
            const data = await resp.json();
            throw new Error(data.error || `HTTP ${resp.status}`);
        }

        // Download the zip
        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'clustering_results.zip';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showAlert('Export completed successfully!', 'success');
    } catch (e) {
        showAlert(e.message);
    }
}
