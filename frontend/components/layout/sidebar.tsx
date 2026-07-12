"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { navItems } from "./nav-items";
import { useAuth, hasRole } from "@/lib/auth-context";
import { useLanguage } from "@/lib/i18n/context";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const { t } = useLanguage();

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Building2 className="h-4 w-4" />
        </div>
        <span className="text-sm font-semibold">Office AI Platform</span>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-3 scrollbar-thin">
        {navItems
          .filter((item) => !item.minRole || hasRole(user, item.minRole))
          .map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-sidebar-accent text-foreground"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-foreground"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {t(item.labelKey)}
              </Link>
            );
          })}
      </nav>
      <div className="border-t border-sidebar-border p-3 text-xs text-muted-foreground">
        Enterprise AI Office Automation
      </div>
    </div>
  );
}
