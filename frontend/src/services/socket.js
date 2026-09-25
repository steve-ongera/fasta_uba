/**
 * src/services/socket.js
 * Thin WebSocket wrapper around the Django Channels consumer at
 * ws/trip/<trip_id>/ (see backend/api/consumers.py + routing.py).
 *
 * Handles: auto-reconnect with backoff, JSON in/out, a pub/sub style
 * `.on(event, cb)` API so components don't touch the raw socket.
 */

import { tokenStore } from "./api";

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

export class TripSocket {
  constructor(tripId) {
    this.tripId = tripId;
    this.socket = null;
    this.listeners = {}; // event name -> [callbacks]
    this.reconnectAttempts = 0;
    this.shouldReconnect = true;
  }

  connect() {
    const token = tokenStore.getAccess();
    const url = `${WS_BASE_URL}/trip/${this.tripId}/?token=${token}`;
    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this._emit("connected", null);
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._emit(data.type || "message", data);
      } catch {
        // ignore malformed frames
      }
    };

    this.socket.onclose = () => {
      this._emit("disconnected", null);
      if (this.shouldReconnect) this._reconnect();
    };

    this.socket.onerror = () => {
      this.socket?.close();
    };

    return this;
  }

  _reconnect() {
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 15000);
    this.reconnectAttempts += 1;
    setTimeout(() => {
      if (this.shouldReconnect) this.connect();
    }, delay);
  }

  send(type, payload = {}) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type, ...payload }));
    }
  }

  // driver app calls this every few seconds while a trip is active
  sendLocationUpdate(lat, lng, heading) {
    this.send("location_update", { lat, lng, heading });
  }

  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return () => this.off(event, callback);
  }

  off(event, callback) {
    if (!this.listeners[event]) return;
    this.listeners[event] = this.listeners[event].filter((cb) => cb !== callback);
  }

  _emit(event, data) {
    (this.listeners[event] || []).forEach((cb) => cb(data));
  }

  disconnect() {
    this.shouldReconnect = false;
    this.socket?.close();
  }
}

/**
 * User-level notification socket (independent of any single trip) — used
 * for "driver matched", "trip cancelled", etc. pushed from NotificationService.
 */
export class UserSocket {
  constructor() {
    this.socket = null;
    this.listeners = {};
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
  }

  connect() {
    const token = tokenStore.getAccess();
    this.socket = new WebSocket(`${WS_BASE_URL}/notifications/?token=${token}`);

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        (this.listeners[data.type] || []).forEach((cb) => cb(data));
      } catch {
        /* ignore */
      }
    };

    this.socket.onclose = () => {
      if (this.shouldReconnect) {
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts++, 15000);
        setTimeout(() => this.connect(), delay);
      }
    };

    return this;
  }

  on(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(callback);
    return () => {
      this.listeners[event] = this.listeners[event].filter((cb) => cb !== callback);
    };
  }

  disconnect() {
    this.shouldReconnect = false;
    this.socket?.close();
  }
}

export const userSocket = new UserSocket();
