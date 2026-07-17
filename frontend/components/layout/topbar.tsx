"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Menu, Moon, Search, Sun, LogOut, UserRound, Settings as SettingsIcon, Globe, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth-context";
import { useCommandPalette } from "@/lib/command-palette-context";
import { useLanguage, localeLabels, type Locale } from "@/lib/i18n/context";
import { SidebarNav } from "./sidebar";

const LOCALES: Locale[] = ["en", "zh-HK", "zh-CN"];

export function Topbar() {
  const { user, logout } = useAuth();
  const { setTheme, resolvedTheme } = useTheme();
  const { locale, setLocale, t } = useLanguage();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { setOpen: setCommandPaletteOpen } = useCommandPalette();

  const initials = user?.full_name
    ? user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()
    : user?.username.slice(0, 2).toUpperCase();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-background px-4">
      <div className="flex items-center gap-2">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation menu">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0">
            <SidebarNav onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>
        <Button
          variant="outline"
          size="sm"
          className="hidden gap-2 text-muted-foreground sm:flex"
          onClick={() => setCommandPaletteOpen(true)}
        >
          <Search className="h-3.5 w-3.5" />
          {t("topbar.searchPlaceholder")}
          <kbd className="ml-4 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium">
            &#8984;K
          </kbd>
        </Button>
      </div>

      <div className="flex items-center gap-1.5">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={t("topbar.language")}>
              <Globe className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{t("topbar.language")}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {LOCALES.map((code) => (
              <DropdownMenuItem key={code} onClick={() => setLocale(code)}>
                {locale === code ? <Check className="h-4 w-4" /> : <span className="w-4" />}
                {localeLabels[code]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle theme"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          <Sun className="h-4 w-4 scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
          <Moon className="absolute h-4 w-4 scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0" />
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2 px-2">
              <Avatar className="h-7 w-7">
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <span className="hidden text-left sm:block">
                <span className="block text-sm font-medium leading-none">{user?.full_name ?? user?.username}</span>
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col gap-1">
              <span className="font-medium text-foreground">{user?.full_name ?? user?.username}</span>
              <span className="flex items-center gap-1.5 text-xs">
                @{user?.username} <Badge variant="secondary" className="capitalize">{user?.role}</Badge>
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/settings")}>
              <UserRound className="h-4 w-4" /> {t("topbar.profile")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/settings")}>
              <SettingsIcon className="h-4 w-4" /> {t("topbar.settings")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onClick={logout}>
              <LogOut className="h-4 w-4" /> {t("topbar.signOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
