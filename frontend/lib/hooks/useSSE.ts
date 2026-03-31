"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { TaskEvent } from "../types";

interface UseSSEOptions {
  taskId: string | null;
  onTerminal?: (status: string) => void;
}

const MAX_RETRIES = 5;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;

export function useSSE({ taskId, onTerminal }: UseSSEOptions) {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);
  const terminalRef = useRef(false);
  // Keep onTerminal in a ref so changing the callback never re-triggers the effect
  const onTerminalRef = useRef(onTerminal);
  onTerminalRef.current = onTerminal;

  const connect = useCallback(() => {
    if (!taskId || terminalRef.current) return;

    const token = (window as Window & { __clerkToken?: string }).__clerkToken || "";
    const url = `${process.env.NEXT_PUBLIC_BACKEND_URL}/v1/task/${taskId}/stream`;

    const es = new EventSource(`${url}?token=${encodeURIComponent(token)}`);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      retriesRef.current = 0; // reset retries on successful connection
    };

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "terminal") {
          terminalRef.current = true;
          onTerminalRef.current?.(data.status);
          es.close();
          setConnected(false);
          return;
        }
        setEvents((prev) => [...prev, data as TaskEvent]);
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();

      // Don't reconnect if terminal or max retries
      if (terminalRef.current) return;
      if (retriesRef.current >= MAX_RETRIES) return;

      // Exponential backoff: 1s, 2s, 4s, 8s, 16s (capped at 30s)
      const delay = Math.min(BASE_DELAY_MS * Math.pow(2, retriesRef.current), MAX_DELAY_MS);
      retriesRef.current += 1;

      setTimeout(() => {
        connect();
      }, delay);
    };
  }, [taskId]);

  useEffect(() => {
    terminalRef.current = false;
    retriesRef.current = 0;
    setEvents([]);
    connect();

    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, [taskId, connect]);

  return { events, connected };
}
