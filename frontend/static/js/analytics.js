class AnalyticsPage {
  async init() {
    const [sla, volume, performance] = await Promise.all([
      AnalyticsAPI.slaReport(),
      AnalyticsAPI.workflowVolume(),
      AnalyticsAPI.approverPerformance(),
    ]);

    this.renderJson('sla-report', sla);
    this.renderJson('volume-report', volume);
    this.renderJson('performance-report', performance);
  }

  renderJson(id, data) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = JSON.stringify(data, null, 2);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const page = new AnalyticsPage();
  try {
    await page.init();
  } catch (error) {
    showToast(`Failed to load analytics: ${error.message}`, 'error');
  }
});
