/**
 * WebSocket client manager with automatic ws:// / wss:// detection and reconnect backoff.
 */

export class SmartClassSocket {
  constructor(sessionId = "global") {
    this.sessionId = sessionId;
    this.socket = null;
    this.handlers = new Map();
    this.retryDelayMs = 1000;
    this.maxRetryDelayMs = 15000;
    this.shouldReconnect = true;
    this.onStatusChange = null;
  }

  connect(sessionId = this.sessionId) {
    this.sessionId = sessionId || "global";
    this.shouldReconnect = true;
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${encodeURIComponent(this.sessionId)}`;
    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      this.retryDelayMs = 1000;
      if (this.onStatusChange) this.onStatusChange("connected");
    };

    this.socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const listeners = this.handlers.get(msg.event) || [];
        listeners.forEach((cb) => cb(msg.data));
      } catch (err) {
        console.warn("Malformed WebSocket message:", err);
      }
    };

    this.socket.onclose = () => {
      if (this.onStatusChange) this.onStatusChange("reconnecting");
      if (!this.shouldReconnect) return;
      setTimeout(() => this.connect(this.sessionId), this.retryDelayMs);
      this.retryDelayMs = Math.min(this.retryDelayMs * 1.5, this.maxRetryDelayMs);
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  on(eventType, callback) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType).push(callback);
  }

  disconnect() {
    this.shouldReconnect = false;
    this.socket?.close();
  }
}
