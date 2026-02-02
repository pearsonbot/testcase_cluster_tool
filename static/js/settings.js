function toggleModelFields() {
    const modelType = document.querySelector('input[name="model_type"]:checked').value;
    document.getElementById('local-fields').classList.toggle('d-none', modelType !== 'local');
    document.getElementById('api-fields').classList.toggle('d-none', modelType !== 'api');
}

async function loadSettings() {
    try {
        const data = await apiFetch('/api/settings/');
        const s = data.settings;

        const modelType = s.model_type || 'builtin';
        const radio = document.getElementById(`model-${modelType}`);
        if (radio) radio.checked = true;

        document.getElementById('model-path').value = s.model_path || '';
        document.getElementById('api-url').value = s.api_url || '';
        document.getElementById('api-key').value = s.api_key || '';
        document.getElementById('api-model-name').value = s.api_model_name || '';

        toggleModelFields();
    } catch (e) {
        showAlert('加载设置失败: ' + e.message);
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
        showAlert('设置保存成功', 'success');
    } catch (e) {
        showAlert('保存设置失败: ' + e.message);
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
    resultEl.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div> 测试中...';
    resultEl.className = 'mt-3 alert alert-info';

    try {
        const data = await apiFetch('/api/settings/test-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        resultEl.innerHTML = `<i class="bi bi-check-circle"></i> 模型测试成功！ ` +
            `模型: ${data.model_name}, 向量维度: ${data.dimension}`;
        resultEl.className = 'mt-3 alert alert-success';
    } catch (e) {
        resultEl.innerHTML = `<i class="bi bi-x-circle"></i> 模型测试失败: ${e.message}`;
        resultEl.className = 'mt-3 alert alert-danger';
    }
}
