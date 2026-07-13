import { Badge } from "@/components/ui/badge";
import type { PosterStatusValue } from "@/lib/api/types";

export function ApprovalBadge({ status }: { status: "pending" | "approved" | "rejected" }) {
  const variant = status === "approved" ? "success" : status === "rejected" ? "destructive" : "warning";
  return (
    <Badge variant={variant} className="capitalize">
      {status}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant="secondary" className="capitalize">
      {status.replaceAll("_", " ")}
    </Badge>
  );
}

// Poster Archive lifecycle - see app/posters/status.py for the transition
// graph this mirrors. Kept separate from ApprovalBadge (still used for
// Documents' pending/approved/rejected review status) since Poster now has
// a richer, seven-state lifecycle rather than a flat three-state one.
const POSTER_STATUS_VARIANT: Record<PosterStatusValue, "secondary" | "warning" | "success" | "destructive" | "outline"> = {
  draft: "secondary",
  pending_review: "warning",
  needs_changes: "warning",
  approved: "success",
  published: "success",
  rejected: "destructive",
  archived: "outline",
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

export function PosterStatusBadge({ status }: { status: PosterStatusValue }) {
  return <Badge variant={POSTER_STATUS_VARIANT[status]}>{POSTER_STATUS_LABEL[status]}</Badge>;
}
