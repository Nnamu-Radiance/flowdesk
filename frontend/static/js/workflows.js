class WorkflowManager {
  constructor() {
    this.currentPage = 1;
    this.bindRealtimeHandler = this.bindRealtimeHandler.bind(this);
  }

  init() {
    document
      .getElementById('status-filter')
      ?.addEventListener('change', () => this.load());

    document
      .getElementById('search-input')
      ?.addEventListener('input', debounce(() => this.load(), 300));

    document
      .getElementById('upload-form')
      ?.addEventListener('submit', (event) => this.handleUpload(event));

    this.bindRealtimeHandler();
    document.addEventListener('flowdesk:notifications-ready', this.bindRealtimeHandler);

    this.load();
  }

  async load() {
    const params = {
      status: document.getElementById('status-filter')?.value || '',
      search: document.getElementById('search-input')?.value || '',
      page: this.currentPage,
    };

    try {
      const result = await WorkflowAPI.list(params);
      this.render(result.results || []);
    } catch (error) {
      showToast(`Failed to load workflows: ${error.message}`, 'error');
    }
  }

  async refreshWorkflowCard(workflowId) {
    try {
      const workflow = await WorkflowAPI.get(workflowId);
      const card = document.querySelector(`[data-workflow-id="${workflowId}"]`);
      if (!card) return;
      const badge = card.querySelector('.badge');
      if (badge) badge.textContent = workflow.status;
    } catch (error) {
      // No-op.
    }
  }

  bindRealtimeHandler() {
    if (!window.notificationManager) return;
    window.notificationManager.on('approval.decision', (payload) => {
      if (payload.workflow_id) this.refreshWorkflowCard(payload.workflow_id);
    });
  }

  async handleUpload(event) {
    event.preventDefault();

    const formData = new FormData(event.target);
    try {
      await WorkflowAPI.upload(formData);
      showToast('Workflow created and processing started.', 'success');
      event.target.reset();
      this.load();
    } catch (error) {
      showToast(`Upload failed: ${error.message}`, 'error');
    }
  }

  render(workflows) {
    const container = document.getElementById('workflows-container');
    if (!container) return;

    if (!workflows.length) {
      container.innerHTML = '<p class="text-gray-500">No workflows found.</p>';
      return;
    }

    container.innerHTML = workflows
      .map(
        (item) => `
      <article class="card" data-workflow-id="${item.id}">
        <header class="card-header">
          <h3 class="text-lg font-semibold">${item.name}</h3>
          <span class="badge badge-warning">${item.status}</span>
        </header>
        <p class="text-sm text-gray-600">${item.document?.filename || 'No document attached'}</p>
        <div class="mt-4 text-xs text-gray-500 flex justify-between">
          <span>Created: ${formatDate(item.created_at)}</span>
          <span>SLA: ${item.sla_status || 'unknown'}</span>
        </div>
      </article>
    `
      )
      .join('');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const manager = new WorkflowManager();
  manager.init();
});
