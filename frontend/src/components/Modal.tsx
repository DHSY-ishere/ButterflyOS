"use client";
import { useEffect } from "react";

export default function Modal({ open, onClose, title, eyebrow, width = 1000, children }: {
  open: boolean; onClose: () => void; title: string; eyebrow?: string; width?: number; children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/55 backdrop-blur-sm rise" onClick={onClose}>
      <div role="dialog" aria-label={title} className="panel w-full max-h-[90vh] overflow-y-auto" style={{ maxWidth: width, borderRadius: 28 }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-6 px-8 pt-7 pb-5 border-b border-white/10">
          <div>
            {eyebrow && <div className="text-[12px] font-semibold tracking-[0.12em] uppercase text-amber mb-1.5">{eyebrow}</div>}
            <h2 className="text-[24px] font-semibold tracking-tight text-white">{title}</h2>
          </div>
          <button className="btn btn-sm" onClick={onClose} aria-label="Close dialog">Close</button>
        </div>
        <div className="px-8 py-7">{children}</div>
      </div>
    </div>
  );
}
