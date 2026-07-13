"use client";

import { useEffect, useState } from "react";
import { Folder as FolderIcon } from "lucide-react";
import { foldersApi } from "@/lib/api/endpoints";
import type { FolderTreeNodeOut } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

interface FlatFolder {
  id: string;
  name: string;
  depth: number;
}

function flatten(nodes: FolderTreeNodeOut[]): FlatFolder[] {
  const out: FlatFolder[] = [];
  for (const node of nodes) {
    out.push({ id: node.id, name: node.name, depth: node.depth });
    out.push(...flatten(node.children));
  }
  return out;
}

export function FolderPickerDialog({
  open,
  onOpenChange,
  onConfirm,
  title = "Move to folder",
  description = "Choose a destination folder, or move to the top level (Unfiled).",
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (folderId: string | null) => void;
  title?: string;
  description?: string;
}) {
  const [folders, setFolders] = useState<FlatFolder[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    foldersApi.tree().then((tree) => setFolders(flatten(tree)));
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="flex max-h-80 flex-col gap-0.5 overflow-y-auto rounded-md border border-border p-1">
          <button
            onClick={() => setSelected(null)}
            className={`flex items-center gap-2 rounded px-2 py-1.5 text-left text-sm ${
              selected === null ? "bg-secondary font-medium" : "hover:bg-muted"
            }`}
          >
            <FolderIcon className="h-4 w-4" /> Unfiled (top level)
          </button>
          {folders.map((f) => (
            <button
              key={f.id}
              onClick={() => setSelected(f.id)}
              style={{ paddingLeft: 8 + f.depth * 16 }}
              className={`flex items-center gap-2 rounded px-2 py-1.5 text-left text-sm ${
                selected === f.id ? "bg-secondary font-medium" : "hover:bg-muted"
              }`}
            >
              <FolderIcon className="h-4 w-4 shrink-0" /> <span className="truncate">{f.name}</span>
            </button>
          ))}
        </div>
        <DialogFooter>
          <Button
            onClick={() => {
              onConfirm(selected);
              onOpenChange(false);
            }}
          >
            Move here
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
