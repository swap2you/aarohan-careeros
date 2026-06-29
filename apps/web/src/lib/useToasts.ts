"use client";

import { useCallback, useRef, useState } from "react";

import type { ToastKind, ToastMessage } from "@/components/Toast";

export function useToasts() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = nextId.current++;
    setToasts((current) => [...current, { id, kind, text }]);
    return id;
  }, []);

  return { toasts, push, dismiss };
}
