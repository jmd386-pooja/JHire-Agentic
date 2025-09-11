"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { Loader } from "@/components/ui/loader";

type Props = {
  jobId: number;
  disabled?: boolean;
};

export default function ExportCandidatesButton({ jobId, disabled }: Props) {
  const [loading, setLoading] = useState(false);

  async function handleExport() {
    try {
      setLoading(true);
      const res = await fetch(`/api/export-candidates?jobId=${jobId}`, {
        method: "GET",
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `candidates-job-${jobId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert("Failed to export candidates. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      onClick={handleExport}
      className="inline-flex items-center gap-2"
      disabled={disabled || loading}
      aria-label="Export candidates as Excel"
      title="Export candidates as Excel"
    >
      {loading ? <Loader size="sm" /> : <Download className="h-4 w-4" />}
      Export
    </Button>
  );
}
