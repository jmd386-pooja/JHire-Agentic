import { PrismaClient } from "@prisma/client";
import { NextRequest, NextResponse } from "next/server";

import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { candidate_id, feedback_text, ratings } = body;

    if (!candidate_id || !feedback_text || ratings === undefined) {
      return NextResponse.json({
        success: false,
        message: "Missing required fields: interview_id, feedback_text, or ratings.",
      }, { status: 400 });
    }

    const interview = await prisma.interview.findFirst({
      where: {
        candidate_id: parseInt(candidate_id), 
      }
    });

    if(interview) {
      const existingFeedback = await prisma.feedback.findFirst({
        where: { interview_id : interview?.id },
      });
  
      if (existingFeedback) {
        return NextResponse.json({
          success: false,
          status: 300,
          message: "Feedback already submitted. Thank you !!",
        }, { status: 300 });
      }
  
      const newFeedback = await prisma.feedback.create({
        data: {
          interview_id: interview?.id,
          feedback_text,
          ratings,
        },
      });
  
      return NextResponse.json({
        success: true,
        data: newFeedback,
        status:200
      });
    }
  } catch (error) {
    console.error("Error saving feedback:", error);
    return NextResponse.json({
      success: false,
      message: "Internal Server Error",
    }, { status: 500 });
  } finally {
    await prisma.$disconnect();
  }
}
