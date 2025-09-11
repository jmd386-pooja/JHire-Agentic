// /app/api/interviews/route.ts

import { NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';


import { prisma } from "@/lib/prisma";
export async function GET() {
  try {
    const interviews = await prisma.interview.findMany({
      select: {
        id: true,
        candidate_id: true,
        interview_date: true,
        status: true,
        Interviewscore: true,
        Codingscore: true,
        Answers: true,
        code: true,
        created_at: true,
      },
    });

    return NextResponse.json(interviews);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to fetch interview data' }, { status: 500 });
  }
}


