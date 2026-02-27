"use client";

import type { TaskEvent, TaskStatus } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import EventLine from "./EventLine";

interface ProgressStreamProps {
  liveEvents: TaskEvent[];
  historicalEvents: TaskEvent[];
  connected: boolean;
  status: TaskStatus;
}

export default function ProgressStream({ liveEvents, historicalEvents, connected, status }: ProgressStreamProps) {
  // Show live events if streaming, otherwise show historical
  const events = liveEvents.length > 0 ? liveEvents : historicalEvents;

  if (events.length === 0 && status === "queued") {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-5 flex items-center gap-3 text-sm text-gray-500">
        <Spinner size="sm" />
        <span>Waiting to start…</span>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 divide-y divide-gray-100 overflow-hidden">
      <div className="px-5 py-3 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">Agent activity</span>
        {connected && (
          <span className="flex items-center gap-1.5 text-xs text-green-600">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
            Live
          </span>
        )}
      </div>
      <div className="divide-y divide-gray-50">
        {events.length === 0 ? (
          <div className="px-5 py-4 text-sm text-gray-400">No activity yet.</div>
        ) : (
          events.map((event, i) => <EventLine key={event.id || i} event={event} />)
        )}
      </div>
    </div>
  );
}
