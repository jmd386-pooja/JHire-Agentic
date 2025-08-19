import { PrismaClient } from "@prisma/client";
import { NextRequest, NextResponse } from "next/server";

const prisma = new PrismaClient();
interface Question {
  id: string;
  question: string;
  constraints: string[];
  testcases: Array<{
    input: string,
    output: string,
    explanation: string
  }>;
}

export async function POST(request: NextRequest) {
  try {
    // const candidate_id = 2;

    const body = await request.json();
    const { candidate_id } = body;

    const candidateId = parseInt(candidate_id);

    if (!candidate_id) {
      return new Response(
        JSON.stringify({ success: false, message: "candidateId is required" }),
        { status: 400 }
      );
    }

    const interview = await prisma.interview.findUnique({
      where: { candidate_id : candidateId },
    });

    if (!interview) {
      return new Response(
        JSON.stringify({ success: false, message: "Interview not found" }),
        { status: 404 }
      );
    }

    let questionId = interview.questions;

    if (!questionId || questionId.trim() === "") {

      const randomQuestion: Question[] = await prisma.$queryRawUnsafe(`
        SELECT id, question, constraints, testcases 
        FROM "Question" 
        ORDER BY RANDOM() 
        LIMIT 1;
      `);

      if (randomQuestion.length === 0) {
        return new Response(
          JSON.stringify({ success: false, message: "No questions found" }),
          { status: 404 }
        );
      }

      questionId = randomQuestion[0].id;

      await prisma.interview.update({
        where: { candidate_id : candidateId },
        data: { questions: questionId },
      });
    }
    const question: Question[] = await prisma.$queryRawUnsafe(`
      SELECT id, question, constraints, testcases
      FROM "Question" 
      where id =$1;`,
      questionId
    );
      
    if (!question) {
      return new Response(
        JSON.stringify({ success: false, message: "Question not found" }),
        { status: 404 }
      );
    }

    const processedQuestion: Question = {
      id: question[0].id,
      question: question[0].question,
      constraints: question[0].constraints,
      testcases: question[0].testcases.map(item => {
        return {
          input: item.input, 
          output: item.output,
          explanation: item.explanation,
        };
      })
    };
    
    return new Response(
      JSON.stringify({ success: true, data: processedQuestion }),
      { status: 200 }
    );
  } catch (error) {
    console.error("Error processing request:", error);
    return new Response(
      JSON.stringify({ success: false, message: "Internal Server Error" }),
      { status: 500 }
    );
  } finally {
    await prisma.$disconnect();
  }
}
