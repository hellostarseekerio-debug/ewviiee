"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LogOut, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { navItems } from "./nav-items";
import { useAuth, hasRole } from "@/lib/auth-context";
import { useCommandPalette } from "@/lib/command-palette-context";
import { useLanguage } from "@/lib/i18n/context";

export function CommandPalette() {
  const { open, setOpen, toggle } = useCommandPalette();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { setTheme } = useTheme();
  const { t } = useLanguage();

  useEffect(() => {
    function handler(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        toggle();
      }
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [toggle]);

  function go(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {navItems
            .filter((item) => !item.minRole || hasRole(user, item.minRole))
            .map((item) => (
              <CommandItem key={item.href} onSelect={() => go(item.href)}>
                <item.icon className="h-4 w-4" />
                {t(item.labelKey)}
              </CommandItem>
            ))}
        </CommandGroup>
        <CommandGroup heading="Theme">
          <CommandItem onSelect={() => { setTheme("light"); setOpen(false); }}>
            <Sun className="h-4 w-4" /> Light mode
          </CommandItem>
          <CommandItem onSelect={() => { setTheme("dark"); setOpen(false); }}>
            <Moon className="h-4 w-4" /> Dark mode
          </CommandItem>
        </CommandGroup>
        <CommandGroup heading="Account">
          <CommandItem onSelect={() => { setOpen(false); logout(); }}>
            <LogOut className="h-4 w-4" /> {t("topbar.signOut")}
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
