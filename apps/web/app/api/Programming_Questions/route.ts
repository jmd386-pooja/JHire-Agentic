import  prisma  from "@/lib/prisma";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    if (
      !body ||
      !body.id ||
      !body.title ||
      !body.question ||
      !body.testcases ||
      !body.internalTestCases ||
      !body.createdAt ||
      !body.constraints
    ) {
      return NextResponse.json(
        { error: "All required fields must be provided." },
        { status: 400 }
      );
    }

    // Additional date validation
    const createdDate = new Date(body.createdAt);
    if (isNaN(createdDate.getTime())) {
      return NextResponse.json(
        { error: "Invalid date format for createdAt." },
        { status: 400 }
      );
    }

    // Create the question entry without 'difficulty'
    const questionEntry = await prisma.question.create({
      data: {
        id: body.id,
        title: body.title,
        question: body.question,
        testcases: body.testcases,
        internalTestCases: body.internalTestCases,
        createdAt: createdDate,
        constraints: body.constraints,
        // No 'difficulty' field here
      },
    });

    return NextResponse.json(questionEntry, { status: 201 });
  } catch (error) {
    console.error("Error creating question:", error);
    return NextResponse.json(
      { error: "An internal server error occurred." },
      { status: 500 }
    );
  }
}


export async function GET() {
  try {
    const questions = await prisma.question.findMany();

    return NextResponse.json(questions, { status: 200 });
  } catch (error) {
    console.error("Error fetching questions:", error);
    return NextResponse.json(
      { error: "An internal server error occurred." },
      { status: 500 }
    );
  }
}


export async function PATCH(request: Request) {
  try {
    const body = await request.json();
    // console.log("Received update body:", body);// Debugging

    if (!body.id) {
      return NextResponse.json(
        { error: "Question ID must be provided." },
        { status: 400 }
      );
    }

    const updatedFields: Partial<{
      question: string;
      title: string;
      testcases: object[];
      internalTestCases: object[];
      constraints: string[];
    }> = {};

    if (body.title) updatedFields.title = body.title;
    if (body.question) updatedFields.question = body.question;
    if (body.testcases) updatedFields.testcases = body.testcases;
    if (body.internalTestCases) updatedFields.internalTestCases = body.internalTestCases;
    if (body.constraints) updatedFields.constraints = body.constraints;

    // No 'difficulty' field to update here
    const updatedQuestion = await prisma.question.update({
      where: { id: body.id },
      data: updatedFields,
    });

    return NextResponse.json(updatedQuestion, { status: 200 });
  } catch (error) {
    console.error("Error updating question:", error);
    return NextResponse.json(
      { error: "An internal server error occurred." },
      { status: 500 }
    );
  }
}
  



export async function DELETE(request: Request) {
  try {
    const { id } = await request.json();
    console.log("Received id for deletion:", id); // Debugging
    if (!id) {
      return NextResponse.json(
        { error: "The 'id' field is required." },
        { status: 400 }
      );
    }

    // Check if the question exists before attempting to delete
    const existingQuestion = await prisma.question.findUnique({
      where: { id },
    });

    if (!existingQuestion) {
      return NextResponse.json(
        { error: `No question found with id: ${id}` },
        { status: 404 }
      );
    }

    // Delete the question entry
    const deletedQuestion = await prisma.question.delete({
      where: { id },
    });

    return NextResponse.json(
      { message: "Question deleted successfully.", deletedQuestion },
      { status: 200 }
    );
  } catch (error) {
    console.error("Error deleting question:", error);
    return NextResponse.json(
      { error: "An internal server error occurred." },
      { status: 500 }
    );
  }
}
 