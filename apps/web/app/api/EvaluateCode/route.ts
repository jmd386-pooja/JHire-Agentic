import { PrismaClient } from '@prisma/client';
import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';

import { prisma } from "@/lib/prisma";

export async function POST(req: NextRequest): Promise<Response> {
  try {
    const body = await req.json();
    const { candidateId, questionId, code, language } = body;

    if (!questionId || !code || !language) {
      return new NextResponse(
        JSON.stringify({
          success: false,
          message: 'Missing required fields: questionId, code, or language',
        }),
        { status: 400 }
      );
    }

    const question = await prisma.question.findUnique({
      where: {
        id: questionId,
      },
    });

    if (!question) {
      return new NextResponse(
        JSON.stringify({
          success: false,
          message: 'Resolution Error! Cannot resolve question!',
        }),
        { status: 404 }
      );
    }

    const { internalTestCases } = question;

    if (!internalTestCases) {
      return new NextResponse(
        JSON.stringify({
          success: false,
          message: 'No internal test cases found for this question!',
        }),
        { status: 404 }
      );
    }

    const prompt = `
    You are tasked with evaluating a user's submitted code for a given programming question. 
    The evaluation will be based on factors including 
    a) algorithm correctness
    b) syntax
    c) efficiency
    d) code structure and 
    e) test case 
   The goal is to provide a score out of 100 with the marks distributed across
  factors described above. Your evalauation is strictly based on factors described above..
    Input Provided to You:
        1.The Problem Statement:
            a.A clear and concise description of the question.
            b.Includes constraints, input format, and output format.
        2.User's Code:
            a.The user's submitted code, provided in a specific programming language.
        3.Sample Test Cases:
            a.Test cases provided to the user with expected input and output.
        4.Internal Test Cases:
            a.Hidden test cases (edge cases, large inputs) to ensure robustness and correctness.
    Evaluation Parameters:
        Score the submission based on the following five components:

        1.Correctness (40 points):
            a.Does the code produce the correct output for all sample and internal test cases?
            b.Clearly highlight which test cases fail or succeed.
        2.Algorithmic Approach (20 points):
            a.Is the solution approach appropriate for the problem?
            b.Does it meet the constraints (time complexity and space complexity)?
        3.Code Efficiency (15 points):
            a.Evaluate the time and space complexity.
            b.Does the code scale well for large inputs?
            c.Suggest improvements if a more efficient approach exists.
        4.Code Syntax & Style (15 points):
            a.Is the code syntactically correct and clean?
            b.Check for proper naming conventions, indentation, comments, and readability.
        5.Edge Case Handling (10 points):
            a.Does the code handle edge cases (e.g., empty inputs, large inputs, or boundary values) correctly?
            b.Identify any missing edge cases.

    Return tht output in this Output Format:
    {
        "score": 85, // Total score out of 100
        "feedback": {
            "correctness": "The code passed all sample test cases but failed 2 internal edge cases. Missing handling for negative inputs.",
            "algorithm": "The approach is brute-force (O(n^2)) when a more efficient solution (O(n)) exists using a hashmap.",
            "efficiency": "The current time complexity is O(n^2), which exceeds the constraints for large inputs.",
            "syntax": "The code syntax is clean, but variable names can be more descriptive for clarity.",
            "edgeCases": "Fails for inputs with large negative numbers."
        },
        "failedTestCases": [
            {
            "input": "[-10, -20, -30], target = -50",
            "expectedOutput": "[1,2]",
            "userOutput": "[]"
            }
        ],
        "suggestions": [
            "Optimize the code using a hashmap to reduce the time complexity to O(n).",
            "Add handling for edge cases with negative numbers or very large inputs."
        ]
    }
    Question is : ${question.question},
    Constraints are : ${question.constraints},
    Sample Testcases are : ${question.testcases},
    Internal Testcases are : ${question.internalTestCases},
    Code submitted by user is : ${code},
    Coding Language is : ${language.name}  
    `; 

    return new Promise((resolve, reject) => {
      const pythonProcess = spawn('python', ['EvaluateCode.py', prompt]);

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pythonProcess.on('close', async (res) => {
        if (res === 0) {
          const json_output = JSON.parse(output.replaceAll("```", "").trim().split("json")[1].trim());
          const { score } = json_output;

          await prisma.interview.update({
            where: {
              candidate_id: parseInt(candidateId),
            },
            data: {
              code: code,
              Codingscore: score,
              codeEvaluation: json_output,
            },
          });

          resolve(new NextResponse(JSON.stringify({ nextQuestion: output }), { status: 200 }));
        } else {
          reject(new NextResponse(JSON.stringify({ error: 'Failed to evaluate the given code' }), { status: 500 }));
        }
      });
    });
  } catch (error) {
    console.log("error", error);
    return new NextResponse(JSON.stringify({ error: 'Failed to evaluate the given code' }), { status: 500 });
  }
}
