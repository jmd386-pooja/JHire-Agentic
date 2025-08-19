import { NextResponse } from "next/server";
import prisma from "@/lib/prisma";
import { hash } from "bcryptjs";

export async function POST() {
  try {
    // Hardcoded user details
    const name = "DemoUser";
    const email = "testing@gmail.com";
    const plainPassword = "1234567890";

    // Check if the user already exists
    const existingUser = await prisma.user.findUnique({
      where: { email },
    });

    if (existingUser) {
      return NextResponse.json(
        { error: "Email already exists" },
        { status: 400 }
      );
    }

    // Hash the password
    const hashedPassword = await hash(plainPassword, 12);

    // Create the user with hardcoded details
    const user = await prisma.user.create({
      data: {
        name,
        email,
        password: hashedPassword,
        role: "USER", // Optional: set role explicitly if needed
      },
    });

    const { password: _, ...userWithoutPassword } = user;

    return NextResponse.json(
      { message: "Hardcoded user created successfully", user: userWithoutPassword },
      { status: 201 }
    );
  } catch (error) {
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
