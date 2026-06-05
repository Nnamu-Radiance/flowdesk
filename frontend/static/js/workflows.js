class WorkflowManager {
  constructor(root) {
    this.root = root;
    this.items = [];
  }

  async init() {
    this.root.innerHTML = `
      <section class="card">
        <div class="form-row">
          <input id="search-input" class="form-input" type="search" placeholder="Search by request type or reference">
          <select id="status-filter" class="form-select">
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="in_approval">In Approval</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
      </section>
      <section class="card">
        <div class="card-hd"><h2 class="card-title">My workflows</h2></div>
        <div id="workflows-container">Loading workflows...</div>
      </section>
    `;
    document.getElementById('status-filter').addEventListener('change', () => this.render());
    document.getElementById('search-input').addEventListener('input', debounce(() => this.render(), 150));
    FlowDeskShell.onLive('approval.decision', (payload) => this.handleDecision(payload));
    FlowDeskShell.onLive('approval.approved', (payload) => this.updateWorkflowStatus(payload.workflow_id, 'Approved', 'approved'));
    FlowDeskShell.onLive('approval.rejected', (payload) => this.updateWorkflowStatus(payload.workflow_id, 'Rejected', 'rejected'));
    FlowDeskShell.onLive('approval.returned', (payload) => this.updateWorkflowStatus(payload.workflow_id, 'Returned', 'returned'));
    FlowDeskShell.onLive('approval.step_completed', (payload) => this.updateWorkflowStage(payload.workflow_id, payload.next_role_display_name || payload.next_role || 'Next approver', payload.step_number, payload.total_steps));
    FlowDeskShell.onLive('approval.requested', (payload) => this.updateWorkflowStage(payload.workflow_id, payload.role_display_name, payload.step_number, payload.total_steps));
    FlowDeskShell.onLive('workflow.status_changed', () => this.load());
    await this.load();
  }

  async load() {
    const payload = await WorkflowAPI.list({ page_size: 100 });
    this.items = FlowDeskShell.results(payload);
    this.render();
  }

  filteredItems() {
    const status = document.getElementById('status-filter')?.value || '';
    const query = (document.getElementById('search-input')?.value || '').toLowerCase();
    return this.items.filter((item) => {
      const ref = item.document?.doc_id || `WF-${item.id}`;
      const name = item.workflow_type_detail?.name || item.name || item.approval_type || '';
      return (!status || item.status === status) && (!query || `${name} ${ref}`.toLowerCase().includes(query));
    });
  }

  render() {
    const container = document.getElementById('workflows-container');
    const workflows = this.filteredItems();
    if (!workflows.length) {
      container.innerHTML = `
        <div style="display:grid;place-items:center;gap:8px;padding:42px;text-align:center;color:#64748b">
          <i class="ti ti-files" style="font-size:28px" aria-hidden="true"></i>
          <strong style="color:#111827;font-size:12px">No requests yet</strong>
          <span style="font-size:11px">Create your first request using the New Request button</span>
          <a class="btn btn-primary btn-sm" href="/static/pages/new-request.html">Make a request</a>
        </div>
      `;
      return;
    }
    container.innerHTML = `
      <table class="tbl">
        <thead><tr><th>Request type</th><th>Reference</th><th>Submitted date</th><th>Current step</th><th>SLA</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>${workflows.map((item) => `
          <tr data-workflow-id="${item.id}" data-status="${FlowDeskShell.esc(item.status || '')}">
            <td>${FlowDeskShell.esc(item.workflow_type_detail?.name || item.name || item.approval_type || 'Workflow')}</td>
            <td class="mono">${FlowDeskShell.esc(item.document?.doc_id || `WF-${item.id}`)}</td>
            <td>${FlowDeskShell.fmtDate(item.submitted_at || item.created_at)}</td>
            <td class="current-stage">${FlowDeskShell.esc(this.stepText(item))}</td>
            <td>${this.slaBar(item)}</td>
            <td>${this.statusPill(item.status)}</td>
            <td>
              <div style="display:flex;gap:6px;align-items:center">
                ${item.status === 'draft' ? `<button class="btn btn-primary btn-sm" data-submit-id="${item.id}" type="button">Submit</button>` : ''}
                <a class="btn btn-sm btn-secondary" href="/static/pages/workflow-detail.html?id=${item.id}"><i class="ti ti-eye" aria-hidden="true"></i> View</a>
              </div>
            </td>
          </tr>
        `).join('')}</tbody>
      </table>
    `;
    container.querySelectorAll('[data-submit-id]').forEach((button) => {
      button.addEventListener('click', () => this.submitWorkflow(button.dataset.submitId, button));
    });
  }

  async submitWorkflow(id, button) {
    button.disabled = true;
    button.textContent = 'Submitting...';
    try {
      await WorkflowAPI.submit(id);
      showToast('Workflow submitted for approval.', 'success');
      await this.load();
    } catch (error) {
      showToast(`Submit failed: ${error.message}`, 'error');
      button.disabled = false;
      button.textContent = 'Submit';
    }
  }

  stepText(item) {
    const meta = item.metadata || {};
    const total = item.workflow_type_detail?.approval_chain?.length || meta.total_steps || 0;
    const current = meta.current_step || (item.status === 'draft' ? 0 : 1);
    return total ? `Step ${current} of ${total}` : FlowDeskShell.titleCase(item.status || 'Draft');
  }

  statusPill(status) {
    const map = { approved: 'pill-green', rejected: 'pill-red', returned: 'pill-amber', in_approval: 'pill-amber', submitted: 'pill-blue', draft: 'pill-gray' };
    return `<span class="pill ${map[status] || 'pill-gray'} status-badge">${FlowDeskShell.titleCase(status || 'Unknown')}</span>`;
  }

  slaBar(item) {
    const pct = Math.min(Number(item.sla_percentage || 0), 100);
    const cls = pct >= 100 || item.sla_status === 'overdue' ? 'danger' : pct >= 50 ? 'warning' : '';
    return `<div class="sla-bar"><div class="sla-track"><div class="sla-fill ${cls}" style="width:${pct}%"></div></div></div>`;
  }

  handleDecision(payload) {
    const status = payload.status || payload.decision || payload.action;
    if (!status) {
      this.load();
      return;
    }
    this.updateWorkflowStatus(payload.workflow_id, FlowDeskShell.titleCase(status), status);
  }

  updateWorkflowStatus(workflowId, label, statusClass) {
    const row = document.querySelector(`[data-workflow-id="${workflowId}"]`);
    const badge = row?.querySelector('.status-badge');
    if (!badge) return;
    const cls = statusClass === 'approved' ? 'pill-green' : statusClass === 'returned' ? 'pill-amber' : statusClass === 'rejected' ? 'pill-red' : 'pill-blue';
    row.dataset.status = statusClass;
    badge.textContent = label;
    badge.className = `pill ${cls} status-badge`;
  }

  updateWorkflowStage(workflowId, roleLabel, stepNumber, totalSteps) {
    const stageCell = document.querySelector(`[data-workflow-id="${workflowId}"] .current-stage`);
    if (!stageCell || !roleLabel) return;
    stageCell.textContent = stepNumber && totalSteps ? `Step ${stepNumber}/${totalSteps} - ${roleLabel}` : roleLabel;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const { user: currentUser, root } = await FlowDeskShell.initPage({ activePage: 'workflows', title: 'My workflows', allowedRoles: ['submitter'] });
    if (typeof connectNotificationSocket === 'function' && currentUser?.id) connectNotificationSocket(currentUser.id);
    window._workflowManager = new WorkflowManager(root);
    await window._workflowManager.init();
  } catch (error) {
    if (error.message !== 'Not authenticated' && error.message !== 'Access denied') showToast(`Failed to load workflows: ${error.message}`, 'error');
  }
});
