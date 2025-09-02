// prisma/seed.ts
import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  await prisma.jobDescription.createMany({
    data: [
      {
        job_description: "We are looking for a Full Stack Developer skilled in React and Node.js.",
        role_category: "Full Stack",
        categorization_confidence: 0.95,
        categorization_reasoning: "JD clearly mentions React and Node.js",
        key_indicators: { skills: ["React", "Node.js", "JavaScript"] },
        total_candidates_evaluated: 0,
      },
      {
        job_description: "Data Scientist with experience in machine learning and Python.",
        role_category: "Data Science",
        categorization_confidence: 0.92,
        categorization_reasoning: "Focuses on ML and Python, clear Data Science role",
        key_indicators: { skills: ["Python", "Machine Learning", "Statistics"] },
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
