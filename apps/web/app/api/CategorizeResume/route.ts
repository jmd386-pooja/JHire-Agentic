import { PrismaClient } from "@prisma/client";

import axios from "axios";

import * as dotenv from "dotenv";
import { NextRequest, NextResponse } from "next/server";
 
dotenv.config();
 
const prisma = new PrismaClient();
const mistralApiKey = process.env.MISTRAL_API_KEY!;
const mistralApiEndpoint = "https://api.mistral.ai/v1/chat/completions";
 
const categories = {
    'Data Science': 'machine learning, data analysis, statistics, Python, R',
    'Data Engineering': 'ETL, SQL, Hadoop, Spark, data pipeline',
    'Full Stack': 'JavaScript, React, Node.js, HTML, CSS, MongoDB'
}

async function categorizeResume(resumeText: string): Promise<string> {

  try {

    const response = await axios.post(

      mistralApiEndpoint,

      {

        model: "mistral-tiny", // change to the model you want

        messages: [

          {

            role: "system",

            content:
  `You are an assistant that categorizes resumes into job domains. Return only categories separated by '|'. If none match, return 'Other'.

Here are the categories and their keywords:
${Object.entries(categories)
  .map(([cat, keywords]) => `- ${cat}: ${keywords}`)
  .join('\n')}

Categorize the following resume into one or more of the above categories (you can choose multiple by separating them with "|"):

- Data Science
- Data Engineering
- Full Stack

If the resume clearly does not fit into any of these, return "Other".
Return only the category name(s) exactly as listed above.
Don't add any explanation, quotes, markdown, or additional text. No sentences. Just the category name(s).
You can also give the combination of categories like "Data Science|Data Engineering" if it fits both.

Resume Text:`

          },

          { role: "user", content: resumeText },

        ],

      },

      {

        headers: {

          Authorization: `Bearer ${mistralApiKey}`,

          "Content-Type": "application/json",

        },

      }

    );
 
    const categoryStr =

      response.data?.choices?.[0]?.message?.content?.trim() || "";

    return categoryStr || "Other";

  } catch (error) {

    console.error("Error calling Mistral API:", error);

    return "Other";

  }

}
 


export async function GET(request: NextRequest) {

  await prisma.$connect();
 
  try {

    // fetch all resumes

    const resumes = await prisma.resumeDetails.findMany();
 
    for (const resume of resumes) {

      // Build combined text

      const resumeText = [

        (resume.skills || []).join(" "),

        (resume.projects || []).join(" "),

        (resume.certifications || []).join(" "),

        (resume.experience || []).join(" "),

      ].join(" ");
 
      // Call categorization

      const categoryStr = await categorizeResume(resumeText);

      const categories = categoryStr.split("|");
 
      for (const cat of categories) {
        const type = cat.trim();

        // Check for duplicate (same candidateId and type)
        const exists = await prisma.category.findFirst({
          where: {
            type,
            candidateId: resume.candidateId,
          },
        });

        if (!exists) {
          await prisma.category.create({
            data: {
              type,
              candidateId: resume.candidateId,
              // id will be auto-generated
            },
          });
        } else {
          console.log(`Skipped duplicate category "${type}" for candidate ${resume.candidateId}`);
        }



      }

    }

  } catch (error) {

    console.error("Error processing resumes:", error);

  } finally {

    await prisma.$disconnect();

  }
  return NextResponse.json({ "message": "success"});

}
 
 