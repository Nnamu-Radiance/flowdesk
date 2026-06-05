class DashboardPage {
  constructor(user, root) {
    this.user = user;
    this.root = root;
    this.role = FlowDeskShell.roleOf(user);
  }

  async init() {
    this.root.innerHTML = `
      <section id="dashboard-stats" class="stats-row"></section>
      <section class="card">
        <div class="card-hd">
          <h2 class="card-title">Recent activity</h2>
          <a class="btn btn-sm btn-secondary" href="/static/pages/workflows.html">View all</a>
        </div>
        <div id="recent-table">Loading recent activity...</div>
      </section>
    `;
    await Promise.all([this.loadStats(), this.loadRecent()]);
    FlowDeskShell.onLive('workflow.status_changed', () => this.loadRecent());
    FlowDeskShell.onLive('approval.decision', () => this.loadRecent());
  }

  async loadStats() {
    const data = await AnalyticsAPI.dashboard().catch(() => ({}));
    const cards = this.cardsForRole(data);
    document.getElementById('dashboard-stats').innerHTML = cards.map((card) => `
      <article class="stat">
        <div class="stat-label">${FlowDeskShell.esc(card.label)}</div>
        <div class="stat-val">${FlowDeskShell.esc(card.value)}</div>
        <div class="stat-sub">${FlowDeskShell.esc(card.sub || '')}</div>
      </article>
    `).join('');
  }

  cardsForRole(data) {
    if (this.role === 'approver') {
      return [
        { label: 'Pending approvals', value: data.pending_approvals ?? data.pending ?? 0 },
        { label: 'Approved today', value: data.approved_today ?? 0 },
        { label: 'Avg response time', value: `${data.avg_response_hours ?? data.avg_response_time ?? 0}h` },
        { label: 'Overdue', value: data.overdue ?? 0 },
      ];
    }
    if (this.role === 'admin') {
      return [
        { label: 'Total workflows', value: data.total_workflows ?? 0 },
        { label: 'Pending approvals', value: data.pending_approvals ?? data.pending ?? 0 },
        { label: 'Approved', value: data.approved ?? 0 },
        { label: 'Rejected', value: data.rejected ?? 0 },
      ];
    }
    return [
      { label: 'My workflows', value: data.my_workflows ?? data.total_workflows ?? 0 },
      { label: 'In approval', value: data.in_approval ?? data.pending_approvals ?? 0 },
      { label: 'Completed', value: data.completed ?? data.approved ?? 0 },
      { label: 'SLA health', value: `${data.sla_health ?? data.sla_health_percentage ?? 100}%` },
    ];
  }

  async loadRecent() {
    const payload = await WorkflowAPI.list({ page_size: 8 }).catch(() => ({ results: [] }));
    const rows = FlowDeskShell.results(payload);
    const table = document.getElementById('recent-table');
    if (!rows.length) {
      table.innerHTML = '<div style="text-align:center;padding:28px;color:#64748b;font-size:11px">No workflow activity yet.</div>';
      return;
    }
    table.innerHTML = `
      <table class="tbl">
        <thead><tr><th>Request type</th><th>Reference</th><th>Current stage</th><th>SLA</th><th>Status</th></tr></thead>
        <tbody>${rows.map((item) => `
          <tr data-href="/static/pages/workflow-detail.html?id=${item.id}">
            <td>${FlowDeskShell.esc(item.workflow_type_detail?.name || item.name || item.approval_type || 'Workflow')}</td>
            <td class="mono">${FlowDeskShell.esc(item.document?.doc_id || `WF-${item.id}`)}</td>
            <td>${FlowDeskShell.esc(this.stageText(item))}</td>
            <td>${this.slaBar(item)}</td>
            <td>${this.statusPill(item.status)}</td>
          </tr>
        `).join('')}</tbody>
      </table>
    `;
    table.querySelectorAll('tr[data-href]').forEach((row) => {
      row.addEventListener('click', () => { window.location.href = row.dataset.href; });
    });
  }

  stageText(item) {
    const meta = item.metadata || {};
    if (item.status === 'approved') return meta.latest_comment || 'Approved by final office';
    if (item.status === 'rejected') return meta.latest_comment || 'Feedback available';
    const total = item.workflow_type_detail?.approval_chain?.length || meta.total_steps || 0;
    const current = meta.current_step || 1;
    if (total) return `${Math.max(total - current + 1, 0)} steps remaining`;
    return item.status === 'draft' ? 'Draft' : 'In review';
  }

  statusPill(status) {
    const map = { approved: 'pill-green', rejected: 'pill-red', in_approval: 'pill-amber', submitted: 'pill-blue', draft: 'pill-gray' };
    return `<span class="pill ${map[status] || 'pill-gray'}">${FlowDeskShell.titleCase(status || 'Unknown')}</span>`;
  }

  slaBar(item) {
    const pct = Math.min(Number(item.sla_percentage || 0), 100);
    const cls = pct >= 100 || item.sla_status === 'overdue' ? 'danger' : pct >= 50 ? 'warning' : '';
    return `<div class="sla-bar"><div class="sla-track"><div class="sla-fill ${cls}" style="width:${pct}%"></div></div><span class="text-gray-500">${FlowDeskShell.esc(item.remaining_time || `${pct}%`)}</span></div>`;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const { user, root } = await FlowDeskShell.initPage({ activePage: 'dashboard', title: 'Dashboard', allowedRoles: ['submitter', 'approver', 'admin'] });
    await new DashboardPage(user, root).init();
  } catch (error) {
    if (error.message !== 'Not authenticated' && error.message !== 'Access denied') showToast(`Failed to load dashboard: ${error.message}`, 'error');
  }
});
