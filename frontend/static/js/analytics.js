class AnalyticsPage {
  constructor(root) {
    this.root = root;
  }

  async init() {
    this.root.innerHTML = `
      <section class="stats-row" id="analytics-stats"></section>
      <section class="card"><div class="card-hd"><h2 class="card-title">SLA report</h2></div><div id="sla-report">Loading...</div></section>
      <section class="card"><div class="card-hd"><h2 class="card-title">Workflow volume</h2></div><div id="volume-report">Loading...</div></section>
      <section class="card"><div class="card-hd"><h2 class="card-title">Approver performance</h2></div><div id="performance-report">Loading...</div></section>
    `;
    const [dashboard, sla, volume, performance] = await Promise.all([
      AnalyticsAPI.dashboard().catch(() => ({})),
      AnalyticsAPI.slaReport().catch(() => ({})),
      AnalyticsAPI.workflowVolume().catch(() => ({})),
      AnalyticsAPI.approverPerformance().catch(() => ({})),
    ]);
    document.getElementById('analytics-stats').innerHTML = [
      ['Total workflows', dashboard.total_workflows ?? 0],
      ['Pending approvals', dashboard.pending_approvals ?? dashboard.pending ?? 0],
      ['Approved', dashboard.approved ?? 0],
      ['Overdue', dashboard.overdue ?? 0],
    ].map(([label, value]) => `<article class="stat"><div class="stat-label">${label}</div><div class="stat-val">${value}</div></article>`).join('');
    this.renderObject('sla-report', sla);
    this.renderObject('volume-report', volume);
    this.renderObject('performance-report', performance);
  }

  renderObject(id, data) {
    const rows = Array.isArray(data) ? data : Object.entries(data || {}).map(([key, value]) => ({ metric: FlowDeskShell.titleCase(key), value }));
    document.getElementById(id).innerHTML = rows.length ? `<table class="tbl"><tbody>${rows.map((row) => `<tr>${Object.values(row).map((value) => `<td>${FlowDeskShell.esc(typeof value === 'object' ? JSON.stringify(value) : value)}</td>`).join('')}</tr>`).join('')}</tbody></table>` : '<p class="text-gray-600" style="font-size:11px">No analytics data available.</p>';
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const { root } = await FlowDeskShell.initPage({ activePage: 'analytics', title: 'Analytics', allowedRoles: ['admin'], options: { hideNewRequest: true } });
    await new AnalyticsPage(root).init();
  } catch (error) {
    if (error.message !== 'Not authenticated' && error.message !== 'Access denied') showToast(`Failed to load analytics: ${error.message}`, 'error');
  }
});
