"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";

type Props = {
  jobId: number;
  total: number; // total candidates for this JD
};

export default function SendEmailsControl({ jobId, total }: Props) {
  const max = Math.max(0, total);
  const min = max > 0 ? 1 : 0;

  const [n, setN] = useState<number>(max);
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<
    "idle" | "running" | "complete" | "error"
  >("idle");
  const [progress, setProgress] = useState(0);
  const { toast } = useToast();

  // Clamp input
  useEffect(() => {
    setN((prev) => clamp(prev, min, max));
  }, [min, max]);

  // Indeterminate progress animation until server responds
  useEffect(() => {
    if (status === "running") {
      setProgress(10);
      const id = setInterval(() => {
        setProgress((p) => (p >= 90 ? 90 : p + 2));
      }, 200);
      return () => clearInterval(id);
    }
    if (status === "complete") setProgress(100);
    if (status === "idle" || status === "error") setProgress(0);
  }, [status]);

  const isAll = useMemo(() => n >= max && max > 0, [n, max]);
  const disabled = max === 0;

  const onSlider = (e: React.ChangeEvent<HTMLInputElement>) => {
    setN(clamp(Number(e.target.value), min, max));
  };
  const onNumber = (e: React.ChangeEvent<HTMLInputElement>) => {
    setN(clamp(Number(e.target.value), min, max));
  };

  const sendEmails = async () => {
    if (disabled) return;
    setOpen(true);
    setStatus("running");

    // Uses the existing /api/chat → agent → email flow
    const message = isAll
      ? `send email to everyone in jd_id:${jobId}`
      : `send email to the top ${n} in jd_id:${jobId}`;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();

      if (res.ok && data?.status === "success") {
        setStatus("complete");
        toast({
          title: "Emails sent",
          description: isAll
            ? `Invitations sent to all (${max}) candidates.`
            : `Invitations sent to top ${n}.`,
        });
        setTimeout(() => setOpen(false), 800);
      } else {
        const err = data?.error || data?.reply || "Unknown error";
        setStatus("error");
        toast({
          variant: "destructive",
          title: "Failed to send emails",
          description: err,
        });
      }
    } catch (e: any) {
      setStatus("error");
      toast({
        variant: "destructive",
        title: "Failed to send emails",
        description: e?.message || String(e),
      });
    }
  };

  return (
    <div className="rounded-xl border p-4 mb-6 bg-white">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <label className="font-semibold">
            {max > 0 ? `Select top N (1–${max})` : "No candidates to email"}
          </label>
          <span className="text-sm text-gray-600">
            {isAll ? `All (${max})` : `Top ${n} of ${max}`}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <input
            type="range"
            min={min}
            max={max || 1}
            step={1}
            value={n}
            onChange={onSlider}
            className="flex-1"
            disabled={disabled}
          />
          <input
            type="number"
            min={min}
            max={max}
            step={1}
            value={n}
            onChange={onNumber}
            className="w-20 rounded border px-2 py-1"
            disabled={disabled}
          />
          <Button
            onClick={sendEmails}
            disabled={disabled}
            className="whitespace-nowrap"
          >
            Send Mails
          </Button>
        </div>

        <p className="text-xs text-gray-500">
          {isAll
            ? `Will send: "send email to everyone in jd_id:${jobId}"`
            : `Will send: "send email to the top ${n} in jd_id:${jobId}"`}
        </p>
      </div>

      {/* Modal with progress */}
      <Modal isOpen={open} onClose={() => setOpen(false)}>
        <div className="p-6 w-[360px] sm:w-[480px]">
          <h2 className="text-xl font-bold mb-3">Sending invitations</h2>
          <div className="space-y-2">
            <div className="text-sm text-muted-foreground">
              {status === "running" && "Sending emails…"}
              {status === "complete" && "Completed ✔"}
              {status === "error" && "An error occurred."}
            </div>
            <Progress value={progress} />
            <div className="text-xs text-muted-foreground">{progress}%</div>
          </div>
          <div className="mt-6 flex justify-end">
            {status !== "running" && (
              <Button onClick={() => setOpen(false)}>Close</Button>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}

function clamp(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.max(min, Math.min(max, v));
}
