import { PrismaClient } from '@prisma/client';
import { NextRequest, NextResponse } from "next/server";

import { prisma } from "@/lib/prisma";
interface Answer {
  text: string; 
}

export async function GET(request: NextRequest) {
  try {
   const getJD = await prisma.jobDescription.findMany(
    {
      select: {
        id : true,
       job_description: true,
      }
    }
   )
   console.log(getJD);
const jobDescriptions = getJD.map(jd => jd.job_description);

    return NextResponse.json(
      { jobDescriptions },
      { status: 200 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: "Internal server error.", status: 500 }
    );
  }
}
