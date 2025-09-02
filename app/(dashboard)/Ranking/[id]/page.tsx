
import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();


interface Props {
  params: { id: string };
}

export default async function CandidatePage({ params }: Props) {
  const jobId = Number(params.id);

  // fetch job info
  const job = await prisma.jobDescription.findUnique({
    where: { id: jobId },
    select: {
      role_category: true,
      job_description: true,
    },
  });

  if (!job) {
    return <p className="p-6">Job not found</p>;
  }

  // fetch candidates for this JD, ordered by rank
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
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <h2 className="text-2xl font-bold mb-4">
          {job.role_category} — Candidates
        </h2>
        <p className="mb-6 text-gray-700">{job.job_description}</p>

        {candidates.length === 0 ? (
          <p>No candidates found for this job description.</p>
        ) : (
          <div className="grid gap-6">
            {candidates.map((c, idx) => (
              <div
                key={idx}
                className="rounded-xl border shadow p-6 bg-white hover:bg-gray-50 transition"
              >
                <h3 className="text-lg font-semibold">
                  {c.final_rank}. {c.candidate_name}
                </h3>
                <p className="text-gray-600">{c.resume_email}</p>

                <div className="mt-2">
                  <p>
                    <strong>Score:</strong> {c.final_score}
                  </p>
                  <p>
                    <strong>Recommendation:</strong> {c.recommendation}
                  </p>
                </div>

                <div className="mt-4">
                  <p className="font-semibold">Strengths:</p>
                  <pre className="bg-gray-100 rounded p-2 text-sm">
                    {JSON.stringify(c.strengths, null, 2)}
                  </pre>

                  <p className="font-semibold mt-2">Weaknesses:</p>
                  <pre className="bg-gray-100 rounded p-2 text-sm">
                    {JSON.stringify(c.weaknesses, null, 2)}
                  </pre>
                </div>

                <div className="mt-4">
                  <p className="font-semibold">Detailed Reasoning:</p>
                  <p className="text-gray-700">{c.detailed_reasoning}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
