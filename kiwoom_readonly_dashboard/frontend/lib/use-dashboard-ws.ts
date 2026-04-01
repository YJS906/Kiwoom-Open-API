"use client";

import { useEffect, useRef, useState } from "react";

import { API_BASE_URL } from "@/lib/api";
import { toWsUrl } from "@/lib/utils";
import type { RealtimeEnvelope } from "@/types/dashboard";

export function useDashboardWs(symbol: string | null) {
  const [events, setEvents] = useState<RealtimeEnvelope[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const desiredSymbolRef = useRef<string | null>(symbol);

  useEffect(() => {
    let isActive = true;
    let retryTimer: number | null = null;

    const connect = () => {
      const socket = new WebSocket(toWsUrl(API_BASE_URL));
      socketRef.current = socket;

      socket.onopen = () => {
        if (!isActive) return;
        setConnected(true);
        sendSubscribe(socket, desiredSymbolRef.current);
      };

      socket.onmessage = (event) => {
        if (!isActive) return;
        try {
          const payload = JSON.parse(event.data) as RealtimeEnvelope;
          setEvents((current) => [...current.slice(-19), payload]);
        } catch {
          // Ignore malformed packets on the client side.
        }
      };

      socket.onerror = () => {
        if (!isActive) return;
        setConnected(false);
      };

      socket.onclose = () => {
        if (!isActive) return;
        setConnected(false);
        retryTimer = window.setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      isActive = false;
      setConnected(false);
      if (retryTimer) {
        window.clearTimeout(retryTimer);
      }
      socketRef.current?.close();
    };
  }, []);

  useEffect(() => {
    desiredSymbolRef.current = symbol;
    if (!symbol) {
      return;
    }
    sendSubscribe(socketRef.current, symbol);
  }, [symbol]);

  return { events, connected };
}

function sendSubscribe(socket: WebSocket | null, symbol: string | null) {
  if (!socket || socket.readyState !== WebSocket.OPEN || !symbol) {
    return;
  }
  socket.send(
    JSON.stringify({
      action: "subscribe",
      symbols: [symbol]
    })
  );
}
