import { NextResponse } from "next/server";
import prisma from "@/lib/prisma";

export async function POST(req: Request) {
  try {
    // Parse the JSON body from the request
    const body = await req.json();

    if (!body?.uniqueId) {
      // Return an error if uniqueId is not provided
      return NextResponse.json(
        { error: "Missing uniqueId in request body" },
        { status: 400 }
      );
    }

    const { uniqueId } = body;

    // Check if the uniqueId exists in the database
    const record = await prisma.candidate.findFirst({
      where: { temp_name:uniqueId },
    });

    if (!record) {
      // Return 404 if the record is not found
      return NextResponse.json(
        { error: "Invalid or expired link" },
        { status: 404 }
      );
    }

    // Respond with success if the record exists
    return NextResponse.json({ message: "Valid link" });
  } catch (error) {
    console.error("Error validating link:", error);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}
