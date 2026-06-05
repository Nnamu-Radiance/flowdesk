const AdminAPI = {
  workflowTypes: () => api.get('/api/admin/approval-types/'),
  createWorkflowType: (payload) => api.post('/api/admin/approval-types/', payload),
  chains: () => api.get('/api/admin/approval-chains/'),
  createChain: (payload) => api.post('/api/admin/approval-chains/', payload),
  replaceSteps: (chainId, steps) => api.request('PUT', `/api/admin/approval-chains/${chainId}/steps/`, { steps }),
  approvers: () => api.get('/api/admin/users/?role=approver'),
};

const AdminConfig = (() => {
  const state = {
    workflowTypes: [],
    chains: [],
    approvers: [],
    expandedTypeId: null,
    csvPreviewWorkflows: [],
    pendingCsvWorkflows: [],
    expandedCsvIndex: null,
    selectedCsvFile: null,
    csvBusy: false,
  };

  const csvFormat = [
    'name,approval_type,description,deadline,priority,tags,metadata',
    'Laptop Purchase,Procurement,Approve laptop request,2026-06-01T17:00:00Z,2,finance;urgent,"{""stop_1"":""Manager"",""required_documents"":""invoice|memo""}"',
  ].join('\n');

  const byId = (id) => document.getElementById(id);
  const results = (payload) => payload?.results || payload || [];

  const escapeHtml = (value) => String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  const approverLabel = (approver) => {
    const fullName = [approver.first_name, approver.last_name].filter(Boolean).join(' ').trim();
    return fullName || approver.username || approver.email || `User ${approver.id}`;
  };

  const chainsForType = (typeId) => state.chains.filter((chain) => Number(chain.workflow_type) === Number(typeId));

  const normalizeImplementedWorkflows = (payload) => {
    const workflows = payload.workflows || payload.created_workflows || payload.preview || state.pendingCsvWorkflows;
    return (workflows || []).map((workflow, index) => {
      const fallback = state.pendingCsvWorkflows.find((item) => item.name === workflow.name) || state.pendingCsvWorkflows[index] || {};
      const stops = workflow.approval_stops || fallback.approval_stops || [];
      const documents = workflow.document_requirements || workflow.required_documents || fallback.document_requirements || [];

      return {
        ...fallback,
        ...workflow,
        approval_type: workflow.approval_type || fallback.approval_type || '',
        approval_stops: stops.map((stop) => (typeof stop === 'string' ? stop : stop.name)).filter(Boolean),
        document_requirements: documents,
      };
    });
  };

  const setWorkflowCardMode = (mode) => {
    byId('workflow-card-title').textContent = mode === 'csv' ? 'Workflows From CSV' : 'Workflow Types';
    byId('new-workflow-type').classList.toggle('hidden', mode === 'csv');
    byId('workflow-type-form').classList.add('hidden');
  };

  const renderCsvWorkflows = () => {
    const container = byId('workflow-types-list');
    if (!container) return;

    setWorkflowCardMode('csv');
    container.innerHTML = state.csvPreviewWorkflows.map((workflow, index) => {
      const expanded = Number(state.expandedCsvIndex) === index;
      const stops = workflow.approval_stops || [];
      const documents = workflow.document_requirements || [];
      const tags = workflow.tags || [];

      return `
        <section class="workflow-type-item">
          <button class="workflow-type-toggle" type="button" data-action="toggle-csv-workflow" data-workflow-index="${index}">
            <span>
              <strong>${escapeHtml(workflow.name)}</strong>
              <span class="block text-sm text-gray-600">${escapeHtml(workflow.approval_type || 'Unassigned workflow type')}</span>
            </span>
            <span class="text-sm text-gray-600">${expanded ? 'Collapse' : 'Expand'}</span>
          </button>
          <div class="workflow-type-panel ${expanded ? '' : 'hidden'}">
            <div class="csv-workflow-detail">
              <p class="text-sm text-gray-600">${escapeHtml(workflow.description || 'No description provided.')}</p>
              <div class="detail-grid">
                <span>Priority: ${escapeHtml(workflow.priority || 1)}</span>
                <span>Deadline: ${escapeHtml(workflow.deadline ? formatDate(workflow.deadline) : 'None')}</span>
                <span>Tags: ${escapeHtml(tags.length ? tags.join(', ') : 'None')}</span>
              </div>
              <section class="chain-item">
                <strong>Approval Steps</strong>
                <ol class="step-list">
                  ${stops.length ? stops.map((stop) => `<li>${escapeHtml(stop)}</li>`).join('') : '<li>No approval steps defined.</li>'}
                </ol>
              </section>
              <section class="chain-item">
                <strong>Required Documents</strong>
                <ol class="step-list">
                  ${documents.length ? documents.map((doc) => `<li>${escapeHtml(doc.label || doc.document_slug)}</li>`).join('') : '<li>No required documents.</li>'}
                </ol>
              </section>
            </div>
          </div>
        </section>
      `;
    }).join('');
  };

  const renderWorkflowTypes = () => {
    const container = byId('workflow-types-list');
    if (!container) return;

    if (state.csvPreviewWorkflows.length) {
      renderCsvWorkflows();
      return;
    }

    setWorkflowCardMode('types');
    if (!state.workflowTypes.length) {
      container.innerHTML = '<p class="text-sm text-gray-600">No workflow types yet.</p>';
      return;
    }

    container.innerHTML = state.workflowTypes.map((type) => {
      const chains = chainsForType(type.id);
      const expanded = Number(state.expandedTypeId) === Number(type.id);
      const chainMarkup = chains.length ? chains.map((chain) => `
        <section class="chain-item">
          <strong>${escapeHtml(chain.name)}</strong>
          <ol class="step-list">
            ${(chain.steps || []).length ? chain.steps.map((step) => `
              <li>${escapeHtml(step.approver_name || step.approver || 'Approver')} ${step.role_required ? `- ${escapeHtml(step.role_required)}` : ''}</li>
            `).join('') : '<li>No steps configured.</li>'}
          </ol>
        </section>
      `).join('') : '<p class="text-sm text-gray-600">No chains yet. Add the first approval step below.</p>';

      const approverOptions = state.approvers.map((approver) => `
        <option value="${approver.id}">${escapeHtml(approverLabel(approver))}</option>
      `).join('');

      return `
        <section class="workflow-type-item">
          <button class="workflow-type-toggle" type="button" data-action="toggle-type" data-type-id="${type.id}">
            <span>
              <strong>${escapeHtml(type.name)}</strong>
              <span class="block text-sm text-gray-600">${type.sla_hours} SLA hours</span>
            </span>
            <span class="text-sm text-gray-600">${chains.length} chain${chains.length === 1 ? '' : 's'} ${expanded ? 'Collapse' : 'Expand'}</span>
          </button>
          <div class="workflow-type-panel ${expanded ? '' : 'hidden'}">
            <div class="chain-list">${chainMarkup}</div>
            <form class="chain-form" data-action="create-chain" data-type-id="${type.id}">
              <input class="form-input" name="name" type="text" placeholder="Chain name" required>
              <select class="form-input" name="approver" required>
                <option value="">Choose approver</option>
                ${approverOptions}
              </select>
              <input class="form-input" name="role_required" type="text" placeholder="Role label, e.g. Manager">
              <div class="chain-form-actions">
                <button class="btn btn-primary" type="submit">Add Chain Step</button>
              </div>
            </form>
          </div>
        </section>
      `;
    }).join('');
  };

  const loadAdminData = async () => {
    const [types, chains, approvers] = await Promise.all([
      AdminAPI.workflowTypes(),
      AdminAPI.chains(),
      AdminAPI.approvers(),
    ]);

    state.workflowTypes = results(types);
    state.chains = results(chains);
    state.approvers = results(approvers);
    if (!state.expandedTypeId && state.workflowTypes.length) {
      state.expandedTypeId = state.workflowTypes[0].id;
    }
    renderWorkflowTypes();
  };

  const resetCsv = ({ clearWorkflows = true } = {}) => {
    state.selectedCsvFile = null;
    state.pendingCsvWorkflows = [];
    if (clearWorkflows) {
      state.csvPreviewWorkflows = [];
      state.expandedCsvIndex = null;
    }
    byId('workflow-csv-file').value = '';
    byId('csv-preview-panel').classList.add('hidden');
    byId('csv-empty-state').classList.remove('hidden');
    byId('csv-summary').innerHTML = '';
    byId('csv-preview-list').innerHTML = '';
    renderWorkflowTypes();
  };

  const showCsvErrors = (errors) => {
    byId('csv-error-list').innerHTML = (errors.length ? errors : [{ row: 1, error: 'No valid workflow rows were found.' }]).map((item) => `
      <div class="csv-error-item">
        <strong>Row ${escapeHtml(item.row || '-')}</strong>
        <span class="block">${escapeHtml(item.error || item.detail || item)}</span>
      </div>
    `).join('');
    byId('csv-error-modal').classList.remove('hidden');
  };

  const renderCsvPreview = (payload) => {
    const preview = payload.preview || [];
    state.pendingCsvWorkflows = preview;

    byId('csv-empty-state').classList.add('hidden');
    byId('csv-preview-panel').classList.remove('hidden');
    byId('csv-summary').textContent = `${payload.valid_rows} workflow${payload.valid_rows === 1 ? '' : 's'} ready to implement`;
    byId('csv-preview-list').innerHTML = preview.map((row, index) => `
      <article class="csv-preview-row" style="animation-delay: ${index * 65}ms">
        <strong>${escapeHtml(row.name)}</strong>
        <p class="text-sm text-gray-600">${escapeHtml(row.description || 'No description')}</p>
        <div class="csv-preview-meta">
          <span>Type: ${escapeHtml(row.approval_type || 'Unassigned')}</span>
          <span>Priority: ${escapeHtml(row.priority || 1)}</span>
          <span>Stops: ${escapeHtml((row.approval_stops || []).join(' > ') || 'None')}</span>
          <span>Documents: ${escapeHtml((row.document_requirements || []).map((doc) => doc.label).join(', ') || 'None')}</span>
        </div>
      </article>
    `).join('');
  };

  const dryRunCsv = async (file) => {
    state.selectedCsvFile = file;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const payload = await WorkflowConfigAPI.upload(formData);
      if (payload.errors && payload.errors.length) {
        showCsvErrors(payload.errors);
        return;
      }
      showToast(`Config loaded: ${payload.created} created, ${payload.updated} updated.`, 'success');
      renderCsvPreview({
        valid_rows: payload.created + payload.updated,
        preview: state.pendingCsvWorkflows,
      });
    } catch (error) {
      showCsvErrors([{ row: 1, error: error.message }]);
    }
  };


  const implementCsv = async () => {
    showToast('Configuration already saved when you uploaded the file.', 'success');
    resetCsv();
  };

  const bindEvents = () => {
    byId('configure-workflow')?.addEventListener('click', () => byId('workflow-csv-file').click());
    byId('choose-workflow-csv')?.addEventListener('click', () => byId('workflow-csv-file').click());
    byId('workflow-csv-file')?.addEventListener('change', (event) => {
      const file = event.target.files?.[0];
      if (file) dryRunCsv(file);
    });
    byId('implement-csv')?.addEventListener('click', implementCsv);
    byId('cancel-csv')?.addEventListener('click', resetCsv);
    byId('close-csv-error')?.addEventListener('click', () => byId('csv-error-modal').classList.add('hidden'));

    byId('new-workflow-type')?.addEventListener('click', () => {
      byId('workflow-type-form').classList.toggle('hidden');
      byId('workflow-type-name').focus();
    });

    byId('workflow-type-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const name = byId('workflow-type-name').value.trim();
      const slaHours = Number(byId('workflow-type-sla').value || 48);
      if (!name) return;

      try {
        const created = await AdminAPI.createWorkflowType({ name, sla_hours: slaHours });
        state.workflowTypes.push(created);
        state.expandedTypeId = created.id;
        event.target.reset();
        byId('workflow-type-sla').value = '48';
        event.target.classList.add('hidden');
        renderWorkflowTypes();
        showToast('Workflow type added.', 'success');
      } catch (error) {
        showToast(`Could not add workflow type: ${error.message}`, 'error');
      }
    });

    byId('workflow-types-list')?.addEventListener('click', (event) => {
      const toggle = event.target.closest('[data-action]');
      if (!toggle) return;
      if (toggle.dataset.action === 'toggle-csv-workflow') {
        const workflowIndex = Number(toggle.dataset.workflowIndex);
        state.expandedCsvIndex = state.expandedCsvIndex === workflowIndex ? null : workflowIndex;
        renderCsvWorkflows();
        return;
      }
      if (toggle.dataset.action !== 'toggle-type') return;
      const typeId = Number(toggle.dataset.typeId);
      state.expandedTypeId = state.expandedTypeId === typeId ? null : typeId;
      renderWorkflowTypes();
    });

    byId('workflow-types-list')?.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-action="create-chain"]');
      if (!form) return;
      event.preventDefault();

      const typeId = Number(form.dataset.typeId);
      const formData = new FormData(form);
      const approver = Number(formData.get('approver'));
      if (!approver) {
        showToast('Choose an approver before adding a chain step.', 'error');
        return;
      }

      try {
        const chain = await AdminAPI.createChain({
          workflow_type: typeId,
          name: formData.get('name'),
        });
        const updated = await AdminAPI.replaceSteps(chain.id, [{
          order: 1,
          approver,
          role_required: formData.get('role_required') || '',
        }]);
        state.chains.push(updated);
        form.reset();
        renderWorkflowTypes();
        showToast('Approval chain added.', 'success');
      } catch (error) {
        showToast(`Could not add chain: ${error.message}`, 'error');
      }
    });
  };

  const init = async () => {
    if (!AuthManager.isAdmin()) {
      window.location.href = '/';
      return;
    }

    bindEvents();
    try {
      await loadAdminData();
    } catch (error) {
      showToast(`Admin configuration failed to load: ${error.message}`, 'error');
    }
  };

  return { init };
})();

document.addEventListener('DOMContentLoaded', AdminConfig.init);
