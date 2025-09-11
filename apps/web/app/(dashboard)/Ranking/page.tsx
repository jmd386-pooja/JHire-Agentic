import { prisma } from "@/lib/prisma";
import Link from "next/link";

// ---- helpers ---------------------------------------------------------------

/**
 * Remove "This Job Description categories are ...:" header
 * and return { textWithoutHeader, categories[] }.
 */
function stripHeaderAndGetCategories(raw: string | null): {
  text: string;
  categories: string[];
} {
  const src = (raw ?? "").trim();

  // Match: "This Job Description categories are <list> :"
  // <list> may be comma-separated; we capture it for badges.
  const re = /^This\s+Job\s+Description\s+categories\s+are\s+([^:]*):\s*/i;
  const m = src.match(re);

  if (!m) {
    return { text: src, categories: [] };
  }

  const cats = m[1]
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const text = src.replace(re, ""); // remove the whole header + colon
  return { text, categories: cats };
}

/**
 * Truncate at first newline if present, and also enforce a max length (with ellipsis).
 */
function truncateOnNewline(text: string, maxChars = 200): string {
  // Cut at first newline (either \n or \r\n)
  const nl = text.search(/\r?\n/);
  let out = nl >= 0 ? text.slice(0, nl) : text;

  // Collapse internal whitespace a bit so it looks neat in cards
  out = out.replace(/\s+/g, " ").trim();

  if (out.length > maxChars) {
    out = out.slice(0, maxChars).trimEnd() + "…";
  }
  return out;
}

// ---- page ------------------------------------------------------------------

export default async function RankingPage() {
  const jobs = await prisma.jobDescription.findMany({
    select: {
      id: true,
      job_description: true,
      role_category: true,
    },
    orderBy: { created_at: "desc" },
  });

  return (
    <div className="bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <h2 className="text-3xl font-bold mb-6">Job Descriptions</h2>

        {jobs.length === 0 ? (
          <p className="text-gray-600">No job descriptions found.</p>
        ) : (
          <ul className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
            {jobs.map((job) => {
              const { text, categories } = stripHeaderAndGetCategories(
                job.job_description ?? ""
              );
              const preview = truncateOnNewline(text, 220);

              return (
                <li key={job.id}>
                  <Link href={`/Ranking/${job.id}`} className="block group">
                    <article
                      className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm
                                 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5
                                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                    >
                      {/* Header */}
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <h3 className="text-base font-semibold text-gray-900">
                          {job.role_category || "Untitled Role"}
                        </h3>
                        <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                          #{job.id}
                        </span>
                      </div>

                      {/* Categories as badges (extracted from header we removed) */}
                      {categories.length > 0 && (
                        <div className="mb-3 flex flex-wrap gap-2">
                          {categories.map((cat, i) => (
                            <span
                              key={`${job.id}-cat-${i}`}
                              className="inline-flex items-center rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700
                                         ring-1 ring-inset ring-sky-100"
                            >
                              {cat}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Description preview (truncated at first newline + maxChars) */}
                      <p
                        className="text-sm text-gray-700
                                   overflow-hidden text-ellipsis whitespace-nowrap"
                        title={text} // full text on hover
                      >
                        {preview}
                      </p>

                      {/* Subtle footer hint */}
                      <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
                        <span className="opacity-80">View details</span>
                        <span
                          aria-hidden
                          className="transition-transform duration-200 group-hover:translate-x-0.5"
                        >
                          →
                        </span>
                      </div>
                    </article>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
