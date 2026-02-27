"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export default function Modal({ open, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl relative max-h-[90vh] overflow-y-auto"
        style={{
          background: "#0d0d1a",
          border: "1px solid rgba(99,102,241,0.2)",
          boxShadow: "0 25px 50px rgba(0,0,0,0.6)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4"
          style={{ borderBottom: "1px solid rgba(99,102,241,0.1)" }}
        >
          <h2 className="text-base font-semibold" style={{ color: "#e2e8f0" }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg flex items-center justify-center text-lg leading-none transition-colors"
            style={{ color: "#64748b" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>,
    document.body
  );
}
