"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Check, Download, History, RotateCcw, X } from "lucide-react";
import { documentsApi } from "@/lib/api/endpoints";
import { getToken } from "@/lib/api/client";
import type { DocumentOut, DocumentVersionOut } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { useAuth, hasRole } from "@/lib/auth-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { ApprovalBadge, StatusBadge } from "@/components/documents/status-badge";
import { ConfirmDialog } from "@/components/ui/prompt-dialog";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm">{value ?? "—"}</p>
    </div>
  );
}

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [document, setDocument] = useState<DocumentOut | null>(null);
  const [versions, setVersions] = useState<DocumentVersionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [doc, vers] = await Promise.all([
        documentsApi.get(params.id),
        documentsApi.versions(params.id),
      ]);
      setDocument(doc);
      setVersions(vers);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleReview(decision: "approve" | "reject") {
    setBusy(true);
    try {
      const updated = decision === "approve" ? await documentsApi.approve(params.id, notes) : await documentsApi.reject(params.id, notes);
      setDocument(updated);
      setNotes("");
      toast.success(decision === "approve" ? "Document approved" : "Document rejected");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleRollback(versionId: string) {
    setBusy(true);
    try {
      const updated = await documentsApi.rollback(params.id, versionId);
      setDocument(updated);
      toast.success("Rolled back to selected version");
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Rollback failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleDownload() {
    try {
      const response = await fetch(documentsApi.downloadUrl(params.id), {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement("a");
      a.href = url;
      a.download = document?.filename ?? "document";
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Could not download this document");
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!document) {
    return <p className="text-sm text-muted-foreground">Document not found.</p>;
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" aria-label="Back" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-semibold tracking-tight">{document.title || document.filename}</h1>
          <div className="mt-1 flex items-center gap-2">
            <StatusBadge status={document.status} />
            <ApprovalBadge status={document.approval_status} />
          </div>
        </div>
        <Button variant="outline" onClick={handleDownload}>
          <Download className="h-4 w-4" /> Download
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Field label="District" value={document.district} />
            <Field label="Estate" value={document.estate} />
            <Field label="Politician" value={document.politician} />
            <Field label="Reference number" value={document.reference_number} />
            <Field label="Document date" value={document.document_date ? new Date(document.document_date).toLocaleDateString() : null} />
            <Field label="Language" value={document.language} />
            <Field label="Version" value={document.version} />
            <Field label="Workflow" value={document.workflow_name} />
            <Field label="Document type" value={document.document_type} />
            <Field label="AI confidence" value={document.ai_confidence != null ? `${Math.round(document.ai_confidence * 100)}%` : null} />
            <Field label="OCR confidence" value={document.ocr_confidence != null ? `${Math.round(document.ocr_confidence * 100)}%` : null} />
            <Field label="Reviewed by" value={document.reviewed_by} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Review</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {hasRole(user, "reviewer") ? (
              <>
                <Textarea
                  placeholder="Notes (optional)"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                />
                <div className="flex gap-2">
                  <Button className="flex-1" disabled={busy} onClick={() => handleReview("approve")}>
                    <Check className="h-4 w-4" /> Approve
                  </Button>
                  <Button variant="destructive" className="flex-1" disabled={busy} onClick={() => handleReview("reject")}>
                    <X className="h-4 w-4" /> Reject
                  </Button>
                </div>
                {document.review_notes && (
                  <p className="rounded-md bg-muted p-2 text-xs text-muted-foreground">{document.review_notes}</p>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Reviewer permissions are required to approve or reject documents.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-4 w-4" /> Version history
          </CardTitle>
        </CardHeader>
        <CardContent>
          {versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No generated versions yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {versions.map((version, i) => (
                <li key={version.id}>
                  {i > 0 && <Separator className="mb-2" />}
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">Version {version.version_number}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {version.created_by ?? "system"} · {new Date(version.created_at).toLocaleString()}
                        {version.notes ? ` · ${version.notes}` : ""}
                      </p>
                    </div>
                    {hasRole(user, "editor") && (
                      <Button variant="outline" size="sm" disabled={busy} onClick={() => setRollbackTarget(version.id)}>
                        <RotateCcw className="h-3.5 w-3.5" /> Restore
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <ConfirmDialog
        open={rollbackTarget !== null}
        onOpenChange={(open) => !open && setRollbackTarget(null)}
        title="Restore this version?"
        description="The document will return for review."
        confirmLabel="Restore"
        onConfirm={() => rollbackTarget && handleRollback(rollbackTarget)}
      />
    </div>
  );
}
