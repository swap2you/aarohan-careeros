"use client";

import { useEffect } from "react";

export type ToastKind = "success" | "error" | "info";

export type ToastMessage = {
  id: number;
  kind: ToastKind;
  text: string;
};

type Props = {
  toasts: ToastMessage[];
  onDismiss: (id: number) => void;
};

export function ToastStack({ toasts, onDismiss }: Props) {
  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastMessage;
  onDismiss: (id: number) => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(toast.id), 6000);
    return () => window.clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div className={`toast toast-${toast.kind}`}>
      <span>{toast.text}</span>
      <button type="button" className="toast-close" onClick={() => onDismiss(toast.id)}>
        Dismiss
      </button>
    </div>
  );
}
