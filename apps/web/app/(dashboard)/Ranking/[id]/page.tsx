import { prisma } from "@/lib/prisma";
import SendEmailsControl from "@/components/SendEmailsControl";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import ExportCandidatesButton from "@/components/ExportCandidatesButton";

// Next 15 App Router: params is async in Server Components
type PageProps = {
  params: Promise<{ id: string }>;
};

// Turn arrays/strings into a neat list of chips
function toList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((v) => (typeof v === "string" ? v.trim() : String(v)))
      .filter(Boolean);
  }
  if (typeof value === "string") {
    return value
      .split(/[\n,]+/) // lines or commas
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

export default async function CandidatePage({ params }: PageProps) {
  const { id } = await params;
  const jobId = Number(id);

  const job = await prisma.jobDescription.findUnique({
    where: { id: jobId },
    select: { role_category: true, job_description: true },
  });

  if (!job) {
    return <p className="p-6">Job not found</p>;
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

  return (
    // NOTE: no min-h-screen; let the dashboard <main> own scrolling
    <div className="bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
        <header className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold">
              {job.role_category} — Candidates
            </h2>
            <p className="mt-2 text-gray-700">{job.job_description}</p>
          </div>

          <div className="shrink-0">
            <ExportCandidatesButton
              jobId={jobId}
              disabled={candidates.length === 0}
            />
          </div>
        </header>

        {/* Range + input + send (Client Component is rendered, not invoked) */}
        <div className="mb-6">
          <SendEmailsControl jobId={jobId} total={candidates.length} />
        </div>

        {candidates.length === 0 ? (
          <p className="text-gray-600">
            No candidates found for this job description.
          </p>
        ) : (
          <Accordion
            type="single"
            collapsible
            className="w-full rounded-xl border border-gray-200 bg-white shadow-sm"
          >
            {candidates.map((c, idx) => {
              const strengths = toList(c.strengths);
              const weaknesses = toList(c.weaknesses);
              const score =
                typeof c.final_score === "number"
                  ? c.final_score.toFixed(2)
                  : String(c.final_score ?? "");

              return (
                <AccordionItem
                  key={`${c.resume_email}-${idx}`}
                  value={`candidate-${idx + 1}`}
                  className="px-3 sm:px-4"
                >
                  <AccordionTrigger className="group py-4 hover:no-underline">
                    <div className="flex w-full items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex h-6 min-w-[1.75rem] items-center justify-center rounded-full bg-slate-100 px-2 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200">
                            {c.final_rank}
                          </span>
                          <h3 className="truncate text-base font-semibold text-gray-900">
                            {c.candidate_name}
                          </h3>
                        </div>
                        <p className="mt-0.5 truncate text-sm text-gray-600">
                          {c.resume_email}
                        </p>
                      </div>

                      <div className="shrink-0 text-right">
                        <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-100">
                          Score: {score}
                        </span>
                      </div>
                    </div>
                  </AccordionTrigger>

                  <AccordionContent className="pb-5">
                    <div className="grid gap-4 sm:gap-6 sm:grid-cols-2">
                      {/* Recommendation */}
                      <section className="sm:col-span-2">
                        <h4 className="mb-2 text-sm font-semibold text-gray-900">
                          Recommendation
                        </h4>
                        <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-800 ring-1 ring-inset ring-gray-200">
                          <pre className="whitespace-pre-wrap break-words">
                            {c.recommendation}
                          </pre>
                        </div>
                      </section>

                      {/* Strengths */}
                      <section>
                        <h4 className="mb-2 text-sm font-semibold text-gray-900">
                          Strengths
                        </h4>
                        {strengths.length > 0 ? (
                          <ul className="flex flex-wrap gap-2">
                            {strengths.map((s, i) => (
                              <li
                                key={`s-${i}`}
                                className="inline-flex items-center rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700 ring-1 ring-inset ring-sky-100"
                              >
                                {s}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700 ring-1 ring-inset ring-gray-200">
                            <pre className="whitespace-pre-wrap break-words">
                              {typeof c.strengths === "string"
                                ? c.strengths
                                : JSON.stringify(c.strengths, null, 2)}
                            </pre>
                          </div>
                        )}
                      </section>

                      {/* Weaknesses */}
                      <section>
                        <h4 className="mb-2 text-sm font-semibold text-gray-900">
                          Weaknesses
                        </h4>
                        {weaknesses.length > 0 ? (
                          <ul className="flex flex-wrap gap-2">
                            {weaknesses.map((w, i) => (
                              <li
                                key={`w-${i}`}
                                className="inline-flex items-center rounded-full bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-100"
                              >
                                {w}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700 ring-1 ring-inset ring-gray-200">
                            <pre className="whitespace-pre-wrap break-words">
                              {typeof c.weaknesses === "string"
                                ? c.weaknesses
                                : JSON.stringify(c.weaknesses, null, 2)}
                            </pre>
                          </div>
                        )}
                      </section>

                      {/* Detailed Reasoning */}
                      <section className="sm:col-span-2">
                        <h4 className="mb-2 text-sm font-semibold text-gray-900">
                          Detailed Reasoning
                        </h4>
                        <div className="max-h-64 overflow-auto rounded-lg bg-gray-50 p-3 text-sm text-gray-800 ring-1 ring-inset ring-gray-200">
                          <pre className="whitespace-pre-wrap break-words">
                            {c.detailed_reasoning}
                          </pre>
                        </div>
                      </section>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        )}
      </div>
    </div>
  );
}
