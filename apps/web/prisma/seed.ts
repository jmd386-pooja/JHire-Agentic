// prisma/seed.ts
import { PrismaClient } from "@prisma/client";

import { prisma } from "@/lib/prisma";

async function main() {
  // Seed Candidate Scores
  await prisma.candidateScore.createMany({
    data: [
      {
        job_id: 2,
        candidate_name: "Jane Doe",
        resume_email: "jane@mail.com",
        final_score: 95,
        final_rank: 1,
        detailed_reasoning: "Strong technical background, clear answers.",
        strengths: "Python, problem solving, communication",
        weaknesses: "Needs more cloud exposure",
        recommendation: "Strongly recommend",
      },
      {
        job_id: 3,
        candidate_name: "John Smith",
        resume_email: "john@mail.com",
        final_score: 82,
        final_rank: 2,
        detailed_reasoning: "Solid fundamentals but less confident in system design.",
        strengths: "SQL, ETL, teamwork",
        weaknesses: "Limited ML exposure",
        recommendation: "Recommend with reservations",
      },
      {
        job_id: 3,
        candidate_name: "Smith",
        resume_email: "joh@mail.com",
        final_score: 70,
        final_rank: 3,
        detailed_reasoning: "Solid fundamentals but less confident in system design.",
        strengths: "SQL teamwork",
        weaknesses: "Limited exposure",
        recommendation: "Recommend with reservations",
      },
      {
        job_id: 3,
        candidate_name: "John",
        resume_email: "john@mail.com",
        final_score: 77,
        final_rank: 2,
        detailed_reasoning: "Solid fundamentals but less confident in system design.",
        strengths: "SQL, ETL, teamwork",
        weaknesses: "Limited ML exposure",
        recommendation: "Recommend with reservations",
      },
      
    ],
  });

  // Seed Job Descriptions
  await prisma.jobDescription.createMany({
    data: [
      {
        job_description: "Data Scientist with experience in machine learning and Python.",
        role_category: "Data Science",
        categorization_confidence: 0.92,
        categorization_reasoning: "Focuses on ML and Python, clear Data Science role",
        key_indicators: JSON.stringify({ skills: ["Python", "Machine Learning", "Statistics"] }),
        total_candidates_evaluated: 0,
      },
      {
        job_description: "Data Engineer experienced in ETL pipelines and SQL.",
        role_category: "Data Engineering",
        categorization_confidence: 0.88,
        categorization_reasoning: "Mentions ETL, pipelines, and SQL, common for Data Engineering",
        key_indicators: { skills: ["ETL", "SQL", "Big Data"] },
        total_candidates_evaluated: 0,
      },
      {
        job_description: "Data Engineer experienced in databricks and SQL.",
        role_category: "Data Engineering",
        categorization_confidence: 0.80,
        categorization_reasoning: "Mentions ETL, databricks, and SQL, common for Data Engineering",
        key_indicators: JSON.stringify({ skills: ["ETL", "SQL", "Big Data"] }),
        total_candidates_evaluated: 0,
      },
    ],
  });
}

main()
  .then(() => prisma.$disconnect())
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
