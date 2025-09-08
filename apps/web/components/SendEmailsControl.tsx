"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";

type Props = {
  jobId: number;
  total: number; // total candidates for this JD
};

export default function SendEmailsControl({ jobId, total }: Props) {
  const max = Math.max(0, total);
  const min = max > 0 ? 1 : 0;

  // default to "all"
  const [n, setN] = useState<number>(max);

  // keep input value clamped
  useEffect(() => {
    setN((prev) => clamp(prev, min, max));
  }, [min, max]);

  const isAll = useMemo(() => n >= max && max > 0, [n, max]);
  const disabled = max === 0;

  const onSlider = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setN(clamp(val, min, max));
  };

  const onNumber = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    const val = raw === "" ? NaN : Number(raw);
    if (Number.isNaN(val)) {
      setN(min);
    } else {
      setN(clamp(val, min, max));
    }
  };

  const send = async () => {
    if (disabled) {
      alert("No candidates available for this job.");
      return;
    }
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
        alert(
          typeof data.reply === "string"
            ? data.reply
            : "Email command sent successfully."
        );
      } else {
        const err = data?.error || data?.reply || "Unknown error";
        alert(`Failed: ${err}`);
        // (optional) console for deeper details
        // eslint-disable-next-line no-console
        console.error("Email send response", data);
      }
    } catch (e: any) {
      alert(`Request failed: ${e?.message || e}`);
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

        {/* Range slider */}
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={n}
          onChange={onSlider}
          disabled={disabled}
          className="w-full"
        />

        {/* Number input (kept in sync) */}
        <div className="flex items-center gap-3">
          <input
            type="number"
            min={min}
            max={max}
            step={1}
            value={Number.isFinite(n) ? n : ""}
            onChange={onNumber}
            disabled={disabled}
            className="w-28 border rounded px-3 py-2"
          />
          <Button onClick={send} disabled={disabled}>
            {isAll ? "Send to Everyone" : `Send Top ${n}`}
          </Button>
        </div>

        {/* Helper hint */}
        <p className="text-xs text-gray-500">
          {isAll
            ? `Will send: "send email to everyone in jd_id:${jobId}"`
            : `Will send: "send email to the top ${n} in jd_id:${jobId}"`}
        </p>
      </div>
    </div>
  );
}

function clamp(v: number, min: number, max: number) {
  if (!Number.isFinite(v)) return min;
  return Math.max(min, Math.min(max, v));
}
