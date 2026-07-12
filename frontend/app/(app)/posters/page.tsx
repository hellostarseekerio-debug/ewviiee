"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  ClipboardPaste,
  Download,
  ExternalLink,
  FolderKanban,
  LayoutGrid,
  List as ListIcon,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { postersApi } from "@/lib/api/endpoints";
import type { PosterFilters } from "@/lib/api/endpoints";
import type { PosterOut } from "@/lib/api/types";
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
import { ApprovalBadge } from "@/components/documents/status-badge";

const PAGE_SIZE = 24;

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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const apiFilters = toApiFilters(filters);
      const response = filters.q.trim()
        ? await postersApi.search({ q: filters.q.trim(), ...apiFilters, skip: page * PAGE_SIZE, limit: PAGE_SIZE })
        : await postersApi.list({ ...apiFilters, skip: page * PAGE_SIZE, limit: PAGE_SIZE });
      setPosters(response.results);
      setTotal(response.total);
      setSelected(new Set());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load posters");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    load();
  }, [load]);

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    if (!confirm(`Delete ${selected.size} selected record(s)? This cannot be undone.`)) return;
    try {
      await postersApi.bulkDelete(Array.from(selected));
      toast.success(`Deleted ${selected.size} record(s)`);
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Bulk delete failed");
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this record?")) return;
    try {
      await postersApi.remove(id);
      toast.success("Deleted");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  async function handleExport() {
    try {
      await postersApi.downloadCsv(toApiFilters(filters));
    } catch {
      toast.error("Export failed");
    }
  }

  return (
    <div className="flex flex-col gap-5">
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
          <Button variant="outline" onClick={handleExport}>
            <Download className="h-4 w-4" /> Export CSV
          </Button>
          {hasRole(user, "editor") && (
            <>
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

      {selected.size > 0 && hasRole(user, "admin") && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="flex items-center justify-between p-3">
            <p className="text-sm font-medium">{selected.size} selected</p>
            <Button variant="destructive" size="sm" onClick={handleBulkDelete}>
              <Trash2 className="h-4 w-4" /> Delete selected
            </Button>
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
          <p>No poster records yet. Paste a block of text to get started.</p>
        </div>
      ) : view === "table" ? (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
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
                  <TableRow key={p.id}>
                    <TableCell>
                      <Checkbox checked={selected.has(p.id)} onCheckedChange={() => toggleSelected(p.id)} />
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <p className="truncate font-medium">{p.poster_title || "(untitled)"}</p>
                      {p.poster_type && (
                        <Badge variant="outline" className="mt-1 capitalize">
                          {p.poster_type}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {[p.district, p.estate].filter(Boolean).join(" · ") || "—"}
                    </TableCell>
                    <TableCell>{p.route_number || "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {p.document_date ? new Date(p.document_date).toLocaleDateString() : "—"}
                    </TableCell>
                    <TableCell>
                      <ApprovalBadge status={p.approval_status} />
                    </TableCell>
                    <TableCell>
                      {p.dropbox_url ? (
                        <Button variant="outline" size="sm" asChild>
                          <a href={p.dropbox_url} target="_blank" rel="noopener noreferrer">
                            <ExternalLink className="h-3.5 w-3.5" /> Open Dropbox
                          </a>
                        </Button>
                      ) : (
                        <Badge variant="secondary">Missing</Badge>
                      )}
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
            <Card key={p.id}>
              <CardContent className="flex flex-col gap-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <Checkbox checked={selected.has(p.id)} onCheckedChange={() => toggleSelected(p.id)} />
                  <ApprovalBadge status={p.approval_status} />
                </div>
                <p className="line-clamp-2 font-medium">{p.poster_title || "(untitled)"}</p>
                <p className="text-xs text-muted-foreground">
                  {[p.district, p.estate].filter(Boolean).join(" · ") || "No district/estate detected"}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {p.route_number && <Badge variant="secondary">Route {p.route_number}</Badge>}
                  {p.poster_type && <Badge variant="outline" className="capitalize">{p.poster_type}</Badge>}
                  {p.document_date && <Badge variant="outline">{new Date(p.document_date).toLocaleDateString()}</Badge>}
                </div>
                <div className="mt-2 flex items-center justify-between">
                  {p.dropbox_url ? (
                    <Button variant="outline" size="sm" asChild>
                      <a href={p.dropbox_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="h-3.5 w-3.5" /> Open Dropbox
                      </a>
                    </Button>
                  ) : (
                    <Badge variant="secondary">Missing Dropbox</Badge>
                  )}
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

      <PasteImportDialog open={pasteOpen} onOpenChange={setPasteOpen} onImported={load} />
      {editTarget && (
        <PosterEditDialog
          poster={editTarget === "new" ? null : editTarget}
          onOpenChange={(open) => !open && setEditTarget(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}

function PasteImportDialog({
  open,
  onOpenChange,
  onImported,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
}) {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleImport() {
    setSubmitting(true);
    try {
      const result = await postersApi.import(text);
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
            confidently detected is left blank rather than guessed.
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
}: {
  poster: PosterOut | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [district, setDistrict] = useState(poster?.district ?? "");
  const [estate, setEstate] = useState(poster?.estate ?? "");
  const [title, setTitle] = useState(poster?.poster_title ?? "");
  const [posterType, setPosterType] = useState(poster?.poster_type ?? "");
  const [route, setRoute] = useState(poster?.route_number ?? "");
  const [dropboxUrl, setDropboxUrl] = useState(poster?.dropbox_url ?? "");
  const [notes, setNotes] = useState(poster?.notes ?? "");
  const [submitting, setSubmitting] = useState(false);

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
          <DialogFooter className="col-span-2">
            <Button type="submit" loading={submitting}>
              {poster ? "Save changes" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
