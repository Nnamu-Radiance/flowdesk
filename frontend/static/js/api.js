if (typeof crypto.randomUUID !== 'function') {
  crypto.randomUUID = function () {
    return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
      (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
    );
  };
}

class APIError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

class APIClient {
  constructor() {
    this.baseURL = '';
    this.refreshing = null;
  }

  getCSRFToken() {
    return document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='))
      ?.split('=')[1] || '';
  }

  async request(method, path, data = null, isFormData = false) {
    const headers = {
      'X-CSRFToken': this.getCSRFToken(),
      'X-Correlation-ID': crypto.randomUUID(),
    };

    let token = AuthManager.getAccessToken();
    if (!token && AuthManager.getRefreshToken()) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) token = AuthManager.getAccessToken();
    }

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    if (!isFormData && data) {
      headers['Content-Type'] = 'application/json';
    }

    const config = {
      method,
      headers,
      credentials: 'include',
      body: data ? (isFormData ? data : JSON.stringify(data)) : undefined,
    };

    let response = await fetch(`${this.baseURL}${path}`, config);

    if (response.status === 401 && AuthManager.getRefreshToken()) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        headers.Authorization = `Bearer ${AuthManager.getAccessToken()}`;
        response = await fetch(`${this.baseURL}${path}`, { ...config, headers });
      }
    }

    if (response.status === 401) {
      AuthManager.clear();
      if (window.location.pathname !== '/login/') {
        window.location.href = '/login/';
      }
    }

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new APIError(response.status, errorBody.detail || JSON.stringify(errorBody));
    }

    if (response.status === 204) return null;
    return response.json();
  }

  async refreshAccessToken() {
    if (this.refreshing) return this.refreshing;
    const refreshToken = AuthManager.getRefreshToken();
    const payload = refreshToken ? { refresh: refreshToken } : {};

    this.refreshing = fetch('/api/auth/refresh/', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.access) {
          throw new APIError(res.status, data.detail || 'Session expired');
        }
        return data;
      })
      .then((data) => {
        AuthManager.setAccessToken(data.access);
        this.refreshing = null;
        return true;
      })
      .catch(() => {
        AuthManager.clear();
        this.refreshing = null;
        if (window.location.pathname !== '/login/') {
          window.location.href = '/login/';
        }
        return false;
      });

    return this.refreshing;
  }

  get(path) {
    return this.request('GET', path);
  }

  post(path, data) {
    return this.request('POST', path, data);
  }

  patch(path, data) {
    return this.request('PATCH', path, data);
  }

  delete(path) {
    return this.request('DELETE', path);
  }

  upload(path, formData) {
    return this.request('POST', path, formData, true);
  }
}

const api = new APIClient();

const AuthAPI = {
  login: (credentials) => api.post('/api/auth/login/', credentials),
  signup: (payload) => api.post('/api/auth/signup/', payload),
  requestMagicLink: (payload) => api.post('/api/auth/magic/request/', payload),
  refresh: (token) => api.post('/api/auth/refresh/', { refresh: token }),
  logout: () => api.post('/api/auth/logout/'),
  me: () => api.get('/api/auth/me/'),
  users: () => api.get('/api/auth/users/'),
};

const WorkflowAPI = {
  list: (params = {}) => api.get(`/api/workflows/?${new URLSearchParams(params)}`),
  get: (id) => api.get(`/api/workflows/${id}/`),
  upload: (formData) => api.upload('/api/workflows/', formData),
  submit: (id) => api.patch(`/api/workflows/${id}/submit/`),
  progress: (id) => api.get(`/api/workflows/${id}/progress/`),
};

const WorkflowConfigAPI = {
  list: () => api.get('/api/workflows/config/'),
  get: (id) => api.get(`/api/workflows/config/${id}/`),
  upload: (formData) => api.upload('/api/workflows/config/upload/', formData),
};


const ApprovalAPI = {
  pending: () => api.get('/api/approvals/pending/'),
  history: (id) => api.get(`/api/approvals/${id}/history/`),
  approve: (id, comments) => api.post(`/api/approvals/${id}/approve/`, { comments }),
  reject: (id, reason) => api.post(`/api/approvals/${id}/reject/`, { reason }),
  reassign: (id, assigneeId) => api.post(`/api/approvals/${id}/reassign/`, { assignee_id: assigneeId }),
};

const AnalyticsAPI = {
  dashboard: () => api.get('/api/analytics/dashboard/'),
  slaReport: () => api.get('/api/analytics/sla-report/'),
  workflowVolume: () => api.get('/api/analytics/workflow-volume/'),
  approverPerformance: () => api.get('/api/analytics/approver-performance/'),
};
