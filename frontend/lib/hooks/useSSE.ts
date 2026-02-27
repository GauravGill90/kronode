"use client";

import { useEffect, useRef, useState } from "react";
import type { TaskEvent } from "../types";

interface UseSSEOptions {
  taskId: string | null;
  onTerminal?: (status: string) => void;
}

export function useSSE({ taskId, onTerminal }: UseSSEOptions) {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  // Keep onTerminal in a ref so changing the callback never re-triggers the effect
  const onTerminalRef = useRef(onTerminal);
  onTerminalRef.current = onTerminal;

  useEffect(() => {
    if (!taskId) return;

    const token = (window as Window & { __clerkToken?: string }).__clerkToken || "";
    const url = `${process.env.NEXT_PUBLIC_BACKEND_URL}/v1/task/${taskId}/stream`;

    const es = new EventSource(`${url}?token=${encodeURIComponent(token)}`);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "terminal") {
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
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [taskId]); // onTerminal intentionally excluded — accessed via ref

  return { events, connected };
}
