/**
 * KisanSetu — Reactive Real-Time Event Bus
 * Synchronizes token transitions, gate scans, and circuit breaker alerts across tabs & screens
 * using BroadcastChannel (zero latency cross-tab) + WebSocket backend stream.
 */

(function (window) {
  'use strict';

  const CHANNEL_NAME = "kisan_setu_live_bus";
  const listeners = {};

  let broadcastChannel = null;
  if (typeof BroadcastChannel !== 'undefined') {
    try {
      broadcastChannel = new BroadcastChannel(CHANNEL_NAME);
      broadcastChannel.onmessage = (event) => {
        if (event && event.data) {
          dispatchLocal(event.data.type, event.data.payload, false);
        }
      };
    } catch (e) {
      console.warn("BroadcastChannel not supported in this environment:", e);
    }
  }

  function dispatchLocal(eventType, data, sendToChannel = true) {
    if (listeners[eventType]) {
      listeners[eventType].forEach(cb => {
        try { cb(data); } catch (err) { console.error("EventBus callback error:", err); }
      });
    }
    // Also trigger wildcard '*' listeners
    if (listeners['*']) {
      listeners['*'].forEach(cb => {
        try { cb({ type: eventType, data }); } catch (err) { console.error("EventBus wildcard callback error:", err); }
      });
    }

    if (sendToChannel && broadcastChannel) {
      try {
        broadcastChannel.postMessage({ type: eventType, payload: data });
      } catch (e) {
        console.warn("BroadcastChannel post error:", e);
      }
    }
  }

  let ws = null;
  let wsReconnectTimeout = null;

  const KisanEventBus = {
    /**
     * Subscribe to an event topic
     */
    subscribe(eventType, callback) {
      if (!listeners[eventType]) {
        listeners[eventType] = [];
      }
      listeners[eventType].push(callback);
      return () => {
        listeners[eventType] = listeners[eventType].filter(cb => cb !== callback);
      };
    },

    /**
     * Publish an event locally and across browser tabs
     */
    publish(eventType, data = {}) {
      dispatchLocal(eventType, data, true);

      // If WebSocket connected, send upstream
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ action: "EVENT", type: eventType, data }));
        } catch (e) {
          // ignore
        }
      }
    },

    /**
     * Connect to backend WebSocket for cross-device network streaming
     */
    connectWebSocket(centerId = "CTR-KARNAL-01") {
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host || 'localhost:8000';
      const url = `${protocol}//${host}/api/v1/ws/${encodeURIComponent(centerId)}`;

      try {
        ws = new WebSocket(url);

        ws.onopen = () => {
          console.log("⚡ KisanEventBus: Real-time yard WebSocket connected (" + centerId + ")");
          if (wsReconnectTimeout) clearTimeout(wsReconnectTimeout);
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type) {
              dispatchLocal(msg.type, msg.data || msg, false);
            }
          } catch (e) {
            console.warn("WebSocket parse error:", e);
          }
        };

        ws.onclose = () => {
          // Reconnect attempt in 5 seconds
          wsReconnectTimeout = setTimeout(() => {
            this.connectWebSocket(centerId);
          }, 5000);
        };

        ws.onerror = () => {
          try { ws.close(); } catch (e) {}
        };
      } catch (e) {
        console.warn("WebSocket creation error:", e);
      }
    }
  };

  // Auto-listen to window storage events as tertiary fallback
  window.addEventListener('storage', (e) => {
    if (e.key === 'kisan_bus_dispatch' && e.newValue) {
      try {
        const parsed = JSON.parse(e.newValue);
        dispatchLocal(parsed.type, parsed.data, false);
      } catch (err) {}
    }
  });

  window.KisanEventBus = KisanEventBus;
})(window);
