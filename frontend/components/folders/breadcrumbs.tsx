"use client";

import { ChevronRight, Folder as FolderIcon } from "lucide-react";
import type { FolderOut } from "@/lib/api/types";

export function FolderBreadcrumbs({
  crumbs,
  onNavigate,
}: {
  crumbs: FolderOut[];
  onNavigate: (folderId: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
      <button onClick={() => onNavigate(null)} className="flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-muted hover:text-foreground">
        <FolderIcon className="h-3.5 w-3.5" /> All records
      </button>
      {crumbs.map((crumb) => (
        <span key={crumb.id} className="flex items-center gap-1">
          <ChevronRight className="h-3.5 w-3.5" />
          <button
            onClick={() => onNavigate(crumb.id)}
            className="rounded px-1.5 py-0.5 hover:bg-muted hover:text-foreground"
          >
            {crumb.name}
          </button>
        </span>
      ))}
    </div>
  );
}
