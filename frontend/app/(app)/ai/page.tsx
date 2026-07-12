"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Cloud, Cpu, Info, Sparkles, Workflow } from "lucide-react";
import { dashboardApi, pluginsApi, workflowsApi } from "@/lib/api/endpoints";
import type { DashboardStats, PluginOut, WorkflowSummary } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export default function AiInsightsPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [plugins, setPlugins] = useState<PluginOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, w, p] = await Promise.all([dashboardApi.stats(), workflowsApi.list(), pluginsApi.list()]);
        setStats(s);
        setWorkflows(w);
        setPlugins(p);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to load AI insights");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Sparkles className="h-5 w-5" /> AI Insights
        </h1>
        <p className="text-sm text-muted-foreground">How AI is being used to process your office&apos;s documents.</p>
      </div>

      <Card className="border-dashed">
        <CardContent className="flex gap-3 p-4">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            This platform doesn&apos;t have a conversational AI assistant (chat) yet - AI runs automatically inside
            document workflows below (OCR, field extraction, classification) rather than through free-form chat. The
            numbers here reflect that automatic usage, tracked in the audit log.
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {loading || !stats ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24" />)
        ) : (
          <>
            <Card>
              <CardContent className="p-5">
                <p className="text-xs font-medium text-muted-foreground">Total AI operations</p>
                <p className="mt-1.5 text-2xl font-semibold">{stats.ai_usage_total}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center justify-between p-5">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Local / on-prem</p>
                  <p className="mt-1.5 text-2xl font-semibold">{stats.ai_usage_local}</p>
                </div>
                <Cpu className="h-5 w-5 text-muted-foreground" />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center justify-between p-5">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Cloud provider</p>
                  <p className="mt-1.5 text-2xl font-semibold">{stats.ai_usage_cloud}</p>
                </div>
                <Cloud className="h-5 w-5 text-muted-foreground" />
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Workflow className="h-4 w-4" /> Available workflows
          </CardTitle>
          <CardDescription>Each run applies OCR, extraction, and classification automatically.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {loading ? (
            <Skeleton className="h-16" />
          ) : workflows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No workflows configured.</p>
          ) : (
            workflows.map((wf) => (
              <div key={wf.name} className="flex items-center justify-between rounded-lg border border-border p-3">
                <div>
                  <p className="text-sm font-medium">{wf.display_name}</p>
                  <p className="text-xs text-muted-foreground">{wf.stages.join(" → ")}</p>
                </div>
                <Badge variant="secondary">{wf.plugin}</Badge>
              </div>
            ))
          )}
          <Button asChild variant="outline" className="mt-2 w-fit">
            <Link href="/documents">Go upload a document to run through a workflow</Link>
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Installed plugins</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {loading ? (
            <Skeleton className="h-8 w-32" />
          ) : plugins.length === 0 ? (
            <p className="text-sm text-muted-foreground">No plugins installed.</p>
          ) : (
            plugins.map((p) => (
              <Badge key={p.plugin_id} variant="outline">
                {p.display_name} · v{p.version}
              </Badge>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
