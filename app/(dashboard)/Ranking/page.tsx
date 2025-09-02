
// app/Ranking/page.tsx
// import { PrismaClient } from '@prisma/client';
// const prisma = new PrismaClient();


// export default async function RankingPage() {
//   // Fetch job descriptions directly from DB
//   const jobs = await prisma.jobDescription.findMany({
//     select: {
//       id: true,
//       job_description: true,
//       role_category: true,
//     },
//     orderBy: { created_at: "desc" },
//   });

//   return (
//     <div className="min-h-screen bg-white">
//       <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
//         <h2 className="text-3xl font-bold mb-6">Job Descriptions</h2>

//       {jobs.length === 0 ? (
//         <p>No job descriptions found.</p>
//       ) : (
//         <div className="grid gap-4">
//           {jobs.map((job) => (
//             <div
//               key={job.id}
//               className="rounded-xl border cursor-pointer shadow p-7 mb-4 bg-white hover:bg-gray-100 transition"
//             >
//               <h2 className="font-semibold">{job.role_category}</h2>
//               <p className="text-gray-600">{job.job_description}</p>
//             </div>
//           ))}
//         </div>
//       )}
//     </div>
//      </div>
//   );
// }


// app/Ranking/page.tsx
import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();
import Link from "next/link";

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
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <h2 className="text-3xl font-bold mb-6">Job Descriptions</h2>

        {jobs.length === 0 ? (
          <p>No job descriptions found.</p>
        ) : (
          <div className="grid gap-4">
            {jobs.map((job) => (
              <Link key={job.id} href={`/Ranking/${job.id}`}>
                <div className="rounded-xl border cursor-pointer shadow p-7 mb-4 bg-white hover:bg-gray-100 transition">
                  <h2 className="font-semibold">{job.role_category}</h2>
                  <p className="text-gray-600">{job.job_description}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
