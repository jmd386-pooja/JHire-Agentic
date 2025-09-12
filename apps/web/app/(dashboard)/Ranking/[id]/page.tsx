import { prisma } from "@/lib/prisma";
import SendEmailsControl from "@/components/SendEmailsControl";
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import ExportCandidatesButton from "@/components/ExportCandidatesButton";

/**
 * Next.js App Router (RSC)
 * In Next 15 server components, route params are provided as a Promise.
 * If you’re on 14, switching the type to `{ params: { id: string } }` also works.
 */
type PageProps = {
  params: Promise<{ id: string }>;
};

function toBigInt(id: string) {
  const n = Number(id);
  if (!Number.isFinite(n)) throw new Error("Invalid id");
  return BigInt(n);
}

function toList(val: unknown): string[] {
  if (Array.isArray(val))
    return val.map((v) => (typeof v === "string" ? v : JSON.stringify(v)));
  if (typeof val === "string") return [val];
  if (val && typeof val === "object") return [JSON.stringify(val)];
  return [];
}

export default async function RankingPage({ params }: PageProps) {
  const { id } = await params; // if on Next 14, use: const { id } = params;
  const jobIdBig = toBigInt(id);
  const jobIdNum = Number(id);

  // Load JD
  const job = await prisma.jobDescription.findUnique({
    where: { id: jobIdBig },
  });

  if (!job) {
    return (
      <div className="px-6 py-8">
        <h2 className="text-xl font-semibold">Job not found</h2>
        <p className="text-gray-600 mt-2">
          The requested job description does not exist.
        </p>
      </div>
    );
  }

  // Load ranking (ascending rank)
  const candidates = await prisma.candidateScore.findMany({
    where: { job_id: jobIdBig },
    orderBy: { final_rank: "asc" },
  });

  return (
    <div className="bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <header className="mb-6 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-2xl font-bold truncate">
              {job.role_category} — Candidates
            </h2>
            {job.job_description && (
              <p className="mt-2 text-gray-700 whitespace-pre-line">
                {job.job_description}
              </p>
            )}
          </div>

          <div className="shrink-0">
            <ExportCandidatesButton
              jobId={jobIdNum}
              disabled={candidates.length === 0}
            />
          </div>
        </header>

        {/* Send mails control (modal + progress handled inside the component) */}
        <div className="mb-6">
          <SendEmailsControl jobId={jobIdNum} total={candidates.length} />
        </div>

        {/* List */}
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
              const strengths = toList(c.strengths as unknown);
              const weaknesses = toList(c.weaknesses as unknown);
              const score =
                typeof c.final_score === "number"
                  ? c.final_score.toFixed(2)
                  : String(c.final_score);

              return (
                <AccordionItem
                  key={`${c.resume_email ?? c.candidate_name}-${idx}`}
                  value={`candidate-${idx + 1}`}
                  className="px-3 sm:px-4"
                >
                  <AccordionTrigger className="group py-4 hover:no-underline">
                    <div className="flex w-full items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex h-6 min-w-6 items-center justify-center rounded bg-slate-100 px-2 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200">
                            {c.final_rank}
                          </span>
                          <h3 className="truncate text-base font-semibold text-gray-900">
                            {c.candidate_name}
                          </h3>
                        </div>
                        <p className="mt-1 text-sm text-gray-600 truncate">
                          {c.resume_email ?? "—"}
                        </p>
                      </div>
                      <span className="shrink-0 text-sm text-gray-800 font-semibold">
                        {score}%
                      </span>
                    </div>
                  </AccordionTrigger>

                  <AccordionContent>
                    <div className="py-3 sm:py-4">
                      <section className="grid sm:grid-cols-2 gap-4">
                        <div className="rounded-lg border p-3">
                          <h4 className="font-semibold mb-2">Recommendation</h4>
                          <p className="text-sm text-gray-700 whitespace-pre-line">
                            {c.recommendation}
                          </p>
                        </div>

                        <div className="rounded-lg border p-3">
                          <h4 className="font-semibold mb-2">Reasoning</h4>
                          <p className="text-sm text-gray-700 whitespace-pre-line">
                            {c.detailed_reasoning}
                          </p>
                        </div>

                        <div className="rounded-lg border p-3">
                          <h4 className="font-semibold mb-2">Strengths</h4>
                          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
                            {strengths.length > 0 ? (
                              strengths.map((s, i) => <li key={i}>{s}</li>)
                            ) : (
                              <li>—</li>
                            )}
                          </ul>
                        </div>

                        <div className="rounded-lg border p-3">
                          <h4 className="font-semibold mb-2">Weaknesses</h4>
                          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
                            {weaknesses.length > 0 ? (
                              weaknesses.map((w, i) => <li key={i}>{w}</li>)
                            ) : (
                              <li>—</li>
                            )}
                          </ul>
                        </div>

                        <div className="rounded-lg border p-3 sm:col-span-2">
                          <h4 className="font-semibold mb-2">Raw</h4>
                          <pre className="rounded bg-slate-50 p-3 text-xs text-slate-800 overflow-auto">
                            {JSON.stringify(
                              {
                                name: c.candidate_name,
                                email: c.resume_email,
                                final_score: c.final_score,
                                final_rank: c.final_rank,
                              },
                              null,
                              2
                            )}
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
