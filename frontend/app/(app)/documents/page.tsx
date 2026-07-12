"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { FileText, Inbox, Trash2, UploadCloud } from "lucide-react";
import { documentsApi, searchApi } from "@/lib/api/endpoints";
import type { DocumentOut } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { useAuth, hasRole } from "@/lib/auth-context";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { ApprovalBadge, StatusBadge } from "@/components/documents/status-badge";
import { UploadDropzone } from "@/components/documents/upload-dropzone";

const PAGE_SIZE = 20;

export default function DocumentsPage() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (query.trim()) {
        const result = await searchApi.search({
          keyword: query.trim(),
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
        });
        setDocuments(result.results);
        setTotal(result.total);
      } else {
        const result = await documentsApi.list(page * PAGE_SIZE, PAGE_SIZE);
        setDocuments(result);
        setTotal(null);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [page, query]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this document? It can be recovered by an administrator if needed.")) return;
    try {
      await documentsApi.remove(id);
      toast.success("Document deleted");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to delete document");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Documents</h1>
          <p className="text-sm text-muted-foreground">Upload, review, and manage every document your office processes.</p>
        </div>
        {hasRole(user, "editor") && (
          <Button onClick={() => setUploadOpen(true)}>
            <UploadCloud className="h-4 w-4" /> Upload
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <Input
            placeholder="Search by district, estate, politician, reference..."
            value={query}
            onChange={(e) => {
              setPage(0);
              setQuery(e.target.value);
            }}
            className="sm:max-w-xs"
          />
          <p className="text-xs text-muted-foreground">
            Searches title, filename, and extracted text. Use the Search page for advanced filters.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
              <Inbox className="h-10 w-10 text-muted-foreground" />
              <p className="font-medium">No documents found</p>
              <p className="text-sm text-muted-foreground">
                {query ? "Try a different search term." : "Upload your first document to get started."}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>District / Estate</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Approval</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell>
                      <Link href={`/documents/${doc.id}`} className="flex items-center gap-2 font-medium hover:underline">
                        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="truncate">{doc.title || doc.filename}</span>
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {[doc.district, doc.estate].filter(Boolean).join(" · ") || "—"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={doc.status} />
                    </TableCell>
                    <TableCell>
                      <ApprovalBadge status={doc.approval_status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(doc.updated_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      {hasRole(user, "admin") && (
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDelete(doc.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {total !== null ? `${total} total results` : `Page ${page + 1}`}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={documents.length < PAGE_SIZE}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload documents</DialogTitle>
            <DialogDescription>
              Files are queued for import - run a workflow afterwards to process them into tracked documents.
            </DialogDescription>
          </DialogHeader>
          <UploadDropzone onUploaded={load} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
