class ApprovalPage {
  async load() {
    const data = await ApprovalAPI.pending();
    this.render(data.results || data || []);
  }

  render(items) {
    const container = document.getElementById('approval-list');
    if (!container) return;

    if (!items.length) {
      container.innerHTML = '<p class="text-gray-500">No pending approvals.</p>';
      return;
    }

    container.innerHTML = items
      .map(
        (item) => `
      <article class="card" data-approval-id="${item.id}">
        <header class="card-header">
          <h3 class="font-semibold">Workflow #${item.workflow_id}</h3>
          <span class="badge badge-warning">Pending</span>
        </header>
        <p class="text-sm text-gray-600">Deadline: ${formatDate(item.deadline)}</p>
        <div class="mt-4 flex gap-2">
          <button class="btn btn-primary btn-sm" data-action="approve" data-id="${item.id}">Approve</button>
          <button class="btn btn-danger btn-sm" data-action="reject" data-id="${item.id}">Reject</button>
        </div>
      </article>
    `
      )
      .join('');

    container.querySelectorAll('button[data-action]').forEach((button) => {
      button.addEventListener('click', () => this.handleAction(button));
    });
  }

  async handleAction(button) {
    const id = button.dataset.id;
    const action = button.dataset.action;

    try {
      if (action === 'approve') {
        await ApprovalAPI.approve(id, 'Approved from dashboard');
      }
      if (action === 'reject') {
        await ApprovalAPI.reject(id, 'Rejected from dashboard');
      }

      showToast(`Approval ${action}d successfully.`, 'success');
      this.load();
    } catch (error) {
      showToast(`Action failed: ${error.message}`, 'error');
    }
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const page = new ApprovalPage();
  try {
    await page.load();
  } catch (error) {
    showToast(`Failed to load approvals: ${error.message}`, 'error');
  }
});
