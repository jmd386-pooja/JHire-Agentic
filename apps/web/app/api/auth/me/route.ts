import { NextResponse } from "next/server";
import { JwtPayload, verify } from "jsonwebtoken";
import prisma from "@/lib/prisma";


export async function GET(req: Request) {
  try {
    const token = req.headers.get("Cookie")?.split("token=")[1]?.split(";")[0];
    if (!token) {
      console.log("No token found in cookies");
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const decoded = verify(token, process.env.JWT_SECRET!) as JwtPayload;
    // Fetch user details from the database
    const user = await prisma.user.findUnique({
      where: { email : decoded.email },
    });

    if (!user) {
      console.log("User not found for email:", decoded.email);
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }


    // Return user details on successful authentication
    return NextResponse.json(
      { name: user.name, email: user.email },
      { status: 200 }
    );
  } catch (error) {
    console.error("Error during authentication:", error);
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
}