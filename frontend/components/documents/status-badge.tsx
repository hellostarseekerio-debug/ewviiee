import { Badge } from "@/components/ui/badge";

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
