class NotificationManager {
  constructor() {
    this.ws = null;
    this.handlers = {};
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.shouldReconnect = true;
  }

  connect() {
    const token = AuthManager.getAccessToken();
    if (!token) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/notifications/?token=${token}`;
    this.shouldReconnect = true;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {}
    };

    this.ws.onclose = () => {
      if (!this.shouldReconnect || this.reconnectAttempts >= this.maxReconnectAttempts) return;
      this.reconnectAttempts += 1;
      setTimeout(() => this.connect(), 3000);
    };
  }

  handleMessage(message) {
    const type = message.type || message.type_key || message.event_type;
    const payload = message.payload || {};
    if (!type) return;

    this.updateBadge();

    this.broadcast(type, payload);

    const messages = {
      'approval.requested': `New document pending your approval: ${payload.workflow_name || payload.workflow_id}`,
      'approval.decision': `Workflow ${payload.workflow_name || payload.workflow_id} was ${payload.status || payload.decision || payload.action}`,
      'approval.step_completed': payload.message || `Workflow ${payload.workflow_name || payload.workflow_id} moved to the next step`,
      'approval.approved': payload.message || `Workflow ${payload.workflow_name || payload.workflow_id} was fully approved`,
      'approval.rejected': payload.message || `Workflow ${payload.workflow_name || payload.workflow_id} was rejected`,
      'approval.returned': payload.message || `Workflow ${payload.workflow_name || payload.workflow_id} was returned`,
      'workflow.created': payload.message || `Workflow ${payload.workflow_name || payload.workflow_id} was submitted`,
      'sla.warning': `SLA warning for workflow ${payload.workflow_id}`,
      'approval.escalated': `Workflow ${payload.workflow_id} has breached SLA`,
    };

    if (messages[type]) {
      const toastType = type.includes('approved') ? 'success' : (type.includes('rejected') || type === 'approval.escalated') ? 'error' : 'info';
      showToast(messages[type], toastType);
    }
  }

  on(eventType, handler) {
    this.handlers[eventType] = this.handlers[eventType] || [];
    this.handlers[eventType].push(handler);
  }

  broadcast(eventType, payload) {
    (this.handlers[eventType] || []).forEach((handler) => handler(payload || {}));
  }

  updateBadge() {
    const badge = document.getElementById('notification-badge') || document.querySelector('.notif-badge, [data-notif-count]');
    if (!badge) return;

    const current = Number.parseInt(badge.textContent || '0', 10);
    badge.textContent = `${current + 1}`;
    badge.classList.remove('hidden');
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.ws) this.ws.close();
  }
}

let notificationManager = null;

function initNotifications() {
  notificationManager = new NotificationManager();
  window.notificationManager = notificationManager;
  notificationManager.connect();
}

function connectNotificationSocket() {
  if (notificationManager?.ws && notificationManager.ws.readyState !== WebSocket.CLOSED) {
    return notificationManager;
  }
  initNotifications();
  return notificationManager;
}

window.connectNotificationSocket = connectNotificationSocket;
