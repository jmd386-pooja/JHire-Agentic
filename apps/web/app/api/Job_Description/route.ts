// import { NextResponse } from "next/server";

// // GET all job descriptions
// export async function GET() {
//   const jobDescriptions = [
//     {
//       id: "data-science",
//       title: "Data Science",
//       description:
//         "Responsibilities include building ML models, analyzing data, and working with Python, SQL, and ML frameworks.",
//     },
//     {
//       id: "data-engineering",
//       title: "Data Engineering",
//       description:
//         "Responsibilities include designing pipelines, working with Spark, Airflow, and DBT, and optimizing ETL processes.",
//     },
//     {
//       id: "full-stack",
//       title: "Full Stack",
//       description:
//         "Responsibilities include frontend and backend development, system design, and deployment of scalable applications.",
//     },
//   ];

//   return NextResponse.json(jobDescriptions);
// }

// // POST a new job description
// export async function POST(req: Request) {
//   const body = await req.json();

//   // For now just echo back what was sent
//   return NextResponse.json({
//     message: "Job description created successfully",
//     data: body,
//   });
// }
