"use client";

import { createContext, useContext, useMemo, useState } from "react";

interface CommandPaletteContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

const CommandPaletteContext = createContext<CommandPaletteContextValue | null>(null);

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const value = useMemo(() => ({ open, setOpen, toggle: () => setOpen((v) => !v) }), [open]);
  return <CommandPaletteContext.Provider value={value}>{children}</CommandPaletteContext.Provider>;
}

// Shared open/close state for the Cmd/Ctrl+K command palette - both the
// keyboard shortcut listener and the visible topbar search button drive
// the same state directly, rather than the button dispatching a synthetic
// KeyboardEvent for the listener to happen to pick back up (fragile: it
// only worked because the listener didn't check event.isTrusted, and any
// future change to that listener would silently break the button).
export function useCommandPalette() {
  const ctx = useContext(CommandPaletteContext);
  if (!ctx) throw new Error("useCommandPalette must be used within a CommandPaletteProvider");
  return ctx;
}
