"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  AlertTriangle,
  Copy,
  Download,
  FileText,
  FolderKanban,
  Users,
  Sparkles,
  HardDrive,
  Upload,
  Search as SearchIcon,
  UserPlus,
  CheckCircle2,
  Clock,
  XCircle,
} from "lucide-react";
import { dashboardApi } from "@/lib/api/endpoints";
import type { DashboardStats } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth, hasRole } from "@/lib/auth-context";

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between p-5">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</p>
          {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-accent-foreground">
          <Icon className="h-4.5 w-4.5" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setStats(await dashboardApi.stats());
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to load dashboard stats");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          Welcome back{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}
        </h1>
        <p className="text-sm text-muted-foreground">Here&apos;s what&apos;s happening across your office.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <StatCard icon={FileText} label="Total documents" value={stats.total_documents} />
            <StatCard
              icon={CheckCircle2}
              label="Approved"
              value={stats.documents_by_approval_status.approved ?? 0}
              sub={`${stats.documents_by_approval_status.pending ?? 0} pending review`}
            />
            <StatCard icon={Users} label="Active users" value={`${stats.active_users}/${stats.total_users}`} />
            <StatCard
              icon={Sparkles}
              label="AI operations"
              value={stats.ai_usage_total}
              sub={`${stats.ai_usage_local} local · ${stats.ai_usage_cloud} cloud`}
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <StatCard icon={FolderKanban} label="Poster records" value={stats.total_posters} />
            <StatCard icon={Clock} label="Pending reviews" value={stats.pending_reviews} />
            <StatCard
              icon={AlertTriangle}
              label="Broken Dropbox links"
              value={stats.broken_dropbox_links}
              sub={stats.broken_dropbox_links > 0 ? "Needs verification" : undefined}
            />
            <StatCard icon={Copy} label="Possible duplicates" value={stats.duplicate_poster_groups} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <StatCard icon={Download} label="Downloads today" value={stats.downloads_today} />
            <StatCard
              icon={HardDrive}
              label="Export storage used"
              value={`${(stats.export_storage_bytes / (1024 * 1024)).toFixed(1)} MB`}
            />
            <StatCard
              icon={Users}
              label="Most active user"
              value={stats.most_active_users[0]?.actor ?? "—"}
              sub={stats.most_active_users[0] ? `${stats.most_active_users[0].action_count} actions` : undefined}
            />
            <StatCard
              icon={FileText}
              label="Recent poster uploads"
              value={stats.recent_poster_uploads.length}
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading || !stats ? (
              <div className="space-y-3 p-5 pt-0">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : stats.recent_activity.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-10 text-center">
                <HardDrive className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">No activity yet - it will show up here as your office uses the platform.</p>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {stats.recent_activity.map((event, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                    <div className="flex items-center gap-3">
                      {event.success ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                      ) : (
                        <XCircle className="h-4 w-4 shrink-0 text-destructive" />
                      )}
                      <div>
                        <p className="font-medium">{event.action.replaceAll("_", " ")}</p>
                        <p className="text-xs text-muted-foreground">
                          {event.actor ?? "system"}
                          {event.resource_type ? ` · ${event.resource_type}` : ""}
                        </p>
                      </div>
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Button asChild variant="outline" className="justify-start">
              <Link href="/documents">
                <Upload className="h-4 w-4" /> Upload a document
              </Link>
            </Button>
            <Button asChild variant="outline" className="justify-start">
              <Link href="/search">
                <SearchIcon className="h-4 w-4" /> Search documents
              </Link>
            </Button>
            {hasRole(user, "admin") && (
              <Button asChild variant="outline" className="justify-start">
                <Link href="/admin/users">
                  <UserPlus className="h-4 w-4" /> Invite a colleague
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {!loading && stats && (
        <Card>
          <CardHeader>
            <CardTitle>Documents by status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {Object.entries(stats.documents_by_status).length === 0 ? (
              <p className="text-sm text-muted-foreground">No documents processed yet.</p>
            ) : (
              Object.entries(stats.documents_by_status).map(([status, count]) => (
                <Badge key={status} variant="secondary" className="gap-1.5 py-1 capitalize">
                  {status.replaceAll("_", " ")}
                  <span className="rounded-full bg-background px-1.5 text-[10px] font-semibold">{count}</span>
                </Badge>
              ))
            )}
          </CardContent>
        </Card>
      )}

      {!loading && stats && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Posters by district</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {Object.entries(stats.posters_by_district).length === 0 ? (
                <p className="text-sm text-muted-foreground">No posters filed to a district yet.</p>
              ) : (
                Object.entries(stats.posters_by_district).map(([district, count]) => (
                  <Badge key={district} variant="secondary" className="gap-1.5 py-1">
                    {district}
                    <span className="rounded-full bg-background px-1.5 text-[10px] font-semibold">{count}</span>
                  </Badge>
                ))
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Posters by estate</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {Object.entries(stats.posters_by_estate).length === 0 ? (
                <p className="text-sm text-muted-foreground">No posters filed to an estate yet.</p>
              ) : (
                Object.entries(stats.posters_by_estate).map(([estate, count]) => (
                  <Badge key={estate} variant="secondary" className="gap-1.5 py-1">
                    {estate}
                    <span className="rounded-full bg-background px-1.5 text-[10px] font-semibold">{count}</span>
                  </Badge>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {!loading && stats && stats.recent_poster_uploads.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent poster uploads</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y divide-border">
              {stats.recent_poster_uploads.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                  <div>
                    <p className="font-medium">{p.title || "(untitled)"}</p>
                    <p className="text-xs text-muted-foreground">
                      {[p.district, p.estate].filter(Boolean).join(" · ") || "Unfiled"}
                    </p>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(p.created_at), { addSuffix: true })}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
