import { prisma } from "@/lib/prisma";
import * as XLSX from "xlsx";

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const jobIdParam = searchParams.get("jobId");
    if (!jobIdParam) {
      return new Response("Missing jobId", { status: 400 });
    }
    const jobId = Number(jobIdParam);
    if (Number.isNaN(jobId)) {
      return new Response("Invalid jobId", { status: 400 });
    }

    // Fetch job + candidates
    const job = await prisma.jobDescription.findUnique({
      where: { id: jobId },
      select: { role_category: true, job_description: true },
    });

    if (!job) {
      return new Response("Job not found", { status: 404 });
    }

    const candidates = await prisma.candidateScore.findMany({
      where: { job_id: jobId },
      orderBy: { final_rank: "asc" },
      select: {
        candidate_name: true,
        resume_email: true,
        final_score: true,
        final_rank: true,
        detailed_reasoning: true,
        strengths: true,
        weaknesses: true,
        recommendation: true,
      },
    });

    // Normalize values for Excel cells
    const normalize = (v: unknown) => {
      if (v == null) return "";
      if (Array.isArray(v))
        return v
          .map((x) => (typeof x === "string" ? x : JSON.stringify(x)))
          .join(", ");
      if (typeof v === "object") return JSON.stringify(v, null, 2);
      return String(v);
    };

    // Build rows (include job meta per row so the file is self-contained)
    const rows = candidates.map((c) => ({
      "Job Role": job.role_category ?? "",
      "Job Description": job.job_description ?? "",
      Rank: c.final_rank ?? "",
      "Candidate Name": c.candidate_name ?? "",
      Email: c.resume_email ?? "",
      "Final Score":
        typeof c.final_score === "number"
          ? c.final_score
          : normalize(c.final_score),
      Recommendation: normalize(c.recommendation),
      Strengths: normalize(c.strengths),
      Weaknesses: normalize(c.weaknesses),
      "Detailed Reasoning": normalize(c.detailed_reasoning),
    }));

    // If no candidates, still return a sheet with headers
    const dataForSheet = rows.length
      ? rows
      : [
          {
            "Job Role": job.role_category ?? "",
            "Job Description": job.job_description ?? "",
            Rank: "",
            "Candidate Name": "",
            Email: "",
            "Final Score": "",
            Recommendation: "",
            Strengths: "",
            Weaknesses: "",
            "Detailed Reasoning": "",
          },
        ];

    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.json_to_sheet(dataForSheet, { skipHeader: false });
    XLSX.utils.book_append_sheet(wb, ws, "Candidates");

    // Generate a Node buffer
    const buf = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });

    const filename = `candidates-job-${jobId}.xlsx`;
    return new Response(buf, {
      status: 200,
      headers: {
        "Content-Type":
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    console.error("EXPORT ERROR:", err);
    return new Response("Failed to export candidates", { status: 500 });
  }
}
