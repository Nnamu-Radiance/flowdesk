const getCSRFToken = () => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; csrftoken=`);
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
};

class APIClient {
  constructor(baseURL = "/api") {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const headers = options.headers || {};
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    headers["X-CSRFToken"] = getCSRFToken();

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
      credentials: "include",
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.error || "Request failed");
    }
    return payload;
  }

  get(endpoint) {
    return this.request(endpoint, { method: "GET" });
  }

  post(endpoint, body) {
    return this.request(endpoint, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  }

  patch(endpoint, body) {
    return this.request(endpoint, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  }
}

window.APIClient = APIClient;
