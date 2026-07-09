"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { AskDrawer } from "@/components/AskDrawer";

type AskContextValue = {
  open: boolean;
  openAsk: () => void;
  closeAsk: () => void;
  toggleAsk: () => void;
};

const AskContext = createContext<AskContextValue | null>(null);

export function AskProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);

  const openAsk = useCallback(() => setOpen(true), []);
  const closeAsk = useCallback(() => setOpen(false), []);
  const toggleAsk = useCallback(() => setOpen((v) => !v), []);

  const value = useMemo(
    () => ({ open, openAsk, closeAsk, toggleAsk }),
    [open, openAsk, closeAsk, toggleAsk],
  );

  return (
    <AskContext.Provider value={value}>
      {children}
      <AskDrawer open={open} onOpen={openAsk} onClose={closeAsk} />
    </AskContext.Provider>
  );
}

export function useAsk() {
  const ctx = useContext(AskContext);
  if (!ctx) {
    throw new Error("useAsk must be used within AskProvider");
  }
  return ctx;
}
