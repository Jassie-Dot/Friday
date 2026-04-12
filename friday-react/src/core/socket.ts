import { useAIStore } from './store';

const API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";

let wsSocket: WebSocket | null = null;
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000;
let pingInterval: ReturnType<typeof setInterval> | null = null;

export function connectWebSocket() {
  if (wsSocket && (wsSocket.readyState === WebSocket.CONNECTING || wsSocket.readyState === WebSocket.OPEN)) {
    return;
  }

  const store = useAIStore.getState();
  store.setConnectionStatus('connecting');

  try {
    wsSocket = new WebSocket(WS_URL);
    reconnectAttempts = 0;

    wsSocket.onopen = () => {
      reconnectAttempts = 0;
      store.setConnectionStatus('connected');
      store.setState('idle');

      if (pingInterval) clearInterval(pingInterval);
      pingInterval = setInterval(() => {
        if (wsSocket?.readyState === WebSocket.OPEN) {
          wsSocket?.send(JSON.stringify({ type: 'ping' }));
        }
      }, 15000);

      wsSocket?.send(JSON.stringify({ type: 'ping' }));
    };

    wsSocket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const store = useAIStore.getState();

        if (payload.type === 'pong') return;

        if (payload.type === 'presence') {
          const mode = payload.data?.mode || 'idle';
          store.setState(mode);

          if (payload.data?.terminal_text && mode === 'responding') {
            import('./voice').then(({ speakText }) => {
              speakText(payload.data.terminal_text);
            });
          }
        }

        if (payload.type === 'bootstrap') {
          if (payload.presence) {
            store.setState(payload.presence.mode || 'idle');
          }
          if (payload.conversation) {
            store.loadMessages(payload.conversation);
          }
        }

        if (payload.type === 'conversation') {
          store.addMessage(payload.data?.role, payload.data?.text);
          if (payload.data?.role === 'friday') {
            import('./voice').then(({ speakText }) => {
              speakText(payload.data?.text);
            });
          }
        }

        if (payload.type === 'event') {
          store.addPanel({
            type: 'alert',
            title: payload.data?.source?.toUpperCase() || 'SYSTEM',
            content: payload.data?.message_type || 'Event received',
          });
        }
      } catch {
        console.warn('FRIDAY: Malformed WS message');
      }
    };

    wsSocket.onclose = (event) => {
      store.setConnectionStatus('disconnected');
      cleanup();
      if (!event.wasClean) {
        scheduleReconnect();
      }
    };

    wsSocket.onerror = () => {
      store.setConnectionStatus('error');
    };

  } catch {
    useAIStore.getState().setConnectionStatus('error');
    scheduleReconnect();
  }
}

function cleanup() {
  if (pingInterval) {
    clearInterval(pingInterval);
    pingInterval = null;
  }
}

function getReconnectDelay(): number {
  const base = Math.min(1000 * Math.pow(1.5, reconnectAttempts), MAX_RECONNECT_DELAY);
  const jitter = base * (0.5 + Math.random() * 0.5);
  return Math.round(jitter);
}

function scheduleReconnect() {
  if (reconnectTimeout) clearTimeout(reconnectTimeout);

  reconnectAttempts++;
  reconnectTimeout = setTimeout(() => {
    connectWebSocket();
  }, getReconnectDelay());
}

export function submitObjectiveToServer(text: string) {
  if (!text.trim()) return;
  const objective = text.trim();

  const store = useAIStore.getState();
  store.addMessage('user', objective);
  store.setState('thinking');

  if (wsSocket && wsSocket.readyState === WebSocket.OPEN) {
    wsSocket.send(JSON.stringify({
      type: 'objective',
      text: objective,
      context: { source: 'frontend-react-voice', timestamp: Date.now() }
    }));
  } else {
    store.setState('error');
    fetch(`${API_URL}/api/objectives/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        objective,
        context: { source: 'frontend-react-http', timestamp: Date.now() }
      })
    })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      store.setState('responding');
    })
    .catch((err) => {
      console.error('FRIDAY: Dispatch error', err);
      store.addMessage('friday', `Connection failed, Boss. The backend isn't responding. Let me try again...`);
      store.setState('idle');
      scheduleReconnect();
    });
  }
}

export function disconnectWebSocket() {
  cleanup();
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }
  if (wsSocket) {
    wsSocket.close(1000, 'User disconnect');
    wsSocket = null;
  }
}

export function getWSState() {
  return wsSocket?.readyState ?? WebSocket.CLOSED;
}
