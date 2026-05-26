class NotificationHandler {
  constructor() {
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  connect() {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    this.socket = new WebSocket(`${protocol}://${window.location.host}/ws/notifications/`);
    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
    };
    this.socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.message) showToast(data.message, data.type || "info");
      if (typeof data.badge_count === "number") {
        const badge = document.getElementById("notification-badge");
        if (badge) badge.textContent = `${data.badge_count}`;
      }
    };
    this.socket.onclose = () => this.reconnect();
  }

  reconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    this.reconnectAttempts += 1;
    const delay = Math.pow(2, this.reconnectAttempts) * 1000;
    setTimeout(() => this.connect(), delay);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const handler = new NotificationHandler();
  handler.connect();
});
