import { NextRequest, NextResponse } from "next/server";
import { PrismaClient } from "@prisma/client";

import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { candidate_id } = body;
    const candidateId = parseInt(candidate_id);

    if (!candidate_id) {
      return NextResponse.json(
        { error: "candidateId is required" },
        { status: 400 }
      );
    }

    // Fetch the interview from the database
    const interview = await prisma.interview.findUnique({
      where: { candidate_id : candidateId},
    });

    if (!interview) {
      return NextResponse.json(
        { error: "Interview not found" },
        { status: 404 }
      );
    }

    let startTime = interview.interview_start_time;

    // If startTime is null, update it with the current time
    if (!startTime) {
      startTime = new Date();
      await prisma.interview.update({
        where: { candidate_id : candidateId},
        data: { interview_start_time: startTime },
      });
    }

    // Return the start time
    return NextResponse.json({ startTime });
  } catch (error) {
    console.error("Error fetching/updating start time:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
