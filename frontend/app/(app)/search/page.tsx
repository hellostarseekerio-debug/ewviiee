"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { FileText, SearchIcon, SlidersHorizontal } from "lucide-react";
import { searchApi } from "@/lib/api/endpoints";
import type { DocumentOut } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApprovalBadge, StatusBadge } from "@/components/documents/status-badge";

const PAGE_SIZE = 20;

interface Filters {
  keyword: string;
  district: string;
  estate: string;
  politician: string;
  reference_number: string;
  workflow_name: string;
}

const emptyFilters: Filters = {
  keyword: "",
  district: "",
  estate: "",
  politician: "",
  reference_number: "",
  workflow_name: "",
};

export default function SearchPage() {
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [showFilters, setShowFilters] = useState(false);
  const [results, setResults] = useState<DocumentOut[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  // Guards against a race where a slower, earlier keystroke's request
  // resolves after a newer one and overwrites fresher results - every
  // runSearch() call stamps the request it fires, and any response whose
  // stamp doesn't match the latest one by the time it resolves is
  // discarded rather than applied to state.
  const latestRequestId = useRef(0);

  useEffect(() => {
    function handler(event: KeyboardEvent) {
      if (event.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    const hasAnyFilter = Object.values(filters).some((v) => v.trim());
    if (!hasAnyFilter) {
      setResults([]);
      setSearched(false);
      return;
    }
    const timeout = setTimeout(() => runSearch(0), 300);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  async function runSearch(newOffset: number) {
    const requestId = ++latestRequestId.current;
    setLoading(true);
    setSearched(true);
    try {
      const response = await searchApi.search({
        keyword: filters.keyword.trim() || undefined,
        district: filters.district.trim() || undefined,
        estate: filters.estate.trim() || undefined,
        politician: filters.politician.trim() || undefined,
        reference_number: filters.reference_number.trim() || undefined,
        workflow_name: filters.workflow_name.trim() || undefined,
        limit: PAGE_SIZE,
        offset: newOffset,
      });
      if (requestId !== latestRequestId.current) return; // a newer search already superseded this one
      setResults(response.results);
      setTotal(response.total);
      setOffset(newOffset);
    } catch (err) {
      if (requestId !== latestRequestId.current) return;
      toast.error(err instanceof ApiError ? err.message : "Search failed");
    } finally {
      if (requestId === latestRequestId.current) setLoading(false);
    }
  }

  function updateFilter(key: keyof Filters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Search</h1>
        <p className="text-sm text-muted-foreground">
          Search across every document&apos;s title, extracted text, and metadata. Press{" "}
          <kbd className="rounded border border-border bg-muted px-1 text-xs">/</kbd> to jump to search.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                ref={inputRef}
                className="pl-9"
                placeholder="Search documents..."
                value={filters.keyword}
                onChange={(e) => updateFilter("keyword", e.target.value)}
                autoFocus
              />
            </div>
            <Button variant="outline" onClick={() => setShowFilters((v) => !v)}>
              <SlidersHorizontal className="h-4 w-4" /> Filters
            </Button>
          </div>

          {showFilters && (
            <div className="grid grid-cols-1 gap-3 border-t border-border pt-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="f-district">District</Label>
                <Input id="f-district" value={filters.district} onChange={(e) => updateFilter("district", e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="f-estate">Estate</Label>
                <Input id="f-estate" value={filters.estate} onChange={(e) => updateFilter("estate", e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="f-politician">Politician</Label>
                <Input id="f-politician" value={filters.politician} onChange={(e) => updateFilter("politician", e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="f-reference">Reference number</Label>
                <Input id="f-reference" value={filters.reference_number} onChange={(e) => updateFilter("reference_number", e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5 sm:col-span-2 lg:col-span-4">
                <Label htmlFor="f-workflow">Workflow</Label>
                <Input id="f-workflow" value={filters.workflow_name} onChange={(e) => updateFilter("workflow_name", e.target.value)} />
              </div>
              <div className="sm:col-span-2 lg:col-span-4">
                <Button variant="ghost" size="sm" onClick={() => setFilters(emptyFilters)}>
                  Clear all filters
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : !searched ? (
        <div className="flex flex-col items-center gap-2 py-16 text-center text-muted-foreground">
          <SearchIcon className="h-10 w-10" />
          <p>Start typing to search across your office&apos;s documents.</p>
        </div>
      ) : results.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-16 text-center text-muted-foreground">
          <FileText className="h-10 w-10" />
          <p>No documents matched your search.</p>
        </div>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">{total} result{total === 1 ? "" : "s"}</p>
          <div className="flex flex-col gap-2">
            {results.map((doc) => (
              <Link key={doc.id} href={`/documents/${doc.id}`}>
                <Card className="transition-colors hover:bg-accent/50">
                  <CardContent className="flex items-start justify-between gap-4 p-4">
                    <div className="flex items-start gap-3">
                      <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                      <div>
                        <p className="font-medium">{doc.title || doc.filename}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {[doc.district, doc.estate, doc.politician].filter(Boolean).join(" · ") || doc.filename}
                        </p>
                      </div>
                    </div>
                    <div className="flex shrink-0 gap-1.5">
                      <StatusBadge status={doc.status} />
                      <ApprovalBadge status={doc.approval_status} />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
          <div className="flex justify-center gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => runSearch(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => runSearch(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
