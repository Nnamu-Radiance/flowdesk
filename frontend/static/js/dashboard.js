class DashboardPage {
  async load() {
    const stats = await AnalyticsAPI.dashboard();
    this.render(stats);
  }

  render(data) {
    const container = document.getElementById('dashboard-cards');
    if (!container) return;

    const cards = [
      { label: 'Total Workflows', value: data.total_workflows ?? 0 },
      { label: 'Pending Approvals', value: data.pending_approvals ?? 0 },
      { label: 'Approved', value: data.approved ?? 0 },
      { label: 'Rejected', value: data.rejected ?? 0 },
    ];

    container.innerHTML = cards
      .map(
        (card) => `
        <article class="card">
          <p class="text-sm text-gray-500">${card.label}</p>
          <p class="text-3xl font-bold mt-2">${card.value}</p>
        </article>
      `
      )
      .join('');
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  const page = new DashboardPage();
  try {
    await page.load();
  } catch (error) {
    showToast(`Failed to load dashboard: ${error.message}`, 'error');
  }
});
