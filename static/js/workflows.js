class WorkflowManager {
  constructor() {
    this.api = new APIClient("/api");
    this.filters = {};
    this.bindEvents();
    this.loadWorkflows();
  }

  bindEvents() {
    document.getElementById("status-filter")?.addEventListener("change", (e) => {
      this.filters.status = e.target.value;
      this.loadWorkflows();
    });
    document.getElementById("search-input")?.addEventListener("input", (e) => {
      this.filters.search = e.target.value;
      this.loadWorkflows();
    });
    document.getElementById("reset-filters")?.addEventListener("click", () => {
      this.filters = {};
      document.getElementById("status-filter").value = "";
      document.getElementById("search-input").value = "";
      this.loadWorkflows();
    });
  }

  async loadWorkflows() {
    try {
      const query = new URLSearchParams(this.filters).toString();
      const data = await this.api.get(`/workflows/${query ? `?${query}` : ""}`);
      this.render(data.results || []);
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  render(items) {
    const container = document.getElementById("workflows-container");
    if (!container) return;
    container.innerHTML = items
      .map(
        (item) => `
      <article class="card">
        <h3 class="text-lg font-semibold mb-2">${item.name}</h3>
        <p class="text-sm text-gray-600 mb-4">${item.document_preview?.filename || "No document"}</p>
        <div class="flex justify-between text-xs">
          <span>${item.status}</span>
          <span>${item.sla_status}</span>
        </div>
      </article>
    `
      )
      .join("");
  }
}

document.addEventListener("DOMContentLoaded", () => new WorkflowManager());
