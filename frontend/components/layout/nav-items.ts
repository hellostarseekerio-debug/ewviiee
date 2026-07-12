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

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  minRole?: UserRole;
}

export const navItems: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/posters", label: "Poster Archive", icon: FolderKanban },
  { href: "/search", label: "Search", icon: Search },
  { href: "/ai", label: "AI Insights", icon: Sparkles },
  { href: "/admin/users", label: "Users", icon: Users, minRole: "admin" },
  { href: "/settings", label: "Settings", icon: Settings },
];
