document.addEventListener("DOMContentLoaded", async () => {
  const api = new APIClient("/api/analytics");
  const target = document.getElementById("dashboard-cards");
  if (!target) return;

  try {
    const data = await api.get("/dashboard/");
    const cards = [
      ["Total Workflows", data.totals.workflows],
      ["Approved", data.totals.approved],
      ["In Approval", data.totals.in_approval],
      ["Overdue", data.totals.overdue],
    ];
    target.innerHTML = cards
      .map(
        ([label, value]) => `
      <section class="card">
        <p class="text-sm text-gray-600">${label}</p>
        <p class="text-3xl font-bold">${value}</p>
      </section>
    `
      )
      .join("");
  } catch (error) {
    showToast(error.message, "error");
  }
});
