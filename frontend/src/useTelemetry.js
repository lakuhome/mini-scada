import { useEffect, useState } from 'react';

export default function useTelemetry() {
  const [state, setState] = useState({ tags: {}, connected: false, receivedAt: null });
  useEffect(() => {
    let stopped = false;
    let socket;
    let reconnect;
    let watchdog;
    function connect() {
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/tags`);
      socket.onmessage = (event) => {
        try {
          const snapshot = JSON.parse(event.data);
          if (snapshot.type !== 'snapshot' || !Array.isArray(snapshot.tags)) return;
          clearTimeout(watchdog);
          setState({ tags: Object.fromEntries(snapshot.tags.map(tag => [tag.id, tag])),
            connected: true, receivedAt: Date.now() });
          watchdog = setTimeout(() => socket.close(), 5000);
        } catch { socket.close(); }
      };
      socket.onopen = () => { watchdog = setTimeout(() => socket.close(), 5000); };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        clearTimeout(watchdog);
        if (stopped) return;
        setState(previous => ({ ...previous, connected: false }));
        reconnect = setTimeout(connect, 1500);
      };
    }
    connect();
    return () => {
      stopped = true;
      clearTimeout(reconnect);
      clearTimeout(watchdog);
      socket.close();
    };
  }, []);
  return state;
}
