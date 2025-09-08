import {NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
interface Answer {
  text: string; 
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { candidate_id, Answers }: { candidate_id: string; Answers: Answer[] }  = body;
    
    if (!candidate_id || !Answers) {
      return NextResponse.json(
        { error: "Missing Details." },
        { status: 400 }
      );
    }

    const candidateID = parseInt(candidate_id);
    const answers = Answers.map((item: Answer) => item.text)

    const Interviewscore = await new Promise<number>((resolve, reject) => {
      const pythonProcess = spawn("python", ["ReviewUser.py", JSON.stringify(Answers)]);
      let output = "";
      let errorOutput = "";

      pythonProcess.stdout.on("data", (data) => {
        output += data.toString();
      });
      pythonProcess.stderr.on("data", (data) => {
        errorOutput += data.toString();
      });
      pythonProcess.on("close", (code) => {
        if (code === 0) {
          const parsedScore = parseFloat(output.trim());
          if (isNaN(parsedScore)) {
            resolve(0);
          } else {
            resolve(parsedScore);
          }
        } else {
          resolve(0);
        }
      });
      pythonProcess.on("error", (err) => {
        resolve(0)
      });
    });
    let interview;
    try {
      interview = await prisma.interview.update({
        where: {
          candidate_id: candidateID,
        },
        data: {
          Answers: answers,
          Interviewscore: Interviewscore, 
        },
      });
    } catch (error) {
    }

    return NextResponse.json(
      { message: "Interview saved successfully.", interview },
      { status: 201 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: "Internal server error.", status: 500 }
    );
  }
}
