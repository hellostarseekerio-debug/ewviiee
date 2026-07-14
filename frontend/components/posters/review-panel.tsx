"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { postersApi } from "@/lib/api/endpoints";
import type { PosterOut } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

// The fields the metadata extraction engine tracks confidence for (see
// Poster.extraction_confidence / app/posters/parser.py's field_confidence) -
// shown here so staff reviewing a flagged record see exactly which fields
// the parser was unsure about, not just an all-or-nothing warning.
const REVIEWABLE_FIELDS: Array<{ key: keyof PosterOut; label: string }> = [
  { key: "poster_title", label: "Title" },
  { key: "district", label: "District" },
  { key: "estate", label: "Estate" },
  { key: "poster_type", label: "Poster type" },
  { key: "route_number", label: "Route" },
];

const LOW_CONFIDENCE_THRESHOLD = 0.8;

export function overallConfidence(poster: PosterOut): number | null {
  // Only fields the record actually has a value for count toward the
  // score - a poster with no bus route to begin with (most records) isn't
  // "less confident" for lacking one, so a null field is excluded rather
  // than scored as 0. This mirrors needs_review's own definition (a
  // record is flagged when its identifying fields are missing, not
  // whenever any field the parser didn't find happens to have a low
  // stored confidence).
  const scores = REVIEWABLE_FIELDS.filter((f) => poster[f.key]).map(
    (f) => poster.extraction_confidence?.[f.key as string]
  );
  const known = scores.filter((v): v is number => typeof v === "number");
  if (known.length === 0) return null;
  return known.reduce((sum, v) => sum + v, 0) / known.length;
}

export function ConfidenceBadge({ poster }: { poster: PosterOut }) {
  const score = overallConfidence(poster);
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const low = score < LOW_CONFIDENCE_THRESHOLD;
  return (
    <Badge variant={low ? "warning" : "secondary"} className="gap-1 tabular-nums">
      {low ? <AlertTriangle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
      {pct}%{low ? " Needs review" : ""}
    </Badge>
  );
}

function FieldConfidence({ poster, field }: { poster: PosterOut; field: string }) {
  const score = poster.extraction_confidence?.[field];
  const source = poster.extraction_sources?.[field];
  if (typeof score !== "number") return null;
  const pct = Math.round(score * 100);
  const low = score < LOW_CONFIDENCE_THRESHOLD;
  return (
    <span className={`text-xs ${low ? "text-warning" : "text-muted-foreground"}`}>
      {pct}%{source ? ` · ${source}` : ""}
    </span>
  );
}

export function ReviewPanel({
  poster,
  onOpenChange,
  onSaved,
}: {
  poster: PosterOut | null;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [district, setDistrict] = useState("");
  const [estate, setEstate] = useState("");
  const [posterType, setPosterType] = useState("");
  const [route, setRoute] = useState("");
  const [title, setTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!poster) return;
    setDistrict(poster.district ?? "");
    setEstate(poster.estate ?? "");
    setPosterType(poster.poster_type ?? "");
    setRoute(poster.route_number ?? "");
    setTitle(poster.poster_title ?? "");
  }, [poster]);

  if (!poster) return null;

  async function handleSave() {
    if (!poster) return;
    setSubmitting(true);
    try {
      await postersApi.update(poster.id, {
        district: district || null,
        estate: estate || null,
        poster_type: posterType || null,
        route_number: route || null,
        poster_title: title || null,
        needs_review: false,
      });
      toast.success(
        "Saved - corrections to the district are remembered automatically for future imports of the same estate"
      );
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Sheet open onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full max-w-md overflow-y-auto">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-semibold">Review record</h2>
          <p className="text-xs text-muted-foreground">
            The parser flagged this record as low-confidence. Correct any field below - a district correction is
            remembered so future imports mentioning the same estate fill it in automatically.
          </p>
        </div>

        <div className="mt-4 flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label>Title</Label>
              <FieldConfidence poster={poster} field="poster_title" />
            </div>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label>District</Label>
              <FieldConfidence poster={poster} field="district" />
            </div>
            <Input value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="e.g. 大埔" />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label>Estate</Label>
              <FieldConfidence poster={poster} field="estate" />
            </div>
            <Input value={estate} onChange={(e) => setEstate(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label>Poster type</Label>
              <FieldConfidence poster={poster} field="poster_type" />
            </div>
            <Input value={posterType} onChange={(e) => setPosterType(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label>Route</Label>
              <FieldConfidence poster={poster} field="route_number" />
            </div>
            <Input value={route} onChange={(e) => setRoute(e.target.value)} />
          </div>

          <div className="mt-2 rounded-md border border-border p-3 text-xs text-muted-foreground">
            <p className="truncate">Source: {poster.source_text || "(manual record, no source text)"}</p>
          </div>

          <Button className="mt-2" loading={submitting} onClick={handleSave}>
            Save and clear review flag
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
