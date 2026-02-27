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

  useEffect(() => {
    if (!taskId) return;

    const token = (window as Window & { __clerkToken?: string }).__clerkToken || "";
    const url = `${process.env.NEXT_PUBLIC_BACKEND_URL}/v1/task/${taskId}/stream`;

    // EventSource doesn't support custom headers — pass token as query param
    const es = new EventSource(`${url}?token=${encodeURIComponent(token)}`);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.type === "terminal") {
          onTerminal?.(data.status);
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
  }, [taskId, onTerminal]);

  return { events, connected };
}
