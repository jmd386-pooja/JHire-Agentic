const { PrismaClient } = require('@prisma/client');
const bcrypt = require('bcryptjs');

const prisma = new PrismaClient();

async function main() {
  // Static user details
//   const staticUsers = [
//     {
//       email: 'jeffrin@gmail.com',
//       name: 'Jeffrin',
//       password: '1234567890', // plain text password
//       role: 'USER',
//     },
//     {
//       email: 'sabareeshwaran.m@jmangroup.com',
//       name: 'Sabareeshwaran',
//       password: '1234567890', // plain text password
//       role: 'USER',
//     },
//   ];

//   for (const user of staticUsers) {
//     // Check if the user already exists
//     const existingUser = await prisma.user.findUnique({
//       where: { email: user.email },
//     });

//     if (!existingUser) {
//       // Hash the password before saving
//       const hashedPassword = await bcrypt.hash(user.password, 12);

//       await prisma.user.create({
//         data: {
//           email: user.email,
//           name: user.name,
//           password: hashedPassword,
//           role: user.role,
//         },
//       });

//       console.log(`User ${user.email} created successfully.`);
//     } else {
//       console.log(`User ${user.email} already exists. Skipping creation.`);
//     }
//   }
// }

const jobDescriptions = [
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
  ];

  for (const jd of jobDescriptions) {
    const existingJD = await prisma.jobDescription.findFirst({
      where: { job_description: jd.job_description },
    });

    if (!existingJD) {
      await prisma.jobDescription.create({ data: jd });
      console.log(`✅ JobDescription "${jd.role_category}" created successfully.`);
    } else {
      console.log(`⚠️ JobDescription "${jd.role_category}" already exists. Skipping.`);
    }
  }
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
