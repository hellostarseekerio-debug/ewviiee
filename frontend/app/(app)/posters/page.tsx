"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  Archive,
  ChevronDown,
  ClipboardPaste,
  Clock,
  Copy,
  Download,
  ExternalLink,
  FolderInput,
  FolderKanban,
  LayoutGrid,
  List as ListIcon,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Star,
  Trash2,
} from "lucide-react";
import { exportJobsApi, foldersApi, postersApi, starredApi } from "@/lib/api/endpoints";
import type { PosterFilters } from "@/lib/api/endpoints";
import type {
  DuplicateGroupOut,
  FolderOut,
  FolderTreeNodeOut,
  PosterOut,
  PosterStatusValue,
  PosterZipExportRequest,
} from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { useAuth, hasRole } from "@/lib/auth-context";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PosterStatusBadge } from "@/components/documents/status-badge";
import { FolderTree, posterDragProps } from "@/components/folders/folder-tree";
import { FolderBreadcrumbs } from "@/components/folders/breadcrumbs";
import { FolderPickerDialog } from "@/components/folders/folder-picker-dialog";
import { PromptDialog } from "@/components/ui/prompt-dialog";
import { ConfidenceBadge, ReviewPanel } from "@/components/posters/review-panel";

// Mirrors app/posters/status.py's POSTER_STATUS_TRANSITIONS - purely to
// decide which options to *offer* in the menu below. The server is the
// real authority: it re-validates every transition and role requirement
// on every request regardless of what this list suggests.
const POSTER_NEXT_STATUSES: Record<PosterStatusValue, PosterStatusValue[]> = {
  draft: ["pending_review"],
  pending_review: ["approved", "rejected", "needs_changes", "draft"],
  needs_changes: ["draft", "pending_review"],
  approved: ["published", "pending_review"],
  published: ["archived"],
  rejected: ["draft", "pending_review"],
  archived: [],
};

const POSTER_STATUS_LABEL: Record<PosterStatusValue, string> = {
  draft: "Draft",
  pending_review: "Pending review",
  needs_changes: "Needs changes",
  approved: "Approved",
  published: "Published",
  rejected: "Rejected",
  archived: "Archived",
};

