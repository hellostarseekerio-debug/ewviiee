import {
  LayoutDashboard,
  FileText,
  FolderKanban,
  Search,
  Sparkles,
  Users,
  Settings,
  type LucideIcon,
} from "lucide-react";
import type { UserRole } from "@/lib/api/types";
import type { TranslationKey } from "@/lib/i18n/context";

export interface NavItem {
  href: string;
  labelKey: TranslationKey;
  icon: LucideIcon;
  minRole?: UserRole;
}

export const navItems: NavItem[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/documents", labelKey: "nav.documents", icon: FileText },
  { href: "/posters", labelKey: "nav.posters", icon: FolderKanban },
  { href: "/search", labelKey: "nav.search", icon: Search },
  { href: "/ai", labelKey: "nav.ai", icon: Sparkles },
  { href: "/admin/users", labelKey: "nav.users", icon: Users, minRole: "admin" },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
];
