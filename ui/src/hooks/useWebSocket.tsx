import { useEffect, useRef } from 'react';

type WebSocketCallbacks = {
  onOpen?: () => void;
  onMessage?: (data: any) => void;
  onClose?: () => void;
  onError?: (event: Event) => void;
}

export const useWebSocket = (url: string, callbacks: WebSocketCallbacks) => {
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(url);
    
    ws.current.onopen = () => {
      console.log("WebSocket Connected");
      callbacks.onOpen?.();
    };
    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        callbacks.onMessage?.(data);
      } catch (error) {
        console.error("Failed to parse WebSocket message:", error);
      }
    };
    ws.current.onerror = (event) => {
        console.error("WebSocket Error:", event);
        callbacks.onError?.(event);
    };
    ws.current.onclose = () => {
        console.log("WebSocket Disconnected");
        callbacks.onClose?.();
    };

    return () => {
      ws.current?.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]); // Зависимости убраны, чтобы избежать переподключений
};