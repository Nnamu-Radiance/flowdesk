class NotificationManager {
  constructor() {
    this.ws = null;
    this.handlers = {};
    this.reconnectDelay = 1000;
    this.maxReconnectDelay = 30000;
  }

  connect() {
    const token = AuthManager.getAccessToken();
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/notifications/?token=${token}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onclose = () => {
      setTimeout(() => this.connect(), this.reconnectDelay);
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    };
  }

  handleMessage(message) {
    const { type, payload } = message;

    this.updateBadge();

    if (this.handlers[type]) {
      this.handlers[type](payload);
    }

    const messages = {
      'approval.requested': `New document pending your approval: ${payload.workflow_name || payload.workflow_id}`,
      'approval.decision': `Workflow ${payload.workflow_name || payload.workflow_id} was ${payload.decision || payload.action}`,
      'sla.warning': `SLA warning for workflow ${payload.workflow_id}`,
      'approval.escalated': `Workflow ${payload.workflow_id} has breached SLA`,
    };

    if (messages[type]) {
      const toastType = type === 'approval.escalated' ? 'error' : 'info';
      showToast(messages[type], toastType);
    }
  }

  on(eventType, handler) {
    this.handlers[eventType] = handler;
  }

  updateBadge() {
    const badge = document.getElementById('notification-badge');
    if (!badge) return;

    const current = Number.parseInt(badge.textContent || '0', 10);
    badge.textContent = `${current + 1}`;
    badge.classList.remove('hidden');
  }

  disconnect() {
    if (this.ws) this.ws.close();
  }
}

let notificationManager = null;

function initNotifications() {
  notificationManager = new NotificationManager();
  notificationManager.connect();
}
