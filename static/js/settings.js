function toggleModelFields() {
    const modelType = document.querySelector('input[name="model_type"]:checked').value;
    document.getElementById('local-fields').classList.toggle('d-none', modelType !== 'local');
    document.getElementById('api-fields').classList.toggle('d-none', modelType !== 'api');
}

async function loadSettings() {
    try {
        const data = await apiFetch('/api/settings/');
        const s = data.settings;

        // Set radio button
        const modelType = s.model_type || 'builtin';
        const radio = document.getElementById(`model-${modelType}`);
        if (radio) radio.checked = true;

        // Set input fields
        document.getElementById('model-path').value = s.model_path || '';
        document.getElementById('api-url').value = s.api_url || '';
        document.getElementById('api-key').value = s.api_key || '';
        document.getElementById('api-model-name').value = s.api_model_name || '';

        toggleModelFields();
    } catch (e) {
        showAlert('Failed to load settings: ' + e.message);
    }
}

async function saveSettings() {
    const modelType = document.querySelector('input[name="model_type"]:checked').value;
    const settings = {
        model_type: modelType,
        model_path: document.getElementById('model-path').value,
        api_url: document.getElementById('api-url').value,
        api_key: document.getElementById('api-key').value,
        api_model_name: document.getElementById('api-model-name').value,
    };

    try {
        await apiFetch('/api/settings/', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        showAlert('Settings saved successfully!', 'success');
    } catch (e) {
        showAlert('Failed to save settings: ' + e.message);
    }
}

async function testModel() {
    const modelType = document.querySelector('input[name="model_type"]:checked').value;
    const settings = {
        model_type: modelType,
        model_path: document.getElementById('model-path').value,
        api_url: document.getElementById('api-url').value,
        api_key: document.getElementById('api-key').value,
        api_model_name: document.getElementById('api-model-name').value,
    };

    const resultEl = document.getElementById('test-result');
    resultEl.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div> Testing...';
    resultEl.className = 'mt-3 alert alert-info';

    try {
        const data = await apiFetch('/api/settings/test-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        resultEl.innerHTML = `<i class="bi bi-check-circle"></i> Model test successful! ` +
            `Model: ${data.model_name}, Dimension: ${data.dimension}`;
        resultEl.className = 'mt-3 alert alert-success';
    } catch (e) {
        resultEl.innerHTML = `<i class="bi bi-x-circle"></i> Model test failed: ${e.message}`;
        resultEl.className = 'mt-3 alert alert-danger';
    }
}
