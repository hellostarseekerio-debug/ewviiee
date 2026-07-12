"use client";

import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { UploadCloud, File as FileIcon, X } from "lucide-react";
import { documentsApi } from "@/lib/api/endpoints";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PendingUpload {
  id: string;
  file: File;
  progress: number;
  status: "uploading" | "done" | "error";
  error?: string;
}

export function UploadDropzone({ onUploaded }: { onUploaded?: () => void }) {
  const [dragActive, setDragActive] = useState(false);
  const [uploads, setUploads] = useState<PendingUpload[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;
    Array.from(files).forEach((file) => {
      const id = `${file.name}-${file.size}-${Date.now()}`;
      setUploads((prev) => [...prev, { id, file, progress: 0, status: "uploading" }]);

      documentsApi
        .upload(file, (pct) => {
          setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, progress: pct } : u)));
        })
        .then(() => {
          setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, status: "done", progress: 100 } : u)));
          toast.success(`${file.name} uploaded - it will appear once a workflow processes it`);
          onUploaded?.();
        })
        .catch((err: Error) => {
          setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, status: "error", error: err.message } : u)));
          toast.error(`${file.name} failed to upload: ${err.message}`);
        });
    });
  }, [onUploaded]);

  return (
    <div className="flex flex-col gap-3">
      <div
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border p-8 text-center transition-colors",
          dragActive && "border-primary bg-accent/50"
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          handleFiles(e.dataTransfer.files);
        }}
      >
        <UploadCloud className="h-8 w-8 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">Drag and drop files here, or</p>
          <Button variant="link" className="h-auto p-0" onClick={() => inputRef.current?.click()}>
            browse from your computer
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">PDF, DOCX, PNG, JPG, TIFF, ZIP</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {uploads.length > 0 && (
        <ul className="flex flex-col gap-2">
          {uploads.map((u) => (
            <li key={u.id} className="flex items-center gap-3 rounded-lg border border-border p-2.5 text-sm">
              <FileIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{u.file.name}</p>
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      u.status === "error" ? "bg-destructive" : "bg-primary"
                    )}
                    style={{ width: `${u.progress}%` }}
                  />
                </div>
                {u.status === "error" && <p className="mt-1 text-xs text-destructive">{u.error}</p>}
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0"
                onClick={() => setUploads((prev) => prev.filter((x) => x.id !== u.id))}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