function PosterStatusMenu({ poster, onChanged }: { poster: PosterOut; onChanged: () => void }) {
  // poster.status is only guaranteed by the TypeScript contract, not at
  // runtime - an out-of-sync backend deploy or unexpected data can send a
  // value outside the known set, and indexing this map would silently
  // return undefined. Fall back to "no transitions offered" rather than
  // crashing the whole page on `.length`.
  const nextStatuses = POSTER_NEXT_STATUSES[poster.status] ?? [];

  async function handleChange(next: PosterStatusValue) {
    try {
      await postersApi.changeStatus(poster.id, { status: next });
      toast.success(`Status changed to ${POSTER_STATUS_LABEL[next]}`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Status change failed");
    }
  }

  if (nextStatuses.length === 0) {
    return <PosterStatusBadge status={poster.status} />;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="h-auto gap-1 p-0 hover:bg-transparent">
          <PosterStatusBadge status={poster.status} />
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuLabel>Change status</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {nextStatuses.map((next) => (
          <DropdownMenuItem key={next} onClick={() => handleChange(next)}>
            {POSTER_STATUS_LABEL[next]}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function StarToggle({ starred, onToggle }: { starred: boolean; onToggle: () => void }) {
  return (
    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onToggle} aria-label={starred ? "Unstar" : "Star"}>
      <Star className={`h-4 w-4 ${starred ? "fill-warning text-warning" : "text-muted-foreground"}`} />
    </Button>
  );
}

// Dropbox Improvements: preview/open, copy link, verify link (real HTTP
// check via app/storage/providers/dropbox.py's verify()), broken-link
// detection, and last-verified timestamp.
function DropboxLinkCell({ poster, onChanged }: { poster: PosterOut; onChanged: () => void }) {
  const [verifying, setVerifying] = useState(false);

  async function handleCopy() {
    if (!poster.dropbox_url) return;
    await navigator.clipboard.writeText(poster.dropbox_url);
    toast.success("Link copied");
  }

  async function handleVerify() {
    setVerifying(true);
    try {
      const result = await postersApi.verifyLink(poster.id);
      if (result.dropbox_link_broken) {
        toast.error("Link appears broken");
      } else {
        toast.success("Link verified OK");
      }
      onChanged();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verification failed");
    } finally {
      setVerifying(false);
    }
  }

  if (!poster.dropbox_url) {
    return <Badge variant="secondary">Missing</Badge>;
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" asChild>
          <a href={poster.dropbox_url} target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-3.5 w-3.5" /> Open
          </a>
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleCopy} aria-label="Copy Dropbox link">
          <Copy className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={handleVerify}
          disabled={verifying}
          aria-label="Verify Dropbox link"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${verifying ? "animate-spin" : ""}`} />
        </Button>
      </div>
      {poster.dropbox_link_broken === true && (
        <Badge variant="destructive" className="w-fit gap-1">
          <AlertTriangle className="h-3 w-3" /> Broken link
        </Badge>
      )}
      {poster.dropbox_last_verified_at && (
        <span className="text-[10px] text-muted-foreground">
          Verified {new Date(poster.dropbox_last_verified_at).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}

const PAGE_SIZE = 24;

type ViewMode =
  | { kind: "folder"; folderId: string | null }
  | { kind: "status"; status: PosterStatusValue }
  | { kind: "favorites" };

interface Filters {
  q: string;
  district: string;
  poster_type: string;
  date_from: string;
  date_to: string;
  has_dropbox: "all" | "yes" | "no";
}

const emptyFilters: Filters = { q: "", district: "", poster_type: "", date_from: "", date_to: "", has_dropbox: "all" };

function toApiFilters(f: Filters): PosterFilters {
  const out: PosterFilters = {};
  if (f.district.trim()) out.district = f.district.trim();
  if (f.poster_type.trim()) out.poster_type = f.poster_type.trim();
  if (f.date_from) out.date_from = f.date_from;
  if (f.date_to) out.date_to = f.date_to;
  if (f.has_dropbox !== "all") out.has_dropbox = f.has_dropbox === "yes";
  return out;
}

export default function PosterArchivePage() {
  const { user } = useAuth();
  const [posters, setPosters] = useState<PosterOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [view, setView] = useState<"table" | "card">("table");
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pasteOpen, setPasteOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<PosterOut | "new" | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>({ kind: "folder", folderId: null });
  const [folderTree, setFolderTree] = useState<FolderTreeNodeOut[]>([]);
  const [breadcrumbs, setBreadcrumbs] = useState<FolderOut[]>([]);
  const [starredIds, setStarredIds] = useState<Set<string>>(new Set());
  const [movePickerOpen, setMovePickerOpen] = useState(false);
  const [bulkEditOpen, setBulkEditOpen] = useState(false);
  const [duplicatesOpen, setDuplicatesOpen] = useState(false);
  const [reviewTarget, setReviewTarget] = useState<PosterOut | null>(null);
  const [exporting, setExporting] = useState(false);
  const [reparsing, setReparsing] = useState(false);
  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadTree = useCallback(async () => {
    try {
      const tree = await foldersApi.tree("poster");
      setFolderTree(tree);
    } catch {
      // Non-fatal - the main list still works without the tree.
    }
  }, []);

  const loadStarred = useCallback(async () => {
    try {
      const items = await starredApi.list("poster");
      setStarredIds(new Set(items.map((i) => i.resource_id)));
    } catch {
      // Favorites are a convenience feature - failing to load them must
      // never block the rest of the page.
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const apiFilters = toApiFilters(filters);
      if (viewMode.kind === "favorites") {
        const items = await starredApi.list("poster");
        setStarredIds(new Set(items.map((i) => i.resource_id)));
        const fetched = await Promise.allSettled(items.map((i) => postersApi.get(i.resource_id)));
        const results = fetched.flatMap((r) => (r.status === "fulfilled" ? [r.value] : []));
        setPosters(results.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE));
        setTotal(results.length);
      } else if (viewMode.kind === "status") {
        const response = await postersApi.list({
          ...apiFilters,
          status: viewMode.status,
          skip: page * PAGE_SIZE,
          limit: PAGE_SIZE,
        } as PosterFilters & { status: string; skip: number; limit: number });
        setPosters(response.results);
        setTotal(response.total);
      } else {
        const folderParams = viewMode.folderId ? { folder_id: viewMode.folderId, recursive: true } : {};
        const response = filters.q.trim()
          ? await postersApi.search({ q: filters.q.trim(), ...apiFilters, ...folderParams, skip: page * PAGE_SIZE, limit: PAGE_SIZE })
          : await postersApi.list({ ...apiFilters, ...folderParams, skip: page * PAGE_SIZE, limit: PAGE_SIZE });
        setPosters(response.results);
        setTotal(response.total);
      }
      setSelected(new Set());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load posters");
    } finally {
      setLoading(false);
    }
  }, [filters, page, viewMode]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadTree();
    loadStarred();
  }, [loadTree, loadStarred]);

  useEffect(() => {
    if (viewMode.kind === "folder" && viewMode.folderId) {
      foldersApi
        .get(viewMode.folderId)
        .then((detail) => setBreadcrumbs(detail.breadcrumbs))
        .catch(() => setBreadcrumbs([]));
    } else {
      setBreadcrumbs([]);
    }
  }, [viewMode]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function refreshAll() {
    load();
    loadTree();
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function toggleStar(posterId: string) {
    const wasStarred = starredIds.has(posterId);
    try {
      if (wasStarred) {
        await starredApi.unstar("poster", posterId);
      } else {
        await starredApi.star("poster", posterId);
      }
      setStarredIds((prev) => {
        const next = new Set(prev);
        if (wasStarred) next.delete(posterId);
        else next.add(posterId);
        return next;
      });
      if (viewMode.kind === "favorites" && wasStarred) load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update favorite");
    }
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    if (!confirm(`Delete ${selected.size} selected record(s)? This cannot be undone.`)) return;
    try {
      await postersApi.bulkDelete(Array.from(selected));
      toast.success(`Deleted ${selected.size} record(s)`);
      refreshAll();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Bulk delete failed");
    }
  }

  async function handleBulkMove(folderId: string | null) {
    if (selected.size === 0) return;
    try {
      const result = await postersApi.bulkMove({ ids: Array.from(selected), folder_id: folderId });
      toast.success(`Moved ${result.moved} record(s)`);
      refreshAll();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Move failed");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this record?")) return;
    try {
      await postersApi.remove(id);
      toast.success("Deleted");
      refreshAll();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function handleExportCsv() {
    try {
      await postersApi.downloadCsv(toApiFilters(filters));
    } catch {
      toast.error("Export failed");
    }
  }

  async function handleReparse() {
    setReparsing(true);
    try {
      const result = await postersApi.reparse();
      toast.success(`Re-parsed ${result.scanned} record(s) - ${result.updated} updated`);
      refreshAll();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Reparse failed");
    } finally {
      setReparsing(false);
    }
  }

  function pollExportJob(jobId: string) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const job = await exportJobsApi.get(jobId);
        if (job.status === "completed") {
          if (pollRef.current) clearInterval(pollRef.current);
          await exportJobsApi.download(jobId);
          toast.success("ZIP export ready and downloaded");
        } else if (job.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          toast.error(job.error_message || "Export failed");
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 2000);
  }

  async function handleExportZip(payload: PosterZipExportRequest) {
    setExporting(true);
    try {
      const result = await postersApi.exportZip(payload);
      if (result.kind === "downloaded") {
        toast.success("ZIP downloaded");
      } else {
        toast.success(`Export queued (${result.job.total_items} records) - preparing in the background...`);
        pollExportJob(result.job.job_id);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  function currentViewZipPayload(): PosterZipExportRequest {
    const apiFilters = toApiFilters(filters);
    const payload: PosterZipExportRequest = { ...apiFilters };
    if (filters.q.trim()) payload.q = filters.q.trim();
    if (viewMode.kind === "folder" && viewMode.folderId) {
      payload.folder_id = viewMode.folderId;
      payload.recursive = true;
    }
    return payload;
  }

  const emptyStateMessage =
    viewMode.kind === "favorites"
      ? "No favorites yet - star a record to find it here quickly."
      : viewMode.kind === "status"
        ? `No ${POSTER_STATUS_LABEL[viewMode.status].toLowerCase()} records.`
        : viewMode.folderId
          ? "This folder is empty."
          : "No poster records yet. Paste a block of text to get started.";

  return (
    <div className="flex flex-col gap-5 lg:flex-row">
      <aside className="flex shrink-0 flex-col gap-4 lg:w-64">
        <div className="flex flex-col gap-0.5">
          <SidebarQuickView
            icon={Clock}
            label="Recent"
            active={viewMode.kind === "folder" && viewMode.folderId === null}
            onClick={() => setViewMode({ kind: "folder", folderId: null })}
          />
          <SidebarQuickView
            icon={Star}
            label="Favorites"
            active={viewMode.kind === "favorites"}
            onClick={() => setViewMode({ kind: "favorites" })}
          />
          <SidebarQuickView
            icon={Loader2}
            label="Processing"
            active={viewMode.kind === "status" && viewMode.status === "pending_review"}
            onClick={() => setViewMode({ kind: "status", status: "pending_review" })}
          />
          <SidebarQuickView
            icon={Archive}
            label="Archived"
            active={viewMode.kind === "status" && viewMode.status === "archived"}
            onClick={() => setViewMode({ kind: "status", status: "archived" })}
          />
        </div>
        <div className="flex flex-col gap-1">
          <p className="px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Folders</p>
          <FolderTree
            nodes={folderTree}
            selectedFolderId={viewMode.kind === "folder" ? viewMode.folderId : null}
            onSelect={(folderId) => setViewMode({ kind: "folder", folderId })}
            onChanged={refreshAll}
          />
          {hasRole(user, "editor") && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-1 justify-start text-muted-foreground"
              onClick={() => setNewFolderOpen(true)}
            >
              <Plus className="h-3.5 w-3.5" /> New folder
            </Button>
          )}
          <PromptDialog
            open={newFolderOpen}
            onOpenChange={setNewFolderOpen}
            title="New top-level folder"
            placeholder="Folder name"
            submitLabel="Create"
            onSubmit={async (name) => {
              try {
                await foldersApi.create({ name, parent_id: null });
                loadTree();
              } catch (err) {
                toast.error(err instanceof ApiError ? err.message : "Create failed");
              }
            }}
          />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col gap-5">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
              <FolderKanban className="h-5 w-5" /> Poster Archive
            </h1>
            <p className="text-sm text-muted-foreground">
              Paste a block of text containing Dropbox links to automatically parse and organize poster records.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleExportCsv}>
              <Download className="h-4 w-4" /> Export CSV
            </Button>
            <Button variant="outline" loading={exporting} onClick={() => handleExportZip(currentViewZipPayload())}>
              <Download className="h-4 w-4" /> Download ZIP
            </Button>
            <Button variant="outline" onClick={() => setDuplicatesOpen(true)}>
              <Copy className="h-4 w-4" /> Duplicates
            </Button>
            {hasRole(user, "editor") && (
              <>
                <Button variant="outline" loading={reparsing} onClick={handleReparse}>
                  <RefreshCw className="h-4 w-4" /> Re-parse existing
                </Button>
                <Button variant="outline" onClick={() => setEditTarget("new")}>
                  <Plus className="h-4 w-4" /> Add manually
                </Button>
                <Button onClick={() => setPasteOpen(true)}>
                  <ClipboardPaste className="h-4 w-4" /> Paste text
                </Button>
              </>
            )}
          </div>
        </div>

        {viewMode.kind === "folder" && (
          <FolderBreadcrumbs crumbs={breadcrumbs} onNavigate={(folderId) => setViewMode({ kind: "folder", folderId })} />
        )}

        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Input
                placeholder="Search district, estate, title, route, Dropbox URL..."
                value={filters.q}
                onChange={(e) => {
                  setPage(0);
                  setFilters((f) => ({ ...f, q: e.target.value }));
                }}
                className="sm:max-w-sm"
              />
              <div className="ml-auto flex gap-1 rounded-lg border border-border p-1">
                <Button
                  variant={view === "table" ? "secondary" : "ghost"}
                  size="sm"
                  onClick={() => setView("table")}
                >
                  <ListIcon className="h-4 w-4" /> Table
                </Button>
                <Button variant={view === "card" ? "secondary" : "ghost"} size="sm" onClick={() => setView("card")}>
                  <LayoutGrid className="h-4 w-4" /> Cards
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-muted-foreground">District</Label>
                <Input
                  value={filters.district}
                  onChange={(e) => {
                    setPage(0);
                    setFilters((f) => ({ ...f, district: e.target.value }));
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-muted-foreground">Poster type</Label>
                <Input
                  placeholder="poster / notice / ..."
                  value={filters.poster_type}
                  onChange={(e) => {
                    setPage(0);
                    setFilters((f) => ({ ...f, poster_type: e.target.value }));
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-muted-foreground">Date from</Label>
                <Input
                  type="date"
                  value={filters.date_from}
                  onChange={(e) => {
                    setPage(0);
                    setFilters((f) => ({ ...f, date_from: e.target.value }));
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-muted-foreground">Date to</Label>
                <Input
                  type="date"
                  value={filters.date_to}
                  onChange={(e) => {
                    setPage(0);
                    setFilters((f) => ({ ...f, date_to: e.target.value }));
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-muted-foreground">Dropbox link</Label>
                <Select
                  value={filters.has_dropbox}
                  onValueChange={(v) => {
                    setPage(0);
                    setFilters((f) => ({ ...f, has_dropbox: v as Filters["has_dropbox"] }));
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="yes">Has Dropbox</SelectItem>
                    <SelectItem value="no">Missing Dropbox</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {selected.size > 0 && (
          <Card className="border-primary/40 bg-primary/5">
            <CardContent className="flex flex-wrap items-center justify-between gap-2 p-3">
              <p className="text-sm font-medium">{selected.size} selected</p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => handleExportZip({ ids: Array.from(selected) })} loading={exporting}>
                  <Download className="h-4 w-4" /> Download ZIP
                </Button>
                {hasRole(user, "editor") && (
                  <Button variant="outline" size="sm" onClick={() => setMovePickerOpen(true)}>
                    <FolderInput className="h-4 w-4" /> Move to folder
                  </Button>
                )}
                {hasRole(user, "editor") && (
                  <Button variant="outline" size="sm" onClick={() => setBulkEditOpen(true)}>
                    <Pencil className="h-4 w-4" /> Bulk edit
                  </Button>
                )}
                {hasRole(user, "admin") && (
                  <Button variant="destructive" size="sm" onClick={handleBulkDelete}>
                    <Trash2 className="h-4 w-4" /> Delete selected
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : posters.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16 text-center text-muted-foreground">
            <FolderKanban className="h-10 w-10" />
            <p>{emptyStateMessage}</p>
          </div>
        ) : view === "table" ? (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10" />
                    <TableHead className="w-10" />
                    <TableHead>Title</TableHead>
                    <TableHead>District / Estate</TableHead>
                    <TableHead>Route</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Dropbox</TableHead>
                    <TableHead className="w-16" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {posters.map((p) => (
                    <TableRow
                      key={p.id}
                      {...posterDragProps(p.id, selected)}
                      className={p.needs_review ? "cursor-pointer bg-warning/5 hover:bg-warning/10" : undefined}
                      onClick={(e) => {
                        if (!p.needs_review) return;
                        // Ignore clicks on interactive elements within the row
                        // (checkbox, star, status menu, dropbox buttons, action
                        // icons) - only the row background itself opens review.
                        if ((e.target as HTMLElement).closest("button, a, input")) return;
                        setReviewTarget(p);
                      }}
                    >
                      <TableCell>
                        <Checkbox checked={selected.has(p.id)} onCheckedChange={() => toggleSelected(p.id)} />
                      </TableCell>
                      <TableCell>
                        <StarToggle starred={starredIds.has(p.id)} onToggle={() => toggleStar(p.id)} />
                      </TableCell>
                      <TableCell className="max-w-xs">
                        <p className="truncate font-medium">{p.poster_title || "(untitled)"}</p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {p.poster_type && (
                            <Badge variant="outline" className="capitalize">
                              {p.poster_type.replaceAll("_", " ")}
                            </Badge>
                          )}
                          {p.needs_review && (
                            <Badge variant="warning" className="gap-1">
                              <AlertTriangle className="h-3 w-3" /> Needs review
                            </Badge>
                          )}
                          <ConfidenceBadge poster={p} />
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {[p.district, p.estate].filter(Boolean).join(" · ") || "—"}
                      </TableCell>
                      <TableCell>{p.route_number || "—"}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {p.document_date ? new Date(p.document_date).toLocaleDateString() : "—"}
                      </TableCell>
                      <TableCell>
                        {hasRole(user, "editor") ? (
                          <PosterStatusMenu poster={p} onChanged={load} />
                        ) : (
                          <PosterStatusBadge status={p.status} />
                        )}
                      </TableCell>
                      <TableCell>
                        <DropboxLinkCell poster={p} onChanged={load} />
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {hasRole(user, "editor") && (
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditTarget(p)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                          )}
                          {hasRole(user, "admin") && (
                            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDelete(p.id)}>
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {posters.map((p) => (
              <Card
                key={p.id}
                {...posterDragProps(p.id, selected)}
                className={p.needs_review ? "cursor-pointer border-warning/40 bg-warning/5" : undefined}
                onClick={(e) => {
                  if (!p.needs_review) return;
                  if ((e.target as HTMLElement).closest("button, a, input")) return;
                  setReviewTarget(p);
                }}
              >
                <CardContent className="flex flex-col gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-1">
                      <Checkbox checked={selected.has(p.id)} onCheckedChange={() => toggleSelected(p.id)} />
                      <StarToggle starred={starredIds.has(p.id)} onToggle={() => toggleStar(p.id)} />
                    </div>
                    {hasRole(user, "editor") ? (
                      <PosterStatusMenu poster={p} onChanged={load} />
                    ) : (
                      <PosterStatusBadge status={p.status} />
                    )}
                  </div>
                  <p className="line-clamp-2 font-medium">{p.poster_title || "(untitled)"}</p>
                  <p className="text-xs text-muted-foreground">
                    {[p.district, p.estate].filter(Boolean).join(" · ") || "No district/estate detected"}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {p.route_number && <Badge variant="secondary">Route {p.route_number}</Badge>}
                    {p.poster_type && (
                      <Badge variant="outline" className="capitalize">
                        {p.poster_type.replaceAll("_", " ")}
                      </Badge>
                    )}
                    {p.document_date && <Badge variant="outline">{new Date(p.document_date).toLocaleDateString()}</Badge>}
                    {p.needs_review && (
                      <Badge variant="warning" className="gap-1">
                        <AlertTriangle className="h-3 w-3" /> Needs review
                      </Badge>
                    )}
                    <ConfidenceBadge poster={p} />
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <DropboxLinkCell poster={p} onChanged={load} />
                    <div className="flex gap-1">
                      {hasRole(user, "editor") && (
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setEditTarget(p)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                      {hasRole(user, "admin") && (
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDelete(p.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {!loading && posters.length > 0 && (
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">{total} total result{total === 1 ? "" : "s"}</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}

        <PasteImportDialog
          open={pasteOpen}
          onOpenChange={setPasteOpen}
          onImported={refreshAll}
          currentFolderId={viewMode.kind === "folder" ? viewMode.folderId : null}
        />
        {editTarget && (
          <PosterEditDialog
            poster={editTarget === "new" ? null : editTarget}
            onOpenChange={(open) => !open && setEditTarget(null)}
            onSaved={refreshAll}
            defaultFolderId={viewMode.kind === "folder" ? viewMode.folderId : null}
          />
        )}
        <FolderPickerDialog
          open={movePickerOpen}
          onOpenChange={setMovePickerOpen}
          onConfirm={handleBulkMove}
          title={`Move ${selected.size} record(s)`}
        />
        <DuplicatesDialog open={duplicatesOpen} onOpenChange={setDuplicatesOpen} />
        <BulkEditDialog
          open={bulkEditOpen}
          onOpenChange={setBulkEditOpen}
          count={selected.size}
          onConfirm={async (fields) => {
            try {
              const result = await postersApi.bulkUpdate({ ids: Array.from(selected), ...fields });
              toast.success(`Updated ${result.updated} record(s)`);
              refreshAll();
            } catch (err) {
              toast.error(err instanceof ApiError ? err.message : "Bulk edit failed");
            }
          }}
        />
        <ReviewPanel
          poster={reviewTarget}
          onOpenChange={(open) => !open && setReviewTarget(null)}
          onSaved={refreshAll}
        />
      </div>
    </div>
  );
}

function DuplicatesDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [groups, setGroups] = useState<DuplicateGroupOut[]>([]);
  const [posterTitles, setPosterTitles] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    postersApi
      .duplicates()
      .then(async (result) => {
        setGroups(result);
        const ids = Array.from(new Set(result.flatMap((g) => g.poster_ids)));
        const fetched = await Promise.allSettled(ids.map((id) => postersApi.get(id)));
        const titles: Record<string, string> = {};
        fetched.forEach((r, i) => {
          if (r.status === "fulfilled") titles[ids[i]] = r.value.poster_title || "(untitled)";
        });
        setPosterTitles(titles);
      })
      .catch(() => toast.error("Failed to load duplicates"))
      .finally(() => setLoading(false));
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Possible duplicates</DialogTitle>
          <DialogDescription>
            Exact Dropbox link reuse and similar titles - review and merge/edit manually; nothing here is changed
            automatically.
          </DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No duplicates detected.</p>
        ) : (
          <div className="flex max-h-96 flex-col gap-3 overflow-y-auto">
            {groups.map((group, i) => (
              <Card key={i}>
                <CardContent className="flex flex-col gap-1 p-3">
                  <Badge variant="outline" className="w-fit capitalize">
                    {group.reason.replaceAll("_", " ")}
                  </Badge>
                  <ul className="text-sm">
                    {group.poster_ids.map((id) => (
                      <li key={id} className="truncate text-muted-foreground">
                        {posterTitles[id] ?? id}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function BulkEditDialog({
  open,
  onOpenChange,
  count,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  count: number;
  onConfirm: (fields: { district?: string | null; estate?: string | null; poster_type?: string | null }) => void;
}) {
  const [district, setDistrict] = useState("");
  const [estate, setEstate] = useState("");
  const [posterType, setPosterType] = useState("");

  function handleConfirm() {
    onConfirm({
      district: district.trim() || undefined,
      estate: estate.trim() || undefined,
      poster_type: posterType.trim() || undefined,
    });
    setDistrict("");
    setEstate("");
    setPosterType("");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Bulk edit {count} record(s)</DialogTitle>
          <DialogDescription>Only fields you fill in are changed - leave a field blank to leave it as-is.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>District</Label>
            <Input value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="Leave blank to keep unchanged" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Estate</Label>
            <Input value={estate} onChange={(e) => setEstate(e.target.value)} placeholder="Leave blank to keep unchanged" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Poster type</Label>
            <Input value={posterType} onChange={(e) => setPosterType(e.target.value)} placeholder="Leave blank to keep unchanged" />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={handleConfirm}>Apply</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SidebarQuickView({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm font-medium transition-colors ${
        active ? "bg-sidebar-accent text-foreground" : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60"
      }`}
    >
      <Icon className="h-4 w-4 shrink-0" /> {label}
    </button>
  );
}

function PasteImportDialog({
  open,
  onOpenChange,
  onImported,
  currentFolderId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
  currentFolderId: string | null;
}) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleImport() {
    setSubmitting(true);
    try {
      const result = await postersApi.import(text, currentFolderId ?? undefined);
      toast.success(
        `Imported ${result.imported} record(s) - ${result.duplicates} duplicate(s), ${result.invalid} invalid link(s) skipped`
      );
      setText("");
      onOpenChange(false);
      onImported();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Paste poster text</DialogTitle>
          <DialogDescription>
            Paste one or more records, each with a title line and a Dropbox link. District, estate, poster type,
            route number, date, language, and keywords are detected automatically - anything that can&apos;t be
            confidently detected is left blank rather than guessed. Records are auto-filed into a Year / Month /
            District / Estate folder{currentFolderId ? " (overridden: filed into the folder you're currently browsing)" : ""}.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          rows={14}
          className="font-mono text-xs"
          placeholder={"沙田 20260707-海報-好消息-73H-愉翠苑來往大埔富蝶邨\nhttps://www.dropbox.com/...\n\n【20260701-滬港兩地「跨境通辦」正式開通！】\nhttps://www.dropbox.com/..."}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <DialogFooter>
          <Button onClick={handleImport} loading={submitting} disabled={!text.trim()}>
            Import
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PosterEditDialog({
  poster,
  onOpenChange,
  onSaved,
  defaultFolderId,
}: {
  poster: PosterOut | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  defaultFolderId: string | null;
}) {
  const [district, setDistrict] = useState(poster?.district ?? "");
  const [estate, setEstate] = useState(poster?.estate ?? "");
  const [title, setTitle] = useState(poster?.poster_title ?? "");
  const [posterType, setPosterType] = useState(poster?.poster_type ?? "");
  const [route, setRoute] = useState(poster?.route_number ?? "");
  const [dropboxUrl, setDropboxUrl] = useState(poster?.dropbox_url ?? "");
  const [notes, setNotes] = useState(poster?.notes ?? "");
  const [campaignName, setCampaignName] = useState(poster?.campaign_name ?? "");
  const [governmentDepartment, setGovernmentDepartment] = useState(poster?.government_department ?? "");
  const [version, setVersion] = useState(poster?.version ?? "");
  const [folderId, setFolderId] = useState<string | null>(poster ? poster.folder_id : defaultFolderId);
  const [folderPickerOpen, setFolderPickerOpen] = useState(false);
  const [folderName, setFolderName] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!folderId) {
      setFolderName(null);
      return;
    }
    foldersApi
      .get(folderId)
      .then((detail) => setFolderName(detail.folder.name))
      .catch(() => setFolderName(null));
  }, [folderId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    const payload = {
      district: district || null,
      estate: estate || null,
      poster_title: title || null,
      poster_type: posterType || null,
      route_number: route || null,
      dropbox_url: dropboxUrl || null,
      notes: notes || null,
      campaign_name: campaignName || null,
      government_department: governmentDepartment || null,
      version: version || null,
      folder_id: folderId,
    };
    try {
      if (poster) {
        await postersApi.update(poster.id, payload);
        toast.success("Updated");
      } else {
        await postersApi.create(payload);
        toast.success("Created");
      }
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{poster ? "Edit poster record" : "Add poster record"}</DialogTitle>
        </DialogHeader>
        <form className="grid grid-cols-2 gap-3" onSubmit={handleSubmit}>
          <div className="col-span-2 flex flex-col gap-1.5">
            <Label>Title</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>District</Label>
            <Input value={district} onChange={(e) => setDistrict(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Estate</Label>
            <Input value={estate} onChange={(e) => setEstate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Poster type</Label>
            <Input value={posterType} onChange={(e) => setPosterType(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Route number</Label>
            <Input value={route} onChange={(e) => setRoute(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Campaign name</Label>
            <Input value={campaignName} onChange={(e) => setCampaignName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Government department</Label>
            <Input value={governmentDepartment} onChange={(e) => setGovernmentDepartment(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Version</Label>
            <Input value={version} onChange={(e) => setVersion(e.target.value)} />
          </div>
          <div className="col-span-2 flex flex-col gap-1.5">
            <Label>Dropbox URL</Label>
            <Input
              value={dropboxUrl}
              placeholder="https://www.dropbox.com/..."
              onChange={(e) => setDropboxUrl(e.target.value)}
            />
          </div>
          <div className="col-span-2 flex flex-col gap-1.5">
            <Label>Notes</Label>
            <Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="col-span-2 flex flex-col gap-1.5">
            <Label>Folder</Label>
            <div className="flex items-center gap-2">
              <span className="flex-1 truncate rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground">
                {folderName ?? "Auto-file by district/estate/date"}
              </span>
              <Button type="button" variant="outline" size="sm" onClick={() => setFolderPickerOpen(true)}>
                Change
              </Button>
            </div>
          </div>
          <DialogFooter className="col-span-2">
            <Button type="submit" loading={submitting}>
              {poster ? "Save changes" : "Create"}
            </Button>
          </DialogFooter>
        </form>
        <FolderPickerDialog
          open={folderPickerOpen}
          onOpenChange={setFolderPickerOpen}
          onConfirm={setFolderId}
          title="Choose a folder"
          description="Overrides automatic Year / Month / District / Estate filing for this record."
        />
      </DialogContent>
    </Dialog>
  );
}
