"use client";

import { useState } from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, Folder as FolderIcon, FolderPlus, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { foldersApi, postersApi } from "@/lib/api/endpoints";
import type { FolderTreeNodeOut } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { useAuth, hasRole } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmDialog, PromptDialog } from "@/components/ui/prompt-dialog";
import { cn } from "@/lib/utils";

// Native HTML5 drag & drop (no new dependency): a folder row is draggable
// (moving that folder elsewhere in the tree) and a drop target (moving
// either a dragged folder, or a set of poster ids dragged from the main
// table, into it). The two payload shapes share one mime type so a single
// onDrop handler can tell them apart.
const DRAG_MIME = "application/x-oap-drag";

type DragPayload = { kind: "folder"; folderId: string } | { kind: "posters"; ids: string[] };

export function posterDragProps(posterId: string, selectedIds: Set<string>) {
  const ids = selectedIds.has(posterId) && selectedIds.size > 0 ? Array.from(selectedIds) : [posterId];
  return {
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      const payload: DragPayload = { kind: "posters", ids };
      e.dataTransfer.setData(DRAG_MIME, JSON.stringify(payload));
      e.dataTransfer.effectAllowed = "move";
    },
  };
}

interface FolderTreeProps {
  nodes: FolderTreeNodeOut[];
  selectedFolderId: string | null;
  onSelect: (folderId: string | null) => void;
  onChanged: () => void;
  totalUnfiledCount?: number;
}

export function FolderTree({ nodes, selectedFolderId, onSelect, onChanged, totalUnfiledCount }: FolderTreeProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <RootDropZone selected={selectedFolderId === null} onSelect={() => onSelect(null)} onChanged={onChanged} count={totalUnfiledCount} />
      {nodes.map((node) => (
        <FolderNode key={node.id} node={node} depth={0} selectedFolderId={selectedFolderId} onSelect={onSelect} onChanged={onChanged} />
      ))}
    </div>
  );
}

function RootDropZone({
  selected,
  onSelect,
  onChanged,
  count,
}: {
  selected: boolean;
  onSelect: () => void;
  onChanged: () => void;
  count?: number;
}) {
  const [dragOver, setDragOver] = useState(false);

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const raw = e.dataTransfer.getData(DRAG_MIME);
    if (!raw) return;
    const payload = JSON.parse(raw) as DragPayload;
    if (payload.kind === "posters") {
      try {
        await postersApi.bulkMove({ ids: payload.ids, folder_id: null });
        toast.success(`Moved ${payload.ids.length} record(s) to Unfiled`);
        onChanged();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Move failed");
      }
    } else if (payload.kind === "folder") {
      try {
        await foldersApi.move(payload.folderId, null);
        toast.success("Folder moved to top level");
        onChanged();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Move failed");
      }
    }
  }

  return (
    <button
      onClick={onSelect}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm font-medium transition-colors",
        selected ? "bg-sidebar-accent text-foreground" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60",
        dragOver && "ring-2 ring-primary"
      )}
    >
      <FolderIcon className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate">All records</span>
      {typeof count === "number" && <span className="text-xs text-muted-foreground">{count}</span>}
    </button>
  );
}

function FolderNode({
  node,
  depth,
  selectedFolderId,
  onSelect,
  onChanged,
}: {
  node: FolderTreeNodeOut;
  depth: number;
  selectedFolderId: string | null;
  onSelect: (id: string | null) => void;
  onChanged: () => void;
}) {
  const { user } = useAuth();
  const [expanded, setExpanded] = useState(depth < 2);
  const [dragOver, setDragOver] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [createSubfolderOpen, setCreateSubfolderOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const hasChildren = node.children.length > 0;

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const raw = e.dataTransfer.getData(DRAG_MIME);
    if (!raw) return;
    const payload = JSON.parse(raw) as DragPayload;
    if (payload.kind === "posters") {
      try {
        await postersApi.bulkMove({ ids: payload.ids, folder_id: node.id });
        toast.success(`Moved ${payload.ids.length} record(s) to "${node.name}"`);
        onChanged();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Move failed");
      }
    } else if (payload.kind === "folder" && payload.folderId !== node.id) {
      try {
        await foldersApi.move(payload.folderId, node.id);
        toast.success(`Moved folder into "${node.name}"`);
        onChanged();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Move failed");
      }
    }
  }

  async function handleRename(name: string) {
    if (name === node.name) return;
    try {
      await foldersApi.rename(node.id, name);
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Rename failed");
    }
  }

  async function handleCreateSubfolder(name: string) {
    try {
      await foldersApi.create({ name, parent_id: node.id });
      setExpanded(true);
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Create failed");
    }
  }

  const deleteIsRecursive = node.total_items > 0 || node.children.length > 0;

  async function handleDelete() {
    try {
      await foldersApi.remove(node.id, { recursive: deleteIsRecursive });
      if (selectedFolderId === node.id) onSelect(null);
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  return (
    <div>
      <div
        draggable
        onDragStart={(e) => {
          const payload: DragPayload = { kind: "folder", folderId: node.id };
          e.dataTransfer.setData(DRAG_MIME, JSON.stringify(payload));
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={cn(
          "group flex items-center gap-1 rounded-md py-1.5 pr-1 text-sm transition-colors",
          selectedFolderId === node.id ? "bg-sidebar-accent text-foreground" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60",
          dragOver && "ring-2 ring-primary"
        )}
        style={{ paddingLeft: 8 + depth * 16 }}
      >
        <button
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 rounded p-0.5 hover:bg-sidebar-accent"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {hasChildren ? (
            expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />
          ) : (
            <span className="block h-3.5 w-3.5" />
          )}
        </button>
        <button onClick={() => onSelect(node.id)} className="flex flex-1 items-center gap-2 truncate text-left">
          <FolderIcon className="h-4 w-4 shrink-0" />
          <span className="truncate font-medium">{node.name}</span>
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">{node.total_items}</span>
        </button>
        {hasRole(user, "editor") && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100">
                <MoreHorizontal className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setCreateSubfolderOpen(true)}>
                <FolderPlus className="h-4 w-4" /> New subfolder
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setRenameOpen(true)}>
                <Pencil className="h-4 w-4" /> Rename
              </DropdownMenuItem>
              {hasRole(user, "admin") && (
                <DropdownMenuItem destructive onClick={() => setDeleteOpen(true)}>
                  <Trash2 className="h-4 w-4" /> Delete
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <FolderNode key={child.id} node={child} depth={depth + 1} selectedFolderId={selectedFolderId} onSelect={onSelect} onChanged={onChanged} />
          ))}
        </div>
      )}
      <PromptDialog
        open={renameOpen}
        onOpenChange={setRenameOpen}
        title="Rename folder"
        defaultValue={node.name}
        submitLabel="Rename"
        onSubmit={handleRename}
      />
      <PromptDialog
        open={createSubfolderOpen}
        onOpenChange={setCreateSubfolderOpen}
        title="New subfolder"
        placeholder="Subfolder name"
        submitLabel="Create"
        onSubmit={handleCreateSubfolder}
      />
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={deleteIsRecursive ? `Delete "${node.name}" and its contents?` : `Delete empty folder "${node.name}"?`}
        description={
          deleteIsRecursive
            ? `"${node.name}" contains ${node.total_items} record(s) and/or subfolders. Records are unfiled, never deleted.`
            : undefined
        }
        confirmLabel="Delete"
        destructive
        onConfirm={handleDelete}
      />
    </div>
  );
}
